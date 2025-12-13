"""Tests for memory manager functionality."""
import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock


class TestMemoryManager:
    """Test memory manager operations."""
    
    @pytest.fixture
    def temp_memory_dir(self):
        """Create a temporary directory for memory files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def memory_manager(self, temp_memory_dir):
        """Create a MemoryManager instance with temp directory."""
        # Create file paths in temp directory
        memory_file = temp_memory_dir / 'observations.json'
        schedule_file = temp_memory_dir / 'schedule.json'
        
        # Import manager
        from src.memory.manager import MemoryManager
        
        # Create manager and directly set its file paths
        manager = MemoryManager()
        manager.memory_file = memory_file
        
        # Also patch SCHEDULE_FILE for schedule operations
        with patch('src.memory.manager.SCHEDULE_FILE', schedule_file):
            yield manager
    
    def test_memory_manager_initialization(self, memory_manager):
        """Test memory manager initialization."""
        assert memory_manager is not None
        assert memory_manager.get_total_count() == 0
    
    def test_add_observation(self, memory_manager, temp_memory_dir):
        """Test adding an observation."""
        # Create a dummy image file
        image_path = temp_memory_dir / 'test_image.jpg'
        image_path.touch()
        
        diary_entry = "This is a test diary entry."
        memory_manager.add_observation(image_path, diary_entry)
        
        assert memory_manager.get_total_count() == 1
        
        # Check that observations.json was created
        observations_file = temp_memory_dir / 'observations.json'
        assert observations_file.exists()
        
        # Verify content
        with open(observations_file, 'r') as f:
            observations = json.load(f)
            assert len(observations) == 1
            assert observations[0]['content'] == diary_entry
            assert observations[0]['id'] == 1
    
    def test_get_recent_memory(self, memory_manager, temp_memory_dir):
        """Test getting recent memory entries."""
        # Add multiple observations
        for i in range(5):
            image_path = temp_memory_dir / f'test_image_{i}.jpg'
            image_path.touch()
            memory_manager.add_observation(image_path, f"Entry {i}")
        
        recent = memory_manager.get_recent_memory(count=3)
        assert len(recent) == 3
        assert recent[-1]['id'] == 5  # Most recent last (returns last N)
        assert recent[0]['id'] == 3
    
    def test_get_total_count(self, memory_manager, temp_memory_dir):
        """Test getting total observation count."""
        assert memory_manager.get_total_count() == 0
        
        for i in range(3):
            image_path = temp_memory_dir / f'test_image_{i}.jpg'
            image_path.touch()
            memory_manager.add_observation(image_path, f"Entry {i}")
        
        assert memory_manager.get_total_count() == 3
    
    def test_get_first_observation_date(self, memory_manager, temp_memory_dir):
        """Test getting first observation date."""
        # Test with no observations
        first_date = memory_manager.get_first_observation_date()
        assert first_date is None
        
        # Add first observation
        image_path = temp_memory_dir / 'test_image_1.jpg'
        image_path.touch()
        memory_manager.add_observation(image_path, "First entry")
        
        first_date = memory_manager.get_first_observation_date()
        assert first_date is not None
        assert isinstance(first_date, datetime)
        
        # Add more observations - first date should remain the same
        image_path2 = temp_memory_dir / 'test_image_2.jpg'
        image_path2.touch()
        memory_manager.add_observation(image_path2, "Second entry")
        
        first_date2 = memory_manager.get_first_observation_date()
        assert first_date2 is not None
        assert first_date2 == first_date  # Should be the same as first
    
    def test_save_and_load_schedule(self, memory_manager, temp_memory_dir):
        """Test saving and loading schedule."""
        from datetime import datetime
        import pytz
        from src.config import LOCATION_TIMEZONE
        
        tz = pytz.timezone(LOCATION_TIMEZONE)
        next_time = datetime.now(tz).replace(hour=8, minute=30)
        
        # Patch SCHEDULE_FILE for this test
        schedule_file = temp_memory_dir / 'schedule.json'
        with patch('src.memory.manager.SCHEDULE_FILE', schedule_file):
            memory_manager.save_next_scheduled_time(next_time, 'morning')
            
            schedule_info = memory_manager.get_next_scheduled_time()
            assert schedule_info is not None
            assert schedule_info['type'] == 'morning'
            assert 'datetime' in schedule_info
