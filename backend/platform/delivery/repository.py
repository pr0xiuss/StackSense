"""PostgreSQL coordination operations; caller owns every short transaction."""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.platform.delivery.api_contracts import (
    DeliveryApiError,
    ManualRetryPolicy,
    RetryAccepted,
    RetryRequest,
)
from backend.platform.delivery.contracts import (
    AttemptIdentity,
    BarrierReceipt,
    DeliveryContractError,
    DeliveryPolicy,
    DeliveryWorkPayload,
    DependencyReceipt,
    HandlerProfile,
    PublicationReceipt,
    VersionScope,
    WorkIdentity,
    WorkKind,
    bundle_fingerprint,
    fingerprint,
    work_fingerprint,
)
from backend.platform.delivery.model import CancellationDecision, Eligibility
from backend.platform.delivery.persistence import DeliveryAttemptModel as Attempt
from backend.platform.delivery.persistence import DeliveryBundleModel as Bundle
from backend.platform.delivery.persistence import DeliveryOutputModel as Output
from backend.platform.delivery.persistence import DeliveryRetryRequestModel as Retry
from backend.platform.delivery.persistence import DeliveryWorkModel as Work


@dataclass(frozen=True, slots=True)
class ExecutionLease:
    identity: AttemptIdentity
    worker_id: str
    deadline: datetime
    secret: str = field(repr=False)

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.secret.encode()).hexdigest()


class DeliveryOwnershipLost(DeliveryContractError):
    pass


class SqlAlchemyDeliveryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def now(self) -> datetime:
        return self.session.execute(select(func.clock_timestamp())).scalar_one()  # type: ignore[no-any-return]

    def lock_project_admission(self, project_id: UUID) -> None:
        # P5-only transaction advisory namespace; no platform table access.
        key = int.from_bytes(
            hashlib.sha256(b"p5-admission:" + project_id.bytes).digest()[:8],
            "big",
            signed=True,
        )
        self.session.execute(select(func.pg_advisory_xact_lock(key)))

    def ensure_bundle(
        self,
        scope: VersionScope,
        policy: DeliveryPolicy,
        eligibility: Eligibility,
        *,
        revisit_seconds: float,
        source_header: dict[str, object] | None = None,
        runtime_profile: dict[str, object] | None = None,
    ) -> UUID:
        self.lock_project_admission(scope.project_id)
        existing = tuple(
            self.session.scalars(
                select(Bundle)
                .where(
                    Bundle.project_id == scope.project_id,
                    Bundle.architecture_version_id == scope.architecture_version_id,
                )
                .order_by(Bundle.id)
                .with_for_update()
            )
        )
        if any(
            VersionScope.model_validate_json(json.dumps(row.scope)) != scope
            for row in existing
        ):
            raise DeliveryContractError("published version source changed")
        digest = bundle_fingerprint(scope, policy)
        now = self.now()
        statement = (
            insert(Bundle)
            .values(
                id=uuid4(),
                project_id=scope.project_id,
                architecture_version_id=scope.architecture_version_id,
                fingerprint=digest,
                scope=scope.model_dump(mode="json"),
                policy=policy.model_dump(mode="json"),
                eligibility=eligibility.value,
                eligibility_retry_at=now + timedelta(seconds=revisit_seconds),
                created_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    Bundle.project_id,
                    Bundle.architecture_version_id,
                    Bundle.fingerprint,
                ]
            )
        )
        self.session.execute(statement)
        bundle = self.session.scalars(
            select(Bundle)
            .where(
                Bundle.project_id == scope.project_id,
                Bundle.architecture_version_id == scope.architecture_version_id,
                Bundle.fingerprint == digest,
            )
            .with_for_update()
        ).one()
        if (
            VersionScope.model_validate_json(json.dumps(bundle.scope)) != scope
            or DeliveryPolicy.model_validate_json(json.dumps(bundle.policy)) != policy
        ):
            raise DeliveryContractError("immutable delivery bundle mismatch")
        if runtime_profile is not None:
            if (
                fingerprint("delivery.runtime", runtime_profile)
                != policy.execution_policy_fingerprint
            ):
                raise DeliveryContractError("runtime profile fingerprint mismatch")
            if (
                bundle.runtime_profile is not None
                and bundle.runtime_profile != runtime_profile
            ):
                raise DeliveryContractError("immutable runtime profile mismatch")
            bundle.runtime_profile = runtime_profile
        if source_header is not None:
            if (
                bundle.source_header is not None
                and bundle.source_header != source_header
            ):
                raise DeliveryContractError("immutable source header mismatch")
            bundle.source_header = source_header
        bundle.eligibility = eligibility.value
        bundle.eligibility_error = None
        bundle.eligibility_retry_at = now + timedelta(seconds=revisit_seconds)
        if eligibility == Eligibility.ELIGIBLE:
            for binding in policy.profiles:
                if binding.slot.kind == WorkKind.REPORT:
                    continue
                identity = WorkIdentity(
                    scope=scope,
                    bundle_id=bundle.id,
                    work_id=uuid4(),
                    run_number=1,
                    binding=binding,
                    bundle_fingerprint=digest,
                    input_fingerprint=work_fingerprint(digest, binding),
                )
                self.session.execute(
                    insert(Work)
                    .values(
                        id=identity.work_id,
                        bundle_id=bundle.id,
                        identity=identity.model_dump(mode="json"),
                        kind=binding.slot.kind.value,
                        template=binding.slot.template or "",
                        run_number=1,
                        is_current=True,
                        dependencies_ready=binding.slot.kind != WorkKind.DIAGRAM
                        or binding.slot.template == "system_overview",
                        state="PENDING",
                        fence=0,
                        executions=0,
                        dispatch_epoch=uuid4(),
                        next_eligible_at=now,
                        safe_reason=(
                            "waiting_on_overview"
                            if binding.slot.kind == WorkKind.DIAGRAM
                            and binding.slot.template != "system_overview"
                            else "handler_unavailable"
                        ),
                        created_at=now,
                    )
                    .on_conflict_do_nothing(
                        index_elements=[
                            Work.bundle_id,
                            Work.kind,
                            Work.template,
                            Work.run_number,
                        ]
                    )
                )
        self.session.flush()
        return bundle.id

    def lock_work(
        self, work_id: UUID, project_id: UUID, *, all_current: bool = False
    ) -> tuple[Bundle, Work]:
        bundle_id = self.session.scalar(
            select(Work.bundle_id)
            .join(Bundle, Bundle.id == Work.bundle_id)
            .where(Work.id == work_id, Bundle.project_id == project_id)
        )
        if bundle_id is None:
            raise DeliveryOwnershipLost("delivery work unavailable")
        bundle = self.session.scalars(
            select(Bundle)
            .where(Bundle.id == bundle_id, Bundle.project_id == project_id)
            .with_for_update()
        ).one()
        if all_current:
            participating = tuple(
                self.session.scalars(
                    select(Work)
                    .where(Work.bundle_id == bundle.id, Work.is_current.is_(True))
                    .order_by(Work.id)
                    .with_for_update()
                )
            )
            work = next((row for row in participating if row.id == work_id), None)
            if work is None:
                raise DeliveryOwnershipLost("delivery run superseded")
        else:
            work = self.session.scalars(
                select(Work)
                .where(Work.id == work_id, Work.bundle_id == bundle.id)
                .with_for_update()
            ).one()
        self.require_work(bundle, work)
        return bundle, work

    @staticmethod
    def require_work(bundle: Bundle, work: Work) -> WorkIdentity:
        """Authoritative columns and JSON must agree before dispatch/claim/use."""
        scope = VersionScope.model_validate_json(json.dumps(bundle.scope))
        policy = DeliveryPolicy.model_validate_json(json.dumps(bundle.policy))
        identity = WorkIdentity.model_validate_json(json.dumps(work.identity))
        expected_input = work_fingerprint(bundle.fingerprint, identity.binding)
        if identity.binding.slot.kind == WorkKind.REPORT:
            if bundle.barrier is None:
                raise DeliveryContractError("report missing pinned barrier")
            barrier = BarrierReceipt.model_validate_json(json.dumps(bundle.barrier))
            barrier.require_policy(policy, bundle.id)
            expected_input = barrier.input_fingerprint()
        if (
            identity.scope != scope
            or identity.bundle_id != bundle.id
            or identity.work_id != work.id
            or identity.run_number != work.run_number
            or bundle.project_id != scope.project_id
            or bundle.architecture_version_id != scope.architecture_version_id
            or bundle.fingerprint != bundle_fingerprint(scope, policy)
            or identity.bundle_fingerprint != bundle.fingerprint
            or identity.binding not in policy.profiles
            or identity.binding.slot.kind != work.kind
            or (identity.binding.slot.template or "") != work.template
            or identity.input_fingerprint != expected_input
        ):
            raise DeliveryContractError(
                "durable work scope/profile/fingerprint mismatch"
            )
        return identity

    def coordinate_dependencies(
        self,
        bundle_id: UUID,
        validate: Callable[[PublicationReceipt], None],
        *,
        tentative: PublicationReceipt | None = None,
    ) -> None:
        """Bundle -> current works -> producer readiness, on M1's transaction."""
        bundle = self.session.scalars(
            select(Bundle).where(Bundle.id == bundle_id).with_for_update()
        ).one()
        if bundle.eligibility != Eligibility.ELIGIBLE:
            return
        works = tuple(
            self.session.scalars(
                select(Work)
                .where(Work.bundle_id == bundle_id, Work.is_current.is_(True))
                .order_by(Work.id)
                .with_for_update()
            )
        )
        scope = VersionScope.model_validate_json(json.dumps(bundle.scope))
        policy = DeliveryPolicy.model_validate_json(json.dumps(bundle.policy))
        by_template = {
            row.template: row for row in works if row.kind == WorkKind.DIAGRAM
        }
        receipts: dict[str, PublicationReceipt] = {}
        for template, row in by_template.items():
            identity = WorkIdentity.model_validate_json(json.dumps(row.identity))
            if (
                identity.scope != scope
                or identity.bundle_id != bundle_id
                or identity.bundle_fingerprint != bundle.fingerprint
                or identity.binding not in policy.profiles
                or identity.input_fingerprint
                != work_fingerprint(bundle.fingerprint, identity.binding)
            ):
                raise DeliveryContractError("diagram work policy/scope mismatch")
            if (
                tentative is not None
                and tentative.prepared.attempt.work.work_id == row.id
            ):
                receipt = tentative
                if row.state != "RUNNING":
                    raise DeliveryContractError("tentative completion is not running")
            elif row.state == "COMPLETED":
                stored = self.session.scalar(
                    select(Output).where(Output.work_id == row.id)
                )
                if stored is None:
                    raise DeliveryContractError("completed work missing receipt")
                receipt = PublicationReceipt.model_validate_json(
                    json.dumps(stored.receipt)
                )
                attempt = self.session.get(Attempt, stored.attempt_id)
                if (
                    attempt is None
                    or attempt.state != "COMPLETED"
                    or stored.id != receipt.receipt_id
                    or stored.fence != row.fence
                    or receipt.prepared.attempt.fence != row.fence
                    or receipt.prepared.attempt.attempt_id != stored.attempt_id
                    or attempt.identity
                    != receipt.prepared.attempt.model_dump(mode="json")
                ):
                    raise DeliveryContractError("receipt completion integrity mismatch")
            else:
                continue
            if receipt.prepared.attempt.work != identity:
                raise DeliveryContractError("receipt work binding mismatch")
            # A missing handler is unavailable, never a fabricated READY.
            validate(receipt)
            receipts[template] = receipt

        overview = by_template.get("system_overview")
        if bundle.sibling_release is None and overview is not None:
            if "system_overview" in receipts:
                release = DependencyReceipt(
                    scope=scope,
                    prerequisite_work_id=overview.id,
                    reason="prerequisite_ready",
                    output=receipts["system_overview"],
                )
            elif overview.state == "FAILED":
                release = DependencyReceipt(
                    scope=scope,
                    prerequisite_work_id=overview.id,
                    reason="overview_final_failure",
                )
            else:
                release = None
            if release is not None:
                bundle.sibling_release = {
                    **release.model_dump(mode="json"),
                    "released_at": self.now().isoformat(),
                    "policy_version": policy.policy_version,
                }
        if bundle.sibling_release is not None:
            release_value = dict(bundle.sibling_release)
            if release_value.pop("policy_version", None) != policy.policy_version:
                raise DeliveryContractError("sibling release policy mismatch")
            timestamp = release_value.pop("released_at", None)
            if not isinstance(timestamp, str):
                raise DeliveryContractError("sibling release timestamp missing")
            released_at = datetime.fromisoformat(timestamp)
            if released_at.tzinfo is None:
                raise DeliveryContractError("sibling release timestamp must be aware")
            prior_release = DependencyReceipt.model_validate_json(
                json.dumps(release_value)
            )
            own_tentative = tentative is not None and prior_release.output == tentative
            released_work = self.session.get(Work, prior_release.prerequisite_work_id)
            if (
                prior_release.scope != scope
                or released_work is None
                or released_work.bundle_id != bundle_id
                or released_work.kind != WorkKind.DIAGRAM
                or released_work.template != "system_overview"
                or released_work.state
                != (
                    "RUNNING"
                    if own_tentative
                    else (
                        "FAILED"
                        if prior_release.reason == "overview_final_failure"
                        else "COMPLETED"
                    )
                )
            ):
                raise DeliveryContractError("sibling release history mismatch")
            if prior_release.output is not None and not own_tentative:
                stored_release = self.session.scalar(
                    select(Output).where(Output.work_id == released_work.id)
                )
                if (
                    stored_release is None
                    or PublicationReceipt.model_validate_json(
                        json.dumps(stored_release.receipt)
                    )
                    != prior_release.output
                ):
                    raise DeliveryContractError("sibling release acceptance mismatch")
            for row in by_template.values():
                if row.state == "PENDING" and not row.dependencies_ready:
                    row.dependencies_ready = True
                    row.safe_reason = "handler_unavailable"
                    row.next_eligible_at = self.now()

        reports = [row for row in works if row.kind == WorkKind.REPORT]
        # Once pinned, even a newer accepted overview cannot rewrite this input.
        if bundle.barrier is not None:
            barrier = BarrierReceipt.model_validate_json(json.dumps(bundle.barrier))
            barrier.require_policy(policy, bundle_id)
            for receipt in barrier.diagrams:
                validate(receipt)
            if len(reports) != 1:
                raise DeliveryContractError("pinned barrier missing report operation")
            identity = WorkIdentity.model_validate_json(json.dumps(reports[0].identity))
            if identity.input_fingerprint != barrier.input_fingerprint():
                raise DeliveryContractError("report prerequisite fingerprint mismatch")
            return
        if reports:
            raise DeliveryContractError("report exists without pinned barrier")
        if set(receipts) != set(policy.required_templates):
            return
        binding = next(p for p in policy.profiles if p.slot.kind == WorkKind.REPORT)
        barrier = BarrierReceipt(
            scope=scope,
            report_profile=binding.profile,
            diagrams=tuple(receipts.values()),
        )
        barrier.require_policy(policy, bundle_id)
        identity = WorkIdentity(
            scope=scope,
            bundle_id=bundle_id,
            work_id=uuid4(),
            run_number=1,
            binding=binding,
            bundle_fingerprint=bundle.fingerprint,
            input_fingerprint=barrier.input_fingerprint(),
        )
        bundle.barrier = barrier.model_dump(mode="json")
        self.session.add(
            Work(
                id=identity.work_id,
                bundle_id=bundle_id,
                identity=identity.model_dump(mode="json"),
                kind=WorkKind.REPORT,
                template="architecture_analysis",
                run_number=1,
                is_current=True,
                dependencies_ready=True,
                state="PENDING",
                fence=0,
                executions=0,
                dispatch_epoch=uuid4(),
                next_eligible_at=self.now(),
                safe_reason="handler_unavailable",
                created_at=self.now(),
            )
        )

    def retry_failed(
        self,
        scope: VersionScope,
        request: RetryRequest,
        actor_id: UUID,
        actor_role: str,
        policy: ManualRetryPolicy | None,
        prerequisites: Callable[[Bundle, Work], None],
    ) -> RetryAccepted:
        if actor_role not in {"OWNER", "ADMIN"}:
            raise DeliveryApiError("delivery_retry_forbidden", 403)
        self.lock_project_admission(scope.project_id)
        bundle, work = self.lock_work(
            request.resource_id, scope.project_id, all_current=False
        )
        if (
            VersionScope.model_validate_json(json.dumps(bundle.scope)) != scope
            or work.kind != request.resource_type
        ):
            raise DeliveryApiError("delivery_not_found", 404)
        digest = fingerprint("delivery.retry-key", request.idempotency_key)
        body = fingerprint(
            "delivery.retry-request", {"scope": scope, "request": request.model_dump()}
        )
        prior = self.session.scalar(
            select(Retry).where(
                Retry.actor_id == actor_id,
                Retry.project_id == scope.project_id,
                Retry.action == "retry",
                Retry.key_digest == digest,
            )
        )
        if prior is not None:
            if prior.request_fingerprint != body:
                raise DeliveryApiError("delivery_idempotency_conflict")
            return RetryAccepted(
                scope=scope,
                operation_id=prior.id,
                work_id=prior.new_work_id,
                retry_of_work_id=prior.previous_work_id,
            )
        if not work.is_current or work.state != "FAILED":
            raise DeliveryApiError("delivery_retry_conflict")
        if bundle.eligibility != Eligibility.ELIGIBLE:
            raise DeliveryApiError("delivery_prerequisite_conflict")
        last = self.session.scalar(
            select(Attempt)
            .where(Attempt.work_id == work.id)
            .order_by(Attempt.ordinal.desc())
            .limit(1)
        )
        if last is None or work.safe_reason != "retryable_exhausted":
            raise DeliveryApiError("delivery_retry_requires_new_input")
        if policy is None or work.run_number > policy.max_rounds:
            raise DeliveryApiError("delivery_retry_policy_unavailable")
        since = self.now() - timedelta(seconds=policy.window_seconds)
        project_count = (
            self.session.scalar(
                select(func.count())
                .select_from(Retry)
                .where(Retry.project_id == scope.project_id, Retry.created_at >= since)
            )
            or 0
        )
        actor_count = (
            self.session.scalar(
                select(func.count())
                .select_from(Retry)
                .where(
                    Retry.project_id == scope.project_id,
                    Retry.actor_id == actor_id,
                    Retry.created_at >= since,
                )
            )
            or 0
        )
        if (
            project_count >= policy.max_project_requests
            or actor_count >= policy.max_actor_requests
        ):
            raise DeliveryApiError("delivery_retry_admission_wait")
        prerequisites(bundle, work)
        identity = WorkIdentity.model_validate_json(json.dumps(work.identity))
        successor = identity.model_copy(
            update={"work_id": uuid4(), "run_number": work.run_number + 1}
        )
        work.is_current = False
        self.session.flush()  # Release partial unique slot before successor insert.
        self.session.add(
            Work(
                id=successor.work_id,
                bundle_id=bundle.id,
                identity=successor.model_dump(mode="json"),
                kind=work.kind,
                template=work.template,
                run_number=successor.run_number,
                is_current=True,
                retry_of_work_id=work.id,
                dependencies_ready=work.dependencies_ready,
                state="PENDING",
                fence=0,
                executions=0,
                dispatch_epoch=uuid4(),
                next_eligible_at=self.now(),
                safe_reason="handler_unavailable",
                created_at=self.now(),
            )
        )
        self.session.flush()
        operation = Retry(
            id=uuid4(),
            actor_id=actor_id,
            project_id=scope.project_id,
            action="retry",
            key_digest=digest,
            request_fingerprint=body,
            previous_work_id=work.id,
            new_work_id=successor.work_id,
            created_at=self.now(),
        )
        self.session.add(operation)
        return RetryAccepted(
            scope=scope,
            operation_id=operation.id,
            work_id=successor.work_id,
            retry_of_work_id=work.id,
        )

    def reserve(
        self,
        work_id: UUID,
        project_id: UUID,
        *,
        reservation_seconds: float,
        correlation_id: str,
    ) -> tuple[DeliveryWorkPayload, UUID] | None:
        bundle, work = self.lock_work(work_id, project_id)
        now = self.now()
        if (
            bundle.eligibility != "ELIGIBLE"
            or not work.is_current
            or work.state not in {"PENDING", "QUEUED", "RETRYING"}
            or work.next_eligible_at > now
            or work.dispatch_until is not None
            and work.dispatch_until > now
            or not work.dependencies_ready
        ):
            return None
        if work.state != "QUEUED":
            work.state = "QUEUED"
            work.dispatch_epoch = uuid4()
        work.dispatch_claim = uuid4()
        work.dispatch_until = now + timedelta(seconds=reservation_seconds)
        identity = WorkIdentity.model_validate_json(json.dumps(work.identity))
        payload = DeliveryWorkPayload(
            contract_version="1.0.0",
            work_id=work.id,
            bundle_id=bundle.id,
            project_id=project_id,
            architecture_version_id=identity.scope.architecture_version_id,
            dispatch_epoch=work.dispatch_epoch,
            correlation_id=correlation_id,
        )
        return payload, work.dispatch_claim

    def sent(
        self,
        payload: DeliveryWorkPayload,
        reservation: UUID,
        *,
        replay_seconds: float,
        succeeded: bool,
        retry_delay: Callable[[int], float] | None = None,
    ) -> None:
        _, work = self.lock_work(payload.work_id, payload.project_id)
        if (
            work.state != "QUEUED"
            or work.dispatch_epoch != payload.dispatch_epoch
            or work.dispatch_claim != reservation
        ):
            return
        now = self.now()
        work.dispatch_claim = None
        work.dispatches += 1
        delay = (
            retry_delay(work.dispatches)
            if not succeeded and retry_delay is not None
            else replay_seconds
        )
        work.dispatch_until = now + timedelta(seconds=delay)
        work.safe_reason = None if succeeded else "broker_unavailable"
        if succeeded:
            work.last_sent_at = now

    def claim(
        self,
        payload: DeliveryWorkPayload,
        binding: HandlerProfile,
        worker_id: str,
        *,
        max_executions: int,
        lease_seconds: float,
        execution_seconds: float,
    ) -> ExecutionLease | None:
        self.lock_project_admission(payload.project_id)
        bundle, work = self.lock_work(payload.work_id, payload.project_id)
        identity = WorkIdentity.model_validate_json(json.dumps(work.identity))
        payload.require_work(identity, work.dispatch_epoch)
        if binding != identity.binding:
            raise DeliveryContractError("pinned handler profile mismatch")
        if (
            work.state != "QUEUED"
            or not work.is_current
            or bundle.eligibility != "ELIGIBLE"
            or not work.dependencies_ready
        ):
            return None
        if work.executions >= max_executions:
            work.state, work.safe_reason = "FAILED", "execution_budget_exhausted"
            return None
        now = self.now()
        attempt = AttemptIdentity(
            work=identity,
            attempt_id=uuid4(),
            ordinal=work.executions + 1,
            fence=work.fence + 1,
            dispatch_epoch=work.dispatch_epoch,
            candidate_id=uuid4(),
        )
        lease = ExecutionLease(
            attempt,
            worker_id,
            now + timedelta(seconds=execution_seconds),
            secrets.token_urlsafe(32),
        )
        work.state, work.fence, work.executions = (
            "RUNNING",
            attempt.fence,
            attempt.ordinal,
        )
        work.dispatch_claim, work.dispatch_until, work.safe_reason = None, None, None
        self.session.add(
            Attempt(
                id=attempt.attempt_id,
                work_id=work.id,
                identity=attempt.model_dump(mode="json"),
                ordinal=attempt.ordinal,
                fence=attempt.fence,
                candidate_id=attempt.candidate_id,
                worker_id=worker_id,
                lease_digest=lease.digest,
                expires_at=min(lease.deadline, now + timedelta(seconds=lease_seconds)),
                state="RUNNING",
                started_at=now,
                heartbeat_at=now,
            )
        )
        self.session.flush()
        return lease

    def live(
        self, lease: ExecutionLease, *, lock: bool = False, all_current: bool = False
    ) -> Attempt:
        _, work = (
            self.lock_work(
                lease.identity.work.work_id,
                lease.identity.work.scope.project_id,
                all_current=all_current,
            )
            if lock
            else (None, None)
        )
        statement = (
            select(Attempt)
            .join(Work, Work.id == Attempt.work_id)
            .join(Bundle, Bundle.id == Work.bundle_id)
            .where(
                Attempt.id == lease.identity.attempt_id,
                Attempt.work_id == lease.identity.work.work_id,
                Attempt.fence == lease.identity.fence,
                Attempt.state == "RUNNING",
                Attempt.lease_digest == lease.digest,
                Attempt.worker_id == lease.worker_id,
                Attempt.expires_at > func.clock_timestamp(),
                Work.state == "RUNNING",
                Work.is_current.is_(True),
                Work.fence == lease.identity.fence,
                Work.dispatch_epoch == lease.identity.dispatch_epoch,
                Bundle.project_id == lease.identity.work.scope.project_id,
            )
        )
        if lock:
            statement = statement.with_for_update(of=Attempt)
        row = self.session.scalar(statement)
        if row is None or (
            work is not None
            and WorkIdentity.model_validate_json(json.dumps(work.identity))
            != lease.identity.work
        ):
            raise DeliveryOwnershipLost("delivery execution ownership lost")
        return row

    def renew(self, lease: ExecutionLease, *, lease_seconds: float) -> bool:
        # Attempt-only update; no application row lock is held across heartbeat.
        now = self.now()
        active = exists(
            select(Work.id)
            .join(Bundle, Bundle.id == Work.bundle_id)
            .where(
                Work.id == lease.identity.work.work_id,
                Work.state == "RUNNING",
                Work.is_current.is_(True),
                Work.fence == lease.identity.fence,
                Work.dispatch_epoch == lease.identity.dispatch_epoch,
                Bundle.project_id == lease.identity.work.scope.project_id,
            )
        )
        result = self.session.execute(
            update(Attempt)
            .where(
                Attempt.id == lease.identity.attempt_id,
                Attempt.state == "RUNNING",
                Attempt.fence == lease.identity.fence,
                Attempt.lease_digest == lease.digest,
                Attempt.worker_id == lease.worker_id,
                Attempt.expires_at > func.clock_timestamp(),
                active,
            )
            .values(
                expires_at=min(lease.deadline, now + timedelta(seconds=lease_seconds)),
                heartbeat_at=now,
            )
            .returning(Attempt.id)
        )
        return result.scalar_one_or_none() is not None

    def finish_failure(
        self,
        lease: ExecutionLease,
        *,
        code: str,
        retryable: bool,
        max_executions: int,
        retry_seconds: float,
    ) -> bool:
        try:
            row = self.live(lease, lock=True)
        except DeliveryOwnershipLost:
            return False
        _, work = self.lock_work(
            lease.identity.work.work_id, lease.identity.work.scope.project_id
        )
        self._end(row, "FAILED", code)
        work.state = (
            "RETRYING" if retryable and work.executions < max_executions else "FAILED"
        )
        work.safe_reason, work.next_eligible_at = code, self.now() + timedelta(
            seconds=retry_seconds
        )
        if retryable and work.state == "FAILED":
            work.safe_reason = "retryable_exhausted"
        return True

    def _end(self, row: Attempt, state: str, code: str | None) -> None:
        row.state, row.failure_code, row.ended_at = state, code, self.now()
        row.lease_digest, row.expires_at = None, None

    def recover(
        self,
        work_id: UUID,
        project_id: UUID,
        *,
        max_executions: int,
        retry_seconds: float,
        retry_delay: Callable[[int], float] | None = None,
    ) -> bool:
        _, work = self.lock_work(work_id, project_id)
        row = self.session.scalar(
            select(Attempt)
            .where(Attempt.work_id == work.id, Attempt.state == "RUNNING")
            .with_for_update()
        )
        if (
            work.state != "RUNNING"
            or row is None
            or row.expires_at is None
            or row.expires_at > self.now()
        ):
            return False
        self._end(row, "EXPIRED", "lease_expired")
        work.fence += 1
        work.state = "RETRYING" if work.executions < max_executions else "FAILED"
        work.safe_reason, work.next_eligible_at = (
            "retryable_exhausted" if work.state == "FAILED" else "lease_expired",
            self.now()
            + timedelta(
                seconds=(
                    retry_delay(row.ordinal)
                    if retry_delay is not None
                    else retry_seconds
                )
            ),
        )
        return True

    def cancel(self, project_id: UUID, decision: CancellationDecision) -> bool:
        _, work = self.lock_work(decision.expected_work_id, project_id)
        if (
            work.state in {"COMPLETED", "FAILED", "CANCELLED"}
            or work.fence != decision.expected_fence
        ):
            return False
        row = self.session.scalar(
            select(Attempt)
            .where(Attempt.work_id == work.id, Attempt.state == "RUNNING")
            .with_for_update()
        )
        now = self.now()
        if row is not None:
            self._end(
                row,
                (
                    "EXPIRED"
                    if row.expires_at is not None and row.expires_at <= now
                    else "CANCELLED"
                ),
                "internal_cancellation",
            )
        work.state, work.dispatch_epoch, work.fence = (
            "CANCELLED",
            uuid4(),
            work.fence + 1,
        )
        work.dispatch_claim, work.dispatch_until = None, None
        work.cancellation = {
            "cause": decision.cause.value,
            "actor_type": decision.actor_type,
            "actor_id": str(decision.actor_id),
            "operation_id": str(decision.operation_id),
            "at": now.isoformat(),
            "invalidated_fence": decision.expected_fence,
            "replacement_policy_id": (
                str(decision.replacement_policy_id)
                if decision.replacement_policy_id
                else None
            ),
        }
        return True
