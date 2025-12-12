import requests
import json
import os
from pathlib import Path
import sys

# Load environment variables from a .env file if present.
# Prefer using the `python-dotenv` package; fall back to a simple parser.
try:
    from dotenv import load_dotenv
    load_dotenv()
    _ENV_LOADED = True
except Exception:
    # Simple fallback: parse a local .env file (KEY=VALUE) if it exists.
    _env_path = Path(__file__).with_name('.env')
    if _env_path.exists():
        try:
            with _env_path.open('r', encoding='utf-8') as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' not in line:
                        continue
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and val and key not in os.environ:
                        os.environ[key] = val
            _ENV_LOADED = True
        except Exception:
            _ENV_LOADED = False
    else:
        _ENV_LOADED = False

# --- 1. CONFIGURATION (FROM ENV / .env) ---
# Recommended environment variable names: `WINDY_WEBCAMS_API_KEY`, `WEBCAM_ID`, `OUTPUT_FILENAME`
API_KEY = os.getenv('WINDY_WEBCAMS_API_KEY') or os.getenv('YOUR_WINDY_WEBCAMS_API_KEY')
WEBCAM_ID = os.getenv('WEBCAM_ID') or os.getenv('WINDY_WEBCAM_ID') or '1358084658'
OUTPUT_FILENAME = os.getenv('OUTPUT_FILENAME') or 'windy_webcam_image.jpg'

# --- 2. API REQUEST SETUP ---
# V3 Endpoint to get a single webcam by ID and include image URLs
# Validate configuration
if not API_KEY or API_KEY.strip() == '' or API_KEY.startswith('YOUR_'):
    print('\nError: No valid Windy webcams API key found.')
    print('Please set `WINDY_WEBCAMS_API_KEY` in your environment or in a `.env` file.')
    print('See `.env.example` for required variables.')
    sys.exit(1)

API_URL = f"https://api.windy.com/webcams/api/v3/webcams/{WEBCAM_ID}"

# The API key must be sent as an HTTP header
HEADERS = {
    "X-WINDY-API-KEY": API_KEY
}

# The 'include=images' modifier is crucial to get the image URLs
PARAMS = {
    "include": "images"
}

print(f"Requesting data for Webcam ID: {WEBCAM_ID}...")

# --- 3. FETCH WEBCAM DATA ---
try:
    response = requests.get(API_URL, headers=HEADERS, params=PARAMS)
    response.raise_for_status()  # Raises an exception for bad status codes (4xx or 5xx)
    webcam_data = response.json()
    
    # --- 4. EXTRACT IMAGE URL ---
    # The image URL is typically nested inside the 'images' field
    # We want the 'full' size of the 'current' image
    image_url = webcam_data.get('images', {}).get('current', {}).get('full')

    if not image_url:
        print("Error: Could not find the 'full' image URL in the response.")
        print("Response structure:", json.dumps(webcam_data, indent=4))
        exit()
        
    print(f"Successfully retrieved image URL: {image_url}")

    # --- 5. DOWNLOAD AND SAVE IMAGE ---
    image_response = requests.get(image_url)
    image_response.raise_for_status() 

    with open(OUTPUT_FILENAME, 'wb') as f:
        f.write(image_response.content)

    print(f"\n✅ SUCCESS! Image saved as {OUTPUT_FILENAME}")
    print(f"The LLM can now process this file for your blog post.")

except requests.exceptions.RequestException as e:
    print(f"❌ An error occurred during the API request: {e}")
    # Handle specific Windy API errors here (e.g., 401 for bad key)