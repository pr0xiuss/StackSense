"""P5 fixed tasks; durable database state owns retries and publication."""

import logging
from typing import Any

from celery import signals
from pydantic import ValidationError

from backend.platform.config import get_settings
from backend.platform.delivery.contracts import (
    DeliveryContractError,
    DeliveryWorkPayload,
)
from backend.platform.delivery.dependencies import build_delivery_coordinator
from backend.platform.delivery.service import DeliveryCoordinator
from backend.platform.delivery_composition import get_output_handler_registry
from backend.platform.dependency_injection import get_database_engine
from backend.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _runtime() -> DeliveryCoordinator | None:
    return build_delivery_coordinator(
        get_database_engine(),
        get_settings(),
        celery_app,
        registry=get_output_handler_registry(),
    )


@celery_app.task(bind=True, name="stacksense.execute_delivery_work", max_retries=0)
def execute_delivery_work(task: Any, **kwargs: Any) -> dict[str, str]:
    try:
        payload = DeliveryWorkPayload.model_validate_json(
            __import__("json").dumps(kwargs)
        )
    except ValidationError, ValueError, TypeError:
        logger.warning("delivery_poison_payload_rejected")
        return {"state": "rejected"}  # Ack poison once; no unbounded requeue.
    runtime = _runtime()
    if runtime is None:
        return {"state": "handler_unavailable"}
    try:
        return {"state": runtime.execute(payload, str(task.request.hostname))}
    except DeliveryContractError:
        logger.warning("delivery_claim_rejected")
        return {"state": "rejected"}


@celery_app.task(bind=True, name="stacksense.reconcile_delivery", max_retries=0)
def reconcile_delivery(task: Any) -> dict[str, int]:
    runtime = _runtime()
    if runtime is None or not runtime.dispatch_enabled:
        return {"discovered": 0, "recovered": 0, "dispatched": 0}
    runtime.heartbeat(str(task.request.hostname), reconciliation=True)
    return runtime.reconcile()  # Persistence/infrastructure errors are not success.


@celery_app.task(bind=True, name="stacksense.delivery_runtime_heartbeat", max_retries=0)
def delivery_runtime_heartbeat(task: Any) -> dict[str, bool]:
    runtime = _runtime()
    if runtime is None:
        return {"ready": False}
    runtime.heartbeat(str(task.request.hostname))
    return {"ready": bool(runtime.registry.profiles)}


@signals.heartbeat_sent.connect(weak=False)
def record_process_heartbeat(sender: Any = None, **kwargs: Any) -> None:
    """Existing Celery worker heartbeat, not a task proving just one consumer."""
    try:
        runtime = _runtime()
        if runtime is not None:
            hostname = getattr(getattr(sender, "eventer", None), "hostname", None)
            if hostname:
                runtime.heartbeat(str(hostname))
    except Exception:
        logger.warning("delivery_worker_capability_unavailable")
