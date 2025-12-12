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
    USE_SCHEDULED_OBSERVATIONS
)
from .scheduler import (
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


def run_observation_cycle(dry_run: bool = False, force_image_refresh: bool = False, observation_type: str = None):
    """
    Run a single observation cycle.
    
    Args:
        dry_run: If True, skip API calls and only test structure
        force_image_refresh: If True, force download of fresh image even if cached
        observation_type: Type of observation ('morning' or 'evening')
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
        
        context_metadata = get_context_metadata(weather_data, observation_type=observation_type)
        logger.info(f"Context: {context_metadata['day_of_week']}, {context_metadata['date']} at {context_metadata['time']} ({context_metadata['season']} {context_metadata['time_of_day']}, {context_metadata['observation_type']} observation)")
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
    global shutdown_requested, trigger_observation
    
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
    
    # Initialize memory manager to track schedule
    memory_manager = MemoryManager()
    
    # Get or calculate next observation time
    now = datetime.now(LOCATION_TZ)
    scheduled_info = memory_manager.get_next_scheduled_time()
    
    if scheduled_info and scheduled_info.get('datetime'):
        # Load existing schedule
        try:
            from datetime import datetime as dt
            next_time = dt.fromisoformat(scheduled_info['datetime'])
            next_time = LOCATION_TZ.localize(next_time.replace(tzinfo=None)) if next_time.tzinfo is None else next_time
            obs_type = scheduled_info.get('type', 'evening')
            logger.info(f"Loaded scheduled observation: {get_observation_schedule_summary(next_time, obs_type)}")
        except Exception as e:
            logger.warning(f"Error loading schedule: {e}, calculating new schedule")
            next_time, obs_type = get_next_observation_time(now)
            memory_manager.save_next_scheduled_time(next_time, obs_type)
            logger.info(f"Next scheduled observation: {get_observation_schedule_summary(next_time, obs_type)}")
    else:
        # Calculate new schedule
        next_time, obs_type = get_next_observation_time(now)
        memory_manager.save_next_scheduled_time(next_time, obs_type)
        logger.info(f"Next scheduled observation: {get_observation_schedule_summary(next_time, obs_type)}")
    
    logger.info("Service running. Waiting for scheduled observation time or manual triggers...")
    logger.info("(Send SIGUSR1 signal to trigger immediate observation)")
    
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
                    # Determine observation type from current time
                    current_time = datetime.now(LOCATION_TZ)
                    current_hour = current_time.hour
                    manual_obs_type = "morning" if 5 <= current_hour < 12 else "evening"
                    run_observation_cycle(observation_type=manual_obs_type)
                    
                    # Schedule next observation
                    next_time, obs_type = get_next_observation_time(current_time)
                    memory_manager.save_next_scheduled_time(next_time, obs_type)
                    logger.info(f"✅ Manual observation completed. Next scheduled: {get_observation_schedule_summary(next_time, obs_type)}")
                except Exception as e:
                    logger.error(f"Manual observation failed: {e}", exc_info=True)
                continue
            
            # Check for scheduled observation
            if USE_SCHEDULED_OBSERVATIONS:
                now = datetime.now(LOCATION_TZ)
                
                # Check if it's time for the scheduled observation
                if is_time_for_observation(now, next_time, tolerance_minutes=5):
                    logger.info(f"⏰ Scheduled {obs_type} observation time reached!")
                    try:
                        run_observation_cycle(observation_type=obs_type)
                        
                        # Schedule next observation
                        next_time, obs_type = get_next_observation_time(now)
                        memory_manager.save_next_scheduled_time(next_time, obs_type)
                        logger.info(f"✅ Observation completed. Next scheduled: {get_observation_schedule_summary(next_time, obs_type)}")
                    except Exception as e:
                        logger.error(f"Scheduled observation failed: {e}", exc_info=True)
                        # Still schedule next time even if this one failed
                        next_time, obs_type = get_next_observation_time(now)
                        memory_manager.save_next_scheduled_time(next_time, obs_type)
            else:
                # Fallback to interval-based (legacy mode)
                interval_seconds = OBSERVATION_INTERVAL_HOURS * 3600
                logger.warning("Interval-based mode is deprecated. Use scheduled observations instead.")
                time.sleep(interval_seconds - 60)  # Already slept 60 seconds
                if not shutdown_requested:
                    try:
                        current_time = datetime.now(LOCATION_TZ)
                        current_hour = current_time.hour
                        interval_obs_type = "morning" if 5 <= current_hour < 12 else "evening"
                        run_observation_cycle(observation_type=interval_obs_type)
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
