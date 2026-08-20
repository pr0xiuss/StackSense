"""Tests for the StackSense health endpoint."""

from fastapi.testclient import TestClient

from backend.api.app import app


def test_health_endpoint() -> None:
    """Health endpoint reports application readiness."""
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
