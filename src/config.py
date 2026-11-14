"""Configuration management for Robot Diary."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Disable ChromaDB telemetry (must be set before chromadb is imported)
os.environ['ANONYMIZED_TELEMETRY'] = 'False'

# Load environment variables
load_dotenv()

# LLM API Configuration
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
# Anthropic key; CLAUDE_KEY is what .env uses, ANTHROPIC_API_KEY also works
CLAUDE_KEY = os.getenv('CLAUDE_KEY') or os.getenv('ANTHROPIC_API_KEY')
# 'claude' or 'groq'. Defaults to Claude whenever a Claude key is present.
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'claude' if CLAUDE_KEY else 'groq').lower()

# Weather API Configuration
PIRATE_WEATHER_KEY = os.getenv('PIRATE_WEATHER_KEY')

# Moltbook "Sign in with Moltbook" - app API key for verifying agent identity tokens
# Get at https://moltbook.com/developers/dashboard (required only for Moltbook-protected routes)
MOLTBOOK_APP_KEY = os.getenv('MOLTBOOK_APP_KEY', '').strip() or None

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
DEPLOY_HOST_IP = os.getenv('DEPLOY_HOST_IP', '')  # Optional: IP address to use instead of hostname from DEPLOY_DESTINATION

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
if LLM_PROVIDER == 'claude':
    # Haiku reads the frame and does the small jobs; Sonnet writes the entry.
    VISION_MODEL = os.getenv('CLAUDE_VISION_MODEL', 'claude-haiku-5-5')
    PROMPT_GENERATION_MODEL = os.getenv('CLAUDE_UTILITY_MODEL', 'claude-haiku-5-5')
    MEMORY_SUMMARIZATION_MODEL = os.getenv('CLAUDE_UTILITY_MODEL', 'claude-haiku-5-5')
    DIARY_WRITING_MODEL = os.getenv('CLAUDE_WRITING_MODEL', 'claude-sonnet-5-5')
    # Thinking depth per model (low | medium | high | xhigh | max)
    CLAUDE_EFFORT = {
        VISION_MODEL: os.getenv('CLAUDE_VISION_EFFORT', 'low'),
        PROMPT_GENERATION_MODEL: 'low',
        DIARY_WRITING_MODEL: os.getenv('CLAUDE_WRITING_EFFORT', 'medium'),
    }
else:
    PROMPT_GENERATION_MODEL = 'openai/gpt-oss-20b'
    VISION_MODEL = 'qwen/qwen3.6-27b'
    MEMORY_SUMMARIZATION_MODEL = 'openai/gpt-oss-20b'  # Cheap model for memory summarization
    # Diary Writing Model - can be overridden via environment variable
    DIARY_WRITING_MODEL = os.getenv('DIARY_WRITING_MODEL', VISION_MODEL)
    CLAUDE_EFFORT = {}

# Prompt Generation Configuration
USE_PROMPT_OPTIMIZATION = os.getenv('USE_PROMPT_OPTIMIZATION', 'false').lower() == 'true'

# Web Search Configuration
# Enable web search when using GPT-OSS-120B (default: true if using GPT-OSS-120B, false otherwise)
ENABLE_WEB_SEARCH = os.getenv('ENABLE_WEB_SEARCH', '').lower()
if ENABLE_WEB_SEARCH == '':
    # Auto-detect: enable if using GPT-OSS-120B
    ENABLE_WEB_SEARCH = (DIARY_WRITING_MODEL == 'openai/gpt-oss-120b')
else:
    ENABLE_WEB_SEARCH = ENABLE_WEB_SEARCH == 'true'

# Robot Configuration
ROBOT_NAME = 'B3N-T5-MNT'
ROBOT_TYPE = 'Maintenance Unit'
ROBOT_DESIGNATION = 'B3N-T5-MNT (Maintenance Unit)'

# Location Configuration
# The robot watches Bourbon Street in New Orleans. EarthCam ended that stream on
# 2026-09-24, so from 2026-10-05 to 2026-11-14 it was "away for maintenance" on
# Main Street in Madison, Indiana. It came home when EarthCam restarted the stream.
LOCATION_CITY = "New Orleans"
LOCATION_STATE = "Louisiana"
LOCATION_STATE_CODE = "LA"  # subdivision code for state holidays (Mardi Gras etc.)
LOCATION_FULL = "New Orleans, Louisiana"
LOCATION_STREET = "Bourbon Street"

# Weather coordinates for the French Quarter
LOCATION_LATITUDE = 29.9511
LOCATION_LONGITUDE = -90.0715

# Memories written during the Madison stay are labeled when recalled, so the robot
# knows why they describe a different street. Bounds are compared against stored
# memory dates, which are naive UTC ISO timestamps.
AWAY_PERIODS = [
    (
        os.getenv('AWAY_START', '2026-10-05T03:00:00'),
        os.getenv('AWAY_END', '2026-11-14T06:00:00'),
        "from your maintenance stay at the Main Street window in Madison, Indiana",
    ),
]

# YouTube Live Stream Configuration
# Note: EarthCam restarts streams under new IDs; override in .env via YOUTUBE_STREAM_URL.
YOUTUBE_STREAM_URL = os.getenv('YOUTUBE_STREAM_URL', 'https://www.youtube.com/watch?v=xqdukYhcGEU')

# Timezone for New Orleans (Central Time)
LOCATION_TIMEZONE = os.getenv('LOCATION_TIMEZONE', 'America/Chicago')

# Validation
if LLM_PROVIDER not in ('claude', 'groq'):
    raise ValueError(f"LLM_PROVIDER must be 'claude' or 'groq', got {LLM_PROVIDER!r}")

_active_key, _key_name = (CLAUDE_KEY, 'CLAUDE_KEY') if LLM_PROVIDER == 'claude' else (GROQ_API_KEY, 'GROQ_API_KEY')
if not _active_key:
    raise ValueError(f"{_key_name} not set in environment")

if len(_active_key) < 10:
    raise ValueError(f"{_key_name} appears to be invalid (too short)")

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
