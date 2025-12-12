# Docker Setup Guide

## Prerequisites

1. Docker and Docker Compose installed
2. `.env` file with all required API keys (copy from `.env.example`)

## Required Environment Variables

Make sure your `.env` file contains:

```bash
# Required
GROQ_API_KEY=your_actual_groq_api_key
PIRATE_WEATHER_KEY=your_actual_pirate_weather_key
YOUTUBE_STREAM_URL=https://www.youtube.com/watch?v=qHW8srS0ylo

# Recommended settings
USE_SCHEDULED_OBSERVATIONS=true
TIMEZONE=America/Chicago
DEPLOY_ENABLED=false  # Set to true when ready to deploy
```

## Building and Running

### 1. Build the Docker image

```bash
docker-compose build
```

### 2. Start the service

```bash
docker-compose up -d
```

### 3. View logs

```bash
docker-compose logs -f robot-diary
```

### 4. Stop the service

```bash
docker-compose down
```

## Verifying It Works

1. **Check logs** - Should see "🤖 Robot Diary Service Starting..."
2. **Check scheduled time** - Should see "Next scheduled observation: ..."
3. **Wait for first observation** - Should complete successfully
4. **Check Hugo build** - Should see "✅ Hugo site built successfully"
5. **Check files** - `hugo/public/` should have new posts

## Troubleshooting

### Hugo not found
- The Dockerfile installs Hugo, but if you see this error, check the build logs
- Ensure Hugo installation step completed successfully

### API errors
- Verify all API keys in `.env` are correct
- Check logs for specific error messages

### Permission errors
- Ensure Docker has permission to write to mounted volumes
- Check that `images/`, `memory/`, `weather/`, and `hugo/` directories exist

### Service exits immediately
- Check logs: `docker-compose logs robot-diary`
- Verify `.env` file is mounted correctly
- Ensure all required environment variables are set

## Manual Observation Trigger

To trigger an observation manually while the container is running:

```bash
docker-compose exec robot-diary python observe_now.py
```

## Updating the Service

After making code changes:

```bash
# Rebuild the image
docker-compose build

# Restart the service
docker-compose restart
```

