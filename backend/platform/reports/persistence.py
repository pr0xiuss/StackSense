"""M5-owned metadata models, DDL, constraints and PostgreSQL guards.

Importing creates no tables; migrations and isolated tests manage DDL.
No upstream persistence or M1 lifecycle is accessed directly here.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, mapped_column

from backend.platform.projects.infra.base import Base

JSON_VALUE = JSON(none_as_null=True).with_variant(
    JSONB(none_as_null=True), "postgresql"
)


class ReportResourceModel(Base):
    __tablename__ = "report_resource"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(Uuid)
    architecture_version_id: Mapped[UUID] = mapped_column(Uuid)
    report_type: Mapped[str] = mapped_column(
        String(32), default="architecture_analysis"
    )
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    binding_fingerprint: Mapped[str] = mapped_column(String(64))
    scope: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    binding: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    captured_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    source_snapshot_digest: Mapped[str | None] = mapped_column(String(64))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_generation_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "architecture_version_id",
            "report_type",
            "input_fingerprint",
            "binding_fingerprint",
            name="uq_report_resource_binding",
        ),
        CheckConstraint(
            "report_type = 'architecture_analysis'",
            name="ck_report_type",
        ),
        CheckConstraint(
            "input_fingerprint ~ '^[0-9a-f]{64}$' "
            "AND binding_fingerprint ~ '^[0-9a-f]{64}$' "
            "AND (source_snapshot_digest IS NULL OR "
            "source_snapshot_digest ~ '^[0-9a-f]{64}$')",
            name="ck_report_resource_hashes",
        ),
        ForeignKeyConstraint(
            ["accepted_generation_id", "id"],
            ["report_generation.id", "report_generation.resource_id"],
            name="fk_report_active_generation",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        Index(
            "ix_report_resource_scope",
            "project_id",
            "architecture_version_id",
            "report_type",
        ),
    )


class ReportGenerationModel(Base):
    __tablename__ = "report_generation"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(
        ForeignKey("report_resource.id", ondelete="RESTRICT")
    )
    project_id: Mapped[UUID] = mapped_column(Uuid)
    architecture_version_id: Mapped[UUID] = mapped_column(Uuid)
    report_type: Mapped[str] = mapped_column(
        String(32), default="architecture_analysis"
    )
    work_id: Mapped[UUID] = mapped_column(Uuid)
    attempt_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    candidate_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    artifact_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    attempt_ordinal: Mapped[int] = mapped_column(BigInteger)
    fence: Mapped[int] = mapped_column(BigInteger)
    dispatch_epoch: Mapped[UUID] = mapped_column(Uuid)
    attempt_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    binding_fingerprint: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(24))

    manifest: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64))
    spec_digest: Mapped[str | None] = mapped_column(String(64))
    render_fingerprint: Mapped[str | None] = mapped_column(String(64))
    manifest_size: Mapped[int | None] = mapped_column(BigInteger)
    pdf_size: Mapped[int | None] = mapped_column(BigInteger)
    pdf_sha256: Mapped[str | None] = mapped_column(String(64))
    page_count: Mapped[int | None] = mapped_column(Integer)

    seal_proof: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    accepted_reference: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    acceptance_context: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    retirement_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    deletion_nonce: Mapped[UUID | None] = mapped_column(Uuid)
    deletion_actor: Mapped[UUID | None] = mapped_column(Uuid)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleting_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("id", "resource_id", name="uq_report_generation_resource"),
        CheckConstraint(
            "state IN ('STAGING','SEALED_VERIFIED','ACCEPTED',"
            "'INVALID','DELETING','DELETED')",
            name="ck_report_generation_state",
        ),
        CheckConstraint(
            "attempt_ordinal > 0 AND fence > 0 "
            "AND (manifest_size IS NULL OR manifest_size >= 0) "
            "AND (pdf_size IS NULL OR pdf_size >= 0)",
            name="ck_report_generation_numbers",
        ),
        CheckConstraint(
            "input_fingerprint ~ '^[0-9a-f]{64}$' "
            "AND binding_fingerprint ~ '^[0-9a-f]{64}$' "
            "AND (manifest_sha256 IS NULL OR manifest_sha256 ~ '^[0-9a-f]{64}$') "
            "AND (spec_digest IS NULL OR spec_digest ~ '^[0-9a-f]{64}$') "
            "AND (render_fingerprint IS NULL OR render_fingerprint ~ '^[0-9a-f]{64}$') "
            "AND (pdf_sha256 IS NULL OR pdf_sha256 ~ '^[0-9a-f]{64}$')",
            name="ck_report_generation_hashes",
        ),
        CheckConstraint(
            "state NOT IN ('SEALED_VERIFIED','ACCEPTED') OR ("
            "manifest IS NOT NULL AND manifest_sha256 IS NOT NULL "
            "AND spec_digest IS NOT NULL AND render_fingerprint IS NOT NULL "
            "AND manifest_size IS NOT NULL AND pdf_size IS NOT NULL "
            "AND pdf_sha256 IS NOT NULL AND page_count IS NOT NULL "
            "AND seal_proof IS NOT NULL AND sealed_at IS NOT NULL)",
            name="ck_report_sealed_proof",
        ),
        CheckConstraint(
            "state <> 'ACCEPTED' OR (accepted_reference IS NOT NULL AND "
            "acceptance_context IS NOT NULL AND accepted_at IS NOT NULL)",
            name="ck_report_acceptance",
        ),
        CheckConstraint(
            "state NOT IN ('DELETING','DELETED') OR (deletion_nonce IS NOT NULL AND "
            "deletion_actor IS NOT NULL AND retirement_snapshot IS NOT NULL AND "
            "deleting_at IS NOT NULL)",
            name="ck_report_deletion_reservation",
        ),
        CheckConstraint(
            "state <> 'DELETED' OR deleted_at IS NOT NULL", name="ck_report_deleted_at"
        ),
        Index(
            "ix_report_generation_history",
            "resource_id",
            "accepted_at",
            "id",
            postgresql_where=text("state = 'ACCEPTED'"),
        ),
        Index("ix_report_generation_cleanup", "state", "created_at", "id"),
    )


class ReportReadPinModel(Base):
    __tablename__ = "report_read_pin"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    generation_id: Mapped[UUID] = mapped_column(
        ForeignKey("report_generation.id", ondelete="RESTRICT")
    )
    actor_id: Mapped[UUID | None] = mapped_column(Uuid)
    purpose: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    token_hash: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint(
            "purpose IN ('api','download','export')",
            name="ck_report_pin_purpose",
        ),
        CheckConstraint(
            "expires_at > created_at AND "
            "expires_at <= created_at + interval '600 seconds'",
            name="ck_report_pin_lifetime",
        ),
        CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="ck_report_pin_hash"),
        Index("ix_report_pin_generation", "generation_id", "expires_at"),
    )


REPORT_TABLES = tuple(
    Base.metadata.tables[m.__tablename__]
    for m in (ReportResourceModel, ReportGenerationModel, ReportReadPinModel)
)

for _table in REPORT_TABLES:
    for _constraint in _table.constraints:
        if isinstance(_constraint, CheckConstraint):
            _constraint.ddl_if(dialect="postgresql")


def install_guards(connection: Connection, schema: str) -> None:
    """M5-only trigger installation for migrations and isolated tests."""
    if (
        connection.dialect.name != "postgresql"
        or re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", schema) is None
    ):
        raise ValueError("invalid report schema")
    q = connection.dialect.identifier_preparer.quote_schema(schema)
    connection.execute(text(f"""
      CREATE FUNCTION {q}.guard_report_generation() RETURNS trigger LANGUAGE plpgsql
      AS $$
    DECLARE r {q}.report_resource; immutable_new jsonb; immutable_old jsonb;
    BEGIN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'report tombstones are retained';
      END IF;
      SELECT * INTO STRICT r FROM {q}.report_resource
      WHERE id=NEW.resource_id FOR UPDATE;
      IF (NEW.project_id,NEW.architecture_version_id,NEW.report_type,
          NEW.input_fingerprint,NEW.binding_fingerprint)
      IS DISTINCT FROM (r.project_id,r.architecture_version_id,r.report_type,
          r.input_fingerprint,r.binding_fingerprint)
      THEN RAISE EXCEPTION 'report generation scope mismatch'; END IF;

      IF NEW.state IN ('SEALED_VERIFIED','ACCEPTED') THEN
        IF jsonb_typeof(NEW.manifest) IS DISTINCT FROM 'object'
           OR jsonb_typeof(NEW.seal_proof) IS DISTINCT FROM 'object'
           OR NOT (NEW.manifest ?& ARRAY['scope','binding','input_fingerprint',
                    'generation_id','artifact_id','members',
                    'source_snapshot_digest','report_spec_digest',
                    'render_fingerprint','artifact_schema_version'])
           OR NOT (NEW.seal_proof ?& ARRAY['verification_version',
                    'manifest_sha256','pdf_sha256','sealed_at'])
           OR NEW.manifest->'scope' IS DISTINCT FROM r.scope
           OR NEW.manifest->'binding' IS DISTINCT FROM r.binding
           OR NEW.manifest->>'generation_id' IS DISTINCT FROM NEW.id::text
           OR NEW.manifest->>'artifact_id' IS DISTINCT FROM NEW.artifact_id::text
           OR NEW.manifest->>'input_fingerprint' IS DISTINCT FROM
              NEW.input_fingerprint
           OR NEW.manifest->>'report_spec_digest' IS DISTINCT FROM
              NEW.spec_digest
           OR NEW.manifest->>'render_fingerprint' IS DISTINCT FROM
              NEW.render_fingerprint
           OR NEW.seal_proof->>'manifest_sha256' IS DISTINCT FROM
              NEW.manifest_sha256
           OR NEW.seal_proof->>'pdf_sha256' IS DISTINCT FROM NEW.pdf_sha256
           OR NEW.seal_proof->>'verification_version' IS DISTINCT FROM '1.0.0'
        THEN RAISE EXCEPTION 'report seal proof binding mismatch'; END IF;
      END IF;

      IF NEW.state='ACCEPTED' THEN
        IF jsonb_typeof(NEW.accepted_reference) IS DISTINCT FROM 'object'
           OR jsonb_typeof(NEW.acceptance_context) IS DISTINCT FROM 'object'
           OR NOT (NEW.acceptance_context ?&
                    ARRAY['transaction_id','attempt_id','reference'])
           OR NEW.accepted_reference->'scope' IS DISTINCT FROM r.scope
           OR NEW.accepted_reference->'binding' IS DISTINCT FROM r.binding
           OR NEW.accepted_reference->>'generation_id' IS DISTINCT FROM
              NEW.id::text
           OR NEW.accepted_reference->>'artifact_id' IS DISTINCT FROM
              NEW.artifact_id::text
           OR NEW.accepted_reference->>'candidate_id' IS DISTINCT FROM
              NEW.candidate_id::text
           OR NEW.accepted_reference->>'resource_id' IS DISTINCT FROM
              NEW.resource_id::text
           OR NEW.accepted_reference->>'input_fingerprint' IS DISTINCT FROM
              NEW.input_fingerprint
           OR NEW.accepted_reference->'sealed' IS DISTINCT FROM 'true'::jsonb
           OR NEW.accepted_reference->'digests'->>'content' IS DISTINCT FROM
              NEW.manifest_sha256
           OR NEW.accepted_reference->'digests'->>'spec' IS DISTINCT FROM
              NEW.spec_digest
           OR NEW.accepted_reference->>'size_bytes' IS DISTINCT FROM
              NEW.manifest_size::text
           OR NEW.acceptance_context->>'attempt_id' IS DISTINCT FROM
              NEW.attempt_id::text
           OR NEW.acceptance_context->'reference' IS DISTINCT FROM
              NEW.accepted_reference
        THEN RAISE EXCEPTION 'report accepted reference mismatch'; END IF;
        PERFORM (NEW.acceptance_context->>'transaction_id')::uuid;
      ELSIF COALESCE(NEW.accepted_reference <> 'null'::jsonb, false)
         OR COALESCE(NEW.acceptance_context <> 'null'::jsonb, false)
         OR NEW.accepted_at IS NOT NULL
      THEN RAISE EXCEPTION 'private generation cannot claim acceptance'; END IF;

      IF TG_OP='INSERT' THEN
        IF NEW.state <> 'STAGING' THEN
          RAISE EXCEPTION 'report starts private';
        END IF;
        RETURN NEW;
      END IF;

      IF OLD.state IN ('ACCEPTED','DELETED') THEN
        RAISE EXCEPTION 'terminal report generation';
      END IF;

      IF NEW.state <> OLD.state AND NOT (
        (OLD.state='STAGING' AND NEW.state IN
         ('SEALED_VERIFIED','INVALID','DELETING')) OR
        (OLD.state='SEALED_VERIFIED' AND NEW.state IN ('ACCEPTED','DELETING')) OR
        (OLD.state='INVALID' AND NEW.state='DELETING') OR
        (OLD.state='DELETING' AND NEW.state='DELETED'))
      THEN RAISE EXCEPTION 'invalid report transition'; END IF;

      immutable_new := to_jsonb(NEW) - ARRAY['state','manifest',
      'manifest_sha256','spec_digest','render_fingerprint','manifest_size',
      'pdf_size','pdf_sha256','page_count','seal_proof','accepted_reference',
      'acceptance_context','retirement_snapshot','deletion_nonce','deletion_actor',
      'sealed_at','accepted_at','deleting_at','deleted_at'];
      immutable_old := to_jsonb(OLD) - ARRAY['state','manifest',
      'manifest_sha256','spec_digest','render_fingerprint','manifest_size',
      'pdf_size','pdf_sha256','page_count','seal_proof','accepted_reference',
      'acceptance_context','retirement_snapshot','deletion_nonce','deletion_actor',
      'sealed_at','accepted_at','deleting_at','deleted_at'];

      IF immutable_new IS DISTINCT FROM immutable_old THEN
        RAISE EXCEPTION 'immutable report identity';
      END IF;

      IF OLD.state <> 'STAGING' AND (NEW.manifest,NEW.manifest_sha256,
      NEW.spec_digest,NEW.render_fingerprint,NEW.manifest_size,NEW.pdf_size,
      NEW.pdf_sha256,NEW.page_count,NEW.seal_proof,NEW.sealed_at)
      IS DISTINCT FROM (OLD.manifest,OLD.manifest_sha256,OLD.spec_digest,
      OLD.render_fingerprint,OLD.manifest_size,OLD.pdf_size,OLD.pdf_sha256,
      OLD.page_count,OLD.seal_proof,OLD.sealed_at)
      THEN RAISE EXCEPTION 'immutable report seal'; END IF;

      IF NEW.state='DELETING' AND EXISTS (
        SELECT 1 FROM {q}.report_read_pin WHERE generation_id=NEW.id
      ) THEN RAISE EXCEPTION 'pinned report'; END IF;

      RETURN NEW;
    END $$;

    CREATE TRIGGER guard_report_generation
    BEFORE INSERT OR UPDATE OR DELETE ON {q}.report_generation
    FOR EACH ROW EXECUTE FUNCTION {q}.guard_report_generation();

    CREATE FUNCTION {q}.guard_report_pointer() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.accepted_generation_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM {q}.report_generation
        WHERE id=NEW.accepted_generation_id AND
        resource_id=NEW.id AND state='ACCEPTED')
      THEN RAISE EXCEPTION 'report pointer requires accepted scoped generation';
      END IF;
      RETURN NEW;
    END $$;

    CREATE OR REPLACE FUNCTION {q}.immutable_report_resource()
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

      IF OLD.accepted_generation_id IS NOT NULL AND
         NEW.accepted_generation_id IS NULL
      THEN RAISE EXCEPTION 'accepted report pointer cannot be cleared'; END IF;
      RETURN NEW;
    END $$;

    CREATE TRIGGER immutable_report_resource
    BEFORE UPDATE ON {q}.report_resource
    FOR EACH ROW EXECUTE FUNCTION {q}.immutable_report_resource();

    CREATE CONSTRAINT TRIGGER guard_report_pointer
    AFTER INSERT OR UPDATE ON {q}.report_resource
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION {q}.guard_report_pointer();

    CREATE FUNCTION {q}.guard_report_pin()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM {q}.report_generation
        WHERE id=NEW.generation_id AND state='ACCEPTED' FOR SHARE
      ) THEN RAISE EXCEPTION 'read pin requires accepted generation'; END IF;
      RETURN NEW;
    END $$;

    CREATE TRIGGER guard_report_pin
    BEFORE INSERT OR UPDATE ON {q}.report_read_pin
    FOR EACH ROW EXECUTE FUNCTION {q}.guard_report_pin();
    """))
