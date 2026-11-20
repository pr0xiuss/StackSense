"""M4-owned metadata models and disposable B1 PostgreSQL constraint prototype.

Importing creates no tables; B1 installs only into explicitly isolated schemas.
No upstream persistence or M1 lifecycle is accessed here.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, mapped_column

from backend.platform.delivery.contracts import HandlerProfile, VersionScope
from backend.platform.diagrams.model import canonical_bytes
from backend.platform.projects.infra.base import Base

JSON_VALUE = JSON().with_variant(JSONB(), "postgresql")


def diagram_resource_id(
    scope: VersionScope, binding: HandlerProfile, input_fingerprint: str
) -> UUID:
    payload = canonical_bytes((scope.semantic_identity(), binding, input_fingerprint))
    return uuid5(
        NAMESPACE_URL,
        "stacksense:diagram-resource:1:" + hashlib.sha256(payload).hexdigest(),
    )


class DiagramResourceModel(Base):
    __tablename__ = "diagram_resource"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(Uuid)
    architecture_version_id: Mapped[UUID] = mapped_column(Uuid)
    template: Mapped[str] = mapped_column(String(32))
    canonical_digest: Mapped[str] = mapped_column(String(64))
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    binding_fingerprint: Mapped[str] = mapped_column(String(64))
    scope: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    binding: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    accepted_generation_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "architecture_version_id",
            "template",
            "input_fingerprint",
            "binding_fingerprint",
            name="uq_diagram_resource_binding",
        ),
        CheckConstraint(
            "template IN "
            "('system_overview','component_architecture','dependency_map','data_flow')",
            name="ck_diagram_template",
        ),
        CheckConstraint(
            "canonical_digest ~ '^[0-9a-f]{64}$' AND input_fingerprint ~ "
            "'^[0-9a-f]{64}$' AND binding_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_diagram_resource_hashes",
        ),
        ForeignKeyConstraint(
            ["accepted_generation_id", "id"],
            ["diagram_generation.id", "diagram_generation.resource_id"],
            name="fk_diagram_active_generation",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        Index(
            "ix_diagram_resource_scope",
            "project_id",
            "architecture_version_id",
            "template",
        ),
    )


class DiagramGenerationModel(Base):
    __tablename__ = "diagram_generation"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(
        ForeignKey("diagram_resource.id", ondelete="RESTRICT")
    )
    project_id: Mapped[UUID] = mapped_column(Uuid)
    architecture_version_id: Mapped[UUID] = mapped_column(Uuid)
    template: Mapped[str] = mapped_column(String(32))
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
    layout_digest: Mapped[str | None] = mapped_column(String(64))
    membership_digest: Mapped[str | None] = mapped_column(String(64))
    manifest_size: Mapped[int | None] = mapped_column(BigInteger)
    total_member_bytes: Mapped[int | None] = mapped_column(BigInteger)
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
        UniqueConstraint("id", "resource_id", name="uq_diagram_generation_resource"),
        CheckConstraint(
            "state IN ('STAGING','SEALED_VERIFIED','ACCEPTED','DELETING','DELETED')",
            name="ck_diagram_generation_state",
        ),
        CheckConstraint(
            "attempt_ordinal > 0 AND fence > 0 AND (manifest_size IS NULL OR "
            "manifest_size >= 0) AND (total_member_bytes IS NULL OR total_member_bytes "
            ">= 0)",
            name="ck_diagram_generation_numbers",
        ),
        CheckConstraint(
            "input_fingerprint ~ '^[0-9a-f]{64}$' AND binding_fingerprint ~ "
            "'^[0-9a-f]{64}$' AND (manifest_sha256 IS NULL OR manifest_sha256 ~ "
            "'^[0-9a-f]{64}$') AND (spec_digest IS NULL OR spec_digest ~ "
            "'^[0-9a-f]{64}$') AND (layout_digest IS NULL OR layout_digest ~ "
            "'^[0-9a-f]{64}$') AND (membership_digest IS NULL OR membership_digest ~ "
            "'^[0-9a-f]{64}$')",
            name="ck_diagram_generation_hashes",
        ),
        CheckConstraint(
            "state NOT IN ('SEALED_VERIFIED','ACCEPTED') OR (manifest IS NOT NULL AND "
            "manifest_sha256 IS NOT NULL AND spec_digest IS NOT NULL AND layout_digest "
            "IS NOT NULL AND membership_digest IS NOT NULL AND manifest_size IS NOT "
            "NULL AND total_member_bytes IS NOT NULL AND seal_proof IS NOT NULL AND "
            "sealed_at IS NOT NULL)",
            name="ck_diagram_sealed_proof",
        ),
        CheckConstraint(
            "state <> 'ACCEPTED' OR (accepted_reference IS NOT NULL AND "
            "acceptance_context IS NOT NULL AND accepted_at IS NOT NULL)",
            name="ck_diagram_acceptance",
        ),
        CheckConstraint(
            "state NOT IN ('DELETING','DELETED') OR (deletion_nonce IS NOT NULL AND "
            "deletion_actor IS NOT NULL AND retirement_snapshot IS NOT NULL AND "
            "deleting_at IS NOT NULL)",
            name="ck_diagram_deletion_reservation",
        ),
        CheckConstraint(
            "state <> 'DELETED' OR deleted_at IS NOT NULL", name="ck_diagram_deleted_at"
        ),
        Index(
            "ix_diagram_generation_history",
            "resource_id",
            "accepted_at",
            "id",
            postgresql_where=text("state = 'ACCEPTED'"),
        ),
        Index("ix_diagram_generation_cleanup", "state", "created_at", "id"),
    )


class DiagramReadPinModel(Base):
    __tablename__ = "diagram_read_pin"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    generation_id: Mapped[UUID] = mapped_column(
        ForeignKey("diagram_generation.id", ondelete="RESTRICT")
    )
    actor_id: Mapped[UUID | None] = mapped_column(Uuid)
    purpose: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    token_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('api','report','view') AND (actor_id IS NOT NULL OR purpose = "
            "'report')",
            name="ck_diagram_pin_purpose",
        ),
        CheckConstraint(
            "expires_at > created_at AND expires_at <= created_at + interval '300 "
            "seconds'",
            name="ck_diagram_pin_lifetime",
        ),
        CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="ck_diagram_pin_hash"),
        Index("ix_diagram_pin_generation", "generation_id", "expires_at"),
    )


DIAGRAM_TABLES = tuple(
    Base.metadata.tables[m.__tablename__]
    for m in (DiagramResourceModel, DiagramGenerationModel, DiagramReadPinModel)
)

# Frozen upstream unit suites create the shared metadata on SQLite. That is
# not a substitute for any M4 PostgreSQL proof; PG-specific checks/triggers
# remain mandatory on the real analysis persistence authority.
for _table in DIAGRAM_TABLES:
    for _constraint in _table.constraints:
        if isinstance(_constraint, CheckConstraint):
            _constraint.ddl_if(dialect="postgresql")


def install_prototype(connection: Connection, schema: str) -> None:
    """Disposable B1-only DDL. Never an import side effect or release migration."""
    if (
        connection.dialect.name != "postgresql"
        or not (connection.engine.url.database or "").startswith("stacksense_p5_b2_")
        or re.fullmatch(r"p5_diagram_[0-9a-f]{32}", schema) is None
    ):
        raise ValueError("disposable diagram database/schema required")
    Base.metadata.create_all(
        connection.execution_options(schema_translate_map={None: schema}),
        tables=DIAGRAM_TABLES,
    )
    install_guards(connection, schema)


def install_guards(connection: Connection, schema: str) -> None:
    """M4-only trigger installation for the additive migration and isolated tests."""
    if (
        connection.dialect.name != "postgresql"
        or re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", schema) is None
    ):
        raise ValueError("invalid diagram schema")
    q = connection.dialect.identifier_preparer.quote_schema(schema)
    connection.execute(text(f"""
      CREATE FUNCTION {q}.guard_diagram_generation() RETURNS trigger LANGUAGE plpgsql
      AS $$
    DECLARE r {q}.diagram_resource; immutable_new jsonb; immutable_old jsonb;
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'diagram tombstones are retained'; END
      IF;
      SELECT * INTO STRICT r FROM {q}.diagram_resource WHERE id=NEW.resource_id FOR
      UPDATE;
      IF (NEW.project_id,NEW.architecture_version_id,NEW.template,
      NEW.input_fingerprint,NEW.binding_fingerprint)
      IS DISTINCT FROM (r.project_id,r.architecture_version_id,r.template,
      r.input_fingerprint,r.binding_fingerprint)
      THEN RAISE EXCEPTION 'diagram generation scope mismatch'; END IF;
      IF NEW.state IN ('SEALED_VERIFIED','ACCEPTED') THEN
        IF jsonb_typeof(NEW.manifest) IS DISTINCT FROM 'object'
           OR jsonb_typeof(NEW.seal_proof) IS DISTINCT FROM 'object'
           OR NOT (NEW.manifest ?& ARRAY['scope','binding','input_fingerprint',
                    'generation_id','artifact_id','members','semantic_digest',
                    'layout_digest','membership_digest','artifact_schema_version'])
           OR NOT (NEW.seal_proof ?& ARRAY['verification_version','manifest_sha256',
                    'member_set_digest','physical_object_id','sealed_at'])
           OR NEW.manifest->'scope' IS DISTINCT FROM r.scope
           OR NEW.manifest->'binding' IS DISTINCT FROM r.binding
           OR NEW.manifest->>'generation_id' IS DISTINCT FROM NEW.id::text
           OR NEW.manifest->>'artifact_id' IS DISTINCT FROM NEW.artifact_id::text
           OR NEW.manifest->>'input_fingerprint' IS DISTINCT FROM NEW.input_fingerprint
           OR NEW.manifest->>'semantic_digest' IS DISTINCT FROM NEW.spec_digest
           OR NEW.manifest->>'layout_digest' IS DISTINCT FROM NEW.layout_digest
           OR NEW.manifest->>'membership_digest' IS DISTINCT FROM NEW.membership_digest
           OR NEW.seal_proof->>'manifest_sha256' IS DISTINCT FROM NEW.manifest_sha256
           OR NEW.seal_proof->>'verification_version' IS DISTINCT FROM '1.0.0'
        THEN RAISE EXCEPTION 'diagram seal proof binding mismatch'; END IF;
      END IF;
      IF NEW.state='ACCEPTED' THEN
        IF jsonb_typeof(NEW.accepted_reference) IS DISTINCT FROM 'object'
           OR jsonb_typeof(NEW.acceptance_context) IS DISTINCT FROM 'object'
      OR NOT (NEW.acceptance_context ?& ARRAY['transaction_id','attempt_id',
      'reference'])
           OR NEW.accepted_reference->'scope' IS DISTINCT FROM r.scope
           OR NEW.accepted_reference->'binding' IS DISTINCT FROM r.binding
           OR NEW.accepted_reference->>'generation_id' IS DISTINCT FROM NEW.id::text
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
      OR NEW.accepted_reference->'digests'->>'layout' IS DISTINCT FROM
      NEW.layout_digest
      OR NEW.accepted_reference->>'size_bytes' IS DISTINCT FROM
      NEW.manifest_size::text
           OR NEW.acceptance_context->>'attempt_id' IS DISTINCT FROM
              NEW.attempt_id::text
           OR NEW.acceptance_context->'reference' IS DISTINCT FROM
              NEW.accepted_reference
        THEN RAISE EXCEPTION 'diagram accepted reference mismatch'; END IF;
        PERFORM (NEW.acceptance_context->>'transaction_id')::uuid;
      ELSIF COALESCE(NEW.accepted_reference <> 'null'::jsonb,false)
         OR COALESCE(NEW.acceptance_context <> 'null'::jsonb,false)
         OR NEW.accepted_at IS NOT NULL
      THEN RAISE EXCEPTION 'private generation cannot claim acceptance'; END IF;
      IF TG_OP='INSERT' THEN
        IF NEW.state <> 'STAGING' THEN RAISE EXCEPTION 'diagram starts private'; END IF;
        RETURN NEW;
      END IF;
      IF OLD.state IN ('ACCEPTED','DELETED') THEN RAISE EXCEPTION
      'terminal diagram generation'; END IF;
      IF NEW.state <> OLD.state AND NOT (
        (OLD.state='STAGING' AND NEW.state IN ('SEALED_VERIFIED','DELETING')) OR
        (OLD.state='SEALED_VERIFIED' AND NEW.state IN ('ACCEPTED','DELETING')) OR
        (OLD.state='DELETING' AND NEW.state='DELETED'))
      THEN RAISE EXCEPTION 'invalid diagram transition'; END IF;
      immutable_new := to_jsonb(NEW) - ARRAY['state','manifest','manifest_sha256',
      'spec_digest','layout_digest','membership_digest','manifest_size',
      'total_member_bytes','seal_proof','accepted_reference','acceptance_context',
      'retirement_snapshot','deletion_nonce','deletion_actor','sealed_at',
      'accepted_at','deleting_at','deleted_at'];
      immutable_old := to_jsonb(OLD) - ARRAY['state','manifest','manifest_sha256',
      'spec_digest','layout_digest','membership_digest','manifest_size',
      'total_member_bytes','seal_proof','accepted_reference','acceptance_context',
      'retirement_snapshot','deletion_nonce','deletion_actor','sealed_at',
      'accepted_at','deleting_at','deleted_at'];
      IF immutable_new IS DISTINCT FROM immutable_old THEN RAISE EXCEPTION
      'immutable diagram identity'; END IF;
      IF OLD.state <> 'STAGING' AND (NEW.manifest,NEW.manifest_sha256,NEW.spec_digest,
      NEW.layout_digest,NEW.membership_digest,NEW.manifest_size,
      NEW.total_member_bytes,NEW.seal_proof,NEW.sealed_at)
      IS DISTINCT FROM (OLD.manifest,OLD.manifest_sha256,OLD.spec_digest,
      OLD.layout_digest,OLD.membership_digest,OLD.manifest_size,
      OLD.total_member_bytes,OLD.seal_proof,OLD.sealed_at)
      THEN RAISE EXCEPTION 'immutable diagram seal'; END IF;
      IF NEW.state='DELETING' AND EXISTS (SELECT 1 FROM {q}.diagram_read_pin WHERE
      generation_id=NEW.id)
      THEN RAISE EXCEPTION 'pinned diagram'; END IF;
      RETURN NEW;
    END $$;
      CREATE TRIGGER guard_diagram_generation BEFORE INSERT OR UPDATE OR DELETE ON
      {q}.diagram_generation
    FOR EACH ROW EXECUTE FUNCTION {q}.guard_diagram_generation();
    CREATE FUNCTION {q}.guard_diagram_pointer() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.accepted_generation_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM {q}.diagram_generation WHERE id=NEW.accepted_generation_id AND
      resource_id=NEW.id AND state='ACCEPTED')
      THEN RAISE EXCEPTION 'diagram pointer requires accepted scoped generation'; END
      IF;
      RETURN NEW;
    END $$;
      CREATE FUNCTION {q}.immutable_diagram_resource() RETURNS trigger LANGUAGE
      plpgsql AS $$
    BEGIN
      IF (to_jsonb(NEW) - 'accepted_generation_id')
         IS DISTINCT FROM (to_jsonb(OLD) - 'accepted_generation_id')
      THEN RAISE EXCEPTION 'immutable diagram resource'; END IF;
      IF OLD.accepted_generation_id IS NOT NULL AND NEW.accepted_generation_id IS NULL
      THEN RAISE EXCEPTION 'accepted pointer cannot be cleared'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER immutable_diagram_resource BEFORE UPDATE ON {q}.diagram_resource
    FOR EACH ROW EXECUTE FUNCTION {q}.immutable_diagram_resource();
      CREATE CONSTRAINT TRIGGER guard_diagram_pointer AFTER INSERT OR UPDATE ON
      {q}.diagram_resource
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION
      {q}.guard_diagram_pointer();
    CREATE FUNCTION {q}.guard_diagram_pin() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM {q}.diagram_generation WHERE id=NEW.generation_id
      AND state='ACCEPTED' FOR SHARE)
      THEN RAISE EXCEPTION 'read pin requires accepted generation'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_diagram_pin BEFORE INSERT OR UPDATE ON {q}.diagram_read_pin
    FOR EACH ROW EXECUTE FUNCTION {q}.guard_diagram_pin();
    """))
