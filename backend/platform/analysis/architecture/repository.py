"""Persistence ports and lifecycle records for immutable Architecture Models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from backend.platform.analysis.architecture.model import (
    ArchitectureConflict,
    ArchitectureDocument,
    ArchitectureEntity,
    ArchitectureEvidence,
    ArchitectureRelationship,
    ArchitectureUnresolvedRelationship,
    ValidatedArchitectureModel,
)


class ArchitectureVersionState(StrEnum):
    """Internal lifecycle for one durable Architecture Version."""

    BUILDING = "building"
    VALIDATING = "validating"
    VALIDATION_FAILED = "validation_failed"
    PUBLISHED = "published"


class ArchitecturePersistenceError(RuntimeError):
    """Base class for intentional Architecture Model persistence failures."""


class ArchitecturePersistenceIntegrityError(ArchitecturePersistenceError):
    """Raised when a retry conflicts with already durable immutable content."""


class ArchitectureVersionStateError(ArchitecturePersistenceError):
    """Raised when an operation violates the Architecture Version lifecycle."""


@dataclass(frozen=True)
class ArchitectureVersionRecord:
    """Safe immutable view of an Architecture Version header."""

    id: UUID
    analysis_id: UUID
    project_id: UUID
    repository_id: UUID
    snapshot_id: UUID
    sequence_number: int
    state: ArchitectureVersionState
    configuration_fingerprint: str
    analyzer_version: str
    ir_schema_version: str
    architecture_schema_version: str
    content_digest: str
    completeness: dict[str, object]
    source_diagnostic_ids: tuple[str, ...]
    entity_count: int
    relationship_count: int
    evidence_count: int
    unresolved_relationship_count: int
    conflict_count: int
    diagnostic_id: UUID | None
    failure_code: str | None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None


@dataclass(frozen=True)
class ArchitecturePage[T]:
    """One deterministic database-backed page from a published version."""

    items: tuple[T, ...]
    total: int


class ArchitecturePublicationRepository(ABC):
    """Unit-of-work port for durable Architecture Version publication.

    Transaction commits and rollbacks remain the application service's concern.
    Implementations must never expose non-published documents through public reads.
    """

    @abstractmethod
    def reserve_version(
        self, document: ArchitectureDocument
    ) -> ArchitectureVersionRecord:
        """Create or idempotently reuse the durable BUILDING header."""
        raise NotImplementedError

    @abstractmethod
    def mark_validating(
        self, version_id: UUID, analysis_id: UUID
    ) -> ArchitectureVersionRecord:
        """Move a BUILDING header to VALIDATING, idempotently."""
        raise NotImplementedError

    @abstractmethod
    def mark_validation_failed(
        self,
        version_id: UUID,
        analysis_id: UUID,
        *,
        diagnostic_id: UUID,
        failure_code: str,
    ) -> ArchitectureVersionRecord:
        """Finalize a deterministic validation failure without child rows."""
        raise NotImplementedError

    @abstractmethod
    def publish(
        self, validated: ValidatedArchitectureModel
    ) -> ArchitectureVersionRecord:
        """Persist all canonical rows and transition atomically to PUBLISHED."""
        raise NotImplementedError

    @abstractmethod
    def get_version(
        self, version_id: UUID, project_id: UUID
    ) -> ArchitectureVersionRecord | None:
        """Read a project-scoped header, including internal lifecycle states."""
        raise NotImplementedError

    @abstractmethod
    def get_published_for_analysis(
        self, analysis_id: UUID, project_id: UUID
    ) -> ArchitectureVersionRecord | None:
        """Read the published header for one analysis and project."""
        raise NotImplementedError

    @abstractmethod
    def load_published_document(
        self, version_id: UUID, project_id: UUID
    ) -> ArchitectureDocument | None:
        """Rehydrate only a complete, published, project-scoped document."""
        raise NotImplementedError

    @abstractmethod
    def list_published_entities(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        kind: str | None = None,
        status: str | None = None,
    ) -> ArchitecturePage[ArchitectureEntity]:
        raise NotImplementedError

    @abstractmethod
    def get_published_entity(
        self, version_id: UUID, entity_id: UUID, project_id: UUID
    ) -> ArchitectureEntity | None:
        raise NotImplementedError

    @abstractmethod
    def list_published_relationships(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        kind: str | None = None,
        status: str | None = None,
    ) -> ArchitecturePage[ArchitectureRelationship]:
        raise NotImplementedError

    @abstractmethod
    def list_published_evidence(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        entity_id: UUID | None = None,
    ) -> ArchitecturePage[ArchitectureEvidence]:
        raise NotImplementedError

    @abstractmethod
    def list_published_unresolved(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> ArchitecturePage[ArchitectureUnresolvedRelationship]:
        raise NotImplementedError

    @abstractmethod
    def list_published_conflicts(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> ArchitecturePage[ArchitectureConflict]:
        raise NotImplementedError


__all__ = [
    "ArchitecturePersistenceError",
    "ArchitecturePersistenceIntegrityError",
    "ArchitecturePage",
    "ArchitecturePublicationRepository",
    "ArchitectureVersionRecord",
    "ArchitectureVersionState",
    "ArchitectureVersionStateError",
]
