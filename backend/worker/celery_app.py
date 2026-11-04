"""Celery application configuration for StackSense background workers."""

from celery import Celery

from backend.platform.config import get_settings

settings = get_settings()

celery_app = Celery(
    "stacksense",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["backend.worker.tasks"],
)

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
)
