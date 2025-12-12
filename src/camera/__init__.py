"""Camera integration for fetching live video frames."""
from .youtube_fetcher import fetch_latest_image, get_latest_cached_image

__all__ = ['fetch_latest_image', 'get_latest_cached_image']

