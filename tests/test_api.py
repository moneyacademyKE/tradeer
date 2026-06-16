import pytest
from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)

def test_api_endpoints_require_auth():
    # Without auth, all /api/ endpoints should return 401
    response = client.get("/api/state")
    assert response.status_code == 401

    response = client.get("/api/signals")
    assert response.status_code == 401

    response = client.get("/api/strategy/base")
    assert response.status_code == 401

def test_api_endpoints_accessible_with_auth():
    headers = {"Authorization": "Basic YWRtaW46YWRtaW4="}  # admin:admin
    response = client.get("/api/state", headers=headers)
    assert response.status_code == 200

    response = client.get("/api/signals", headers=headers)
    assert response.status_code == 200

    response = client.get("/api/strategy/base", headers=headers)
    assert response.status_code == 200
