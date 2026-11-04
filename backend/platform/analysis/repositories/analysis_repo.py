"""Analysis repository persistence contract."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.platform.analysis.domain.analysis import Analysis
from backend.platform.analysis.domain.constants import AnalysisStatus


class AnalysisRepository(ABC):
    """Persistence contract for authoritative Analysis entities."""

    @abstractmethod
    def save(
        self,
        analysis: Analysis,
        *,
        idempotency_key: str | None = None,
    ) -> Analysis:
        """Persist a new analysis record."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, analysis_id: UUID, project_id: UUID) -> Analysis | None:
        """Retrieve an analysis by identifier within the owning project."""
        raise NotImplementedError

    @abstractmethod
    def get_by_idempotency_key(
        self,
        project_id: UUID,
        idempotency_key: str,
    ) -> Analysis | None:
        """Retrieve an analysis by idempotency key within project."""
        raise NotImplementedError

    @abstractmethod
    def update(self, analysis: Analysis, expected_version: int) -> Analysis:
        """Update an existing analysis using optimistic concurrency check.

        Raises AnalysisStateConflictError on version mismatch.
        """
        raise NotImplementedError

    @abstractmethod
    def list_by_project(
        self,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        status: AnalysisStatus | None = None,
    ) -> list[Analysis]:
        """List analyses for a project with deterministic pagination."""
        raise NotImplementedError

    @abstractmethod
    def count_by_project(
        self,
        project_id: UUID,
        status: AnalysisStatus | None = None,
    ) -> int:
        """Count analyses for a project with optional status filtering."""
        raise NotImplementedError
