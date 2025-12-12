import subprocess
from playwright.async_api import async_playwright

WEBCAM_URL = "https://troyohio.gov/542/Live-Downtown-Webcams"
M3U8_IDENTIFIER = "playlist.m3u8"

async def grab_webcam_frame():
    # --- PHASE 1: Get the Tokenized HLS URL ---
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # 4. Intercept Request: Wait for the dynamic M3U8 file to be requested by the video player
        try:
            # Navigate to the page
            await page.goto(WEBCAM_URL)
            
            # Wait for the specific request to the Angelcam stream
            hls_request = await page.wait_for_request(
                lambda request: M3U8_IDENTIFIER in request.url,
                timeout=30000 # 30 seconds timeout
            )
            new_hls_url = hls_request.url
            
        except Exception as e:
            # Handle failure to get the URL (e.g., timeout, page structure changed)
            print(f"Error retrieving HLS URL: {e}")
            return False
            
        finally:
            await browser.close()

    # --- PHASE 2: Grab the Frame with FFmpeg ---
    # Example working command: ffmpeg -i "https://e1-na3.angelcam.com/cameras/98816/streams/hls/playlist.m3u8?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9%2EeyJpYXQiOjE3NjU1MTcxNDIsIm5iZiI6MTc2NTUxNzAyMiwiZXhwIjoxNzY1NTI0MzQyLCJkaWQiOiI5ODgxNiJ9%2EYWiSPlti%5FkzplBkx1dtevAD4%5F4Voo3C6O7SBi%5FdPwow" -vframes 1 -update 1 webcam_frame.jpg
    if new_hls_url:
        output_filename = "webcam_frame.jpg"
        ffmpeg_cmd = [
            "ffmpeg", 
            "-i", new_hls_url, 
            "-vframes", "1", 
            "-update", "1", 
            output_filename
        ]
        
        try:
            print(f"Running FFmpeg to capture frame: {output_filename}")
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
            print(f"Successfully captured frame to {output_filename}")
            return output_filename
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg failed with error: {e.stderr.decode()}")
            return False
    
    return False

# You would then call this function, likely within an asyncio context.
# Example: 
# import asyncio
# asyncio.run(grab_webcam_frame())