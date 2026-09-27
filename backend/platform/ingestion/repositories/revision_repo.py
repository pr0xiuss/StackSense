"""RepositoryRevision persistence contract."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.platform.ingestion.domain.revision import RepositoryRevision


class RevisionRepository(ABC):
    """Persistence contract for RepositoryRevision records."""

    @abstractmethod
    def save(self, revision: RepositoryRevision) -> RepositoryRevision:
        """Persist a new repository revision and return the entity."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, revision_id: UUID) -> RepositoryRevision | None:
        """Retrieve a revision by identifier."""
        raise NotImplementedError

    @abstractmethod
    def list_by_repository(
        self,
        repository_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[RepositoryRevision]:
        """List revisions for a repository with deterministic pagination."""
        raise NotImplementedError
