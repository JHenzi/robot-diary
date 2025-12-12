# Quick Reference Guide

## Running Observations

### Start the Service (Scheduled Mode)
```bash
python run_service.py
```

The service will:
- Run an observation immediately
- Then wait for scheduled times (9:00 AM and 4:20 PM)
- Check every minute if it's time for an observation

### Run a Single Observation Now
```bash
python observe_now.py
```

This runs one observation cycle immediately and exits. Perfect for testing or manual observations.

## Schedule Configuration

Default schedule: **9:00 AM** and **4:20 PM** (Cincinnati time)

To change, edit `.env`:
```bash
OBSERVATION_TIMES=9:00,16:20
```

## Manual Trigger (While Service is Running)

### Option 1: Use the script
```bash
python observe_now.py
```

### Option 2: Send signal (Unix/Linux/Mac only)
```bash
# Find process ID
ps aux | grep run_service.py

# Trigger observation
kill -USR1 <PID>
```

## What Happens During an Observation

1. ✅ Fetches latest webcam image (uses cache if unchanged)
2. ✅ Loads recent memory
3. ✅ Fetches weather data
4. ✅ Generates context-aware prompt (with date/time + weather)
5. ✅ Creates diary entry using AI vision
6. ✅ Saves to memory
7. ✅ Generates Hugo post
8. ✅ Builds Hugo site

## Files Created

- **Diary entries**: `hugo/content/posts/YYYY-MM-DD_observation_N.md`
- **Images**: `hugo/static/images/observation_N_*.jpg`
- **Memory**: `memory/observations.json`
- **Logs**: `robot_diary.log`

## Troubleshooting

**Service not running observations?**
- Check `USE_SCHEDULED_OBSERVATIONS=true` in `.env`
- Verify `OBSERVATION_TIMES` format (comma-separated, 24-hour)

**Want to test without waiting?**
- Use `python observe_now.py` for immediate observation

**Check service status:**
- View logs: `tail -f robot_diary.log`
- Check if running: `ps aux | grep run_service.py`

