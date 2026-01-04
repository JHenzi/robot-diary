#!/usr/bin/env python
"""
Backfill script to generate and store image embeddings for existing observations.

This script:
1. Loads all memories from observations.json
2. For each observation with an image_path, generates an image embedding using CLIP
3. Stores embeddings in ChromaDB image collection

Run this once after implementing the boredom factor feature to populate
image embeddings for all historical observations.
"""
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.memory.retriever import HybridMemoryRetriever, MEMORY_FILE
from src.config import PROJECT_ROOT, IMAGES_DIR
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def resolve_image_path(image_path_str: str) -> Path:
    """
    Resolve image path, handling Docker paths and relative paths.
    
    Args:
        image_path_str: Image path from memory (could be Docker path, relative, or absolute)
        
    Returns:
        Resolved Path object, or None if path cannot be resolved
    """
    from pathlib import Path
    
    # Try the path as-is first
    path = Path(image_path_str)
    if path.exists():
        return path
    
    # If it's a Docker path (/app/images/...), convert to local
    if str(path).startswith('/app/images/'):
        filename = path.name
        local_path = IMAGES_DIR / filename
        if local_path.exists():
            return local_path
    
    # If it's just a filename, look in IMAGES_DIR
    if not str(path).startswith('/') and '/' not in str(path):
        local_path = IMAGES_DIR / path
        if local_path.exists():
            return local_path
    
    # Try relative to PROJECT_ROOT
    relative_path = PROJECT_ROOT / path
    if relative_path.exists():
        return relative_path
    
    # Try relative to IMAGES_DIR if path has subdirectories
    if '/' in str(path) and not str(path).startswith('/'):
        local_path = IMAGES_DIR / path
        if local_path.exists():
            return local_path
    
    return None


def main():
    """Backfill image embeddings for all existing observations."""
    # Check for --force flag to re-generate all embeddings
    force = '--force' in sys.argv or '-f' in sys.argv
    
    logger.info("Starting backfill of image embeddings...")
    
    # Initialize hybrid retriever (this will initialize ChromaDB and CLIP model)
    retriever = HybridMemoryRetriever()
    
    if not retriever.chroma_available:
        logger.error("ChromaDB is not available. Please install chromadb and sentence-transformers:")
        logger.error("  pip install chromadb sentence-transformers")
        return 1
    
    if not retriever.image_embedding_model:
        logger.error("Image embedding model is not available. Please ensure CLIP model can be loaded:")
        logger.error("  The clip-ViT-B-32 model should be downloaded automatically by sentence-transformers")
        return 1
    
    # If force flag, delete and recreate image collection
    if force:
        logger.info("⚠️  Force flag detected - clearing existing image embeddings collection...")
        try:
            # Delete the collection
            retriever.client.delete_collection(name=retriever.image_collection.name)
            logger.info("✅ Deleted existing image embeddings collection")
            
            # Recreate it
            from src.memory.retriever import IMAGE_COLLECTION_NAME
            retriever.image_collection = retriever.client.get_or_create_collection(
                name=IMAGE_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("✅ Recreated image embeddings collection")
        except Exception as e:
            logger.warning(f"Could not delete collection (may not exist): {e}")
    
    # Load all memories from JSON
    if not MEMORY_FILE.exists():
        logger.error(f"Memory file not found: {MEMORY_FILE}")
        return 1
    
    try:
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                logger.warning("Memory file is empty")
                return 0
            memories = json.loads(content)
    except Exception as e:
        logger.error(f"Error loading memories: {e}")
        return 1
    
    logger.info(f"Found {len(memories)} observations in memory file")
    
    # Process each memory
    processed = 0
    skipped = 0
    failed = 0
    missing_images = 0
    
    for mem in memories:
        mem_id = mem.get('id')
        image_path_str = mem.get('image_path')
        
        if not mem_id:
            logger.warning(f"Skipping memory without ID: {mem}")
            skipped += 1
            continue
        
        if not image_path_str:
            logger.debug(f"Memory {mem_id} has no image_path, skipping")
            skipped += 1
            continue
        
        # Check if embedding already exists (unless force)
        if not force:
            try:
                existing = retriever.image_collection.get(ids=[str(mem_id)])
                if existing and existing.get('ids') and len(existing['ids']) > 0:
                    logger.debug(f"Image embedding {mem_id} already exists, skipping")
                    skipped += 1
                    continue
            except Exception as e:
                logger.debug(f"Error checking for existing embedding {mem_id}: {e}")
        
        # Resolve image path (handles Docker paths, relative paths, etc.)
        image_path = resolve_image_path(image_path_str)
        if image_path is None:
            logger.warning(f"Image file not found for memory {mem_id}: {image_path_str}")
            missing_images += 1
            continue
        
        # Generate and store embedding
        try:
            success = retriever.add_image_embedding_to_chroma(mem, image_path)
            if success:
                processed += 1
                if processed % 10 == 0:
                    logger.info(f"Processed {processed} image embeddings...")
            else:
                failed += 1
                logger.warning(f"Failed to add image embedding for memory {mem_id}")
        except Exception as e:
            failed += 1
            logger.error(f"Error processing memory {mem_id}: {e}")
    
    # Summary
    logger.info("=" * 60)
    logger.info("Backfill Summary:")
    logger.info(f"  ✅ Processed: {processed}")
    logger.info(f"  ⏭️  Skipped: {skipped}")
    logger.info(f"  ❌ Failed: {failed}")
    logger.info(f"  📷 Missing images: {missing_images}")
    logger.info("=" * 60)
    
    if processed > 0:
        logger.info(f"✅ Successfully backfilled {processed} image embeddings!")
        logger.info("Boredom factor calculations will now work for all historical observations.")
    else:
        logger.warning("No image embeddings were processed. This could mean:")
        logger.warning("  - All embeddings already exist (use --force to re-generate)")
        logger.warning("  - No observations have image_path fields")
        logger.warning("  - Image files are missing")
        logger.warning("  - An error occurred during processing")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

