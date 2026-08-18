import os
import pytest
import json
from unittest.mock import patch
import httpx
from fastapi import status, HTTPException
from app.config import settings
from app.models.job import Job, JobSearchResponse
from app.services.job_client import AdzunaJobClient

# Ensure test settings have credentials for client check
@pytest.fixture(autouse=True)
def setup_test_credentials():
    old_id = settings.ADZUNA_APP_ID
    old_key = settings.ADZUNA_APP_KEY
    settings.ADZUNA_APP_ID = "mock_app_id"
    settings.ADZUNA_APP_KEY = "mock_app_key"
    yield
    settings.ADZUNA_APP_ID = old_id
    settings.ADZUNA_APP_KEY = old_key

# Helper to construct mock response with a request attached
def create_mock_response(status_code: int, json_data: dict = None) -> httpx.Response:
    req = httpx.Request("GET", "https://api.adzuna.com")
    return httpx.Response(status_code, json=json_data, request=req)

# Mock raw response structure from Adzuna API
ADZUNA_SUCCESS_JSON = {
    "count": 100,
    "results": [
        {
            "id": "12345",
            "title": "Software Developer",
            "description": "Develop apps with Python.",
            "salary_min": 50000.0,
            "salary_max": 70000.0,
            "contract_type": "permanent",
            "contract_time": "full_time",
            "created": "2026-08-17T12:00:00Z",
            "redirect_url": "https://example.com/job/12345",
            "company": {
                "display_name": "Pythonic Solutions"
            },
            "location": {
                "display_name": "Chennai, Tamil Nadu"
            },
            "category": {
                "label": "IT Jobs"
            }
        }
    ]
}

# ----------------- Client Unit Tests -----------------

def test_job_normalization():
    """
    Test that the raw Adzuna object maps correctly to our Job Pydantic schema.
    """
    client = AdzunaJobClient()
    raw_job = ADZUNA_SUCCESS_JSON["results"][0]
    normalized = client.normalize_job(raw_job)

    assert normalized.id == "adzuna_12345"
    assert normalized.title == "Software Developer"
    assert normalized.company == "Pythonic Solutions"
    assert normalized.location == "Chennai, Tamil Nadu"
    assert normalized.salary_min == 50000.0
    assert normalized.salary_max == 70000.0
    assert normalized.contract_type == "permanent"
    assert normalized.contract_time == "full_time"
    assert normalized.category == "IT Jobs"
    assert normalized.url == "https://example.com/job/12345"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_client_search_success(mock_get):
    """
    Test successful jobs retrieval and validation from client.
    """
    mock_get.return_value = create_mock_response(200, ADZUNA_SUCCESS_JSON)

    client = AdzunaJobClient()
    res = await client.search_jobs("developer", "Chennai")

    assert res["total_returned"] == 1
    assert res["total_count"] == 100
    assert len(res["jobs"]) == 1
    assert res["jobs"][0].id == "adzuna_12345"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_client_search_empty(mock_get):
    """
    Test client behavior when Adzuna returns zero results.
    """
    mock_get.return_value = create_mock_response(200, {"count": 0, "results": []})

    client = AdzunaJobClient()
    res = await client.search_jobs("xyz", "nowhere")
    assert res["total_returned"] == 0
    assert res["jobs"] == []


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_client_rate_limited(mock_get):
    """
    Test that HTTP 429 returns rate limit error.
    """
    mock_get.return_value = create_mock_response(429)

    client = AdzunaJobClient()
    with pytest.raises(HTTPException) as exc_info:
        await client.search_jobs("developer", "Chennai")
    
    assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Rate limit exceeded" in exc_info.value.detail


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_client_unauthorized(mock_get):
    """
    Test that HTTP 401 returns a configuration server error.
    """
    mock_get.return_value = create_mock_response(401)

    client = AdzunaJobClient()
    with pytest.raises(HTTPException) as exc_info:
        await client.search_jobs("developer", "Chennai")
    
    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Authentication failed" in exc_info.value.detail


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_client_server_error(mock_get):
    """
    Test that HTTP 500 triggers bad gateway/request status exception.
    """
    mock_get.return_value = create_mock_response(500)

    client = AdzunaJobClient()
    with pytest.raises(HTTPException) as exc_info:
        await client.search_jobs("developer", "Chennai")
    
    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY or exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_client_timeout(mock_get):
    """
    Test that request timeout returns gateway timeout error.
    """
    mock_get.side_effect = httpx.TimeoutException("Timeout")

    client = AdzunaJobClient()
    with pytest.raises(HTTPException) as exc_info:
        await client.search_jobs("developer", "Chennai")
    
    assert exc_info.value.status_code == status.HTTP_504_GATEWAY_TIMEOUT
    assert "timed out" in exc_info.value.detail


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_client_malformed_response(mock_get):
    """
    Test that malformed JSON triggers bad gateway exception.
    """
    mock_get.return_value = create_mock_response(200, {"results": "not a list"})

    client = AdzunaJobClient()
    with pytest.raises(HTTPException) as exc_info:
        await client.search_jobs("developer", "Chennai")
    
    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY
    assert "malformed search results" in exc_info.value.detail


# ----------------- API Route Tests -----------------

@patch("httpx.AsyncClient.get")
def test_api_jobs_search_route(mock_get, client):
    """
    Test GET /api/jobs/search endpoint success and local json caching.
    """
    mock_get.return_value = create_mock_response(200, ADZUNA_SUCCESS_JSON)

    response = client.get("/api/jobs/search?role=developer&location=Chennai")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert data["query"]["role"] == "developer"
    assert data["query"]["location"] == "Chennai"
    assert data["total_returned"] == 1
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["id"] == "adzuna_12345"
    assert "retrieved_at" in data

    # Verify that a cached file search_*.json is written to jobs_dir
    files = list(settings.JOBS_DIR.glob("search_*.json"))
    assert len(files) >= 1
    
    # Read the latest file
    latest_file = max(files, key=os.path.getctime)
    with open(latest_file, "r") as f:
        stored = json.load(f)
    assert stored["source"] == "adzuna"
    assert stored["search_parameters"]["role"] == "developer"

    # Cleanup
    latest_file.unlink()
