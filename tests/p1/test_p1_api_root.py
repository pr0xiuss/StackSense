"""Tests for the StackSense API root endpoint."""

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.platform.config import get_settings


def test_api_root_returns_metadata() -> None:
    """API root returns the configured application metadata."""
    client = TestClient(app)
    settings = get_settings()

    response = client.get("/api/v1/")

    assert response.status_code == 200
    assert response.json() == {
        "name": settings.app_name,
        "version": settings.app_version,
    }


def test_api_root_rejects_unexpected_response_fields() -> None:
    """API metadata schema forbids unexpected response fields."""
    client = TestClient(app)

    response = client.get("/api/v1/")

    assert set(response.json()) == {"name", "version"}
