from fastapi import status

def test_health_check(client):
    """
    Test the GET /health endpoint.
    """
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_name" in data
