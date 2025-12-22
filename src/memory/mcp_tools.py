"""Memory query tools for function calling (MCP-style on-demand queries)."""
import logging
from typing import List, Dict, Optional
from pathlib import Path

from .retriever import HybridMemoryRetriever
from .manager import MemoryManager

logger = logging.getLogger(__name__)


class MemoryQueryTools:
    """
    Tools for LLM to query memories on-demand during generation.
    These are exposed as function calling tools to the LLM.
    """
    
    def __init__(self, memory_manager: MemoryManager):
        """
        Initialize memory query tools.
        
        Args:
            memory_manager: MemoryManager instance for accessing memories
        """
        self.memory_manager = memory_manager
        self._retriever = None
    
    def _get_retriever(self) -> Optional[HybridMemoryRetriever]:
        """Lazy initialization of hybrid retriever."""
        if self._retriever is None:
            retriever = self.memory_manager._get_hybrid_retriever()
            if retriever:
                self._retriever = retriever
        return self._retriever
    
    def query_memories(self, query: str, top_k: int = 5) -> str:
        """
        Query memories semantically based on a natural language query.
        Uses embeddings to find contextually relevant memories.
        
        Args:
            query: Natural language query (e.g., "rainy weather observations", "people walking")
            top_k: Number of most relevant memories to return (default: 5)
        
        Returns:
            Formatted string with relevant memories, or empty string if none found
        """
        try:
            retriever = self._get_retriever()
            if retriever and retriever.chroma_available:
                # Use semantic search via ChromaDB
                memories = retriever.get_hybrid_memories(
                    query_text=query,
                    recent_count=0,  # Don't include temporal - this is semantic-only query
                    semantic_top_k=top_k
                )
            else:
                # Fallback: search in temporal memories using keyword matching
                logger.debug("ChromaDB unavailable, using keyword search in temporal memories")
                all_memories = self.memory_manager.get_recent_memory(count=50)  # Get more to search
                memories = []
                query_lower = query.lower()
                
                for mem in all_memories:
                    text = (mem.get('llm_summary') or mem.get('summary') or mem.get('content', '')).lower()
                    if query_lower in text or any(word in text for word in query_lower.split() if len(word) > 3):
                        memories.append({
                            'id': mem.get('id'),
                            'date': mem.get('date'),
                            'text': mem.get('llm_summary') or mem.get('summary') or mem.get('content', ''),
                            'source': 'temporal'
                        })
                        if len(memories) >= top_k:
                            break
            
            if not memories:
                return f"No memories found matching query: '{query}'"
            
            # Format results
            formatted = []
            for mem in memories:
                mem_id = mem.get('id', '?')
                date = mem.get('date', 'Unknown date')
                text = mem.get('text', '')
                
                # Format date
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    formatted_date = dt.strftime('%B %d, %Y')
                except:
                    formatted_date = date
                
                formatted.append(f"Observation #{mem_id} ({formatted_date}): {text[:300]}{'...' if len(text) > 300 else ''}")
            
            return "\n\n".join(formatted)
            
        except Exception as e:
            logger.error(f"Error querying memories: {e}")
            return f"Error querying memories: {str(e)}"
    
    def get_recent_memories(self, count: int = 5) -> str:
        """
        Get the most recent N observations for temporal continuity.
        Useful for comparing current observation with recent ones.
        
        Args:
            count: Number of recent memories to return (default: 5)
        
        Returns:
            Formatted string with recent memories
        """
        try:
            recent = self.memory_manager.get_recent_memory(count=count)
            
            if not recent:
                return "No recent observations found."
            
            # Format results
            formatted = []
            for mem in reversed(recent):  # Most recent first
                mem_id = mem.get('id', '?')
                date = mem.get('date', 'Unknown date')
                text = mem.get('llm_summary') or mem.get('summary') or mem.get('content', '')
                
                # Format date
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    formatted_date = dt.strftime('%B %d, %Y')
                except:
                    formatted_date = date
                
                formatted.append(f"Observation #{mem_id} ({formatted_date}): {text[:300]}{'...' if len(text) > 300 else ''}")
            
            return "\n\n".join(formatted)
            
        except Exception as e:
            logger.error(f"Error getting recent memories: {e}")
            return f"Error getting recent memories: {str(e)}"
    
    def check_memory_exists(self, topic: str) -> str:
        """
        Quick check if any memories exist about a specific topic.
        Returns a simple yes/no answer with a brief example if found.
        
        Args:
            topic: Topic to check (e.g., "rain", "crowds", "morning observations")
        
        Returns:
            "Yes" or "No" with brief context if found
        """
        try:
            retriever = self._get_retriever()
            if retriever and retriever.chroma_available:
                # Use semantic search
                memories = retriever.get_hybrid_memories(
                    query_text=topic,
                    recent_count=0,
                    semantic_top_k=1  # Just need to know if it exists
                )
            else:
                # Fallback: keyword search
                all_memories = self.memory_manager.get_recent_memory(count=50)
                memories = []
                topic_lower = topic.lower()
                
                for mem in all_memories:
                    text = (mem.get('llm_summary') or mem.get('summary') or mem.get('content', '')).lower()
                    if topic_lower in text or any(word in text for word in topic_lower.split() if len(word) > 3):
                        memories.append({
                            'id': mem.get('id'),
                            'date': mem.get('date'),
                            'text': mem.get('llm_summary') or mem.get('summary') or mem.get('content', ''),
                            'source': 'temporal'
                        })
                        break
            
            if not memories:
                return f"No, I don't have any memories about '{topic}'."
            
            mem = memories[0]
            mem_id = mem.get('id', '?')
            text = mem.get('text', '')
            snippet = text[:150] + '...' if len(text) > 150 else text
            
            return f"Yes, I have memories about '{topic}'. Example: Observation #{mem_id}: {snippet}"
            
        except Exception as e:
            logger.error(f"Error checking memory existence: {e}")
            return f"Error checking memory: {str(e)}"


def get_memory_tool_schemas() -> List[Dict]:
    """
    Get function schemas for Groq function calling.
    These define the tools available to the LLM.
    
    Returns:
        List of tool definitions in Groq function calling format
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "query_memories",
                "description": "Query your memory for similar past observations by searching for specific, concrete details you see. When you notice a key detail (like a man in red shirt, 10 people, bikes, Tuesday night), search for similar observations with that same detail. Vary what you search for - don't always query the same things. Focus on concrete elements that would appear in similar stories: specific objects, vehicles, clothing, group sizes, time patterns, or notable details.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Specific, concrete detail to search for in past observations. If you see a man in red shirt, search for 'men in red shirts'. If you see 10 people, search for '10 people' or similar group sizes. If it's Tuesday night, search for 'tuesday night'. Be specific enough to find matches, but vary what you search for across different observations. Focus on key details that would appear in similar stories."
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of most relevant memories to return (default: 5, max: 10)",
                            "default": 5,
                            "minimum": 1,
                            "maximum": 10
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_recent_memories",
                "description": "Get your most recent observations for temporal continuity. Use this to compare current observation with recent ones, especially for morning vs evening comparisons or day-to-day changes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Number of recent memories to retrieve (default: 5, max: 10)",
                            "default": 5,
                            "minimum": 1,
                            "maximum": 10
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_memory_exists",
                "description": "Quickly check if you have any memories about a specific topic. Returns yes/no with a brief example if found. Use this for quick checks before doing a full query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Topic to check (e.g., 'rain', 'crowds', 'morning observations', 'holiday decorations')"
                        }
                    },
                    "required": ["topic"]
                }
            }
        }
    ]
