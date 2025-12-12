#!/usr/bin/env python3
"""
Robot Diary Service

A long-running service that periodically observes New Orleans, Louisiana
through a live YouTube stream and generates diary entries.
"""
import time
import signal
import sys
import logging
from pathlib import Path
from datetime import datetime
import pytz

from .config import (
    OBSERVATION_INTERVAL_HOURS,
    PROJECT_ROOT,
    PIRATE_WEATHER_KEY,
    OBSERVATION_TIMES,
    USE_SCHEDULED_OBSERVATIONS
)
from .scheduler import (
    parse_observation_times,
    get_next_observation_time,
    is_time_for_observation,
    get_observation_schedule_summary
)
from .camera import fetch_latest_image
from .llm import GroqClient, generate_dynamic_prompt, create_diary_entry
from .memory import MemoryManager
from .hugo import HugoGenerator
from .weather import PirateWeatherClient
from .context import get_context_metadata

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(PROJECT_ROOT / 'robot_diary.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Global flags
shutdown_requested = False
trigger_observation = False
last_observation_time = None  # Track when we last ran an observation
last_observation_scheduled_time = None  # Track which scheduled time we last ran

# Location timezone (from config)
from . import config as app_config
LOCATION_TZ = pytz.timezone(app_config.LOCATION_TIMEZONE)


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    shutdown_requested = True


def trigger_observation_handler(signum, frame):
    """Handle manual observation trigger signal (SIGUSR1)."""
    global trigger_observation
    logger.info(f"Received observation trigger signal {signum}")
    trigger_observation = True


def run_observation_cycle(dry_run: bool = False, force_image_refresh: bool = False):
    """
    Run a single observation cycle.
    
    Args:
        dry_run: If True, skip API calls and only test structure
        force_image_refresh: If True, force download of fresh image even if cached
    """
    logger.info("=" * 60)
    logger.info("Starting observation cycle" + (" (DRY RUN)" if dry_run else ""))
    logger.info("=" * 60)
    
    if dry_run:
        logger.info("DRY RUN MODE: Skipping API calls")
        return
    
    try:
        # Initialize components
        memory_manager = MemoryManager()
        llm_client = GroqClient()
        hugo_generator = HugoGenerator()
        
        # Step 1: Fetch latest image (with caching)
        logger.info("Step 1: Fetching latest webcam image...")
        image_path = fetch_latest_image(force_refresh=force_image_refresh)
        if force_image_refresh:
            logger.info(f"Using fresh image (force refresh): {image_path}")
        else:
            logger.info(f"Using image: {image_path}")
        
        # Step 2: Load recent memory
        logger.info("Step 2: Loading recent memory...")
        recent_memory = memory_manager.get_recent_memory(count=10)
        memory_count = memory_manager.get_total_count()
        logger.info(f"Loaded {len(recent_memory)} recent observations (total: {memory_count})")
        
        # Step 2.5: Fetch weather and context metadata
        logger.info("Step 2.5: Fetching weather and context metadata...")
        weather_data = {}
        if PIRATE_WEATHER_KEY:
            try:
                weather_client = PirateWeatherClient(PIRATE_WEATHER_KEY)
                weather_data = weather_client.get_current_weather(use_cache=True)
            except Exception as e:
                logger.warning(f"Failed to fetch weather: {e}")
        
        context_metadata = get_context_metadata(weather_data)
        logger.info(f"Context: {context_metadata['day_of_week']}, {context_metadata['date']} at {context_metadata['time']} ({context_metadata['season']} {context_metadata['time_of_day']})")
        if weather_data:
            logger.info(f"Weather: {weather_data.get('summary', 'Unknown')}, {weather_data.get('temperature', '?')}°F")
        
        # Step 3: Generate dynamic prompt
        logger.info("Step 3: Generating dynamic prompt...")
        optimized_prompt = generate_dynamic_prompt(recent_memory, llm_client, 
                                                   context_metadata, weather_data, memory_count)
        logger.debug(f"Optimized prompt: {optimized_prompt[:200]}...")
        
        # Step 4: Create diary entry
        logger.info("Step 4: Creating diary entry...")
        diary_entry = create_diary_entry(image_path, optimized_prompt, llm_client, context_metadata)
        logger.info(f"Diary entry created ({len(diary_entry)} characters)")
        
        # Step 5: Save to memory
        logger.info("Step 5: Saving to memory...")
        observation_id = len(memory_manager.get_recent_memory()) + 1
        memory_manager.add_observation(image_path, diary_entry)
        
        # Step 6: Generate Hugo post
        logger.info("Step 6: Generating Hugo post...")
        post_path = hugo_generator.create_post(diary_entry, image_path, observation_id, context_metadata)
        
        # Step 7: Build Hugo site
        logger.info("Step 7: Building Hugo site...")
        build_success = hugo_generator.build_site()
        
        # Step 8: Deploy site (if enabled and build succeeded)
        if build_success:
            logger.info("Step 8: Deploying site...")
            hugo_generator.deploy_site()
        else:
            logger.warning("Skipping deployment due to build failure")
        
        logger.info("=" * 60)
        logger.info("✅ Observation cycle completed successfully")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Error in observation cycle: {e}", exc_info=True)
        raise


def main():
    """Main service loop."""
    global shutdown_requested, trigger_observation, last_observation_time, last_observation_scheduled_time
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    try:
        signal.signal(signal.SIGUSR1, trigger_observation_handler)  # Manual trigger
    except AttributeError:
        # SIGUSR1 not available on Windows
        logger.warning("SIGUSR1 not available on this platform (Windows). Manual trigger via signal disabled.")
    
    logger.info("🤖 Robot Diary Service Starting...")
    logger.info(f"Project root: {PROJECT_ROOT}")
    
    # Parse observation schedule
    if USE_SCHEDULED_OBSERVATIONS:
        observation_times = parse_observation_times(OBSERVATION_TIMES)
        logger.info(get_observation_schedule_summary(observation_times))
        
        # Calculate next observation time
        now = datetime.now(LOCATION_TZ)
        next_time = get_next_observation_time(now, observation_times)
        logger.info(f"Next scheduled observation: {next_time.strftime('%A, %B %d at %I:%M %p %Z')}")
        logger.info("Service running. Waiting for scheduled observation time or manual triggers...")
    else:
        observation_times = None
        logger.info(f"Using interval-based observations: every {OBSERVATION_INTERVAL_HOURS} hours")
        
        # Run initial observation immediately only for interval-based mode
        logger.info("Running initial observation...")
        try:
            run_observation_cycle()
        except Exception as e:
            logger.error(f"Initial observation failed: {e}")
            sys.exit(1)
        
        logger.info("Service running. Waiting for next interval or manual triggers...")
    
    # Main service loop
    
    while not shutdown_requested:
        try:
            # Check every minute for scheduled times or manual triggers
            time.sleep(60)
            
            if shutdown_requested:
                break
            
            # Check for manual trigger
            if trigger_observation:
                logger.info("Manual observation triggered!")
                trigger_observation = False
                try:
                    run_observation_cycle()
                    last_observation_time = datetime.now(TROY_TZ)  # Update last observation time
                except Exception as e:
                    logger.error(f"Manual observation failed: {e}", exc_info=True)
                continue
            
            # Check for scheduled observation
            if USE_SCHEDULED_OBSERVATIONS and observation_times:
                now = datetime.now(LOCATION_TZ)
                
                # Find which scheduled time we're closest to (if any)
                current_time_only = now.time()
                matched_scheduled_time = None
                for obs_time in observation_times:
                    obs_minutes = obs_time.hour * 60 + obs_time.minute
                    current_minutes = current_time_only.hour * 60 + current_time_only.minute
                    time_diff = abs(current_minutes - obs_minutes)
                    if time_diff > 12 * 60:  # Handle wrap-around
                        time_diff = 24 * 60 - time_diff
                    if time_diff <= 5:  # Within 5 minute tolerance
                        matched_scheduled_time = obs_time
                        break
                
                # Check if we should run an observation
                should_run = False
                if matched_scheduled_time is not None:
                    # Check if we've already run for this scheduled time
                    if last_observation_scheduled_time != matched_scheduled_time:
                        # This is a new scheduled time, run it
                        should_run = True
                    elif last_observation_time is None:
                        # No previous observation recorded, run it
                        should_run = True
                    else:
                        # Check if enough time has passed (cooldown period)
                        time_since_last = (now - last_observation_time).total_seconds() / 60  # minutes
                        if time_since_last >= 10:  # At least 10 minutes cooldown
                            should_run = True
                        else:
                            logger.debug(f"Skipping observation - already ran for {matched_scheduled_time.strftime('%I:%M %p')} ({time_since_last:.1f} min ago, need 10 min cooldown)")
                
                if should_run:
                    next_time = get_next_observation_time(now, observation_times)
                    logger.info(f"⏰ Scheduled observation time reached ({matched_scheduled_time.strftime('%I:%M %p')})!")
                    try:
                        run_observation_cycle()
                        last_observation_time = datetime.now(TROY_TZ)  # Update last observation time
                        last_observation_scheduled_time = matched_scheduled_time  # Track which scheduled time we ran
                        logger.info(f"✅ Observation completed. Next scheduled observation: {next_time.strftime('%A, %B %d at %I:%M %p %Z')}")
                    except Exception as e:
                        logger.error(f"Scheduled observation failed: {e}", exc_info=True)
            elif not USE_SCHEDULED_OBSERVATIONS:
                # Fallback to interval-based (legacy mode)
                interval_seconds = OBSERVATION_INTERVAL_HOURS * 3600
                logger.warning("Interval-based mode is deprecated. Use scheduled observations instead.")
                time.sleep(interval_seconds - 60)  # Already slept 60 seconds
                if not shutdown_requested:
                    try:
                        run_observation_cycle()
                    except Exception as e:
                        logger.error(f"Interval observation failed: {e}", exc_info=True)
            
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in service loop: {e}", exc_info=True)
            logger.info("Continuing service...")
            time.sleep(60)  # Wait a minute before retrying
    
    logger.info("🤖 Robot Diary Service Stopped")


if __name__ == '__main__':
    main()

