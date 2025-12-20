#!/usr/bin/env python3
"""
Migration script to populate ChromaDB from existing JSON memories.

This script:
1. Loads all memories from observations.json
2. Embeds them using sentence-transformers
3. Adds them to ChromaDB for semantic search

Run this once after installing chromadb and sentence-transformers.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.memory.retriever import HybridMemoryRetriever
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Migrate existing JSON memories to ChromaDB."""
    logger.info("Starting migration of JSON memories to ChromaDB...")
    
    # Initialize hybrid retriever (this will initialize ChromaDB)
    retriever = HybridMemoryRetriever()
    
    if not retriever.chroma_available:
        logger.error("ChromaDB is not available. Please install chromadb and sentence-transformers:")
        logger.error("  pip install chromadb sentence-transformers")
        return 1
    
    # Migrate memories
    migrated_count = retriever.migrate_json_to_chroma()
    
    if migrated_count > 0:
        logger.info(f"✅ Successfully migrated {migrated_count} memories to ChromaDB")
        logger.info("Hybrid memory retrieval is now enabled!")
    else:
        logger.warning("No memories were migrated. This could mean:")
        logger.warning("  - No memories exist in observations.json")
        logger.warning("  - All memories already exist in ChromaDB")
        logger.warning("  - An error occurred during migration")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
