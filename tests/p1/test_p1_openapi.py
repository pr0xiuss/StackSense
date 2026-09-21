"""Tests for the P1 OpenAPI contract."""

from backend.api.app import app


def test_p1_system_endpoints_are_documented() -> None:
    """P1 system endpoints are present in the OpenAPI document."""
    schema = app.openapi()

    assert "/api/v1/" in schema["paths"]
    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/system/info" in schema["paths"]
    assert "/api/v1/system/database" in schema["paths"]


def test_database_endpoint_declares_response_schema() -> None:
    """Database endpoint declares its response schema."""
    schema = app.openapi()

    response = schema["paths"]["/api/v1/system/database"]["get"]["responses"]["200"]

    assert "content" in response
    assert "application/json" in response["content"]
