#!/usr/bin/env python3
"""Update the schedule.json file to tomorrow morning (CST)."""
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

# CST is UTC-6, CDT is UTC-5 (we'll use UTC-6 for simplicity)
# In December, it's CST (UTC-6)
CST_OFFSET = timedelta(hours=-6)
LOCATION_TZ = timezone(CST_OFFSET)

# Get tomorrow morning (8:30 AM) in CST
now_utc = datetime.now(timezone.utc)
now_cst = now_utc.astimezone(LOCATION_TZ)
tomorrow = now_cst + timedelta(days=1)
tomorrow_morning = tomorrow.replace(hour=8, minute=30, second=0, microsecond=0)

# Create schedule
schedule = {
    "next_observation": {
        "datetime": tomorrow_morning.isoformat(),
        "type": "morning"
    },
    "last_updated": datetime.now(LOCATION_TZ).isoformat()
}

# Atomic write
schedule_file = Path("memory/schedule.json")
temp_file = schedule_file.with_suffix('.json.tmp')

try:
    with open(temp_file, 'w') as f:
        json.dump(schedule, f, indent=2)
        f.flush()
        import os
        os.fsync(f.fileno())
    
    temp_file.replace(schedule_file)
    print(f"✅ Schedule updated successfully!")
    print(f"   Next observation: {tomorrow_morning.strftime('%A, %B %d at %I:%M %p')} (CST)")
    print(f"   Type: morning")
    print(f"   ISO: {tomorrow_morning.isoformat()}")
except Exception as e:
    print(f"❌ Error updating schedule: {e}")
    if temp_file.exists():
        temp_file.unlink()

