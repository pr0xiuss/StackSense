"""Tests for the StackSense API error contract."""

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.platform.errors import ErrorCategory, StackSenseError


def test_application_error_response() -> None:
    """Application errors are translated into the public error contract."""
    client = TestClient(app)

    async def failing_endpoint() -> None:
        raise StackSenseError(
            code="TEST_ERROR",
            message="Test error.",
            category=ErrorCategory.INTERNAL,
        )

    app.add_api_route(
        "/_test/error-contract",
        failing_endpoint,
        methods=["GET"],
    )

    try:
        response = client.get("/_test/error-contract")
    finally:
        app.router.routes.pop()

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "TEST_ERROR",
            "message": "Test error.",
            "details": {},
        }
    }
