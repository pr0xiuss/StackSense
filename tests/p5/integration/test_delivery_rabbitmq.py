"""Real routing/redelivery and production task execution in a worker process."""

import os
import subprocess
import sys
import time
from uuid import uuid4

import pytest
from celery import Celery
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.platform.delivery.persistence import DeliveryAttemptModel as Attempt
from backend.platform.delivery.persistence import DeliveryOutputModel as Output
from backend.platform.delivery.persistence import DeliveryWorkModel as Work
from backend.platform.delivery.queue import EXECUTE_TASK, CeleryDeliveryPublisher
from backend.platform.delivery.repository import SqlAlchemyDeliveryRepository
from tests.p5.delivery.test_rollout import coordinator
from tests.p5.integration.test_delivery_postgres import producer_table, scheduled


def test_real_unacknowledged_message_redelivered(delivery_engine):
    broker = os.environ.get("RABBITMQ_TEST_URL")
    if not broker:
        pytest.skip("RABBITMQ_TEST_URL required")
    _, _, _, payload, _ = scheduled(delivery_engine)
    name, app = "p5.test." + uuid4().hex, Celery("p5-transport", broker=broker)
    try:
        with app.connection_for_write() as connection:
            queue = connection.SimpleQueue(name)
            CeleryDeliveryPublisher(app, queue=name, timeout_seconds=2.0).publish(
                payload
            )
            message = queue.get(timeout=5)
            assert message.headers["task"] == EXECUTE_TASK
            assert message.payload[1] == payload.model_dump(mode="json")
            queue.close()  # Connection close before ACK.
        with app.connection_for_read() as connection:
            queue = connection.SimpleQueue(name)
            try:
                message = queue.get(timeout=5)
                assert message.payload[1] == payload.model_dump(mode="json")
                message.ack()
            finally:
                queue.close()
    finally:
        with app.connection_for_write() as connection:
            connection.channel().queue_delete(queue=name)
        app.close()


@pytest.mark.parametrize("crash_after_claim", [False, True])
def test_actual_worker_executes_production_task_and_duplicate_is_noop(
    delivery_engine, tmp_path, crash_after_claim
):
    broker = os.environ.get("RABBITMQ_TEST_URL")
    if not broker:
        pytest.skip("RABBITMQ_TEST_URL required")
    producer_table(delivery_engine)
    _, _, _, payload, _ = scheduled(delivery_engine)
    queue = "p5.worker.test." + uuid4().hex
    environment = {
        **os.environ,
        "P5_TEST_SCHEMA": delivery_engine.get_execution_options()[
            "schema_translate_map"
        ][None],
        "P5_TEST_QUEUE": queue,
    }
    app = Celery("p5-worker-test", broker=broker)
    if crash_after_claim:
        environment["P5_TEST_PAUSE_AFTER_CLAIM"] = "1"
    log_path = tmp_path / "worker.log"
    with log_path.open("w+") as log:
        worker = subprocess.Popen(
            [sys.executable, "-m", "tests.p5.integration.worker_fixture"],
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            runtime = coordinator(
                delivery_engine, queue=queue, workers=("test-worker@fixture",)
            )
            until = time.monotonic() + 20
            while time.monotonic() < until:
                assert worker.poll() is None, "fixture worker exited before readiness"
                with runtime.session() as session:
                    if runtime.fleet_ready(
                        session, payload_to_binding(payload, session)
                    ):
                        break
                time.sleep(0.1)
            else:
                pytest.fail("real worker did not advertise exact capability")
            publisher = CeleryDeliveryPublisher(app, queue=queue, timeout_seconds=2.0)
            publisher.publish(payload)
            if crash_after_claim:
                until = time.monotonic() + 20
                while time.monotonic() < until:
                    with Session(delivery_engine) as session:
                        if session.get(Work, payload.work_id).state == "RUNNING":
                            break
                    time.sleep(0.1)
                else:
                    pytest.fail("fixture execution never claimed")
                worker.kill()  # Only the exact test subprocess created above.
                worker.wait(timeout=5)
                with runtime.session() as session, session.begin():
                    from datetime import timedelta

                    now = SqlAlchemyDeliveryRepository(session).now()
                    session.execute(
                        update(Attempt)
                        .where(Attempt.work_id == payload.work_id)
                        .values(expires_at=now - timedelta(seconds=1))
                    )
                assert runtime.recover() == 1
                with runtime.session() as session, session.begin():
                    repo = SqlAlchemyDeliveryRepository(session)
                    session.get(Work, payload.work_id).next_eligible_at = repo.now()
                    session.flush()
                    successor, _ = repo.reserve(
                        payload.work_id,
                        payload.project_id,
                        reservation_seconds=1.0,
                        correlation_id="test:recovery",
                    )
                assert successor.dispatch_epoch != payload.dispatch_epoch
                environment.pop("P5_TEST_PAUSE_AFTER_CLAIM")
                worker = subprocess.Popen(
                    [sys.executable, "-m", "tests.p5.integration.worker_fixture"],
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                publisher.publish(successor)
            until = time.monotonic() + 20
            while time.monotonic() < until:
                with Session(delivery_engine) as session:
                    state = session.get(Work, payload.work_id).state
                    if state == "COMPLETED":
                        break
                time.sleep(0.1)
            assert state == "COMPLETED"
            publisher.publish(payload)
            time.sleep(0.5)
            with Session(delivery_engine) as session:
                assert session.scalar(select(func.count()).select_from(Attempt)) == (
                    2 if crash_after_claim else 1
                )
                assert session.scalar(select(func.count()).select_from(Output)) == 1
                if crash_after_claim:
                    assert set(session.scalars(select(Attempt.state))) == {
                        "EXPIRED",
                        "COMPLETED",
                    }
        finally:
            worker.terminate()
            try:
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=5)
            with app.connection_for_write() as connection:
                connection.channel().queue_delete(queue=queue)
            app.close()


def payload_to_binding(payload, session):
    import json

    from backend.platform.delivery.contracts import WorkIdentity

    return WorkIdentity.model_validate_json(
        json.dumps(session.get(Work, payload.work_id).identity)
    ).binding
