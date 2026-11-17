"""Read-only cooperative execution and B1 publication-contract fixtures."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.platform.delivery.contracts import (
    DeliveryContractError,
    ExecutionStopped,
    StopReason,
    WorkExecutionContext,
    execution_control,
)
from backend.platform.delivery.publication import (
    PublicationContext,
    PublicationContractViolation,
    PublicationGuard,
)
from tests.p5.delivery.test_contracts import attempt, receipt


@pytest.mark.parametrize("reason", list(StopReason))
def test_stop_latches_without_changing_lifecycle_or_fence(reason: StopReason) -> None:
    current = [None]
    control = execution_control(lambda: current[0])
    owner = attempt()
    context = WorkExecutionContext(
        attempt=owner, deadline=datetime.now(UTC), control=control
    )
    assert not control.should_stop()
    current[0] = reason
    assert control.should_stop()
    current[0] = None
    with pytest.raises(ExecutionStopped) as error:
        control.checkpoint()
    assert error.value.reason == reason
    assert context.attempt == owner and owner.fence == 1
    assert not hasattr(control, "cancel") and not hasattr(control, "invalidate_fence")
    assert set(name for name in dir(control) if not name.startswith("_")) == {
        "checkpoint",
        "should_stop",
    }
    assert "control" not in context.model_dump()


@pytest.mark.parametrize("operation", ["commit", "rollback", "close"])
def test_caught_producer_violation_still_poisoned_fixture(operation: str) -> None:
    # Contract fixture only; B2 must prove an actual GuardedEnlistedSession
    # intercepts before SQLAlchemy lifecycle/events in real PostgreSQL.
    guard = PublicationGuard()
    calls = []

    def producer_lifecycle() -> None:
        guard.reject_producer_lifecycle()
        calls.append(operation)

    guard.require_healthy()
    with pytest.raises(PublicationContractViolation):
        producer_lifecycle()
    assert calls == []
    for _ in range(2):
        with pytest.raises(PublicationContractViolation):
            guard.require_healthy()


def test_publication_context_has_no_raw_transaction_and_rechecks_binding() -> None:
    candidate = receipt().prepared
    context = PublicationContext(
        transaction_id=uuid4(), attempt=candidate.attempt, deadline=datetime.now(UTC)
    )
    context.require_prepared(candidate)
    assert not any(
        name in PublicationContext.model_fields
        for name in ("session", "connection", "engine", "lease_token")
    )
    stale = PublicationContext(
        transaction_id=uuid4(), attempt=attempt(), deadline=datetime.now(UTC)
    )
    with pytest.raises(DeliveryContractError):
        stale.require_prepared(candidate)


def test_m1_clock_observation_stops_at_deadline_without_reviving() -> None:
    clock = [4.0]
    control = execution_control(
        lambda: StopReason.DEADLINE if clock[0] >= 5.0 else None
    )
    control.checkpoint()
    clock[0] = 5.0
    with pytest.raises(ExecutionStopped) as error:
        control.checkpoint()
    assert error.value.reason == StopReason.DEADLINE
    clock[0] = 0.0
    assert control.should_stop()
