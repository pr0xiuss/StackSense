"""M5 sealed report metadata; no upstream lifecycle or schema changes.

Revision ID: e3b8a1c94d2f
Revises: 7d4a6c2e910b
"""

from alembic import op
from sqlalchemy import MetaData, text

from backend.platform.reports.persistence import REPORT_TABLES, install_guards

revision = "e3b8a1c94d2f"
down_revision = "7d4a6c2e910b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    metadata = MetaData()
    for table in REPORT_TABLES:
        table.to_metadata(metadata)
    metadata.create_all(connection, checkfirst=False)
    install_guards(connection, connection.scalar(text("SELECT current_schema()")))


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM report_generation WHERE state='ACCEPTED') "
            "OR EXISTS (SELECT 1 FROM report_read_pin)"
        )
    ):
        raise RuntimeError("accepted report artifacts or pins prevent downgrade")
    connection.execute(
        text("ALTER TABLE report_resource DROP CONSTRAINT fk_report_active_generation")
    )
    for name in ("report_read_pin", "report_generation", "report_resource"):
        connection.execute(text(f"DROP TABLE IF EXISTS {name} CASCADE"))
