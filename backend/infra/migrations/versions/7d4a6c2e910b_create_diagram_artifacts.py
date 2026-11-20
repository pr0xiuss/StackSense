"""M4 sealed diagram metadata; no upstream lifecycle or schema changes.

Revision ID: 7d4a6c2e910b
Revises: 26c95d71b603
"""

from alembic import op
from sqlalchemy import text

from backend.platform.diagrams.persistence import DIAGRAM_TABLES, install_guards
from backend.platform.projects.infra.base import Base

revision = "7d4a6c2e910b"
down_revision = "26c95d71b603"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    Base.metadata.create_all(connection, tables=DIAGRAM_TABLES, checkfirst=False)
    install_guards(connection, connection.scalar(text("SELECT current_schema()")))


def downgrade() -> None:
    connection = op.get_bind()
    # Downgrade is not a cleanup command. Never erase accepted provenance/pins.
    if connection.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM diagram_generation WHERE state='ACCEPTED') "
            "OR EXISTS (SELECT 1 FROM diagram_read_pin)"
        )
    ):
        raise RuntimeError("accepted diagram artifacts or pins prevent downgrade")
    connection.execute(
        text(
            "ALTER TABLE diagram_resource DROP CONSTRAINT fk_diagram_active_generation"
        )
    )
    for name in ("diagram_read_pin", "diagram_generation", "diagram_resource"):
        op.drop_table(name)
    for name in (
        "guard_diagram_pin",
        "guard_diagram_pointer",
        "immutable_diagram_resource",
        "guard_diagram_generation",
    ):
        connection.execute(text(f"DROP FUNCTION {name}()"))
