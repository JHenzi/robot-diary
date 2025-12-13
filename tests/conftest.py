"""Pytest configuration and shared fixtures."""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment(tmp_path_factory):
    """Set up test environment before any imports."""
    # Set required environment variables
    os.environ['GROQ_API_KEY'] = 'test_key_for_testing_only_minimum_10_chars'
    os.environ['YOUTUBE_STREAM_URL'] = 'https://www.youtube.com/watch?v=test123'
    
    # Create minimal Hugo structure for validation
    hugo_dir = tmp_path_factory.mktemp('hugo')
    (hugo_dir / 'hugo.toml').touch()
    os.environ['HUGO_SITE_PATH'] = str(hugo_dir)
    
    # Reload config if already imported
    if 'src.config' in sys.modules:
        import importlib
        importlib.reload(sys.modules['src.config'])

