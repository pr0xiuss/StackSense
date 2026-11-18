"""Owner-controlled additive M1 search reprojection operation records.

Revision ID: 26c95d71b603
Revises: 8b395e61f204
"""

import sqlalchemy as sa
from alembic import op

revision = "26c95d71b603"
down_revision = "8b395e61f204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_search_reprojections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("key_digest", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("request_snapshot", sa.JSON(), nullable=False),
        sa.Column("response_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "predecessor_work_id",
            sa.Uuid(),
            sa.ForeignKey("delivery_work.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "successor_work_id",
            sa.Uuid(),
            sa.ForeignKey("delivery_work.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "actor_id",
            "project_id",
            "key_digest",
            name="uq_delivery_search_reprojection_key",
        ),
    )


def downgrade() -> None:
    op.drop_table("delivery_search_reprojections")
