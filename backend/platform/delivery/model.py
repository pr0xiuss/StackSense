"""Pure P5 lifecycle rules; no database claims, lease clocks or hidden defaults."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Literal
from uuid import UUID

from backend.platform.delivery.contracts import (
    AttemptIdentity,
    DeliveryContractError,
    DeliveryPolicy,
    RetryClass,
    VersionScope,
    WorkIdentity,
    bundle_fingerprint,
)


class Eligibility(StrEnum):
    WAITING = "WAITING_FOR_ANALYSIS"
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"


class WorkState(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AttemptState(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class CancellationCause(StrEnum):
    ADMINISTRATIVE_WITHDRAWAL = "ADMINISTRATIVE_WITHDRAWAL"
    POLICY_SUPERSEDED = "POLICY_SUPERSEDED"


@dataclass(frozen=True, slots=True)
class CancellationDecision:
    cause: CancellationCause
    actor_id: UUID
    operation_id: UUID
    expected_work_id: UUID
    expected_fence: int
    replacement_policy_id: UUID | None = None
    actor_type: Literal["operator", "system"] = "operator"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.cause, CancellationCause)
            or self.actor_type not in {"operator", "system"}
            or type(self.expected_fence) is not int
            or self.expected_fence < 0
            or not all(
                isinstance(value, UUID)
                for value in (self.actor_id, self.operation_id, self.expected_work_id)
            )
            or self.replacement_policy_id is not None
            and not isinstance(self.replacement_policy_id, UUID)
        ):
            raise DeliveryContractError("invalid internal cancellation decision")
        if (
            self.cause == CancellationCause.POLICY_SUPERSEDED
            and self.replacement_policy_id is None
        ):
            raise DeliveryContractError(
                "policy cancellation requires replacement identity"
            )


@dataclass(frozen=True, slots=True)
class DeliveryBundle:
    id: UUID
    scope: VersionScope
    policy: DeliveryPolicy
    eligibility: Eligibility

    def __post_init__(self) -> None:
        if not isinstance(self.eligibility, Eligibility):
            raise DeliveryContractError("invalid bundle eligibility")

    @property
    def fingerprint(self) -> str:
        return bundle_fingerprint(self.scope, self.policy)


@dataclass(frozen=True, slots=True)
class DerivedWork:
    identity: WorkIdentity
    state: WorkState = WorkState.PENDING
    fence: int = 0
    acquired_executions: int = 0
    retry_of_work_id: UUID | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.state, WorkState)
            or type(self.fence) is not int
            or type(self.acquired_executions) is not int
            or min(self.fence, self.acquired_executions) < 0
        ):
            raise DeliveryContractError("invalid work state/counters")


@dataclass(frozen=True, slots=True)
class WorkAttempt:
    identity: AttemptIdentity
    state: AttemptState = AttemptState.RUNNING

    def __post_init__(self) -> None:
        if not isinstance(self.state, AttemptState):
            raise DeliveryContractError("invalid attempt state")


def transition_work(work: DerivedWork, target: WorkState) -> DerivedWork:
    """Pure legal transition; claim/cancel use their explicit guards below."""
    allowed = {
        WorkState.PENDING: {WorkState.QUEUED},
        WorkState.QUEUED: set(),  # Successful claim alone creates RUNNING.
        WorkState.RUNNING: {WorkState.COMPLETED, WorkState.FAILED, WorkState.RETRYING},
        WorkState.RETRYING: {WorkState.QUEUED},
    }
    if target not in allowed.get(work.state, set()):
        raise DeliveryContractError("illegal delivery work transition")
    return replace(work, state=target)


def transition_attempt(attempt: WorkAttempt, target: AttemptState) -> WorkAttempt:
    if attempt.state != AttemptState.RUNNING or target not in {
        AttemptState.COMPLETED,
        AttemptState.FAILED,
        AttemptState.EXPIRED,
        AttemptState.CANCELLED,
    }:
        raise DeliveryContractError("illegal delivery attempt transition")
    return replace(attempt, state=target)


def claim_work(
    work: DerivedWork, identity: AttemptIdentity, *, max_executions: int
) -> tuple[DerivedWork, WorkAttempt]:
    """Validate a claim candidate. B2 must establish this atomically in SQL."""
    if (
        work.state != WorkState.QUEUED
        or identity.work != work.identity
        or type(max_executions) is not int
        or max_executions <= 0
        or work.acquired_executions >= max_executions
        or identity.ordinal != work.acquired_executions + 1
        or identity.fence != work.fence + 1
    ):
        raise DeliveryContractError("invalid delivery execution claim")
    return replace(
        work,
        state=WorkState.RUNNING,
        fence=identity.fence,
        acquired_executions=identity.ordinal,
    ), WorkAttempt(identity)


def cancel_work(
    work: DerivedWork, decision: CancellationDecision, *, ownership_invalidated: bool
) -> DerivedWork:
    """Only M1 calls after serialized authorization and epoch/lease invalidation.

    This pure rule is not authorization, a durable cancellation or an attempt edit.
    An expired attempt retains EXPIRED in the coordinator's separate history.
    """
    if (
        decision.expected_work_id != work.identity.work_id
        or decision.expected_fence != work.fence
        or work.state in {WorkState.COMPLETED, WorkState.FAILED, WorkState.CANCELLED}
        or not ownership_invalidated
    ):
        raise DeliveryContractError("invalid internal cancellation")
    return replace(work, state=WorkState.CANCELLED, fence=work.fence + 1)


def manual_successor(
    work: DerivedWork,
    *,
    new_work_id: UUID,
    actor_role: str,
    retry_class: RetryClass,
    current: bool,
    prerequisites_ready: bool,
    admission_allowed: bool,
) -> DerivedWork:
    """Pure same-input retry rule; locks/idempotency/audit are B2/B3 concerns."""
    if actor_role not in {"OWNER", "ADMIN"}:
        raise PermissionError("delivery retry requires OWNER or ADMIN")
    if (
        work.state != WorkState.FAILED
        or not current
        or new_work_id == work.identity.work_id
        or retry_class != RetryClass.TRANSIENT
        or not prerequisites_ready
        or not admission_allowed
    ):
        raise DeliveryContractError(
            "delivery retry requires eligible current failed work"
        )
    identity = WorkIdentity.model_validate(
        {
            **work.identity.model_dump(),
            "work_id": new_work_id,
            "run_number": work.identity.run_number + 1,
        }
    )
    return DerivedWork(identity, retry_of_work_id=work.identity.work_id)
