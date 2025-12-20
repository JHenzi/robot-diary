"""Memory management for storing robot observations."""
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

from ..config import MEMORY_DIR, MEMORY_RETENTION_DAYS, MAX_MEMORY_ENTRIES
from datetime import datetime

logger = logging.getLogger(__name__)

MEMORY_FILE = MEMORY_DIR / 'observations.json'
SCHEDULE_FILE = MEMORY_DIR / 'schedule.json'


class MemoryManager:
    """Manages robot memory/observations."""
    
    def __init__(self):
        self.memory_file = MEMORY_FILE
        self._ensure_memory_file()
        # Initialize hybrid retriever (lazy initialization)
        self._hybrid_retriever = None
    
    def _get_hybrid_retriever(self):
        """Lazy initialization of hybrid retriever."""
        if self._hybrid_retriever is None:
            try:
                from .retriever import HybridMemoryRetriever
                self._hybrid_retriever = HybridMemoryRetriever(memory_file=self.memory_file)
            except Exception as e:
                logger.warning(f"Failed to initialize hybrid retriever: {e}")
                self._hybrid_retriever = None
        return self._hybrid_retriever
    
    def _ensure_memory_file(self):
        """Ensure memory file exists."""
        if not self.memory_file.exists():
            self._save_memory([])
    
    def _load_memory(self) -> List[Dict]:
        """Load memory from file with error recovery."""
        if not self.memory_file.exists():
            return []
        
        try:
            with open(self.memory_file, 'r') as f:
                content = f.read().strip()
                if not content:
                    return []
                return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error loading memory: {e}")
            logger.warning("Memory file appears corrupted. Attempting to recover...")
            # Try to backup corrupted file
            backup_file = self.memory_file.with_suffix('.json.bak')
            try:
                import shutil
                shutil.copy2(self.memory_file, backup_file)
                logger.info(f"Backed up corrupted file to {backup_file}")
            except Exception as backup_error:
                logger.warning(f"Failed to backup corrupted file: {backup_error}")
            return []
        except Exception as e:
            logger.error(f"Error loading memory: {e}")
            return []
    
    def _save_memory(self, memory: List[Dict]):
        """Save memory to file using atomic write to prevent corruption."""
        try:
            # Write to temporary file first
            temp_file = self.memory_file.with_suffix('.json.tmp')
            
            # Write JSON to temp file
            with open(temp_file, 'w') as f:
                json.dump(memory, f, indent=2)
                # Ensure data is flushed to disk
                f.flush()
                import os
                os.fsync(f.fileno())
            
            # Atomic rename (works on most filesystems)
            # This ensures the original file is only replaced if write succeeds
            temp_file.replace(self.memory_file)
            logger.debug(f"Memory saved successfully ({len(memory)} entries)")
            
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
            # Clean up temp file if it exists
            temp_file = self.memory_file.with_suffix('.json.tmp')
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            raise  # Re-raise to allow caller to handle
    
    def add_observation(self, image_path: Path, diary_entry: str, image_url: Optional[str] = None, llm_client=None):
        """
        Add a new observation to memory.
        
        Args:
            image_path: Path to the image file
            diary_entry: The generated diary entry text
            image_url: Original image URL (optional)
            llm_client: Optional GroqClient instance for generating LLM summaries
        """
        memory = self._load_memory()
        
        observation_id = len(memory) + 1
        observation_date = datetime.now().isoformat()
        
        # Generate LLM summary if client provided
        llm_summary = None
        if llm_client:
            try:
                llm_summary = llm_client.generate_memory_summary(diary_entry, observation_id, observation_date)
                logger.debug(f"Generated LLM summary for observation #{observation_id}")
            except Exception as e:
                logger.warning(f"Failed to generate LLM summary: {e}, using fallback")
        
        # Ensure all values are JSON-serializable
        observation = {
            'id': observation_id,
            'date': observation_date,
            'image_path': str(image_path),
            'image_filename': str(image_path.name) if hasattr(image_path, 'name') else str(image_path),
            'image_url': image_url,
            'content': str(diary_entry),
            'summary': str(diary_entry[:200] + '...' if len(diary_entry) > 200 else diary_entry),
            'llm_summary': str(llm_summary) if llm_summary is not None else None  # Intelligent summary from LLM
        }
        
        memory.append(observation)
        
        # Clean old entries
        memory = self._clean_old_entries(memory)
        
        # Limit total entries
        if len(memory) > MAX_MEMORY_ENTRIES:
            memory = memory[-MAX_MEMORY_ENTRIES:]
        
        self._save_memory(memory)
        logger.info(f"✅ Observation added to memory (ID: {observation['id']})")
        
        # Also add to ChromaDB if hybrid retriever is available
        retriever = self._get_hybrid_retriever()
        if retriever:
            retriever.add_memory_to_chroma(observation)
    
    def get_recent_memory(self, count: int = 10) -> List[Dict]:
        """
        Get recent memory entries.
        
        Args:
            count: Number of recent entries to return
            
        Returns:
            List of recent memory entries
        """
        memory = self._load_memory()
        return memory[-count:] if memory else []
    
    def get_hybrid_memories(
        self,
        query_text: Optional[str] = None,
        recent_count: int = 5,
        semantic_top_k: int = 5,
        context_metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Get hybrid memories: combines recent temporal memories with semantically relevant ones.
        
        Args:
            query_text: Optional query text for semantic search
            recent_count: Number of most recent temporal memories to always include
            semantic_top_k: Number of top semantically relevant memories to retrieve
            context_metadata: Optional context (date, time, weather) to build query
        
        Returns:
            List of memory dictionaries with 'id', 'date', 'text', 'source' fields
        """
        retriever = self._get_hybrid_retriever()
        if retriever:
            return retriever.get_hybrid_memories(
                query_text=query_text,
                recent_count=recent_count,
                semantic_top_k=semantic_top_k,
                context_metadata=context_metadata
            )
        else:
            # Fallback to recent temporal memories only
            logger.debug("Hybrid retriever not available, using temporal memories only")
            recent = self.get_recent_memory(count=recent_count)
            # Format to match hybrid retriever output format
            # Reverse to get most recent first (get_recent_memory returns oldest to newest in slice)
            formatted = [
                {
                    'id': m.get('id'),
                    'date': m.get('date'),
                    'text': m.get('llm_summary') or m.get('summary') or m.get('content', ''),
                    'source': 'temporal'
                }
                for m in reversed(recent)  # Reverse to get most recent first
            ]
            return formatted
    
    def _clean_old_entries(self, memory: List[Dict]) -> List[Dict]:
        """Remove entries older than retention period."""
        cutoff_date = datetime.now() - timedelta(days=MEMORY_RETENTION_DAYS)
        cutoff_iso = cutoff_date.isoformat()
        
        filtered = [
            entry for entry in memory
            if entry.get('date', '') >= cutoff_iso
        ]
        
        removed = len(memory) - len(filtered)
        if removed > 0:
            logger.info(f"Cleaned {removed} old memory entries")
        
        return filtered
    
    def get_memory_summary(self) -> Dict:
        """Get summary statistics about memory."""
        memory = self._load_memory()
        return {
            'total_entries': len(memory),
            'oldest_entry': memory[0]['date'] if memory else None,
            'newest_entry': memory[-1]['date'] if memory else None
        }
    
    def get_total_count(self) -> int:
        """Get total number of observations in memory."""
        memory = self._load_memory()
        return len(memory)
    
    def get_first_observation_date(self) -> Optional[datetime]:
        """
        Get the date of the first observation.
        
        Returns:
            Datetime of first observation, or None if no observations exist
        """
        memory = self._load_memory()
        if not memory:
            return None
        
        try:
            first_entry = memory[0]
            first_date_str = first_entry.get('date', '')
            if first_date_str:
                # Parse ISO format datetime
                return datetime.fromisoformat(first_date_str.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"Error parsing first observation date: {e}")
        
        return None
    
    def get_next_scheduled_time(self) -> Optional[Dict]:
        """
        Get the next scheduled observation time from memory.
        
        Returns:
            Dictionary with 'datetime' (ISO string) and 'type' ('morning' or 'evening'), or None
        """
        if not SCHEDULE_FILE.exists():
            return None
        
        try:
            with open(SCHEDULE_FILE, 'r') as f:
                content = f.read().strip()
                if not content:
                    return None
                schedule = json.loads(content)
                return schedule.get('next_observation')
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error loading schedule: {e}")
            logger.warning("Schedule file appears corrupted. Attempting to recover...")
            # Try to backup corrupted file
            backup_file = SCHEDULE_FILE.with_suffix('.json.bak')
            try:
                import shutil
                shutil.copy2(SCHEDULE_FILE, backup_file)
                logger.info(f"Backed up corrupted schedule file to {backup_file}")
            except Exception as backup_error:
                logger.warning(f"Failed to backup corrupted schedule file: {backup_error}")
            return None
        except Exception as e:
            logger.warning(f"Error loading schedule: {e}")
            return None
    
    def save_next_scheduled_time(self, next_time: datetime, obs_type: str):
        """
        Save the next scheduled observation time to memory using atomic write.
        
        Args:
            next_time: Next observation datetime
            obs_type: Type of observation ('morning' or 'evening')
        """
        try:
            schedule = {
                'next_observation': {
                    'datetime': next_time.isoformat(),
                    'type': obs_type
                },
                'last_updated': datetime.now().isoformat()
            }
            
            # Write to temporary file first
            temp_file = SCHEDULE_FILE.with_suffix('.json.tmp')
            
            with open(temp_file, 'w') as f:
                json.dump(schedule, f, indent=2)
                # Ensure data is flushed to disk
                f.flush()
                import os
                os.fsync(f.fileno())
            
            # Atomic rename
            temp_file.replace(SCHEDULE_FILE)
            logger.debug(f"Saved next scheduled time: {next_time.isoformat()} ({obs_type})")
            
        except Exception as e:
            logger.error(f"Error saving schedule: {e}")
            # Clean up temp file if it exists (wrap in try-except to handle permission errors)
            temp_file = SCHEDULE_FILE.with_suffix('.json.tmp')
            try:
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass
            except (PermissionError, OSError):
                # Can't even check if file exists due to permissions
                pass
            # Don't re-raise - schedule saving failure is not critical
            # The service will recalculate the schedule next time if needed

