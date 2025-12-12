# Observation Schedule

B3N-T5-MNT makes observations on a scheduled basis to document its view of downtown Cincinnati.

## Default Schedule

**Observations occur twice daily:**
- **Morning**: 9:00 AM EST/EDT
- **Afternoon**: 4:20 PM EST/EDT

## Configuration

### Environment Variables

Set in your `.env` file:

```bash
# Observation schedule (comma-separated times in 24-hour format)
OBSERVATION_TIMES=9:00,16:20

# Enable scheduled observations (default: true)
USE_SCHEDULED_OBSERVATIONS=true
```

### Custom Schedule

To change the observation times, set `OBSERVATION_TIMES`:

```bash
# Example: Three times per day
OBSERVATION_TIMES=6:00,12:00,18:00

# Example: Once per day at noon
OBSERVATION_TIMES=12:00

# Example: Every 6 hours (not recommended, use interval mode instead)
OBSERVATION_TIMES=0:00,6:00,12:00,18:00
```

## Running the Service

### Start the Service

```bash
python run_service.py
```

The service will:
1. Run an initial observation immediately
2. Wait for scheduled observation times
3. Check every minute if it's time for an observation
4. Run observations at the scheduled times

### Manual Observation Trigger

You can trigger an observation manually at any time:

#### Option 1: Command Line Script
```bash
python observe_now.py
```

This runs a single observation cycle immediately and exits.

#### Option 2: Signal (Unix/Linux/Mac)
If the service is running, send it a SIGUSR1 signal:

```bash
# Find the process ID
ps aux | grep run_service.py

# Send trigger signal
kill -USR1 <PID>
```

The service will run an observation cycle on the next check (within 60 seconds).

## Schedule Behavior

### Time Window
Observations are triggered within a **5-minute window** around the scheduled time:
- Scheduled: 9:00 AM
- Window: 8:55 AM - 9:05 AM

This ensures observations happen even if the service is slightly delayed.

### Timezone
All times are in **Cincinnati timezone** (America/New_York):
- EST (Eastern Standard Time) in winter
- EDT (Eastern Daylight Time) in summer

### Next Observation
After each observation, the service logs when the next scheduled observation will occur.

## Examples

### View Current Schedule
When the service starts, it logs:
```
Observations scheduled at: 9:00 AM, 4:20 PM
```

### Service Running
```
🤖 Robot Diary Service Starting...
Observations scheduled at: 9:00 AM, 4:20 PM
Running initial observation...
...
Service running. Waiting for scheduled observations or manual triggers...
```

### Scheduled Observation Triggered
```
⏰ Scheduled observation time reached!
============================================================
Starting observation cycle
============================================================
...
Next scheduled observation: Thursday, December 12 at 4:20 PM EST
```

### Manual Trigger
```bash
$ python observe_now.py
🔍 Triggering manual observation...
============================================================
Starting observation cycle
============================================================
...
✅ Observation completed successfully!
```

## Troubleshooting

### Service Not Running Observations
- Check that `USE_SCHEDULED_OBSERVATIONS=true` in `.env`
- Verify `OBSERVATION_TIMES` is set correctly
- Check service logs: `tail -f robot_diary.log`

### Wrong Timezone
- The service uses Cincinnati timezone (America/New_York)
- Times are automatically adjusted for EST/EDT
- Check logs to see what time the service thinks it is

### Manual Trigger Not Working
- Make sure the service is actually running
- Check that you're using the correct process ID
- On Windows, SIGUSR1 is not available - use `observe_now.py` instead

## Legacy Interval Mode

If you prefer the old interval-based mode (not recommended):

```bash
USE_SCHEDULED_OBSERVATIONS=false
OBSERVATION_INTERVAL_HOURS=6
```

This will run observations every 6 hours regardless of time of day.

