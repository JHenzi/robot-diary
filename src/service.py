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
import random

from .config import (
    OBSERVATION_INTERVAL_HOURS,
    PROJECT_ROOT,
    PIRATE_WEATHER_KEY,
    USE_SCHEDULED_OBSERVATIONS,
    MEMORY_DIR
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
from .news import get_random_headlines, get_random_articles, get_random_cluster, get_cluster_articles
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


def run_news_based_observation(dry_run: bool = False, observation_type: str = None):
    """
    Run a news-based observation cycle (text-only, no image).
    
    This is used when image fetching fails or as a random variation.
    
    Args:
        dry_run: If True, skip API calls and only test structure
        observation_type: Type of observation ('morning' or 'evening')
    """
    logger.info("=" * 60)
    logger.info("Starting NEWS-BASED observation cycle" + (" (DRY RUN)" if dry_run else ""))
    logger.info("=" * 60)
    
    if dry_run:
        logger.info("DRY RUN MODE: Skipping API calls")
        return
    
    try:
        # Initialize components
        memory_manager = MemoryManager()
        llm_client = GroqClient()
        hugo_generator = HugoGenerator()
        
        # Step 1: Fetch random cluster and articles with full metadata
        logger.info("Step 1: Fetching news cluster and articles...")
        cluster = get_random_cluster()
        if not cluster:
            raise Exception("Failed to fetch news cluster")
        
        cluster_id = cluster.get('cluster_id')
        topic_label = cluster.get('topic_label', 'Unknown Topic')
        cluster_created_at = cluster.get('created_at')
        cluster_updated_at = cluster.get('updated_at')
        sentiment_dist = cluster.get('sentiment_distribution', {})
        
        articles = get_cluster_articles(cluster_id, limit=3)
        
        if not articles:
            raise Exception(f"Failed to fetch articles from cluster {cluster_id}")
        
        # Extract headlines for logging/display
        headlines = [article.get('title', '') for article in articles if article.get('title')]
        
        logger.info(f"Selected cluster: {cluster_id} - {topic_label}")
        logger.info(f"Articles: {len(articles)} (cluster created: {cluster_created_at}, updated: {cluster_updated_at})")
        logger.info(f"Headlines: {headlines}")
        
        # Step 2: Load recent memory
        logger.info("Step 2: Loading recent memory...")
        recent_memory = memory_manager.get_recent_memory(count=10)
        memory_count = memory_manager.get_total_count()
        logger.info(f"Loaded {len(recent_memory)} recent observations (total: {memory_count})")
        
        # Calculate days since first observation
        days_since_first = 0
        first_obs_date = memory_manager.get_first_observation_date()
        if first_obs_date:
            now = datetime.now(LOCATION_TZ)
            # Ensure first_obs_date is timezone-aware
            if first_obs_date.tzinfo is None:
                first_obs_date = LOCATION_TZ.localize(first_obs_date)
            else:
                first_obs_date = first_obs_date.astimezone(LOCATION_TZ)
            days_since_first = (now - first_obs_date).days
            logger.info(f"Days since first observation: {days_since_first}")
        else:
            logger.info("No previous observations found - this is the first observation")
        
        # Step 2.5: Fetch weather and context metadata
        logger.info("Step 2.5: Fetching weather and context metadata...")
        weather_data = {}
        if PIRATE_WEATHER_KEY:
            try:
                weather_client = PirateWeatherClient(PIRATE_WEATHER_KEY)
                weather_data = weather_client.get_current_weather(use_cache=True)
            except Exception as e:
                logger.warning(f"Failed to fetch weather: {e}")
                weather_data = {}  # Continue without weather
        
        context_metadata = get_context_metadata(weather_data, observation_type=observation_type)
        # Add news cluster info to context with full metadata
        context_metadata['news_cluster'] = {
            'cluster_id': cluster_id,
            'topic_label': topic_label,
            'created_at': cluster_created_at,
            'updated_at': cluster_updated_at,
            'sentiment_distribution': sentiment_dist,
            'articles': articles  # Full article objects with published_at, source, sentiment_label, etc.
        }
        logger.info(f"Context: {context_metadata['day_of_week']}, {context_metadata['date']} at {context_metadata['time']} ({context_metadata['season']} {context_metadata['time_of_day']}, {context_metadata['observation_type']} observation)")
        if weather_data:
            logger.info(f"Weather: {weather_data.get('summary', 'Unknown')}, {weather_data.get('temperature', '?')}°F")
        
        # Step 3: Generate dynamic prompt with news context
        logger.info("Step 3: Generating dynamic prompt for news-based observation...")
        
        # Create a special prompt for news-based observations
        # Identity context (informs perspective, mention when relevant)
        news_identity_context = """You are B3N-T5-MNT, a maintenance robot working in a building in New Orleans, Louisiana. You are an observer of human nature with a unique robotic perspective. Your identity informs your perspective and it should be mentioned when it makes sense or is relevant. Mention it casually when contextually appropriate (e.g., 'as a robot tasked with...'), but don't explain your entire backstory in every entry."""

        # Format articles with dates and sources for the prompt
        articles_text = []
        for article in articles:
            title = article.get('title', '')
            published_at = article.get('published_at', '')
            source = article.get('source', '')
            sentiment = article.get('sentiment_label', '')
            
            # Format date if available
            date_str = ""
            if published_at:
                try:
                    # Parse ISO format: "2025-12-12T17:33:20+00:00"
                    dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    date_str = f" (published {dt.strftime('%B %d, %Y at %I:%M %p')})"
                except Exception:
                    date_str = f" (published {published_at})"
            
            source_str = f" from {source}" if source else ""
            sentiment_str = f" [{sentiment}]" if sentiment else ""
            
            articles_text.append(f"- {title}{source_str}{date_str}{sentiment_str}")
        
        # Writing instructions for news-based observations
        news_prompt_base = f"""{news_identity_context}

You have picked up a transmission about "{topic_label}". The news items you've intercepted are:
{chr(10).join(articles_text)}

Write a diary entry reflecting on this news. Focus on:
- What you find interesting about this topic from your robotic perspective
- How it relates to your observations of people and human nature
- Patterns or behaviors you notice in the news that connect to your window observations
- Reflections on human activities and motivations
- Memory callbacks to specific past observations when relevant
- Consider the timing of the news - when these events happened relative to your current observation

Be thoughtful, reflective, and write from your unique robotic perspective. Reference your recent memories if relevant."""
        
        optimized_prompt = generate_dynamic_prompt(recent_memory, llm_client, 
                                                   context_metadata, weather_data, memory_count, days_since_first)
        # Combine with news-specific context
        full_prompt = f"""{news_prompt_base}

{optimized_prompt}

Remember: You have picked up a transmission about "{topic_label}". The news items are:
{chr(10).join(articles_text)}

Write as if you've intercepted these transmissions and are reflecting on them as an observer of human nature. Consider when these events happened relative to your current observation time. Focus on observation and reflection, not on explaining your identity or backstory."""
        
        logger.debug(f"News-based prompt: {full_prompt[:200]}...")
        
        # Step 4: Create text-only diary entry
        logger.info("Step 4: Creating text-only diary entry from news...")
        diary_entry = llm_client.create_diary_entry_from_text(full_prompt, context_metadata)
        logger.info(f"Diary entry created ({len(diary_entry)} characters)")
        
        # Step 5: Save to memory (no image path)
        logger.info("Step 5: Saving to memory...")
        memory_count = memory_manager.get_total_count()
        observation_id = memory_count + 1
        # Create a placeholder image path for memory (news-based entries don't have images)
        placeholder_image = PROJECT_ROOT / 'images' / 'news_transmission.png'
        memory_manager.add_observation(placeholder_image, diary_entry, image_url=f"news://{cluster_id}", llm_client=llm_client)
        
        # Step 5.5: Calculate NEXT scheduled observation (after this one completes)
        logger.info("Step 5.5: Calculating next scheduled observation...")
        from .scheduler import get_observation_schedule_summary, get_next_observation_time
        now = datetime.now(LOCATION_TZ)
        next_time, next_obs_type = get_next_observation_time(now)
        memory_manager.save_next_scheduled_time(next_time, next_obs_type)
        next_schedule = get_observation_schedule_summary(next_time, next_obs_type)
        logger.info(f"Next scheduled observation: {next_schedule}")
        
        # Step 6: Generate Hugo post (no image)
        logger.info("Step 6: Generating Hugo post...")
        timezone = context_metadata.get('timezone', 'CST') if context_metadata else 'CST'
        diary_entry_with_schedule = diary_entry + f"\n\n---\n\n*Next scheduled observation: {next_schedule} ({timezone})*"
        
        post_path = hugo_generator.create_post(diary_entry_with_schedule, placeholder_image, observation_id, context_metadata, is_news_based=True)
        
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
        logger.info("✅ News-based observation cycle completed successfully")
        logger.info("=" * 60)
        
        # Save the date of this news observation (so we don't trigger again immediately)
        # This needs to be done here so it works even when called from fallback or manual triggers
        try:
            import json
            last_news_file = MEMORY_DIR / '.last_news_observation.json'
            with open(last_news_file, 'w') as f:
                json.dump({'date': datetime.now().isoformat()}, f)
            logger.debug("Saved last news observation date")
        except Exception as e:
            logger.warning(f"Failed to save last news observation date: {e}")
        
    except Exception as e:
        logger.error(f"❌ Error in news-based observation cycle: {e}", exc_info=True)
        raise


def run_observation_cycle(dry_run: bool = False, force_image_refresh: bool = False, observation_type: str = None, news_only: bool = False, is_unscheduled: bool = False):
    """
    Run a single observation cycle.
    
    Args:
        dry_run: If True, skip API calls and only test structure
        force_image_refresh: If True, force download of fresh image even if cached
        observation_type: Type of observation ('morning' or 'evening')
        news_only: If True, skip image fetch and create news-based observation
    """
    # If news_only flag is set, run news-based observation
    if news_only:
        return run_news_based_observation(dry_run=dry_run, observation_type=observation_type)
    
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
        image_path = None
        try:
            image_path = fetch_latest_image(force_refresh=force_image_refresh)
            if force_image_refresh:
                logger.info(f"Using fresh image (force refresh): {image_path}")
            else:
                logger.info(f"Using image: {image_path}")
        except Exception as e:
            logger.error(f"Failed to fetch new image: {e}")
            logger.info("🔄 Falling back to news-based observation...")
            # Fall back to news-based observation
            return run_news_based_observation(dry_run=False, observation_type=observation_type)
        
        # Step 2: Load recent memory
        logger.info("Step 2: Loading recent memory...")
        recent_memory = memory_manager.get_recent_memory(count=10)
        memory_count = memory_manager.get_total_count()
        logger.info(f"Loaded {len(recent_memory)} recent observations (total: {memory_count})")
        
        # Calculate days since first observation
        days_since_first = 0
        first_obs_date = memory_manager.get_first_observation_date()
        if first_obs_date:
            now = datetime.now(LOCATION_TZ)
            # Ensure first_obs_date is timezone-aware
            if first_obs_date.tzinfo is None:
                first_obs_date = LOCATION_TZ.localize(first_obs_date)
            else:
                first_obs_date = first_obs_date.astimezone(LOCATION_TZ)
            days_since_first = (now - first_obs_date).days
            logger.info(f"Days since first observation: {days_since_first}")
        else:
            logger.info("No previous observations found - this is the first observation")
        
        # Step 2.5: Fetch weather, news, and context metadata
        logger.info("Step 2.5: Fetching weather, news, and context metadata...")
        weather_data = {}
        if PIRATE_WEATHER_KEY:
            try:
                weather_client = PirateWeatherClient(PIRATE_WEATHER_KEY)
                weather_data = weather_client.get_current_weather(use_cache=True)
            except Exception as e:
                logger.warning(f"Failed to fetch weather: {e}")
                weather_data = {}  # Continue without weather
        
        # Fetch news articles (40% chance to include in prompt)
        news_articles = []
        if random.random() < 0.40:  # 40% chance
            try:
                news_articles = get_random_articles(count=2)
                if news_articles:
                    # Extract headlines for backward compatibility
                    news_headlines = [article.get('title', '') for article in news_articles if article.get('title')]
                    logger.info(f"Fetched news articles: {news_headlines}")
            except Exception as e:
                logger.warning(f"Failed to fetch news: {e}")
                news_articles = []
        
        context_metadata = get_context_metadata(weather_data, observation_type=observation_type)
        # Add news articles to context metadata (full objects with dates, sources, etc.)
        context_metadata['news_articles'] = news_articles
        # Also include headlines for backward compatibility
        context_metadata['news_headlines'] = [article.get('title', '') for article in news_articles if article.get('title')]
        # Mark as unscheduled if this is a manual observation
        context_metadata['is_unscheduled'] = is_unscheduled
        logger.info(f"Context: {context_metadata['day_of_week']}, {context_metadata['date']} at {context_metadata['time']} ({context_metadata['season']} {context_metadata['time_of_day']}, {context_metadata['observation_type']} observation)")
        if weather_data:
            logger.info(f"Weather: {weather_data.get('summary', 'Unknown')}, {weather_data.get('temperature', '?')}°F")
        
        # Step 3: Generate dynamic prompt
        logger.info("Step 3: Generating dynamic prompt...")
        optimized_prompt = generate_dynamic_prompt(recent_memory, llm_client, 
                                                   context_metadata, weather_data, memory_count, days_since_first)
        logger.debug(f"Optimized prompt: {optimized_prompt[:200]}...")
        
        # Step 4: Create diary entry
        logger.info("Step 4: Creating diary entry...")
        diary_entry = create_diary_entry(image_path, optimized_prompt, llm_client, context_metadata)
        logger.info(f"Diary entry created ({len(diary_entry)} characters)")
        
        # Step 5: Save to memory
        logger.info("Step 5: Saving to memory...")
        # Get observation ID from memory count (will be unique per observation)
        memory_count = memory_manager.get_total_count()
        observation_id = memory_count + 1
        memory_manager.add_observation(image_path, diary_entry, llm_client=llm_client)
        
        # Step 5.5: Calculate NEXT scheduled observation (after this one completes)
        logger.info("Step 5.5: Calculating next scheduled observation...")
        from .scheduler import get_observation_schedule_summary, get_next_observation_time
        now = datetime.now(LOCATION_TZ)
        next_time, next_obs_type = get_next_observation_time(now)
        memory_manager.save_next_scheduled_time(next_time, next_obs_type)
        next_schedule = get_observation_schedule_summary(next_time, next_obs_type)
        logger.info(f"Next scheduled observation: {next_schedule}")
        
        # Step 6: Generate Hugo post
        logger.info("Step 6: Generating Hugo post...")
        timezone = context_metadata.get('timezone', 'CST') if context_metadata else 'CST'
        diary_entry_with_schedule = diary_entry + f"\n\n---\n\n*Next scheduled observation: {next_schedule} ({timezone})*"
        
        post_path = hugo_generator.create_post(diary_entry_with_schedule, image_path, observation_id, context_metadata)
        
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


def run_simulation_cycle(force_image_refresh: bool = False, observation_type: str = None, is_unscheduled: bool = False):
    """
    Run a simulation observation cycle - generates diary entry and prompt but doesn't save to memory or Hugo.
    
    Outputs a markdown file with:
    - The prompt/context at the top
    - The diary entry
    - The image link
    
    Args:
        force_image_refresh: If True, force download of fresh image even if cached
        observation_type: Type of observation ('morning' or 'evening')
    """
    logger.info("=" * 60)
    logger.info("Starting SIMULATION observation cycle")
    logger.info("=" * 60)
    
    try:
        # Initialize components (no Hugo generator needed)
        memory_manager = MemoryManager()
        llm_client = GroqClient()
        
        # Step 1: Fetch latest image (with caching)
        logger.info("Step 1: Fetching latest webcam image...")
        image_path = None
        try:
            image_path = fetch_latest_image(force_refresh=force_image_refresh)
            if force_image_refresh:
                logger.info(f"Using fresh image (force refresh): {image_path}")
            else:
                logger.info(f"Using image: {image_path}")
        except Exception as e:
            logger.error(f"Failed to fetch new image: {e}")
            raise Exception("Simulation requires an image - cannot proceed without one")
        
        # Step 2: Load recent memory
        logger.info("Step 2: Loading recent memory...")
        recent_memory = memory_manager.get_recent_memory(count=10)
        memory_count = memory_manager.get_total_count()
        logger.info(f"Loaded {len(recent_memory)} recent observations (total: {memory_count})")
        
        # Calculate days since first observation
        days_since_first = 0
        first_obs_date = memory_manager.get_first_observation_date()
        if first_obs_date:
            now = datetime.now(LOCATION_TZ)
            # Ensure first_obs_date is timezone-aware
            if first_obs_date.tzinfo is None:
                first_obs_date = LOCATION_TZ.localize(first_obs_date)
            else:
                first_obs_date = first_obs_date.astimezone(LOCATION_TZ)
            days_since_first = (now - first_obs_date).days
            logger.info(f"Days since first observation: {days_since_first}")
        else:
            logger.info("No previous observations found - this is the first observation")
        
        # Step 2.5: Fetch weather, news, and context metadata
        logger.info("Step 2.5: Fetching weather, news, and context metadata...")
        weather_data = {}
        if PIRATE_WEATHER_KEY:
            try:
                weather_client = PirateWeatherClient(PIRATE_WEATHER_KEY)
                weather_data = weather_client.get_current_weather(use_cache=True)
            except Exception as e:
                logger.warning(f"Failed to fetch weather: {e}")
                weather_data = {}  # Continue without weather
        
        # Fetch news articles (40% chance to include in prompt)
        news_articles = []
        if random.random() < 0.40:  # 40% chance
            try:
                news_articles = get_random_articles(count=2)
                if news_articles:
                    # Extract headlines for backward compatibility
                    news_headlines = [article.get('title', '') for article in news_articles if article.get('title')]
                    logger.info(f"Fetched news articles: {news_headlines}")
            except Exception as e:
                logger.warning(f"Failed to fetch news: {e}")
                news_articles = []
        
        context_metadata = get_context_metadata(weather_data, observation_type=observation_type)
        # Add news articles to context metadata (full objects with dates, sources, etc.)
        context_metadata['news_articles'] = news_articles
        # Also include headlines for backward compatibility
        context_metadata['news_headlines'] = [article.get('title', '') for article in news_articles if article.get('title')]
        # Mark as unscheduled if this is a manual observation
        context_metadata['is_unscheduled'] = is_unscheduled
        logger.info(f"Context: {context_metadata['day_of_week']}, {context_metadata['date']} at {context_metadata['time']} ({context_metadata['season']} {context_metadata['time_of_day']}, {context_metadata['observation_type']} observation)")
        if weather_data:
            logger.info(f"Weather: {weather_data.get('summary', 'Unknown')}, {weather_data.get('temperature', '?')}°F")
        
        # Step 3: Generate dynamic prompt
        logger.info("Step 3: Generating dynamic prompt...")
        optimized_prompt = generate_dynamic_prompt(recent_memory, llm_client, 
                                                   context_metadata, weather_data, memory_count, days_since_first)
        logger.debug(f"Optimized prompt: {optimized_prompt[:200]}...")
        
        # Step 4: Create diary entry
        logger.info("Step 4: Creating diary entry...")
        diary_entry = create_diary_entry(image_path, optimized_prompt, llm_client, context_metadata)
        logger.info(f"Diary entry created ({len(diary_entry)} characters)")
        
        # Get the full prompt (includes image description) if available
        full_prompt = getattr(llm_client, '_last_full_prompt', optimized_prompt)
        
        # Step 5: Generate simulation markdown file
        logger.info("Step 5: Generating simulation markdown file...")
        
        # Create simulations directory
        simulations_dir = PROJECT_ROOT / 'simulations'
        simulations_dir.mkdir(exist_ok=True)
        
        # Generate filename with timestamp
        now = datetime.now(LOCATION_TZ)
        timestamp = now.strftime('%Y-%m-%d_%H%M%S')
        sim_filename = f"simulation_{timestamp}.md"
        sim_path = simulations_dir / sim_filename
        
        # Format context metadata for display
        context_display = []
        context_display.append(f"**Date/Time:** {context_metadata.get('date', 'Unknown')} at {context_metadata.get('time', 'Unknown')}")
        context_display.append(f"**Day:** {context_metadata.get('day_of_week', 'Unknown')}")
        context_display.append(f"**Season:** {context_metadata.get('season', 'Unknown')}")
        context_display.append(f"**Time of Day:** {context_metadata.get('time_of_day', 'Unknown')}")
        context_display.append(f"**Observation Type:** {context_metadata.get('observation_type', 'Unknown')}")
        
        if weather_data:
            temp = weather_data.get('temperature', '?')
            summary = weather_data.get('summary', 'Unknown')
            context_display.append(f"**Weather:** {summary}, {temp}°F")
        
        if news_articles:
            context_display.append(f"**News Articles:** {len(news_articles)} articles included")
        
        context_display.append(f"**Memory Count:** {memory_count} total observations")
        context_display.append(f"**Days Since First:** {days_since_first}")
        
        # Get relative image path for markdown (from simulations/ directory)
        # Simulations are in PROJECT_ROOT/simulations/, images are in PROJECT_ROOT/images/
        # So we need ../images/ relative path
        try:
            # Get relative path from PROJECT_ROOT
            image_rel_to_root = image_path.relative_to(PROJECT_ROOT)
            # Convert to relative path from simulations/ directory
            image_rel_path = f"../{image_rel_to_root}"
        except ValueError:
            # Path is not relative to PROJECT_ROOT, use relative path assuming images/ directory
            image_rel_path = f"../images/{image_path.name}"
        
        # Write markdown file
        with open(sim_path, 'w', encoding='utf-8') as f:
            f.write("# Simulation Observation\n\n")
            f.write(f"**Generated:** {now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n\n")
            f.write("## Context\n\n")
            f.write("\n".join(f"- {item}" for item in context_display))
            f.write("\n\n")
            f.write("---\n\n")
            f.write("## Prompt Sent to LLM\n\n")
            f.write("```\n")
            f.write(full_prompt)  # Use full prompt that includes image description
            f.write("\n```\n\n")
            f.write("---\n\n")
            f.write("## Diary Entry\n\n")
            f.write(diary_entry)
            f.write("\n\n")
            f.write("---\n\n")
            f.write("## Image\n\n")
            f.write(f"![Observation Image]({image_rel_path})\n\n")
        
        logger.info(f"✅ Simulation markdown saved to: {sim_path}")
        logger.info("=" * 60)
        logger.info("✅ Simulation cycle completed successfully")
        logger.info("=" * 60)
        
        return str(sim_path)
        
    except Exception as e:
        logger.error(f"❌ Error in simulation cycle: {e}", exc_info=True)
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
    
    # Track last news-based observation (for random triggering)
    last_news_observation_file = MEMORY_DIR / '.last_news_observation.json'
    
    def get_last_news_observation_date():
        """Get the date of the last news-based observation."""
        if not last_news_observation_file.exists():
            return None
        try:
            import json
            with open(last_news_observation_file, 'r') as f:
                data = json.load(f)
                return datetime.fromisoformat(data.get('date', ''))
        except:
            return None
    
    def save_last_news_observation_date():
        """Save the current date as last news observation date."""
        try:
            import json
            with open(last_news_observation_file, 'w') as f:
                json.dump({'date': datetime.now().isoformat()}, f)
        except Exception as e:
            logger.warning(f"Failed to save last news observation date: {e}")
    
    # Get or calculate next observation time
    now = datetime.now(LOCATION_TZ)
    scheduled_info = memory_manager.get_next_scheduled_time()
    
    if scheduled_info and scheduled_info.get('datetime'):
        # Load existing schedule
        try:
            from datetime import datetime as dt
            next_time = dt.fromisoformat(scheduled_info['datetime'])
            # Ensure timezone-aware and convert to LOCATION_TZ for proper comparison
            if next_time.tzinfo is None:
                next_time = LOCATION_TZ.localize(next_time)
            else:
                # Convert to LOCATION_TZ if it's in a different timezone
                next_time = next_time.astimezone(LOCATION_TZ)
            obs_type = scheduled_info.get('type', 'evening')
            
            # Check if scheduled time is in the past - if so, recalculate
            if next_time < now:
                logger.warning(f"Loaded scheduled time ({get_observation_schedule_summary(next_time, obs_type)}) is in the past. Recalculating...")
                next_time, obs_type = get_next_observation_time(now)
                memory_manager.save_next_scheduled_time(next_time, obs_type)
                logger.info(f"Next scheduled observation: {get_observation_schedule_summary(next_time, obs_type)}")
            else:
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
                        # Randomly decide if this should be a news-based observation (10% chance, or if it's been 3+ days)
                        last_news_date = get_last_news_observation_date()
                        days_since_news = None
                        if last_news_date:
                            days_since_news = (now - last_news_date.replace(tzinfo=LOCATION_TZ)).days
                        
                        use_news_observation = False
                        if days_since_news is None or days_since_news >= 3:
                            # It's been 3+ days since last news observation, do one
                            use_news_observation = True
                            logger.info(f"Triggering news-based observation (last one was {days_since_news} days ago)")
                        elif random.random() < 0.10:  # 10% random chance
                            use_news_observation = True
                            logger.info("Randomly triggering news-based observation")
                        
                        if use_news_observation:
                            run_news_based_observation(observation_type=obs_type)
                            save_last_news_observation_date()
                        else:
                            run_observation_cycle(observation_type=obs_type)
                        
                        # Read the next scheduled time that was saved by the observation cycle
                        next_schedule = memory_manager.get_next_scheduled_time()
                        if next_schedule:
                            next_time = datetime.fromisoformat(next_schedule['datetime']).astimezone(LOCATION_TZ)
                            obs_type = next_schedule['type']
                            logger.info(f"✅ Observation completed. Next scheduled: {get_observation_schedule_summary(next_time, obs_type)}")
                        else:
                            # Fallback: calculate if somehow not saved
                            next_time, obs_type = get_next_observation_time(now)
                            memory_manager.save_next_scheduled_time(next_time, obs_type)
                            logger.info(f"✅ Observation completed. Next scheduled: {get_observation_schedule_summary(next_time, obs_type)}")
                    except Exception as e:
                        logger.error(f"Scheduled observation failed: {e}", exc_info=True)
                        # Still schedule next time even if this one failed (since observation cycle didn't complete)
                        next_time, obs_type = get_next_observation_time(now)
                        memory_manager.save_next_scheduled_time(next_time, obs_type)
                        logger.info(f"✅ Next scheduled (after error): {get_observation_schedule_summary(next_time, obs_type)}")
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
