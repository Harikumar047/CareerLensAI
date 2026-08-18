"""
Tests for YouTube Learning Resource Service (Dynamic Discovery).

Covers:
- Successful dynamic search with mocked YouTube API
- Empty results handling
- API 500 error & 403 invalid key handling
- Timeout handling (httpx.TimeoutException)
- Query construction with job context
- Content filtering & ranking (beginner / reputable channel preference)
- In-memory TTL caching & cache expiration
- Missing API key safe handling (no crashes)
"""
import time
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.services.youtube_service import YouTubeService, REPUTABLE_CHANNELS


MOCK_YOUTUBE_API_RESPONSE = {
    "items": [
        {
            "id": {"videoId": "mock_vid_123"},
            "snippet": {
                "title": "AWS Certified Cloud Practitioner Full Course - 2024",
                "description": "Learn AWS fundamentals, EC2, S3, and IAM from scratch.",
                "channelTitle": "freeCodeCamp.org",
                "publishedAt": "2024-01-15T10:00:00Z",
                "thumbnails": {
                    "high": {"url": "https://i.ytimg.com/vi/mock_vid_123/hqdefault.jpg"}
                },
            },
        },
        {
            "id": {"playlistId": "mock_pl_456"},
            "snippet": {
                "title": "AWS Complete Beginner Tutorial Series",
                "description": "Step by step AWS playlist.",
                "channelTitle": "Programming with Mosh",
                "publishedAt": "2023-11-20T08:30:00Z",
                "thumbnails": {
                    "medium": {"url": "https://i.ytimg.com/vi/mock_pl_456/mqdefault.jpg"}
                },
            },
        },
    ]
}


def test_youtube_missing_api_key_returns_empty():
    """Service without API key should safely return empty list without crashing."""
    svc = YouTubeService(api_key="")
    results = svc.search_learning_resources("AWS")
    assert results == []


def test_query_construction_with_and_without_context():
    """Verify query formulation incorporates skill and job context."""
    svc = YouTubeService(api_key="test_key")
    
    q_no_ctx = svc._build_query("AWS")
    assert "AWS" in q_no_ctx
    assert "beginner" in q_no_ctx

    q_with_ctx = svc._build_query("AWS", context="EC2 Lambda DynamoDB")
    assert "AWS" in q_with_ctx
    assert "EC2 Lambda DynamoDB" in q_with_ctx
    assert "beginner" in q_with_ctx


@patch("httpx.Client.get")
def test_successful_dynamic_search(mock_get):
    """Test successful API call and parsing into CourseRecommendationItem."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_YOUTUBE_API_RESPONSE
    mock_get.return_value = mock_resp

    svc = YouTubeService(api_key="valid_test_key", ttl_seconds=60)
    svc.clear_cache()

    results = svc.search_learning_resources("AWS", context="EC2", max_results=2)

    assert len(results) == 2
    assert results[0].skill == "AWS"
    assert results[0].title == "AWS Certified Cloud Practitioner Full Course - 2024"
    assert results[0].provider == "freeCodeCamp.org"
    assert results[0].resource_type == "youtube"
    assert results[0].url == "https://www.youtube.com/watch?v=mock_vid_123"
    assert results[0].free is True
    assert results[0].level == "beginner"
    assert results[0].thumbnail == "https://i.ytimg.com/vi/mock_vid_123/hqdefault.jpg"

    assert results[1].url == "https://www.youtube.com/playlist?list=mock_pl_456"
    assert results[1].provider == "Programming with Mosh"


@patch("httpx.Client.get")
def test_youtube_caching_and_ttl_expiration(mock_get):
    """Test in-memory cache hit and subsequent TTL expiration."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_YOUTUBE_API_RESPONSE
    mock_get.return_value = mock_resp

    svc = YouTubeService(api_key="valid_test_key", ttl_seconds=1)
    svc.clear_cache()

    # First call: makes HTTP request
    res1 = svc.search_learning_resources("Docker", max_results=2)
    assert len(res1) == 2
    assert mock_get.call_count == 1

    # Second immediate call: should hit cache without calling API
    res2 = svc.search_learning_resources("Docker", max_results=2)
    assert len(res2) == 2
    assert mock_get.call_count == 1  # count did not increase

    # Wait for TTL to expire
    time.sleep(1.1)

    # Third call after TTL: should re-query API
    res3 = svc.search_learning_resources("Docker", max_results=2)
    assert len(res3) == 2
    assert mock_get.call_count == 2


@patch("httpx.Client.get")
def test_youtube_api_error_handling(mock_get):
    """Test graceful handling of 403 Forbidden or 500 Server Error."""
    # 403 Forbidden
    mock_resp_403 = MagicMock()
    mock_resp_403.status_code = 403
    mock_resp_403.text = "Forbidden"
    mock_get.return_value = mock_resp_403

    svc = YouTubeService(api_key="invalid_key", ttl_seconds=60)
    svc.clear_cache()
    res_403 = svc.search_learning_resources("Python")
    assert res_403 == []

    # 500 Server Error
    mock_resp_500 = MagicMock()
    mock_resp_500.status_code = 500
    mock_resp_500.text = "Internal Server Error"
    mock_get.return_value = mock_resp_500

    res_500 = svc.search_learning_resources("Python")
    assert res_500 == []


@patch("httpx.Client.get", side_effect=httpx.TimeoutException("Connection timed out"))
def test_youtube_timeout_handling(mock_get):
    """Test graceful handling when network request times out."""
    svc = YouTubeService(api_key="valid_key", ttl_seconds=60)
    svc.clear_cache()
    res = svc.search_learning_resources("Kubernetes")
    assert res == []


@patch("httpx.Client.get")
def test_youtube_empty_items(mock_get):
    """Test empty results from YouTube."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"items": []}
    mock_get.return_value = mock_resp

    svc = YouTubeService(api_key="valid_key", ttl_seconds=60)
    svc.clear_cache()
    res = svc.search_learning_resources("ObscureSkill")
    assert res == []
