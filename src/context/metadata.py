"""Generate context metadata (date/time, weather, etc.) for prompts."""
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Optional
import logging

from ..config import ROBOT_NAME, LOCATION_LATITUDE, LOCATION_LONGITUDE, LOCATION_CITY, LOCATION_STATE

# New Orleans, Louisiana timezone (Central Time)
from ..config import LOCATION_TIMEZONE
LOCATION_TZ = pytz.timezone(LOCATION_TIMEZONE)

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    from astral import LocationInfo
    from astral.sun import sun
    from astral import moon
    ASTRAL_AVAILABLE = True
except ImportError:
    ASTRAL_AVAILABLE = False
    logger.warning("astral library not available - sunrise/sunset and moon phase calculations will be skipped")

try:
    import holidays
    HOLIDAYS_AVAILABLE = True
except ImportError:
    HOLIDAYS_AVAILABLE = False
    logger.warning("holidays library not available - holiday detection will be skipped")


def get_season(month: int) -> str:
    """Get season name from month."""
    if month in [12, 1, 2]:
        return "Winter"
    elif month in [3, 4, 5]:
        return "Spring"
    elif month in [6, 7, 8]:
        return "Summer"
    else:
        return "Fall"


def get_ordinal_suffix(day: int) -> str:
    """Get ordinal suffix for day (1st, 2nd, 3rd, 4th, etc.)."""
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return suffix


def format_date_for_title(metadata: Dict) -> str:
    """
    Format date for post title: "Thursday December 11th 2025, Morning Update"
    
    Args:
        metadata: Context metadata dictionary
        
    Returns:
        Formatted date string
    """
    day_suffix = get_ordinal_suffix(metadata['day'])
    time_of_day_capitalized = metadata['time_of_day'].capitalize()
    
    return f"{metadata['day_of_week']} {metadata['month']} {metadata['day']}{day_suffix} {metadata['year']}, {time_of_day_capitalized} Update"


def get_time_of_day(hour: int) -> str:
    """Get time of day description."""
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "night"


def get_moon_phase(date: datetime) -> Optional[Dict]:
    """
    Calculate moon phase and detect special events (full moon, new moon, supermoon, blue moon).
    
    Args:
        date: Date to calculate moon phase for
        
    Returns:
        Dictionary with moon phase info, or None if calculation fails
    """
    if not ASTRAL_AVAILABLE:
        return None
    
    try:
        # Calculate moon phase (0.0 = new moon, 0.5 = full moon)
        phase_value = moon.phase(date)
        
        # Determine phase name
        if phase_value < 0.03 or phase_value > 0.97:
            phase_name = "new moon"
            is_key_event = True
        elif 0.47 <= phase_value <= 0.53:
            phase_name = "full moon"
            is_key_event = True
        elif phase_value < 0.22:
            phase_name = "waxing crescent"
            is_key_event = False
        elif phase_value < 0.28:
            phase_name = "first quarter"
            is_key_event = False
        elif phase_value < 0.47:
            phase_name = "waxing gibbous"
            is_key_event = False
        elif phase_value < 0.72:
            phase_name = "waning gibbous"
            is_key_event = False
        elif phase_value < 0.78:
            phase_name = "last quarter"
            is_key_event = False
        else:
            phase_name = "waning crescent"
            is_key_event = False
        
        # Calculate days until next full/new moon
        days_to_full = None
        days_to_new = None
        
        # Find next full moon (phase = 0.5)
        test_date = date
        for _ in range(30):  # Search up to 30 days ahead
            test_date += timedelta(days=1)
            test_phase = moon.phase(test_date)
            if 0.47 <= test_phase <= 0.53:
                days_to_full = (test_date - date).days
                break
        
        # Find next new moon (phase = 0.0 or 1.0)
        test_date = date
        for _ in range(30):
            test_date += timedelta(days=1)
            test_phase = moon.phase(test_date)
            if test_phase < 0.03 or test_phase > 0.97:
                days_to_new = (test_date - date).days
                break
        
        # Detect special events
        moon_event = None
        if phase_name == "full moon":
            # Check for blue moon (second full moon in calendar month)
            # This is approximate - would need to check all full moons in month
            # For now, we'll just note if it's a full moon
            moon_event = "full moon"
        elif phase_name == "new moon":
            moon_event = "new moon"
        
        return {
            'phase_name': phase_name,
            'phase_value': phase_value,
            'is_key_event': is_key_event,
            'days_to_full_moon': days_to_full,
            'days_to_new_moon': days_to_new,
            'moon_event': moon_event
        }
    except Exception as e:
        logger.warning(f"Error calculating moon phase: {e}")
        return None


def get_holidays(date: datetime) -> List[str]:
    """
    Detect US holidays (federal + cultural/religious) for the given date.
    
    Args:
        date: Date to check for holidays
        
    Returns:
        List of holiday names, empty list if none or if library unavailable
    """
    if not HOLIDAYS_AVAILABLE:
        return []
    
    try:
        # Get US holidays (includes federal holidays)
        us_holidays = holidays.UnitedStates(years=date.year)
        
        # Also get state holidays for Louisiana (includes Mardi Gras, etc.)
        la_holidays = holidays.US(subdiv='LA', years=date.year)
        
        # Combine and get unique holidays for this date
        # Holidays library uses date objects as keys, not strings
        date_obj = date.date()
        holiday_list = []
        
        if date_obj in us_holidays:
            holiday_list.append(us_holidays[date_obj])
        if date_obj in la_holidays and la_holidays[date_obj] not in holiday_list:
            holiday_list.append(la_holidays[date_obj])
        
        return holiday_list
    except Exception as e:
        logger.warning(f"Error detecting holidays: {e}")
        return []


def get_upcoming_holidays(date: datetime, days_ahead: int = 30) -> List[Dict]:
    """
    Detect upcoming US holidays within the next N days.
    
    Args:
        date: Current date
        days_ahead: Number of days to look ahead (default: 30)
        
    Returns:
        List of dicts with 'name' and 'days_until' keys, empty list if none or if library unavailable
    """
    if not HOLIDAYS_AVAILABLE:
        return []
    
    try:
        # Get US holidays for current year and next year (in case we're near year end)
        us_holidays = holidays.UnitedStates(years=[date.year, date.year + 1])
        la_holidays = holidays.US(subdiv='LA', years=[date.year, date.year + 1])
        
        # Combine both holiday dicts
        all_holidays = {}
        all_holidays.update(us_holidays)
        all_holidays.update(la_holidays)
        
        upcoming = []
        date_only = date.date()
        holidays_found_in_dict = 0
        
        # Check each day in the range
        for i in range(1, days_ahead + 1):
            check_date = date_only + timedelta(days=i)
            check_date_str = check_date.strftime('%Y-%m-%d')
            
            # Holidays library uses date objects as keys, not strings
            if check_date in all_holidays:
                holidays_found_in_dict += 1
                holiday_name = all_holidays[check_date]
                # Filter out minor holidays, focus on major ones
                major_holidays = [
                    'Christmas', 'New Year', 'Thanksgiving', 'Independence Day',
                    'Memorial Day', 'Labor Day', 'Veterans Day', 'Presidents Day',
                    'Martin Luther King', 'Easter', 'Halloween', 'Valentine',
                    'Mardi Gras', 'New Year\'s Day', 'Christmas Day', 'New Year\'s Eve'
                ]
                
                # Include if it's a major holiday or contains major holiday keywords (case-insensitive)
                holiday_lower = holiday_name.lower()
                matches = [m for m in major_holidays if m.lower() in holiday_lower]
                
                if matches:
                    upcoming.append({
                        'name': holiday_name,
                        'days_until': i,
                        'date': check_date_str
                    })
                    logger.info(f"🎄 Found upcoming holiday: {holiday_name} in {i} days ({check_date_str})")
                else:
                    # Log holidays we're filtering out for debugging
                    logger.debug(f"Filtered out minor holiday: {holiday_name} on {check_date_str}")
        
        # Sort by days until
        upcoming.sort(key=lambda x: x['days_until'])
        
        # Debug: log if no holidays found
        if not upcoming and holidays_found_in_dict > 0:
            logger.warning(f"Found {holidays_found_in_dict} holiday(s) in date range but all were filtered out as minor holidays")
        elif not upcoming:
            # Check a few specific dates to see what's happening
            sample_dates = [(date_only + timedelta(days=i)).strftime('%Y-%m-%d') for i in [1, 11, 25] if i <= days_ahead]
            logger.debug(f"No upcoming holidays found. Checked {days_ahead} days from {date_only}. Sample dates: {sample_dates}")
            # Check if Christmas is actually in the dict
            xmas_date = (date_only + timedelta(days=11)).strftime('%Y-%m-%d') if 11 <= days_ahead else None
            if xmas_date and xmas_date in all_holidays:
                xmas_name = all_holidays[xmas_date]
                logger.debug(f"DEBUG: Found {xmas_name} on {xmas_date} in all_holidays dict, but wasn't added to upcoming list")
                # Check why it wasn't added
                holiday_lower = xmas_name.lower()
                matches = [m for m in ['Christmas', 'New Year', 'Thanksgiving', 'Independence Day', 'Memorial Day', 'Labor Day', 'Veterans Day', 'Presidents Day', 'Martin Luther King', 'Easter', 'Halloween', 'Valentine', 'Mardi Gras', 'New Year\'s Day', 'Christmas Day', 'New Year\'s Eve'] if m.lower() in holiday_lower]
                logger.debug(f"DEBUG: Filter check for '{xmas_name}': would match {matches}")
        
        return upcoming
    except Exception as e:
        logger.warning(f"Error detecting upcoming holidays: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return []


def get_sunrise_sunset(date: datetime) -> Optional[Dict]:
    """
    Calculate sunrise and sunset times for New Orleans.
    
    Args:
        date: Date to calculate for
        
    Returns:
        Dictionary with sunrise/sunset info, or None if calculation fails
    """
    if not ASTRAL_AVAILABLE:
        return None
    
    try:
        # Create location for New Orleans
        location = LocationInfo(
            name=LOCATION_CITY,
            region=LOCATION_STATE,
            timezone=LOCATION_TIMEZONE,
            latitude=LOCATION_LATITUDE,
            longitude=LOCATION_LONGITUDE
        )
        
        # Calculate sun times
        s = sun(location.observer, date=date.date(), tzinfo=LOCATION_TZ)
        
        sunrise = s['sunrise']
        sunset = s['sunset']
        
        # Calculate time since/until sunrise/sunset
        current_time = date
        hours_since_sunrise = None
        hours_until_sunset = None
        hours_since_sunset = None
        is_daytime = None
        
        if current_time >= sunrise and current_time < sunset:
            is_daytime = True
            hours_since_sunrise = (current_time - sunrise).total_seconds() / 3600
            hours_until_sunset = (sunset - current_time).total_seconds() / 3600
            hours_since_sunset = None
        elif current_time < sunrise:
            is_daytime = False
            hours_until_sunset = None
            hours_since_sunrise = None
            # Before sunrise - could calculate hours since yesterday's sunset, but skip for simplicity
            hours_since_sunset = None
        else:  # current_time >= sunset
            is_daytime = False
            hours_since_sunrise = (current_time - sunrise).total_seconds() / 3600
            hours_until_sunset = None
            hours_since_sunset = (current_time - sunset).total_seconds() / 3600
        
        return {
            'sunrise_time': sunrise.strftime('%I:%M %p'),
            'sunset_time': sunset.strftime('%I:%M %p'),
            'sunrise': sunrise,
            'sunset': sunset,
            'hours_since_sunrise': hours_since_sunrise,
            'hours_until_sunset': hours_until_sunset,
            'hours_since_sunset': hours_since_sunset,
            'is_daytime': is_daytime
        }
    except Exception as e:
        logger.warning(f"Error calculating sunrise/sunset: {e}")
        return None


def get_seasonal_progress(date: datetime) -> Dict:
    """
    Calculate day of year and progress through current season.
    
    Args:
        date: Date to calculate for
        
    Returns:
        Dictionary with seasonal progress info
    """
    # Day of year (1-365/366)
    day_of_year = date.timetuple().tm_yday
    
    # Determine season and calculate progress
    season = get_season(date.month)
    
    # Define season boundaries (approximate)
    season_days = {
        'Winter': (12, 1, 2),  # Dec, Jan, Feb
        'Spring': (3, 4, 5),   # Mar, Apr, May
        'Summer': (6, 7, 8),    # Jun, Jul, Aug
        'Fall': (9, 10, 11)     # Sep, Oct, Nov
    }
    
    # Calculate days in current season
    season_months = season_days[season]
    days_in_season = 0
    for month in season_months:
        if month == 2:
            # February - check for leap year
            if date.year % 4 == 0 and (date.year % 100 != 0 or date.year % 400 == 0):
                days_in_season += 29
            else:
                days_in_season += 28
        elif month in [4, 6, 9, 11]:
            days_in_season += 30
        else:
            days_in_season += 31
    
    # Calculate which day of season we're on
    if season == 'Winter':
        if date.month == 12:
            day_of_season = date.day
        elif date.month == 1:
            # Days in Dec + days in Jan so far
            dec_days = 31
            day_of_season = dec_days + date.day
        else:  # February
            dec_days = 31
            jan_days = 31
            day_of_season = dec_days + jan_days + date.day
    elif season == 'Spring':
        if date.month == 3:
            day_of_season = date.day
        elif date.month == 4:
            mar_days = 31
            day_of_season = mar_days + date.day
        else:  # May
            mar_days = 31
            apr_days = 30
            day_of_season = mar_days + apr_days + date.day
    elif season == 'Summer':
        if date.month == 6:
            day_of_season = date.day
        elif date.month == 7:
            jun_days = 30
            day_of_season = jun_days + date.day
        else:  # August
            jun_days = 30
            jul_days = 31
            day_of_season = jun_days + jul_days + date.day
    else:  # Fall
        if date.month == 9:
            day_of_season = date.day
        elif date.month == 10:
            sep_days = 30
            day_of_season = sep_days + date.day
        else:  # November
            sep_days = 30
            oct_days = 31
            day_of_season = sep_days + oct_days + date.day
    
    # Determine progress (early/mid/late - thirds)
    progress_ratio = day_of_season / days_in_season
    if progress_ratio < 0.33:
        season_progress = "early"
    elif progress_ratio < 0.67:
        season_progress = "middle"
    else:
        season_progress = "late"
    
    # Calculate days until next season
    next_season_months = {
        'Winter': (3, 4, 5),   # Spring
        'Spring': (6, 7, 8),   # Summer
        'Summer': (9, 10, 11), # Fall
        'Fall': (12, 1, 2)     # Winter
    }
    
    # Find first day of next season
    if season == 'Winter':
        next_season_start = datetime(date.year, 3, 1, tzinfo=LOCATION_TZ)
    elif season == 'Spring':
        next_season_start = datetime(date.year, 6, 1, tzinfo=LOCATION_TZ)
    elif season == 'Summer':
        next_season_start = datetime(date.year, 9, 1, tzinfo=LOCATION_TZ)
    else:  # Fall
        next_season_start = datetime(date.year, 12, 1, tzinfo=LOCATION_TZ)
    
    if date >= next_season_start:
        # Next season is next year
        if season == 'Fall':
            next_season_start = datetime(date.year + 1, 3, 1, tzinfo=LOCATION_TZ)
        else:
            next_season_start = datetime(date.year + 1, next_season_start.month, 1, tzinfo=LOCATION_TZ)
    
    days_until_next_season = (next_season_start.date() - date.date()).days
    
    return {
        'day_of_year': day_of_year,
        'season_progress': season_progress,
        'days_until_next_season': days_until_next_season,
        'day_of_season': day_of_season,
        'days_in_season': days_in_season
    }


def get_astronomical_events(date: datetime) -> Dict:
    """
    Detect astronomical events (solstices, equinoxes).
    
    Args:
        date: Date to check
        
    Returns:
        Dictionary with astronomical event info
    """
    year = date.year
    
    # Approximate dates for solstices and equinoxes
    # Spring equinox: ~March 20
    # Summer solstice: ~June 21
    # Fall equinox: ~September 22
    # Winter solstice: ~December 21
    
    spring_equinox = datetime(year, 3, 20, tzinfo=LOCATION_TZ)
    summer_solstice = datetime(year, 6, 21, tzinfo=LOCATION_TZ)
    fall_equinox = datetime(year, 9, 22, tzinfo=LOCATION_TZ)
    winter_solstice = datetime(year, 12, 21, tzinfo=LOCATION_TZ)
    
    # Check if today is one of these events (within 1 day)
    is_equinox = False
    is_solstice = False
    event_name = None
    
    date_only = date.date()
    
    if abs((spring_equinox.date() - date_only).days) <= 1:
        is_equinox = True
        event_name = "spring equinox"
    elif abs((summer_solstice.date() - date_only).days) <= 1:
        is_solstice = True
        event_name = "summer solstice"
    elif abs((fall_equinox.date() - date_only).days) <= 1:
        is_equinox = True
        event_name = "fall equinox"
    elif abs((winter_solstice.date() - date_only).days) <= 1:
        is_solstice = True
        event_name = "winter solstice"
    
    # Calculate days since/until next event
    events = [
        (spring_equinox, "spring equinox"),
        (summer_solstice, "summer solstice"),
        (fall_equinox, "fall equinox"),
        (winter_solstice, "winter solstice")
    ]
    
    # Sort events and find next one
    future_events = [(e, n) for e, n in events if e.date() >= date_only]
    if future_events:
        next_event_date, next_event_name = min(future_events, key=lambda x: x[0])
        days_until_next = (next_event_date.date() - date_only).days
    else:
        # Next event is next year
        next_year_spring = datetime(year + 1, 3, 20, tzinfo=LOCATION_TZ)
        next_event_name = "spring equinox"
        days_until_next = (next_year_spring.date() - date_only).days
    
    return {
        'is_equinox': is_equinox,
        'is_solstice': is_solstice,
        'event_name': event_name,
        'days_until_next_event': days_until_next,
        'next_event_name': next_event_name
    }


def get_context_metadata(weather_data: Dict = None, observation_type: str = None) -> Dict:
    """
    Generate comprehensive context metadata.
    
    Args:
        weather_data: Optional weather data dictionary
        observation_type: Type of observation ('morning' or 'evening')
        
    Returns:
        Dictionary with context metadata
    """
    # Get current time in location timezone
    now = datetime.now(LOCATION_TZ)
    
    # Day of week names
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    
    # Determine observation type if not provided
    if observation_type is None:
        time_of_day_str = get_time_of_day(now.hour)
        if time_of_day_str == "morning":
            observation_type = "morning"
        else:
            observation_type = "evening"
    
    metadata = {
        # Date/Time
        'date': now.strftime('%B %d, %Y'),  # "December 11, 2025"
        'date_iso': now.strftime('%Y-%m-%d'),  # "2025-12-11"
        'time': now.strftime('%I:%M %p'),  # "10:51 PM"
        'time_24h': now.strftime('%H:%M'),  # "22:51"
        'day_of_week': day_names[now.weekday()],  # "Wednesday"
        'month': month_names[now.month - 1],  # "December"
        'month_num': now.month,  # 12
        'day': now.day,  # 11
        'year': now.year,  # 2025
        'hour': now.hour,  # 22
        'minute': now.minute,  # 51
        
        # Temporal context
        'season': get_season(now.month),  # "Winter"
        'time_of_day': get_time_of_day(now.hour),  # "evening"
        'is_weekend': now.weekday() >= 5,  # True/False
        'is_weekday': now.weekday() < 5,  # True/False
        'observation_type': observation_type,  # "morning" or "evening"
        
        # Timezone
        'timezone': 'CST' if now.astimezone(LOCATION_TZ).dst() == timedelta(0) else 'CDT',
        'timezone_name': LOCATION_TIMEZONE,
        
        # Robot info
        'robot_name': ROBOT_NAME,
        
        # Weather (if provided)
        'weather': weather_data or {}
    }
    
    # Add moon phase (if available)
    moon_info = get_moon_phase(now)
    if moon_info:
        metadata['moon'] = moon_info
    
    # Add holidays (if available)
    holidays_list = get_holidays(now)
    if holidays_list:
        metadata['holidays'] = holidays_list
        metadata['is_holiday'] = True
    else:
        metadata['is_holiday'] = False
    
    # Add upcoming holidays (if available)
    if not HOLIDAYS_AVAILABLE:
        logger.warning("⚠️  Holidays library not available - upcoming holiday detection disabled")
    else:
        upcoming_holidays = get_upcoming_holidays(now, days_ahead=30)
        if upcoming_holidays:
            metadata['upcoming_holidays'] = upcoming_holidays
            logger.info(f"🎄 Found {len(upcoming_holidays)} upcoming holiday(s): {[h['name'] for h in upcoming_holidays]}")
        else:
            logger.warning(f"⚠️  No upcoming holidays found for date {now.date()} (checked next 30 days)")
    
    # Add sunrise/sunset (if available)
    sun_info = get_sunrise_sunset(now)
    if sun_info:
        metadata['sun'] = sun_info
    
    # Add seasonal progress
    seasonal_info = get_seasonal_progress(now)
    metadata.update(seasonal_info)
    
    # Add astronomical events
    astro_info = get_astronomical_events(now)
    metadata.update(astro_info)
    
    return metadata


def format_context_for_prompt(metadata: Dict) -> str:
    """
    Format context metadata as a readable string for prompts.
    Intelligently includes relevant context (holidays, moon events, etc.).
    
    Args:
        metadata: Context metadata dictionary
        
    Returns:
        Formatted context string
    """
    parts = []
    
    # Date/Time
    parts.append(f"Today is {metadata['day_of_week']}, {metadata['date']} at {metadata['time']} {metadata['timezone']}")
    
    # Holidays (high priority - include if present)
    if metadata.get('is_holiday') and metadata.get('holidays'):
        holiday_names = ", ".join(metadata['holidays'])
        parts.append(f"Today is {holiday_names}")
    
    # Upcoming holidays (high priority - include if within 30 days)
    upcoming = metadata.get('upcoming_holidays', [])
    if upcoming:
        # Show the nearest major holiday
        nearest = upcoming[0]
        days = nearest['days_until']
        name = nearest['name']
        if days == 1:
            parts.append(f"Tomorrow is {name}")
        elif days <= 7:
            parts.append(f"{name} is in {days} days")
        elif days <= 14:
            parts.append(f"{name} is in {days} days (less than 2 weeks away)")
        else:
            weeks = days // 7
            parts.append(f"{name} is in {days} days (about {weeks} weeks away)")
    
    # Season
    parts.append(f"It is {metadata['season']} ({metadata['time_of_day']})")
    
    # Moon phase - only include key events (full/new moon) or if it's a special event
    moon = metadata.get('moon')
    if moon and moon.get('is_key_event'):
        moon_event = moon.get('moon_event')
        if moon_event:
            parts.append(f"A {moon_event} is visible")
        else:
            parts.append(f"The moon is in {moon.get('phase_name')} phase")
    
    # Astronomical events (solstices, equinoxes)
    if metadata.get('is_equinox') or metadata.get('is_solstice'):
        event_name = metadata.get('event_name')
        if event_name:
            parts.append(f"Today is the {event_name}")
    
    # Sunrise/Sunset context (if available and relevant)
    sun = metadata.get('sun')
    if sun:
        if sun.get('is_daytime'):
            hours_since = sun.get('hours_since_sunrise')
            if hours_since is not None and hours_since < 2:
                parts.append("The sun rose recently")
            elif hours_since is not None and hours_since > 10:
                parts.append("The sun has been up for many hours")
        else:
            # It's nighttime - check hours since sunset
            hours_since_sunset = sun.get('hours_since_sunset')
            if hours_since_sunset is not None:
                if hours_since_sunset < 2:
                    parts.append("The sun set recently")
                elif hours_since_sunset < 6:
                    parts.append(f"The sun set {int(hours_since_sunset)} hours ago")
    
    # Seasonal progress (if in middle or late season)
    season_progress = metadata.get('season_progress')
    days_until_next = metadata.get('days_until_next_season')
    if season_progress in ['middle', 'late'] and days_until_next is not None:
        if days_until_next < 30:
            weeks = days_until_next // 7
            if weeks > 0:
                parts.append(f"We're in the {season_progress} of {metadata['season']}, with the next season {weeks} weeks away")
            else:
                parts.append(f"We're in the {season_progress} of {metadata['season']}, with the next season {days_until_next} days away")
    
    # Weekend/Weekday
    if metadata['is_weekend']:
        parts.append("It is a weekend")
    else:
        parts.append("It is a weekday")
    
    # Observation type context
    obs_type = metadata.get('observation_type', 'evening')
    if obs_type == 'morning':
        parts.append("This is a morning observation - the robot is performing its scheduled health scan and looking out the window, excited to see people starting their day")
    else:
        parts.append("This is an evening observation - the robot is reflecting on what people have been doing throughout the day or what they are doing this night")
    
    return ". ".join(parts) + "."


def format_weather_for_prompt(weather_data: Dict) -> str:
    """
    Format weather data for prompt inclusion.
    
    Args:
        weather_data: Weather data dictionary
        
    Returns:
        Formatted weather string
    """
    if not weather_data:
        return "Weather data is currently unavailable."
    
    parts = []
    
    # Main conditions
    summary = weather_data.get('summary', '')
    temp = weather_data.get('temperature')
    
    if summary and temp:
        parts.append(f"The weather is {summary.lower()} with a temperature of {temp}°F")
    elif temp:
        parts.append(f"The temperature is {temp}°F")
    
    # Wind (especially if windy)
    wind_speed = weather_data.get('wind_speed', 0)
    if wind_speed > 15:
        wind_gust = weather_data.get('wind_gust')
        if wind_gust:
            parts.append(f"it's very windy with speeds of {wind_speed} mph and gusts up to {wind_gust} mph")
        else:
            parts.append(f"it's windy with speeds of {wind_speed} mph")
    elif wind_speed > 10:
        parts.append(f"there's a moderate breeze at {wind_speed} mph")
    
    # Precipitation
    precip_prob = weather_data.get('precip_probability', 0)
    if precip_prob > 0.3:
        precip_type = weather_data.get('precip_type', 'precipitation')
        parts.append(f"there's a {precip_prob * 100:.0f}% chance of {precip_type}")
    
    return ". ".join(parts) + "." if parts else "Weather conditions are normal."

