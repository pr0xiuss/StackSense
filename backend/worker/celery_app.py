"""Celery application configuration for StackSense background workers."""

from celery import Celery

from backend.platform.config import get_settings

settings = get_settings()

celery_app = Celery(
    "stacksense",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["backend.worker.tasks", "backend.worker.graph_tasks"],
)

beat_schedule = {
    "recover-analysis-jobs": {
        "task": "stacksense.recover_analysis_jobs",
        "schedule": settings.analysis_dispatch_recovery_interval_seconds,
    },
    "reconcile-graph-projections": {
        "task": "stacksense.reconcile_graph_projections",
        "schedule": settings.graph_reconciliation_interval_seconds,
        "options": {"queue": settings.graph_maintenance_queue_name},
    },
    "graph-runtime-heartbeat": {
        "task": "stacksense.graph_runtime_heartbeat",
        "schedule": settings.graph_heartbeat_interval_seconds,
        "kwargs": {"capability": "reconciliation_scheduling"},
        "options": {"queue": settings.graph_maintenance_queue_name},
    },
}
if settings.graph_projection_dispatch_enabled:
    beat_schedule["graph-execution-heartbeat"] = {
        "task": "stacksense.graph_runtime_heartbeat",
        "schedule": settings.graph_heartbeat_interval_seconds,
        "kwargs": {"capability": "projection_execution"},
        "options": {"queue": settings.graph_queue_name},
    }

celery_app.conf.update(
    task_default_queue=settings.analysis_queue_name,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=settings.analysis_worker_prefetch_multiplier,
    worker_concurrency=settings.analysis_worker_concurrency,
    worker_max_tasks_per_child=settings.analysis_worker_max_tasks_per_child,
    task_routes={
        "stacksense.execute_analysis": {"queue": settings.analysis_queue_name},
        "stacksense.recover_analysis_jobs": {"queue": settings.analysis_queue_name},
        "stacksense.reconcile_graph_projections": {
            "queue": settings.graph_maintenance_queue_name
        },
        "stacksense.graph_runtime_heartbeat": {
            "queue": settings.graph_maintenance_queue_name
        },
        "stacksense.cleanup_graph_generation": {
            "queue": settings.graph_maintenance_queue_name
        },
        "stacksense.execute_graph_projection": {"queue": settings.graph_queue_name},
    },
    beat_schedule=beat_schedule,
)
