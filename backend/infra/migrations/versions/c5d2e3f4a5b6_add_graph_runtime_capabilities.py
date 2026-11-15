"""add graph runtime capabilities

Revision ID: c5d2e3f4a5b6
Revises: f4c1b2d3e4a5
Create Date: 2026-11-11 00:00:01.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "f4c1b2d3e4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "graph_runtime_capabilities",
        sa.Column("capability", sa.String(length=64), nullable=False),
        sa.Column("worker_id", sa.String(length=255), nullable=False),
        sa.Column("ready", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "capability IN ('reconciliation_scheduling','projection_execution')",
            name="ck_graph_runtime_capability_name",
        ),
        sa.PrimaryKeyConstraint("capability", "worker_id"),
    )
    op.create_index(
        "ix_graph_runtime_capability_observed",
        "graph_runtime_capabilities",
        ["capability", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_graph_runtime_capability_observed",
        table_name="graph_runtime_capabilities",
    )
    op.drop_table("graph_runtime_capabilities")
