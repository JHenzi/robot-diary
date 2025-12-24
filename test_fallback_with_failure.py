#!/usr/bin/env python
"""
Test that fallback works when ChromaDB initialization fails.

This simulates ChromaDB failure to verify the exception handling works.
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.memory.manager import MemoryManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_fallback_on_chromadb_failure():
    """Test that fallback works when ChromaDB fails to initialize."""
    logger.info("=" * 60)
    logger.info("Testing Fallback When ChromaDB Fails")
    logger.info("=" * 60)
    
    # Create memory manager
    manager = MemoryManager()
    
    # Simulate ChromaDB failure by making _get_hybrid_retriever return None
    # This simulates what happens when ChromaDB initialization throws an exception
    logger.info("\n1. Simulating ChromaDB failure...")
    original_method = manager._get_hybrid_retriever
    
    def failing_retriever():
        """Simulate ChromaDB failure."""
        logger.info("   Simulating ChromaDB initialization failure...")
        return None
    
    manager._get_hybrid_retriever = failing_retriever
    
    # Now test that get_hybrid_memories still works
    logger.info("\n2. Testing get_hybrid_memories() with ChromaDB failed...")
    try:
        memories = manager.get_hybrid_memories(recent_count=3)
        logger.info(f"✅ SUCCESS: Retrieved {len(memories)} memories despite ChromaDB failure")
        logger.info(f"   Memory sources: {[m.get('source', 'unknown') for m in memories]}")
        
        # Verify all are temporal (fallback)
        all_temporal = all(m.get('source') == 'temporal' for m in memories)
        if all_temporal:
            logger.info("✅ All memories are temporal (correct fallback)")
        else:
            logger.error(f"❌ FAILED: Expected all temporal, got: {[m.get('source') for m in memories]}")
            return False
        
        # Verify required fields
        required_fields = ['id', 'date', 'text', 'source']
        for mem in memories:
            missing = [f for f in required_fields if f not in mem]
            if missing:
                logger.error(f"❌ FAILED: Memory missing fields: {missing}")
                return False
        
        logger.info("✅ All memories have required fields")
        
    except Exception as e:
        logger.error(f"❌ FAILED: Exception during get_hybrid_memories: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Restore original method
        manager._get_hybrid_retriever = original_method
    
    # Test scheduler independence
    logger.info("\n3. Verifying scheduler independence...")
    try:
        next_time = manager.get_next_scheduled_time()
        count = manager.get_total_count()
        first_date = manager.get_first_observation_date()
        
        logger.info(f"✅ Scheduler methods work independently:")
        logger.info(f"   - get_next_scheduled_time(): {next_time is not None}")
        logger.info(f"   - get_total_count(): {count}")
        logger.info(f"   - get_first_observation_date(): {first_date is not None}")
        
    except Exception as e:
        logger.error(f"❌ FAILED: Scheduler methods failed: {e}")
        return False
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ FALLBACK VERIFICATION PASSED")
    logger.info("=" * 60)
    logger.info("\nConclusion:")
    logger.info("  ✅ System works correctly when ChromaDB fails")
    logger.info("  ✅ Falls back to temporal-only memory retrieval")
    logger.info("  ✅ Scheduler remains independent and functional")
    logger.info("  ✅ All critical functionality preserved")
    
    return True


if __name__ == "__main__":
    success = test_fallback_on_chromadb_failure()
    sys.exit(0 if success else 1)

