"""Tests for Hugo generator (file operations only, no builds)."""
import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
from src.hugo.generator import HugoGenerator


class TestHugoGenerator:
    """Test Hugo generator file operations."""
    
    @pytest.fixture
    def temp_hugo_dir(self):
        """Create a temporary Hugo directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hugo_path = Path(tmpdir) / 'hugo'
            hugo_path.mkdir()
            (hugo_path / 'content').mkdir()
            (hugo_path / 'content' / 'posts').mkdir()
            (hugo_path / 'static').mkdir()
            (hugo_path / 'static' / 'images').mkdir()
            yield hugo_path
    
    @pytest.fixture
    def hugo_generator(self, temp_hugo_dir):
        """Create a HugoGenerator instance with temp directory."""
        # Mock the config values that HugoGenerator uses
        with patch('src.hugo.generator.HUGO_CONTENT_DIR', temp_hugo_dir / 'content' / 'posts'), \
             patch('src.hugo.generator.HUGO_STATIC_IMAGES_DIR', temp_hugo_dir / 'static' / 'images'):
            generator = HugoGenerator()
            yield generator
    
    def test_hugo_generator_initialization(self, hugo_generator, temp_hugo_dir):
        """Test Hugo generator initialization."""
        assert hugo_generator is not None
        assert hugo_generator.content_dir == temp_hugo_dir / 'content' / 'posts'
        assert hugo_generator.static_images_dir == temp_hugo_dir / 'static' / 'images'
    
    def test_create_post_file_structure(self, hugo_generator, temp_hugo_dir):
        """Test post file creation structure."""
        # Create a dummy image
        image_path = temp_hugo_dir / 'test_image.jpg'
        image_path.touch()
        
        diary_entry = "This is a test diary entry."
        context_metadata = {
            'date': 'December 12, 2025',
            'day_of_week': 'Thursday',
            'month': 'December',
            'day': 12,
            'year': 2025
        }
        
        post_path = hugo_generator.create_post(
            diary_entry,
            image_path,
            observation_id=1,
            context_metadata=context_metadata
        )
        
        assert post_path.exists()
        assert post_path.suffix == '.md'
        
        # Check file content
        content = post_path.read_text()
        assert diary_entry in content
        assert '+++' in content  # Hugo front matter
    
    def test_create_post_without_image(self, hugo_generator, temp_hugo_dir):
        """Test post creation without image (news-based)."""
        diary_entry = "This is a news-based entry."
        context_metadata = {
            'date': 'December 12, 2025',
            'day_of_week': 'Thursday',
            'month': 'December',
            'day': 12,
            'year': 2025
        }
        
        # Use a placeholder path that doesn't exist
        placeholder = temp_hugo_dir / 'news_transmission.png'
        
        post_path = hugo_generator.create_post(
            diary_entry,
            placeholder,
            observation_id=2,
            context_metadata=context_metadata,
            is_news_based=True
        )
        
        assert post_path.exists()
        content = post_path.read_text()
        assert diary_entry in content
        # Should not have image markdown for news-based
        assert '![' not in content or 'news-transmission' in content.lower()

