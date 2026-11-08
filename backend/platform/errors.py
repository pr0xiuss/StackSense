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


class UsernameAlreadyExistsError(StackSenseError):
    """Raised when attempting to register a username that already exists."""

    def __init__(
        self, message: str = "A user with this username already exists."
    ) -> None:
        super().__init__(
            code="username_already_exists",
            message=message,
            category=ErrorCategory.VALIDATION,
        )


class InvalidRefreshTokenError(StackSenseError):
    """Raised when a provided refresh token is malformed, unrecognized, or tampered."""

    def __init__(self, message: str = "Invalid refresh token.") -> None:
        super().__init__(
            code="invalid_refresh_token",
            message=message,
            category=ErrorCategory.AUTHENTICATION,
        )


class RefreshTokenExpiredError(StackSenseError):
    """Raised when an expired refresh token is presented for token refresh."""

    def __init__(self, message: str = "Refresh token has expired.") -> None:
        super().__init__(
            code="refresh_token_expired",
            message=message,
            category=ErrorCategory.AUTHENTICATION,
        )


class RefreshTokenRevokedError(StackSenseError):
    """Raised when a revoked refresh token is presented for token refresh."""

    def __init__(self, message: str = "Refresh token has been revoked.") -> None:
        super().__init__(
            code="refresh_token_revoked",
            message=message,
            category=ErrorCategory.AUTHENTICATION,
        )


class IngestionNotFoundError(StackSenseError):
    """Raised when an ingestion job does not exist."""

    def __init__(self, message: str = "Ingestion not found.") -> None:
        super().__init__(
            code="ingestion_not_found",
            message=message,
            category=ErrorCategory.VALIDATION,
        )


class ActiveIngestionExistsError(StackSenseError):
    """Raised when an active ingestion is already running for the repository."""

    def __init__(
        self,
        message: str = "An active ingestion is already running for this repository.",
    ) -> None:
        super().__init__(
            code="active_ingestion_exists",
            message=message,
            category=ErrorCategory.VALIDATION,
        )


class InvalidIngestionStateError(StackSenseError):
    """Raised when an invalid ingestion state transition is attempted."""

    def __init__(
        self,
        message: str = "Invalid ingestion state transition.",
    ) -> None:
        super().__init__(
            code="invalid_ingestion_state",
            message=message,
            category=ErrorCategory.VALIDATION,
        )


class SourceValidationError(StackSenseError):
    """Raised when repository source fails validation limits or checks."""

    def __init__(
        self,
        message: str = "Repository source validation failed.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="source_validation_failed",
            message=message,
            category=ErrorCategory.VALIDATION,
            details=details,
        )


class StorageOperationError(StackSenseError):
    """Raised when an external storage read/write/delete operation fails."""

    def __init__(self, message: str = "Storage operation failed.") -> None:
        super().__init__(
            code="storage_operation_failed",
            message=message,
            category=ErrorCategory.INTERNAL,
            severity=ErrorSeverity.ERROR,
        )


class RevisionAlreadyExistsError(StackSenseError):
    """Raised when a revision identifier already exists for the repository."""

    def __init__(
        self,
        message: str = (
            "A revision with this identifier already exists for this repository."
        ),
    ) -> None:
        super().__init__(
            code="revision_already_exists",
            message=message,
            category=ErrorCategory.VALIDATION,
        )


class InvalidSourceTypeError(StackSenseError):
    """Raised when an unsupported or invalid repository source type is provided."""

    def __init__(
        self,
        message: str = "Unsupported or invalid repository source type.",
    ) -> None:
        super().__init__(
            code="invalid_source_type",
            message=message,
            category=ErrorCategory.VALIDATION,
        )


class InvalidGitHubUrlError(StackSenseError):
    """Raised when a provided GitHub repository URL is malformed, invalid, or unsafe."""

    def __init__(
        self,
        message: str = "Invalid GitHub repository URL.",
    ) -> None:
        super().__init__(
            code="invalid_github_url",
            message=message,
            category=ErrorCategory.VALIDATION,
        )


class InvalidGitHubRefError(StackSenseError):
    """Raised when a provided GitHub ref contains invalid or unsafe characters."""

    def __init__(
        self,
        message: str = "Invalid GitHub ref (branch, tag, or commit).",
    ) -> None:
        super().__init__(
            code="invalid_github_ref",
            message=message,
            category=ErrorCategory.VALIDATION,
        )


class GitHubRepositoryNotFoundError(StackSenseError):
    """Raised when a public GitHub repository does not exist or is private."""

    def __init__(
        self,
        message: str = "Repository not found or access denied.",
    ) -> None:
        super().__init__(
            code="github_repository_not_found",
            message=message,
            category=ErrorCategory.VALIDATION,
        )


class GitHubAcquisitionError(StackSenseError):
    """Raised when acquiring a public GitHub repository fails.

    Occurs due to network failures, timeouts, or provider rejection.
    """

    def __init__(
        self,
        message: str = "Failed to acquire GitHub repository.",
    ) -> None:
        super().__init__(
            code="github_acquisition_failed",
            message=message,
            category=ErrorCategory.VALIDATION,
        )


class GitHubRateLimitExceededError(GitHubAcquisitionError):
    """Raised when GitHub API or codeload rate limits are exceeded."""

    def __init__(
        self,
        message: str = "Repository not found or access denied.",
    ) -> None:
        super().__init__(message=message)
        self.code = "github_rate_limit_exceeded"


class GitHubAccessDeniedError(GitHubAcquisitionError):
    """Raised when GitHub access is denied (private repository or forbidden)."""

    def __init__(
        self,
        message: str = "Repository not found or access denied.",
    ) -> None:
        super().__init__(message=message)
        self.code = "github_access_denied"
        self.category = ErrorCategory.AUTHORIZATION


class GitHubNetworkError(GitHubAcquisitionError):
    """Raised on network failures or connection drops during GitHub acquisition."""

    def __init__(
        self,
        message: str = "GitHub repository acquisition failed due to network error.",
    ) -> None:
        super().__init__(message=message)
        self.code = "github_network_error"


class GitHubTimeoutError(GitHubAcquisitionError):
    """Raised when GitHub acquisition times out (gateway timeout)."""

    def __init__(
        self,
        message: str = "GitHub repository download timed out.",
    ) -> None:
        super().__init__(message=message)
        self.code = "github_timeout"


class MaxFileCountExceededError(SourceValidationError):
    """Raised when repository archive exceeds maximum permitted file count."""

    def __init__(
        self,
        message: str = "Repository archive exceeds maximum permitted file count.",
    ) -> None:
        super().__init__(message=message)
        self.code = "max_file_count_exceeded"


class UnsupportedArchiveFormatError(SourceValidationError):
    """Raised when an archive has an unsupported format or extension."""

    def __init__(
        self,
        message: str = (
            "Unsupported archive format. Supported formats: .zip, .tar, .tar.gz, .tgz."
        ),
    ) -> None:
        super().__init__(message=message)
        self.code = "unsupported_archive_format"


class ServerPathNotAllowedError(StackSenseError):
    """Raised when a server filesystem path is outside the allowed source roots."""

    def __init__(
        self,
        message: str = "Server filesystem path is outside the allowed source roots.",
    ) -> None:
        super().__init__(
            code="server_path_not_allowed",
            message=message,
            category=ErrorCategory.AUTHORIZATION,
        )


ServerPathAccessDeniedError = ServerPathNotAllowedError


class ServerPathNotFoundError(StackSenseError):
    """Raised when a requested server filesystem path does not exist."""

    def __init__(
        self,
        message: str = "Server filesystem path not found.",
    ) -> None:
        super().__init__(
            code="server_path_not_found",
            message=message,
            category=ErrorCategory.VALIDATION,
        )


# --- Analysis Lifecycle and Execution Errors (Phase 3 Module 1) ---


class AnalysisError(StackSenseError):
    """Base exception for analysis execution and lifecycle failures."""

    def __init__(
        self,
        *,
        code: str = "analysis_error",
        message: str = "An analysis error occurred.",
        category: ErrorCategory = ErrorCategory.INTERNAL,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        scope: ErrorScope = ErrorScope.REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            category=category,
            severity=severity,
            scope=scope,
            details=details,
        )


class AnalysisNotFoundError(AnalysisError):
    """Raised when an analysis record does not exist or is not accessible."""

    def __init__(
        self,
        message: str = "Analysis not found in the specified project.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="analysis_not_found",
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.ERROR,
            details=details,
        )


class AnalysisAlreadyExistsError(AnalysisError):
    """Raised when an analysis with the same identifier already exists."""

    def __init__(
        self,
        message: str = (
            "An analysis with this identifier or idempotency key already exists."
        ),
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="analysis_already_exists",
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.ERROR,
            details=details,
        )


class AnalysisStateConflictError(AnalysisError):
    """Raised when an invalid state transition or concurrent state mutation occurs."""

    def __init__(
        self,
        message: str = "Invalid analysis state transition.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="analysis_state_conflict",
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.ERROR,
            details=details,
        )


class AnalysisInputError(AnalysisError):
    """Raised when analysis input data or prerequisites are missing or invalid."""

    def __init__(
        self,
        message: str = "Analysis input specification is invalid or incomplete.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="analysis_input_invalid",
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.ERROR,
            details=details,
        )


class AnalysisAccessDeniedError(AnalysisError):
    """Raised when delegated analysis access does not match request scope."""

    def __init__(
        self,
        message: str = "Delegated analysis access is not permitted.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="analysis_access_denied",
            message=message,
            category=ErrorCategory.AUTHORIZATION,
            details=details,
        )


class AnalysisQueueUnavailableError(AnalysisError):
    """Raised when a durable analysis cannot be dispatched to the worker queue."""

    def __init__(
        self,
        message: str = "Analysis was saved but could not be dispatched.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="analysis_queue_unavailable",
            message=message,
            category=ErrorCategory.INTERNAL,
            details=details,
        )


class AnalysisIntegrityError(AnalysisError):
    """Raised when ownership chain or snapshot verification fails."""

    def __init__(
        self,
        message: str = (
            "Analysis snapshot ownership chain or integrity verification failed."
        ),
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="analysis_integrity_violation",
            message=message,
            category=ErrorCategory.INTERNAL,
            severity=ErrorSeverity.CRITICAL,
            details=details,
        )


class AnalysisCancellationNotAllowedError(AnalysisError):
    """Raised when cancellation is requested for an uncancellable analysis."""

    def __init__(
        self,
        message: str = "Analysis cannot be cancelled in its current state.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="analysis_cancel_not_allowed",
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.ERROR,
            details=details,
        )


class AnalysisCancelledError(AnalysisError):
    """Raised during cooperative cancellation at an execution checkpoint."""

    def __init__(
        self,
        message: str = "Analysis execution was cancelled.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="analysis_cancelled",
            message=message,
            category=ErrorCategory.INTERNAL,
            severity=ErrorSeverity.WARNING,
            details=details,
        )


class AnalysisTimeoutError(AnalysisError):
    """Raised when analysis or stage execution duration exceeds configured limits."""

    def __init__(
        self,
        message: str = "Analysis execution exceeded duration limit.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="analysis_timeout",
            message=message,
            category=ErrorCategory.INTERNAL,
            severity=ErrorSeverity.ERROR,
            details=details,
        )


class ArtifactContentUnavailableError(AnalysisError):
    """Raised when required artifact content cannot be retrieved from storage."""

    def __init__(
        self,
        message: str = "Artifact content unavailable from storage.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="artifact_content_unavailable",
            message=message,
            category=ErrorCategory.INTERNAL,
            severity=ErrorSeverity.ERROR,
            details=details,
        )


class UnsupportedCapabilityError(AnalysisError):
    """Raised when a requested analysis capability is not supported."""

    def __init__(
        self,
        message: str = "Requested analysis capability is not supported.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="unsupported_capability",
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.ERROR,
            details=details,
        )


class AnalysisConfigurationError(AnalysisError):
    """Raised when analysis configuration parameters are invalid."""

    def __init__(
        self,
        message: str = "Analysis configuration is invalid.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="analysis_configuration_invalid",
            message=message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.ERROR,
            details=details,
        )


class ArchitectureResultNotFoundError(AnalysisError):
    """Raised when no published Architecture Model exists in project scope."""

    def __init__(
        self,
        message: str = "Published Architecture Model not found.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="architecture_result_not_found",
            message=message,
            category=ErrorCategory.VALIDATION,
            details=details,
        )
