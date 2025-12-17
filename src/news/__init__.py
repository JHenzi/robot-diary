"""News integration for contextual awareness."""
from .pulse_client import (
    PulseClient, 
    get_random_headlines,
    get_random_articles,
    get_clusters_list,
    get_random_cluster,
    get_cluster_headlines,
    get_cluster_articles,
    get_articles_from_multiple_clusters
)

__all__ = [
    'PulseClient', 
    'get_random_headlines',
    'get_random_articles',
    'get_clusters_list',
    'get_random_cluster',
    'get_cluster_headlines',
    'get_cluster_articles',
    'get_articles_from_multiple_clusters'
]

