"""SQLAlchemy persistence models for Analysis Lifecycle and Diagnostics."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.platform.projects.infra.base import Base


class AnalysisModel(Base):
    """Authoritative Analysis lifecycle persistence entity."""

    __tablename__ = "analyses"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
    )
    repository_id: Mapped[UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
    )
    snapshot_id: Mapped[UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="created",
        index=True,
    )
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    completeness: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    published_version_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'queued', 'running', 'partial', "
            "'completed', 'completed_with_warnings', 'failed', "
            "'cancel_requested', 'cancelled', 'timeout')",
            name="ck_analyses_status",
        ),
        Index("ix_analyses_project_created", "project_id", "created_at"),
        Index(
            "uq_analyses_project_idempotency",
            "project_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )


class AnalysisJobModel(Base):
    """Background Job execution state entity."""

    __tablename__ = "analysis_jobs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )
    attempt: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )
    worker_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'queued', 'running', 'retrying', "
            "'completed', 'failed', 'cancelled')",
            name="ck_analysis_jobs_status",
        ),
        CheckConstraint("attempt >= 1", name="ck_analysis_jobs_attempt"),
        Index("ix_analysis_jobs_stale", "status", "heartbeat_at"),
    )


class AnalysisStageModel(Base):
    """Analysis Stage execution state entity."""

    __tablename__ = "analysis_stages"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("analysis_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    stage_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )
    stage_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    is_mandatory: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    processed_items: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_items: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'queued', 'running', 'completed', "
            "'failed', 'skipped', 'cancelled')",
            name="ck_analysis_stages_status",
        ),
        UniqueConstraint(
            "analysis_id",
            "stage_name",
            name="uq_analysis_stages_analysis_stage",
        ),
        Index("ix_analysis_stages_order", "analysis_id", "stage_order"),
    )


class AnalysisEventModel(Base):
    """Durable lifecycle audit and notification event."""

    __tablename__ = "analysis_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    __table_args__ = (
        CheckConstraint(
            "sequence_number >= 1",
            name="ck_analysis_events_sequence_number",
        ),
        UniqueConstraint(
            "analysis_id",
            "sequence_number",
            name="uq_analysis_events_sequence",
        ),
    )


class AnalysisDiagnosticModel(Base):
    """Lifecycle-safe persisted analysis diagnostic record."""

    __tablename__ = "analysis_diagnostics"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("analysis_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    stage: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )
    retryability: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    details: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    artifact_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        nullable=True,
    )
    artifact_path: Mapped[str | None] = mapped_column(
        String(4096),
        nullable=True,
    )
    source_line: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    source_column: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_analysis_diagnostics_severity", "analysis_id", "severity"),
        Index("ix_analysis_diagnostics_stage", "analysis_id", "stage"),
    )
