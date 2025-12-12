"""Fetch and cache webcam images from Windy API."""
import requests
import hashlib
from pathlib import Path
from datetime import datetime
import json
import logging

from ..config import WINDY_API_KEY, WEBCAM_ID, IMAGES_DIR

logger = logging.getLogger(__name__)

# Cache metadata file to track latest image
CACHE_METADATA_FILE = IMAGES_DIR / '.cache_metadata.json'


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


def _get_image_hash(image_url: str) -> str:
    """Generate a hash from image URL to identify unique images."""
    return hashlib.md5(image_url.encode()).hexdigest()


def fetch_latest_image(force_refresh: bool = False) -> Path:
    """
    Fetch the latest webcam image from Windy API.
    
    Uses intelligent caching to avoid unnecessary downloads:
    - Checks API for current image URL
    - Compares URL hash with cached image
    - Only downloads if URL changed or cache missing
    
    Args:
        force_refresh: If True, fetch new image even if cached
        
    Returns:
        Path to the cached image file
        
    Raises:
        requests.RequestException: If API call fails
        ValueError: If image URL not found in response
    """
    # Fetch image URL from API (minimal API call to check for updates)
    logger.info(f"Checking Windy API for latest image URL (Webcam ID: {WEBCAM_ID})...")
    
    api_url = f"https://api.windy.com/webcams/api/v3/webcams/{WEBCAM_ID}"
    headers = {"X-WINDY-API-KEY": WINDY_API_KEY}
    params = {"include": "images"}
    
    response = requests.get(api_url, headers=headers, params=params)
    response.raise_for_status()
    webcam_data = response.json()
    
    # Extract image URL - try 'full' first, then 'preview' as fallback
    current_images = webcam_data.get('images', {}).get('current', {})
    image_url = current_images.get('full') or current_images.get('preview')
    if not image_url:
        raise ValueError(f"Image URL not found in API response. Available fields: {list(current_images.keys())}")
    
    # Check if this is the same image we already have
    image_hash = _get_image_hash(image_url)
    cache_metadata = _load_cache_metadata()
    
    # Use cache if URL hasn't changed and we're not forcing refresh
    if not force_refresh and cache_metadata.get('latest_hash') == image_hash:
        cached_path = IMAGES_DIR / cache_metadata.get('latest_path', '')
        if cached_path.exists():
            logger.info(f"✅ Image URL unchanged, using cached file: {cached_path}")
            return cached_path
    
    # Download new image
    logger.info(f"Downloading new image from: {image_url}")
    image_response = requests.get(image_url)
    image_response.raise_for_status()
    
    # Save with timestamp and hash
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"webcam_{timestamp}_{image_hash[:8]}.jpg"
    image_path = IMAGES_DIR / filename
    
    with open(image_path, 'wb') as f:
        f.write(image_response.content)
    
    # Update cache metadata
    cache_metadata = {
        'latest_hash': image_hash,
        'latest_path': filename,
        'latest_url': image_url,
        'fetched_at': datetime.now().isoformat(),
        'webcam_id': WEBCAM_ID
    }
    _save_cache_metadata(cache_metadata)
    
    logger.info(f"✅ Image saved and cached: {image_path}")
    return image_path


def get_latest_cached_image() -> Path | None:
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

