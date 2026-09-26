"""create_users_and_credentials

Revision ID: 9b2afaa2a527
Revises: 2771a7f24f34
Create Date: 2026-09-26 13:47:31.789358

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9b2afaa2a527"
down_revision: str | Sequence[str] | None = "2771a7f24f34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )
    op.create_table(
        "user_credentials",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    # Add foreign key with NOT VALID so existing historical rows don't cause
    # migration failure, while all new inserts and updates are strictly enforced.
    op.execute("""
        ALTER TABLE project_access
        ADD CONSTRAINT fk_project_access_user_id_users
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE RESTRICT
        NOT VALID;
        """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        ALTER TABLE project_access
        DROP CONSTRAINT IF EXISTS fk_project_access_user_id_users;
        """)
    op.drop_table("user_credentials")
    op.drop_index("ix_users_email_lower", table_name="users")
    op.drop_table("users")
