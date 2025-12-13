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
        """Test personality note generation with all stages."""
        # Test first observation
        note = mock_client._get_personality_note(0)
        assert isinstance(note, str)
        assert len(note) > 0
        assert "first observation" in note.lower()
        
        # Test new observer stage
        note = mock_client._get_personality_note(3)
        assert isinstance(note, str)
        assert "new" in note.lower() or "curious" in note.lower()
        
        # Test developing patterns stage
        note = mock_client._get_personality_note(10)
        assert isinstance(note, str)
        
        # Test accumulating experience stage
        note = mock_client._get_personality_note(25)
        assert isinstance(note, str)
        
        # Test seasoned observer stage
        note = mock_client._get_personality_note(50)
        assert isinstance(note, str)
        
        # Test long-term witness stage
        note = mock_client._get_personality_note(75)
        assert isinstance(note, str)
        
        # Test veteran observer stage
        note = mock_client._get_personality_note(150)
        assert isinstance(note, str)
        
        # Test ancient observer stage
        note = mock_client._get_personality_note(250)
        assert isinstance(note, str)
    
    def test_get_personality_note_with_seasonal_modifiers(self, mock_client):
        """Test personality note with seasonal modifiers."""
        context_metadata = {'season': 'Winter'}
        note = mock_client._get_personality_note(10, context_metadata=context_metadata)
        assert isinstance(note, str)
        assert "winter" in note.lower() or "introspective" in note.lower() or "contemplative" in note.lower()
        
        context_metadata = {'season': 'Spring'}
        note = mock_client._get_personality_note(10, context_metadata=context_metadata)
        assert isinstance(note, str)
        assert "spring" in note.lower() or "optimism" in note.lower() or "curiosity" in note.lower()
        
        context_metadata = {'season': 'Summer'}
        note = mock_client._get_personality_note(10, context_metadata=context_metadata)
        assert isinstance(note, str)
        assert "summer" in note.lower() or "energy" in note.lower() or "observant" in note.lower()
        
        context_metadata = {'season': 'Fall'}
        note = mock_client._get_personality_note(10, context_metadata=context_metadata)
        assert isinstance(note, str)
        assert "fall" in note.lower() or "autumn" in note.lower() or "nostalgic" in note.lower() or "reflective" in note.lower()
    
    def test_get_personality_note_with_holiday_modifiers(self, mock_client):
        """Test personality note with holiday modifiers."""
        context_metadata = {'is_holiday': True, 'holidays': ['Christmas']}
        note = mock_client._get_personality_note(10, context_metadata=context_metadata)
        assert isinstance(note, str)
        assert "holiday" in note.lower() or "reflects" in note.lower()
        
        # Test with just is_holiday flag
        context_metadata = {'is_holiday': True}
        note = mock_client._get_personality_note(10, context_metadata=context_metadata)
        assert isinstance(note, str)
        assert "holiday" in note.lower()
    
    def test_get_personality_note_with_weather_modifiers(self, mock_client):
        """Test personality note with weather modifiers."""
        # Test rain weather
        weather_data = {'summary': 'Light Rain'}
        note = mock_client._get_personality_note(10, weather_data=weather_data)
        assert isinstance(note, str)
        assert "rain" in note.lower() or "contemplative" in note.lower() or "introspective" in note.lower()
        
        # Test clear weather
        weather_data = {'summary': 'Clear'}
        note = mock_client._get_personality_note(10, weather_data=weather_data)
        assert isinstance(note, str)
        assert "clear" in note.lower() or "engaged" in note.lower() or "observant" in note.lower()
        
        # Test cloudy weather
        weather_data = {'summary': 'Overcast'}
        note = mock_client._get_personality_note(10, weather_data=weather_data)
        assert isinstance(note, str)
        assert "cloud" in note.lower() or "subdued" in note.lower() or "reflective" in note.lower()
    
    def test_get_personality_note_with_milestone_modifiers(self, mock_client):
        """Test personality note with milestone modifiers."""
        # Test first week
        note = mock_client._get_personality_note(5, days_since_first=3)
        assert isinstance(note, str)
        assert "first week" in note.lower() or "new" in note.lower() or "fascinating" in note.lower()
        
        # Test first month
        note = mock_client._get_personality_note(10, days_since_first=20)
        assert isinstance(note, str)
        assert "month" in note.lower() or "patterns" in note.lower()
        
        # Test first season
        note = mock_client._get_personality_note(30, days_since_first=75)
        assert isinstance(note, str)
        assert "season" in note.lower() or "perspective" in note.lower()
        
        # Test first year
        note = mock_client._get_personality_note(100, days_since_first=400)
        assert isinstance(note, str)
        assert "year" in note.lower() or "milestone" in note.lower() or "profound" in note.lower()
    
    def test_get_personality_note_with_combined_modifiers(self, mock_client):
        """Test personality note with multiple modifiers combined."""
        context_metadata = {
            'season': 'Winter',
            'is_holiday': True
        }
        weather_data = {'summary': 'Light Rain'}
        
        note = mock_client._get_personality_note(
            25, 
            context_metadata=context_metadata,
            weather_data=weather_data,
            days_since_first=15
        )
        
        assert isinstance(note, str)
        # Should contain multiple modifiers
        modifier_count = note.count('.')
        assert modifier_count >= 2  # Base personality + at least 2 modifiers
    
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

