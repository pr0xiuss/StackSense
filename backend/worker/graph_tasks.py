"""P4 graph reconciliation task; projection execution belongs to M2."""

from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID, uuid4

from celery import Task
from sqlalchemy.orm import Session

from backend.platform.config import Settings, get_settings
from backend.platform.dependency_injection import get_database_engine
from backend.platform.graph.executor import ProjectionExecutor
from backend.platform.graph.lifecycle import GraphProjectionReconciler
from backend.platform.graph.neo4j import Neo4jInfrastructure
from backend.platform.graph.persistence import SqlAlchemyGraphProjectionRepository
from backend.platform.graph.projection_store import Neo4jProjectionStore
from backend.platform.graph.queue import (
    GRAPH_CLEANUP_TASK_NAME,
    GRAPH_EXECUTION_TASK_NAME,
    CeleryProjectionPublisher,
    ProjectionWorkPayload,
)
from backend.platform.graph.runtime import (
    PROJECTION_EXECUTION,
    RECONCILIATION_SCHEDULING,
    GraphRuntimeCapabilities,
)
from backend.platform.graph.source import SqlAlchemyPublishedArchitectureSource
from backend.platform.graph.verification import GraphVerifier
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


def get_task_projection_executor(
    settings: Settings | None = None,
) -> ProjectionExecutor:
    """Instantiate a production projection executor."""
    configured = settings or get_settings()
    infra = Neo4jInfrastructure(configured)
    store = Neo4jProjectionStore(infra.driver, configured)
    verifier = GraphVerifier(store=store)
    return ProjectionExecutor(
        settings=configured,
        store=store,
        verifier=verifier,
    )


@celery_app.task(
    bind=True,
    name=GRAPH_EXECUTION_TASK_NAME,
    max_retries=0,
)
def execute_graph_projection_task(
    task: Task,
    *,
    projection_id: str,
    attempt_id: str,
    project_id: str,
    architecture_version_id: str,
    generation_id: str,
    contract_version: str,
    correlation_id: str,
    executor: ProjectionExecutor | None = None,
) -> dict[str, object]:
    """Execute one bounded P4-W1 projection claim."""
    settings = get_settings()
    request = task.request
    worker_id = str(getattr(request, "hostname", "graph-worker"))

    payload = ProjectionWorkPayload(
        projection_id=UUID(projection_id),
        attempt_id=UUID(attempt_id),
        project_id=UUID(project_id),
        architecture_version_id=UUID(architecture_version_id),
        generation_id=UUID(generation_id),
        contract_version=contract_version,
        correlation_id=correlation_id,
    )

    actual_executor = executor or get_task_projection_executor(settings)
    result = actual_executor.execute(payload, worker_id=worker_id)

    safe_summary: dict[str, object] = {
        "status": result.status,
        "generation_id": str(result.generation_id) if result.generation_id else None,
        "disposition": result.disposition.value if result.disposition else None,
        "failure_code": result.failure_code,
        "transient": result.transient,
        "execution_duration_seconds": round(result.execution_duration_seconds, 4),
        "nodes_written": result.nodes_written,
        "relationships_written": result.relationships_written,
    }
    logger.info("Graph projection execution completed: %s", safe_summary)
    return safe_summary


@celery_app.task(
    bind=True,
    name=GRAPH_CLEANUP_TASK_NAME,
    max_retries=0,
)
def cleanup_graph_generation_task(
    task: Task,
    *,
    project_id: str,
    architecture_version_id: str,
    generation_id: str,
    force: bool = False,
    executor: ProjectionExecutor | None = None,
) -> dict[str, object]:
    """Evaluate and execute bounded cleanup for an eligible generation."""
    settings = get_settings()
    actual_executor = executor or get_task_projection_executor(settings)

    result = actual_executor.cleanup_generation(
        project_id=UUID(project_id),
        architecture_version_id=UUID(architecture_version_id),
        generation_id=UUID(generation_id),
        force=force,
    )

    safe_summary: dict[str, object] = {
        "eligible": result.eligible,
        "generation_id": str(result.generation_id),
        "reason": result.reason,
        "deleted_count": result.deleted_count,
    }
    logger.info("Graph generation cleanup completed: %s", safe_summary)
    return safe_summary


__all__ = [
    "cleanup_graph_generation_task",
    "execute_graph_projection_task",
    "get_task_projection_executor",
    "graph_projection_execution_ready",
    "graph_runtime_heartbeat_task",
    "reconcile_graph_projections_task",
]
