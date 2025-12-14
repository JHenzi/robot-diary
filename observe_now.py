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
from datetime import datetime
import pytz

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.service import run_observation_cycle, run_simulation_cycle
from src.config import LOCATION_TIMEZONE
from src.context.metadata import get_time_of_day
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
        '--use-cache',
        action='store_true',
        help='Use cached image if available (default: always fetch fresh image for manual observations)'
    )
    parser.add_argument(
        '--news-only',
        action='store_true',
        help='Create a news-based observation (text-only, no image)'
    )
    parser.add_argument(
        '--simulate',
        action='store_true',
        help='Run in simulation mode - generates markdown with prompt/context but does not save to memory or Hugo'
    )
    args = parser.parse_args()
    
    if args.simulate:
        print("🧪 Running SIMULATION mode (no memory/Hugo saving)...")
    elif args.news_only:
        print("📡 Triggering NEWS-BASED observation (text-only, no image)...")
    elif args.use_cache:
        print("🔍 Triggering manual observation (using cached image if available)...")
    else:
        print("🔍 Triggering manual observation with FORCE REFRESH (will fetch new image)...")
    
    try:
        # Determine observation type from current time
        location_tz = pytz.timezone(LOCATION_TIMEZONE)
        current_time = datetime.now(location_tz)
        current_hour = current_time.hour
        time_of_day = get_time_of_day(current_hour)
        observation_type = "morning" if time_of_day == "morning" else "evening"
        
        # Force refresh by default, unless --use-cache is specified
        force_refresh = not args.use_cache
        
        if args.simulate:
            sim_path = run_simulation_cycle(
                force_image_refresh=force_refresh,
                observation_type=observation_type,
                is_unscheduled=True  # Manual observations are always unscheduled
            )
            print(f"✅ Simulation completed successfully!")
            print(f"📄 Markdown saved to: {sim_path}")
        else:
            run_observation_cycle(
                force_image_refresh=force_refresh, 
                observation_type=observation_type,
                news_only=args.news_only,
                is_unscheduled=True  # Manual observations are always unscheduled
            )
            print("✅ Observation completed successfully!")
    except Exception as e:
        print(f"❌ Observation failed: {e}")
        sys.exit(1)

