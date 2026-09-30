"""create repositories table

Revision ID: 283065bf8700
Revises: 64ab0e257e77
Create Date: 2026-09-25 13:25:47.134646
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "283065bf8700"
down_revision: str | Sequence[str] | None = "64ab0e257e77"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the repositories table."""
    op.create_table(
        "repositories",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.String(length=2000),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="registered",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "name",
            name="uq_repositories_project_id_name",
        ),
    )

    op.create_index(
        op.f("ix_repositories_project_id"),
        "repositories",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the repositories table."""
    op.drop_index(
        op.f("ix_repositories_project_id"),
        table_name="repositories",
    )
    op.drop_table("repositories")
