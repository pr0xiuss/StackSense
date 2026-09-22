"""Integration tests for the StackSense database system endpoint."""

from fastapi.testclient import TestClient

from backend.api.app import app


def test_database_status_reports_connection() -> None:
    """Database endpoint confirms PostgreSQL connectivity."""
    client = TestClient(app)

    response = client.get("/api/v1/system/database")

    assert response.status_code == 200
    assert response.json() == {"status": "connected"}


def test_database_status_exposes_expected_response_fields() -> None:
    """Database status exposes only its public contract."""
    client = TestClient(app)

    response = client.get("/api/v1/system/database")

    assert set(response.json()) == {"status"}
