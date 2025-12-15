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
    
    morning_start = time(7, 30)
    morning_end = time(9, 30)
    evening_start_weekday = time(16, 0)
    evening_start_weekend = time(18, 0)
    
    # If we know the last scheduled time, avoid scheduling multiple observations
    # in the same window (e.g., multiple morning runs in one day).
    if last_scheduled_time is not None:
        last_local = last_scheduled_time.astimezone(LOCATION_TZ)
        last_date = last_local.date()
        last_time_only = last_local.time()

        if last_date == current_date:
            # If we already had a morning observation today and we're still within
            # the morning window, skip scheduling another morning and move on to evening.
            if morning_start <= last_time_only <= morning_end and morning_start <= current_time_only <= morning_end:
                # Force logic to treat this as "after morning window"
                current_time_only = morning_end

            # If we already had an evening observation today, schedule the next
            # observation for tomorrow morning instead of another evening today.
            evening_end_weekday = time(18, 0)  # 6:00 PM
            evening_end_weekend = time(23, 59)  # 11:59 PM
            evening_end = evening_end_weekend if is_weekend else evening_end_weekday

            if is_weekend:
                evening_start = evening_start_weekend
            else:
                evening_start = evening_start_weekday

            if evening_start <= last_time_only <= evening_end:
                # Force logic to treat this as "after evening window"
                current_time_only = time(23, 59)
    
    # Check if we should schedule morning or evening
    if current_time_only < morning_end:
        # It's before 9:30 AM - could be early morning (before 7:30) or between 7:30-9:30
        # If it's very early (before 7:30), schedule morning for today
        # If it's between 7:30-9:30, check if we can still schedule morning for today
        if current_time_only < morning_start:
            # Very early morning (before 7:30 AM) - schedule morning for today
            morning_time = get_random_morning_time()
            next_dt = LOCATION_TZ.localize(datetime.combine(current_date, morning_time))
            return next_dt, "morning"
        
        # It's between 7:30-9:30 AM, try to schedule morning for today if possible
        # Get a random morning time, but ensure it's after current time
        morning_time = get_random_morning_time()
        # If the random time is before or equal to current time, pick a time between
        # current time and 9:30 AM
        if morning_time <= current_time_only:
            # Calculate minutes from midnight for current time and morning end
            current_minutes = current_time_only.hour * 60 + current_time_only.minute
            morning_end_minutes = 9 * 60 + 30  # 9:30 AM
            # Pick a random time between current time and 9:30 AM
            if current_minutes < morning_end_minutes:
                random_minutes = random.randint(current_minutes + 1, morning_end_minutes)
                morning_time = time(random_minutes // 60, random_minutes % 60)
            else:
                # Current time is at or after 9:30 (shouldn't happen in this branch, but safety check)
                next_date = current_date + timedelta(days=1)
                morning_time = get_random_morning_time()
                next_dt = LOCATION_TZ.localize(datetime.combine(next_date, morning_time))
                return next_dt, "morning"
        
        next_dt = LOCATION_TZ.localize(datetime.combine(current_date, morning_time))
        # SAFETY CHECK: Ensure the scheduled time is in the future
        if next_dt > current_time_local:
            return next_dt, "morning"
        
        # Fallback: schedule tomorrow morning (shouldn't happen, but safety check)
        next_date = current_date + timedelta(days=1)
        morning_time = get_random_morning_time()
        next_dt = LOCATION_TZ.localize(datetime.combine(next_date, morning_time))
        return next_dt, "morning"
    else:
        # It's past morning time (after 9:30 AM), schedule evening
        # BUT: if it's after midnight but before 9:30 AM, we should have been in the first branch
        # This else branch handles times after 9:30 AM
        
        # Special case: if it's very late at night (after evening window), schedule next morning
        # Evening window: weekdays 4:00 PM-6:00 PM, weekends 6:00 PM-11:59 PM
        evening_end_weekday = time(18, 0)  # 6:00 PM
        evening_end_weekend = time(23, 59)  # 11:59 PM
        evening_end = evening_end_weekend if is_weekend else evening_end_weekday
        
        # If current time is after the evening window, schedule next morning
        if current_time_only > evening_end:
            next_date = current_date + timedelta(days=1)
            morning_time = get_random_morning_time()
            next_dt = LOCATION_TZ.localize(datetime.combine(next_date, morning_time))
            return next_dt, "morning"
        
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
            # SAFETY CHECK: Ensure the scheduled time is in the future
            if next_dt > current_time_local:
                return next_dt, "evening"
        
        # Evening time has passed or would be in the past, schedule next day's morning
        next_date = current_date + timedelta(days=1)
        morning_time = get_random_morning_time()
        next_dt = LOCATION_TZ.localize(datetime.combine(next_date, morning_time))
        # FINAL SAFETY CHECK: This should always be in the future, but verify
        if next_dt <= current_time_local:
            # This should never happen, but if it does, add another day
            next_date = next_date + timedelta(days=1)
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
    
    # CRITICAL: Never trigger if scheduled time is in the past (beyond tolerance)
    # Only trigger if we're within tolerance_minutes AFTER the scheduled time
    if scheduled_time_local < current_time_local:
        # Scheduled time is in the past - check if we're still within tolerance window
        time_diff = (current_time_local - scheduled_time_local).total_seconds() / 60
        # Only trigger if we're within tolerance (e.g., scheduled for 2:00, it's 2:03, tolerance is 5)
        if time_diff <= tolerance_minutes:
            return True
        else:
            # Scheduled time is too far in the past - don't trigger
            return False
    
    # Scheduled time is in the future - check if we're within tolerance before it
    time_diff = (scheduled_time_local - current_time_local).total_seconds() / 60
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
