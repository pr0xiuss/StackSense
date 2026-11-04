"""AnalysisInput, AnalysisArtifact, and ArtifactCatalog contracts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO
from uuid import UUID

from backend.platform.analysis.domain.analysis import AnalysisConfiguration
from backend.platform.analysis.domain.constants import (
    ANALYZER_VERSION,
    ARCHITECTURE_SCHEMA_VERSION,
    IR_SCHEMA_VERSION,
)
from backend.platform.ingestion.domain.constants import ArtifactCategory, SupportLevel


@dataclass(frozen=True, slots=True)
class AnalysisArtifact:
    """Read-only view of a repository artifact within an analysis input.

    Note: storage keys and absolute filesystem paths are explicitly omitted to
    preserve encapsulation across the F1 execution boundary.
    """

    id: UUID
    revision_id: UUID
    path: str
    size_bytes: int
    content_hash: str
    category: ArtifactCategory
    support_level: SupportLevel


class ArtifactContentReader(ABC):
    """Abstract interface providing lazy, bounded content access for artifacts."""

    @abstractmethod
    def read_bytes(
        self,
        artifact: AnalysisArtifact,
        max_bytes: int | None = None,
    ) -> bytes:
        """Read content bytes for an artifact up to max_bytes.

        Raises ArtifactContentUnavailableError on storage/retrieval failures.
        """
        raise NotImplementedError

    @abstractmethod
    def open_stream(self, artifact: AnalysisArtifact) -> BinaryIO:
        """Open a readable binary stream for the artifact's content.

        Raises ArtifactContentUnavailableError on storage/retrieval failures.
        """
        raise NotImplementedError

    @abstractmethod
    def exists(self, artifact: AnalysisArtifact) -> bool:
        """Check whether the underlying artifact content is accessible in storage."""
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class ArtifactCatalog:
    """Catalog of discovered analysis artifacts with deterministic sorting."""

    artifacts: tuple[AnalysisArtifact, ...]

    def __post_init__(self) -> None:
        # Guarantee deterministic ordering by normalized path
        sorted_artifacts = tuple(sorted(self.artifacts, key=lambda a: a.path))
        object.__setattr__(self, "artifacts", sorted_artifacts)

    @property
    def total_files(self) -> int:
        """Total number of artifacts in catalog."""
        return len(self.artifacts)

    @property
    def total_bytes(self) -> int:
        """Total size in bytes of all artifacts in catalog."""
        return sum(a.size_bytes for a in self.artifacts)

    def get_by_path(self, path: str) -> AnalysisArtifact | None:
        """Find artifact by relative normalized path."""
        for artifact in self.artifacts:
            if artifact.path == path:
                return artifact
        return None

    def get_by_id(self, artifact_id: UUID) -> AnalysisArtifact | None:
        """Find artifact by identifier."""
        for artifact in self.artifacts:
            if artifact.id == artifact_id:
                return artifact
        return None

    def filter_by_category(
        self, category: ArtifactCategory
    ) -> tuple[AnalysisArtifact, ...]:
        """Filter artifacts matching the specified category."""
        return tuple(a for a in self.artifacts if a.category == category)

    def filter_by_support_level(
        self,
        support_level: SupportLevel,
    ) -> tuple[AnalysisArtifact, ...]:
        """Filter artifacts matching the specified support level."""
        return tuple(a for a in self.artifacts if a.support_level == support_level)

    def paths(self) -> tuple[str, ...]:
        """Return all artifact paths in deterministic order."""
        return tuple(a.path for a in self.artifacts)


@dataclass(frozen=True, slots=True)
class AnalysisInput:
    """Authoritative immutable input bundle for analysis execution."""

    analysis_id: UUID
    project_id: UUID
    repository_id: UUID
    snapshot_id: UUID  # Phase 2 RepositoryRevision.id
    revision_identifier: str
    source_hash: str
    total_files: int
    total_bytes: int
    effective_configuration: AnalysisConfiguration
    artifact_catalog: ArtifactCatalog
    content_reader: ArtifactContentReader
    analyzer_version: str = ANALYZER_VERSION
    ir_schema_version: str = IR_SCHEMA_VERSION
    architecture_schema_version: str = ARCHITECTURE_SCHEMA_VERSION
