"""Tests for news client (mocked, no API calls)."""
import pytest
from unittest.mock import patch, Mock
from src.news.pulse_client import (
    get_clusters_list,
    get_random_cluster,
    get_cluster_articles,
    get_cluster_headlines,
    get_random_headlines,
    get_random_articles,
    PulseClient
)


class TestPulseClientFunctions:
    """Test Pulse API client functions with mocked requests."""
    
    def test_get_clusters_list_success(self):
        """Test successful cluster list fetch."""
        mock_clusters = [
            {'cluster_id': 'c-1', 'topic_label': 'Technology'},
            {'cluster_id': 'c-2', 'topic_label': 'Politics'}
        ]
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_clusters
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = get_clusters_list()
            assert len(result) == 2
            assert result[0]['cluster_id'] == 'c-1'
    
    def test_get_clusters_list_request_error(self):
        """Test cluster list fetch with request error."""
        with patch('requests.get', side_effect=Exception("Network error")):
            result = get_clusters_list()
            assert result == []
    
    def test_get_clusters_list_http_error(self):
        """Test cluster list fetch with HTTP error."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = Exception("404 Not Found")
            mock_get.return_value = mock_response
            
            result = get_clusters_list()
            assert result == []
    
    def test_get_random_cluster_success(self):
        """Test getting random cluster."""
        mock_clusters = [
            {'cluster_id': 'c-1', 'topic_label': 'Tech'},
            {'cluster_id': 'c-2', 'topic_label': 'News'}
        ]
        
        with patch('src.news.pulse_client.get_clusters_list', return_value=mock_clusters):
            result = get_random_cluster()
            assert result is not None
            assert result['cluster_id'] in ['c-1', 'c-2']
    
    def test_get_random_cluster_no_clusters(self):
        """Test getting random cluster when no clusters available."""
        with patch('src.news.pulse_client.get_clusters_list', return_value=[]):
            result = get_random_cluster()
            assert result is None
    
    def test_get_cluster_articles_success(self):
        """Test fetching cluster articles."""
        mock_articles = {
            'articles': [
                {
                    'title': 'Article 1',
                    'published_at': '2025-12-12T10:00:00Z',
                    'source': 'Source 1',
                    'sentiment_label': 'positive'
                },
                {
                    'title': 'Article 2',
                    'published_at': '2025-12-12T11:00:00Z',
                    'source': 'Source 2',
                    'sentiment_label': 'neutral'
                }
            ]
        }
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_articles
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = get_cluster_articles('c-1', limit=2)
            assert len(result) == 2
            assert result[0]['title'] == 'Article 1'
            assert result[0]['published_at'] == '2025-12-12T10:00:00Z'
    
    def test_get_cluster_articles_empty(self):
        """Test fetching articles from empty cluster."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {'articles': []}
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = get_cluster_articles('c-1')
            assert result == []
    
    def test_get_cluster_articles_error(self):
        """Test fetching articles with error."""
        with patch('requests.get', side_effect=Exception("Error")):
            result = get_cluster_articles('c-1')
            assert result == []
    
    def test_get_cluster_headlines(self):
        """Test getting headlines from cluster."""
        mock_articles = [
            {'title': 'Headline 1'},
            {'title': 'Headline 2'},
            {'title': ''}  # Empty title should be filtered
        ]
        
        with patch('src.news.pulse_client.get_cluster_articles', return_value=mock_articles):
            result = get_cluster_headlines('c-1', limit=3)
            assert len(result) == 2  # Empty title filtered out
            assert 'Headline 1' in result
            assert 'Headline 2' in result
    
    def test_get_random_headlines_success(self):
        """Test getting random headlines."""
        mock_cluster = {'cluster_id': 'c-1'}
        mock_headlines = ['Headline 1', 'Headline 2']
        
        with patch('src.news.pulse_client.get_random_cluster', return_value=mock_cluster), \
             patch('src.news.pulse_client.get_cluster_headlines', return_value=mock_headlines):
            result = get_random_headlines(count=2)
            assert len(result) == 2
            assert 'Headline 1' in result
    
    def test_get_random_headlines_no_cluster(self):
        """Test getting random headlines when no cluster available."""
        with patch('src.news.pulse_client.get_random_cluster', return_value=None):
            result = get_random_headlines(count=2)
            assert result == []
    
    def test_get_random_articles_success(self):
        """Test getting random articles."""
        mock_cluster = {'cluster_id': 'c-1'}
        mock_articles = [
            {'title': 'Article 1', 'source': 'Source 1'},
            {'title': 'Article 2', 'source': 'Source 2'}
        ]
        
        with patch('src.news.pulse_client.get_random_cluster', return_value=mock_cluster), \
             patch('src.news.pulse_client.get_cluster_articles', return_value=mock_articles):
            result = get_random_articles(count=2)
            assert len(result) == 2
            assert result[0]['title'] == 'Article 1'


class TestPulseClientClass:
    """Test PulseClient class methods."""
    
    @pytest.fixture
    def pulse_client(self):
        """Create PulseClient instance."""
        return PulseClient()
    
    def test_client_initialization(self, pulse_client):
        """Test client initialization."""
        assert pulse_client.api_base == "https://pulse.henzi.org/api"
    
    def test_get_headlines_with_cluster_id(self, pulse_client):
        """Test getting headlines with specific cluster ID."""
        mock_articles = {
            'articles': [
                {'title': 'Headline 1'},
                {'title': 'Headline 2'}
            ]
        }
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_articles
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = pulse_client.get_headlines(cluster_id='c-1', limit=2)
            assert len(result) == 2
            assert 'Headline 1' in result
    
    def test_get_headlines_random_cluster(self, pulse_client):
        """Test getting headlines with random cluster."""
        mock_articles = {
            'articles': [
                {'title': 'Random Headline'}
            ]
        }
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_articles
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = pulse_client.get_headlines(cluster_id=None, limit=1)
            assert len(result) == 1
    
    def test_get_headlines_error(self, pulse_client):
        """Test getting headlines with error."""
        with patch('requests.get', side_effect=Exception("Error")):
            result = pulse_client.get_headlines(cluster_id='c-1')
            assert result == []
    
    def test_get_sentiment_overview_success(self, pulse_client):
        """Test getting sentiment overview."""
        mock_sentiment = {
            'positive': 0.6,
            'negative': 0.2,
            'neutral': 0.2
        }
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_sentiment
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = pulse_client.get_sentiment_overview()
            assert result == mock_sentiment
    
    def test_get_sentiment_overview_error(self, pulse_client):
        """Test getting sentiment overview with error."""
        with patch('requests.get', side_effect=Exception("Error")):
            result = pulse_client.get_sentiment_overview()
            assert result is None

