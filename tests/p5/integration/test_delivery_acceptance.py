"""Actual Celery delivery from public discovery through the report barrier.

Fixture artifacts prove coordination, not downstream diagram/PDF generation.
"""

import json
import os
import subprocess
import sys
import time
from datetime import timedelta
from uuid import uuid4

import pytest
from celery import Celery
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import VersionScope, WorkKind
from backend.platform.delivery.persistence import DeliveryAttemptModel as Attempt
from backend.platform.delivery.persistence import DeliveryBundleModel as Bundle
from backend.platform.delivery.persistence import DeliveryOutputModel as Output
from backend.platform.delivery.persistence import DeliveryWorkModel as Work
from backend.platform.delivery.queue import CeleryDeliveryPublisher
from tests.p5.delivery.test_barrier import complete_registry, payload_for
from tests.p5.delivery.test_rollout import coordinator
from tests.p5.integration.test_delivery_postgres import producer_table


def wait_for(predicate, worker, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        assert worker.poll() is None, "fixture worker exited"
        if predicate():
            return
        time.sleep(0.1)
    pytest.fail("fixture delivery condition did not become true")


@pytest.mark.parametrize(
    "crash_point", ["before_fourth_publish", "after_barrier_before_send"]
)
def test_source_four_ready_report_survives_worker_restart(
    delivery_engine, tmp_path, crash_point
):
    broker = os.environ.get("RABBITMQ_TEST_URL")
    if not broker:
        pytest.skip("RABBITMQ_TEST_URL required")
    table = producer_table(delivery_engine)
    queue = "p5.acceptance." + uuid4().hex
    app = Celery("p5-acceptance", broker=broker)
    publisher = CeleryDeliveryPublisher(app, queue=queue, timeout_seconds=2.0)
    runtime = coordinator(
        delivery_engine,
        registry=complete_registry(table),
        publisher=publisher,
        queue=queue,
        workers=("test-worker@fixture",),
    )
    assert runtime.discover() == 1
    with Session(delivery_engine) as session:
        bundle = session.scalar(select(Bundle))
        scope, bundle_id = (
            VersionScope.model_validate_json(json.dumps(bundle.scope)),
            bundle.id,
        )
    environment = {
        **os.environ,
        "P5_TEST_SCHEMA": delivery_engine.get_execution_options()[
            "schema_translate_map"
        ][None],
        "P5_TEST_QUEUE": queue,
        "P5_TEST_ALL_HANDLERS": "1",
    }
    if crash_point == "before_fourth_publish":
        environment["P5_TEST_PAUSE_DATA_FLOW"] = "1"

    def state(template, expected):
        with Session(delivery_engine) as session:
            return (
                session.scalar(
                    select(Work.state).where(
                        Work.bundle_id == bundle_id,
                        Work.template == template,
                        Work.is_current.is_(True),
                    )
                )
                == expected
            )

    with (tmp_path / "acceptance-worker.log").open("w+") as log:

        def start():
            return subprocess.Popen(
                [sys.executable, "-m", "tests.p5.integration.worker_fixture"],
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
            )

        worker = start()
        try:

            def ready():
                with runtime.session() as session:
                    return all(
                        runtime.fleet_ready(session, b)
                        for b in runtime.registry.profiles
                    )

            wait_for(ready, worker)
            for template in (
                "system_overview",
                "component_architecture",
                "dependency_map",
            ):
                publisher.publish(payload_for(runtime, scope, bundle_id, template))
                wait_for(lambda selected=template: state(selected, "COMPLETED"), worker)
            payload = payload_for(runtime, scope, bundle_id, "data_flow")
            publisher.publish(payload)
            wait_for(
                lambda: state(
                    "data_flow",
                    (
                        "RUNNING"
                        if crash_point == "before_fourth_publish"
                        else "COMPLETED"
                    ),
                ),
                worker,
            )
            worker.kill()
            worker.wait(timeout=5)
            if crash_point == "before_fourth_publish":
                with Session(delivery_engine) as session:
                    assert session.scalar(select(func.count()).select_from(Output)) == 3
                    assert session.get(Bundle, bundle_id).barrier is None
                with runtime.session() as session, session.begin():
                    session.execute(
                        update(Attempt)
                        .where(
                            Attempt.work_id == payload.work_id,
                            Attempt.state == "RUNNING",
                        )
                        .values(
                            expires_at=func.clock_timestamp() - timedelta(seconds=1)
                        )
                    )
                assert runtime.recover() == 1
                with runtime.session() as session, session.begin():
                    session.get(Work, payload.work_id).next_eligible_at = (
                        func.clock_timestamp()
                    )
                environment.pop("P5_TEST_PAUSE_DATA_FLOW")
            worker = start()
            wait_for(ready, worker)
            if crash_point == "before_fourth_publish":
                publisher.publish(payload_for(runtime, scope, bundle_id, "data_flow"))
                wait_for(lambda: state("data_flow", "COMPLETED"), worker)
            # Lost completion hints and restarted reconciliation cannot duplicate
            # report intent. No message was sent before its SQL acceptance.
            for _ in range(2):
                runtime.dependencies()
            with Session(delivery_engine) as session:
                assert (
                    session.scalar(
                        select(func.count())
                        .select_from(Work)
                        .where(Work.kind == WorkKind.REPORT)
                    )
                    == 1
                )
                report = session.scalar(
                    select(Work).where(Work.kind == WorkKind.REPORT)
                )
                assert report.state == "PENDING"
                assert session.get(Bundle, bundle_id).barrier is not None
            publisher.publish(
                payload_for(runtime, scope, bundle_id, "architecture_analysis")
            )
            wait_for(lambda: state("architecture_analysis", "COMPLETED"), worker)
            with Session(delivery_engine) as session:
                assert session.scalar(select(func.count()).select_from(Output)) == 5
        finally:
            if worker.poll() is None:
                worker.terminate()
                try:
                    worker.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    worker.wait(timeout=5)
            with app.connection_for_write() as connection:
                connection.channel().queue_delete(queue=queue)
            app.close()
