"""Pure lifecycle tests are not substitutes for PostgreSQL fencing races."""

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from backend.platform.delivery.contracts import DeliveryContractError, RetryClass
from backend.platform.delivery.model import (
    AttemptState,
    CancellationCause,
    CancellationDecision,
    DerivedWork,
    WorkState,
    cancel_work,
    claim_work,
    manual_successor,
    transition_attempt,
    transition_work,
)
from tests.p5.delivery.test_contracts import attempt


def test_claim_counts_execution_only_and_redispatch_cannot_reclaim() -> None:
    owner = attempt()
    pending = DerivedWork(owner.work)
    queued = transition_work(pending, WorkState.QUEUED)
    assert queued.acquired_executions == 0
    running, acquired = claim_work(queued, owner, max_executions=2)
    assert running.acquired_executions == running.fence == 1
    assert acquired.state == AttemptState.RUNNING
    assert pending.state == WorkState.PENDING
    with pytest.raises(DeliveryContractError):
        claim_work(running, owner, max_executions=2)
    with pytest.raises(DeliveryContractError):
        claim_work(queued, owner, max_executions=0)
    with pytest.raises(FrozenInstanceError):
        running.fence = 5


@pytest.mark.parametrize(
    "terminal", [WorkState.COMPLETED, WorkState.FAILED, WorkState.CANCELLED]
)
@pytest.mark.parametrize("target", list(WorkState))
def test_terminal_work_never_reopens(terminal: WorkState, target: WorkState) -> None:
    with pytest.raises(DeliveryContractError):
        transition_work(DerivedWork(attempt().work, state=terminal), target)


@pytest.mark.parametrize(
    "terminal",
    [
        AttemptState.COMPLETED,
        AttemptState.FAILED,
        AttemptState.EXPIRED,
        AttemptState.CANCELLED,
    ],
)
def test_terminal_attempt_history_immutable(terminal: AttemptState) -> None:
    queued = DerivedWork(attempt().work, state=WorkState.QUEUED)
    owner = attempt().model_copy(update={"work": queued.identity})
    _, acquired = claim_work(queued, owner, max_executions=2)
    ended = transition_attempt(acquired, terminal)
    with pytest.raises(DeliveryContractError):
        transition_attempt(ended, AttemptState.CANCELLED)
    assert ended.state == terminal
    assert acquired.state == AttemptState.RUNNING


@pytest.mark.parametrize("state", list(WorkState))
def test_cancellation_matrix_needs_explicit_fence_invalidation(
    state: WorkState,
) -> None:
    work = DerivedWork(attempt().work, state=state)
    decision = CancellationDecision(
        CancellationCause.ADMINISTRATIVE_WITHDRAWAL,
        uuid4(),
        uuid4(),
        work.identity.work_id,
        0,
    )
    with pytest.raises(DeliveryContractError):
        cancel_work(work, decision, ownership_invalidated=False)
    if state in {WorkState.COMPLETED, WorkState.FAILED, WorkState.CANCELLED}:
        with pytest.raises(DeliveryContractError):
            cancel_work(work, decision, ownership_invalidated=True)
    else:
        cancelled = cancel_work(work, decision, ownership_invalidated=True)
        assert cancelled.fence == 1
        assert cancelled.state == WorkState.CANCELLED


def test_stale_cancellation_and_missing_policy_identity_rejected() -> None:
    work = DerivedWork(attempt().work)
    decision = CancellationDecision(
        CancellationCause.ADMINISTRATIVE_WITHDRAWAL, uuid4(), uuid4(), uuid4(), 0
    )
    with pytest.raises(DeliveryContractError):
        cancel_work(work, decision, ownership_invalidated=True)
    with pytest.raises(DeliveryContractError):
        CancellationDecision(
            CancellationCause.POLICY_SUPERSEDED,
            uuid4(),
            uuid4(),
            work.identity.work_id,
            0,
        )


@pytest.mark.parametrize("role", ["OWNER", "ADMIN", "DEVELOPER", "VIEWER"])
def test_successor_roles_terminal_history_and_pinned_inputs(role: str) -> None:
    failed = DerivedWork(
        attempt().work, state=WorkState.FAILED, fence=3, acquired_executions=3
    )
    args = dict(
        new_work_id=uuid4(),
        actor_role=role,
        retry_class=RetryClass.TRANSIENT,
        current=True,
        prerequisites_ready=True,
        admission_allowed=True,
    )
    if role not in {"OWNER", "ADMIN"}:
        with pytest.raises(PermissionError):
            manual_successor(failed, **args)
        return
    new = manual_successor(failed, **args)
    assert new.identity.input_fingerprint == failed.identity.input_fingerprint
    assert new.identity.binding == failed.identity.binding
    assert (
        new.identity.run_number == 2
        and new.identity.run_fingerprint() != failed.identity.run_fingerprint()
    )
    assert new.retry_of_work_id == failed.identity.work_id
    assert new.state == WorkState.PENDING and new.acquired_executions == new.fence == 0
    assert failed.state == WorkState.FAILED


@pytest.mark.parametrize(
    "field", ["current", "prerequisites_ready", "admission_allowed", "retry_class"]
)
def test_retry_cannot_bypass_integrity_prerequisite_or_admission(field: str) -> None:
    args = dict(
        new_work_id=uuid4(),
        actor_role="OWNER",
        retry_class=RetryClass.TRANSIENT,
        current=True,
        prerequisites_ready=True,
        admission_allowed=True,
    )
    args[field] = RetryClass.INTEGRITY if field == "retry_class" else False
    with pytest.raises(DeliveryContractError):
        manual_successor(DerivedWork(attempt().work, state=WorkState.FAILED), **args)
