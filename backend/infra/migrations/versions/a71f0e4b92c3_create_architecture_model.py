"""create_architecture_model

Revision ID: a71f0e4b92c3
Revises: c4b1897a0f12
Create Date: 2026-11-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a71f0e4b92c3"
down_revision: str | Sequence[str] | None = "c4b1897a0f12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create immutable Architecture Version persistence tables."""
    op.create_table(
        "architecture_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("configuration_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("analyzer_version", sa.String(length=64), nullable=False),
        sa.Column("ir_schema_version", sa.String(length=64), nullable=False),
        sa.Column("architecture_schema_version", sa.String(length=64), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("completeness", sa.JSON(), nullable=False),
        sa.Column("source_diagnostic_ids", sa.JSON(), nullable=False),
        sa.Column("entity_count", sa.Integer(), nullable=False),
        sa.Column("relationship_count", sa.Integer(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("unresolved_relationship_count", sa.Integer(), nullable=False),
        sa.Column("conflict_count", sa.Integer(), nullable=False),
        sa.Column("diagnostic_id", sa.Uuid(), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('building', 'validating', 'validation_failed', 'published')",
            name="ck_architecture_versions_state",
        ),
        sa.CheckConstraint(
            "sequence_number > 0", name="ck_architecture_versions_sequence_positive"
        ),
        sa.CheckConstraint(
            "entity_count >= 0 AND relationship_count >= 0 "
            "AND evidence_count >= 0 AND unresolved_relationship_count >= 0 "
            "AND conflict_count >= 0",
            name="ck_architecture_versions_counts_nonnegative",
        ),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["diagnostic_id"], ["analysis_diagnostics.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_id", name="uq_architecture_versions_analysis"),
        sa.UniqueConstraint(
            "repository_id",
            "sequence_number",
            name="uq_architecture_versions_repository_sequence",
        ),
    )
    op.create_index(
        "ix_architecture_versions_project_repository_sequence",
        "architecture_versions",
        ["project_id", "repository_id", "sequence_number"],
    )
    op.create_index(
        "ix_architecture_versions_project_state",
        "architecture_versions",
        ["project_id", "state"],
    )

    op.create_table(
        "architecture_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("logical_id", sa.Text(), nullable=False),
        sa.Column("source_evidence_key", sa.Text(), nullable=False),
        sa.Column("source_record_type", sa.String(length=100), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("source_fact_key", sa.Text(), nullable=True),
        sa.Column("source_range", sa.JSON(), nullable=True),
        sa.Column("producer_id", sa.String(length=255), nullable=True),
        sa.Column("producer_version", sa.String(length=64), nullable=True),
        sa.Column("strength", sa.String(length=64), nullable=False),
        sa.Column("polarity", sa.String(length=32), nullable=False),
        sa.Column("safe_metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"], ["architecture_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "version_id", "logical_id", name="uq_architecture_evidence_logical"
        ),
    )
    op.create_index(
        "ix_architecture_evidence_version", "architecture_evidence", ["version_id"]
    )

    op.create_table(
        "architecture_entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("logical_id", sa.Text(), nullable=False),
        sa.Column("semantic_signature", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("namespace", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_ir_keys", sa.JSON(), nullable=False),
        sa.Column("safe_metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"], ["architecture_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "version_id", "logical_id", name="uq_architecture_entities_logical"
        ),
    )
    op.create_index(
        "ix_architecture_entities_version_kind",
        "architecture_entities",
        ["version_id", "kind"],
    )

    op.create_table(
        "architecture_relationships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("logical_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("source_entity_id", sa.Uuid(), nullable=False),
        sa.Column("target_entity_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_ir_keys", sa.JSON(), nullable=False),
        sa.Column("safe_metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_entity_id"], ["architecture_entities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"], ["architecture_entities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["version_id"], ["architecture_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "version_id", "logical_id", name="uq_architecture_relationships_logical"
        ),
    )
    op.create_index(
        "ix_architecture_relationships_version_kind",
        "architecture_relationships",
        ["version_id", "kind"],
    )
    op.create_index(
        "ix_architecture_relationships_source",
        "architecture_relationships",
        ["version_id", "source_entity_id"],
    )
    op.create_index(
        "ix_architecture_relationships_target",
        "architecture_relationships",
        ["version_id", "target_entity_id"],
    )

    op.create_table(
        "architecture_unresolved_relationships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("logical_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("source_entity_id", sa.Uuid(), nullable=False),
        sa.Column("target_descriptor", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_ir_keys", sa.JSON(), nullable=False),
        sa.Column("candidate_references", sa.JSON(), nullable=False),
        sa.Column("safe_metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_entity_id"], ["architecture_entities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["version_id"], ["architecture_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "version_id", "logical_id", name="uq_architecture_unresolved_logical"
        ),
    )
    op.create_index(
        "ix_architecture_unresolved_version",
        "architecture_unresolved_relationships",
        ["version_id"],
    )

    op.create_table(
        "architecture_conflicts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("logical_id", sa.Text(), nullable=False),
        sa.Column("conflict_type", sa.String(length=100), nullable=False),
        sa.Column("subject_key", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"], ["architecture_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "version_id", "logical_id", name="uq_architecture_conflicts_logical"
        ),
    )
    op.create_index(
        "ix_architecture_conflicts_version", "architecture_conflicts", ["version_id"]
    )

    _create_association_table(
        "architecture_entity_evidence",
        "entity_id",
        "architecture_entities.id",
    )
    _create_association_table(
        "architecture_relationship_evidence",
        "relationship_id",
        "architecture_relationships.id",
    )
    _create_association_table(
        "architecture_unresolved_evidence",
        "unresolved_relationship_id",
        "architecture_unresolved_relationships.id",
    )
    _create_association_table(
        "architecture_conflict_evidence",
        "conflict_id",
        "architecture_conflicts.id",
    )
    op.create_foreign_key(
        "fk_analyses_published_version_id_architecture_versions",
        "analyses",
        "architecture_versions",
        ["published_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def _create_association_table(
    table_name: str, owner_column: str, owner_target: str
) -> None:
    op.create_table(
        table_name,
        sa.Column(owner_column, sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint([owner_column], [owner_target], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["evidence_id"], ["architecture_evidence.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint(owner_column, "evidence_id"),
    )


def downgrade() -> None:
    """Drop Architecture Version persistence tables."""
    op.drop_constraint(
        "fk_analyses_published_version_id_architecture_versions",
        "analyses",
        type_="foreignkey",
    )
    op.drop_table("architecture_conflict_evidence")
    op.drop_table("architecture_unresolved_evidence")
    op.drop_table("architecture_relationship_evidence")
    op.drop_table("architecture_entity_evidence")
    op.drop_index(
        "ix_architecture_conflicts_version", table_name="architecture_conflicts"
    )
    op.drop_table("architecture_conflicts")
    op.drop_index(
        "ix_architecture_unresolved_version",
        table_name="architecture_unresolved_relationships",
    )
    op.drop_table("architecture_unresolved_relationships")
    op.drop_index(
        "ix_architecture_relationships_target", table_name="architecture_relationships"
    )
    op.drop_index(
        "ix_architecture_relationships_source", table_name="architecture_relationships"
    )
    op.drop_index(
        "ix_architecture_relationships_version_kind",
        table_name="architecture_relationships",
    )
    op.drop_table("architecture_relationships")
    op.drop_index(
        "ix_architecture_entities_version_kind", table_name="architecture_entities"
    )
    op.drop_table("architecture_entities")
    op.drop_index(
        "ix_architecture_evidence_version", table_name="architecture_evidence"
    )
    op.drop_table("architecture_evidence")
    op.drop_index(
        "ix_architecture_versions_project_state", table_name="architecture_versions"
    )
    op.drop_index(
        "ix_architecture_versions_project_repository_sequence",
        table_name="architecture_versions",
    )
    op.drop_table("architecture_versions")
