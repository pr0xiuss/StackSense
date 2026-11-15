"""SQLAlchemy persistence for the P4 projection lifecycle control plane."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    select,
    text,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.platform.graph.model import (
    ACTIVE_ATTEMPT_STATES,
    GRAPH_SCHEMA_VERSION,
    MAX_EXECUTIONS,
    PROJECTION_CONTRACT_VERSION,
    PROJECTION_TYPE,
    PROJECTOR_VERSION,
    ActivationDisposition,
    ActivationResult,
    ProjectionActorType,
    ProjectionAttempt,
    ProjectionAttemptState,
    ProjectionCounts,
    ProjectionLease,
    ProjectionPublicState,
    ProjectionResource,
    ProjectionWorkClaim,
    VerificationReceipt,
)
from backend.platform.graph.repository import (
    DispatchCandidate,
    EnsureProjectionResult,
    GraphLifecycleIntegrityError,
    GraphLifecycleStateError,
    GraphProjectionRepository,
)
from backend.platform.graph.source import PublishedArchitectureHeader
from backend.platform.projects.domain.project_role import ProjectRole
from backend.platform.projects.infra.base import Base


class GraphProjectionResourceModel(Base):
    __tablename__ = "graph_projection_resources"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    architecture_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    repository_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    architecture_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    projection_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_content_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    source_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    active_generation_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    active_projector_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    active_graph_schema_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    active_payload_digest: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    active_entity_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_relationship_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    active_evidence_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_unresolved_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_conflict_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_failure_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "architecture_version_id",
            "projection_type",
            name="uq_graph_projection_resource_version_type",
        ),
        UniqueConstraint(
            "id", "active_generation_id", name="uq_graph_resource_active_generation"
        ),
        CheckConstraint(
            "architecture_sequence > 0", name="ck_graph_resource_sequence_positive"
        ),
        CheckConstraint("version > 0", name="ck_graph_resource_version_positive"),
        CheckConstraint(
            "state IN ('PENDING','RUNNING','COMPLETED','FAILED','STALE')",
            name="ck_graph_resource_state",
        ),
        CheckConstraint(
            "((state IN ('COMPLETED','STALE') AND active_generation_id IS NOT NULL) "
            "OR (state IN ('PENDING','RUNNING','FAILED') AND "
            "active_generation_id IS NULL))",
            name="ck_graph_resource_state_active_generation",
        ),
        CheckConstraint(
            "((active_generation_id IS NULL AND active_projector_version IS NULL "
            "AND active_graph_schema_version IS NULL AND active_payload_digest IS NULL "
            "AND active_entity_count IS NULL AND active_relationship_count IS NULL "
            "AND active_evidence_count IS NULL AND active_unresolved_count IS NULL "
            "AND active_conflict_count IS NULL) OR (active_generation_id IS NOT NULL "
            "AND active_projector_version IS NOT NULL "
            "AND active_graph_schema_version IS NOT NULL "
            "AND active_payload_digest IS NOT NULL "
            "AND active_entity_count IS NOT NULL "
            "AND active_relationship_count IS NOT NULL "
            "AND active_evidence_count IS NOT NULL "
            "AND active_unresolved_count IS NOT NULL "
            "AND active_conflict_count IS NOT NULL AND active_entity_count >= 0 "
            "AND active_relationship_count >= 0 AND active_evidence_count >= 0 "
            "AND active_unresolved_count >= 0 AND active_conflict_count >= 0))",
            name="ck_graph_resource_active_summary",
        ),
        ForeignKeyConstraint(
            ["id", "active_generation_id"],
            [
                "graph_projection_attempts.resource_id",
                "graph_projection_attempts.generation_id",
            ],
            name="fk_graph_resource_active_generation",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        Index(
            "ix_graph_resource_project_version", "project_id", "architecture_version_id"
        ),
        Index(
            "ix_graph_resource_repository_sequence",
            "repository_id",
            "architecture_sequence",
        ),
        Index("ix_graph_resource_state", "state"),
    )
    __mapper_args__ = {"version_id_col": version}


class GraphProjectionAttemptModel(Base):
    __tablename__ = "graph_projection_attempts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("graph_projection_resources.id", ondelete="CASCADE"),
        nullable=False,
    )
    generation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, unique=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_content_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    source_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    graph_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    projector_version: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dispatch_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expected_entity_count: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_relationship_count: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_unresolved_count: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_conflict_count: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_entity_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_relationship_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    actual_evidence_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_unresolved_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_conflict_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_key_set_digest: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    actual_key_set_digest: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    expected_endpoint_digest: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    actual_endpoint_digest: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    expected_payload_digest: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    actual_payload_digest: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "resource_id", "generation_id", name="uq_graph_attempt_resource_generation"
        ),
        UniqueConstraint(
            "resource_id", "attempt_number", name="uq_graph_attempt_resource_number"
        ),
        CheckConstraint("attempt_number > 0", name="ck_graph_attempt_number_positive"),
        CheckConstraint("version > 0", name="ck_graph_attempt_version_positive"),
        CheckConstraint(
            "state IN ('QUEUED','RUNNING','RETRYING','COMPLETED','FAILED',"
            "'SUPERSEDED')",
            name="ck_graph_attempt_state",
        ),
        CheckConstraint(
            "actor_type IN ('SYSTEM','USER')", name="ck_graph_attempt_actor_type"
        ),
        CheckConstraint(
            "((actor_type = 'SYSTEM' AND actor_id IS NULL AND actor_role IS NULL) OR "
            "(actor_type = 'USER' AND actor_id IS NOT NULL AND "
            "actor_role IS NOT NULL))",
            name="ck_graph_attempt_actor_fields",
        ),
        CheckConstraint(
            "execution_count >= 0 AND execution_count <= 3 AND dispatch_count >= 0",
            name="ck_graph_attempt_counts",
        ),
        CheckConstraint(
            "expected_entity_count >= 0 AND expected_relationship_count >= 0 AND "
            "expected_evidence_count >= 0 AND expected_unresolved_count >= 0 AND "
            "expected_conflict_count >= 0",
            name="ck_graph_attempt_expected_counts",
        ),
        CheckConstraint(
            "((actual_entity_count IS NULL AND actual_relationship_count IS NULL "
            "AND actual_evidence_count IS NULL AND actual_unresolved_count IS NULL "
            "AND actual_conflict_count IS NULL) OR (actual_entity_count IS NOT NULL "
            "AND actual_relationship_count IS NOT NULL "
            "AND actual_evidence_count IS NOT NULL "
            "AND actual_unresolved_count IS NOT NULL "
            "AND actual_conflict_count IS NOT NULL AND actual_entity_count >= 0 AND "
            "actual_relationship_count >= 0 AND actual_evidence_count >= 0 AND "
            "actual_unresolved_count >= 0 AND actual_conflict_count >= 0))",
            name="ck_graph_attempt_actual_counts",
        ),
        CheckConstraint(
            "((state = 'RUNNING' AND lease_owner IS NOT NULL AND "
            "lease_token IS NOT NULL "
            "AND lease_heartbeat_at IS NOT NULL AND lease_expires_at IS NOT NULL) OR "
            "(state <> 'RUNNING' AND lease_owner IS NULL AND lease_token IS NULL "
            "AND lease_heartbeat_at IS NULL AND lease_expires_at IS NULL))",
            name="ck_graph_attempt_lease_state",
        ),
        Index(
            "uq_graph_attempt_one_active",
            "resource_id",
            unique=True,
            postgresql_where=text("state IN ('QUEUED','RUNNING','RETRYING')"),
            sqlite_where=text("state IN ('QUEUED','RUNNING','RETRYING')"),
        ),
        Index("ix_graph_attempt_undispatched", "state", "dispatched_at"),
        Index("ix_graph_attempt_expired_lease", "state", "lease_expires_at"),
        Index("ix_graph_attempt_resource_history", "resource_id", "attempt_number"),
        Index("ix_graph_attempt_correlation", "correlation_id"),
    )
    __mapper_args__ = {"version_id_col": version}


class GraphRuntimeCapabilityModel(Base):
    """Expiring evidence that scheduled work reached a graph-queue worker."""

    __tablename__ = "graph_runtime_capabilities"

    capability: Mapped[str] = mapped_column(String(64), primary_key=True)
    worker_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    ready: Mapped[bool] = mapped_column(Boolean, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "capability IN ('reconciliation_scheduling','projection_execution')",
            name="ck_graph_runtime_capability_name",
        ),
        Index("ix_graph_runtime_capability_observed", "capability", "observed_at"),
    )


class SqlAlchemyGraphProjectionRepository(GraphProjectionRepository):
    """PostgreSQL adapter; callers own commit and rollback boundaries."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_with_initial_attempt(
        self,
        header: PublishedArchitectureHeader,
        *,
        correlation_id: str,
    ) -> EnsureProjectionResult:
        existing = self._resource_for_version(header.architecture_version_id, lock=True)
        if existing is not None:
            self._assert_resource_scope(existing, header)
            active = self._active_attempt(existing.id)
            return EnsureProjectionResult(
                self._resource(existing),
                None if active is None else self._attempt(active),
                False,
            )
        now = datetime.now(UTC)
        resource = GraphProjectionResourceModel(
            id=uuid4(),
            architecture_version_id=header.architecture_version_id,
            project_id=header.project_id,
            repository_id=header.repository_id,
            architecture_sequence=header.sequence_number,
            projection_type=PROJECTION_TYPE,
            source_content_digest=header.content_digest,
            source_schema_version=header.architecture_schema_version,
            state=ProjectionPublicState.PENDING.value,
            active_generation_id=None,
            active_projector_version=None,
            active_graph_schema_version=None,
            active_payload_digest=None,
            active_entity_count=None,
            active_relationship_count=None,
            active_evidence_count=None,
            active_unresolved_count=None,
            active_conflict_count=None,
            last_failure_code=None,
            last_failure_message=None,
            version=1,
            created_at=now,
            updated_at=now,
            activated_at=None,
        )
        attempt = self._new_attempt(
            resource,
            attempt_number=1,
            actor_type=ProjectionActorType.SYSTEM,
            actor_id=None,
            actor_role=None,
            correlation_id=correlation_id,
            expected_counts=header.counts,
            now=now,
        )
        try:
            with self._session.begin_nested():
                self._session.add(resource)
                self._session.flush()
                self._session.add(attempt)
                self._session.flush()
        except IntegrityError:
            existing = self._resource_for_version(
                header.architecture_version_id, lock=True
            )
            if existing is None:
                raise
            self._assert_resource_scope(existing, header)
            active = self._active_attempt(existing.id)
            return EnsureProjectionResult(
                self._resource(existing),
                None if active is None else self._attempt(active),
                False,
            )
        return EnsureProjectionResult(
            self._resource(resource), self._attempt(attempt), True
        )

    def create_rebuild_attempt(
        self,
        resource_id: UUID,
        *,
        actor_type: ProjectionActorType,
        actor_id: UUID | None,
        actor_role: str | None,
        correlation_id: str,
    ) -> ProjectionAttempt:
        resource = self._required_resource(resource_id, lock=True)
        current = self._active_attempt(resource_id)
        if current is not None:
            return self._attempt(current)
        if actor_type is ProjectionActorType.USER:
            normalized_role = "" if actor_role is None else actor_role.strip().lower()
            if actor_id is None or normalized_role not in {
                ProjectRole.OWNER.value,
                ProjectRole.ADMIN.value,
            }:
                raise GraphLifecycleStateError("rebuild requires OWNER or ADMIN")
            actor_role = normalized_role
        next_number = (
            int(
                self._session.scalar(
                    select(func.max(GraphProjectionAttemptModel.attempt_number)).where(
                        GraphProjectionAttemptModel.resource_id == resource_id
                    )
                )
                or 0
            )
            + 1
        )
        now = datetime.now(UTC)
        attempt = self._new_attempt(
            resource,
            attempt_number=next_number,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_role=actor_role,
            correlation_id=correlation_id,
            expected_counts=self._source_counts(resource),
            now=now,
        )
        try:
            with self._session.begin_nested():
                self._session.add(attempt)
                self._session.flush()
        except IntegrityError:
            current = self._active_attempt(resource_id)
            if current is None:
                raise
            return self._attempt(current)
        if resource.active_generation_id is None:
            resource.state = ProjectionPublicState.PENDING.value
            resource.updated_at = now
        self._session.flush()
        return self._attempt(attempt)

    def get_resource(self, resource_id: UUID) -> ProjectionResource | None:
        model = self._session.get(GraphProjectionResourceModel, resource_id)
        return None if model is None else self._resource(model)

    def get_attempt(self, attempt_id: UUID) -> ProjectionAttempt | None:
        model = self._session.get(GraphProjectionAttemptModel, attempt_id)
        return None if model is None else self._attempt(model)

    def mark_dispatched(self, attempt_id: UUID, *, at: datetime) -> ProjectionAttempt:
        attempt = self._required_attempt(attempt_id, lock=True)
        if ProjectionAttemptState(attempt.state) not in {
            ProjectionAttemptState.QUEUED,
            ProjectionAttemptState.RETRYING,
        }:
            raise GraphLifecycleStateError("attempt is not dispatchable")
        attempt.dispatch_count += 1
        attempt.dispatched_at = at
        attempt.updated_at = at
        self._session.flush()
        return self._attempt(attempt)

    def list_dispatch_candidates(
        self,
        *,
        now: datetime,
        dispatched_before: datetime,
        retry_ready_before: datetime,
        limit: int,
    ) -> tuple[DispatchCandidate, ...]:
        if not 1 <= limit <= 500:
            raise ValueError("dispatch candidate limit must be 1..500")
        statement = (
            select(GraphProjectionAttemptModel, GraphProjectionResourceModel)
            .join(
                GraphProjectionResourceModel,
                GraphProjectionResourceModel.id
                == GraphProjectionAttemptModel.resource_id,
            )
            .where(
                GraphProjectionAttemptModel.state.in_(
                    (
                        ProjectionAttemptState.QUEUED.value,
                        ProjectionAttemptState.RETRYING.value,
                    )
                ),
                (
                    GraphProjectionAttemptModel.dispatched_at.is_(None)
                    | (GraphProjectionAttemptModel.dispatched_at <= dispatched_before)
                ),
                (
                    (
                        GraphProjectionAttemptModel.state
                        == ProjectionAttemptState.QUEUED.value
                    )
                    | (GraphProjectionAttemptModel.updated_at <= retry_ready_before)
                ),
            )
            .order_by(
                GraphProjectionAttemptModel.updated_at,
                GraphProjectionAttemptModel.id,
            )
            .limit(limit)
        )
        rows = self._session.execute(statement).all()
        return tuple(
            DispatchCandidate(
                resource=self._resource(resource), attempt=self._attempt(attempt)
            )
            for attempt, resource in rows
        )

    def list_expired_attempt_ids(
        self, *, now: datetime, limit: int
    ) -> tuple[UUID, ...]:
        if not 1 <= limit <= 500:
            raise ValueError("expired attempt limit must be 1..500")
        return tuple(
            self._session.scalars(
                select(GraphProjectionAttemptModel.id)
                .where(
                    GraphProjectionAttemptModel.state
                    == ProjectionAttemptState.RUNNING.value,
                    GraphProjectionAttemptModel.lease_expires_at.is_not(None),
                    GraphProjectionAttemptModel.lease_expires_at <= now,
                )
                .order_by(
                    GraphProjectionAttemptModel.lease_expires_at,
                    GraphProjectionAttemptModel.id,
                )
                .limit(limit)
            )
        )

    def acquire_lease(
        self,
        claim: ProjectionWorkClaim,
        *,
        worker_id: str,
        now: datetime,
        duration: timedelta,
    ) -> ProjectionLease | None:
        if not worker_id or duration <= timedelta(0):
            raise ValueError("worker and positive lease duration are required")
        attempt = self._required_attempt(claim.attempt_id, lock=True)
        resource = self._required_resource(attempt.resource_id, lock=True)
        if (
            claim.projection_id != resource.id
            or claim.project_id != resource.project_id
            or claim.architecture_version_id != resource.architecture_version_id
            or claim.generation_id != attempt.generation_id
            or claim.contract_version != attempt.contract_version
            or claim.correlation_id != attempt.correlation_id
        ):
            raise GraphLifecycleIntegrityError(
                "worker payload does not match persisted projection scope"
            )
        if ProjectionAttemptState(attempt.state) not in {
            ProjectionAttemptState.QUEUED,
            ProjectionAttemptState.RETRYING,
        }:
            return None
        if attempt.execution_count >= MAX_EXECUTIONS:
            return None
        token = secrets.token_urlsafe(32)
        expires_at = now + duration
        attempt.state = ProjectionAttemptState.RUNNING.value
        attempt.execution_count += 1
        attempt.lease_owner = worker_id
        attempt.lease_token = token
        attempt.lease_heartbeat_at = now
        attempt.lease_expires_at = expires_at
        attempt.updated_at = now
        if resource.active_generation_id is None:
            resource.state = ProjectionPublicState.RUNNING.value
            resource.updated_at = now
        self._session.flush()
        return ProjectionLease(
            resource_id=attempt.resource_id,
            attempt_id=attempt.id,
            generation_id=attempt.generation_id,
            worker_id=worker_id,
            token=token,
            expires_at=expires_at,
        )

    def heartbeat(
        self,
        lease: ProjectionLease,
        *,
        now: datetime,
        duration: timedelta,
    ) -> ProjectionLease | None:
        attempt = self._required_attempt(lease.attempt_id, lock=True)
        if not self._valid_lease(attempt, lease, now) or duration <= timedelta(0):
            return None
        expires_at = now + duration
        attempt.lease_heartbeat_at = now
        attempt.lease_expires_at = expires_at
        attempt.updated_at = now
        self._session.flush()
        return ProjectionLease(
            resource_id=lease.resource_id,
            attempt_id=lease.attempt_id,
            generation_id=lease.generation_id,
            worker_id=lease.worker_id,
            token=lease.token,
            expires_at=expires_at,
        )

    def record_execution_failure(
        self,
        lease: ProjectionLease,
        *,
        now: datetime,
        failure_code: str,
        failure_message: str,
        transient: bool,
    ) -> ProjectionAttempt:
        attempt = self._required_attempt(lease.attempt_id, lock=True)
        if not self._valid_lease(attempt, lease, now):
            raise GraphLifecycleStateError("lease is stale or expired")
        resource = self._required_resource(attempt.resource_id, lock=True)
        attempt.failure_code = _safe_text(failure_code, 100)
        attempt.failure_message = _safe_text(failure_message, 500)
        attempt.updated_at = now
        self._clear_lease(attempt)
        if transient and attempt.execution_count < MAX_EXECUTIONS:
            attempt.state = ProjectionAttemptState.RETRYING.value
            if resource.active_generation_id is None:
                resource.state = ProjectionPublicState.RUNNING.value
        else:
            attempt.state = ProjectionAttemptState.FAILED.value
            attempt.completed_at = now
            resource.last_failure_code = attempt.failure_code
            resource.last_failure_message = attempt.failure_message
            if resource.active_generation_id is None:
                resource.state = ProjectionPublicState.FAILED.value
        resource.updated_at = now
        self._session.flush()
        return self._attempt(attempt)

    def recover_expired_attempt(
        self,
        attempt_id: UUID,
        *,
        now: datetime,
    ) -> ProjectionAttempt | None:
        attempt = self._required_attempt(attempt_id, lock=True)
        if (
            ProjectionAttemptState(attempt.state) is not ProjectionAttemptState.RUNNING
            or attempt.lease_expires_at is None
            or _ensure_utc(attempt.lease_expires_at) > _ensure_utc(now)
        ):
            return None
        resource = self._required_resource(attempt.resource_id, lock=True)
        attempt.failure_code = "GRAPH_PROJECTION_LEASE_EXPIRED"
        attempt.failure_message = "Projection worker lease expired."
        attempt.updated_at = now
        self._clear_lease(attempt)
        if attempt.execution_count < MAX_EXECUTIONS:
            attempt.state = ProjectionAttemptState.RETRYING.value
            if resource.active_generation_id is None:
                resource.state = ProjectionPublicState.RUNNING.value
        else:
            attempt.state = ProjectionAttemptState.FAILED.value
            attempt.completed_at = now
            resource.last_failure_code = attempt.failure_code
            resource.last_failure_message = attempt.failure_message
            if resource.active_generation_id is None:
                resource.state = ProjectionPublicState.FAILED.value
        resource.updated_at = now
        self._session.flush()
        return self._attempt(attempt)

    def activate_verified(
        self,
        receipt: VerificationReceipt,
        *,
        now: datetime,
    ) -> ActivationResult:
        resource = self._required_resource(receipt.resource_id, lock=True)
        attempt = self._required_attempt(receipt.attempt_id, lock=True)
        self._assert_receipt_scope(resource, attempt, receipt)
        if (
            ProjectionAttemptState(attempt.state) is ProjectionAttemptState.COMPLETED
            and resource.active_generation_id == receipt.generation_id
        ):
            return ActivationResult(
                ActivationDisposition.ALREADY_ACTIVATED,
                self._resource(resource),
                self._attempt(attempt),
            )
        lease = ProjectionLease(
            resource_id=receipt.resource_id,
            attempt_id=receipt.attempt_id,
            generation_id=receipt.generation_id,
            worker_id=receipt.lease_owner,
            token=receipt.lease_token,
            expires_at=attempt.lease_expires_at or now,
        )
        if not self._valid_lease(attempt, lease, now):
            return ActivationResult(
                ActivationDisposition.REJECTED_STALE,
                self._resource(resource),
                self._attempt(attempt),
            )
        self._copy_verification(attempt, receipt)
        if not receipt.summaries_match():
            attempt.state = ProjectionAttemptState.FAILED.value
            attempt.failure_code = _safe_text(
                receipt.failure_code or "GRAPH_PROJECTION_VERIFICATION_FAILED", 100
            )
            attempt.failure_message = _safe_text(
                receipt.failure_message or "Candidate graph verification failed.", 500
            )
            attempt.completed_at = now
            attempt.updated_at = now
            self._clear_lease(attempt)
            resource.last_failure_code = attempt.failure_code
            resource.last_failure_message = attempt.failure_message
            if resource.active_generation_id is None:
                resource.state = ProjectionPublicState.FAILED.value
            resource.updated_at = now
            self._session.flush()
            return ActivationResult(
                ActivationDisposition.RECORDED_FAILURE,
                self._resource(resource),
                self._attempt(attempt),
            )

        newest_sequence = int(
            self._session.scalar(
                select(
                    func.max(GraphProjectionResourceModel.architecture_sequence)
                ).where(
                    GraphProjectionResourceModel.repository_id
                    == resource.repository_id,
                    GraphProjectionResourceModel.projection_type
                    == resource.projection_type,
                )
            )
            or resource.architecture_sequence
        )
        attempt.state = ProjectionAttemptState.COMPLETED.value
        attempt.completed_at = now
        attempt.updated_at = now
        attempt.failure_code = None
        attempt.failure_message = None
        self._clear_lease(attempt)
        resource.active_generation_id = attempt.generation_id
        resource.active_projector_version = attempt.projector_version
        resource.active_graph_schema_version = attempt.graph_schema_version
        resource.active_payload_digest = receipt.actual_payload_digest
        self._set_active_counts(
            resource, receipt.actual_counts or receipt.expected_counts
        )
        resource.state = (
            ProjectionPublicState.COMPLETED.value
            if resource.architecture_sequence >= newest_sequence
            else ProjectionPublicState.STALE.value
        )
        resource.last_failure_code = None
        resource.last_failure_message = None
        resource.activated_at = now
        resource.updated_at = now
        self._session.flush()
        return ActivationResult(
            ActivationDisposition.ACTIVATED,
            self._resource(resource),
            self._attempt(attempt),
        )

    def mark_older_resources_stale(
        self, header: PublishedArchitectureHeader, *, now: datetime
    ) -> int:
        result = self._session.execute(
            update(GraphProjectionResourceModel)
            .where(
                GraphProjectionResourceModel.repository_id == header.repository_id,
                GraphProjectionResourceModel.projection_type == PROJECTION_TYPE,
                GraphProjectionResourceModel.architecture_sequence
                < header.sequence_number,
                GraphProjectionResourceModel.active_generation_id.is_not(None),
                GraphProjectionResourceModel.state
                == ProjectionPublicState.COMPLETED.value,
            )
            .values(state=ProjectionPublicState.STALE.value, updated_at=now)
            .values(version=GraphProjectionResourceModel.version + 1)
        )
        return int(getattr(result, "rowcount", 0) or 0)

    def _new_attempt(
        self,
        resource: GraphProjectionResourceModel,
        *,
        attempt_number: int,
        actor_type: ProjectionActorType,
        actor_id: UUID | None,
        actor_role: str | None,
        correlation_id: str,
        expected_counts: ProjectionCounts,
        now: datetime,
    ) -> GraphProjectionAttemptModel:
        if not 1 <= len(correlation_id) <= 255:
            raise ValueError("correlation ID must contain 1..255 characters")
        return GraphProjectionAttemptModel(
            id=uuid4(),
            resource_id=resource.id,
            generation_id=uuid4(),
            attempt_number=attempt_number,
            state=ProjectionAttemptState.QUEUED.value,
            actor_type=actor_type.value,
            actor_id=actor_id,
            actor_role=actor_role,
            correlation_id=correlation_id,
            contract_version=PROJECTION_CONTRACT_VERSION,
            source_content_digest=resource.source_content_digest,
            source_schema_version=resource.source_schema_version,
            graph_schema_version=GRAPH_SCHEMA_VERSION,
            projector_version=PROJECTOR_VERSION,
            execution_count=0,
            dispatch_count=0,
            dispatched_at=None,
            lease_owner=None,
            lease_token=None,
            lease_heartbeat_at=None,
            lease_expires_at=None,
            expected_entity_count=expected_counts.entities,
            expected_relationship_count=expected_counts.relationships,
            expected_evidence_count=expected_counts.evidence,
            expected_unresolved_count=expected_counts.unresolved,
            expected_conflict_count=expected_counts.conflicts,
            actual_entity_count=None,
            actual_relationship_count=None,
            actual_evidence_count=None,
            actual_unresolved_count=None,
            actual_conflict_count=None,
            expected_key_set_digest=None,
            actual_key_set_digest=None,
            expected_endpoint_digest=None,
            actual_endpoint_digest=None,
            expected_payload_digest=None,
            actual_payload_digest=None,
            failure_code=None,
            failure_message=None,
            version=1,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )

    def _resource_for_version(
        self, architecture_version_id: UUID, *, lock: bool
    ) -> GraphProjectionResourceModel | None:
        statement = select(GraphProjectionResourceModel).where(
            GraphProjectionResourceModel.architecture_version_id
            == architecture_version_id,
            GraphProjectionResourceModel.projection_type == PROJECTION_TYPE,
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def _required_resource(
        self, resource_id: UUID, *, lock: bool
    ) -> GraphProjectionResourceModel:
        statement = select(GraphProjectionResourceModel).where(
            GraphProjectionResourceModel.id == resource_id
        )
        if lock:
            statement = statement.with_for_update()
        model = self._session.scalar(statement)
        if model is None:
            raise GraphLifecycleStateError("projection resource not found")
        return model

    def _required_attempt(
        self, attempt_id: UUID, *, lock: bool
    ) -> GraphProjectionAttemptModel:
        statement = select(GraphProjectionAttemptModel).where(
            GraphProjectionAttemptModel.id == attempt_id
        )
        if lock:
            statement = statement.with_for_update()
        model = self._session.scalar(statement)
        if model is None:
            raise GraphLifecycleStateError("projection attempt not found")
        return model

    def _active_attempt(self, resource_id: UUID) -> GraphProjectionAttemptModel | None:
        return self._session.scalar(
            select(GraphProjectionAttemptModel)
            .where(
                GraphProjectionAttemptModel.resource_id == resource_id,
                GraphProjectionAttemptModel.state.in_(
                    tuple(state.value for state in ACTIVE_ATTEMPT_STATES)
                ),
            )
            .with_for_update()
        )

    @staticmethod
    def _assert_resource_scope(
        resource: GraphProjectionResourceModel,
        header: PublishedArchitectureHeader,
    ) -> None:
        actual = (
            resource.project_id,
            resource.repository_id,
            resource.architecture_sequence,
            resource.source_content_digest,
            resource.source_schema_version,
        )
        supplied = (
            header.project_id,
            header.repository_id,
            header.sequence_number,
            header.content_digest,
            header.architecture_schema_version,
        )
        if actual != supplied:
            raise GraphLifecycleIntegrityError(
                "Architecture Version already owns a different projection scope"
            )

    @staticmethod
    def _assert_receipt_scope(
        resource: GraphProjectionResourceModel,
        attempt: GraphProjectionAttemptModel,
        receipt: VerificationReceipt,
    ) -> None:
        expected = (
            resource.id,
            attempt.id,
            attempt.resource_id,
            attempt.generation_id,
            resource.project_id,
            resource.architecture_version_id,
            attempt.contract_version,
            attempt.source_content_digest,
            attempt.source_schema_version,
            attempt.graph_schema_version,
            attempt.projector_version,
            ProjectionCounts(
                entities=attempt.expected_entity_count,
                relationships=attempt.expected_relationship_count,
                evidence=attempt.expected_evidence_count,
                unresolved=attempt.expected_unresolved_count,
                conflicts=attempt.expected_conflict_count,
            ),
        )
        supplied = (
            receipt.resource_id,
            receipt.attempt_id,
            receipt.resource_id,
            receipt.generation_id,
            receipt.project_id,
            receipt.architecture_version_id,
            receipt.contract_version,
            receipt.source_content_digest,
            receipt.source_schema_version,
            receipt.graph_schema_version,
            receipt.projector_version,
            receipt.expected_counts,
        )
        if expected != supplied:
            raise GraphLifecycleIntegrityError("verification receipt scope mismatch")

    @staticmethod
    def _valid_lease(
        attempt: GraphProjectionAttemptModel,
        lease: ProjectionLease,
        now: datetime,
    ) -> bool:
        return (
            ProjectionAttemptState(attempt.state) is ProjectionAttemptState.RUNNING
            and attempt.resource_id == lease.resource_id
            and attempt.generation_id == lease.generation_id
            and attempt.lease_owner == lease.worker_id
            and secrets.compare_digest(attempt.lease_token or "", lease.token)
            and attempt.lease_expires_at is not None
            and _ensure_utc(attempt.lease_expires_at) > _ensure_utc(now)
        )

    @staticmethod
    def _clear_lease(attempt: GraphProjectionAttemptModel) -> None:
        attempt.lease_owner = None
        attempt.lease_token = None
        attempt.lease_heartbeat_at = None
        attempt.lease_expires_at = None

    @staticmethod
    def _copy_verification(
        attempt: GraphProjectionAttemptModel, receipt: VerificationReceipt
    ) -> None:
        actual = receipt.actual_counts
        if actual is not None:
            attempt.actual_entity_count = actual.entities
            attempt.actual_relationship_count = actual.relationships
            attempt.actual_evidence_count = actual.evidence
            attempt.actual_unresolved_count = actual.unresolved
            attempt.actual_conflict_count = actual.conflicts
        attempt.expected_key_set_digest = receipt.expected_key_set_digest
        attempt.actual_key_set_digest = receipt.actual_key_set_digest
        attempt.expected_endpoint_digest = receipt.expected_endpoint_digest
        attempt.actual_endpoint_digest = receipt.actual_endpoint_digest
        attempt.expected_payload_digest = receipt.expected_payload_digest
        attempt.actual_payload_digest = receipt.actual_payload_digest

    @staticmethod
    def _set_active_counts(
        resource: GraphProjectionResourceModel, counts: ProjectionCounts
    ) -> None:
        resource.active_entity_count = counts.entities
        resource.active_relationship_count = counts.relationships
        resource.active_evidence_count = counts.evidence
        resource.active_unresolved_count = counts.unresolved
        resource.active_conflict_count = counts.conflicts

    def _source_counts(
        self, resource: GraphProjectionResourceModel
    ) -> ProjectionCounts:
        first = self._session.scalar(
            select(GraphProjectionAttemptModel)
            .where(GraphProjectionAttemptModel.resource_id == resource.id)
            .order_by(GraphProjectionAttemptModel.attempt_number)
            .limit(1)
        )
        if first is None:
            raise GraphLifecycleIntegrityError(
                "projection resource is missing immutable source expectations"
            )
        return ProjectionCounts(
            entities=first.expected_entity_count,
            relationships=first.expected_relationship_count,
            evidence=first.expected_evidence_count,
            unresolved=first.expected_unresolved_count,
            conflicts=first.expected_conflict_count,
        )

    @staticmethod
    def _resource(model: GraphProjectionResourceModel) -> ProjectionResource:
        active_counts = None
        if model.active_entity_count is not None:
            active_counts = ProjectionCounts(
                entities=model.active_entity_count,
                relationships=model.active_relationship_count or 0,
                evidence=model.active_evidence_count or 0,
                unresolved=model.active_unresolved_count or 0,
                conflicts=model.active_conflict_count or 0,
            )
        return ProjectionResource(
            id=model.id,
            architecture_version_id=model.architecture_version_id,
            project_id=model.project_id,
            repository_id=model.repository_id,
            architecture_sequence=model.architecture_sequence,
            projection_type=model.projection_type,
            source_content_digest=model.source_content_digest,
            source_schema_version=model.source_schema_version,
            state=ProjectionPublicState(model.state),
            active_generation_id=model.active_generation_id,
            active_projector_version=model.active_projector_version,
            active_graph_schema_version=model.active_graph_schema_version,
            active_payload_digest=model.active_payload_digest,
            active_counts=active_counts,
            last_failure_code=model.last_failure_code,
            last_failure_message=model.last_failure_message,
            version=model.version,
            created_at=_ensure_utc(model.created_at),
            updated_at=_ensure_utc(model.updated_at),
            activated_at=(
                None if model.activated_at is None else _ensure_utc(model.activated_at)
            ),
        )

    @staticmethod
    def _attempt(model: GraphProjectionAttemptModel) -> ProjectionAttempt:
        actual_counts = None
        if model.actual_entity_count is not None:
            actual_counts = ProjectionCounts(
                entities=model.actual_entity_count,
                relationships=model.actual_relationship_count or 0,
                evidence=model.actual_evidence_count or 0,
                unresolved=model.actual_unresolved_count or 0,
                conflicts=model.actual_conflict_count or 0,
            )
        return ProjectionAttempt(
            id=model.id,
            resource_id=model.resource_id,
            generation_id=model.generation_id,
            attempt_number=model.attempt_number,
            state=ProjectionAttemptState(model.state),
            actor_type=ProjectionActorType(model.actor_type),
            actor_id=model.actor_id,
            actor_role=model.actor_role,
            correlation_id=model.correlation_id,
            contract_version=model.contract_version,
            source_content_digest=model.source_content_digest,
            source_schema_version=model.source_schema_version,
            graph_schema_version=model.graph_schema_version,
            projector_version=model.projector_version,
            execution_count=model.execution_count,
            dispatch_count=model.dispatch_count,
            dispatched_at=(
                None
                if model.dispatched_at is None
                else _ensure_utc(model.dispatched_at)
            ),
            lease_owner=model.lease_owner,
            lease_token=model.lease_token,
            lease_heartbeat_at=(
                None
                if model.lease_heartbeat_at is None
                else _ensure_utc(model.lease_heartbeat_at)
            ),
            lease_expires_at=(
                None
                if model.lease_expires_at is None
                else _ensure_utc(model.lease_expires_at)
            ),
            expected_counts=ProjectionCounts(
                entities=model.expected_entity_count,
                relationships=model.expected_relationship_count,
                evidence=model.expected_evidence_count,
                unresolved=model.expected_unresolved_count,
                conflicts=model.expected_conflict_count,
            ),
            actual_counts=actual_counts,
            expected_key_set_digest=model.expected_key_set_digest,
            actual_key_set_digest=model.actual_key_set_digest,
            expected_endpoint_digest=model.expected_endpoint_digest,
            actual_endpoint_digest=model.actual_endpoint_digest,
            expected_payload_digest=model.expected_payload_digest,
            actual_payload_digest=model.actual_payload_digest,
            failure_code=model.failure_code,
            failure_message=model.failure_message,
            version=model.version,
            created_at=_ensure_utc(model.created_at),
            updated_at=_ensure_utc(model.updated_at),
            completed_at=(
                None if model.completed_at is None else _ensure_utc(model.completed_at)
            ),
        )


def _safe_text(value: str, maximum: int) -> str:
    normalized = " ".join(value.split())
    normalized = re.sub(
        r"(?i)\b(password|passwd|secret|token|api[_-]?key|credential)\s*[:=]\s*[^\s,;]+",
        r"\1=<redacted>",
        normalized,
    )
    normalized = re.sub(
        r"(?i)([a-z][a-z0-9+.-]*://)[^/@\s:]+:[^/@\s]+@",
        r"\1<redacted>@",
        normalized,
    )
    return normalized[:maximum]


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "GraphProjectionAttemptModel",
    "GraphProjectionResourceModel",
    "SqlAlchemyGraphProjectionRepository",
]
