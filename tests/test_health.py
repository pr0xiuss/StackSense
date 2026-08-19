"""Tests for StackSense health endpoints."""

from fastapi.testclient import TestClient


def test_liveness(client: TestClient) -> None:
    """Liveness endpoint reports that the application is alive."""
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness(client: TestClient) -> None:
    """Readiness endpoint reports that the application is ready."""
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
