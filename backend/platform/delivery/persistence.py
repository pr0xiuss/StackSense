"""P5-owned durable coordination records. No foreign keys into frozen domains."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.platform.projects.infra.base import Base


class DeliveryBundleModel(Base):
    __tablename__ = "delivery_bundles"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    architecture_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    policy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_header: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    runtime_profile: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    eligibility: Mapped[str] = mapped_column(String(32), nullable=False)
    eligibility_error: Mapped[str | None] = mapped_column(String(128))
    eligibility_retry_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    barrier: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    sibling_release: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "architecture_version_id",
            "fingerprint",
            name="uq_delivery_bundle_scope_policy",
        ),
        CheckConstraint(
            "eligibility IN ('WAITING_FOR_ANALYSIS','ELIGIBLE','INELIGIBLE')",
            name="ck_delivery_bundle_eligibility",
        ),
        Index("ix_delivery_eligibility_due", "eligibility", "eligibility_retry_at"),
    )


class DeliveryWorkModel(Base):
    __tablename__ = "delivery_work"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    bundle_id: Mapped[UUID] = mapped_column(
        ForeignKey("delivery_bundles.id", ondelete="RESTRICT"), nullable=False
    )
    identity: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    template: Mapped[str] = mapped_column(String(32), nullable=False)
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dependencies_ready: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    retry_of_work_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("delivery_work.id", ondelete="RESTRICT")
    )
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    fence: Mapped[int] = mapped_column(Integer, nullable=False)
    executions: Mapped[int] = mapped_column(Integer, nullable=False)
    dispatches: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    dispatch_epoch: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    dispatch_claim: Mapped[UUID | None] = mapped_column(Uuid)
    dispatch_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_eligible_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_reason: Mapped[str | None] = mapped_column(String(128))
    cancellation: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "bundle_id",
            "kind",
            "template",
            "run_number",
            name="uq_delivery_work_slot_run",
        ),
        UniqueConstraint("id", "bundle_id", name="uq_delivery_work_bundle"),
        CheckConstraint(
            "state IN ('PENDING','QUEUED','RUNNING','RETRYING','COMP"
            "LETED','FAILED','CANCELLED')",
            name="ck_delivery_work_state",
        ),
        CheckConstraint(
            "fence >= 0 AND executions >= 0 AND run_number > 0",
            name="ck_delivery_work_counters",
        ),
        CheckConstraint(
            "(kind='search_projection' AND template='') OR (kind='di"
            "agram' AND template IN ('system_overview','component_ar"
            "chitecture','dependency_map','data_flow')) OR (kind='re"
            "port' AND template='architecture_analysis')",
            name="ck_delivery_work_slot",
        ),
        Index(
            "uq_delivery_work_current",
            "bundle_id",
            "kind",
            "template",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current"),
        ),
        Index("ix_delivery_work_due", "state", "next_eligible_at", "dispatch_until"),
    )


class DeliveryAttemptModel(Base):
    __tablename__ = "delivery_attempts"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    work_id: Mapped[UUID] = mapped_column(
        ForeignKey("delivery_work.id", ondelete="RESTRICT"), nullable=False
    )
    identity: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    fence: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, unique=True)
    worker_id: Mapped[str] = mapped_column(String(256), nullable=False)
    lease_digest: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("work_id", "ordinal", name="uq_delivery_attempt_ordinal"),
        UniqueConstraint("work_id", "fence", name="uq_delivery_attempt_fence"),
        UniqueConstraint("id", "work_id", name="uq_delivery_attempt_work"),
        CheckConstraint(
            "ordinal > 0 AND fence > 0", name="ck_delivery_attempt_counters"
        ),
        CheckConstraint(
            "state IN ('RUNNING','COMPLETED','FAILED','EXPIRED','CANCELLED')",
            name="ck_delivery_attempt_state",
        ),
        CheckConstraint(
            "(state='RUNNING' AND lease_digest IS NOT NULL AND expir"
            "es_at IS NOT NULL AND ended_at IS NULL) OR (state<>'RUN"
            "NING' AND lease_digest IS NULL AND expires_at IS NULL A"
            "ND ended_at IS NOT NULL)",
            name="ck_delivery_attempt_lease",
        ),
        Index(
            "uq_delivery_attempt_running",
            "work_id",
            unique=True,
            postgresql_where=text("state='RUNNING'"),
            sqlite_where=text("state='RUNNING'"),
        ),
        Index("ix_delivery_attempt_expiry", "state", "expires_at"),
    )


class DeliveryOutputModel(Base):
    __tablename__ = "delivery_outputs"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    bundle_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    work_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, unique=True)
    attempt_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, unique=True)
    fence: Mapped[int] = mapped_column(Integer, nullable=False)
    receipt: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    committed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["work_id", "bundle_id"],
            ["delivery_work.id", "delivery_work.bundle_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["attempt_id", "work_id"],
            ["delivery_attempts.id", "delivery_attempts.work_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("fence > 0", name="ck_delivery_output_fence"),
    )


class DeliveryDiscoveryModel(Base):
    __tablename__ = "delivery_discovery_state"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    cursor: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    pending: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    fence: Mapped[int] = mapped_column(Integer, nullable=False)
    owner: Mapped[UUID | None] = mapped_column(Uuid)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("fence >= 0", name="ck_delivery_discovery_fence"),
    )


class DeliveryCapabilityModel(Base):
    __tablename__ = "delivery_runtime_capabilities"
    worker_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    profile: Mapped[str] = mapped_column(String(64), primary_key=True)
    contract_version: Mapped[str] = mapped_column(String(32), nullable=False)
    deployment_epoch: Mapped[str] = mapped_column(String(256), nullable=False)
    queue: Mapped[str] = mapped_column(String(256), nullable=False)
    ready: Mapped[bool] = mapped_column(Boolean, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    __table_args__ = (Index("ix_delivery_capability_time", "observed_at"),)


class DeliveryRetryRequestModel(Base):
    __tablename__ = "delivery_retry_requests"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    key_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_work_id: Mapped[UUID] = mapped_column(
        ForeignKey("delivery_work.id", ondelete="RESTRICT"), nullable=False
    )
    new_work_id: Mapped[UUID] = mapped_column(
        ForeignKey("delivery_work.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "actor_id",
            "project_id",
            "action",
            "key_digest",
            name="uq_delivery_retry_request",
        ),
    )


DELIVERY_TABLES = (
    DeliveryBundleModel.__table__,
    DeliveryWorkModel.__table__,
    DeliveryAttemptModel.__table__,
    DeliveryOutputModel.__table__,
    DeliveryDiscoveryModel.__table__,
    DeliveryCapabilityModel.__table__,
    DeliveryRetryRequestModel.__table__,
)
