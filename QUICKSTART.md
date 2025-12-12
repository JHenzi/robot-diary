# Quick Start Guide

## First Time Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set up environment variables:**
   - Copy `.env.example` to `.env` (if it exists)
   - Add your API keys:
     - `WINDY_WEBCAMS_API_KEY`
     - `GROQ_API_KEY`

3. **Verify configuration:**
```bash
python -c "from src.config import *; print('Config OK')"
```

## Running the Service

### Option 1: Direct script
```bash
python run_service.py
```

### Option 2: As a module
```bash
python -m src
```

## How It Works

The service follows this workflow to **avoid unnecessary API calls**:

1. **Image Caching**: 
   - Checks if we already have the latest image
   - Only fetches from Windy API if image URL has changed
   - Caches metadata to avoid redundant downloads

2. **Observation Cycle**:
   - Fetches latest image (uses cache if available)
   - Loads recent memory
   - Generates dynamic prompt using `gpt-oss-20b` (cheaper model)
   - Creates diary entry using `llama-4-maverick` (vision model)
   - Saves to memory
   - Generates Hugo post
   - Builds Hugo site

3. **Memory Management**:
   - Stores observations in `memory/observations.json`
   - Automatically cleans old entries (default: 30 days)
   - Limits total entries (default: 50)

## Important Notes

- **First Run**: Will fetch image and make API calls
- **Subsequent Runs**: Will use cached image if URL hasn't changed
- **Force Refresh**: Set `force_refresh=True` in code to always fetch new image
- **API Safety**: The service is designed to minimize API calls through caching

## Configuration

Edit your `.env` file or set environment variables:

- `OBSERVATION_INTERVAL_HOURS`: How often to observe (default: 6)
- `HUGO_SITE_PATH`: Path to Hugo site (default: `./hugo`)
- `HUGO_BUILD_ON_UPDATE`: Auto-build Hugo (default: `true`)
- `MEMORY_RETENTION_DAYS`: How long to keep memories (default: 30)

## Troubleshooting

- **API Key Errors**: Check your `.env` file has correct keys
- **Hugo Build Fails**: Ensure Hugo is installed (`hugo version`)
- **Image Not Found**: Check Windy API key and webcam ID
- **Import Errors**: Make sure you're in the project root directory

