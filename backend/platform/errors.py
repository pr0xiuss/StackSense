"""StackSense application error contracts."""

from enum import StrEnum
from typing import Any


class ErrorCategory(StrEnum):
    """Canonical high-level error categories."""

    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    INTERNAL = "internal"


class ErrorSeverity(StrEnum):
    """Error severity levels."""

    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorScope(StrEnum):
    """Scope at which an error occurs."""

    REQUEST = "request"
    SYSTEM = "system"


class StackSenseError(Exception):
    """Base exception for intentional StackSense application failures."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        scope: ErrorScope = ErrorScope.REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)

        self.code = code
        self.message = message
        self.category = category
        self.severity = severity
        self.scope = scope
        self.details = details or {}