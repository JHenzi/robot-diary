"""Client for fetching news headlines from Pulse API."""
import requests
import random
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

PULSE_API_BASE = "https://pulse.henzi.org/api"


def get_clusters_list() -> List[Dict]:
    """
    Fetch list of all available news clusters.
    
    Returns:
        List of cluster dictionaries with cluster_id, topic_label, etc.
    """
    try:
        url = f"{PULSE_API_BASE}/clusters/"
        logger.info(f"Fetching clusters list from {url}...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        clusters = response.json()
        logger.info(f"✅ Fetched {len(clusters)} clusters")
        return clusters
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to fetch clusters list: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching clusters list: {e}")
        return []


def get_random_cluster() -> Optional[Dict]:
    """
    Get a random cluster from the available clusters.
    
    Returns:
        Random cluster dictionary, or None if fetch fails
    """
    clusters = get_clusters_list()
    if not clusters:
        return None
    
    cluster = random.choice(clusters)
    logger.info(f"Selected random cluster: {cluster.get('cluster_id')} - {cluster.get('topic_label')}")
    return cluster


def get_cluster_articles(cluster_id: str, limit: int = 3) -> List[Dict]:
    """
    Fetch articles for a specific cluster with full metadata.
    
    Args:
        cluster_id: Cluster ID (e.g., 'c-1', 'c-22')
        limit: Number of articles to fetch
        
    Returns:
        List of article dictionaries with title, published_at, source, sentiment_label, etc.
    """
    try:
        url = f"{PULSE_API_BASE}/clusters/{cluster_id}/articles"
        params = {'limit': limit}
        
        logger.info(f"Fetching articles from cluster {cluster_id}...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        articles = data.get('articles', [])
        
        if articles:
            logger.info(f"✅ Fetched {len(articles)} articles from {cluster_id}")
        else:
            logger.warning(f"No articles found in cluster {cluster_id}")
        
        return articles
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to fetch articles from {cluster_id}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching articles from {cluster_id}: {e}")
        return []


def get_cluster_headlines(cluster_id: str, limit: int = 3) -> List[str]:
    """
    Fetch headlines for a specific cluster (backward compatibility).
    
    Args:
        cluster_id: Cluster ID (e.g., 'c-1', 'c-22')
        limit: Number of headlines to fetch
        
    Returns:
        List of headline titles
    """
    articles = get_cluster_articles(cluster_id, limit)
    return [article.get('title', '') for article in articles if article.get('title')]


def get_random_headlines(count: int = 2) -> List[str]:
    """
    Fetch random headlines from Pulse API (backward compatibility).
    
    Randomly selects a cluster and fetches headlines.
    
    Args:
        count: Number of headlines to fetch (default: 2)
        
    Returns:
        List of headline titles, or empty list if fetch fails
    """
    cluster = get_random_cluster()
    if not cluster:
        return []
    
    cluster_id = cluster.get('cluster_id')
    if not cluster_id:
        return []
    
    return get_cluster_headlines(cluster_id, limit=count)


def get_random_articles(count: int = 2) -> List[Dict]:
    """
    Fetch random articles from Pulse API with full metadata.
    
    Randomly selects a cluster and fetches articles.
    
    Args:
        count: Number of articles to fetch (default: 2)
        
    Returns:
        List of article dictionaries with full metadata, or empty list if fetch fails
    """
    cluster = get_random_cluster()
    if not cluster:
        return []
    
    cluster_id = cluster.get('cluster_id')
    if not cluster_id:
        return []
    
    return get_cluster_articles(cluster_id, limit=count)


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

