#!/usr/bin/env python3
"""
Manually trigger an observation cycle.

Usage:
    python observe_now.py [--force-refresh]

Options:
    --force-refresh    Force download of a fresh image, even if cached

This will run a single observation cycle immediately, regardless of schedule.
"""
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.service import run_observation_cycle
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Manually trigger an observation cycle')
    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Force download of a fresh image, even if cached'
    )
    args = parser.parse_args()
    
    if args.force_refresh:
        print("🔍 Triggering manual observation with FORCE REFRESH (will fetch new image)...")
    else:
        print("🔍 Triggering manual observation...")
    
    try:
        run_observation_cycle(force_image_refresh=args.force_refresh)
        print("✅ Observation completed successfully!")
    except Exception as e:
        print(f"❌ Observation failed: {e}")
        sys.exit(1)

