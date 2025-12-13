"""Angelcam API client for fetching public cameras."""
import requests
import logging
from typing import List, Dict, Optional
from ..config import ANGEL_CAM_APIKEY

logger = logging.getLogger(__name__)

ANGELCAM_API_BASE = "https://api.angelcam.com/v1"


class AngelcamClient:
    """Client for interacting with Angelcam API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the client with an API key."""
        self.api_key = api_key or ANGEL_CAM_APIKEY
        if not self.api_key:
            raise ValueError("ANGEL_CAM_APIKEY not set in environment")
        
        self.headers = {
            "Authorization": f"PersonalAccessToken {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def get_public_cameras(
        self, 
        limit: int = 100, 
        offset: int = 0, 
        online_only: bool = True
    ) -> Dict:
        """
        Fetch list of public cameras.
        
        Args:
            limit: Maximum number of cameras to return (default: 100)
            offset: Offset for pagination (default: 0)
            online_only: If True, only return online cameras (default: True)
        
        Returns:
            Dictionary with 'count', 'next', 'previous', and 'results' keys
        """
        url = f"{ANGELCAM_API_BASE}/public-cameras/"
        params = {
            "limit": limit,
            "offset": offset
        }
        if online_only:
            params["online"] = 1
        
        logger.info(f"Fetching public cameras from Angelcam API (limit={limit}, offset={offset}, online_only={online_only})...")
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            if response.status_code != 200:
                logger.error(f"API returned status {response.status_code}")
                logger.error(f"Response: {response.text}")
            response.raise_for_status()
            data = response.json()
            logger.info(f"✅ Retrieved {len(data.get('results', []))} cameras (total: {data.get('count', 0)})")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching public cameras: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response body: {e.response.text}")
            raise
    
    def get_all_public_cameras(self, online_only: bool = True) -> List[Dict]:
        """
        Fetch all public cameras (handles pagination automatically).
        
        Args:
            online_only: If True, only return online cameras (default: True)
        
        Returns:
            List of camera objects
        """
        all_cameras = []
        offset = 0
        limit = 100
        
        while True:
            data = self.get_public_cameras(limit=limit, offset=offset, online_only=online_only)
            all_cameras.extend(data.get('results', []))
            
            # Check if there are more pages
            if not data.get('next'):
                break
            
            offset += limit
        
        logger.info(f"✅ Retrieved total of {len(all_cameras)} cameras")
        return all_cameras
    
    def find_camera_by_location(
        self, 
        city: Optional[str] = None,
        state: Optional[str] = None,
        keywords: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Find cameras by location keywords in name or description.
        
        Args:
            city: City name to search for
            state: State name to search for
            keywords: Additional keywords to search for
        
        Returns:
            List of matching camera objects
        """
        all_cameras = self.get_all_public_cameras(online_only=True)
        
        search_terms = []
        if city:
            search_terms.append(city.lower())
        if state:
            search_terms.append(state.lower())
        if keywords:
            search_terms.extend([k.lower() for k in keywords])
        
        if not search_terms:
            return all_cameras
        
        matching_cameras = []
        for camera in all_cameras:
            name = camera.get('name', '').lower()
            # Check if any search term appears in the camera name
            if any(term in name for term in search_terms):
                matching_cameras.append(camera)
        
        logger.info(f"✅ Found {len(matching_cameras)} cameras matching location keywords: {search_terms}")
        return matching_cameras
    
    def get_camera_hls_url(self, camera: Dict) -> Optional[str]:
        """
        Extract HLS stream URL from a camera object.
        
        Args:
            camera: Camera object from API
        
        Returns:
            HLS stream URL or None if not available
        """
        streams = camera.get('streams', [])
        for stream in streams:
            if stream.get('format') == 'hls':
                return stream.get('url')
        return None
    
    def get_camera_snapshot_url(self, camera: Dict) -> Optional[str]:
        """
        Get live snapshot URL from a camera object.
        
        Args:
            camera: Camera object from API
        
        Returns:
            Snapshot URL or None if not available
        """
        return camera.get('live_snapshot')

