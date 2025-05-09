from typing import Dict
import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))
from feddit_api.main import app, analyze_sentiment

client = TestClient(app)

@pytest.fixture
def mock_feddit_client(monkeypatch) -> None:
    test_comments = [
        {
            'id': 1,
            'username': 'user1',
            'text': 'This is a great comment!',
            'created_at': 1234567890
        },
        {
            'id': 2,
            'username': 'user2',
            'text': 'This is a terrible comment.',
            'created_at': 1234567891
        },
        {
            'id': 3,
            'username': 'user3',
            'text': 'This is a neutral comment.',
            'created_at': 1234567892
        }
    ]

    async def mock_get_subfeddit_by_name(*args, **kwargs) -> Dict:
        return {
            'id': 1,
            'title': 'test_subfeddit'
        }

    async def mock_get_comments(subfeddit_id: int, limit: int = None, skip: int = 0) -> Dict:
        start = skip
        end = start + limit if limit else len(test_comments)
        comments = test_comments[start:end]
        return {
            'subfeddit_id': 1,
            'comments': comments,
            'limit': limit,
            'skip': skip
        }

    from feddit_api.main import feddit_client
    monkeypatch.setattr(feddit_client, "get_subfeddit_by_name", mock_get_subfeddit_by_name)
    monkeypatch.setattr(feddit_client, "get_comments", mock_get_comments)

def test_get_comments(mock_feddit_client: None) -> None:
    response = client.get("/api/subfeddit/test_subfeddit/comments", params={"limit": 5})
    assert response.status_code == 200
    data = response.json()
    assert data['subfeddit_name'] == 'test_subfeddit'
    assert len(data['comments']) == 3
    
    for comment in data['comments']:
        assert all(key in comment for key in ('id', 'username', 'text', 'created_at', 'sentiment'))
        assert all(key in comment['sentiment'] for key in ('polarity', 'classification'))
        assert comment['sentiment']['classification'] in ('positive', 'negative', 'neutral')

def test_get_comments_with_pagination(mock_feddit_client: None) -> None:
    response = client.get("/api/subfeddit/test_subfeddit/comments", params={"limit": 2, "skip": 1})
    assert response.status_code == 200
    data = response.json()
    assert len(data['comments']) == 2
    assert data['skip'] == 1
    assert data['limit'] == 2

def test_get_comments_sorted_by_polarity(mock_feddit_client: None) -> None:
    response = client.get("/api/subfeddit/test_subfeddit/comments", 
                         params={"sort_by": "polarity", "sort_order": "desc"})
    assert response.status_code == 200
    data = response.json()
    polarities = [comment['sentiment']['polarity'] for comment in data['comments']]
    assert polarities == sorted(polarities, reverse=True)

def test_get_comments_sorted_by_created_at(mock_feddit_client: None) -> None:
    response = client.get("/api/subfeddit/test_subfeddit/comments", 
                         params={"sort_by": "created_at", "sort_order": "asc"})
    assert response.status_code == 200
    data = response.json()
    timestamps = [comment['created_at'] for comment in data['comments']]
    assert timestamps == sorted(timestamps)

def test_get_comments_filtered_by_sentiment(mock_feddit_client: None) -> None:
    response = client.get("/api/subfeddit/test_subfeddit/comments", 
                         params={"filter_by": "positive"})
    assert response.status_code == 200
    data = response.json()
    assert all(comment['sentiment']['classification'] == 'positive' for comment in data['comments'])

def test_analyze_sentiment_endpoint() -> None:
    response = client.post("/api/sentiment/analyze", 
                          json={"text": "This is a great comment!"})
    assert response.status_code == 200
    data = response.json()
    assert all(key in data for key in ('polarity', 'classification'))
    assert data['classification'] in ('positive', 'negative', 'neutral')

def test_analyze_sentiment_endpoint_invalid_request() -> None:
    response = client.post("/api/sentiment/analyze", 
                          json={"invalid": "field"})
    assert response.status_code == 422

def test_get_comments_invalid_subfeddit(monkeypatch) -> None:
    async def mock_error(*args, **kwargs):
        raise ValueError("Subfeddit not found")
    
    from feddit_api.main import feddit_client
    monkeypatch.setattr(feddit_client, "get_subfeddit_by_name", mock_error)
    
    response = client.get("/api/subfeddit/nonexistent/comments")
    assert response.status_code == 500 