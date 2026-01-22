"""Fetch live frames from YouTube streams using yt-dlp and FFmpeg."""
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import json
import logging

from ..config import IMAGES_DIR, YOUTUBE_STREAM_URL

logger = logging.getLogger(__name__)

# Cache metadata file to track latest image
CACHE_METADATA_FILE = IMAGES_DIR / '.cache_metadata.json'
IMAGE_CACHE_TTL_MINUTES = 30  # Cache expires after 30 minutes


def _load_cache_metadata():
    """Load cache metadata."""
    if CACHE_METADATA_FILE.exists():
        try:
            with open(CACHE_METADATA_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cache metadata: {e}")
    return {}


def _save_cache_metadata(metadata):
    """Save cache metadata."""
    try:
        with open(CACHE_METADATA_FILE, 'w') as f:
            json.dump(metadata, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save cache metadata: {e}")


def _get_image_hash(image_path: Path) -> str:
    """Generate a hash from image file to identify unique images."""
    try:
        with open(image_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        logger.warning(f"Failed to hash image: {e}")
        return hashlib.md5(str(datetime.now()).encode()).hexdigest()


def _get_youtube_stream_url(youtube_url: str) -> str:
    """
    Get the direct stream URL from a YouTube URL using yt-dlp.
    
    Tries multiple format options as fallbacks:
    1. No format specified (let yt-dlp choose automatically)
    2. 'b' (best pre-merged format)
    3. 'worst' (fallback for compatibility)
    
    Args:
        youtube_url: YouTube URL (watch or live)
        
    Returns:
        Direct stream URL for FFmpeg
        
    Raises:
        Exception: If all format attempts fail
        FileNotFoundError: If yt-dlp is not installed
    """
    logger.info(f"Getting stream URL from YouTube: {youtube_url}")
    
    # Try different format options as fallbacks
    format_options = [
        None,  # No format - let yt-dlp choose automatically (recommended)
        'b',   # Best pre-merged format
        'worst',  # Fallback option
    ]
    
    last_error = None
    for fmt_option in format_options:
        try:
            # Build command
            cmd = ['yt-dlp', '-g']  # Get URL only, don't download
            
            # Add format option if specified
            if fmt_option:
                cmd.extend(['-f', fmt_option])
            
            cmd.append(youtube_url)
            
            logger.debug(f"Trying yt-dlp with format: {fmt_option or 'auto'}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
            
            stream_url = result.stdout.strip()
            if not stream_url:
                raise ValueError("yt-dlp returned empty stream URL")
            
            logger.info(f"✅ Retrieved stream URL (format: {fmt_option or 'auto'}): {stream_url[:100]}...")
            return stream_url
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            logger.warning(f"yt-dlp failed with format '{fmt_option or 'auto'}': {error_msg[:200]}")
            last_error = error_msg
            
            # If this is the last option, we'll raise the error
            if fmt_option == format_options[-1]:
                break
            
            # Continue to next format option
            continue
            
        except FileNotFoundError:
            raise FileNotFoundError(
                "yt-dlp not found. Install with: pip install yt-dlp"
            )
    
    # All format options failed
    logger.error(f"All yt-dlp format options failed. Last error: {last_error}")
    raise Exception(
        f"Failed to get YouTube stream URL after trying all format options. "
        f"Last error: {last_error[:500] if last_error else 'Unknown error'}"
    )


def _capture_frame_with_ffmpeg(stream_url: str, output_path: Path) -> bool:
    """Capture a single frame from stream using FFmpeg."""
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", stream_url,
        "-vframes", "1",
        "-update", "1",
        "-y",  # Overwrite output file
        str(output_path)
    ]
    
    try:
        logger.info(f"Capturing frame with FFmpeg to: {output_path}")
        result = subprocess.run(
            ffmpeg_cmd,
            check=True,
            capture_output=True,
            timeout=30  # 30 second timeout
        )
        logger.info("✅ Frame captured successfully")
        return True
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timed out after 30 seconds")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed: {e.stderr.decode() if e.stderr else 'Unknown error'}")
        return False
    except FileNotFoundError:
        logger.error("FFmpeg not found. Is FFmpeg installed?")
        raise


def fetch_latest_image(force_refresh: bool = False) -> Path:
    """
    Fetch a live frame from YouTube stream using yt-dlp and FFmpeg.
    
    Uses intelligent caching to avoid unnecessary captures:
    - Only captures new frame if force_refresh is True or cache is missing/expired
    - Cache expires after 30 minutes
    - Compares image hash to detect if content changed
    
    Args:
        force_refresh: If True, capture new frame even if cached
        
    Returns:
        Path to the captured image file
        
    Raises:
        FileNotFoundError: If yt-dlp or FFmpeg is not installed
        Exception: If capture fails
    """
    # Check cache first (unless forcing refresh)
    cache_metadata = _load_cache_metadata()
    if not force_refresh and cache_metadata.get('latest_path'):
        cached_path = IMAGES_DIR / cache_metadata.get('latest_path')
        if cached_path.exists():
            # Check if cache is still valid (not expired)
            fetched_at = cache_metadata.get('fetched_at')
            if fetched_at:
                try:
                    cached_time = datetime.fromisoformat(fetched_at)
                    age = datetime.now() - cached_time
                    
                    if age < timedelta(minutes=IMAGE_CACHE_TTL_MINUTES):
                        logger.info(f"✅ Using cached image (age: {age}): {cached_path}")
                        return cached_path
                    else:
                        logger.info(f"Cache expired (age: {age}), capturing new frame")
                except Exception as e:
                    logger.warning(f"Error checking cache age: {e}, capturing new frame")
            else:
                # No timestamp, treat as expired
                logger.info("Cache missing timestamp, capturing new frame")
    
    # Capture new frame
    logger.info(f"Capturing live frame from YouTube stream: {YOUTUBE_STREAM_URL}")
    
    # Get stream URL using yt-dlp
    try:
        stream_url = _get_youtube_stream_url(YOUTUBE_STREAM_URL)
    except Exception as e:
        logger.error(f"Failed to get YouTube stream URL: {e}")
        raise
    
    # Capture frame with FFmpeg
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"youtube_{timestamp}.jpg"
    image_path = IMAGES_DIR / filename
    
    success = _capture_frame_with_ffmpeg(stream_url, image_path)
    if not success:
        raise Exception("Failed to capture frame with FFmpeg")
    
    # Calculate hash and update cache
    image_hash = _get_image_hash(image_path)
    cache_metadata = {
        'latest_hash': image_hash,
        'latest_path': filename,
        'stream_url': stream_url[:100] + '...' if len(stream_url) > 100 else stream_url,  # Store partial URL for reference
        'fetched_at': datetime.now().isoformat(),
        'source': 'youtube_live_stream',
        'youtube_url': YOUTUBE_STREAM_URL
    }
    _save_cache_metadata(cache_metadata)
    
    logger.info(f"✅ Live frame captured and saved: {image_path}")
    return image_path


def get_latest_cached_image() -> Optional[Path]:
    """
    Get the latest cached image if available.
    
    Returns:
        Path to cached image, or None if no cache exists
    """
    cache_metadata = _load_cache_metadata()
    if not cache_metadata:
        return None
    
    latest_path = cache_metadata.get('latest_path')
    if not latest_path:
        return None
    
    image_path = IMAGES_DIR / latest_path
    if image_path.exists():
        return image_path
    
    return None

