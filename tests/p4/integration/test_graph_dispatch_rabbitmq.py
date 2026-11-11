"""Real RabbitMQ routing evidence for the strict P4-W1 envelope."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from celery import Celery
from kombu.exceptions import OperationalError

from backend.platform.graph.model import WORKER_CONTRACT_VERSION
from backend.platform.graph.queue import (
    GRAPH_EXECUTION_TASK_NAME,
    CeleryProjectionPublisher,
    ProjectionWorkPayload,
)


def test_identifier_only_work_is_routed_to_dedicated_rabbitmq_queue() -> None:
    broker_url = os.getenv("RABBITMQ_TEST_URL")
    if not broker_url:
        pytest.skip("RABBITMQ_TEST_URL is required")
    queue_name = f"graph.projections.test.{uuid4()}"
    app = Celery("stacksense-p4-test", broker=broker_url)
    payload = ProjectionWorkPayload(
        projection_id=uuid4(),
        attempt_id=uuid4(),
        project_id=uuid4(),
        architecture_version_id=uuid4(),
        generation_id=uuid4(),
        contract_version=WORKER_CONTRACT_VERSION,
        correlation_id="rabbitmq-integration",
    )

    with app.connection_for_write() as connection:
        queue = connection.SimpleQueue(queue_name)
        try:
            CeleryProjectionPublisher(queue_name=queue_name, celery=app).publish(
                payload
            )
            message = queue.get(block=True, timeout=5)
            assert message.headers["task"] == GRAPH_EXECUTION_TASK_NAME
            body = message.payload
            assert isinstance(body, list)
            assert body[1] == payload.model_dump(mode="json")
            assert "lease_token" not in body[1]
            message.ack()
        finally:
            queue.close()
            channel = connection.channel()
            try:
                channel.queue_delete(queue=queue_name)
            finally:
                channel.close()
            app.close()


def test_rabbitmq_redelivers_unacknowledged_projection_work() -> None:
    broker_url = os.getenv("RABBITMQ_TEST_URL")
    if not broker_url:
        pytest.skip("RABBITMQ_TEST_URL is required")
    queue_name = f"graph.projections.redelivery.{uuid4()}"
    app = Celery("stacksense-p4-redelivery", broker=broker_url)
    payload = ProjectionWorkPayload(
        projection_id=uuid4(),
        attempt_id=uuid4(),
        project_id=uuid4(),
        architecture_version_id=uuid4(),
        generation_id=uuid4(),
        contract_version=WORKER_CONTRACT_VERSION,
        correlation_id="rabbitmq-redelivery",
    )

    with app.connection_for_write() as first_connection:
        first_queue = first_connection.SimpleQueue(queue_name)
        CeleryProjectionPublisher(queue_name=queue_name, celery=app).publish(payload)
        first_delivery = first_queue.get(block=True, timeout=5)
        assert first_delivery.payload[1]["attempt_id"] == str(payload.attempt_id)
        first_queue.close()

    with app.connection_for_read() as second_connection:
        second_queue = second_connection.SimpleQueue(queue_name)
        try:
            redelivery = second_queue.get(block=True, timeout=5)
            assert redelivery.payload[1] == payload.model_dump(mode="json")
            redelivery.ack()
        finally:
            second_queue.close()
            channel = second_connection.channel()
            try:
                channel.queue_delete(queue=queue_name)
            finally:
                channel.close()
    app.close()


def test_publisher_recovers_after_real_broker_connection_failure() -> None:
    broker_url = os.getenv("RABBITMQ_TEST_URL")
    if not broker_url:
        pytest.skip("RABBITMQ_TEST_URL is required")
    payload = ProjectionWorkPayload(
        projection_id=uuid4(),
        attempt_id=uuid4(),
        project_id=uuid4(),
        architecture_version_id=uuid4(),
        generation_id=uuid4(),
        contract_version=WORKER_CONTRACT_VERSION,
        correlation_id="rabbitmq-recovery",
    )
    unavailable = Celery(
        "stacksense-p4-unavailable",
        broker="amqp://guest:guest@127.0.0.1:1//",
    )
    unavailable.conf.update(
        broker_connection_timeout=0.2,
        task_publish_retry=False,
    )
    with pytest.raises(OperationalError):
        CeleryProjectionPublisher(
            queue_name="graph.projections.unavailable", celery=unavailable
        ).publish(payload)
    unavailable.close()

    queue_name = f"graph.projections.recovery.{uuid4()}"
    recovered = Celery("stacksense-p4-recovered", broker=broker_url)
    with recovered.connection_for_write() as connection:
        queue = connection.SimpleQueue(queue_name)
        try:
            CeleryProjectionPublisher(queue_name=queue_name, celery=recovered).publish(
                payload
            )
            message = queue.get(block=True, timeout=5)
            assert message.payload[1] == payload.model_dump(mode="json")
            message.ack()
        finally:
            queue.close()
            channel = connection.channel()
            try:
                channel.queue_delete(queue=queue_name)
            finally:
                channel.close()
    recovered.close()
