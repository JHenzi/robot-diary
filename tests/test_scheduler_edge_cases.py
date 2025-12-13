"""Tests for scheduler edge cases and boundary conditions."""
import pytest
from datetime import datetime, time
import pytz
from src.scheduler import (
    get_random_morning_time,
    get_random_evening_time,
    get_next_observation_time,
    is_time_for_observation
)


class TestSchedulerEdgeCases:
    """Test scheduler edge cases and boundary conditions."""
    
    def test_morning_time_boundaries(self):
        """Test that morning times are within expected boundaries."""
        for _ in range(10):  # Test multiple random generations
            morning_time = get_random_morning_time()
            total_minutes = morning_time.hour * 60 + morning_time.minute
            assert 450 <= total_minutes <= 570  # 7:30 AM to 9:30 AM
    
    def test_evening_time_weekday_boundaries(self):
        """Test weekday evening time boundaries."""
        for _ in range(10):
            evening_time, is_next_day = get_random_evening_time(is_weekend=False)
            assert is_next_day is False
            total_minutes = evening_time.hour * 60 + evening_time.minute
            assert 960 <= total_minutes <= 1080  # 4:00 PM to 6:00 PM
    
    def test_evening_time_weekend_boundaries(self):
        """Test weekend evening time boundaries."""
        for _ in range(10):
            evening_time, is_next_day = get_random_evening_time(is_weekend=True)
            total_minutes = evening_time.hour * 60 + evening_time.minute
            if is_next_day:
                # Next day, should be 0:00 to 1:00
                assert evening_time.hour < 2
            else:
                # Same day, should be 18:00 to 24:00
                assert 1080 <= total_minutes <= 1440
    
    def test_is_time_for_observation_exact_match(self):
        """Test observation time check with exact match."""
        from src.config import LOCATION_TIMEZONE
        tz = pytz.timezone(LOCATION_TIMEZONE)
        
        now = datetime.now(tz)
        scheduled = now  # Exact match
        
        assert is_time_for_observation(now, scheduled, tolerance_minutes=5) is True
    
    def test_is_time_for_observation_within_tolerance(self):
        """Test observation time check within tolerance."""
        from src.config import LOCATION_TIMEZONE
        from datetime import timedelta
        tz = pytz.timezone(LOCATION_TIMEZONE)
        
        now = datetime.now(tz)
        scheduled = now + timedelta(minutes=3)  # 3 minutes in future
        
        assert is_time_for_observation(now, scheduled, tolerance_minutes=5) is True
    
    def test_is_time_for_observation_at_tolerance_boundary(self):
        """Test observation time check at tolerance boundary."""
        from src.config import LOCATION_TIMEZONE
        from datetime import timedelta
        tz = pytz.timezone(LOCATION_TIMEZONE)
        
        now = datetime.now(tz)
        scheduled = now + timedelta(minutes=5)  # Exactly 5 minutes
        
        assert is_time_for_observation(now, scheduled, tolerance_minutes=5) is True
    
    def test_is_time_for_observation_past_tolerance(self):
        """Test observation time check past tolerance."""
        from src.config import LOCATION_TIMEZONE
        from datetime import timedelta
        tz = pytz.timezone(LOCATION_TIMEZONE)
        
        now = datetime.now(tz)
        scheduled = now + timedelta(minutes=6)  # 6 minutes in future
        
        assert is_time_for_observation(now, scheduled, tolerance_minutes=5) is False
    
    def test_is_time_for_observation_past_time(self):
        """Test observation time check with past scheduled time."""
        from src.config import LOCATION_TIMEZONE
        from datetime import timedelta
        tz = pytz.timezone(LOCATION_TIMEZONE)
        
        now = datetime.now(tz)
        scheduled = now - timedelta(minutes=10)  # 10 minutes in past (outside tolerance)
        
        assert is_time_for_observation(now, scheduled, tolerance_minutes=5) is False
    
    def test_get_next_observation_time_future(self):
        """Test that next observation time is always in the future."""
        from src.config import LOCATION_TIMEZONE
        tz = pytz.timezone(LOCATION_TIMEZONE)
        
        now = datetime.now(tz)
        next_time, obs_type = get_next_observation_time(now)
        
        assert next_time > now
        assert obs_type in ['morning', 'evening']
    
    def test_get_next_observation_time_timezone_aware(self):
        """Test that next observation time is timezone-aware."""
        from src.config import LOCATION_TIMEZONE
        tz = pytz.timezone(LOCATION_TIMEZONE)
        
        now = datetime.now(tz)
        next_time, _ = get_next_observation_time(now)
        
        assert next_time.tzinfo is not None
        # Compare timezone names instead of objects (pytz timezone objects can differ)
        assert str(next_time.tzinfo) == str(tz) or next_time.tzinfo.zone == tz.zone

