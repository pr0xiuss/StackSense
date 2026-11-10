"""create_analysis_lifecycle_tables

Revision ID: c4b1897a0f12
Revises: 9296ffc9a48c
Create Date: 2026-11-04 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4b1897a0f12"
down_revision: str | Sequence[str] | None = "9296ffc9a48c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create analyses, jobs, stages, events, and diagnostics tables."""
    # 1. analyses table
    op.create_table(
        "analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="created",
            nullable=False,
        ),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("completeness", sa.JSON(), nullable=True),
        sa.Column("published_version_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('created', 'queued', 'running', 'partial', "
            "'completed', 'completed_with_warnings', 'failed', "
            "'cancel_requested', 'cancelled', 'timeout')",
            name="ck_analyses_status",
        ),
    )
    op.create_index(
        "ix_analyses_project_id",
        "analyses",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_analyses_repository_id",
        "analyses",
        ["repository_id"],
        unique=False,
    )
    op.create_index(
        "ix_analyses_snapshot_id",
        "analyses",
        ["snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_analyses_status",
        "analyses",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_analyses_project_created",
        "analyses",
        ["project_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_analyses_project_idempotency",
        "analyses",
        ["project_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    # 2. analysis_jobs table
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "max_attempts",
            sa.Integer(),
            server_default="3",
            nullable=False,
        ),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'queued', 'running', 'retrying', "
            "'completed', 'failed', 'cancelled')",
            name="ck_analysis_jobs_status",
        ),
        sa.CheckConstraint("attempt >= 1", name="ck_analysis_jobs_attempt"),
    )
    op.create_index(
        "ix_analysis_jobs_analysis_id",
        "analysis_jobs",
        ["analysis_id"],
        unique=False,
    )
    op.create_index(
        "ix_analysis_jobs_project_id",
        "analysis_jobs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_analysis_jobs_status",
        "analysis_jobs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_analysis_jobs_stale",
        "analysis_jobs",
        ["status", "heartbeat_at"],
        unique=False,
    )

    # 3. analysis_stages table
    op.create_table(
        "analysis_stages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("stage_name", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("stage_order", sa.Integer(), nullable=False),
        sa.Column(
            "is_mandatory",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "processed_items",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "total_items",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["analysis_jobs.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "analysis_id",
            "stage_name",
            name="uq_analysis_stages_analysis_stage",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'queued', 'running', 'completed', "
            "'failed', 'skipped', 'cancelled')",
            name="ck_analysis_stages_status",
        ),
    )
    op.create_index(
        "ix_analysis_stages_analysis_id",
        "analysis_stages",
        ["analysis_id"],
        unique=False,
    )
    op.create_index(
        "ix_analysis_stages_order",
        "analysis_stages",
        ["analysis_id", "stage_order"],
        unique=False,
    )

    # 4. analysis_events table
    op.create_table(
        "analysis_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "analysis_id",
            "sequence_number",
            name="uq_analysis_events_sequence",
        ),
        sa.CheckConstraint(
            "sequence_number >= 1",
            name="ck_analysis_events_sequence_number",
        ),
    )
    op.create_index(
        "ix_analysis_events_analysis_id",
        "analysis_events",
        ["analysis_id"],
        unique=False,
    )

    # 5. analysis_diagnostics table
    op.create_table(
        "analysis_diagnostics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("stage", sa.String(length=100), nullable=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("scope", sa.String(length=50), nullable=False),
        sa.Column("message", sa.String(length=2000), nullable=False),
        sa.Column("retryability", sa.String(length=50), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("artifact_path", sa.String(length=4096), nullable=True),
        sa.Column("source_line", sa.Integer(), nullable=True),
        sa.Column("source_column", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["analysis_jobs.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analysis_diagnostics_analysis_id",
        "analysis_diagnostics",
        ["analysis_id"],
        unique=False,
    )
    op.create_index(
        "ix_analysis_diagnostics_severity",
        "analysis_diagnostics",
        ["analysis_id", "severity"],
        unique=False,
    )
    op.create_index(
        "ix_analysis_diagnostics_stage",
        "analysis_diagnostics",
        ["analysis_id", "stage"],
        unique=False,
    )


def downgrade() -> None:
    """Drop analysis lifecycle tables in reverse dependency order."""
    op.drop_table("analysis_diagnostics")
    op.drop_table("analysis_events")
    op.drop_table("analysis_stages")
    op.drop_table("analysis_jobs")
    op.drop_table("analyses")
