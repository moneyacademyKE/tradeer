import pytest
from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)

def test_api_endpoints_require_authentication():
    # Attempting to fetch state without auth should fail with 401
    response = client.get("/api/state")
    assert response.status_code == 401

    # Attempting to fetch signals without auth should fail with 401
    response = client.get("/api/signals")
    assert response.status_code == 401

    # Attempting to fetch strategy details without auth should fail with 401
    response = client.get("/api/strategy/base")
    assert response.status_code == 401

def test_api_endpoints_accept_valid_credentials(monkeypatch):
    # Mock environment variables for testing
    monkeypatch.setenv("DASHBOARD_USERNAME", "testuser")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "testpass")

    # Request with valid credentials should succeed
    auth = ("testuser", "testpass")
    
    response = client.get("/api/state", auth=auth)
    assert response.status_code == 200

    response = client.get("/api/signals", auth=auth)
    assert response.status_code == 200

    response = client.get("/api/strategy/base", auth=auth)
    assert response.status_code == 200

def test_api_endpoints_reject_invalid_credentials(monkeypatch):
    monkeypatch.setenv("DASHBOARD_USERNAME", "testuser")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "testpass")

    # Request with invalid credentials should fail with 401
    auth = ("testuser", "wrongpass")
    
    response = client.get("/api/state", auth=auth)
    assert response.status_code == 401
