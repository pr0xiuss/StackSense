"""SQLAlchemy implementation of EventRepository."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.platform.analysis.domain.event import (
    AnalysisEvent,
    AnalysisEventType,
)
from backend.platform.analysis.infra.lifecycle_model import AnalysisEventModel
from backend.platform.analysis.repositories.event_repo import EventRepository


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class SqlAlchemyEventRepository(EventRepository):
    """PostgreSQL-backed implementation of EventRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: AnalysisEventModel) -> AnalysisEvent:
        timestamp = _ensure_utc(model.timestamp)
        assert timestamp is not None
        return AnalysisEvent(
            id=model.id,
            analysis_id=model.analysis_id,
            sequence_number=model.sequence_number,
            event_type=AnalysisEventType(model.event_type),
            timestamp=timestamp,
            payload=model.payload,
        )

    def append(self, event: AnalysisEvent) -> AnalysisEvent:
        """Append an event to the analysis event log."""
        model = AnalysisEventModel(
            id=event.id,
            analysis_id=event.analysis_id,
            sequence_number=event.sequence_number,
            event_type=event.event_type.value,
            timestamp=event.timestamp,
            payload=event.payload,
        )
        self._session.add(model)
        self._session.flush()
        return event

    def list_by_analysis(
        self,
        analysis_id: UUID,
        *,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> list[AnalysisEvent]:
        """List events for an analysis after the specified sequence number."""
        stmt = (
            select(AnalysisEventModel)
            .where(
                AnalysisEventModel.analysis_id == analysis_id,
                AnalysisEventModel.sequence_number > after_sequence,
            )
            .order_by(AnalysisEventModel.sequence_number)
            .limit(limit)
        )
        models = self._session.scalars(stmt).all()
        return [self._to_domain(m) for m in models]

    def get_latest_sequence_number(self, analysis_id: UUID) -> int:
        """Return the highest sequence number recorded for the analysis (0 if none)."""
        stmt = select(func.max(AnalysisEventModel.sequence_number)).where(
            AnalysisEventModel.analysis_id == analysis_id,
        )
        val = self._session.scalar(stmt)
        return val if val is not None else 0
