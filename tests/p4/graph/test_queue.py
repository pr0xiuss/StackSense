"""Strict P4-W1 payload tests."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.platform.graph.queue import (
    GRAPH_EXECUTION_TASK_NAME,
    CeleryProjectionPublisher,
    ProjectionWorkPayload,
)


def _payload() -> dict[str, object]:
    return {
        "projection_id": str(uuid4()),
        "attempt_id": str(uuid4()),
        "project_id": str(uuid4()),
        "architecture_version_id": str(uuid4()),
        "generation_id": str(uuid4()),
        "contract_version": "1.0.0",
        "correlation_id": "correlation-1",
    }


def test_worker_payload_is_identifier_only_and_strict() -> None:
    parsed = ProjectionWorkPayload.model_validate(_payload())
    assert set(parsed.model_dump()) == {
        "projection_id",
        "attempt_id",
        "project_id",
        "architecture_version_id",
        "generation_id",
        "contract_version",
        "correlation_id",
    }


@pytest.mark.parametrize("field", tuple(_payload()))
def test_worker_payload_rejects_every_missing_field(field: str) -> None:
    payload = _payload()
    del payload[field]

    with pytest.raises(ValidationError):
        ProjectionWorkPayload.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [("contract_version", "2.0.0"), ("lease_token", "must-not-be-serialized")],
)
def test_worker_payload_rejects_unsupported_or_secret_fields(
    field: str, value: str
) -> None:
    payload = _payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        ProjectionWorkPayload.model_validate(payload)


def test_celery_publisher_routes_identifier_only_payload() -> None:
    class CeleryStub:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object], str]] = []

        def send_task(
            self, name: str, *, kwargs: dict[str, object], queue: str
        ) -> None:
            self.calls.append((name, kwargs, queue))

    celery = CeleryStub()
    payload = ProjectionWorkPayload.model_validate(_payload())

    CeleryProjectionPublisher(queue_name="graph.projections", celery=celery).publish(
        payload
    )

    assert celery.calls == [
        (
            GRAPH_EXECUTION_TASK_NAME,
            payload.model_dump(mode="json"),
            "graph.projections",
        )
    ]
    assert "lease_token" not in celery.calls[0][1]
