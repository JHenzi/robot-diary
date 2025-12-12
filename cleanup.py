#!/usr/bin/env python3
"""
Cleanup script for Robot Diary.

This script will:
1. Delete all observations/memory JSON files
2. Delete all saved webcam images
3. Delete all Hugo posts
4. Rebuild the Hugo site (without deploying)
"""
import sys
from pathlib import Path
import shutil
import subprocess
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.config import (
    MEMORY_DIR,
    IMAGES_DIR,
    HUGO_CONTENT_DIR,
    HUGO_SITE_PATH,
    PROJECT_ROOT
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def delete_memory():
    """Delete all memory/observation JSON files."""
    logger.info("🗑️  Deleting memory files...")
    
    memory_file = MEMORY_DIR / 'observations.json'
    if memory_file.exists():
        memory_file.unlink()
        logger.info(f"   ✅ Deleted: {memory_file}")
    else:
        logger.info(f"   ℹ️  No memory file found: {memory_file}")
    
    # Also clean cache metadata
    cache_metadata = IMAGES_DIR / '.cache_metadata.json'
    if cache_metadata.exists():
        cache_metadata.unlink()
        logger.info(f"   ✅ Deleted cache metadata: {cache_metadata}")


def delete_images():
    """Delete all saved webcam images."""
    logger.info("🗑️  Deleting webcam images...")
    
    if not IMAGES_DIR.exists():
        logger.info(f"   ℹ️  Images directory doesn't exist: {IMAGES_DIR}")
        return
    
    deleted_count = 0
    for image_file in IMAGES_DIR.glob('*.jpg'):
        image_file.unlink()
        deleted_count += 1
    
    for image_file in IMAGES_DIR.glob('*.png'):
        image_file.unlink()
        deleted_count += 1
    
    logger.info(f"   ✅ Deleted {deleted_count} image file(s)")
    
    # Delete cache metadata if it exists
    cache_metadata = IMAGES_DIR / '.cache_metadata.json'
    if cache_metadata.exists():
        cache_metadata.unlink()
        logger.info(f"   ✅ Deleted cache metadata")


def delete_hugo_posts():
    """Delete all Hugo posts."""
    logger.info("🗑️  Deleting Hugo posts...")
    
    if not HUGO_CONTENT_DIR.exists():
        logger.info(f"   ℹ️  Hugo posts directory doesn't exist: {HUGO_CONTENT_DIR}")
        return
    
    deleted_count = 0
    for post_file in HUGO_CONTENT_DIR.glob('*.md'):
        post_file.unlink()
        deleted_count += 1
    
    logger.info(f"   ✅ Deleted {deleted_count} Hugo post file(s)")
    
    # Also delete images from Hugo static directory
    hugo_images_dir = HUGO_SITE_PATH / 'static' / 'images'
    if hugo_images_dir.exists():
        deleted_images = 0
        for image_file in hugo_images_dir.glob('*.jpg'):
            image_file.unlink()
            deleted_images += 1
        for image_file in hugo_images_dir.glob('*.png'):
            image_file.unlink()
            deleted_images += 1
        if deleted_images > 0:
            logger.info(f"   ✅ Deleted {deleted_images} image file(s) from Hugo static directory")


def rebuild_hugo():
    """Rebuild the Hugo site without deploying."""
    logger.info("🔨 Rebuilding Hugo site...")
    
    if not HUGO_SITE_PATH.exists():
        logger.error(f"   ❌ Hugo site directory doesn't exist: {HUGO_SITE_PATH}")
        return False
    
    try:
        result = subprocess.run(
            ['hugo'],
            cwd=HUGO_SITE_PATH,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info("   ✅ Hugo site rebuilt successfully")
        logger.debug(f"   Hugo output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"   ❌ Hugo build failed: {e}")
        logger.error(f"   Error output: {e.stderr}")
        return False
    except FileNotFoundError:
        logger.error("   ❌ Hugo not found. Is Hugo installed?")
        return False


def main():
    """Main cleanup function."""
    print("=" * 60)
    print("🧹 Robot Diary Cleanup Script")
    print("=" * 60)
    print()
    print("This will:")
    print("  1. Delete all memory/observation JSON files")
    print("  2. Delete all saved webcam images")
    print("  3. Delete all Hugo posts")
    print("  4. Rebuild the Hugo site (without deploying)")
    print()
    
    response = input("Are you sure you want to continue? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("❌ Cleanup cancelled.")
        return
    
    print()
    
    # Perform cleanup
    try:
        delete_memory()
        print()
        
        delete_images()
        print()
        
        delete_hugo_posts()
        print()
        
        rebuild_hugo()
        print()
        
        print("=" * 60)
        print("✅ Cleanup completed successfully!")
        print("=" * 60)
        print()
        print("The robot will start fresh on the next observation.")
        
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

