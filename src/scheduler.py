"""Scheduler for time-based observations."""
from datetime import datetime, time, timedelta
import pytz
from typing import List, Tuple

# Cincinnati timezone
CINCINNATI_TZ = pytz.timezone('America/New_York')

# Default observation times (9:00 AM and 4:20 PM)
DEFAULT_OBSERVATION_TIMES = [
    time(9, 0),   # 9:00 AM
    time(16, 20)  # 4:20 PM
]


def parse_observation_times(time_strings: List[str]) -> List[time]:
    """
    Parse observation time strings into time objects.
    
    Args:
        time_strings: List of time strings in format "HH:MM" or "HH:MM:SS"
        
    Returns:
        List of time objects
        
    Example:
        parse_observation_times(["9:00", "16:20"]) -> [time(9, 0), time(16, 20)]
    """
    times = []
    for time_str in time_strings:
        parts = time_str.split(':')
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
        times.append(time(hour, minute, second))
    return sorted(times)


def get_next_observation_time(current_time: datetime, observation_times: List[time]) -> datetime:
    """
    Get the next scheduled observation time.
    
    Args:
        current_time: Current datetime (timezone-aware)
        observation_times: List of observation times (time objects)
        
    Returns:
        Next observation datetime
    """
    current_time_cincy = current_time.astimezone(CINCINNATI_TZ)
    current_date = current_time_cincy.date()
    current_time_only = current_time_cincy.time()
    
    # Check if any observation time is later today
    for obs_time in observation_times:
        if obs_time > current_time_only:
            # Next observation is today
            return CINCINNATI_TZ.localize(
                datetime.combine(current_date, obs_time)
            )
    
    # Next observation is tomorrow (first time)
    next_date = current_date + timedelta(days=1)
    first_obs_time = observation_times[0]
    return CINCINNATI_TZ.localize(
        datetime.combine(next_date, first_obs_time)
    )


def is_time_for_observation(current_time: datetime, observation_times: List[time], 
                            tolerance_minutes: int = 5) -> bool:
    """
    Check if it's time for a scheduled observation.
    
    Args:
        current_time: Current datetime (timezone-aware)
        observation_times: List of observation times
        tolerance_minutes: Minutes before/after scheduled time to trigger
        
    Returns:
        True if it's time for an observation
    """
    current_time_cincy = current_time.astimezone(CINCINNATI_TZ)
    current_time_only = current_time_cincy.time()
    current_minutes = current_time_only.hour * 60 + current_time_only.minute
    
    for obs_time in observation_times:
        obs_minutes = obs_time.hour * 60 + obs_time.minute
        
        # Calculate time difference in minutes
        time_diff = abs(current_minutes - obs_minutes)
        
        # Handle wrap-around (e.g., 23:55 to 00:05)
        if time_diff > 12 * 60:  # More than 12 hours difference
            time_diff = 24 * 60 - time_diff
        
        # Check if within tolerance window
        if time_diff <= tolerance_minutes:
            return True
    
    return False


def get_observation_schedule_summary(observation_times: List[time]) -> str:
    """
    Get a human-readable summary of the observation schedule.
    
    Args:
        observation_times: List of observation times
        
    Returns:
        Summary string
    """
    time_strings = [t.strftime('%I:%M %p') for t in observation_times]
    return f"Observations scheduled at: {', '.join(time_strings)}"

