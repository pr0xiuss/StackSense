"""Create P5 delivery coordination tables; no frozen schema changes."""

import sqlalchemy as sa
from alembic import op

revision = "1a8dc18797a1"
down_revision = "c5d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_bundles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("architecture_version_id", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("source_header", sa.JSON(), nullable=True),
        sa.Column("runtime_profile", sa.JSON(), nullable=True),
        sa.Column("eligibility", sa.String(length=32), nullable=False),
        sa.Column("eligibility_error", sa.String(length=128), nullable=True),
        sa.Column("eligibility_retry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("barrier", sa.JSON(), nullable=True),
        sa.Column("sibling_release", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "eligibility IN ('WAITING_FOR_ANALYSIS','ELIGIBLE','INELIGIBLE')",
            name="ck_delivery_bundle_eligibility",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "architecture_version_id",
            "fingerprint",
            name="uq_delivery_bundle_scope_policy",
        ),
    )
    op.create_index(
        "ix_delivery_eligibility_due",
        "delivery_bundles",
        ["eligibility", "eligibility_retry_at"],
        unique=False,
    )
    op.create_table(
        "delivery_work",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bundle_id", sa.Uuid(), nullable=False),
        sa.Column("identity", sa.JSON(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("template", sa.String(length=32), nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column(
            "dependencies_ready",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("retry_of_work_id", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("fence", sa.Integer(), nullable=False),
        sa.Column("executions", sa.Integer(), nullable=False),
        sa.Column(
            "dispatches", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("dispatch_epoch", sa.Uuid(), nullable=False),
        sa.Column("dispatch_claim", sa.Uuid(), nullable=True),
        sa.Column("dispatch_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_eligible_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_reason", sa.String(length=128), nullable=True),
        sa.Column("cancellation", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(kind='search_projection' AND template='') OR (kind='di"
            "agram' AND template IN ('system_overview','component_ar"
            "chitecture','dependency_map','data_flow')) OR (kind='re"
            "port' AND template='architecture_analysis')",
            name="ck_delivery_work_slot",
        ),
        sa.CheckConstraint(
            "state IN ('PENDING','QUEUED','RUNNING','RETRYING','COMP"
            "LETED','FAILED','CANCELLED')",
            name="ck_delivery_work_state",
        ),
        sa.CheckConstraint(
            "fence >= 0 AND executions >= 0 AND run_number > 0",
            name="ck_delivery_work_counters",
        ),
        sa.ForeignKeyConstraint(
            ["bundle_id"], ["delivery_bundles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["retry_of_work_id"], ["delivery_work.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "bundle_id",
            "kind",
            "template",
            "run_number",
            name="uq_delivery_work_slot_run",
        ),
        sa.UniqueConstraint("id", "bundle_id", name="uq_delivery_work_bundle"),
    )
    op.create_index(
        "ix_delivery_work_due",
        "delivery_work",
        ["state", "next_eligible_at", "dispatch_until"],
        unique=False,
    )
    op.create_index(
        "uq_delivery_work_current",
        "delivery_work",
        ["bundle_id", "kind", "template"],
        unique=True,
        postgresql_where=sa.text("is_current"),
        sqlite_where=sa.text("is_current"),
    )
    op.create_table(
        "delivery_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("identity", sa.JSON(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("fence", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.String(length=256), nullable=False),
        sa.Column("lease_digest", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("failure_code", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(state='RUNNING' AND lease_digest IS NOT NULL AND expir"
            "es_at IS NOT NULL AND ended_at IS NULL) OR (state<>'RUN"
            "NING' AND lease_digest IS NULL AND expires_at IS NULL A"
            "ND ended_at IS NOT NULL)",
            name="ck_delivery_attempt_lease",
        ),
        sa.CheckConstraint(
            "state IN ('RUNNING','COMPLETED','FAILED','EXPIRED','CANCELLED')",
            name="ck_delivery_attempt_state",
        ),
        sa.CheckConstraint(
            "ordinal > 0 AND fence > 0", name="ck_delivery_attempt_counters"
        ),
        sa.ForeignKeyConstraint(["work_id"], ["delivery_work.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id"),
        sa.UniqueConstraint("id", "work_id", name="uq_delivery_attempt_work"),
        sa.UniqueConstraint("work_id", "fence", name="uq_delivery_attempt_fence"),
        sa.UniqueConstraint("work_id", "ordinal", name="uq_delivery_attempt_ordinal"),
    )
    op.create_index(
        "ix_delivery_attempt_expiry",
        "delivery_attempts",
        ["state", "expires_at"],
        unique=False,
    )
    op.create_index(
        "uq_delivery_attempt_running",
        "delivery_attempts",
        ["work_id"],
        unique=True,
        postgresql_where=sa.text("state='RUNNING'"),
        sqlite_where=sa.text("state='RUNNING'"),
    )
    op.create_table(
        "delivery_outputs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bundle_id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("fence", sa.Integer(), nullable=False),
        sa.Column("receipt", sa.JSON(), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("fence > 0", name="ck_delivery_output_fence"),
        sa.ForeignKeyConstraint(
            ["attempt_id", "work_id"],
            ["delivery_attempts.id", "delivery_attempts.work_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["work_id", "bundle_id"],
            ["delivery_work.id", "delivery_work.bundle_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id"),
        sa.UniqueConstraint("work_id"),
    )
    op.create_table(
        "delivery_discovery_state",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("cursor", sa.JSON(), nullable=True),
        sa.Column("pending", sa.JSON(), nullable=True),
        sa.Column("fence", sa.Integer(), nullable=False),
        sa.Column("owner", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("fence >= 0", name="ck_delivery_discovery_fence"),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "delivery_runtime_capabilities",
        sa.Column("worker_id", sa.String(length=256), nullable=False),
        sa.Column("profile", sa.String(length=64), nullable=False),
        sa.Column("contract_version", sa.String(length=32), nullable=False),
        sa.Column("deployment_epoch", sa.String(length=256), nullable=False),
        sa.Column("queue", sa.String(length=256), nullable=False),
        sa.Column("ready", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("worker_id", "profile"),
    )
    op.create_index(
        "ix_delivery_capability_time",
        "delivery_runtime_capabilities",
        ["observed_at"],
        unique=False,
    )
    op.create_table(
        "delivery_retry_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("key_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("previous_work_id", sa.Uuid(), nullable=False),
        sa.Column("new_work_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["new_work_id"], ["delivery_work.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["previous_work_id"], ["delivery_work.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "actor_id",
            "project_id",
            "action",
            "key_digest",
            name="uq_delivery_retry_request",
        ),
    )


def downgrade() -> None:
    # Only fixture/owner-authorized P5 rollback; never cascade into P1–P4.
    op.drop_table("delivery_retry_requests")
    op.drop_table("delivery_runtime_capabilities")
    op.drop_table("delivery_discovery_state")
    op.drop_table("delivery_outputs")
    op.drop_table("delivery_attempts")
    op.drop_table("delivery_work")
    op.drop_table("delivery_bundles")
