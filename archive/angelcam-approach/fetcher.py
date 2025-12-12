"""Fetch live webcam frames using Playwright and FFmpeg."""
import subprocess
import asyncio
import hashlib
from pathlib import Path
from datetime import datetime
import json
import logging

from ..config import IMAGES_DIR

logger = logging.getLogger(__name__)

# Troy, Ohio webcam configuration
WEBCAM_URL = "https://troyohio.gov/542/Live-Downtown-Webcams"
M3U8_IDENTIFIER = "playlist.m3u8"

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


def _get_image_hash(image_path: Path) -> str:
    """Generate a hash from image file to identify unique images."""
    try:
        with open(image_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        logger.warning(f"Failed to hash image: {e}")
        return hashlib.md5(str(datetime.now()).encode()).hexdigest()


def _capture_frame_with_ffmpeg(hls_url: str, output_path: Path) -> bool:
    """Capture a single frame from HLS stream using FFmpeg."""
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", hls_url,
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


async def _get_hls_url():
    """Get the tokenized HLS URL from the webcam page using Playwright."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise ImportError("playwright is required. Install with: pip install playwright && playwright install chromium")
    
    async with async_playwright() as p:
        # Launch browser with realistic settings to avoid detection
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        # Create context with realistic browser fingerprint
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
            }
        )
        
        # Remove webdriver property
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = await context.new_page()
        
        # Set up request listener to catch all requests
        hls_url = None
        request_event = asyncio.Event()
        
        def handle_request(request):
            """Capture HLS requests."""
            nonlocal hls_url
            url = request.url
            if M3U8_IDENTIFIER in url and not hls_url:
                hls_url = url
                logger.info(f"✅ Captured HLS URL: {url[:100]}...")
                request_event.set()
        
        page.on('request', handle_request)
        
        try:
            # Navigate to the page
            logger.info(f"Navigating to: {WEBCAM_URL}")
            await page.goto(WEBCAM_URL, wait_until='networkidle', timeout=30000)
            
            # Check if we already got it
            if hls_url:
                return hls_url
            
            # Wait for the request event
            logger.info("Waiting for HLS stream request (up to 30 seconds)...")
            try:
                await asyncio.wait_for(request_event.wait(), timeout=30.0)
            except asyncio.TimeoutError:
                # Give it more time
                logger.info("Waiting additional 10 seconds...")
                await page.wait_for_timeout(10000)
                
                if not hls_url:
                    # Log all requests for debugging
                    logger.warning("HLS URL not captured. Checking page state...")
                    # Try to find iframe and interact with it
                    iframes = await page.query_selector_all('iframe')
                    logger.info(f"Found {len(iframes)} iframes")
                    for i, iframe in enumerate(iframes):
                        src = await iframe.get_attribute('src')
                        logger.info(f"  Iframe {i}: {src}")
                    
                    raise TimeoutError("HLS stream request not detected within timeout period")
            
            if not hls_url:
                raise ValueError("HLS URL was not captured")
            
            return hls_url
            
        except Exception as e:
            logger.error(f"Error retrieving HLS URL: {e}")
            raise
        finally:
            page.remove_listener('request', handle_request)
            await context.close()
            await browser.close()


def fetch_latest_image(force_refresh: bool = False) -> Path:
    """
    Fetch a live webcam frame from Troy, Ohio webcam using Playwright and FFmpeg.
    
    Uses intelligent caching to avoid unnecessary captures:
    - Only captures new frame if force_refresh is True or cache is missing
    - Compares image hash to detect if content changed
    
    Args:
        force_refresh: If True, capture new frame even if cached
        
    Returns:
        Path to the captured image file
        
    Raises:
        ImportError: If playwright is not installed
        FileNotFoundError: If FFmpeg is not installed
        Exception: If capture fails
    """
    # Check cache first (unless forcing refresh)
    cache_metadata = _load_cache_metadata()
    if not force_refresh and cache_metadata.get('latest_path'):
        cached_path = IMAGES_DIR / cache_metadata.get('latest_path')
        if cached_path.exists():
            logger.info(f"✅ Using cached image: {cached_path}")
            return cached_path
    
    # Capture new frame
    logger.info("Capturing live webcam frame from Troy, Ohio...")
    
    # Get HLS URL using Playwright
    try:
        hls_url = asyncio.run(_get_hls_url())
    except Exception as e:
        logger.error(f"Failed to get HLS URL: {e}")
        raise
    
    # Capture frame with FFmpeg
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"webcam_{timestamp}.jpg"
    image_path = IMAGES_DIR / filename
    
    success = _capture_frame_with_ffmpeg(hls_url, image_path)
    if not success:
        raise Exception("Failed to capture frame with FFmpeg")
    
    # Calculate hash and update cache
    image_hash = _get_image_hash(image_path)
    cache_metadata = {
        'latest_hash': image_hash,
        'latest_path': filename,
        'hls_url': hls_url[:100] + '...' if len(hls_url) > 100 else hls_url,  # Store partial URL for reference
        'fetched_at': datetime.now().isoformat(),
        'source': 'troy_ohio_live_webcam'
    }
    _save_cache_metadata(cache_metadata)
    
    logger.info(f"✅ Live frame captured and saved: {image_path}")
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
