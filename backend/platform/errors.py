"""StackSense application error contracts."""

from enum import StrEnum
from typing import Any


class ErrorCategory(StrEnum):
    """Canonical high-level error categories."""

    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    INTERNAL = "internal"
    AUTHORIZATION = "authorization"


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


class ProjectAccessDeniedError(StackSenseError):
    """Raised when a user has no access to a project."""

    def __init__(self) -> None:
        super().__init__(
            code="project_access_denied",
            message="User does not have access to this project.",
            category=ErrorCategory.AUTHORIZATION,
        )


class ProjectAccessAlreadyExistsError(StackSenseError):
    """Raised when a user already has access to a project."""

    def __init__(self) -> None:
        super().__init__(
            code="project_access_already_exists",
            message="User already has access to this project.",
            category=ErrorCategory.VALIDATION,
        )


class ProjectAccessNotFoundError(StackSenseError):
    """Raised when project access does not exist."""

    def __init__(self) -> None:
        super().__init__(
            code="project_access_not_found",
            message="Project access record does not exist.",
            category=ErrorCategory.VALIDATION,
        )


class RepositoryNotFoundError(StackSenseError):
    """Raised when a repository does not exist."""

    def __init__(self) -> None:
        super().__init__(
            code="repository_not_found",
            message="Repository not found in the specified project.",
            category=ErrorCategory.VALIDATION,
        )


class RepositoryAlreadyExistsError(StackSenseError):
    """Raised when a repository name already exists within the project."""

    def __init__(self) -> None:
        super().__init__(
            code="repository_already_exists",
            message="A repository with this name already exists in the project.",
            category=ErrorCategory.VALIDATION,
        )
