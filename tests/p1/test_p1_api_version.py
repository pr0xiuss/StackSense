"""Tests for the StackSense API versioning foundation."""

from fastapi.testclient import TestClient

from backend.api.app import app


def test_v1_health_endpoint_is_available() -> None:
    """Version 1 exposes the health endpoint."""
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200


def test_unversioned_health_endpoint_is_not_available() -> None:
    """Health is not exposed outside the versioned API namespace."""
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 404
