"""Live graph scheduler and queue-worker capability tests."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.platform.graph.runtime import (
    PROJECTION_EXECUTION,
    RECONCILIATION_SCHEDULING,
    GraphRuntimeCapabilities,
)
from backend.platform.projects.infra.base import Base


def test_capability_requires_fresh_successful_worker_heartbeat() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    observed = datetime.now(UTC)
    with Session(engine) as session:
        runtime = GraphRuntimeCapabilities(session)
        runtime.record_worker_heartbeat(
            capability=RECONCILIATION_SCHEDULING,
            worker_id="graph-worker@host",
            ready=True,
            now=observed,
        )
        runtime.record_worker_heartbeat(
            capability=PROJECTION_EXECUTION,
            worker_id="graph-worker@host",
            ready=False,
            now=observed,
        )
        session.commit()

        assert runtime.is_live(
            RECONCILIATION_SCHEDULING,
            ttl=timedelta(seconds=60),
            now=observed + timedelta(seconds=59),
        )
        assert not runtime.is_live(
            PROJECTION_EXECUTION,
            ttl=timedelta(seconds=60),
            now=observed + timedelta(seconds=59),
        )
        assert not runtime.is_live(
            RECONCILIATION_SCHEDULING,
            ttl=timedelta(seconds=60),
            now=observed + timedelta(seconds=61),
        )

        runtime.record_worker_heartbeat(
            capability=PROJECTION_EXECUTION,
            worker_id="graph-worker@host",
            ready=True,
            now=observed + timedelta(seconds=62),
        )
        session.commit()
        assert runtime.is_live(
            PROJECTION_EXECUTION,
            ttl=timedelta(seconds=60),
            now=observed + timedelta(seconds=63),
        )
    engine.dispose()
