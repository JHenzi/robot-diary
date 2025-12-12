"""Configuration management for Robot Diary."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Groq API Configuration
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Weather API Configuration
PIRATE_WEATHER_KEY = os.getenv('PIRATE_WEATHER_KEY')

# Angelcam API Configuration
ANGEL_CAM_APIKEY = os.getenv('ANGEL_CAM_APIKEY')

# Service Configuration
OBSERVATION_INTERVAL_HOURS = float(os.getenv('OBSERVATION_INTERVAL_HOURS', '6'))
HUGO_SITE_PATH = Path(os.getenv('HUGO_SITE_PATH', './hugo')).resolve()
HUGO_BUILD_ON_UPDATE = os.getenv('HUGO_BUILD_ON_UPDATE', 'true').lower() == 'true'
HUGO_PUBLIC_DIR = HUGO_SITE_PATH / 'public'

# Deployment Configuration
DEPLOY_ENABLED = os.getenv('DEPLOY_ENABLED', 'false').lower() == 'true'
DEPLOY_METHOD = os.getenv('DEPLOY_METHOD', 'rsync').lower()  # 'rsync' or 'scp'
DEPLOY_DESTINATION = os.getenv('DEPLOY_DESTINATION', '')  # Format: user@host:/path/to/destination
DEPLOY_SSH_KEY = os.getenv('DEPLOY_SSH_KEY', '')  # Optional: path to SSH key file

# Observation Schedule Configuration
# Format: comma-separated times in "HH:MM" format (24-hour)
# Default: 9:00 AM and 4:20 PM
OBSERVATION_TIMES_STR = os.getenv('OBSERVATION_TIMES', '9:00,16:20')
OBSERVATION_TIMES = [t.strip() for t in OBSERVATION_TIMES_STR.split(',')]
USE_SCHEDULED_OBSERVATIONS = os.getenv('USE_SCHEDULED_OBSERVATIONS', 'true').lower() == 'true'

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
IMAGES_DIR = PROJECT_ROOT / 'images'
MEMORY_DIR = PROJECT_ROOT / 'memory'
HUGO_CONTENT_DIR = HUGO_SITE_PATH / 'content' / 'posts'
HUGO_STATIC_IMAGES_DIR = HUGO_SITE_PATH / 'static' / 'images'

# Memory Configuration
MEMORY_RETENTION_DAYS = int(os.getenv('MEMORY_RETENTION_DAYS', '30'))
MAX_MEMORY_ENTRIES = int(os.getenv('MAX_MEMORY_ENTRIES', '50'))

# Model Configuration
PROMPT_GENERATION_MODEL = 'openai/gpt-oss-20b'
VISION_MODEL = 'meta-llama/llama-4-maverick-17b-128e-instruct'

# Robot Configuration
ROBOT_NAME = 'B3N-T5-MNT'
ROBOT_TYPE = 'Maintenance Unit'
ROBOT_DESIGNATION = 'B3N-T5-MNT (Maintenance Unit)'

# Location Configuration
LOCATION_CITY = "New Orleans"
LOCATION_STATE = "Louisiana"
LOCATION_FULL = "New Orleans, Louisiana"

# Weather coordinates for New Orleans, Louisiana
LOCATION_LATITUDE = 29.9511
LOCATION_LONGITUDE = -90.0715

# YouTube Live Stream Configuration
YOUTUBE_STREAM_URL = os.getenv('YOUTUBE_STREAM_URL', 'https://www.youtube.com/watch?v=qHW8srS0ylo')

# Timezone for New Orleans (Central Time)
LOCATION_TIMEZONE = 'America/Chicago'

# Validation
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not set in environment")

if len(GROQ_API_KEY) < 10:
    raise ValueError("GROQ_API_KEY appears to be invalid (too short)")

# Validate YouTube URL format
if YOUTUBE_STREAM_URL and not ('youtube.com' in YOUTUBE_STREAM_URL or 'youtu.be' in YOUTUBE_STREAM_URL):
    raise ValueError(f"YOUTUBE_STREAM_URL appears invalid: {YOUTUBE_STREAM_URL}")

# Validate timezone
try:
    import pytz
    pytz.timezone(LOCATION_TIMEZONE)
except Exception as e:
    raise ValueError(f"Invalid timezone: {LOCATION_TIMEZONE} - {e}")

# Validate Hugo site exists
if not HUGO_SITE_PATH.exists():
    raise ValueError(f"HUGO_SITE_PATH does not exist: {HUGO_SITE_PATH}")
if not (HUGO_SITE_PATH / 'hugo.toml').exists() and not (HUGO_SITE_PATH / 'config.toml').exists():
    raise ValueError(f"HUGO_SITE_PATH does not appear to be a valid Hugo site: {HUGO_SITE_PATH}")

# Validate deployment config if enabled
if DEPLOY_ENABLED:
    if not DEPLOY_DESTINATION:
        raise ValueError("DEPLOY_ENABLED=true but DEPLOY_DESTINATION is not set")
    if DEPLOY_METHOD not in ['rsync', 'scp']:
        raise ValueError(f"Invalid DEPLOY_METHOD: {DEPLOY_METHOD}. Must be 'rsync' or 'scp'")

# Ensure directories exist
IMAGES_DIR.mkdir(exist_ok=True)
MEMORY_DIR.mkdir(exist_ok=True)
(PROJECT_ROOT / 'weather').mkdir(exist_ok=True)
HUGO_CONTENT_DIR.mkdir(parents=True, exist_ok=True)
HUGO_STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

