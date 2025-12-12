"""Memory management for storing robot observations."""
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

from ..config import MEMORY_DIR, MEMORY_RETENTION_DAYS, MAX_MEMORY_ENTRIES

logger = logging.getLogger(__name__)

MEMORY_FILE = MEMORY_DIR / 'observations.json'


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
        """Load memory from file."""
        try:
            with open(self.memory_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading memory: {e}")
            return []
    
    def _save_memory(self, memory: List[Dict]):
        """Save memory to file."""
        try:
            with open(self.memory_file, 'w') as f:
                json.dump(memory, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
    
    def add_observation(self, image_path: Path, diary_entry: str, image_url: Optional[str] = None):
        """
        Add a new observation to memory.
        
        Args:
            image_path: Path to the image file
            diary_entry: The generated diary entry text
            image_url: Original image URL (optional)
        """
        memory = self._load_memory()
        
        observation = {
            'id': len(memory) + 1,
            'date': datetime.now().isoformat(),
            'image_path': str(image_path),
            'image_filename': image_path.name,
            'image_url': image_url,
            'content': diary_entry,
            'summary': diary_entry[:200] + '...' if len(diary_entry) > 200 else diary_entry
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

