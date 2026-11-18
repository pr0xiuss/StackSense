"""Separately versioned, additive M1 same-profile search reprojection port.

This is not retry and does not modify C0. M2 may call this public service but
must never write these records or create work itself. Automatic repair remains
unavailable until a trusted-system policy is separately approved.
"""

import json
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import Field, TypeAdapter
from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.platform.delivery.api_contracts import DeliveryApiError
from backend.platform.delivery.contracts import (
    ArtifactReference,
    FrozenContract,
    PublicationReceipt,
    VersionScope,
    WorkIdentity,
    WorkKind,
    fingerprint,
)
from backend.platform.delivery.persistence import DeliveryOutputModel as Output
from backend.platform.delivery.persistence import DeliveryWorkModel as Work
from backend.platform.delivery.registry import HandlerUnavailable
from backend.platform.delivery.repository import (
    DeliveryOwnershipLost,
    SqlAlchemyDeliveryRepository,
)
from backend.platform.delivery.service import DeliveryCoordinator
from backend.platform.projects.infra.base import Base

ReprojectionKey = Annotated[
    str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
]


class SearchReprojectionRequest(FrozenContract):
    reprojection_version: Literal["1.0.0"] = "1.0.0"
    idempotency_key: ReprojectionKey
    expected_predecessor_work_id: UUID
    expected_accepted_reference: ArtifactReference
    reason: Literal["manual_rebuild", "storage_missing", "storage_corrupt"]
    observation_id: UUID | None = None


class AuthorizedReprojectionPrincipal(FrozenContract):
    actor_id: UUID
    project_id: UUID
    role: str


class SearchReprojectionPolicy(FrozenContract):
    """Independent explicit admission; never borrow failed-retry defaults."""

    max_rounds: Annotated[int, Field(gt=0)]
    window_seconds: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    max_actor_requests: Annotated[int, Field(gt=0)]
    max_project_requests: Annotated[int, Field(gt=0)]


class SearchReprojectionAccepted(FrozenContract):
    reprojection_version: Literal["1.0.0"] = "1.0.0"
    scope: VersionScope
    operation_id: UUID
    predecessor_work_id: UUID
    new_work_id: UUID
    state: Literal["PENDING"] = "PENDING"
    input_fingerprint: str
    profile_fingerprint: str
    reason: Literal["manual_rebuild", "storage_missing", "storage_corrupt"]


class SearchReprojectionOperation(Base):
    __tablename__ = "delivery_search_reprojections"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    key_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    request_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    response_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    predecessor_work_id: Mapped[UUID] = mapped_column(
        ForeignKey("delivery_work.id", ondelete="RESTRICT"), nullable=False
    )
    successor_work_id: Mapped[UUID] = mapped_column(
        ForeignKey("delivery_work.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "actor_id",
            "project_id",
            "key_digest",
            name="uq_delivery_search_reprojection_key",
        ),
    )


class SearchReprojectionService:
    def __init__(
        self, coordinator: DeliveryCoordinator, policy: SearchReprojectionPolicy | None
    ) -> None:
        self._runtime, self._policy = coordinator, policy

    @staticmethod
    def _authorize(
        scope: VersionScope, principal: AuthorizedReprojectionPrincipal
    ) -> None:
        if principal.project_id != scope.project_id or principal.role not in {
            "OWNER",
            "ADMIN",
        }:
            raise DeliveryApiError("delivery_reprojection_forbidden", 403)

    def lookup(
        self,
        scope: VersionScope,
        idempotency_key: str,
        principal: AuthorizedReprojectionPrincipal,
    ) -> SearchReprojectionAccepted | None:
        """Replay before M2 re-resolves today's producer pointer.

        Fresh delegated authorization is still required on every lookup.
        """
        scope = VersionScope.model_validate(scope)
        idempotency_key = TypeAdapter(ReprojectionKey).validate_python(idempotency_key)
        principal = AuthorizedReprojectionPrincipal.model_validate(principal)
        self._authorize(scope, principal)
        with self._runtime.session() as session:
            row = session.scalar(
                select(SearchReprojectionOperation).where(
                    SearchReprojectionOperation.actor_id == principal.actor_id,
                    SearchReprojectionOperation.project_id == scope.project_id,
                    SearchReprojectionOperation.key_digest
                    == fingerprint("delivery.reprojection-key", idempotency_key),
                )
            )
            if row is None:
                return None
            result = SearchReprojectionAccepted.model_validate_json(
                json.dumps(row.response_snapshot)
            )
            if result.scope != scope:
                raise DeliveryApiError("delivery_idempotency_conflict")
            return result

    def request_search_reprojection(
        self,
        scope: VersionScope,
        request: SearchReprojectionRequest,
        principal: AuthorizedReprojectionPrincipal,
    ) -> SearchReprojectionAccepted:
        scope = VersionScope.model_validate(scope)
        request = SearchReprojectionRequest.model_validate(request)
        principal = AuthorizedReprojectionPrincipal.model_validate(principal)
        self._authorize(scope, principal)
        if request.reason != "manual_rebuild" or request.observation_id is not None:
            # No counterfeit system actors or unapproved automatic-repair policy.
            raise DeliveryApiError("delivery_automatic_repair_unavailable", 409)
        reference = request.expected_accepted_reference
        if reference.scope != scope or reference.binding.slot.kind != WorkKind.SEARCH:
            raise DeliveryApiError("delivery_reprojection_reference_conflict")
        digest = fingerprint("delivery.reprojection-key", request.idempotency_key)
        body = fingerprint(
            "delivery.reprojection-request", {"scope": scope, "request": request}
        )
        runtime = self._runtime
        with runtime.session() as session, session.begin():
            repo = SqlAlchemyDeliveryRepository(session)
            repo.lock_project_admission(scope.project_id)
            prior = session.scalar(
                select(SearchReprojectionOperation).where(
                    SearchReprojectionOperation.actor_id == principal.actor_id,
                    SearchReprojectionOperation.project_id == scope.project_id,
                    SearchReprojectionOperation.key_digest == digest,
                )
            )
            if prior is not None:
                if prior.request_fingerprint != body:
                    raise DeliveryApiError("delivery_idempotency_conflict")
                return SearchReprojectionAccepted.model_validate_json(
                    json.dumps(prior.response_snapshot)
                )
            try:
                bundle, work = repo.lock_work(
                    request.expected_predecessor_work_id, scope.project_id
                )
            except DeliveryOwnershipLost as exc:
                raise DeliveryApiError("delivery_not_found", 404) from exc
            identity = WorkIdentity.model_validate_json(json.dumps(work.identity))
            if (
                identity.scope != scope
                or identity.binding != reference.binding
                or identity.input_fingerprint != reference.input_fingerprint
                or work.kind != WorkKind.SEARCH
                or work.template != ""
                or not work.is_current
                or work.state != "COMPLETED"
            ):
                raise DeliveryApiError("delivery_reprojection_conflict")
            output = session.scalar(select(Output).where(Output.work_id == work.id))
            if output is None:
                raise DeliveryApiError("delivery_reprojection_reference_conflict")
            receipt = PublicationReceipt.model_validate_json(json.dumps(output.receipt))
            if (
                receipt.accepted.reference != reference
                or receipt.prepared.attempt.work != identity
                or output.attempt_id != receipt.prepared.attempt.attempt_id
                or output.fence != receipt.prepared.attempt.fence
            ):
                raise DeliveryApiError("delivery_reprojection_reference_conflict")
            if (
                bundle.eligibility != "ELIGIBLE"
                or not work.dependencies_ready
                or not runtime.execution_enabled
                or not runtime.dispatch_enabled
                or bundle.runtime_profile != runtime.budgets.model_dump(mode="json")
            ):
                raise DeliveryApiError("delivery_runtime_unavailable", 503)
            try:
                runtime.registry.resolve(identity.binding)
            except HandlerUnavailable as exc:
                raise DeliveryApiError("delivery_handler_unavailable", 503) from exc
            if not runtime.fleet_ready(session, identity.binding):
                raise DeliveryApiError("delivery_worker_unavailable", 503)
            policy = self._policy
            rounds = (
                session.scalar(
                    select(func.count())
                    .select_from(SearchReprojectionOperation)
                    .join(
                        Work, Work.id == SearchReprojectionOperation.predecessor_work_id
                    )
                    .where(Work.bundle_id == bundle.id)
                )
                or 0
            )
            if policy is None or rounds >= policy.max_rounds:
                raise DeliveryApiError("delivery_reprojection_policy_unavailable")
            since = repo.now() - timedelta(seconds=policy.window_seconds)
            recent = (
                select(func.count())
                .select_from(SearchReprojectionOperation)
                .where(
                    SearchReprojectionOperation.project_id == scope.project_id,
                    SearchReprojectionOperation.created_at >= since,
                )
            )
            if (session.scalar(recent) or 0) >= policy.max_project_requests or (
                session.scalar(
                    recent.where(
                        SearchReprojectionOperation.actor_id == principal.actor_id
                    )
                )
                or 0
            ) >= policy.max_actor_requests:
                raise DeliveryApiError("delivery_reprojection_admission_wait")
            successor = WorkIdentity.model_validate(
                identity.model_copy(
                    update={"work_id": uuid4(), "run_number": identity.run_number + 1}
                )
            )
            work.is_current = False
            session.flush()
            session.add(
                Work(
                    id=successor.work_id,
                    bundle_id=bundle.id,
                    identity=successor.model_dump(mode="json"),
                    kind=work.kind,
                    template=work.template,
                    run_number=successor.run_number,
                    is_current=True,
                    dependencies_ready=True,
                    state="PENDING",
                    fence=0,
                    executions=0,
                    dispatch_epoch=uuid4(),
                    next_eligible_at=repo.now(),
                    safe_reason="handler_unavailable",
                    created_at=repo.now(),
                )
            )
            session.flush()
            result = SearchReprojectionAccepted(
                scope=scope,
                operation_id=uuid4(),
                predecessor_work_id=work.id,
                new_work_id=successor.work_id,
                input_fingerprint=identity.input_fingerprint,
                profile_fingerprint=fingerprint(
                    "delivery.reprojection-profile", identity.binding
                ),
                reason=request.reason,
            )
            session.add(
                SearchReprojectionOperation(
                    id=result.operation_id,
                    project_id=scope.project_id,
                    actor_id=principal.actor_id,
                    key_digest=digest,
                    request_fingerprint=body,
                    request_snapshot={
                        "scope": scope.model_dump(mode="json"),
                        "request": request.model_dump(mode="json"),
                        "principal": principal.model_dump(mode="json"),
                    },
                    response_snapshot=result.model_dump(mode="json"),
                    predecessor_work_id=work.id,
                    successor_work_id=successor.work_id,
                    created_at=repo.now(),
                )
            )
            return result
