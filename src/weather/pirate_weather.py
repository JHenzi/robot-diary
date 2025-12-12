"""Pirate Weather API client for fetching weather data."""
import requests
import json
from pathlib import Path
from datetime import datetime, timedelta
import logging

from ..config import PROJECT_ROOT

logger = logging.getLogger(__name__)

# Cincinnati coordinates
CINCINNATI_LAT = 39.1031
CINCINNATI_LON = -84.5120

# Cache file
WEATHER_CACHE_FILE = PROJECT_ROOT / 'weather' / '.weather_cache.json'
WEATHER_CACHE_TTL_MINUTES = 30


class PirateWeatherClient:
    """Client for Pirate Weather API."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.pirateweather.net"
        WEATHER_CACHE_FILE.parent.mkdir(exist_ok=True)
    
    def _load_cache(self) -> dict | None:
        """Load cached weather data."""
        if not WEATHER_CACHE_FILE.exists():
            return None
        
        try:
            with open(WEATHER_CACHE_FILE, 'r') as f:
                cache = json.load(f)
            
            # Check if cache is still valid
            cached_time = datetime.fromisoformat(cache.get('cached_at', ''))
            age = datetime.now() - cached_time
            
            if age < timedelta(minutes=WEATHER_CACHE_TTL_MINUTES):
                logger.info(f"Using cached weather data (age: {age})")
                return cache.get('data')
            else:
                logger.info(f"Cache expired (age: {age})")
                return None
                
        except Exception as e:
            logger.warning(f"Error loading weather cache: {e}")
            return None
    
    def _save_cache(self, data: dict):
        """Save weather data to cache."""
        try:
            cache = {
                'cached_at': datetime.now().isoformat(),
                'data': data
            }
            with open(WEATHER_CACHE_FILE, 'w') as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving weather cache: {e}")
    
    def get_current_weather(self, use_cache: bool = True) -> dict:
        """
        Get current weather for Cincinnati.
        
        Args:
            use_cache: If True, use cached data if available and fresh
            
        Returns:
            Dictionary with current weather data
        """
        # Check cache first
        if use_cache:
            cached = self._load_cache()
            if cached:
                return cached
        
        # Fetch from API
        logger.info("Fetching current weather from Pirate Weather API...")
        
        url = f"{self.base_url}/forecast/{self.api_key}/{CINCINNATI_LAT},{CINCINNATI_LON}"
        params = {
            'units': 'us',  # US units (Fahrenheit, mph, etc.)
            'exclude': 'minutely,hourly,daily,alerts,flags'  # Only get current conditions
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract current conditions
            currently = data.get('currently', {})
            
            # Format weather data for prompt
            weather_data = {
                'temperature': currently.get('temperature'),
                'apparent_temperature': currently.get('apparentTemperature'),
                'summary': currently.get('summary', 'Unknown'),
                'icon': currently.get('icon', 'unknown'),
                'wind_speed': currently.get('windSpeed', 0),
                'wind_gust': currently.get('windGust'),
                'wind_bearing': currently.get('windBearing'),
                'humidity': currently.get('humidity', 0),
                'pressure': currently.get('pressure'),
                'cloud_cover': currently.get('cloudCover', 0),
                'visibility': currently.get('visibility', 10),
                'uv_index': currently.get('uvIndex', 0),
                'dew_point': currently.get('dewPoint'),
                'precip_intensity': currently.get('precipIntensity', 0),
                'precip_probability': currently.get('precipProbability', 0),
                'precip_type': currently.get('precipType'),
                'timezone': data.get('timezone', 'America/New_York'),
                'fetched_at': datetime.now().isoformat()
            }
            
            # Cache the data
            self._save_cache(weather_data)
            
            logger.info(f"✅ Weather fetched: {weather_data['summary']}, {weather_data['temperature']}°F")
            return weather_data
            
        except requests.RequestException as e:
            logger.error(f"Error fetching weather: {e}")
            # Return cached data even if expired, or empty dict
            cached = self._load_cache()
            if cached:
                logger.warning("Using expired cache due to API error")
                return cached
            return {}
    
    def format_weather_for_prompt(self, weather_data: dict) -> str:
        """
        Format weather data as a readable string for prompts.
        
        Args:
            weather_data: Weather data dictionary
            
        Returns:
            Formatted weather string
        """
        if not weather_data:
            return "Weather data unavailable."
        
        parts = []
        
        # Temperature
        temp = weather_data.get('temperature')
        feels_like = weather_data.get('apparent_temperature')
        if temp:
            if feels_like and abs(temp - feels_like) > 2:
                parts.append(f"{temp}°F (feels like {feels_like}°F)")
            else:
                parts.append(f"{temp}°F")
        
        # Summary/conditions
        summary = weather_data.get('summary', '')
        if summary:
            parts.append(summary)
        
        # Wind
        wind_speed = weather_data.get('wind_speed', 0)
        wind_gust = weather_data.get('wind_gust')
        if wind_speed:
            wind_desc = f"{wind_speed} mph"
            if wind_gust and wind_gust > wind_speed * 1.5:
                wind_desc += f" (gusts up to {wind_gust} mph)"
            parts.append(f"Wind: {wind_desc}")
        
        # Precipitation
        precip_prob = weather_data.get('precip_probability', 0)
        precip_type = weather_data.get('precip_type')
        if precip_prob > 0:
            if precip_type:
                parts.append(f"{precip_prob * 100:.0f}% chance of {precip_type}")
            else:
                parts.append(f"{precip_prob * 100:.0f}% chance of precipitation")
        
        # Humidity
        humidity = weather_data.get('humidity', 0)
        if humidity:
            parts.append(f"Humidity: {humidity * 100:.0f}%")
        
        # Cloud cover
        cloud_cover = weather_data.get('cloud_cover', 0)
        if cloud_cover is not None:
            if cloud_cover < 0.25:
                parts.append("Mostly clear")
            elif cloud_cover < 0.5:
                parts.append("Partly cloudy")
            elif cloud_cover < 0.75:
                parts.append("Mostly cloudy")
            else:
                parts.append("Overcast")
        
        return ", ".join(parts) if parts else "Weather conditions unknown."


def get_current_weather(api_key: str, use_cache: bool = True) -> dict:
    """
    Convenience function to get current weather.
    
    Args:
        api_key: Pirate Weather API key
        use_cache: Use cached data if available
        
    Returns:
        Weather data dictionary
    """
    client = PirateWeatherClient(api_key)
    return client.get_current_weather(use_cache=use_cache)

