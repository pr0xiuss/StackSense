"""Tests for StackSense application error contracts."""

from backend.platform.errors import (
    ErrorCategory,
    ErrorScope,
    ErrorSeverity,
    StackSenseError,
)


def test_stacksense_error_preserves_contract() -> None:
    """StackSense errors preserve their defined attributes."""
    error = StackSenseError(
        code="TEST_ERROR",
        message="Test error.",
        category=ErrorCategory.INTERNAL,
        severity=ErrorSeverity.CRITICAL,
        scope=ErrorScope.SYSTEM,
        details={"component": "database"},
    )

    assert error.code == "TEST_ERROR"
    assert error.message == "Test error."
    assert error.category == ErrorCategory.INTERNAL
    assert error.severity == ErrorSeverity.CRITICAL
    assert error.scope == ErrorScope.SYSTEM
    assert error.details == {"component": "database"}
