"""Helper for sanitizing and appending durable lifecycle events with sequences."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from backend.platform.analysis.domain.event import (
    FORBIDDEN_PAYLOAD_KEYS,
    AnalysisEvent,
    AnalysisEventType,
)
from backend.platform.analysis.repositories.event_repo import EventRepository


def sanitize_event_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Sanitize payload dictionary by stripping or redacting forbidden keys."""
    if not payload:
        return {}
    clean: dict[str, Any] = {}
    for k, v in payload.items():
        if k.lower() in FORBIDDEN_PAYLOAD_KEYS:
            continue
        if isinstance(v, dict):
            clean[k] = sanitize_event_payload(v)
        else:
            clean[k] = v
    return clean


class LifecycleEventEmitter:
    """Emits monotonically sequenced, sanitized AnalysisEvent records."""

    def __init__(
        self,
        event_repo: EventRepository,
        analysis_id: UUID,
    ) -> None:
        self._event_repo = event_repo
        self._analysis_id = analysis_id
        self._seq = event_repo.get_latest_sequence_number(analysis_id)

    def emit(
        self,
        event_type: AnalysisEventType,
        payload: dict[str, Any] | None = None,
        *,
        timestamp: datetime | None = None,
    ) -> AnalysisEvent:
        """Create, sanitize, persist, and return an AnalysisEvent."""
        self._seq += 1
        clean_payload = sanitize_event_payload(payload)
        now = timestamp or datetime.now(UTC)

        event = AnalysisEvent(
            id=uuid4(),
            analysis_id=self._analysis_id,
            sequence_number=self._seq,
            event_type=event_type,
            timestamp=now,
            payload=clean_payload,
        )
        self._event_repo.append(event)
        return event

    def emit_queued(self, job_id: UUID) -> AnalysisEvent:
        return self.emit(
            AnalysisEventType.ANALYSIS_QUEUED,
            {"job_id": str(job_id)},
        )

    def emit_started(self, job_id: UUID, worker_id: str | None = None) -> AnalysisEvent:
        payload: dict[str, Any] = {"job_id": str(job_id)}
        if worker_id:
            payload["worker_id"] = worker_id
        return self.emit(AnalysisEventType.ANALYSIS_STARTED, payload)

    def emit_stage_started(
        self, stage_name: str, stage_id: UUID, order: int
    ) -> AnalysisEvent:
        return self.emit(
            AnalysisEventType.ANALYSIS_STAGE_STARTED,
            {"stage_name": stage_name, "stage_id": str(stage_id), "order": order},
        )

    def emit_stage_progress(
        self,
        stage_name: str,
        stage_id: UUID,
        processed_items: int,
        total_items: int,
        message: str | None = None,
    ) -> AnalysisEvent:
        payload: dict[str, Any] = {
            "stage_name": stage_name,
            "stage_id": str(stage_id),
            "processed_items": processed_items,
            "total_items": total_items,
        }
        if message:
            payload["message"] = message
        return self.emit(AnalysisEventType.ANALYSIS_STAGE_PROGRESS, payload)

    def emit_stage_completed(
        self,
        stage_name: str,
        stage_id: UUID,
        processed_items: int,
        total_items: int,
    ) -> AnalysisEvent:
        return self.emit(
            AnalysisEventType.ANALYSIS_STAGE_COMPLETED,
            {
                "stage_name": stage_name,
                "stage_id": str(stage_id),
                "processed_items": processed_items,
                "total_items": total_items,
            },
        )

    def emit_stage_failed(
        self,
        stage_name: str,
        stage_id: UUID,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> AnalysisEvent:
        return self.emit(
            AnalysisEventType.ANALYSIS_STAGE_FAILED,
            {
                "stage_name": stage_name,
                "stage_id": str(stage_id),
                "error_code": error_code or "stage_failed",
                "error_message": error_message or "Stage execution failed.",
            },
        )

    def emit_stage_skipped(
        self, stage_name: str, stage_id: UUID, reason: str | None = None
    ) -> AnalysisEvent:
        return self.emit(
            AnalysisEventType.ANALYSIS_STAGE_SKIPPED,
            {
                "stage_name": stage_name,
                "stage_id": str(stage_id),
                "reason": reason or "Stage skipped.",
            },
        )

    def emit_completed(
        self,
        *,
        with_warnings: bool = False,
        summary: dict[str, Any] | None = None,
    ) -> AnalysisEvent:
        event_type = (
            AnalysisEventType.ANALYSIS_COMPLETED_WITH_WARNINGS
            if with_warnings
            else AnalysisEventType.ANALYSIS_COMPLETED
        )
        return self.emit(event_type, summary or {})

    def emit_failed(
        self,
        error_code: str,
        error_message: str,
    ) -> AnalysisEvent:
        return self.emit(
            AnalysisEventType.ANALYSIS_FAILED,
            {"error_code": error_code, "error_message": error_message},
        )

    def emit_cancelled(self, reason: str | None = None) -> AnalysisEvent:
        return self.emit(
            AnalysisEventType.ANALYSIS_CANCELLED,
            {"reason": reason or "Analysis execution cancelled."},
        )

    def emit_timeout(self, max_duration_seconds: int) -> AnalysisEvent:
        return self.emit(
            AnalysisEventType.ANALYSIS_TIMEOUT,
            {"max_duration_seconds": max_duration_seconds},
        )
