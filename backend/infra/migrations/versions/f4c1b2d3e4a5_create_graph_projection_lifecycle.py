"""create graph projection lifecycle

Revision ID: f4c1b2d3e4a5
Revises: a71f0e4b92c3
Create Date: 2026-11-11 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4c1b2d3e4a5"
down_revision: str | Sequence[str] | None = "a71f0e4b92c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "graph_projection_resources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("architecture_version_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("architecture_sequence", sa.Integer(), nullable=False),
        sa.Column("projection_type", sa.String(length=32), nullable=False),
        sa.Column("source_content_digest", sa.String(length=128), nullable=False),
        sa.Column("source_schema_version", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("active_generation_id", sa.Uuid(), nullable=True),
        sa.Column("active_projector_version", sa.String(length=64), nullable=True),
        sa.Column("active_graph_schema_version", sa.String(length=64), nullable=True),
        sa.Column("active_payload_digest", sa.String(length=128), nullable=True),
        sa.Column("active_entity_count", sa.Integer(), nullable=True),
        sa.Column("active_relationship_count", sa.Integer(), nullable=True),
        sa.Column("active_evidence_count", sa.Integer(), nullable=True),
        sa.Column("active_unresolved_count", sa.Integer(), nullable=True),
        sa.Column("active_conflict_count", sa.Integer(), nullable=True),
        sa.Column("last_failure_code", sa.String(length=100), nullable=True),
        sa.Column("last_failure_message", sa.String(length=500), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "architecture_sequence > 0", name="ck_graph_resource_sequence_positive"
        ),
        sa.CheckConstraint("version > 0", name="ck_graph_resource_version_positive"),
        sa.CheckConstraint(
            "state IN ('PENDING','RUNNING','COMPLETED','FAILED','STALE')",
            name="ck_graph_resource_state",
        ),
        sa.CheckConstraint(
            "((state IN ('COMPLETED','STALE') AND active_generation_id IS NOT NULL) "
            "OR (state IN ('PENDING','RUNNING','FAILED') AND "
            "active_generation_id IS NULL))",
            name="ck_graph_resource_state_active_generation",
        ),
        sa.CheckConstraint(
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
        sa.ForeignKeyConstraint(
            ["architecture_version_id"],
            ["architecture_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "architecture_version_id",
            "projection_type",
            name="uq_graph_projection_resource_version_type",
        ),
        sa.UniqueConstraint(
            "id", "active_generation_id", name="uq_graph_resource_active_generation"
        ),
    )
    op.create_index(
        "ix_graph_resource_project_version",
        "graph_projection_resources",
        ["project_id", "architecture_version_id"],
    )
    op.create_index(
        "ix_graph_resource_repository_sequence",
        "graph_projection_resources",
        ["repository_id", "architecture_sequence"],
    )
    op.create_index("ix_graph_resource_state", "graph_projection_resources", ["state"])

    op.create_table(
        "graph_projection_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column("correlation_id", sa.String(length=255), nullable=False),
        sa.Column("contract_version", sa.String(length=64), nullable=False),
        sa.Column("source_content_digest", sa.String(length=128), nullable=False),
        sa.Column("source_schema_version", sa.String(length=64), nullable=False),
        sa.Column("graph_schema_version", sa.String(length=64), nullable=False),
        sa.Column("projector_version", sa.String(length=64), nullable=False),
        sa.Column("execution_count", sa.Integer(), nullable=False),
        sa.Column("dispatch_count", sa.Integer(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=255), nullable=True),
        sa.Column("lease_token", sa.String(length=255), nullable=True),
        sa.Column("lease_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_entity_count", sa.Integer(), nullable=False),
        sa.Column("expected_relationship_count", sa.Integer(), nullable=False),
        sa.Column("expected_evidence_count", sa.Integer(), nullable=False),
        sa.Column("expected_unresolved_count", sa.Integer(), nullable=False),
        sa.Column("expected_conflict_count", sa.Integer(), nullable=False),
        sa.Column("actual_entity_count", sa.Integer(), nullable=True),
        sa.Column("actual_relationship_count", sa.Integer(), nullable=True),
        sa.Column("actual_evidence_count", sa.Integer(), nullable=True),
        sa.Column("actual_unresolved_count", sa.Integer(), nullable=True),
        sa.Column("actual_conflict_count", sa.Integer(), nullable=True),
        sa.Column("expected_key_set_digest", sa.String(length=128), nullable=True),
        sa.Column("actual_key_set_digest", sa.String(length=128), nullable=True),
        sa.Column("expected_endpoint_digest", sa.String(length=128), nullable=True),
        sa.Column("actual_endpoint_digest", sa.String(length=128), nullable=True),
        sa.Column("expected_payload_digest", sa.String(length=128), nullable=True),
        sa.Column("actual_payload_digest", sa.String(length=128), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_message", sa.String(length=500), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "attempt_number > 0", name="ck_graph_attempt_number_positive"
        ),
        sa.CheckConstraint("version > 0", name="ck_graph_attempt_version_positive"),
        sa.CheckConstraint(
            "state IN ('QUEUED','RUNNING','RETRYING','COMPLETED','FAILED',"
            "'SUPERSEDED')",
            name="ck_graph_attempt_state",
        ),
        sa.CheckConstraint(
            "actor_type IN ('SYSTEM','USER')", name="ck_graph_attempt_actor_type"
        ),
        sa.CheckConstraint(
            "((actor_type = 'SYSTEM' AND actor_id IS NULL AND actor_role IS NULL) OR "
            "(actor_type = 'USER' AND actor_id IS NOT NULL AND "
            "actor_role IS NOT NULL))",
            name="ck_graph_attempt_actor_fields",
        ),
        sa.CheckConstraint(
            "execution_count >= 0 AND execution_count <= 3 AND dispatch_count >= 0",
            name="ck_graph_attempt_counts",
        ),
        sa.CheckConstraint(
            "expected_entity_count >= 0 AND expected_relationship_count >= 0 AND "
            "expected_evidence_count >= 0 AND expected_unresolved_count >= 0 AND "
            "expected_conflict_count >= 0",
            name="ck_graph_attempt_expected_counts",
        ),
        sa.CheckConstraint(
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
        sa.CheckConstraint(
            "((state = 'RUNNING' AND lease_owner IS NOT NULL AND "
            "lease_token IS NOT NULL "
            "AND lease_heartbeat_at IS NOT NULL AND lease_expires_at IS NOT NULL) OR "
            "(state <> 'RUNNING' AND lease_owner IS NULL AND lease_token IS NULL "
            "AND lease_heartbeat_at IS NULL AND lease_expires_at IS NULL))",
            name="ck_graph_attempt_lease_state",
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"], ["graph_projection_resources.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generation_id"),
        sa.UniqueConstraint(
            "resource_id", "generation_id", name="uq_graph_attempt_resource_generation"
        ),
        sa.UniqueConstraint(
            "resource_id", "attempt_number", name="uq_graph_attempt_resource_number"
        ),
    )
    op.create_index(
        "uq_graph_attempt_one_active",
        "graph_projection_attempts",
        ["resource_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('QUEUED','RUNNING','RETRYING')"),
    )
    op.create_index(
        "ix_graph_attempt_undispatched",
        "graph_projection_attempts",
        ["state", "dispatched_at"],
    )
    op.create_index(
        "ix_graph_attempt_expired_lease",
        "graph_projection_attempts",
        ["state", "lease_expires_at"],
    )
    op.create_index(
        "ix_graph_attempt_resource_history",
        "graph_projection_attempts",
        ["resource_id", "attempt_number"],
    )
    op.create_index(
        "ix_graph_attempt_correlation",
        "graph_projection_attempts",
        ["correlation_id"],
    )
    op.create_foreign_key(
        "fk_graph_resource_active_generation",
        "graph_projection_resources",
        "graph_projection_attempts",
        ["id", "active_generation_id"],
        ["resource_id", "generation_id"],
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_graph_resource_active_generation",
        "graph_projection_resources",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_graph_attempt_correlation", table_name="graph_projection_attempts"
    )
    op.drop_index(
        "ix_graph_attempt_resource_history", table_name="graph_projection_attempts"
    )
    op.drop_index(
        "ix_graph_attempt_expired_lease", table_name="graph_projection_attempts"
    )
    op.drop_index(
        "ix_graph_attempt_undispatched", table_name="graph_projection_attempts"
    )
    op.drop_index("uq_graph_attempt_one_active", table_name="graph_projection_attempts")
    op.drop_table("graph_projection_attempts")
    op.drop_index("ix_graph_resource_state", table_name="graph_projection_resources")
    op.drop_index(
        "ix_graph_resource_repository_sequence",
        table_name="graph_projection_resources",
    )
    op.drop_index(
        "ix_graph_resource_project_version",
        table_name="graph_projection_resources",
    )
    op.drop_table("graph_projection_resources")
