"""Event repository persistence contract."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.platform.analysis.domain.event import AnalysisEvent


class EventRepository(ABC):
    """Persistence contract for durable AnalysisEvent records."""

    @abstractmethod
    def append(self, event: AnalysisEvent) -> AnalysisEvent:
        """Append an event to the analysis event log."""
        raise NotImplementedError

    @abstractmethod
    def list_by_analysis(
        self,
        analysis_id: UUID,
        *,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> list[AnalysisEvent]:
        """List events for an analysis after the specified sequence number."""
        raise NotImplementedError

    @abstractmethod
    def get_latest_sequence_number(self, analysis_id: UUID) -> int:
        """Return the highest sequence number recorded for the analysis (0 if none)."""
        raise NotImplementedError
