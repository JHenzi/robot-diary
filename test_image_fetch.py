#!/usr/bin/env python
"""
Test script to debug image fetching.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.camera import fetch_latest_image, get_latest_cached_image
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == '__main__':
    print("=" * 60)
    print("Testing Image Fetching")
    print("=" * 60)
    
    # Test 1: Check for cached image
    print("\n1. Checking for cached image...")
    cached = get_latest_cached_image()
    if cached:
        print(f"   ✅ Found cached image: {cached}")
        print(f"   Size: {cached.stat().st_size} bytes")
    else:
        print("   ℹ️  No cached image found")
    
    # Test 2: Fetch fresh image
    print("\n2. Fetching fresh image (force refresh)...")
    try:
        image_path = fetch_latest_image(force_refresh=True)
        print(f"   ✅ Successfully fetched image: {image_path}")
        print(f"   Exists: {image_path.exists()}")
        print(f"   Size: {image_path.stat().st_size} bytes")
    except Exception as e:
        print(f"   ❌ Failed to fetch image: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ Image fetching test completed successfully!")
    print("=" * 60)

