import pytest
from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)

def test_api_endpoints_accessible_without_auth():
    # Attempting to fetch state without auth should succeed with 200
    response = client.get("/api/state")
    assert response.status_code == 200

    # Attempting to fetch signals without auth should succeed with 200
    response = client.get("/api/signals")
    assert response.status_code == 200

    # Attempting to fetch strategy details without auth should succeed with 200
    response = client.get("/api/strategy/base")
    assert response.status_code == 200

