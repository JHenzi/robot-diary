"""Tests for prompt templates and formatting."""
import pytest
from src.llm.prompts import (
    ROBOT_IDENTITY,
    WRITING_INSTRUCTIONS,
    CREATIVITY_ENCOURAGEMENT,
    BASE_PROMPT_TEMPLATE
)


class TestPrompts:
    """Test prompt templates."""
    
    def test_robot_identity_exists(self):
        """Test that robot identity template exists."""
        assert isinstance(ROBOT_IDENTITY, str)
        assert len(ROBOT_IDENTITY) > 0
        assert "B3N-T5-MNT" in ROBOT_IDENTITY
        assert "New Orleans" in ROBOT_IDENTITY
    
    def test_writing_instructions_exists(self):
        """Test that writing instructions exist."""
        assert isinstance(WRITING_INSTRUCTIONS, str)
        assert len(WRITING_INSTRUCTIONS) > 0
        assert "THOUGHTFUL" in WRITING_INSTRUCTIONS.upper() or "OBSERVANT" in WRITING_INSTRUCTIONS.upper()
    
    def test_creativity_encouragement_exists(self):
        """Test that creativity encouragement exists."""
        assert isinstance(CREATIVITY_ENCOURAGEMENT, str)
        assert len(CREATIVITY_ENCOURAGEMENT) > 0
        assert "CREATIVE" in CREATIVITY_ENCOURAGEMENT.upper()
    
    def test_base_prompt_template(self):
        """Test that base prompt template combines components."""
        assert isinstance(BASE_PROMPT_TEMPLATE, str)
        assert len(BASE_PROMPT_TEMPLATE) > 0
        assert ROBOT_IDENTITY in BASE_PROMPT_TEMPLATE
        assert WRITING_INSTRUCTIONS in BASE_PROMPT_TEMPLATE
        assert CREATIVITY_ENCOURAGEMENT in BASE_PROMPT_TEMPLATE
    
    def test_prompt_no_api_key_required(self):
        """Test that prompt templates don't require API keys."""
        # This test just verifies we can import and use prompts without API
        assert BASE_PROMPT_TEMPLATE is not None

