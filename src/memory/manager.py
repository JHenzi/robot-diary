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
        
        observation = {
            'id': observation_id,
            'date': observation_date,
            'image_path': str(image_path),
            'image_filename': image_path.name,
            'image_url': image_url,
            'content': diary_entry,
            'summary': diary_entry[:200] + '...' if len(diary_entry) > 200 else diary_entry,
            'llm_summary': llm_summary  # Intelligent summary from LLM
        }
        
        memory.append(observation)
        
        # Clean old entries
        memory = self._clean_old_entries(memory)
        
        # Limit total entries
        if len(memory) > MAX_MEMORY_ENTRIES:
            memory = memory[-MAX_MEMORY_ENTRIES:]
        
        self._save_memory(memory)
        logger.info(f"✅ Observation added to memory (ID: {observation['id']})")
    
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
            # Clean up temp file if it exists
            temp_file = SCHEDULE_FILE.with_suffix('.json.tmp')
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            raise  # Re-raise to allow caller to handle

