"""Ingestion domain models and contracts."""

from backend.platform.ingestion.domain.artifact import RepositoryArtifact
from backend.platform.ingestion.domain.constants import (
    MAX_ARCHIVE_NESTING_DEPTH,
    MAX_COMPRESSION_RATIO,
    MAX_DIRECTORY_DEPTH,
    MAX_EXTRACTED_SIZE_BYTES,
    MAX_INDIVIDUAL_FILE_SIZE_BYTES,
    MAX_PATH_LENGTH,
    MAX_REPOSITORY_FILE_COUNT,
    MAX_REPOSITORY_SIZE_BYTES,
    ArtifactCategory,
    IngestionStatus,
    SourceType,
    SupportLevel,
)
from backend.platform.ingestion.domain.ingestion import Ingestion
from backend.platform.ingestion.domain.revision import RepositoryRevision
from backend.platform.ingestion.domain.source import (
    normalize_source_type,
    parse_github_url,
    validate_github_ref,
    validate_github_url,
)

__all__ = [
    "MAX_ARCHIVE_NESTING_DEPTH",
    "MAX_COMPRESSION_RATIO",
    "MAX_DIRECTORY_DEPTH",
    "MAX_EXTRACTED_SIZE_BYTES",
    "MAX_INDIVIDUAL_FILE_SIZE_BYTES",
    "MAX_PATH_LENGTH",
    "MAX_REPOSITORY_FILE_COUNT",
    "MAX_REPOSITORY_SIZE_BYTES",
    "ArtifactCategory",
    "Ingestion",
    "IngestionStatus",
    "RepositoryArtifact",
    "RepositoryRevision",
    "SourceType",
    "SupportLevel",
    "normalize_source_type",
    "parse_github_url",
    "validate_github_ref",
    "validate_github_url",
]
