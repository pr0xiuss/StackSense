"""add_username_to_users

Revision ID: aa22a5dc8c27
Revises: 9b2afaa2a527
Create Date: 2026-09-29 13:05:14.705748

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aa22a5dc8c27"
down_revision: str | Sequence[str] | None = "9b2afaa2a527"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: add username column, backfill, and enforce unique index."""
    op.add_column("users", sa.Column("username", sa.String(length=30), nullable=True))

    # Backfill username from email prefix: replace non-alphanumeric with _,
    # ensure length >= 3 and <= 30
    op.execute("""
        UPDATE users
        SET username = CASE
            WHEN length(
                SUBSTRING(
                    REGEXP_REPLACE(
                        SPLIT_PART(LOWER(email), '@', 1), '[^a-z0-9_]', '_', 'g'
                    ),
                    1, 30
                )
            ) < 3
            THEN rpad(
                SUBSTRING(
                    REGEXP_REPLACE(
                        SPLIT_PART(LOWER(email), '@', 1), '[^a-z0-9_]', '_', 'g'
                    ),
                    1, 30
                ), 3, '_'
            )
            ELSE SUBSTRING(
                REGEXP_REPLACE(
                    SPLIT_PART(LOWER(email), '@', 1), '[^a-z0-9_]', '_', 'g'
                ),
                1, 30
            )
        END
        WHERE username IS NULL;
        """)

    # Resolve any duplicate usernames by appending last 8 chars of user UUID
    op.execute("""
        UPDATE users
        SET username = SUBSTRING(username, 1, 21) || '_' ||
                       RIGHT(REPLACE(id::text, '-', ''), 8)
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY lower(username) ORDER BY created_at
                ) as rn
                FROM users
            ) sub WHERE rn > 1
        );
        """)

    op.alter_column("users", "username", nullable=False)

    op.create_index(
        "ix_users_username_lower",
        "users",
        [sa.text("lower(username)")],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema: drop unique index and username column."""
    op.drop_index("ix_users_username_lower", table_name="users")
    op.drop_column("users", "username")
