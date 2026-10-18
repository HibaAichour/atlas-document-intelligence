"""Tests for the health endpoint."""

from fastapi.testclient import TestClient

from app.main import APP_VERSION, app

client = TestClient(app)


def test_health_returns_ok() -> None:
    """The health endpoint answers 200 with the expected status payload."""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": APP_VERSION}