"""Real existing Celery task/RabbitMQ -> M1 -> M4; isolated test queue only.

Uses the explicit rootless/application-store proof fixtures, not certified
production deployment. No new application queue, worker or producer fallback.
"""

# ruff: noqa: F811

import os
from time import monotonic, sleep
from uuid import uuid4

import pytest
from celery.app.trace import setup_worker_optimizations
from celery.contrib.testing.worker import TestWorkController, start_worker
from kombu import Exchange, Queue
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import BarrierReceipt, DiagramTemplate
from backend.platform.delivery.persistence import DeliveryBundleModel, DeliveryWorkModel
from backend.platform.delivery.queue import CeleryDeliveryPublisher
from backend.platform.delivery.registry import HandlerRegistration, WorkHandlerRegistry
from backend.platform.delivery.service import DeliveryCoordinator, FleetManifest
from backend.platform.diagrams.model import canonical_bytes
from backend.platform.diagrams.repository import DiagramPublicationPort
from backend.worker import delivery_tasks
from backend.worker.celery_app import celery_app
from tests.p5.delivery.test_rollout import budgets
from tests.p5.diagrams.test_c2_consumers import prepared
from tests.p5.diagrams.test_database import diagram_db  # noqa: F401
from tests.p5.diagrams.test_publication import lease_for
from tests.p5.integration.test_delivery_postgres import policy
from tests.p5.integration.test_diagram_pipeline import diagram_pipeline  # noqa: F401

pytestmark = pytest.mark.skipif(
    os.environ.get("M4_B1_ESSENTIAL_PROOFS") != "1",
    reason="opt-in real broker + pinned rootless runtime",
)


class BoundedWorker(TestWorkController):
    def __init__(self, *args, **kwargs):
        # Normal prefork worker children initialize tracing with their worker
        # name before consumer strategies are built; embedded solo does not.
        setup_worker_optimizations(kwargs["app"], hostname=kwargs["hostname"])
        super().__init__(*args, **kwargs)

    def ensure_started(self):
        if not self._on_started.wait(15):
            self.stop()
            raise RuntimeError("test Celery consumer did not become ready within 15s")


def test_actual_celery_identifier_payloads_publish_all_four_and_pin_report_barrier(
    diagram_db,
    diagram_pipeline,
    monkeypatch,
):
    engine, _, _ = diagram_db
    scope, _, make_handler = diagram_pipeline
    bindings = tuple(prepared(t).descriptor.reference.binding for t in DiagramTemplate)
    selected = policy().model_copy(
        update={
            "profiles": tuple(
                next((b for b in bindings if b.slot == p.slot), p)
                for p in policy().profiles
            )
        }
    )
    registry = WorkHandlerRegistry(
        tuple(
            HandlerRegistration(
                binding=b,
                handler=make_handler(b),
                publication_factory=DiagramPublicationPort,
            )
            for b in bindings
        )
    )
    queue = "m4-b3-proof-" + uuid4().hex
    hostname = queue + "@localhost"
    publisher = CeleryDeliveryPublisher(celery_app, queue=queue, timeout_seconds=1)

    def unavailable_reader():
        raise AssertionError(
            "execution does not discover or substitute source versions"
        )

    runtime = DeliveryCoordinator(
        engine=engine,
        registry=registry,
        publisher=publisher,
        policy=selected,
        budgets=budgets(),
        dispatch_enabled=True,
        fleet=FleetManifest(
            queue=queue,
            deployment_epoch="m4-b3-test",
            workers=(hostname,),
            admission_approved=True,
        ),
        reader=unavailable_reader,
    )
    monkeypatch.setattr(delivery_tasks, "_runtime", lambda: runtime)
    assert not celery_app.conf.task_always_eager
    celery_app.amqp.queues.add(
        Queue(
            queue,
            exchange=Exchange(queue, type="direct", durable=False, auto_delete=True),
            routing_key=queue,
            durable=False,
            auto_delete=True,
        )
    )
    responses = []
    original = runtime.execute

    def record(payload, worker_id):
        result = original(payload, worker_id)
        responses.append(
            {"state": result, "worker_id": worker_id, "expected": runtime.fleet.workers}
        )
        return result

    monkeypatch.setattr(runtime, "execute", record)
    with start_worker(
        celery_app,
        WorkController=BoundedWorker,
        hostname=hostname,
        pool="solo",
        concurrency=1,
        queues=(queue,),
        perform_ping_check=False,
        shutdown_timeout=30,
        loglevel="WARNING",
    ) as worker:
        hostname = str(worker.hostname)
        runtime.fleet = runtime.fleet.model_copy(update={"workers": (hostname,)})
        for template in DiagramTemplate:
            runtime.heartbeat(hostname)
            payload, _ = lease_for(engine, template, scope, claim=False)
            # C0 serializes identifiers only; no scope, artifact, paths or secrets.
            assert set(payload.model_dump()) == {
                "contract_version",
                "project_id",
                "bundle_id",
                "work_id",
                "dispatch_epoch",
                "architecture_version_id",
                "correlation_id",
            }
            publisher.publish(payload)
            until = monotonic() + 30
            while monotonic() < until:
                with Session(engine) as s:
                    row = s.get(DeliveryWorkModel, payload.work_id)
                    state, reason, bundle_id = row.state, row.safe_reason, row.bundle_id
                if state in ("COMPLETED", "FAILED", "CANCELLED"):
                    break
                sleep(0.05)
            assert state == "COMPLETED", (template, state, reason, responses)
    with Session(engine) as s:
        bundle = s.get(DeliveryBundleModel, bundle_id)
        barrier = BarrierReceipt.model_validate_json(canonical_bytes(bundle.barrier))
    assert {
        r.accepted.reference.binding.slot.template for r in barrier.diagrams
    } == set(DiagramTemplate)
