"""Domain unit tests for M4 Ingestion entities and limits."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import uuid4

import pytest

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
    SupportLevel,
)
from backend.platform.ingestion.domain.ingestion import Ingestion
from backend.platform.ingestion.domain.revision import RepositoryRevision


def test_section_7_resource_limits() -> None:
    """Verify Section 7 baseline resource limits are correctly defined."""
    assert MAX_REPOSITORY_SIZE_BYTES == 500 * 1024 * 1024
    assert MAX_EXTRACTED_SIZE_BYTES == 1024 * 1024 * 1024
    assert MAX_INDIVIDUAL_FILE_SIZE_BYTES == 5 * 1024 * 1024
    assert MAX_REPOSITORY_FILE_COUNT == 50_000
    assert MAX_DIRECTORY_DEPTH == 100
    assert MAX_PATH_LENGTH == 4096
    assert MAX_ARCHIVE_NESTING_DEPTH == 2
    assert MAX_COMPRESSION_RATIO == 100.0


def test_ingestion_status_enums() -> None:
    """Verify IngestionStatus enum values."""
    assert IngestionStatus.PENDING.value == "pending"
    assert IngestionStatus.PROCESSING.value == "processing"
    assert IngestionStatus.COMPLETED.value == "completed"
    assert IngestionStatus.FAILED.value == "failed"


def test_support_level_enums() -> None:
    """Verify SupportLevel enum matches Appendix G.4."""
    expected = {"full", "partial", "metadata", "ignored", "unsupported"}
    assert {s.value for s in SupportLevel} == expected


def test_artifact_category_enums() -> None:
    """Verify ArtifactCategory enum matches Appendix G.3."""
    expected = {
        "source_code",
        "markup_ui",
        "configuration",
        "documentation",
        "images",
        "architecture_assets",
        "infrastructure",
        "database_artifacts",
        "dependency_metadata",
        "tests",
        "generated_artifacts",
        "binary_artifacts",
        "data_files",
        "environment_secrets",
        "build_cache_artifacts",
        "unknown_unsupported",
    }
    assert {c.value for c in ArtifactCategory} == expected


def test_ingestion_lifecycle_transitions() -> None:
    """Verify valid and invalid state transitions for Ingestion."""
    now = datetime.now(UTC)
    ingestion = Ingestion(
        id=uuid4(),
        project_id=uuid4(),
        repository_id=uuid4(),
        source_type="archive",
        source_reference="s3://bucket/repo.zip",
        status=IngestionStatus.PENDING,
        error_code=None,
        error_message=None,
        started_at=None,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )

    # From PENDING: can transition to PROCESSING or FAILED
    assert ingestion.can_transition_to(IngestionStatus.PROCESSING) is True
    assert ingestion.can_transition_to(IngestionStatus.FAILED) is True
    assert ingestion.can_transition_to(IngestionStatus.COMPLETED) is False
    assert ingestion.can_transition_to(IngestionStatus.PENDING) is False

    # From PROCESSING: can transition to COMPLETED or FAILED
    processing = Ingestion(
        id=ingestion.id,
        project_id=ingestion.project_id,
        repository_id=ingestion.repository_id,
        source_type=ingestion.source_type,
        source_reference=ingestion.source_reference,
        status=IngestionStatus.PROCESSING,
        error_code=None,
        error_message=None,
        started_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )
    assert processing.can_transition_to(IngestionStatus.COMPLETED) is True
    assert processing.can_transition_to(IngestionStatus.FAILED) is True
    assert processing.can_transition_to(IngestionStatus.PENDING) is False
    assert processing.can_transition_to(IngestionStatus.PROCESSING) is False

    # Terminal state: COMPLETED cannot transition anywhere
    completed = Ingestion(
        id=ingestion.id,
        project_id=ingestion.project_id,
        repository_id=ingestion.repository_id,
        source_type=ingestion.source_type,
        source_reference=ingestion.source_reference,
        status=IngestionStatus.COMPLETED,
        error_code=None,
        error_message=None,
        started_at=now,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )
    assert completed.can_transition_to(IngestionStatus.PROCESSING) is False
    assert completed.can_transition_to(IngestionStatus.FAILED) is False
    assert completed.can_transition_to(IngestionStatus.PENDING) is False

    # Terminal state: FAILED cannot transition anywhere
    failed = Ingestion(
        id=ingestion.id,
        project_id=ingestion.project_id,
        repository_id=ingestion.repository_id,
        source_type=ingestion.source_type,
        source_reference=ingestion.source_reference,
        status=IngestionStatus.FAILED,
        error_code="ERR_EXTRACTION",
        error_message="Extraction failed",
        started_at=now,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )
    assert failed.can_transition_to(IngestionStatus.PENDING) is False
    assert failed.can_transition_to(IngestionStatus.PROCESSING) is False
    assert failed.can_transition_to(IngestionStatus.COMPLETED) is False


def test_ingestion_immutability() -> None:
    """Verify Ingestion entity is immutable."""
    now = datetime.now(UTC)
    ingestion = Ingestion(
        id=uuid4(),
        project_id=uuid4(),
        repository_id=uuid4(),
        source_type="archive",
        source_reference="s3://bucket/repo.zip",
        status=IngestionStatus.PENDING,
        error_code=None,
        error_message=None,
        started_at=None,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )
    with pytest.raises(FrozenInstanceError):
        ingestion.status = IngestionStatus.PROCESSING  # type: ignore[misc]


def test_repository_revision_domain_entity() -> None:
    """Verify RepositoryRevision creation and immutability."""
    now = datetime.now(UTC)
    rev_id = uuid4()
    proj_id = uuid4()
    repo_id = uuid4()
    ingest_id = uuid4()

    rev = RepositoryRevision(
        id=rev_id,
        project_id=proj_id,
        repository_id=repo_id,
        ingestion_id=ingest_id,
        revision_identifier="v1.0.0",
        source_hash="a" * 64,
        total_files=42,
        total_bytes=1048576,
        created_at=now,
    )

    assert rev.id == rev_id
    assert rev.project_id == proj_id
    assert rev.repository_id == repo_id
    assert rev.ingestion_id == ingest_id
    assert rev.revision_identifier == "v1.0.0"
    assert rev.source_hash == "a" * 64
    assert rev.total_files == 42
    assert rev.total_bytes == 1048576
    assert rev.created_at == now

    with pytest.raises(FrozenInstanceError):
        rev.total_files = 100  # type: ignore[misc]


def test_repository_artifact_domain_entity() -> None:
    """Verify RepositoryArtifact creation and immutability."""
    now = datetime.now(UTC)
    art_id = uuid4()
    proj_id = uuid4()
    repo_id = uuid4()
    rev_id = uuid4()

    artifact = RepositoryArtifact(
        id=art_id,
        project_id=proj_id,
        repository_id=repo_id,
        revision_id=rev_id,
        path="src/main.py",
        size_bytes=2048,
        content_hash="b" * 64,
        category=ArtifactCategory.SOURCE_CODE,
        support_level=SupportLevel.FULL,
        storage_key="content/bb/main.py",
        created_at=now,
    )

    assert artifact.id == art_id
    assert artifact.project_id == proj_id
    assert artifact.repository_id == repo_id
    assert artifact.revision_id == rev_id
    assert artifact.path == "src/main.py"
    assert artifact.size_bytes == 2048
    assert artifact.content_hash == "b" * 64
    assert artifact.category == ArtifactCategory.SOURCE_CODE
    assert artifact.support_level == SupportLevel.FULL
    assert artifact.storage_key == "content/bb/main.py"
    assert artifact.created_at == now

    with pytest.raises(FrozenInstanceError):
        artifact.size_bytes = 4096  # type: ignore[misc]
