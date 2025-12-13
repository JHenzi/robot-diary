"""Tests for context metadata generation."""
import pytest
from datetime import datetime
import pytz
from src.context.metadata import (
    get_context_metadata,
    format_context_for_prompt,
    format_weather_for_prompt,
    get_season,
    get_time_of_day,
    format_date_for_title
)


class TestContextMetadata:
    """Test context metadata functions."""
    
    def test_get_season(self):
        """Test season calculation."""
        assert get_season(12) == "Winter"
        assert get_season(1) == "Winter"
        assert get_season(2) == "Winter"
        assert get_season(3) == "Spring"
        assert get_season(6) == "Summer"
        assert get_season(9) == "Fall"
    
    def test_get_time_of_day(self):
        """Test time of day calculation."""
        assert get_time_of_day(6) == "morning"
        assert get_time_of_day(10) == "morning"
        assert get_time_of_day(12) == "afternoon"
        assert get_time_of_day(15) == "afternoon"
        assert get_time_of_day(17) == "evening"
        assert get_time_of_day(20) == "evening"
        assert get_time_of_day(22) == "night"
        assert get_time_of_day(2) == "night"
    
    def test_get_context_metadata(self):
        """Test context metadata generation."""
        metadata = get_context_metadata()
        
        assert isinstance(metadata, dict)
        assert 'date' in metadata
        assert 'time' in metadata
        assert 'day_of_week' in metadata
        assert 'season' in metadata
        assert 'time_of_day' in metadata
        assert 'is_weekend' in metadata
        assert 'robot_name' in metadata
        assert metadata['robot_name'] == "B3N-T5-MNT"
        
        # New optional fields (may or may not be present depending on libraries)
        assert 'is_holiday' in metadata
        assert 'day_of_year' in metadata
        assert 'season_progress' in metadata
        assert 'days_until_next_season' in metadata
        assert 'is_equinox' in metadata
        assert 'is_solstice' in metadata
    
    def test_get_context_metadata_with_weather(self):
        """Test context metadata with weather data."""
        weather_data = {
            'summary': 'Partly Cloudy',
            'temperature': 72
        }
        metadata = get_context_metadata(weather_data=weather_data)
        
        assert 'weather' in metadata
        assert metadata['weather'] == weather_data
    
    def test_get_context_metadata_with_observation_type(self):
        """Test context metadata with observation type."""
        metadata = get_context_metadata(observation_type='morning')
        assert metadata['observation_type'] == 'morning'
        
        metadata = get_context_metadata(observation_type='evening')
        assert metadata['observation_type'] == 'evening'
    
    def test_format_context_for_prompt(self):
        """Test context formatting for prompts."""
        metadata = get_context_metadata()
        formatted = format_context_for_prompt(metadata)
        
        assert isinstance(formatted, str)
        assert len(formatted) > 0
        assert metadata['day_of_week'] in formatted
        assert metadata['date'] in formatted
    
    def test_format_context_for_prompt_with_holiday(self):
        """Test context formatting with holiday."""
        # Create metadata with a holiday (e.g., Christmas)
        metadata = get_context_metadata()
        metadata['is_holiday'] = True
        metadata['holidays'] = ['Christmas Day']
        
        formatted = format_context_for_prompt(metadata)
        assert 'Christmas' in formatted
    
    def test_format_context_for_prompt_with_moon(self):
        """Test context formatting with moon phase."""
        metadata = get_context_metadata()
        metadata['moon'] = {
            'phase_name': 'full moon',
            'is_key_event': True,
            'moon_event': 'full moon'
        }
        
        formatted = format_context_for_prompt(metadata)
        # Should include moon info if it's a key event
        assert isinstance(formatted, str)
    
    def test_format_context_for_prompt_missing_optional_data(self):
        """Test that formatting works gracefully when optional data is missing."""
        metadata = get_context_metadata()
        # Remove optional fields
        metadata.pop('moon', None)
        metadata.pop('sun', None)
        metadata['is_holiday'] = False
        metadata.pop('holidays', None)
        
        formatted = format_context_for_prompt(metadata)
        assert isinstance(formatted, str)
        assert len(formatted) > 0
        # Should still include basic context
        assert metadata['day_of_week'] in formatted
    
    def test_format_weather_for_prompt(self):
        """Test weather formatting for prompts."""
        weather_data = {
            'summary': 'Partly Cloudy',
            'temperature': 72,
            'wind_speed': 5
        }
        formatted = format_weather_for_prompt(weather_data)
        
        assert isinstance(formatted, str)
        assert len(formatted) > 0
        assert '72' in formatted or 'Partly' in formatted.lower()
    
    def test_format_weather_for_prompt_no_data(self):
        """Test weather formatting with no data."""
        formatted = format_weather_for_prompt(None)
        assert isinstance(formatted, str)
        assert 'unavailable' in formatted.lower() or 'normal' in formatted.lower()
    
    def test_format_date_for_title(self):
        """Test date formatting for post titles."""
        metadata = {
            'day_of_week': 'Monday',
            'month': 'December',
            'day': 11,
            'year': 2025,
            'time_of_day': 'morning'  # Required by format_date_for_title
        }
        title = format_date_for_title(metadata)
        
        assert isinstance(title, str)
        assert 'Monday' in title
        assert 'December' in title
        assert '11' in title or '11th' in title
        assert 'Morning' in title or 'morning' in title
    
    def test_get_ordinal_suffix(self):
        """Test ordinal suffix generation."""
        from src.context.metadata import get_ordinal_suffix
        
        assert get_ordinal_suffix(1) == "st"
        assert get_ordinal_suffix(2) == "nd"
        assert get_ordinal_suffix(3) == "rd"
        assert get_ordinal_suffix(4) == "th"
        assert get_ordinal_suffix(11) == "th"  # Special case
        assert get_ordinal_suffix(21) == "st"
        assert get_ordinal_suffix(22) == "nd"

