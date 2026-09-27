"""create_ingestion_tables

Revision ID: 2771a7f24f34
Revises: d4e2b79c3fa6
Create Date: 2026-09-25 17:52:04.508422

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2771a7f24f34"
down_revision: str | Sequence[str] | None = "d4e2b79c3fa6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create ingestions, repository_revisions, and repository_artifacts tables."""
    # 1. ingestions table
    op.create_table(
        "ingestions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_reference", sa.String(length=1024), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_ingestions_status",
        ),
    )
    op.create_index(
        "ix_ingestions_project_id",
        "ingestions",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_ingestions_repository_id",
        "ingestions",
        ["repository_id"],
        unique=False,
    )
    op.create_index(
        "uq_ingestions_active_repo",
        "ingestions",
        ["repository_id"],
        unique=True,
        postgresql_where=sa.text("status = 'processing'"),
    )

    # 2. repository_revisions table
    op.create_table(
        "repository_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_id", sa.Uuid(), nullable=True),
        sa.Column("revision_identifier", sa.String(length=255), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("total_files", sa.Integer(), nullable=False),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_id"],
            ["ingestions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id",
            "revision_identifier",
            name="uq_repository_revisions_repo_rev",
        ),
    )
    op.create_index(
        "ix_repository_revisions_project_id",
        "repository_revisions",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_repository_revisions_repository_id",
        "repository_revisions",
        ["repository_id"],
        unique=False,
    )

    # 3. repository_artifacts table
    op.create_table(
        "repository_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(length=4096), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("support_level", sa.String(length=50), nullable=False),
        sa.Column("storage_key", sa.String(length=4096), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["repository_revisions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "revision_id",
            "path",
            name="uq_repository_artifacts_rev_path",
        ),
    )
    op.create_index(
        "ix_repository_artifacts_project_id",
        "repository_artifacts",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_repository_artifacts_revision_id",
        "repository_artifacts",
        ["revision_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop repository_artifacts, repository_revisions, and ingestions tables."""
    op.drop_index(
        "ix_repository_artifacts_revision_id",
        table_name="repository_artifacts",
    )
    op.drop_index(
        "ix_repository_artifacts_project_id",
        table_name="repository_artifacts",
    )
    op.drop_table("repository_artifacts")

    op.drop_index(
        "ix_repository_revisions_repository_id",
        table_name="repository_revisions",
    )
    op.drop_index(
        "ix_repository_revisions_project_id",
        table_name="repository_revisions",
    )
    op.drop_table("repository_revisions")

    op.drop_index(
        "uq_ingestions_active_repo",
        table_name="ingestions",
    )
    op.drop_index(
        "ix_ingestions_repository_id",
        table_name="ingestions",
    )
    op.drop_index(
        "ix_ingestions_project_id",
        table_name="ingestions",
    )
    op.drop_table("ingestions")
