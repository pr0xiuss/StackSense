"""Constants, resource limits, and classification enums for repository ingestion."""

from enum import StrEnum

# --- Section 7 Baseline Resource Limits ---
MAX_REPOSITORY_SIZE_BYTES: int = 500 * 1024 * 1024  # 500 MB (Section 7.4)
MAX_EXTRACTED_SIZE_BYTES: int = 1024 * 1024 * 1024  # 1 GB (Section 7.5)
MAX_INDIVIDUAL_FILE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB (Section 7.6)
MAX_REPOSITORY_FILE_COUNT: int = 50_000  # 50,000 files (Section 7.7)
MAX_DIRECTORY_DEPTH: int = 100  # 100 levels (Section 7.8)
MAX_PATH_LENGTH: int = 4096  # 4,096 characters (Section 7.9)
MAX_ARCHIVE_NESTING_DEPTH: int = 2  # 2 levels (Section 7.10)
MAX_COMPRESSION_RATIO: float = 100.0  # 100:1 ratio (Section 7.11)


class IngestionStatus(StrEnum):
    """Lifecycle states for an ingestion operation."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SupportLevel(StrEnum):
    """Canonical artifact support levels per master.txt Appendix G.4."""

    FULL = "full"
    PARTIAL = "partial"
    METADATA = "metadata"
    IGNORED = "ignored"
    UNSUPPORTED = "unsupported"


class ArtifactCategory(StrEnum):
    """Canonical artifact categories per master.txt Appendix G.3."""

    SOURCE_CODE = "source_code"
    MARKUP_UI = "markup_ui"
    CONFIGURATION = "configuration"
    DOCUMENTATION = "documentation"
    IMAGES = "images"
    ARCHITECTURE_ASSETS = "architecture_assets"
    INFRASTRUCTURE = "infrastructure"
    DATABASE_ARTIFACTS = "database_artifacts"
    DEPENDENCY_METADATA = "dependency_metadata"
    TESTS = "tests"
    GENERATED_ARTIFACTS = "generated_artifacts"
    BINARY_ARTIFACTS = "binary_artifacts"
    DATA_FILES = "data_files"
    ENVIRONMENT_SECRETS = "environment_secrets"
    BUILD_CACHE_ARTIFACTS = "build_cache_artifacts"
    UNKNOWN_UNSUPPORTED = "unknown_unsupported"
