"""Tests for context metadata edge cases."""
import pytest
from datetime import datetime
import pytz
from src.context.metadata import (
    get_season,
    get_time_of_day,
    get_ordinal_suffix,
    format_date_for_title,
    format_weather_for_prompt,
    get_context_metadata
)


class TestContextMetadataEdgeCases:
    """Test context metadata edge cases and boundary conditions."""
    
    def test_get_season_all_months(self):
        """Test season calculation for all months."""
        assert get_season(12) == "Winter"
        assert get_season(1) == "Winter"
        assert get_season(2) == "Winter"
        assert get_season(3) == "Spring"
        assert get_season(4) == "Spring"
        assert get_season(5) == "Spring"
        assert get_season(6) == "Summer"
        assert get_season(7) == "Summer"
        assert get_season(8) == "Summer"
        assert get_season(9) == "Fall"
        assert get_season(10) == "Fall"
        assert get_season(11) == "Fall"
    
    def test_get_time_of_day_boundaries(self):
        """Test time of day calculation at boundaries."""
        assert get_time_of_day(0) == "night"
        assert get_time_of_day(5) == "morning"  # 5 AM is morning, not night
        assert get_time_of_day(6) == "morning"
        assert get_time_of_day(11) == "morning"
        assert get_time_of_day(12) == "afternoon"
        assert get_time_of_day(16) == "afternoon"
        assert get_time_of_day(17) == "evening"
        assert get_time_of_day(20) == "evening"  # 20 is evening (17 <= hour < 21)
        assert get_time_of_day(21) == "night"  # 21 is night (>= 21 or < 5)
        assert get_time_of_day(22) == "night"
        assert get_time_of_day(23) == "night"
    
    def test_get_ordinal_suffix_all_cases(self):
        """Test ordinal suffix for various numbers."""
        # Standard cases
        assert get_ordinal_suffix(1) == "st"
        assert get_ordinal_suffix(2) == "nd"
        assert get_ordinal_suffix(3) == "rd"
        assert get_ordinal_suffix(4) == "th"
        
        # Special cases (11, 12, 13)
        assert get_ordinal_suffix(11) == "th"
        assert get_ordinal_suffix(12) == "th"
        assert get_ordinal_suffix(13) == "th"
        
        # Teens
        assert get_ordinal_suffix(21) == "st"
        assert get_ordinal_suffix(22) == "nd"
        assert get_ordinal_suffix(23) == "rd"
        assert get_ordinal_suffix(24) == "th"
        
        # Larger numbers
        assert get_ordinal_suffix(101) == "st"
        assert get_ordinal_suffix(102) == "nd"
        assert get_ordinal_suffix(103) == "rd"
        assert get_ordinal_suffix(111) == "th"  # Special case
        assert get_ordinal_suffix(112) == "th"
        assert get_ordinal_suffix(113) == "th"
    
    def test_format_date_for_title_all_fields(self):
        """Test date formatting with all fields."""
        metadata = {
            'day_of_week': 'Monday',
            'month': 'December',
            'day': 11,
            'year': 2025,
            'time_of_day': 'morning'
        }
        title = format_date_for_title(metadata)
        
        assert 'Monday' in title
        assert 'December' in title
        assert '11th' in title
        assert '2025' in title
        assert 'Morning' in title
    
    def test_format_weather_for_prompt_none(self):
        """Test weather formatting with None."""
        result = format_weather_for_prompt(None)
        assert "unavailable" in result.lower() or "normal" in result.lower()
    
    def test_format_weather_for_prompt_empty_dict(self):
        """Test weather formatting with empty dictionary."""
        result = format_weather_for_prompt({})
        assert "unavailable" in result.lower() or "unknown" in result.lower()
    
    def test_get_context_metadata_weekend_detection(self):
        """Test weekend detection in context metadata."""
        # This is a bit tricky - we need to test with known dates
        # For now, just verify the field exists
        metadata = get_context_metadata()
        assert 'is_weekend' in metadata
        assert isinstance(metadata['is_weekend'], bool)
    
    def test_get_context_metadata_with_weather(self):
        """Test context metadata with weather data."""
        weather = {
            'temperature': 72,
            'summary': 'Sunny'
        }
        metadata = get_context_metadata(weather_data=weather)
        
        assert 'weather' in metadata
        assert metadata['weather'] == weather
    
    def test_get_context_metadata_with_observation_type(self):
        """Test context metadata with observation type."""
        metadata = get_context_metadata(observation_type='morning')
        assert metadata['observation_type'] == 'morning'
        
        metadata = get_context_metadata(observation_type='evening')
        assert metadata['observation_type'] == 'evening'
    
    def test_get_context_metadata_all_fields(self):
        """Test that context metadata includes all expected fields."""
        metadata = get_context_metadata()
        
        required_fields = [
            'date', 'time', 'day_of_week', 'month', 'day', 'year',
            'season', 'time_of_day', 'is_weekend', 'robot_name'
        ]
        
        for field in required_fields:
            assert field in metadata, f"Missing field: {field}"

