"""Bounded P5 dispatch, execution and recovery; no diagram/report algorithms."""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import timedelta
from functools import partial
from random import Random
from threading import Event, Thread
from time import monotonic
from typing import Annotated, Literal, Self
from typing import cast as type_cast
from uuid import UUID, uuid4

from pydantic import Field, TypeAdapter, model_validator
from sqlalchemy import cast, event, func, or_, select, update
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.platform.analysis.architecture.dto import ArchitectureVersionResponse
from backend.platform.delivery.api_contracts import (
    DeliveryApiError,
    DeliveryEligibility,
    DeliveryState,
    DeliverySummary,
    ManualRetryPolicy,
    RetryAccepted,
    RetryRequest,
    WorkSummary,
)
from backend.platform.delivery.contracts import (
    C0_VERSION,
    BarrierReceipt,
    DeliveryContractError,
    DeliveryExecutionFailure,
    DeliveryPolicy,
    DeliveryWorkPayload,
    DiagramTemplate,
    ExecutionStopped,
    FrozenContract,
    HandlerProfile,
    PublicationReceipt,
    RetryClass,
    StopReason,
    Token,
    VersionScope,
    WorkExecutionContext,
    WorkIdentity,
    WorkKind,
    bundle_fingerprint,
    execution_control,
    fingerprint,
)
from backend.platform.delivery.persistence import DeliveryAttemptModel as Attempt
from backend.platform.delivery.persistence import DeliveryBundleModel as Bundle
from backend.platform.delivery.persistence import DeliveryCapabilityModel as Capability
from backend.platform.delivery.persistence import DeliveryDiscoveryModel as Discovery
from backend.platform.delivery.persistence import DeliveryOutputModel as Output
from backend.platform.delivery.persistence import DeliveryWorkModel as Work
from backend.platform.delivery.publication import (
    PublicationContractViolation,
    PublicationUnitOfWork,
    ReadyValidation,
)
from backend.platform.delivery.queue import DeliveryPublisher
from backend.platform.delivery.registry import HandlerUnavailable, WorkHandlerRegistry
from backend.platform.delivery.repository import (
    DeliveryOwnershipLost,
    ExecutionLease,
    SqlAlchemyDeliveryRepository,
)
from backend.platform.delivery.source import PublishedVersionReader
from backend.platform.graph.source import (
    PublishedArchitectureCursor,
    PublishedArchitectureHeader,
)

Seconds = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Count = Annotated[int, Field(gt=0)]
logger = logging.getLogger(__name__)


class RuntimeBudgets(FrozenContract):
    """All values explicitly supplied; no unapproved production defaults."""

    lease_seconds: Seconds
    heartbeat_seconds: Seconds
    execution_seconds: Seconds
    publication_seconds: Seconds
    lock_timeout_ms: Count
    max_executions: Count
    retry_seconds: Seconds
    retry_max_seconds: Seconds
    retry_jitter_fraction: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    redispatch_seconds: Seconds
    reservation_seconds: Seconds
    capability_ttl_seconds: Seconds
    scan_seconds: Seconds
    scan_lease_seconds: Seconds
    revisit_seconds: Seconds
    broker_timeout_seconds: Seconds
    reconcile_seconds: Seconds
    max_items: Count
    quarantine_max_records: Count
    page_size: Annotated[int, Field(gt=0, le=500)]
    per_project_running: Count

    @model_validator(mode="after")
    def ordering(self) -> Self:
        if (
            self.heartbeat_seconds >= self.lease_seconds
            or self.capability_ttl_seconds <= self.heartbeat_seconds
            or self.publication_seconds >= self.lease_seconds
            or self.scan_lease_seconds <= self.scan_seconds
            or self.retry_max_seconds < self.retry_seconds
        ):
            raise ValueError("inconsistent delivery liveness budgets")
        return self


class FleetManifest(FrozenContract):
    queue: Token
    deployment_epoch: Token
    workers: tuple[
        Annotated[
            str, Field(min_length=1, max_length=256, pattern=r"^[a-zA-Z0-9_.:@-]+$")
        ],
        ...,
    ]
    admission_approved: Literal[True]

    @model_validator(mode="after")
    def unique(self) -> Self:
        if not self.workers or len(set(self.workers)) != len(self.workers):
            raise ValueError("fleet requires unique approved consumers")
        return self


def profile_key(binding: HandlerProfile, execution_policy_fingerprint: str) -> str:
    return fingerprint(
        "delivery.handler-profile",
        {"binding": binding, "runtime": execution_policy_fingerprint},
    )


class DeliveryCoordinator:
    def __init__(
        self,
        *,
        engine: Engine,
        registry: WorkHandlerRegistry,
        publisher: DeliveryPublisher,
        policy: DeliveryPolicy,
        budgets: RuntimeBudgets,
        fleet: FleetManifest,
        reader: Callable[[], AbstractContextManager[PublishedVersionReader]],
        dispatch_enabled: bool,
        execution_enabled: bool | None = None,
        rng: Random | None = None,
        manual_retry_policy: ManualRetryPolicy | None = None,
    ) -> None:
        self.engine, self.registry, self.publisher = engine, registry, publisher
        self.policy, self.budgets, self.fleet, self.reader, self.dispatch_enabled = (
            policy,
            budgets,
            fleet,
            reader,
            dispatch_enabled,
        )
        self.execution_enabled = (
            dispatch_enabled if execution_enabled is None else execution_enabled
        )
        self._rng = rng or Random()
        self.manual_retry_policy = manual_retry_policy
        self.runtime_fingerprint = fingerprint("delivery.runtime", budgets)
        if policy.execution_policy_fingerprint != self.runtime_fingerprint:
            raise ValueError("delivery policy must explicitly pin its runtime profile")

    def retry_delay(self, ordinal: int) -> float:
        try:
            base = math.ldexp(self.budgets.retry_seconds, max(0, ordinal - 1))
        except OverflowError:
            base = self.budgets.retry_max_seconds
        base = min(base, self.budgets.retry_max_seconds)
        jitter = (
            (2 * self._rng.random() - 1) * self.budgets.retry_jitter_fraction * base
        )
        return max(0.0, min(self.budgets.retry_max_seconds, base + jitter))

    def session(self) -> Session:
        session = Session(self.engine, autoflush=False, expire_on_commit=False)

        def budget_sql(
            session: Session, transaction: object, connection: object
        ) -> None:
            from sqlalchemy.engine import Connection

            assert isinstance(connection, Connection)
            connection.execute(
                select(
                    func.set_config(
                        "lock_timeout", str(self.budgets.lock_timeout_ms), True
                    )
                )
            )
            connection.execute(
                select(
                    func.set_config(
                        "statement_timeout",
                        str(max(1, int(self.budgets.publication_seconds * 1000))),
                        True,
                    )
                )
            )

        event.listen(session, "after_begin", budget_sql)
        return session

    def heartbeat(self, worker_id: str, *, reconciliation: bool = False) -> None:
        with self.session() as session, session.begin():
            now = SqlAlchemyDeliveryRepository(session).now()
            profiles = [
                (profile_key(b, self.runtime_fingerprint), True)
                for b in self.registry.profiles
            ]
            profiles.append(("task_registration", True))
            if reconciliation:
                profiles.append(("reconciliation_scheduling", True))
            for profile, ready in profiles:
                session.execute(
                    insert(Capability)
                    .values(
                        worker_id=worker_id,
                        profile=profile,
                        contract_version=C0_VERSION,
                        deployment_epoch=self.fleet.deployment_epoch,
                        queue=self.fleet.queue,
                        ready=ready,
                        observed_at=now,
                    )
                    .on_conflict_do_update(
                        index_elements=[Capability.worker_id, Capability.profile],
                        set_={
                            "ready": ready,
                            "observed_at": now,
                            "contract_version": C0_VERSION,
                            "deployment_epoch": self.fleet.deployment_epoch,
                            "queue": self.fleet.queue,
                        },
                    )
                )

    def fleet_ready(self, session: Session, binding: HandlerProfile) -> bool:
        now = SqlAlchemyDeliveryRepository(session).now()
        evidence_limit = len(self.fleet.workers) * (len(self.registry.profiles) + 2)
        rows = tuple(
            session.scalars(
                select(Capability)
                .where(
                    Capability.queue == self.fleet.queue,
                    Capability.observed_at
                    > now - timedelta(seconds=self.budgets.capability_ttl_seconds),
                )
                .limit(evidence_limit + 1)
            )
        )
        if len(rows) > evidence_limit:
            return False  # Fail closed on excess evidence, never silently omit peers.
        if any(r.worker_id not in self.fleet.workers for r in rows):
            return False
        matching = {
            r.worker_id
            for r in rows
            if r.profile == profile_key(binding, self.runtime_fingerprint)
            and r.ready
            and r.contract_version == C0_VERSION
            and r.deployment_epoch == self.fleet.deployment_epoch
        }
        registered = {
            r.worker_id
            for r in rows
            if r.profile == "task_registration"
            and r.ready
            and r.contract_version == C0_VERSION
            and r.deployment_epoch == self.fleet.deployment_epoch
        }
        return matching == registered == set(self.fleet.workers)

    def dispatch(self) -> int:
        if not self.dispatch_enabled:
            return 0
        with self.session() as session:
            now = SqlAlchemyDeliveryRepository(session).now()
            candidates = tuple(
                session.execute(
                    select(Work.id, Bundle.project_id)
                    .join(Bundle, Work.bundle_id == Bundle.id)
                    .where(
                        Work.state.in_(("PENDING", "QUEUED", "RETRYING")),
                        Work.is_current.is_(True),
                        Work.dependencies_ready.is_(True),
                        Work.next_eligible_at <= now,
                        or_(Work.dispatch_until.is_(None), Work.dispatch_until <= now),
                    )
                    .order_by(Work.next_eligible_at, Work.id)
                    .limit(self.budgets.max_items)
                )
            )
        sent = 0
        for work_id, project_id in candidates:
            with self.session() as session, session.begin():
                repo = SqlAlchemyDeliveryRepository(session)
                repo.lock_project_admission(project_id)
                bundle, work = repo.lock_work(work_id, project_id)
                if bundle.runtime_profile != self.budgets.model_dump(mode="json"):
                    work.safe_reason = "runtime_profile_unavailable"
                    work.next_eligible_at = repo.now() + timedelta(
                        seconds=self.budgets.revisit_seconds
                    )
                    continue
                if not work.dependencies_ready:
                    continue
                identity = WorkIdentity.model_validate_json(json.dumps(work.identity))
                try:
                    self.registry.resolve(identity.binding)
                except HandlerUnavailable:
                    work.safe_reason = "handler_unavailable"
                    work.next_eligible_at = repo.now() + timedelta(
                        seconds=self.budgets.revisit_seconds
                    )
                    continue
                if not self.fleet_ready(session, identity.binding):
                    if work.safe_reason != "waiting_on_overview":
                        work.safe_reason = "worker_unavailable"
                    work.next_eligible_at = repo.now() + timedelta(
                        seconds=self.budgets.revisit_seconds
                    )
                    continue
                running = (
                    session.scalar(
                        select(func.count())
                        .select_from(Work)
                        .join(Bundle, Bundle.id == Work.bundle_id)
                        .where(Bundle.project_id == project_id, Work.state == "RUNNING")
                    )
                    or 0
                )
                if running >= self.budgets.per_project_running:
                    continue
                reservation = repo.reserve(
                    work_id,
                    project_id,
                    reservation_seconds=self.budgets.reservation_seconds,
                    correlation_id=f"delivery:{uuid4()}",
                )
            if reservation is None:
                continue
            payload, token = reservation
            succeeded = False
            try:
                self.publisher.publish(payload)
                succeeded = True
                sent += 1
            except Exception:
                # Fixed code only; never log raw broker exceptions or payloads.
                pass
            with self.session() as session, session.begin():
                SqlAlchemyDeliveryRepository(session).sent(
                    payload,
                    token,
                    replay_seconds=self.budgets.redispatch_seconds,
                    succeeded=succeeded,
                    retry_delay=self.retry_delay,
                )
        return sent

    def execute(self, payload: DeliveryWorkPayload, worker_id: str) -> str:
        if not self.execution_enabled or worker_id not in self.fleet.workers:
            return "dispatch_disabled"
        with self.session() as session, session.begin():
            repo = SqlAlchemyDeliveryRepository(session)
            repo.lock_project_admission(payload.project_id)
            bundle, row = repo.lock_work(payload.work_id, payload.project_id)
            if bundle.runtime_profile != self.budgets.model_dump(mode="json"):
                return "runtime_profile_unavailable"
            identity = WorkIdentity.model_validate_json(json.dumps(row.identity))
            self.registry.resolve(identity.binding)  # no claim on mismatch
            if not self.fleet_ready(session, identity.binding):
                return "worker_unavailable"
            running = (
                session.scalar(
                    select(func.count())
                    .select_from(Work)
                    .join(Bundle, Bundle.id == Work.bundle_id)
                    .where(
                        Bundle.project_id == payload.project_id, Work.state == "RUNNING"
                    )
                )
                or 0
            )
            if running >= self.budgets.per_project_running:
                return "admission_wait"
            lease = repo.claim(
                payload,
                identity.binding,
                worker_id,
                max_executions=self.budgets.max_executions,
                lease_seconds=self.budgets.lease_seconds,
                execution_seconds=self.budgets.execution_seconds,
            )
        if lease is None:
            return "duplicate"
        stop, lost = Event(), Event()
        until = monotonic() + self.budgets.execution_seconds

        def observe() -> StopReason | None:
            if lost.is_set():
                return StopReason.OWNERSHIP_LOST
            return StopReason.DEADLINE if monotonic() >= until else None

        def renew() -> None:
            while not stop.wait(self.budgets.heartbeat_seconds):
                try:
                    with self.session() as session, session.begin():
                        if not SqlAlchemyDeliveryRepository(session).renew(
                            lease, lease_seconds=self.budgets.lease_seconds
                        ):
                            lost.set()
                            return
                except Exception:
                    lost.set()
                    return

        heartbeat = Thread(target=renew, daemon=True, name="delivery-attempt-heartbeat")
        heartbeat.start()
        try:
            context = WorkExecutionContext(
                attempt=lease.identity,
                deadline=lease.deadline,
                control=execution_control(observe),
                prerequisites=self.report_prerequisites(lease),
            )
            prepared = self.registry.execute(context)
            stop.set()
            heartbeat.join(timeout=self.budgets.lease_seconds)
            if heartbeat.is_alive() or observe() is not None:
                raise DeliveryOwnershipLost("heartbeat not quiescent")
            with self.session() as session, session.begin():
                if not SqlAlchemyDeliveryRepository(session).renew(
                    lease, lease_seconds=self.budgets.lease_seconds
                ):
                    raise DeliveryOwnershipLost("publication lease lost")
            factory = self.registry.resolve(identity.binding).publication_factory
            with PublicationUnitOfWork(
                self.engine,
                timeout_seconds=self.budgets.publication_seconds,
                lock_timeout_ms=self.budgets.lock_timeout_ms,
            ) as uow:
                uow.complete(
                    lease,
                    prepared,
                    factory,
                    stage_dependencies=lambda session, receipt: self._dependencies(
                        uow, session, identity.bundle_id, receipt
                    ),
                )
                uow.commit()
            logger.info(
                "delivery_output_accepted",
                extra={
                    "work_id": str(identity.work_id),
                    "bundle_id": str(identity.bundle_id),
                    "actor_type": "system",
                },
            )
            return "completed"
        except Exception as exc:
            stop.set()
            heartbeat.join(timeout=self.budgets.lease_seconds)
            # Ambiguous commit: a committed exact receipt wins, never rerun a
            # producer or mark completed work failed based on transport error.
            with self.session() as session:
                accepted = session.scalar(
                    select(Output.id).where(
                        Output.work_id == lease.identity.work.work_id,
                        Output.attempt_id == lease.identity.attempt_id,
                        Output.fence == lease.identity.fence,
                    )
                )
                if accepted is not None:
                    return "completed"
            with self.session() as session, session.begin():
                SqlAlchemyDeliveryRepository(session).finish_failure(
                    lease,
                    code=(
                        exc.failure.code
                        if isinstance(exc, DeliveryExecutionFailure)
                        else (
                            exc.reason.value
                            if isinstance(exc, ExecutionStopped)
                            else (
                                "publication_contract_violation"
                                if isinstance(exc, PublicationContractViolation)
                                else "execution_failed"
                            )
                        )
                    ),
                    retryable=(
                        exc.failure.retry_class == RetryClass.TRANSIENT
                        if isinstance(exc, DeliveryExecutionFailure)
                        else isinstance(exc, (ExecutionStopped, DeliveryOwnershipLost))
                    ),
                    max_executions=self.budgets.max_executions,
                    retry_seconds=self.retry_delay(lease.identity.ordinal),
                )
            return "failed"
        finally:
            stop.set()

    def recover(self) -> int:
        with self.session() as session:
            ids = tuple(
                session.execute(
                    select(Work.id, Bundle.project_id)
                    .join(Bundle, Bundle.id == Work.bundle_id)
                    .join(Attempt, Attempt.work_id == Work.id)
                    .where(
                        Attempt.state == "RUNNING",
                        Attempt.expires_at <= func.clock_timestamp(),
                        cast(Bundle.runtime_profile, JSONB)
                        == self.budgets.model_dump(mode="json"),
                    )
                    .order_by(Attempt.expires_at)
                    .limit(self.budgets.max_items)
                )
            )
        count = 0
        for work_id, project_id in ids:
            with self.session() as session, session.begin():
                count += SqlAlchemyDeliveryRepository(session).recover(
                    work_id,
                    project_id,
                    max_executions=self.budgets.max_executions,
                    retry_seconds=self.budgets.retry_seconds,
                    retry_delay=self.retry_delay,
                )
        return count

    def discover(self) -> int:
        """One bounded leased page; reset after a complete pass, revisit waits."""
        key = fingerprint("delivery.discovery-policy", self.policy)
        owner, until = uuid4(), monotonic() + self.budgets.scan_seconds
        with self.session() as session, session.begin():
            repo = SqlAlchemyDeliveryRepository(session)
            now = repo.now()
            session.execute(
                insert(Discovery)
                .values(key=key, fence=0)
                .on_conflict_do_nothing(index_elements=[Discovery.key])
            )
            row = session.scalars(
                select(Discovery).where(Discovery.key == key).with_for_update()
            ).one()
            if row.expires_at is not None and row.expires_at > now:
                return 0
            row.owner, row.fence, row.expires_at = (
                owner,
                row.fence + 1,
                now + timedelta(seconds=self.budgets.scan_lease_seconds),
            )
            fence, saved = row.fence, row.cursor
        cursor = (
            PublishedArchitectureCursor(
                UUID(saved["project_id"]),
                UUID(saved["repository_id"]),
                saved["sequence_number"],
                UUID(saved["architecture_version_id"]),
            )
            if saved
            else None
        )
        processed = 0
        try:
            with self.reader() as reader:
                page = reader.list_for_discovery(
                    limit=min(self.budgets.page_size, self.budgets.max_items),
                    cursor=cursor,
                )
                for header in page.items:
                    if monotonic() >= until:
                        break
                    try:
                        inspection = reader.inspect_eligibility(header)
                    except ValueError:
                        inspection = None  # Safe persistent quarantine, not omission.
                    with self.session() as session, session.begin():
                        repo = SqlAlchemyDeliveryRepository(session)
                        if inspection is not None:
                            repo.ensure_bundle(
                                inspection.scope,
                                self.policy,
                                inspection.eligibility,
                                revisit_seconds=self.budgets.revisit_seconds,
                                runtime_profile=self.budgets.model_dump(mode="json"),
                                source_header=json.loads(
                                    TypeAdapter(PublishedArchitectureHeader).dump_json(
                                        header
                                    )
                                ),
                            )
                        state = session.scalars(
                            select(Discovery)
                            .where(
                                Discovery.key == key,
                                Discovery.owner == owner,
                                Discovery.fence == fence,
                                Discovery.expires_at > func.clock_timestamp(),
                            )
                            .with_for_update()
                        ).one_or_none()
                        if state is None:
                            raise DeliveryOwnershipLost("discovery lease lost")
                        if inspection is None:
                            quarantines = dict(
                                (state.pending or {}).get("quarantine", {})
                            )
                            identity = str(header.architecture_version_id)
                            if (
                                identity not in quarantines
                                and len(quarantines)
                                >= self.budgets.quarantine_max_records
                            ):
                                raise ValueError(
                                    "delivery source quarantine capacity reached"
                                )
                            quarantines[identity] = {
                                "project_id": str(header.project_id),
                                "repository_id": str(header.repository_id),
                                "analysis_id": str(header.analysis_id),
                                "sequence_number": header.sequence_number,
                                "code": "source_integrity_failed",
                            }
                            state.pending = {"quarantine": quarantines}
                        state.cursor = {
                            "project_id": str(header.project_id),
                            "repository_id": str(header.repository_id),
                            "sequence_number": header.sequence_number,
                            "architecture_version_id": str(
                                header.architecture_version_id
                            ),
                        }
                        processed += 1
                with self.session() as session, session.begin():
                    state = session.scalars(
                        select(Discovery)
                        .where(
                            Discovery.key == key,
                            Discovery.owner == owner,
                            Discovery.fence == fence,
                        )
                        .with_for_update()
                    ).one_or_none()
                    if state is not None:
                        if processed == len(page.items) and page.next_cursor is None:
                            state.cursor, state.completed_at = (
                                None,
                                SqlAlchemyDeliveryRepository(session).now(),
                            )
                        state.owner, state.expires_at = None, None
        finally:
            # A crash leaves only a bounded expiring scan reservation.
            pass
        return processed

    def revisit(self) -> int:
        with self.session() as session:
            rows = tuple(
                session.execute(
                    select(Bundle.id, Bundle.source_header)
                    .where(
                        Bundle.eligibility == "WAITING_FOR_ANALYSIS",
                        cast(Bundle.policy, JSONB)
                        == self.policy.model_dump(mode="json"),
                        Bundle.eligibility_retry_at <= func.clock_timestamp(),
                        Bundle.source_header.is_not(None),
                    )
                    .order_by(Bundle.eligibility_retry_at)
                    .limit(self.budgets.max_items)
                )
            )
        count = 0
        with self.reader() as reader:
            for bundle_id, header_data in rows:
                try:
                    header = TypeAdapter(PublishedArchitectureHeader).validate_json(
                        json.dumps(header_data)
                    )
                    inspection = reader.inspect_eligibility(header)
                    with self.session() as session, session.begin():
                        SqlAlchemyDeliveryRepository(session).ensure_bundle(
                            inspection.scope,
                            self.policy,
                            inspection.eligibility,
                            revisit_seconds=self.budgets.revisit_seconds,
                            source_header=header_data,
                            runtime_profile=self.budgets.model_dump(mode="json"),
                        )
                    count += 1
                except Exception as exc:
                    with self.session() as session, session.begin():
                        session.execute(
                            update(Bundle)
                            .where(Bundle.id == bundle_id)
                            .values(
                                eligibility_error=(
                                    "source_integrity_failed"
                                    if isinstance(exc, ValueError)
                                    else "source_unavailable"
                                ),
                                eligibility_retry_at=SqlAlchemyDeliveryRepository(
                                    session
                                ).now()
                                + timedelta(seconds=self.budgets.revisit_seconds),
                            )
                        )
        return count

    def report_prerequisites(self, lease: ExecutionLease) -> BarrierReceipt | None:
        if lease.identity.work.binding.slot.kind != WorkKind.REPORT:
            return None
        with self.session() as session:
            bundle = session.get(Bundle, lease.identity.work.bundle_id)
            if bundle is None or bundle.barrier is None:
                raise DeliveryContractError("report missing immutable prerequisites")
            barrier = BarrierReceipt.model_validate_json(json.dumps(bundle.barrier))
            policy = DeliveryPolicy.model_validate_json(json.dumps(bundle.policy))
            barrier.require_policy(policy, bundle.id)
            if barrier.input_fingerprint() != lease.identity.work.input_fingerprint:
                raise DeliveryContractError("report input fingerprint mismatch")
        # Revalidate pinned generations, not current/latest diagram aliases.
        with self._uow() as uow:
            for receipt in barrier.diagrams:
                self._validate_receipt(uow, receipt)
        return barrier

    def _uow(self) -> PublicationUnitOfWork:
        return PublicationUnitOfWork(
            self.engine,
            timeout_seconds=self.budgets.publication_seconds,
            lock_timeout_ms=self.budgets.lock_timeout_ms,
        )

    def _validate_receipt(
        self, uow: PublicationUnitOfWork, receipt: PublicationReceipt
    ) -> None:
        registration = self.registry.resolve(receipt.prepared.attempt.work.binding)
        receipt = PublicationReceipt.model_validate(receipt)
        context = uow.context(receipt.prepared.attempt)
        context.require_reference(receipt.accepted.reference)
        result = ReadyValidation.model_validate(
            uow.enlist(registration.publication_factory).validate_ready(
                receipt.accepted.reference, context
            )
        )
        uow.require_healthy()
        if result.reference != receipt.accepted.reference:
            raise DeliveryContractError("readiness substituted immutable reference")

    def _dependencies(
        self,
        uow: PublicationUnitOfWork,
        session: Session,
        bundle_id: UUID,
        tentative: PublicationReceipt | None = None,
    ) -> None:
        SqlAlchemyDeliveryRepository(session).coordinate_dependencies(
            bundle_id,
            lambda receipt: self._validate_receipt(uow, receipt),
            tentative=tentative,
        )

    def dependencies(self) -> int:
        with self.session() as session:
            ids = tuple(
                session.scalars(
                    select(Bundle.id)
                    .where(
                        Bundle.eligibility == "ELIGIBLE",
                        cast(Bundle.runtime_profile, JSONB)
                        == self.budgets.model_dump(mode="json"),
                        Bundle.barrier.is_(None),
                    )
                    .order_by(Bundle.eligibility_retry_at, Bundle.id)
                    .limit(self.budgets.max_items)
                )
            )
        count = 0
        for bundle_id in ids:
            try:
                with self._uow() as uow:
                    uow.coordinate(
                        partial(self._dependencies, uow, bundle_id=bundle_id)
                    )
                    uow.commit()
                count += 1
            except HandlerUnavailable, DeliveryContractError:
                # Missing producer is an honest wait; rotate this bundle so a
                # permanently blocked first page cannot starve later bundles.
                logger.warning(
                    "delivery_dependencies_unavailable",
                    extra={"bundle_id": str(bundle_id), "actor_type": "system"},
                )
            finally:
                with self.session() as session, session.begin():
                    session.execute(
                        update(Bundle)
                        .where(Bundle.id == bundle_id)
                        .values(
                            eligibility_retry_at=func.clock_timestamp()
                            + timedelta(seconds=self.budgets.revisit_seconds)
                        )
                    )
        return count

    def retry(
        self,
        scope: VersionScope,
        request: RetryRequest,
        actor_id: UUID,
        actor_role: str,
    ) -> RetryAccepted:
        request = RetryRequest.model_validate(request)
        with self.session() as session, session.begin():

            def prerequisites(bundle: Bundle, work: Work) -> None:
                if (
                    not self.execution_enabled
                    or not self.dispatch_enabled
                    or bundle.runtime_profile != self.budgets.model_dump(mode="json")
                ):
                    raise DeliveryApiError("delivery_runtime_unavailable", 503)
                identity = WorkIdentity.model_validate_json(json.dumps(work.identity))
                try:
                    self.registry.resolve(identity.binding)
                except HandlerUnavailable as exc:
                    raise DeliveryApiError("delivery_handler_unavailable", 503) from exc
                if not self.fleet_ready(session, identity.binding):
                    raise DeliveryApiError("delivery_worker_unavailable", 503)
                if not work.dependencies_ready:
                    raise DeliveryApiError("delivery_prerequisite_conflict")
                if work.kind == WorkKind.REPORT:
                    if bundle.barrier is None:
                        raise DeliveryApiError("delivery_prerequisite_conflict")
                    barrier = BarrierReceipt.model_validate_json(
                        json.dumps(bundle.barrier)
                    )
                    barrier.require_policy(
                        DeliveryPolicy.model_validate_json(json.dumps(bundle.policy)),
                        bundle.id,
                    )
                    if barrier.input_fingerprint() != identity.input_fingerprint:
                        raise DeliveryApiError("delivery_prerequisite_conflict")
                    with self._uow() as uow:
                        for receipt in barrier.diagrams:
                            self._validate_receipt(uow, receipt)

            try:
                return SqlAlchemyDeliveryRepository(session).retry_failed(
                    scope,
                    request,
                    actor_id,
                    actor_role,
                    self.manual_retry_policy,
                    prerequisites,
                )
            except DeliveryOwnershipLost as exc:
                raise DeliveryApiError("delivery_not_found", 404) from exc

    def scope_for_record(
        self, record: ArchitectureVersionResponse
    ) -> VersionScope | None:
        """Reuse accepted immutable scope for polling, without loading source bytes.

        The caller must obtain the exact published record through the public
        ArchitectureQueryService. Any metadata change fails closed.
        """
        with self.session() as session:
            rows = tuple(
                session.scalars(
                    select(Bundle)
                    .where(
                        Bundle.project_id == record.project_id,
                        Bundle.architecture_version_id == record.id,
                        cast(Bundle.policy, JSONB)
                        == self.policy.model_dump(mode="json"),
                    )
                    .order_by(Bundle.id)
                    .limit(2)
                )
            )
            if len(rows) > 1:
                raise DeliveryContractError("ambiguous delivery policy scope")
            for row in rows:
                scope = VersionScope.model_validate_json(json.dumps(row.scope))
                if row.fingerprint != bundle_fingerprint(scope, self.policy):
                    continue
                if (
                    scope.project_id,
                    scope.repository_id,
                    scope.analysis_id,
                    scope.snapshot_id,
                    scope.architecture_version_id,
                    scope.sequence_number,
                    scope.published_at,
                    scope.canonical_digest,
                    scope.architecture_schema_version,
                    scope.ir_schema_version,
                ) != (
                    record.project_id,
                    record.repository_id,
                    record.analysis_id,
                    record.snapshot_id,
                    record.id,
                    record.sequence_number,
                    record.published_at,
                    record.content_digest,
                    record.architecture_schema_version,
                    record.ir_schema_version,
                ):
                    raise DeliveryContractError("published delivery metadata changed")
                return scope
        return None

    def summary(self, scope: VersionScope, actor_role: str) -> DeliverySummary:
        with self.session() as session, session.begin():
            # A short share lock gives a coherent snapshot across separate tables;
            # it does not discover/schedule/modify anything.
            bundle = session.scalar(
                select(Bundle)
                .where(
                    Bundle.project_id == scope.project_id,
                    Bundle.architecture_version_id == scope.architecture_version_id,
                    Bundle.fingerprint == bundle_fingerprint(scope, self.policy),
                )
                .with_for_update(read=True)
            )
            if bundle is None:
                return DeliverySummary(
                    scope=scope,
                    eligibility="NOT_SCHEDULED",
                    capabilities=(
                        ("dispatch_disabled",) if not self.dispatch_enabled else ()
                    ),
                )
            rows = tuple(
                session.scalars(
                    select(Work)
                    .where(Work.bundle_id == bundle.id, Work.is_current.is_(True))
                    .order_by(Work.kind, Work.template)
                )
            )
            summaries: dict[str, WorkSummary] = {}
            capabilities: set[str] = set()
            if not self.dispatch_enabled:
                capabilities.add("dispatch_disabled")
            now = SqlAlchemyDeliveryRepository(session).now()
            reconciler = session.scalar(
                select(Capability.observed_at)
                .where(
                    Capability.profile == "reconciliation_scheduling",
                    Capability.worker_id.in_(self.fleet.workers),
                    Capability.queue == self.fleet.queue,
                    Capability.deployment_epoch == self.fleet.deployment_epoch,
                    Capability.contract_version == C0_VERSION,
                    Capability.ready.is_(True),
                )
                .order_by(Capability.observed_at.desc())
                .limit(1)
            )
            if reconciler is None or reconciler <= now - timedelta(
                seconds=self.budgets.capability_ttl_seconds
            ):
                capabilities.add("reconciler_unavailable")
            for row in rows:
                identity = WorkIdentity.model_validate_json(json.dumps(row.identity))
                reason = row.safe_reason
                if not row.dependencies_ready:
                    overview = next(
                        (r for r in rows if r.template == "system_overview"), None
                    )
                    reason = (
                        "waiting_on_overview_retry"
                        if overview and overview.state == "RETRYING"
                        else "waiting_on_overview"
                    )
                available = False
                try:
                    self.registry.resolve(identity.binding)
                    available = self.fleet_ready(session, identity.binding)
                    if not available:
                        capabilities.add("worker_unavailable")
                except HandlerUnavailable:
                    capabilities.add("handler_unavailable")
                stored = session.scalar(select(Output).where(Output.work_id == row.id))
                reference = (
                    PublicationReceipt.model_validate_json(
                        json.dumps(stored.receipt)
                    ).accepted.reference
                    if stored
                    else None
                )
                summaries[row.template or "search"] = WorkSummary(
                    kind=identity.binding.slot.kind,
                    template=identity.binding.slot.template,
                    work_id=row.id,
                    state=type_cast(DeliveryState, row.state),
                    reason=reason,
                    run_number=row.run_number,
                    executions=row.executions,
                    max_executions=self.budgets.max_executions,
                    retry_allowed=actor_role in {"OWNER", "ADMIN"}
                    and row.state == "FAILED"
                    and row.safe_reason == "retryable_exhausted"
                    and self.manual_retry_policy is not None
                    and row.run_number <= self.manual_retry_policy.max_rounds
                    and available
                    and self.execution_enabled
                    and self.dispatch_enabled,
                    reference=reference,
                    cancellation_cause=(row.cancellation or {}).get("cause"),
                )
            waiting = tuple(
                str(t)
                for t in DiagramTemplate
                if t not in summaries or summaries[t].reference is None
            )
            report = summaries.get("architecture_analysis") or WorkSummary(
                kind=WorkKind.REPORT,
                template="architecture_analysis",
                state="WAITING_FOR_DIAGRAMS",
            )
            return DeliverySummary(
                scope=scope,
                bundle_id=bundle.id,
                policy_version=self.policy.policy_version,
                eligibility=type_cast(DeliveryEligibility, bundle.eligibility),
                diagrams=tuple(summaries[t] for t in DiagramTemplate if t in summaries),
                search=summaries.get("search"),
                report=report,
                waiting_on=waiting,
                capabilities=tuple(sorted(capabilities)),
                sibling_release_reason=(bundle.sibling_release or {}).get("reason"),
                updated_at=SqlAlchemyDeliveryRepository(session).now(),
                last_reconciler_at=reconciler,
                source_error=bundle.eligibility_error,
            )

    def reconcile(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for name, operation in (
            ("revisited", self.revisit),
            ("discovered", self.discover),
            ("recovered", self.recover),
            ("dependencies", self.dependencies),
            ("dispatched", self.dispatch),
        ):
            try:
                result[name] = operation()
            except Exception:
                result[name], result[name + "_failures"] = 0, 1
        return result
