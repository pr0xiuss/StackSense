"""Tests for StackSense API exception handlers."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.error_handlers import register_exception_handlers
from backend.platform.errors import ErrorCategory, StackSenseError


def create_test_application() -> FastAPI:
    """Create a minimal application with the StackSense error handler."""
    application = FastAPI()
    register_exception_handlers(application)

    @application.get("/test-error")
    async def test_error() -> None:
        raise StackSenseError(
            code="TEST_ERROR",
            message="Test error.",
            category=ErrorCategory.INTERNAL,
            details={"key": "value"},
        )

    return application


def test_stacksense_error_response() -> None:
    """StackSense errors are translated into the public API contract."""
    client = TestClient(create_test_application())

    response = client.get("/test-error")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "TEST_ERROR",
            "message": "Test error.",
            "details": {"key": "value"},
        }
    }
