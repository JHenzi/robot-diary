"""Randomized scheduler for time-based observations."""
from datetime import datetime, time, timedelta
import random
import pytz
from typing import Optional, Tuple

# Location timezone (from config)
from .config import LOCATION_TIMEZONE
LOCATION_TZ = pytz.timezone(LOCATION_TIMEZONE)


def get_random_morning_time() -> time:
    """
    Get a random time between 7:30 AM and 9:30 AM.
    
    Returns:
        Random time object
    """
    # Random minutes between 7:30 (450 minutes) and 9:30 (570 minutes)
    total_minutes = random.randint(450, 570)
    hour = total_minutes // 60
    minute = total_minutes % 60
    return time(hour, minute)


def get_random_evening_time(is_weekend: bool) -> Tuple[time, bool]:
    """
    Get a random evening time based on weekday/weekend.
    
    Weekdays: 4:00 PM - 6:00 PM (16:00 - 18:00)
    Weekends: 6:00 PM - 11:59 PM (18:00 - 23:59)
    
    Args:
        is_weekend: True if it's a weekend
        
    Returns:
        Tuple of (time object, is_next_day)
        is_next_day is always False now (evening times stay on same day)
    """
    if is_weekend:
        # Weekend: 6:00 PM (18:00) to 11:59 PM (23:59) - keep evening times on same day
        # For late night (midnight-1:00 AM), we'll handle that separately if needed
        total_minutes = random.randint(1080, 1439)  # 18:00 to 23:59
        hour = total_minutes // 60
        minute = total_minutes % 60
        return time(hour, minute), False
    else:
        # Weekday: 4:00 PM - 6:00 PM (16:00 - 18:00)
        total_minutes = random.randint(960, 1080)  # 16:00 to 18:00
        hour = total_minutes // 60
        minute = total_minutes % 60
        return time(hour, minute), False


def get_next_observation_time(current_time: datetime, 
                             last_scheduled_time: Optional[datetime] = None) -> Tuple[datetime, str]:
    """
    Get the next randomized observation time.
    
    Args:
        current_time: Current datetime (timezone-aware)
        last_scheduled_time: The last scheduled observation time (to avoid repeats)
        
    Returns:
        Tuple of (next_observation_datetime, observation_type)
        observation_type is either "morning" or "evening"
    """
    current_time_local = current_time.astimezone(LOCATION_TZ)
    current_date = current_time_local.date()
    current_time_only = current_time_local.time()
    current_weekday = current_time_local.weekday()
    is_weekend = current_weekday >= 5
    
    # Determine if we need morning or evening observation
    # Morning is 7:30-9:30, so if it's before 9:30, we might need morning
    # If it's after 9:30, we definitely need evening (or next day's morning)
    
    morning_end = time(9, 30)
    evening_start_weekday = time(16, 0)
    evening_start_weekend = time(18, 0)
    
    # Check if we should schedule morning or evening
    if current_time_only < morning_end:
        # It's still morning time, schedule morning observation for today
        morning_time = get_random_morning_time()
        # Make sure it's after current time
        if morning_time > current_time_only:
            next_dt = LOCATION_TZ.localize(datetime.combine(current_date, morning_time))
            return next_dt, "morning"
        else:
            # Morning time has passed, schedule evening
            if is_weekend:
                evening_time, is_next_day = get_random_evening_time(True)
            else:
                evening_time, is_next_day = get_random_evening_time(False)
            
            # Check if evening time is next day (weekend late night)
            if is_next_day:
                next_date = current_date + timedelta(days=1)
                next_dt = LOCATION_TZ.localize(datetime.combine(next_date, evening_time))
            else:
                next_dt = LOCATION_TZ.localize(datetime.combine(current_date, evening_time))
            
            return next_dt, "evening"
    else:
        # It's past morning time, schedule evening
        if is_weekend:
            evening_time, is_next_day = get_random_evening_time(True)
        else:
            evening_time, is_next_day = get_random_evening_time(False)
        
        # Check if we can schedule for today or need tomorrow
        if is_next_day:
            # Weekend late night - schedule for next day
            next_date = current_date + timedelta(days=1)
            next_dt = LOCATION_TZ.localize(datetime.combine(next_date, evening_time))
            return next_dt, "evening"
        elif evening_time > current_time_only:
            # Evening time is later today - can schedule for today
            next_dt = LOCATION_TZ.localize(datetime.combine(current_date, evening_time))
            return next_dt, "evening"
        else:
            # Evening time has passed, schedule next day's morning
            next_date = current_date + timedelta(days=1)
            morning_time = get_random_morning_time()
            next_dt = LOCATION_TZ.localize(datetime.combine(next_date, morning_time))
            return next_dt, "morning"


def is_time_for_observation(current_time: datetime, 
                            scheduled_time: datetime,
                            tolerance_minutes: int = 5) -> bool:
    """
    Check if it's time for a scheduled observation.
    
    Args:
        current_time: Current datetime (timezone-aware)
        scheduled_time: Scheduled observation datetime
        tolerance_minutes: Minutes before/after scheduled time to trigger
        
    Returns:
        True if it's time for an observation
    """
    if scheduled_time is None:
        return False
    
    current_time_local = current_time.astimezone(LOCATION_TZ)
    scheduled_time_local = scheduled_time.astimezone(LOCATION_TZ)
    
    time_diff = abs((current_time_local - scheduled_time_local).total_seconds() / 60)
    
    return time_diff <= tolerance_minutes


def get_observation_schedule_summary(next_time: datetime, obs_type: str) -> str:
    """
    Get a human-readable summary of the next observation.
    
    Args:
        next_time: Next observation datetime
        obs_type: Type of observation ("morning" or "evening")
        
    Returns:
        Summary string
    """
    next_time_local = next_time.astimezone(LOCATION_TZ)
    time_str = next_time_local.strftime('%I:%M %p on %A, %B %d')
    return f"Next {obs_type} observation scheduled for {time_str}"
