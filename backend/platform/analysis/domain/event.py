"""Durable lifecycle event semantics and safe payload contract."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from backend.platform.errors import AnalysisIntegrityError

FORBIDDEN_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "storage_key",
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "source_code",
        "traceback",
        "stack_trace",
    }
)


class AnalysisEventType(StrEnum):
    """Canonical event types emitted throughout the analysis lifecycle."""

    ANALYSIS_CREATED = "analysis.created"
    ANALYSIS_QUEUED = "analysis.queued"
    ANALYSIS_STARTED = "analysis.started"
    ANALYSIS_STAGE_STARTED = "analysis.stage.started"
    ANALYSIS_STAGE_PROGRESS = "analysis.stage.progress"
    ANALYSIS_STAGE_COMPLETED = "analysis.stage.completed"
    ANALYSIS_STAGE_FAILED = "analysis.stage.failed"
    ANALYSIS_STAGE_SKIPPED = "analysis.stage.skipped"
    ANALYSIS_PARTIAL = "analysis.partial"
    ANALYSIS_CANCEL_REQUESTED = "analysis.cancel_requested"
    ANALYSIS_CANCELLED = "analysis.cancelled"
    ANALYSIS_TIMEOUT = "analysis.timeout"
    ANALYSIS_COMPLETED = "analysis.completed"
    ANALYSIS_COMPLETED_WITH_WARNINGS = "analysis.completed_with_warnings"
    ANALYSIS_FAILED = "analysis.failed"


@dataclass(frozen=True, slots=True)
class AnalysisEvent:
    """Immutable durable lifecycle event row for audit and SSE streaming."""

    id: UUID
    analysis_id: UUID
    sequence_number: int  # Monotonically increasing sequence starting at 1
    event_type: AnalysisEventType
    timestamp: datetime
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sequence_number < 1:
            raise AnalysisIntegrityError(
                message="Event sequence number must be positive (>= 1).",
                details={"sequence_number": self.sequence_number},
            )
        # Verify that payload contains no sensitive keys
        for key in self.payload:
            if key.lower() in FORBIDDEN_PAYLOAD_KEYS:
                raise AnalysisIntegrityError(
                    message=f"Event payload contains forbidden sensitive key '{key}'.",
                    details={"forbidden_key": key},
                )
