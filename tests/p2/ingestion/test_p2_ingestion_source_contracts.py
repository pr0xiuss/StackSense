"""Unit tests for M4 Source Acquisition domain contracts and DTO validation."""

from uuid import uuid4

import pytest

from backend.platform.config import Settings
from backend.platform.errors import (
    ErrorCategory,
    GitHubAcquisitionError,
    GitHubRepositoryNotFoundError,
    InvalidGitHubRefError,
    InvalidGitHubUrlError,
    InvalidSourceTypeError,
    ServerPathNotAllowedError,
    ServerPathNotFoundError,
    SourceValidationError,
    StackSenseError,
    UnsupportedArchiveFormatError,
)
from backend.platform.ingestion.application.dto import TriggerIngestionRequest
from backend.platform.ingestion.domain.constants import SourceType
from backend.platform.ingestion.domain.source import (
    normalize_source_type,
    validate_github_ref,
    validate_github_url,
)


def test_source_type_enum_values() -> None:
    """Verify canonical SourceType enum values."""
    assert SourceType.GITHUB == "github"
    assert SourceType.ARCHIVE == "archive"
    assert SourceType.SERVER_PATH == "server_path"


def test_normalize_source_type_aliases() -> None:
    """Verify legacy aliases and case-insensitive normalization."""
    assert normalize_source_type("github") == SourceType.GITHUB
    assert normalize_source_type("GITHUB") == SourceType.GITHUB
    assert normalize_source_type(SourceType.GITHUB) == SourceType.GITHUB

    assert normalize_source_type("archive") == SourceType.ARCHIVE
    assert normalize_source_type("zip") == SourceType.ARCHIVE
    assert normalize_source_type("ZIP") == SourceType.ARCHIVE

    assert normalize_source_type("server_path") == SourceType.SERVER_PATH
    assert normalize_source_type("directory") == SourceType.SERVER_PATH
    assert normalize_source_type("dir") == SourceType.SERVER_PATH
    assert normalize_source_type("local") == SourceType.SERVER_PATH


def test_normalize_source_type_invalid() -> None:
    """Verify unsupported source types are rejected with InvalidSourceTypeError."""
    with pytest.raises(InvalidSourceTypeError) as exc:
        normalize_source_type("gitlab")
    assert "Unsupported repository source type 'gitlab'" in str(exc.value)

    with pytest.raises(InvalidSourceTypeError):
        normalize_source_type("bitbucket")

    with pytest.raises(InvalidSourceTypeError):
        normalize_source_type("")

    with pytest.raises(InvalidSourceTypeError):
        normalize_source_type(123)  # type: ignore[arg-type]


def test_validate_github_url_valid() -> None:
    """Verify valid public GitHub repository URLs normalize properly."""
    assert (
        validate_github_url("https://github.com/octocat/Hello-World")
        == "https://github.com/octocat/Hello-World"
    )
    assert (
        validate_github_url("https://www.github.com/octocat/Hello-World")
        == "https://github.com/octocat/Hello-World"
    )
    assert (
        validate_github_url("https://github.com/my-org/my.repo.git")
        == "https://github.com/my-org/my.repo"
    )
    assert (
        validate_github_url("https://github.com/my-org/my-repo/")
        == "https://github.com/my-org/my-repo"
    )


def test_validate_github_url_invalid_schemes() -> None:
    """Verify non-HTTPS schemes are rejected."""
    with pytest.raises(InvalidGitHubUrlError):
        validate_github_url("http://github.com/user/repo")

    with pytest.raises(InvalidGitHubUrlError):
        validate_github_url("git://github.com/user/repo")

    with pytest.raises(InvalidGitHubUrlError):
        validate_github_url("file:///etc/passwd")


def test_validate_github_url_ssrf_and_host_restrictions() -> None:
    """Verify non-github.com hosts, localhost, and IP addresses are rejected."""
    with pytest.raises(InvalidGitHubUrlError):
        validate_github_url("https://gitlab.com/user/repo")

    with pytest.raises(InvalidGitHubUrlError):
        validate_github_url("https://localhost/user/repo")

    with pytest.raises(InvalidGitHubUrlError):
        validate_github_url("https://127.0.0.1/user/repo")

    with pytest.raises(InvalidGitHubUrlError):
        validate_github_url("https://169.254.169.254/user/repo")

    with pytest.raises(InvalidGitHubUrlError):
        validate_github_url("https://user:pass@github.com/user/repo")


def test_validate_github_url_invalid_syntax() -> None:
    """Verify query params, fragments, and invalid paths are rejected."""
    with pytest.raises(InvalidGitHubUrlError):
        validate_github_url("https://github.com/user/repo?query=1")

    with pytest.raises(InvalidGitHubUrlError):
        validate_github_url("https://github.com/user/repo#anchor")

    with pytest.raises(InvalidGitHubUrlError):
        validate_github_url("https://github.com/onlyuser")

    with pytest.raises(InvalidGitHubUrlError):
        validate_github_url("https://github.com/user/repo/extra/path")

    with pytest.raises(InvalidGitHubUrlError):
        validate_github_url("")


def test_validate_github_ref_valid() -> None:
    """Verify valid Git references pass unchanged."""
    assert validate_github_ref(None) is None
    assert validate_github_ref("") is None
    assert validate_github_ref("   ") is None
    assert validate_github_ref("main") == "main"
    assert validate_github_ref("v1.2.3") == "v1.2.3"
    assert validate_github_ref("feature/auth-login") == "feature/auth-login"
    assert validate_github_ref("release_2026.09") == "release_2026.09"
    assert validate_github_ref("7a3b8c9d1234567890abcdef") == "7a3b8c9d1234567890abcdef"


def test_validate_github_ref_invalid() -> None:
    """Verify traversal, command injection, and git-invalid characters are rejected."""
    # Path traversal
    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("../main")

    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("feature/../escape")

    # Command injection & shell metacharacters
    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("main; rm -rf /")

    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("main && echo 1")

    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("main`id`")

    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("main$USER")

    # Whitespace and control chars
    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("main branch")

    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("main\nbranch")

    # Git syntax violations
    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("/main")

    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("main/")

    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref(".main")

    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("main.")

    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("feature//branch")

    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("main.lock")

    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("foo@{1}")

    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("foo~1")

    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("foo^2")

    # Length limit
    with pytest.raises(InvalidGitHubRefError):
        validate_github_ref("a" * 256)


def test_trigger_ingestion_request_github() -> None:
    """Verify TriggerIngestionRequest for GitHub source type."""
    repo_id = uuid4()
    req = TriggerIngestionRequest(
        repository_id=repo_id,
        source_type="github",
        repository_url="https://github.com/octocat/Hello-World",
        ref="main",
        revision_identifier="v1.0.0",
    )
    assert req.repository_id == repo_id
    assert req.source_type == SourceType.GITHUB
    assert req.repository_url == "https://github.com/octocat/Hello-World"
    assert req.ref == "main"
    assert req.source_reference == "https://github.com/octocat/Hello-World@main"
    assert req.revision_identifier == "v1.0.0"


def test_trigger_ingestion_request_github_without_ref() -> None:
    """Verify TriggerIngestionRequest for GitHub without explicit ref."""
    req = TriggerIngestionRequest(
        source_type=SourceType.GITHUB,
        repository_url="https://github.com/octocat/Hello-World",
    )
    assert req.source_type == SourceType.GITHUB
    assert req.repository_url == "https://github.com/octocat/Hello-World"
    assert req.ref is None
    assert req.source_reference == "https://github.com/octocat/Hello-World"


def test_trigger_ingestion_request_archive_legacy_zip() -> None:
    """Verify backwards compatibility for legacy zip source type."""
    req = TriggerIngestionRequest(
        source_type="zip",
        source_reference="/path/to/archive.zip",
    )
    assert req.source_type == SourceType.ARCHIVE
    assert req.source_reference == "/path/to/archive.zip"


def test_trigger_ingestion_request_server_path_legacy_dir() -> None:
    """Verify backwards compatibility for legacy directory source type."""
    req = TriggerIngestionRequest(
        source_type="directory",
        source_reference="/var/stacksense/staged/repo.tar.gz",
    )
    assert req.source_type == SourceType.SERVER_PATH
    assert req.source_reference == "/var/stacksense/staged/repo.tar.gz"


def test_trigger_ingestion_request_unknown_type_rejected() -> None:
    """Verify unknown source_type is rejected with InvalidSourceTypeError."""
    with pytest.raises(InvalidSourceTypeError):
        TriggerIngestionRequest(
            source_type="svn",
            source_reference="/some/path",
        )


def test_trigger_ingestion_request_missing_required_reference() -> None:
    """Verify archive and server_path require non-empty source_reference."""
    with pytest.raises(SourceValidationError):
        TriggerIngestionRequest(
            source_type=SourceType.ARCHIVE,
            source_reference=None,
        )

    with pytest.raises(SourceValidationError):
        TriggerIngestionRequest(
            source_type=SourceType.SERVER_PATH,
            source_reference="   ",
        )


def test_domain_error_contracts() -> None:
    """Verify all new acquisition error types inherit properly with correct codes."""
    errors = [
        (InvalidSourceTypeError(), "invalid_source_type", ErrorCategory.VALIDATION),
        (InvalidGitHubUrlError(), "invalid_github_url", ErrorCategory.VALIDATION),
        (InvalidGitHubRefError(), "invalid_github_ref", ErrorCategory.VALIDATION),
        (
            GitHubRepositoryNotFoundError(),
            "github_repository_not_found",
            ErrorCategory.VALIDATION,
        ),
        (
            GitHubAcquisitionError(),
            "github_acquisition_failed",
            ErrorCategory.VALIDATION,
        ),
        (
            UnsupportedArchiveFormatError(),
            "unsupported_archive_format",
            ErrorCategory.VALIDATION,
        ),
        (
            ServerPathNotAllowedError(),
            "server_path_not_allowed",
            ErrorCategory.AUTHORIZATION,
        ),
        (
            ServerPathNotFoundError(),
            "server_path_not_found",
            ErrorCategory.VALIDATION,
        ),
    ]

    for err, expected_code, expected_category in errors:
        assert isinstance(err, StackSenseError)
        assert err.code == expected_code
        assert err.category == expected_category


def test_settings_allowed_source_roots() -> None:
    """Verify configuration settings for allowed source roots and timeout."""
    settings = Settings(
        allowed_source_roots="data/staged,/opt/custom_staged",
        github_acquisition_timeout_seconds=45,
    )
    assert settings.allowed_source_roots == [
        "data/staged",
        "/opt/custom_staged",
    ]
    assert settings.github_acquisition_timeout_seconds == 45
