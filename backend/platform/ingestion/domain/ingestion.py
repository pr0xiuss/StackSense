"""Ingestion domain entity."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from backend.platform.ingestion.domain.constants import IngestionStatus


@dataclass(frozen=True, slots=True)
class Ingestion:
    """Domain entity representing a repository source ingestion operation."""

    id: UUID
    project_id: UUID
    repository_id: UUID
    source_type: str
    source_reference: str
    status: IngestionStatus
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def can_transition_to(self, target: IngestionStatus) -> bool:
        """Evaluate whether transition to target status is valid."""
        allowed: dict[IngestionStatus, set[IngestionStatus]] = {
            IngestionStatus.PENDING: {
                IngestionStatus.PROCESSING,
                IngestionStatus.FAILED,
            },
            IngestionStatus.PROCESSING: {
                IngestionStatus.COMPLETED,
                IngestionStatus.FAILED,
            },
            IngestionStatus.COMPLETED: set(),
            IngestionStatus.FAILED: set(),
        }
        return target in allowed.get(self.status, set())
