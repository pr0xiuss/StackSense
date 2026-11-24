"""Correct M5 JSON-null first capture and preserve all committed snapshot fields.

Revision ID: f4c6b8d2a901
Revises: e3b8a1c94d2f
"""

from alembic import op
from sqlalchemy import text

revision = "f4c6b8d2a901"
down_revision = "e3b8a1c94d2f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing JSON null is an empty slot, not a captured immutable object.
    # No data rewrite, accepted-history deletion or upstream DDL.
    op.execute(text("""
    CREATE OR REPLACE FUNCTION immutable_report_resource()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF (to_jsonb(NEW) - ARRAY['accepted_generation_id','captured_snapshot',
          'source_snapshot_digest','captured_at'])
         IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['accepted_generation_id',
          'captured_snapshot','source_snapshot_digest','captured_at'])
      THEN RAISE EXCEPTION 'immutable report resource'; END IF;
      IF jsonb_typeof(OLD.captured_snapshot)='object' AND
         (NEW.captured_snapshot,NEW.source_snapshot_digest,NEW.captured_at)
         IS DISTINCT FROM
         (OLD.captured_snapshot,OLD.source_snapshot_digest,OLD.captured_at)
      THEN RAISE EXCEPTION 'captured report snapshot is insert-once'; END IF;
      IF OLD.accepted_generation_id IS NOT NULL AND NEW.accepted_generation_id IS NULL
      THEN RAISE EXCEPTION 'accepted report pointer cannot be cleared'; END IF;
      RETURN NEW;
    END $$;
    """))


def downgrade() -> None:
    # Restoring the defective guard would reject legitimate first captures and
    # permit checksum/time mutation; a downgrade is deliberately fail-closed.
    raise RuntimeError("report snapshot-integrity correction cannot be downgraded")
