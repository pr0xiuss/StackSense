"""add project access user index

Revision ID: 64ab0e257e77
Revises: bf1b64e1ccdd
Create Date: 2026-09-21 22:13:39.117128
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "64ab0e257e77"
down_revision: str | Sequence[str] | None = "bf1b64e1ccdd"
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
