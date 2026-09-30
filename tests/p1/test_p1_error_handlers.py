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


def test_m4_acquisition_error_status_mappings() -> None:
    """Verify that all new M4 acquisition error types map to expected HTTP codes."""
    from backend.platform.errors import (
        GitHubAccessDeniedError,
        GitHubAcquisitionError,
        GitHubNetworkError,
        GitHubRateLimitExceededError,
        GitHubRepositoryNotFoundError,
        GitHubTimeoutError,
        InvalidGitHubRefError,
        InvalidGitHubUrlError,
        InvalidSourceTypeError,
        MaxFileCountExceededError,
        ServerPathNotAllowedError,
        ServerPathNotFoundError,
        UnsupportedArchiveFormatError,
    )

    test_cases = [
        (InvalidSourceTypeError(), 422, "invalid_source_type"),
        (InvalidGitHubUrlError(), 422, "invalid_github_url"),
        (InvalidGitHubRefError(), 422, "invalid_github_ref"),
        (GitHubRepositoryNotFoundError(), 404, "github_repository_not_found"),
        (GitHubAcquisitionError(), 502, "github_acquisition_failed"),
        (GitHubRateLimitExceededError(), 429, "github_rate_limit_exceeded"),
        (GitHubAccessDeniedError(), 403, "github_access_denied"),
        (GitHubNetworkError(), 503, "github_network_error"),
        (GitHubTimeoutError(), 504, "github_timeout"),
        (UnsupportedArchiveFormatError(), 422, "unsupported_archive_format"),
        (ServerPathNotAllowedError(), 403, "server_path_not_allowed"),
        (ServerPathNotFoundError(), 404, "server_path_not_found"),
        (MaxFileCountExceededError(), 422, "max_file_count_exceeded"),
    ]

    for err, expected_status, expected_code in test_cases:
        app = FastAPI()
        register_exception_handlers(app)

        def make_handler(exc_to_raise: Exception):
            async def _handler() -> None:
                raise exc_to_raise

            return _handler

        app.add_api_route(
            f"/test-{expected_code}",
            make_handler(err),
            methods=["GET"],
        )

        c = TestClient(app)
        res = c.get(f"/test-{expected_code}")
        assert (
            res.status_code == expected_status
        ), f"Expected {expected_status} for {expected_code}, got {res.status_code}"
        assert res.json()["error"]["code"] == expected_code
