"""News integration for contextual awareness."""
from .pulse_client import (
    PulseClient, 
    get_random_headlines,
    get_clusters_list,
    get_random_cluster,
    get_cluster_headlines
)

__all__ = [
    'PulseClient', 
    'get_random_headlines',
    'get_clusters_list',
    'get_random_cluster',
    'get_cluster_headlines'
]

