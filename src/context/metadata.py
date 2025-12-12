"""Generate context metadata (date/time, weather, etc.) for prompts."""
from datetime import datetime, timedelta
import pytz
from typing import Dict

from ..config import ROBOT_NAME

# Cincinnati timezone
CINCINNATI_TZ = pytz.timezone('America/New_York')


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


def get_context_metadata(weather_data: Dict = None) -> Dict:
    """
    Generate comprehensive context metadata.
    
    Args:
        weather_data: Optional weather data dictionary
        
    Returns:
        Dictionary with context metadata
    """
    # Get current time in Cincinnati timezone
    now = datetime.now(CINCINNATI_TZ)
    
    # Day of week names
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    
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
        
        # Timezone
        'timezone': 'EST' if now.astimezone(CINCINNATI_TZ).dst() == timedelta(0) else 'EDT',
        'timezone_name': 'America/New_York',
        
        # Robot info
        'robot_name': ROBOT_NAME,
        
        # Weather (if provided)
        'weather': weather_data or {}
    }
    
    return metadata


def format_context_for_prompt(metadata: Dict) -> str:
    """
    Format context metadata as a readable string for prompts.
    
    Args:
        metadata: Context metadata dictionary
        
    Returns:
        Formatted context string
    """
    parts = []
    
    # Date/Time
    parts.append(f"Today is {metadata['day_of_week']}, {metadata['date']} at {metadata['time']} {metadata['timezone']}")
    
    # Season
    parts.append(f"It is {metadata['season']} ({metadata['time_of_day']})")
    
    # Weekend/Weekday
    if metadata['is_weekend']:
        parts.append("It is a weekend")
    else:
        parts.append("It is a weekday")
    
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

