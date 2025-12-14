#!/usr/bin/env python
"""
Cleanup script for unreferenced cached images.

This script:
1. Finds all images in images/ directory
2. Checks which are referenced in memory/observations.json
3. Deletes unreferenced images
4. Optionally cleans Hugo static images that aren't referenced in posts
"""
import sys
import json
from pathlib import Path
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.config import IMAGES_DIR, MEMORY_DIR, HUGO_SITE_PATH, HUGO_STATIC_IMAGES_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def get_referenced_images():
    """Get set of all image filenames referenced in memory."""
    referenced = set()
    
    memory_file = MEMORY_DIR / 'observations.json'
    if not memory_file.exists():
        logger.warning(f"Memory file not found: {memory_file}")
        return referenced
    
    try:
        with open(memory_file, 'r') as f:
            observations = json.load(f)
        
        for obs in observations:
            # Extract filename from path (handles both Docker and local paths)
            image_path = obs.get('image_path', '')
            image_filename = obs.get('image_filename', '')
            
            if image_filename:
                referenced.add(image_filename)
            elif image_path:
                # Extract filename from path
                filename = Path(image_path).name
                if filename:
                    referenced.add(filename)
        
        logger.info(f"Found {len(referenced)} referenced images in memory")
        return referenced
    
    except Exception as e:
        logger.error(f"Error reading memory file: {e}")
        return referenced


def cleanup_images_directory(referenced_images, dry_run=False):
    """Clean up unreferenced images in images/ directory."""
    if not IMAGES_DIR.exists():
        logger.info(f"Images directory doesn't exist: {IMAGES_DIR}")
        return 0
    
    all_images = []
    for ext in ['*.jpg', '*.png']:
        all_images.extend(IMAGES_DIR.glob(ext))
    
    # Also check for news_transmission.png (special case)
    news_image = IMAGES_DIR / 'news_transmission.png'
    if news_image.exists():
        all_images.append(news_image)
    
    unreferenced = []
    for image_path in all_images:
        # Skip cache metadata
        if image_path.name == '.cache_metadata.json':
            continue
        
        if image_path.name not in referenced_images:
            unreferenced.append(image_path)
    
    if not unreferenced:
        logger.info("✅ No unreferenced images found in images/ directory")
        return 0
    
    logger.info(f"Found {len(unreferenced)} unreferenced image(s):")
    for img in unreferenced:
        logger.info(f"  - {img.name}")
    
    if dry_run:
        logger.info("🔍 DRY RUN: Would delete these images")
        return len(unreferenced)
    
    deleted = 0
    for img in unreferenced:
        try:
            img.unlink()
            deleted += 1
            logger.info(f"  ✅ Deleted: {img.name}")
        except Exception as e:
            logger.error(f"  ❌ Failed to delete {img.name}: {e}")
    
    logger.info(f"✅ Deleted {deleted} unreferenced image(s)")
    return deleted


def cleanup_hugo_images(dry_run=False):
    """Clean up Hugo static images that aren't referenced in posts."""
    if not HUGO_STATIC_IMAGES_DIR.exists():
        logger.info(f"Hugo static images directory doesn't exist: {HUGO_STATIC_IMAGES_DIR}")
        return 0
    
    # Get all Hugo posts
    posts_dir = HUGO_SITE_PATH / 'content' / 'posts'
    if not posts_dir.exists():
        logger.info(f"Hugo posts directory doesn't exist: {posts_dir}")
        return 0
    
    referenced_hugo_images = set()
    for post_file in posts_dir.glob('*.md'):
        try:
            with open(post_file, 'r') as f:
                content = f.read()
                # Find image references in markdown
                import re
                # Match: ![alt](/images/filename.jpg) or ![alt](images/filename.jpg)
                matches = re.findall(r'!\[.*?\]\(/images/([^)]+)\)', content)
                matches.extend(re.findall(r'!\[.*?\]\(images/([^)]+)\)', content))
                for match in matches:
                    referenced_hugo_images.add(match)
        except Exception as e:
            logger.warning(f"Error reading post {post_file.name}: {e}")
    
    # Find all images in Hugo static directory
    all_hugo_images = []
    for ext in ['*.jpg', '*.png']:
        all_hugo_images.extend(HUGO_STATIC_IMAGES_DIR.glob(ext))
    
    unreferenced = []
    for image_path in all_hugo_images:
        if image_path.name not in referenced_hugo_images:
            unreferenced.append(image_path)
    
    if not unreferenced:
        logger.info("✅ No unreferenced images found in Hugo static/images/ directory")
        return 0
    
    logger.info(f"Found {len(unreferenced)} unreferenced Hugo image(s):")
    for img in unreferenced:
        logger.info(f"  - {img.name}")
    
    if dry_run:
        logger.info("🔍 DRY RUN: Would delete these Hugo images")
        return len(unreferenced)
    
    deleted = 0
    for img in unreferenced:
        try:
            img.unlink()
            deleted += 1
            logger.info(f"  ✅ Deleted: {img.name}")
        except Exception as e:
            logger.error(f"  ❌ Failed to delete {img.name}: {e}")
    
    logger.info(f"✅ Deleted {deleted} unreferenced Hugo image(s)")
    return deleted


def main():
    """Main cleanup function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up unreferenced cached images')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without actually deleting')
    parser.add_argument('--hugo-only', action='store_true', help='Only clean Hugo static images')
    parser.add_argument('--images-only', action='store_true', help='Only clean images/ directory')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🧹 Robot Diary Image Cleanup")
    print("=" * 60)
    print()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be deleted")
        print()
    
    total_deleted = 0
    
    try:
        if not args.hugo_only:
            referenced = get_referenced_images()
            deleted = cleanup_images_directory(referenced, dry_run=args.dry_run)
            total_deleted += deleted
            print()
        
        if not args.images_only:
            deleted = cleanup_hugo_images(dry_run=args.dry_run)
            total_deleted += deleted
            print()
        
        print("=" * 60)
        if args.dry_run:
            print(f"🔍 DRY RUN: Would delete {total_deleted} image(s)")
        else:
            print(f"✅ Cleanup completed! Deleted {total_deleted} unreferenced image(s)")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
