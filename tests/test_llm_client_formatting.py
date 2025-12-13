"""Tests for LLM client formatting functions (no API calls)."""
import pytest
from unittest.mock import Mock, patch
from src.llm.client import GroqClient


class TestLLMClientFormatting:
    """Test LLM client formatting methods that don't require API calls."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock GroqClient (no API key needed)."""
        with patch('src.llm.client.GroqClient.__init__', lambda self: None):
            client = GroqClient()
            # Mock the client attribute
            client.client = Mock()
            return client
    
    def test_format_memory_for_prompt_gen(self, mock_client):
        """Test memory formatting for prompt generation."""
        memory = [
            {
                'id': 1,
                'date': '2025-12-12T10:00:00',
                'content': 'Test entry 1',
                'llm_summary': 'Summary 1'
            },
            {
                'id': 2,
                'date': '2025-12-13T10:00:00',
                'content': 'Test entry 2',
                'summary': 'Summary 2'
            }
        ]
        
        formatted = mock_client._format_memory_for_prompt_gen(memory)
        
        assert isinstance(formatted, str)
        assert len(formatted) > 0
        assert 'Observation #1' in formatted or 'Observation #2' in formatted
    
    def test_get_style_variation(self, mock_client):
        """Test style variation generation."""
        variation = mock_client._get_style_variation()
        
        assert isinstance(variation, str)
        assert 'STYLE VARIATION' in variation
        assert len(variation) > 0
    
    def test_get_perspective_shift(self, mock_client):
        """Test perspective shift generation."""
        perspective = mock_client._get_perspective_shift()
        
        assert isinstance(perspective, str)
        assert 'PERSPECTIVE' in perspective
        assert len(perspective) > 0
    
    def test_get_focus_instruction(self, mock_client):
        """Test focus instruction generation."""
        context_metadata = {
            'time_of_day': 'morning',
            'weather': {}
        }
        
        focus = mock_client._get_focus_instruction(context_metadata)
        
        assert isinstance(focus, str)
        assert 'FOCUS' in focus
        assert len(focus) > 0
    
    def test_get_creative_challenge(self, mock_client):
        """Test creative challenge generation."""
        challenge = mock_client._get_creative_challenge()
        
        # May return empty string (40% chance), but if it returns something, should be valid
        assert isinstance(challenge, str)
        if challenge:
            assert 'CREATIVE CHALLENGE' in challenge
    
    def test_get_anti_repetition_instruction(self, mock_client):
        """Test anti-repetition instruction generation."""
        # Test with no memory
        instruction = mock_client._get_anti_repetition_instruction([])
        assert instruction == ""
        
        # Test with memory but no repetition
        memory = [
            {'id': 1, 'content': 'First entry about the morning.'},
            {'id': 2, 'content': 'Second entry about the evening.'}
        ]
        instruction = mock_client._get_anti_repetition_instruction(memory)
        # May be empty if no pattern detected
        assert isinstance(instruction, str)
    
    def test_get_personality_note(self, mock_client):
        """Test personality note generation."""
        # Test with low memory count
        note = mock_client._get_personality_note(0)
        assert isinstance(note, str)
        assert len(note) > 0
        
        # Test with high memory count
        note = mock_client._get_personality_note(100)
        assert isinstance(note, str)
        assert len(note) > 0
    
    def test_get_seasonal_note(self, mock_client):
        """Test seasonal note generation."""
        context_metadata = {
            'season': 'Winter',
            'month': 12
        }
        note = mock_client._get_seasonal_note(context_metadata)
        assert isinstance(note, str)
        
        # Test with no metadata
        note = mock_client._get_seasonal_note(None)
        assert isinstance(note, str)

