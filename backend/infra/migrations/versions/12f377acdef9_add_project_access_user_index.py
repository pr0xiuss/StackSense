"""add project access user index

Revision ID: 12f377acdef9
Revises: 64ab0e257e77
Create Date: 2026-09-22 00:35:58.340520

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.

revision: str = "12f377acdef9"
down_revision: str | Sequence[str] | None = "64ab0e257e77"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_project_access_user_id",
        "project_access",
        ["user_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_project_access_user_id",
        table_name="project_access",
    )
