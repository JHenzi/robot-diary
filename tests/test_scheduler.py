"""Tests for scheduler functionality."""
import pytest
from datetime import datetime, time
import pytz
from src.scheduler import (
    get_random_morning_time,
    get_random_evening_time,
    get_next_observation_time,
    is_time_for_observation,
    get_observation_schedule_summary
)


class TestScheduler:
    """Test scheduler functions."""
    
    def test_get_random_morning_time(self):
        """Test that morning time is within expected range."""
        morning_time = get_random_morning_time()
        assert isinstance(morning_time, time)
        # Should be between 7:30 AM (450 minutes) and 9:30 AM (570 minutes)
        total_minutes = morning_time.hour * 60 + morning_time.minute
        assert 450 <= total_minutes <= 570
    
    def test_get_random_evening_time_weekday(self):
        """Test weekday evening time range."""
        evening_time, is_next_day = get_random_evening_time(is_weekend=False)
        assert isinstance(evening_time, time)
        assert isinstance(is_next_day, bool)
        assert is_next_day is False  # Weekday times should not be next day
        # Should be between 4:00 PM (960 minutes) and 6:00 PM (1080 minutes)
        total_minutes = evening_time.hour * 60 + evening_time.minute
        assert 960 <= total_minutes <= 1080
    
    def test_get_random_evening_time_weekend(self):
        """Test weekend evening time range."""
        evening_time, is_next_day = get_random_evening_time(is_weekend=True)
        assert isinstance(evening_time, time)
        assert isinstance(is_next_day, bool)
        # Weekend can be 6:00 PM (1080) to 1:00 AM next day (1500)
        total_minutes = evening_time.hour * 60 + evening_time.minute
        if is_next_day:
            # Next day, so hour should be 0-1
            assert evening_time.hour < 2
        else:
            # Same day, should be 18:00-24:00
            assert 1080 <= total_minutes <= 1440
    
    def test_get_next_observation_time(self):
        """Test next observation time calculation."""
        from src.config import LOCATION_TIMEZONE
        tz = pytz.timezone(LOCATION_TIMEZONE)
        
        # Test with current time
        now = datetime.now(tz)
        next_time, obs_type = get_next_observation_time(now)
        
        assert isinstance(next_time, datetime)
        assert next_time.tzinfo is not None
        assert obs_type in ['morning', 'evening']
        assert next_time > now  # Should be in the future
    
    def test_is_time_for_observation(self):
        """Test observation time checking."""
        from src.config import LOCATION_TIMEZONE
        from datetime import timedelta
        tz = pytz.timezone(LOCATION_TIMEZONE)
        
        now = datetime.now(tz)
        scheduled = now + timedelta(minutes=2)  # 2 minutes in future
        
        # Should be within tolerance (default 5 minutes)
        assert is_time_for_observation(now, scheduled, tolerance_minutes=5) is True
        
        # Should not be within tolerance if too far
        scheduled_far = now + timedelta(minutes=10)
        assert is_time_for_observation(now, scheduled_far, tolerance_minutes=5) is False
    
    def test_get_observation_schedule_summary(self):
        """Test schedule summary formatting."""
        from src.config import LOCATION_TIMEZONE
        tz = pytz.timezone(LOCATION_TIMEZONE)
        
        next_time = datetime.now(tz).replace(hour=8, minute=30)
        summary = get_observation_schedule_summary(next_time, 'morning')
        
        assert isinstance(summary, str)
        assert 'morning' in summary.lower()
        assert '8:30' in summary or '08:30' in summary

