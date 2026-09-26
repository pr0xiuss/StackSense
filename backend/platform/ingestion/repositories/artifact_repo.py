"""RepositoryArtifact persistence contract."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.platform.ingestion.domain.artifact import RepositoryArtifact


class ArtifactRepository(ABC):
    """Persistence contract for RepositoryArtifact records."""

    @abstractmethod
    def save_batch(self, artifacts: list[RepositoryArtifact]) -> None:
        """Persist a batch of artifact records."""
        raise NotImplementedError

    @abstractmethod
    def list_by_revision(
        self,
        revision_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[RepositoryArtifact]:
        """List artifacts belonging to a revision with deterministic pagination."""
        raise NotImplementedError
