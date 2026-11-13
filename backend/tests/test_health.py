import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["service"] == "Proofline API"
    assert data["version"] == "0.1.0"


def test_root_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "running"
    assert data["health"] == "/api/v1/health"


def test_request_id_header(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert "x-request-id" in response.headers


def test_security_headers(client):
    response = client.get("/api/v1/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_cors_preflight(client):
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_auth_requires_bearer_token(client):
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_workspaces_require_authentication(client):
    response = client.get("/api/v1/workspaces")

    assert response.status_code == 401


def test_workspace_creation_requires_authentication(client):
    response = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Test Workspace",
            "slug": "test-workspace",
        },
    )

    assert response.status_code == 401
