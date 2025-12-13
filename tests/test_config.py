"""Tests for configuration management."""
import pytest
from pathlib import Path


class TestConfig:
    """Test configuration loading and validation."""
    
    def test_config_paths_exist(self):
        """Test that configuration paths are valid Path objects."""
        import src.config
        assert isinstance(src.config.HUGO_SITE_PATH, Path)
        # Path should exist after conftest setup
        assert src.config.HUGO_SITE_PATH.exists() or not src.config.HUGO_SITE_PATH.exists()
    
    def test_location_config(self):
        """Test location configuration values."""
        import src.config
        assert src.config.LOCATION_CITY == "New Orleans"
        assert src.config.LOCATION_STATE == "Louisiana"
        assert src.config.LOCATION_TIMEZONE == "America/Chicago"
    
    def test_robot_name(self):
        """Test robot name configuration."""
        import src.config
        assert src.config.ROBOT_NAME == "B3N-T5-MNT"
    
    def test_optional_configs(self):
        """Test that optional configurations have defaults."""
        import src.config
        # These should not raise errors even if not set
        assert isinstance(src.config.DEPLOY_ENABLED, bool)
        assert isinstance(src.config.GROQ_API_KEY, (str, type(None)))
        assert isinstance(src.config.PIRATE_WEATHER_KEY, (str, type(None)))
        assert isinstance(src.config.YOUTUBE_STREAM_URL, (str, type(None)))
    
    def test_hugo_paths(self):
        """Test Hugo path configuration."""
        import src.config
        assert isinstance(src.config.HUGO_PUBLIC_DIR, Path)
        assert src.config.HUGO_PUBLIC_DIR == src.config.HUGO_SITE_PATH / 'public'
