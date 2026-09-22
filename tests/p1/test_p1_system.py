"""Tests for the StackSense system endpoints."""

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.platform.config import get_settings


def test_system_info_returns_application_information() -> None:
    """System information returns configured application values."""
    client = TestClient(app)
    settings = get_settings()

    response = client.get("/api/v1/system/info")

    assert response.status_code == 200
    assert response.json() == {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }


def test_database_endpoint_is_exposed() -> None:
    """Database system endpoint is exposed by the v1 API."""
    client = TestClient(app)

    response = client.get("/api/v1/system/database")

    assert response.status_code == 200
    assert response.json() == {"status": "connected"}
