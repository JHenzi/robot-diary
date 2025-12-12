"""Script to analyze and select a suitable public camera from Angelcam."""
import json
import logging
from pathlib import Path
from src.camera.angelcam_client import AngelcamClient
from src.config import LOCATION_CITY, LOCATION_STATE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CAMERAS_CACHE_FILE = Path("camera_selection.json")


def analyze_and_save_cameras():
    """Fetch, analyze, and save public cameras."""
    client = AngelcamClient()
    
    # First, try to find cameras in Troy, Ohio
    logger.info(f"Searching for cameras in {LOCATION_CITY}, {LOCATION_STATE}...")
    troy_cameras = client.find_camera_by_location(
        city=LOCATION_CITY,
        state=LOCATION_STATE,
        keywords=["downtown", "main", "street", "square", "center"]
    )
    
    if troy_cameras:
        logger.info(f"✅ Found {len(troy_cameras)} cameras in {LOCATION_CITY}, {LOCATION_STATE}")
        for camera in troy_cameras:
            logger.info(f"  - {camera.get('name')} (ID: {camera.get('id')}, Status: {camera.get('status')})")
            hls_url = client.get_camera_hls_url(camera)
            if hls_url:
                logger.info(f"    HLS URL available: {hls_url[:80]}...")
    else:
        logger.info(f"No cameras found in {LOCATION_CITY}, {LOCATION_STATE}, fetching all online cameras...")
        all_cameras = client.get_all_public_cameras(online_only=True)
        
        # Show first 10 cameras as examples
        logger.info(f"Found {len(all_cameras)} total online cameras. Showing first 10:")
        for camera in all_cameras[:10]:
            logger.info(f"  - {camera.get('name')} (ID: {camera.get('id')}, Status: {camera.get('status')})")
            hls_url = client.get_camera_hls_url(camera)
            if hls_url:
                logger.info(f"    HLS URL available")
    
    # Select the best camera
    selected_camera = None
    
    if troy_cameras:
        # Prefer cameras with HLS streams
        for camera in troy_cameras:
            if client.get_camera_hls_url(camera):
                selected_camera = camera
                break
        # If no HLS, take the first one
        if not selected_camera and troy_cameras:
            selected_camera = troy_cameras[0]
    else:
        # If no Troy cameras, get all and find one with HLS
        all_cameras = client.get_all_public_cameras(online_only=True)
        for camera in all_cameras:
            if client.get_camera_hls_url(camera):
                selected_camera = camera
                break
        # If still none, take first online camera
        if not selected_camera and all_cameras:
            selected_camera = all_cameras[0]
    
    if selected_camera:
        logger.info(f"\n✅ Selected camera: {selected_camera.get('name')} (ID: {selected_camera.get('id')})")
        hls_url = client.get_camera_hls_url(selected_camera)
        snapshot_url = client.get_camera_snapshot_url(selected_camera)
        
        camera_data = {
            "id": selected_camera.get('id'),
            "name": selected_camera.get('name'),
            "type": selected_camera.get('type'),
            "status": selected_camera.get('status'),
            "hls_url": hls_url,
            "snapshot_url": snapshot_url,
            "public_page_url": selected_camera.get('public_page_url')
        }
        
        # Save to file
        with open(CAMERAS_CACHE_FILE, 'w') as f:
            json.dump(camera_data, f, indent=2)
        
        logger.info(f"✅ Camera data saved to {CAMERAS_CACHE_FILE}")
        logger.info(f"   HLS URL: {hls_url[:100] if hls_url else 'N/A'}...")
        logger.info(f"   Snapshot URL: {snapshot_url[:100] if snapshot_url else 'N/A'}...")
        
        return camera_data
    else:
        logger.error("❌ No suitable camera found!")
        return None


if __name__ == "__main__":
    analyze_and_save_cameras()

