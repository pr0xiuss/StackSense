"""Source domain models, validation contracts, and normalization rules."""

import re
from urllib.parse import urlparse

from backend.platform.errors import (
    InvalidGitHubRefError,
    InvalidGitHubUrlError,
    InvalidSourceTypeError,
)
from backend.platform.ingestion.domain.constants import SourceType

# GitHub username/org: 1-39 chars, alphanumeric with single internal hyphens
# Repository name: 1-100 chars, alphanumeric, hyphens, underscores, dots
_GITHUB_PATH_PATTERN = re.compile(
    r"^/(?P<owner>[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38})"
    r"/(?P<repo>[a-zA-Z0-9_.-]{1,100}?)(?:\.git)?/?$"
)

# Prohibited characters in git refs: control chars, whitespace,
# path traversal, shell metachars
_PROHIBITED_REF_CHARS = set("~^:?*[\\];&|<>$`\"'!()`{}")


def normalize_source_type(source_type: str | SourceType) -> SourceType:
    """Normalize input source type to canonical SourceType enum.

    Translates supported legacy aliases ('zip', 'directory', etc.) to canonical values.
    Rejects any unsupported or unknown source types with InvalidSourceTypeError.
    """
    if isinstance(source_type, SourceType):
        return source_type

    if not isinstance(source_type, str):
        type_name = type(source_type).__name__
        raise InvalidSourceTypeError(
            f"Expected source_type string or SourceType, got {type_name}."
        )

    val = source_type.strip().lower()
    mapping: dict[str, SourceType] = {
        "github": SourceType.GITHUB,
        "archive": SourceType.ARCHIVE,
        "zip": SourceType.ARCHIVE,
        "server_path": SourceType.SERVER_PATH,
        "directory": SourceType.SERVER_PATH,
        "dir": SourceType.SERVER_PATH,
        "local": SourceType.SERVER_PATH,
    }
    if val not in mapping:
        raise InvalidSourceTypeError(
            f"Unsupported repository source type '{source_type}'. "
            f"Supported source types: github, archive, server_path."
        )
    return mapping[val]


def parse_github_url(url: str) -> tuple[str, str, str]:
    """Validate that a URL is a safe, well-formed public GitHub repository URL.

    Enforces HTTPS, restricts host to github.com / www.github.com, rejects IP addresses,
    credentials, ports, query params, fragments, and invalid path syntax.

    Returns:
        tuple of (canonical_url, owner, repo)
    """
    if not isinstance(url, str) or not url.strip():
        raise InvalidGitHubUrlError("GitHub repository URL must not be empty.")

    clean_url = url.strip()
    try:
        parsed = urlparse(clean_url)
    except Exception as exc:
        raise InvalidGitHubUrlError(f"Malformed URL: {exc}") from exc

    if parsed.scheme.lower() != "https":
        raise InvalidGitHubUrlError(
            f"GitHub repository URL must use HTTPS scheme, got '{parsed.scheme}'."
        )

    if parsed.username or parsed.password or "@" in parsed.netloc:
        raise InvalidGitHubUrlError(
            "GitHub repository URL must not contain embedded credentials."
        )

    hostname = (parsed.hostname or "").lower()
    if hostname not in ("github.com", "www.github.com"):
        raise InvalidGitHubUrlError(
            f"Only public github.com repositories are supported. "
            f"Host '{hostname}' is not allowed."
        )

    if parsed.port not in (None, 443):
        raise InvalidGitHubUrlError("Invalid port in GitHub repository URL.")

    if parsed.query or parsed.fragment:
        raise InvalidGitHubUrlError(
            "GitHub repository URL must not contain query parameters or fragments."
        )

    match = _GITHUB_PATH_PATTERN.match(parsed.path)
    if not match:
        raise InvalidGitHubUrlError(
            f"Invalid GitHub repository path: '{parsed.path}'. "
            "Expected format: 'https://github.com/<owner>/<repo>'."
        )

    owner = match.group("owner")
    repo = match.group("repo")

    if repo in (".", "..") or repo.endswith("."):
        raise InvalidGitHubUrlError(f"Invalid repository name: '{repo}'.")

    canonical_url = f"https://github.com/{owner}/{repo}"
    return canonical_url, owner, repo


def validate_github_url(url: str) -> str:
    """Validate that a URL is a safe, well-formed public GitHub repository URL.

    Enforces HTTPS, restricts host to github.com / www.github.com, rejects IP addresses,
    credentials, ports, query params, fragments, and invalid path syntax.

    Returns:
        Normalized canonical URL string: 'https://github.com/{owner}/{repo}'
    """
    canonical_url, _, _ = parse_github_url(url)
    return canonical_url


def validate_github_ref(ref: str | None) -> str | None:
    """Validate and normalize a Git reference (branch, tag, or commit hash).

    Enforces length limits, rejects path traversal, shell characters,
    and git-invalid syntax.

    Returns:
        Clean, validated ref string or None if ref was None or empty.
    """
    if ref is None:
        return None

    clean_ref = ref.strip()
    if not clean_ref:
        return None

    if len(clean_ref) > 255:
        raise InvalidGitHubRefError(
            f"GitHub ref exceeds maximum 255 characters (length: {len(clean_ref)})."
        )

    if ".." in clean_ref:
        raise InvalidGitHubRefError(
            f"Path traversal ('..') is not permitted in Git ref: '{clean_ref}'."
        )

    if any(ord(c) < 32 or ord(c) == 127 for c in clean_ref):
        raise InvalidGitHubRefError(
            f"Control characters are not permitted in Git ref: '{clean_ref}'."
        )

    if any(c.isspace() for c in clean_ref):
        raise InvalidGitHubRefError(
            f"Whitespace characters are not permitted in Git ref: '{clean_ref}'."
        )

    prohibited_found = set(clean_ref) & _PROHIBITED_REF_CHARS
    if prohibited_found:
        chars_str = ", ".join(repr(c) for c in sorted(prohibited_found))
        raise InvalidGitHubRefError(
            f"Prohibited characters {chars_str} detected in Git ref: '{clean_ref}'."
        )

    if clean_ref.startswith("/") or clean_ref.endswith("/"):
        raise InvalidGitHubRefError(
            f"Git ref cannot start or end with a slash: '{clean_ref}'."
        )

    if clean_ref.startswith(".") or clean_ref.endswith("."):
        raise InvalidGitHubRefError(
            f"Git ref cannot start or end with a dot: '{clean_ref}'."
        )

    if "//" in clean_ref:
        raise InvalidGitHubRefError(
            f"Git ref cannot contain consecutive slashes: '{clean_ref}'."
        )

    if clean_ref.endswith(".lock"):
        raise InvalidGitHubRefError(f"Git ref cannot end with '.lock': '{clean_ref}'.")

    if "@{" in clean_ref:
        raise InvalidGitHubRefError(f"Git ref cannot contain '@{{': '{clean_ref}'.")

    return clean_ref
