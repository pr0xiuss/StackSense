"""repair_project_access_user_index

Revision ID: d4e2b79c3fa6
Revises: 283065bf8700
Create Date: 2026-09-25 14:06:02.261795

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e2b79c3fa6"
down_revision: str | Sequence[str] | None = "283065bf8700"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_project_access_user_id",
        "project_access",
        ["user_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    """Downgrade schema.

    Note: ix_project_access_user_id belongs to the schema established by
    historical migration 64ab0e257e77, whose downgrade() drops the index.
    Dropping it here would leave the index missing when 64ab0e257e77.downgrade()
    executes, causing an UndefinedObject error when crossing 64ab0e257e77.
    """
    pass
