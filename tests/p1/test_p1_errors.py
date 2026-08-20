"""Tests for StackSense application errors."""

from backend.platform.errors import (
    ErrorCategory,
    ErrorScope,
    ErrorSeverity,
    StackSenseError,
)


def test_stacksense_error_preserves_contract() -> None:
    """Application errors preserve their defined attributes."""
    error = StackSenseError(
        code="TEST_ERROR",
        message="Test error.",
        category=ErrorCategory.INTERNAL,
        severity=ErrorSeverity.ERROR,
        scope=ErrorScope.REQUEST,
        details={"key": "value"},
    )

    assert error.code == "TEST_ERROR"
    assert error.message == "Test error."
    assert error.category == ErrorCategory.INTERNAL
    assert error.severity == ErrorSeverity.ERROR
    assert error.scope == ErrorScope.REQUEST
    assert error.details == {"key": "value"}
