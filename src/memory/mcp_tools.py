"""Memory query tools for function calling (MCP-style on-demand queries)."""
import logging
import random
import re
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from .retriever import HybridMemoryRetriever
from .manager import MemoryManager
from ..config import AWAY_PERIODS

logger = logging.getLogger(__name__)


def should_offer_memory_recall() -> bool:
    """
    Decide whether this entry gets memory tools at all. Most entries should link back
    to the archive, but not every one - and the odds themselves vary per run.
    """
    return random.random() < random.uniform(0.6, 0.9)


def should_offer_news_recall(has_news: bool) -> bool:
    """Decide whether this entry can look up related news it heard before."""
    return has_news and random.random() < random.uniform(0.45, 0.8)


def _format_date(date: str) -> str:
    try:
        dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
        return dt.strftime('%B %d, %Y')
    except Exception:
        return date


def _header(mem: Dict) -> str:
    """'Observation #N (date)', labeled when written away from home so other-street details make sense."""
    date = str(mem.get('date') or '')
    where = next((f", {label}" for start, end, label in AWAY_PERIODS if date and start <= date < end), "")
    return f"Observation #{mem.get('id', '?')} ({_format_date(date or 'Unknown date')}{where})"


def _is_news_memory(mem: Dict) -> bool:
    return str(mem.get('image_url') or '').startswith('news://') or bool(mem.get('news_headlines'))


def _news_snippet(text: str, query: str, max_chars: int = 350) -> str:
    """Pick the sentences of an entry that relate to the query."""
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    words = {w for w in re.findall(r'[a-z]+', query.lower()) if len(w) > 3}
    scored = [(sum(w in s.lower() for w in words), i) for i, s in enumerate(sentences)]
    picked = sorted(i for score, i in sorted(scored, reverse=True)[:3] if score > 0)
    snippet = " ".join(sentences[i] for i in picked)  # empty when nothing in the entry relates
    return snippet[:max_chars] + ('...' if len(snippet) > max_chars else '')


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

    def _search(self, query: str, top_k: int) -> List[Dict]:
        """Semantic search over the whole archive, with keyword fallback."""
        retriever = self._get_retriever()
        if retriever and retriever.chroma_available:
            return retriever.get_hybrid_memories(
                query_text=query,
                recent_count=0,  # Don't include temporal - this is semantic-only query
                semantic_top_k=top_k
            )
        # Fallback: keyword search, most recent first
        logger.debug("ChromaDB unavailable, using keyword search in temporal memories")
        memories = []
        query_lower = query.lower()
        for mem in reversed(self.memory_manager._load_memory()):
            text = mem.get('llm_summary') or mem.get('summary') or mem.get('content', '')
            haystack = f"{text} {' '.join(mem.get('news_headlines') or [])}".lower()
            if query_lower in haystack or any(word in haystack for word in query_lower.split() if len(word) > 3):
                memories.append({'id': mem.get('id'), 'date': mem.get('date'), 'text': text, 'source': 'temporal'})
                if len(memories) >= top_k:
                    break
        return memories

    def query_memories(self, query: str, top_k: int = 5) -> str:
        """
        Query memories semantically based on a natural language query.

        Args:
            query: Natural language query (e.g., "rainy weather observations", "people walking")
            top_k: Number of most relevant memories to return (default: 5)

        Returns:
            Formatted string with relevant memories, or a no-match message
        """
        try:
            memories = self._search(query, top_k)
            if not memories:
                return f"No memories found matching query: '{query}'"

            formatted = []
            for mem in memories:
                text = mem.get('text', '')
                formatted.append(f"{_header(mem)}: {text[:300]}{'...' if len(text) > 300 else ''}")
            return "\n\n".join(formatted)

        except Exception as e:
            logger.error(f"Error querying memories: {e}")
            return f"Error querying memories: {str(e)}"

    def get_recent_memories(self, count: int = 5) -> str:
        """
        Get the most recent N observations for temporal continuity.

        Args:
            count: Number of recent memories to return (default: 5)

        Returns:
            Formatted string with recent memories
        """
        try:
            recent = self.memory_manager.get_recent_memory(count=count)
            if not recent:
                return "No recent observations found."

            formatted = []
            for mem in reversed(recent):  # Most recent first
                text = mem.get('llm_summary') or mem.get('summary') or mem.get('content', '')
                formatted.append(f"{_header(mem)}: {text[:300]}{'...' if len(text) > 300 else ''}")
            return "\n\n".join(formatted)

        except Exception as e:
            logger.error(f"Error getting recent memories: {e}")
            return f"Error getting recent memories: {str(e)}"

    def check_memory_exists(self, topic: str) -> str:
        """
        Quick check if any memories exist about a specific topic.

        Args:
            topic: Topic to check (e.g., "rain", "crowds", "morning observations")

        Returns:
            "Yes" or "No" with brief context if found
        """
        try:
            memories = self._search(topic, 1)
            if not memories:
                return f"No, I don't have any memories about '{topic}'."

            mem = memories[0]
            text = mem.get('text', '')
            snippet = text[:150] + '...' if len(text) > 150 else text
            return f"Yes, I have memories about '{topic}'. Example: {_header(mem)}: {snippet}"

        except Exception as e:
            logger.error(f"Error checking memory existence: {e}")
            return f"Error checking memory: {str(e)}"

    def query_news_memories(self, topic: str, top_k: int = 3) -> str:
        """
        Find earlier entries where the robot heard news related to a topic.
        Searches the whole archive and returns only the news-related part of each entry.

        Args:
            topic: News topic, person, place, or event to look for
            top_k: Number of past entries to return (default: 3)

        Returns:
            Formatted string with related past news, or a no-match message
        """
        try:
            candidates = [m for m in self.memory_manager._load_memory() if _is_news_memory(m)]
            # Keyword ranking over the full entry + headlines: the Chroma embeddings only
            # cover each entry's opening, while news is usually discussed further in.
            words = {w for w in re.findall(r'[a-z]+', topic.lower()) if len(w) > 3}
            scored = []
            for mem in candidates:
                headlines = mem.get('news_headlines') or []
                haystack = f"{mem.get('content', '')} {' '.join(headlines)}".lower()
                score = sum(w in haystack for w in words)
                if score and score >= min(2, len(words)):  # one shared word is usually a coincidence
                    scored.append((score, str(mem.get('date', '')), mem))
            scored.sort(key=lambda x: (x[0], x[1]), reverse=True)  # best match, then most recent

            formatted = []
            for _, _, mem in scored[:top_k]:
                headlines = mem.get('news_headlines') or []
                snippet = _news_snippet(mem.get('content', ''), topic)
                if not snippet and not headlines:
                    continue
                heard = f" Heard: {'; '.join(headlines)}." if headlines else ""
                wrote = f" You wrote: {snippet}" if snippet else ""
                formatted.append(f"{_header(mem)}:{heard}{wrote}")
            if not formatted:
                return f"You haven't heard any related news about '{topic}' before."
            return "\n\n".join(formatted)

        except Exception as e:
            logger.error(f"Error querying news memories: {e}")
            return f"Error querying news memories: {str(e)}"


def get_memory_tool_schemas(include_recall: bool = True, include_news: bool = False) -> List[Dict]:
    """
    Get function schemas for Groq function calling.
    These define the tools available to the LLM.

    Args:
        include_recall: Include the general memory tools (recent observations)
        include_news: Include the news-memory tool (related news heard before)

    Returns:
        List of tool definitions in Groq function calling format
    """
    schemas = []
    if include_recall:
        schemas.extend([
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
        ])
    if include_news:
        schemas.append({
            "type": "function",
            "function": {
                "name": "query_news_memories",
                "description": "Look up earlier transmissions you heard about a related story - to notice how a story has developed, recurred, or reversed since you last heard of it. Returns the headlines you heard and what you wrote about them.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "A specific name, place, event, or subject from the news you're hearing now (e.g. 'midterm polls', 'Apple iPhone', 'hurricane season')."
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of past entries to return (default: 3, max: 5)",
                            "default": 3,
                            "minimum": 1,
                            "maximum": 5
                        }
                    },
                    "required": ["topic"]
                }
            }
        })
    return schemas
