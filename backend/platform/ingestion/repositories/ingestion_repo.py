"""Ingestion persistence contract."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.platform.ingestion.domain.ingestion import Ingestion


class IngestionRepository(ABC):
    """Persistence contract for Ingestion operational records."""

    @abstractmethod
    def save(self, ingestion: Ingestion) -> Ingestion:
        """Persist a new ingestion operation and return the entity."""
        raise NotImplementedError

    @abstractmethod
    def update(self, ingestion: Ingestion) -> Ingestion:
        """Update an existing ingestion record."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, ingestion_id: UUID) -> Ingestion | None:
        """Retrieve an ingestion operation by identifier."""
        raise NotImplementedError

    @abstractmethod
    def list_by_repository(
        self,
        repository_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[Ingestion]:
        """List ingestion operations for a repository with pagination."""
        raise NotImplementedError
