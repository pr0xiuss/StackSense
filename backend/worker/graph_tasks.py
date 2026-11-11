"""P4 graph reconciliation task; projection execution belongs to M2."""

from __future__ import annotations

import logging
from datetime import timedelta
from uuid import uuid4

from celery import Task
from sqlalchemy.orm import Session

from backend.platform.config import Settings, get_settings
from backend.platform.dependency_injection import get_database_engine
from backend.platform.graph.lifecycle import GraphProjectionReconciler
from backend.platform.graph.persistence import SqlAlchemyGraphProjectionRepository
from backend.platform.graph.queue import (
    GRAPH_EXECUTION_TASK_NAME,
    CeleryProjectionPublisher,
)
from backend.platform.graph.runtime import (
    PROJECTION_EXECUTION,
    RECONCILIATION_SCHEDULING,
    GraphRuntimeCapabilities,
)
from backend.platform.graph.source import SqlAlchemyPublishedArchitectureSource
from backend.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def graph_projection_execution_ready(
    session: Session, settings: Settings | None = None
) -> bool:
    """Require a fresh queue-worker heartbeat advertising the M2 executor."""
    configured = settings or get_settings()
    return bool(
        configured.graph_projection_dispatch_enabled
        and GraphRuntimeCapabilities(session).is_live(
            PROJECTION_EXECUTION,
            ttl=timedelta(seconds=configured.graph_capability_ttl_seconds),
        )
    )


@celery_app.task(bind=True, name="stacksense.graph_runtime_heartbeat")
def graph_runtime_heartbeat_task(task: Task, capability: str) -> dict[str, bool]:
    """Prove Beat delivery and graph-queue worker capabilities with an expiring row."""
    settings = get_settings()
    request = task.request
    worker_id = str(getattr(request, "hostname", "graph-worker"))
    app = task.app
    if capability == RECONCILIATION_SCHEDULING:
        ready = True
    elif capability == PROJECTION_EXECUTION:
        ready = bool(
            settings.graph_projection_dispatch_enabled
            and GRAPH_EXECUTION_TASK_NAME in app.tasks
        )
    else:
        raise ValueError("unsupported graph heartbeat capability")
    with Session(get_database_engine()) as session:
        GraphRuntimeCapabilities(session).record_worker_heartbeat(
            capability=capability,
            worker_id=worker_id,
            ready=ready,
        )
        session.commit()
    return {capability: ready}


@celery_app.task(name="stacksense.reconcile_graph_projections")
def reconcile_graph_projections_task() -> dict[str, int | bool]:
    """Discover canonical publications and recover existing durable intent."""
    settings = get_settings()
    correlation_id = f"graph-reconcile:{uuid4()}"
    engine = get_database_engine()
    with Session(engine) as session:
        reconciler = GraphProjectionReconciler(
            source=SqlAlchemyPublishedArchitectureSource(session),
            repository=SqlAlchemyGraphProjectionRepository(session),
            publisher=CeleryProjectionPublisher(queue_name=settings.graph_queue_name),
            checkpoint=session.commit,
            rollback=session.rollback,
            execution_ready=lambda: graph_projection_execution_ready(session, settings),
            page_size=settings.graph_reconciliation_page_size,
            recovery_batch_size=settings.graph_recovery_batch_size,
            dispatch_recovery_after=timedelta(
                seconds=settings.graph_dispatch_recovery_seconds
            ),
            retry_backoff=timedelta(seconds=settings.graph_retry_backoff_seconds),
        )
        summary = reconciler.reconcile(correlation_id=correlation_id)
    safe_summary = {
        "publications_scanned": summary.publications_scanned,
        "resources_created": summary.resources_created,
        "stale_resources": summary.stale_resources,
        "expired_leases_recovered": summary.expired_leases_recovered,
        "terminal_expired_attempts": summary.terminal_expired_attempts,
        "dispatch_candidates": summary.dispatch_candidates,
        "dispatched": summary.dispatched,
        "publish_failures": summary.publish_failures,
        "dispatch_enabled": summary.dispatch_enabled,
    }
    logger.info("Graph reconciliation completed: %s", safe_summary)
    return safe_summary


__all__ = [
    "graph_projection_execution_ready",
    "graph_runtime_heartbeat_task",
    "reconcile_graph_projections_task",
]
