"""Durable, expiring graph scheduler and worker capability evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform.graph.persistence import GraphRuntimeCapabilityModel

RECONCILIATION_SCHEDULING = "reconciliation_scheduling"
PROJECTION_EXECUTION = "projection_execution"


class GraphRuntimeCapabilities:
    """Record and query live capabilities without treating registration as liveness."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record_worker_heartbeat(
        self,
        *,
        capability: str,
        worker_id: str,
        ready: bool,
        now: datetime | None = None,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id must not be empty")
        observed_at = now or datetime.now(UTC)
        if capability not in {RECONCILIATION_SCHEDULING, PROJECTION_EXECUTION}:
            raise ValueError("unsupported graph runtime capability")
        self._session.merge(
            GraphRuntimeCapabilityModel(
                capability=capability,
                worker_id=worker_id,
                ready=ready,
                observed_at=observed_at,
            )
        )

    def is_live(
        self,
        capability: str,
        *,
        ttl: timedelta,
        now: datetime | None = None,
    ) -> bool:
        if ttl <= timedelta(0):
            raise ValueError("capability TTL must be positive")
        cutoff = (now or datetime.now(UTC)) - ttl
        return (
            self._session.scalar(
                select(GraphRuntimeCapabilityModel.capability)
                .where(
                    GraphRuntimeCapabilityModel.capability == capability,
                    GraphRuntimeCapabilityModel.ready.is_(True),
                    GraphRuntimeCapabilityModel.observed_at >= cutoff,
                )
                .limit(1)
            )
            is not None
        )


__all__ = [
    "GraphRuntimeCapabilities",
    "PROJECTION_EXECUTION",
    "RECONCILIATION_SCHEDULING",
]
