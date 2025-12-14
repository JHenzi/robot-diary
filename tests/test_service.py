"""Tests for service module, focusing on next scheduled time logic."""
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pytz

from src.memory.manager import MemoryManager
from src.scheduler import get_next_observation_time


class TestServiceNextScheduledTime:
    """Test that next scheduled time is calculated correctly after observations."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def mock_memory_manager(self, temp_dir):
        """Create a MemoryManager with temp directory."""
        memory_file = temp_dir / 'observations.json'
        schedule_file = temp_dir / 'schedule.json'
        
        # Patch the module-level constants so MemoryManager uses temp files
        with patch('src.memory.manager.MEMORY_FILE', memory_file), \
             patch('src.memory.manager.SCHEDULE_FILE', schedule_file):
            manager = MemoryManager()
            yield manager
    
    @pytest.fixture
    def location_tz(self):
        """Get location timezone."""
        from src.config import LOCATION_TIMEZONE
        return pytz.timezone(LOCATION_TIMEZONE)
    
    def test_next_scheduled_time_calculated_after_observation(self, mock_memory_manager, location_tz, temp_dir):
        """Test that next scheduled time is calculated AFTER saving observation, not before."""
        # Set up initial state: no saved schedule
        assert mock_memory_manager.get_next_scheduled_time() is None
        
        # Mock the observation cycle components
        mock_image_path = temp_dir / 'test_image.jpg'
        mock_image_path.touch()
        
        mock_diary_entry = "Test diary entry"
        
        # Ensure patches are active for MemoryManager instantiation inside run_observation_cycle
        memory_file = temp_dir / 'observations.json'
        schedule_file = temp_dir / 'schedule.json'
        
        # Mock all external dependencies
        with patch('src.memory.manager.MEMORY_FILE', memory_file), \
             patch('src.memory.manager.SCHEDULE_FILE', schedule_file), \
             patch('src.service.fetch_latest_image', return_value=mock_image_path), \
             patch('src.service.GroqClient') as mock_groq_class, \
             patch('src.service.HugoGenerator') as mock_hugo_class, \
             patch('src.service.get_context_metadata') as mock_context, \
             patch('src.service.generate_dynamic_prompt', return_value="Mock prompt"), \
             patch('src.service.create_diary_entry', return_value=mock_diary_entry), \
             patch('src.service.PirateWeatherClient'):
            
            # Set up mocks
            mock_llm_client = Mock()
            mock_llm_client.generate_prompt.return_value = "Mock prompt"
            mock_llm_client.create_diary_entry.return_value = mock_diary_entry
            mock_groq_class.return_value = mock_llm_client
            
            mock_hugo_gen = Mock()
            mock_hugo_gen.create_post.return_value = temp_dir / 'post.md'
            mock_hugo_gen.build_site.return_value = True
            mock_hugo_class.return_value = mock_hugo_gen
            
            mock_context.return_value = {
                'date': 'December 13, 2025',
                'time': '10:00 AM',
                'timezone': 'CST',
                'day_of_week': 'Friday',
                'season': 'Winter',
                'time_of_day': 'morning',
                'observation_type': 'morning'
            }
            
            # Import and run observation cycle
            from src.service import run_observation_cycle
            
            # Record the time before the observation
            before_time = datetime.now(location_tz)
            
            # Run the observation cycle
            run_observation_cycle(observation_type='morning')
            
            # Record the time after the observation
            after_time = datetime.now(location_tz)
            
            # Verify that a next scheduled time was saved
            scheduled_info = mock_memory_manager.get_next_scheduled_time()
            assert scheduled_info is not None
            assert 'datetime' in scheduled_info
            
            # Parse the saved scheduled time
            next_time = datetime.fromisoformat(scheduled_info['datetime'])
            if next_time.tzinfo is None:
                next_time = location_tz.localize(next_time)
            else:
                next_time = next_time.astimezone(location_tz)
            
            # CRITICAL: The next scheduled time should be AFTER the observation completed
            # It should be in the future relative to when we finished
            assert next_time > after_time, \
                f"Next scheduled time ({next_time}) should be after observation completed ({after_time})"
            
            # It should also be after the before_time (sanity check)
            assert next_time > before_time, \
                f"Next scheduled time ({next_time}) should be after observation started ({before_time})"
            
            # Verify it's a reasonable time in the future (at least a few minutes)
            time_diff = (next_time - after_time).total_seconds()
            assert time_diff > 60, \
                f"Next scheduled time should be at least 1 minute in the future, got {time_diff} seconds"
    
    def test_next_scheduled_time_is_future_time(self, mock_memory_manager, location_tz, temp_dir):
        """Test that calculated next scheduled time is always in the future."""
        # Set up: save an observation first
        mock_image_path = temp_dir / 'test_image.jpg'
        mock_image_path.touch()
        
        mock_llm_client = Mock()
        mock_llm_client.generate_memory_summary.return_value = "Test summary"
        
        mock_memory_manager.add_observation(
            mock_image_path,
            "Test entry",
            llm_client=mock_llm_client
        )
        
        # Now calculate next scheduled time
        now = datetime.now(location_tz)
        next_time, next_obs_type = get_next_observation_time(now)
        
        # Verify it's in the future
        assert next_time > now, \
            f"Next scheduled time ({next_time}) should be after current time ({now})"
        
        # Save it
        mock_memory_manager.save_next_scheduled_time(next_time, next_obs_type)
        
        # Retrieve and verify
        scheduled_info = mock_memory_manager.get_next_scheduled_time()
        assert scheduled_info is not None
        
        retrieved_time = datetime.fromisoformat(scheduled_info['datetime'])
        if retrieved_time.tzinfo is None:
            retrieved_time = location_tz.localize(retrieved_time)
        else:
            retrieved_time = retrieved_time.astimezone(location_tz)
        
        # Should still be in the future
        current_time = datetime.now(location_tz)
        assert retrieved_time > current_time, \
            f"Retrieved scheduled time ({retrieved_time}) should be after current time ({current_time})"
    
    def test_next_scheduled_time_included_in_post(self, mock_memory_manager, location_tz, temp_dir):
        """Test that the next scheduled time is included in the Hugo post content."""
        # Set up mocks
        mock_image_path = temp_dir / 'test_image.jpg'
        mock_image_path.touch()
        
        mock_diary_entry = "Test diary entry content"
        
        # Ensure patches are active for MemoryManager instantiation inside run_observation_cycle
        memory_file = temp_dir / 'observations.json'
        schedule_file = temp_dir / 'schedule.json'
        
        with patch('src.memory.manager.MEMORY_FILE', memory_file), \
             patch('src.memory.manager.SCHEDULE_FILE', schedule_file), \
             patch('src.service.fetch_latest_image', return_value=mock_image_path), \
             patch('src.service.GroqClient') as mock_groq_class, \
             patch('src.service.HugoGenerator') as mock_hugo_class, \
             patch('src.service.get_context_metadata') as mock_context, \
             patch('src.service.generate_dynamic_prompt', return_value="Mock prompt"), \
             patch('src.service.create_diary_entry', return_value=mock_diary_entry), \
             patch('src.service.PirateWeatherClient'):
            
            mock_llm_client = Mock()
            mock_llm_client.generate_prompt.return_value = "Mock prompt"
            mock_llm_client.create_diary_entry.return_value = mock_diary_entry
            mock_groq_class.return_value = mock_llm_client
            
            mock_hugo_gen = Mock()
            mock_hugo_gen.create_post.return_value = temp_dir / 'post.md'
            mock_hugo_gen.build_site.return_value = True
            mock_hugo_class.return_value = mock_hugo_gen
            
            mock_context.return_value = {
                'date': 'December 13, 2025',
                'time': '10:00 AM',
                'timezone': 'CST',
                'day_of_week': 'Friday',
                'season': 'Winter',
                'time_of_day': 'morning',
                'observation_type': 'morning'
            }
            
            from src.service import run_observation_cycle
            
            # Run the observation cycle
            run_observation_cycle(observation_type='morning')
            
            # Verify that create_post was called with diary entry containing next scheduled time
            assert mock_hugo_gen.create_post.called
            
            # Get the arguments passed to create_post
            call_args = mock_hugo_gen.create_post.call_args
            diary_entry_with_schedule = call_args[0][0]  # First positional argument
            
            # Verify the diary entry includes the next scheduled time
            assert "Next scheduled observation" in diary_entry_with_schedule
            assert "CST" in diary_entry_with_schedule or "CDT" in diary_entry_with_schedule
            
            # Verify the original diary entry is still there
            assert mock_diary_entry in diary_entry_with_schedule
    
    def test_news_based_observation_also_calculates_next_time(self, mock_memory_manager, location_tz, temp_dir):
        """Test that news-based observations also calculate next scheduled time correctly."""
        # Ensure patches are active for MemoryManager instantiation inside run_news_based_observation
        memory_file = temp_dir / 'observations.json'
        schedule_file = temp_dir / 'schedule.json'
        
        # Set up mocks
        with patch('src.memory.manager.MEMORY_FILE', memory_file), \
             patch('src.memory.manager.SCHEDULE_FILE', schedule_file), \
             patch('src.service.GroqClient') as mock_groq_class, \
             patch('src.service.HugoGenerator') as mock_hugo_class, \
             patch('src.service.get_context_metadata') as mock_context, \
             patch('src.service.get_random_cluster') as mock_cluster, \
             patch('src.service.get_cluster_articles') as mock_articles, \
             patch('src.service.PirateWeatherClient'):
            
            mock_llm_client = Mock()
            mock_llm_client.generate_prompt.return_value = "Mock prompt"
            mock_llm_client.create_diary_entry_from_text.return_value = "News-based entry"
            mock_groq_class.return_value = mock_llm_client
            
            mock_hugo_gen = Mock()
            mock_hugo_gen.create_post.return_value = temp_dir / 'post.md'
            mock_hugo_gen.build_site.return_value = True
            mock_hugo_class.return_value = mock_hugo_gen
            
            mock_context.return_value = {
                'date': 'December 13, 2025',
                'time': '10:00 AM',
                'timezone': 'CST',
                'day_of_week': 'Friday',
                'season': 'Winter',
                'time_of_day': 'morning',
                'observation_type': 'morning'
            }
            
            mock_cluster.return_value = {
                'cluster_id': 'test123',
                'topic_label': 'Test Topic',
                'created_at': '2025-12-13T10:00:00Z',
                'updated_at': '2025-12-13T10:00:00Z',
                'sentiment_distribution': {}
            }
            
            mock_articles.return_value = [
                {'title': 'Test Article', 'published_at': '2025-12-13T09:00:00Z', 'source': 'Test Source'}
            ]
            
            from src.service import run_news_based_observation
            
            # Record time before
            before_time = datetime.now(location_tz)
            
            # Run news-based observation
            run_news_based_observation(observation_type='morning')
            
            # Record time after
            after_time = datetime.now(location_tz)
            
            # Verify next scheduled time was saved and is in the future
            scheduled_info = mock_memory_manager.get_next_scheduled_time()
            assert scheduled_info is not None
            
            next_time = datetime.fromisoformat(scheduled_info['datetime'])
            if next_time.tzinfo is None:
                next_time = location_tz.localize(next_time)
            else:
                next_time = next_time.astimezone(location_tz)
            
            assert next_time > after_time, \
                f"Next scheduled time ({next_time}) should be after observation completed ({after_time})"
            
            # Verify it was included in the post
            assert mock_hugo_gen.create_post.called
            call_args = mock_hugo_gen.create_post.call_args
            diary_entry_with_schedule = call_args[0][0]
            assert "Next scheduled observation" in diary_entry_with_schedule

