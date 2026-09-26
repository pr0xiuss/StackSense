"""StackSense application error contracts."""

from enum import StrEnum
from typing import Any


class ErrorCategory(StrEnum):
    """Canonical high-level error categories."""

    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    INTERNAL = "internal"
    AUTHORIZATION = "authorization"
    AUTHENTICATION = "authentication"


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


class InvalidCredentialsError(StackSenseError):
    """Raised when email or password is invalid."""

    def __init__(self, message: str = "Invalid email or password.") -> None:
        super().__init__(
            code="invalid_credentials",
            message=message,
            category=ErrorCategory.AUTHENTICATION,
        )


class AuthenticationRequiredError(StackSenseError):
    """Raised when authentication credentials are required but missing."""

    def __init__(
        self, message: str = "Authentication credentials were not provided."
    ) -> None:
        super().__init__(
            code="authentication_required",
            message=message,
            category=ErrorCategory.AUTHENTICATION,
        )


class InvalidTokenError(StackSenseError):
    """Raised when an authentication token is malformed, invalid, or forged."""

    def __init__(self, message: str = "Authentication token is invalid.") -> None:
        super().__init__(
            code="invalid_token",
            message=message,
            category=ErrorCategory.AUTHENTICATION,
        )


class TokenExpiredError(StackSenseError):
    """Raised when an authentication token has expired."""

    def __init__(self, message: str = "Authentication token has expired.") -> None:
        super().__init__(
            code="token_expired",
            message=message,
            category=ErrorCategory.AUTHENTICATION,
        )


class UserInactiveError(StackSenseError):
    """Raised when an authenticated user account has been deactivated."""

    def __init__(self, message: str = "User account is inactive.") -> None:
        super().__init__(
            code="user_inactive",
            message=message,
            category=ErrorCategory.AUTHENTICATION,
        )


class PasswordPolicyError(StackSenseError):
    """Raised when a password violates length or complexity policy."""

    def __init__(
        self, message: str = "Password does not meet policy requirements."
    ) -> None:
        super().__init__(
            code="password_policy_violation",
            message=message,
            category=ErrorCategory.VALIDATION,
        )


class UserAlreadyExistsError(StackSenseError):
    """Raised when attempting to register an email address that already exists."""

    def __init__(
        self, message: str = "A user with this email address already exists."
    ) -> None:
        super().__init__(
            code="user_already_exists",
            message=message,
            category=ErrorCategory.VALIDATION,
        )
