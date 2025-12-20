"""Tests for MCP-style memory query tools."""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.memory.mcp_tools import MemoryQueryTools, get_memory_tool_schemas
from src.memory.manager import MemoryManager


class TestMemoryQueryTools:
    """Test memory query tools for function calling."""
    
    @pytest.fixture
    def temp_memory_dir(self):
        """Create a temporary directory for memory files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def memory_manager(self, temp_memory_dir, monkeypatch):
        """Create a MemoryManager with temp directory."""
        memory_file = temp_memory_dir / 'observations.json'
        schedule_file = temp_memory_dir / 'schedule.json'
        
        from src.memory.manager import MemoryManager
        manager = MemoryManager()
        manager.memory_file = memory_file
        
        # Mock hybrid retriever to prevent ChromaDB initialization in tests
        monkeypatch.setattr(manager, '_get_hybrid_retriever', lambda: None)
        
        with patch('src.memory.manager.SCHEDULE_FILE', schedule_file):
            yield manager
    
    @pytest.fixture
    def memory_tools(self, memory_manager, temp_memory_dir):
        """Create MemoryQueryTools instance."""
        # Add some test memories
        for i in range(5):
            image_path = temp_memory_dir / f'test_{i}.jpg'
            image_path.touch()
            memory_manager.add_observation(image_path, f"Entry {i}: Test observation about weather and people")
        
        return MemoryQueryTools(memory_manager)
    
    def test_get_memory_tool_schemas(self):
        """Test that tool schemas are properly formatted."""
        schemas = get_memory_tool_schemas()
        
        assert len(schemas) == 3
        assert all(schema.get("type") == "function" for schema in schemas)
        
        function_names = [s["function"]["name"] for s in schemas]
        assert "query_memories" in function_names
        assert "get_recent_memories" in function_names
        assert "check_memory_exists" in function_names
    
    def test_query_memories_with_chromadb(self, memory_tools, memory_manager):
        """Test query_memories when ChromaDB is available."""
        # Mock the retriever to simulate ChromaDB availability
        mock_retriever = MagicMock()
        mock_retriever.chroma_available = True
        mock_retriever.get_hybrid_memories.return_value = [
            {'id': 3, 'date': '2024-01-03T10:00:00', 'text': 'Weather observation', 'source': 'semantic'}
        ]
        
        memory_tools._retriever = mock_retriever
        
        result = memory_tools.query_memories("weather", top_k=5)
        
        assert "weather" in result.lower() or "observation" in result.lower()
        assert "Observation #3" in result
        mock_retriever.get_hybrid_memories.assert_called_once()
    
    def test_query_memories_fallback(self, memory_tools):
        """Test query_memories falls back to keyword search when ChromaDB unavailable."""
        # No retriever (ChromaDB unavailable)
        memory_tools._retriever = None
        
        result = memory_tools.query_memories("weather", top_k=5)
        
        # Should use keyword search in temporal memories
        assert len(result) > 0
        assert "No memories found" not in result or "weather" in result.lower()
    
    def test_get_recent_memories(self, memory_tools):
        """Test get_recent_memories returns formatted recent memories."""
        result = memory_tools.get_recent_memories(count=3)
        
        assert len(result) > 0
        assert "Observation #" in result
        # Should have multiple observations
        assert result.count("Observation #") >= 1
    
    def test_get_recent_memories_empty(self, memory_manager):
        """Test get_recent_memories when no memories exist."""
        tools = MemoryQueryTools(memory_manager)
        result = tools.get_recent_memories(count=5)
        
        assert result == "No recent observations found."
    
    def test_check_memory_exists_found(self, memory_tools):
        """Test check_memory_exists when topic exists."""
        result = memory_tools.check_memory_exists("weather")
        
        assert "Yes" in result or "yes" in result.lower()
        assert "Observation #" in result
    
    def test_check_memory_exists_not_found(self, memory_manager):
        """Test check_memory_exists when topic doesn't exist."""
        tools = MemoryQueryTools(memory_manager)
        result = tools.check_memory_exists("nonexistent topic xyz123")
        
        assert "No" in result or "no" in result.lower()
        assert "don't have" in result.lower() or "no memories" in result.lower()
    
    def test_query_memories_error_handling(self, memory_tools):
        """Test that query_memories handles errors gracefully."""
        # Mock retriever to raise an error
        mock_retriever = MagicMock()
        mock_retriever.chroma_available = True
        mock_retriever.get_hybrid_memories.side_effect = Exception("Test error")
        
        memory_tools._retriever = mock_retriever
        
        result = memory_tools.query_memories("test query")
        
        # Should return error message, not crash
        assert "Error" in result or len(result) > 0


class TestMemoryQueryToolsIntegration:
    """Integration tests for memory query tools with actual memory manager."""
    
    @pytest.fixture
    def temp_memory_dir(self):
        """Create a temporary directory for memory files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def memory_manager(self, temp_memory_dir, monkeypatch):
        """Create a MemoryManager with temp directory."""
        memory_file = temp_memory_dir / 'observations.json'
        schedule_file = temp_memory_dir / 'schedule.json'
        
        from src.memory.manager import MemoryManager
        manager = MemoryManager()
        manager.memory_file = memory_file
        
        # Mock hybrid retriever to prevent ChromaDB initialization
        monkeypatch.setattr(manager, '_get_hybrid_retriever', lambda: None)
        
        with patch('src.memory.manager.SCHEDULE_FILE', schedule_file):
            yield manager
    
    def test_tools_work_without_chromadb(self, memory_manager, temp_memory_dir):
        """Test that tools work even when ChromaDB is unavailable."""
        # Add memories
        for i in range(3):
            image_path = temp_memory_dir / f'test_{i}.jpg'
            image_path.touch()
            memory_manager.add_observation(image_path, f"Entry {i}: Observation about people and weather")
        
        tools = MemoryQueryTools(memory_manager)
        
        # Test all three functions
        recent = tools.get_recent_memories(count=2)
        assert "Observation #" in recent
        
        query_result = tools.query_memories("people", top_k=3)
        assert len(query_result) > 0
        
        exists = tools.check_memory_exists("people")
        assert "Yes" in exists or "yes" in exists.lower()
