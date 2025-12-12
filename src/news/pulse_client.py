"""Client for fetching news headlines from Pulse API."""
import requests
import random
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

PULSE_API_BASE = "https://pulse.henzi.org/api"


def get_random_headlines(count: int = 2) -> List[str]:
    """
    Fetch random headlines from Pulse API.
    
    Randomly selects a cluster (c-1, c-2, or c-3) and fetches headlines.
    
    Args:
        count: Number of headlines to fetch (default: 2)
        
    Returns:
        List of headline titles, or empty list if fetch fails
    """
    try:
        # Randomly select a cluster
        cluster_id = random.choice(['c-1', 'c-2', 'c-3'])
        url = f"{PULSE_API_BASE}/clusters/{cluster_id}/articles"
        
        params = {
            'limit': count
        }
        
        logger.info(f"Fetching headlines from cluster {cluster_id}...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        articles = data.get('articles', [])
        
        headlines = [article.get('title', '') for article in articles if article.get('title')]
        
        if headlines:
            logger.info(f"✅ Fetched {len(headlines)} headlines: {headlines[:2]}")
        else:
            logger.warning("No headlines found in API response")
        
        return headlines
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to fetch headlines: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching headlines: {e}")
        return []


class PulseClient:
    """Client for Pulse API news integration."""
    
    def __init__(self):
        self.api_base = PULSE_API_BASE
    
    def get_headlines(self, cluster_id: Optional[str] = None, limit: int = 2) -> List[str]:
        """
        Get headlines from a specific cluster or random cluster.
        
        Args:
            cluster_id: Cluster ID (c-1, c-2, c-3) or None for random
            limit: Number of headlines to fetch
            
        Returns:
            List of headline titles
        """
        if cluster_id is None:
            cluster_id = random.choice(['c-1', 'c-2', 'c-3'])
        
        try:
            url = f"{self.api_base}/clusters/{cluster_id}/articles"
            params = {'limit': limit}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            articles = data.get('articles', [])
            headlines = [article.get('title', '') for article in articles if article.get('title')]
            
            return headlines
            
        except Exception as e:
            logger.warning(f"Failed to fetch headlines from {cluster_id}: {e}")
            return []
    
    def get_sentiment_overview(self) -> Optional[Dict]:
        """
        Get overall sentiment statistics from Pulse API.
        
        Returns:
            Dictionary with sentiment data, or None if fetch fails
        """
        try:
            url = f"{self.api_base}/stats/overview"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.warning(f"Failed to fetch sentiment overview: {e}")
            return None

