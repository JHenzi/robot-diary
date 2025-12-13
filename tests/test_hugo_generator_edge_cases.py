"""Tests for Hugo generator edge cases and error handling."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock
from src.hugo.generator import HugoGenerator


class TestHugoGeneratorEdgeCases:
    """Test Hugo generator edge cases."""
    
    @pytest.fixture
    def temp_hugo_dir(self):
        """Create temporary Hugo directory."""
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
        """Create HugoGenerator with temp directory."""
        with patch('src.hugo.generator.HUGO_CONTENT_DIR', temp_hugo_dir / 'content' / 'posts'), \
             patch('src.hugo.generator.HUGO_STATIC_IMAGES_DIR', temp_hugo_dir / 'static' / 'images'):
            generator = HugoGenerator()
            yield generator
    
    def test_create_post_with_long_content(self, hugo_generator, temp_hugo_dir):
        """Test creating post with very long content."""
        image_path = temp_hugo_dir / 'test.jpg'
        image_path.touch()
        
        long_content = "A" * 10000  # Very long content
        context_metadata = {
            'date': 'December 12, 2025',
            'day_of_week': 'Thursday',
            'month': 'December',
            'day': 12,
            'year': 2025
        }
        
        post_path = hugo_generator.create_post(
            long_content,
            image_path,
            observation_id=1,
            context_metadata=context_metadata
        )
        
        assert post_path.exists()
        content = post_path.read_text()
        assert long_content in content
    
    def test_create_post_with_special_characters(self, hugo_generator, temp_hugo_dir):
        """Test creating post with special characters."""
        image_path = temp_hugo_dir / 'test.jpg'
        image_path.touch()
        
        special_content = "Entry with 'quotes', \"double quotes\", & ampersands, <tags>, and newlines\n\nHere."
        context_metadata = {
            'date': 'December 12, 2025',
            'day_of_week': 'Thursday',
            'month': 'December',
            'day': 12,
            'year': 2025
        }
        
        post_path = hugo_generator.create_post(
            special_content,
            image_path,
            observation_id=1,
            context_metadata=context_metadata
        )
        
        assert post_path.exists()
        content = post_path.read_text()
        assert "Entry with" in content
    
    def test_create_post_news_based_no_image(self, hugo_generator, temp_hugo_dir):
        """Test creating news-based post without image."""
        context_metadata = {
            'date': 'December 12, 2025',
            'day_of_week': 'Thursday',
            'month': 'December',
            'day': 12,
            'year': 2025
        }
        
        # Use non-existent image path
        fake_image = temp_hugo_dir / 'news.png'
        
        post_path = hugo_generator.create_post(
            "News-based entry",
            fake_image,
            observation_id=2,
            context_metadata=context_metadata,
            is_news_based=True
        )
        
        assert post_path.exists()
        content = post_path.read_text()
        assert "News-based entry" in content
    
    def test_create_post_duplicate_observation_id(self, hugo_generator, temp_hugo_dir):
        """Test creating posts with same observation ID (should use timestamp)."""
        image_path = temp_hugo_dir / 'test.jpg'
        image_path.touch()
        
        context_metadata = {
            'date': 'December 12, 2025',
            'day_of_week': 'Thursday',
            'month': 'December',
            'day': 12,
            'year': 2025
        }
        
        # Create first post
        post1 = hugo_generator.create_post(
            "First entry",
            image_path,
            observation_id=1,
            context_metadata=context_metadata
        )
        
        # Create second post with same ID (should have different filename due to timestamp)
        post2 = hugo_generator.create_post(
            "Second entry",
            image_path,
            observation_id=1,
            context_metadata=context_metadata
        )
        
        # Both should exist and be different files
        assert post1.exists()
        assert post2.exists()
        assert post1 != post2

