"""P5-C1 deterministic knowledge projection and metadata allowlist validation.

This module implements the pure KnowledgeProjector translating an immutable
ArchitectureDocument and VersionScope into a deterministic KnowledgeProjection,
strictly enforcing §7.4 and §7.10 of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

import collections
import math
import re
from collections.abc import Mapping
from typing import Any, Final

from backend.platform.analysis.architecture.model import (
    ArchitectureDocument,
)
from backend.platform.delivery.contracts import (
    ProducerProfile,
    VersionScope,
)
from backend.platform.knowledge.contracts import (
    SearchCapacityExceededError,
    SearchIntegrityError,
)
from backend.platform.knowledge.model import (
    C1_CONTRACT_VERSION,
    SUMMARY_CANONICAL_REFERENCE,
    KnowledgeCounts,
    KnowledgeDocumentKind,
    KnowledgeModelError,
    KnowledgeProjection,
    KnowledgeRecord,
    SourceReferenceDescriptor,
    compute_projection_digest,
)

MAX_ENTITIES: Final[int] = 25_000
MAX_RELATIONSHIPS: Final[int] = 50_000
MAX_EVIDENCE: Final[int] = 75_000
MAX_UNRESOLVED: Final[int] = 10_000
MAX_CONFLICTS: Final[int] = 5_000
MAX_CANONICAL_SOURCE_BYTES: Final[int] = 128 * 1024 * 1024  # 128 MiB
MAX_METADATA_STRING_LENGTH: Final[int] = 500

ALLOWED_METADATA_KEYS: Final[frozenset[str]] = frozenset(
    {
        "framework",
        "architectural_role",
        "runtime_role",
        "application_namespace",
        "method",
        "path",
        "database_engine",
        "infrastructure_kind",
        "dependency_name",
        "manifest_declared",
        "source_referenced",
    }
)

_HOST_PATH_RE = re.compile(
    r"(?:^[A-Za-z]:[/\\])|(?:^/(?:home|Users|var|tmp|etc|root|usr|opt)/)"
    r"|(?:^\\\\)|(?:^//)"
)

_SENSITIVE_RE = re.compile(
    r"(?:password|passwd|secret|token|private_key|\bauth\b|auth_|api_key|credential|certificate_key)",
    re.I,
)


def filter_safe_metadata(
    raw_metadata: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Filter raw metadata against the strict allowlist and safety rules.

    Returns:
        tuple of (safe_metadata, omitted_counts_by_key).
    """
    if not raw_metadata:
        return {}, {}

    safe: dict[str, Any] = {}
    omitted: collections.Counter[str] = collections.Counter()

    for k, v in raw_metadata.items():
        key_str = str(k)
        if key_str not in ALLOWED_METADATA_KEYS:
            omitted[key_str] += 1
            continue

        if _SENSITIVE_RE.search(key_str):
            omitted[key_str] += 1
            continue

        if v is None:
            omitted[key_str] += 1
            continue

        if isinstance(v, bool):
            safe[key_str] = v
            continue

        if isinstance(v, int):
            safe[key_str] = v
            continue

        if isinstance(v, float):
            if math.isfinite(v):
                safe[key_str] = v
            else:
                omitted[key_str] += 1
            continue

        if isinstance(v, str):
            if len(v) > MAX_METADATA_STRING_LENGTH:
                omitted[key_str] += 1
                continue
            if _SENSITIVE_RE.search(v):
                omitted[key_str] += 1
                continue
            if _HOST_PATH_RE.search(v):
                omitted[key_str] += 1
                continue
            if key_str == "path":
                raw_path = v.replace("\\", "/")
                if (
                    raw_path.startswith("/")
                    or ".." in raw_path.split("/")
                    or _HOST_PATH_RE.search(raw_path)
                ):
                    omitted[key_str] += 1
                    continue
                safe[key_str] = raw_path
                continue

            safe[key_str] = v
            continue

        # Any non-scalar is omitted
        omitted[key_str] += 1

    return safe, dict(omitted)


class KnowledgeProjector:
    """Pure deterministic projector converting ArchitectureDocument to projection."""

    def project(
        self,
        document: ArchitectureDocument,
        scope: VersionScope,
        profile: ProducerProfile | None = None,
        *,
        canonical_source_bytes: bytes | None = None,
    ) -> KnowledgeProjection:
        """Project architecture document into deterministic knowledge projection.

        Raises:
            SearchIntegrityError: if scope does not match document exactly.
            SearchCapacityExceededError: if document exceeds approved capacity caps.
        """
        self._validate_scope(document=document, scope=scope)
        self._validate_capacity(
            document=document, canonical_source_bytes=canonical_source_bytes
        )

        total_omitted: collections.Counter[str] = collections.Counter()

        # 1. Project Entities
        entity_records: list[KnowledgeRecord] = []
        for ent in document.entities:
            safe_meta, omitted = filter_safe_metadata(ent.metadata)
            total_omitted.update(omitted)
            tf: dict[str, str] = {
                "name": ent.name,
                "kind": ent.kind.value,
                "status": ent.status.value,
            }
            if ent.namespace:
                tf["namespace"] = ".".join(ent.namespace)

            try:
                rec = KnowledgeRecord.create(
                    scope=scope,
                    document_kind=KnowledgeDocumentKind.ENTITY,
                    canonical_reference=ent.logical_id,
                    title=ent.name,
                    text_fields=tf,
                    kind=ent.kind.value,
                    status=ent.status.value,
                    evidence_ids=ent.evidence_ids,
                    safe_metadata=safe_meta,
                )
            except KnowledgeModelError as exc:
                raise SearchIntegrityError(
                    f"Entity record creation failed for {ent.logical_id}: {exc}",
                    safe_details={"logical_id": ent.logical_id, "error": str(exc)},
                ) from exc
            entity_records.append(rec)

        # 2. Project Relationships
        rel_records: list[KnowledgeRecord] = []
        for rel in document.relationships:
            safe_meta, omitted = filter_safe_metadata(rel.metadata)
            total_omitted.update(omitted)
            tf = {
                "kind": rel.kind.value,
                "status": rel.status.value,
                "source_logical_id": rel.source_logical_id,
                "target_logical_id": rel.target_logical_id,
            }
            title = f"{rel.source_logical_id} -> {rel.target_logical_id}"
            try:
                rec = KnowledgeRecord.create(
                    scope=scope,
                    document_kind=KnowledgeDocumentKind.RELATIONSHIP,
                    canonical_reference=rel.logical_id,
                    title=title,
                    text_fields=tf,
                    kind=rel.kind.value,
                    status=rel.status.value,
                    source_logical_id=rel.source_logical_id,
                    target_logical_id=rel.target_logical_id,
                    evidence_ids=rel.evidence_ids,
                    safe_metadata=safe_meta,
                )
            except KnowledgeModelError as exc:
                raise SearchIntegrityError(
                    f"Relationship record creation failed for {rel.logical_id}: {exc}",
                    safe_details={"logical_id": rel.logical_id, "error": str(exc)},
                ) from exc
            rel_records.append(rec)

        # 3. Project Evidence
        evidence_records: list[KnowledgeRecord] = []
        for ev in document.evidence:
            safe_meta, omitted = filter_safe_metadata(ev.metadata)
            total_omitted.update(omitted)
            try:
                source_ref = SourceReferenceDescriptor(
                    source_record_type=ev.source_record_type,
                    path=ev.path,
                    artifact_id=ev.artifact_id,
                    source_fact_key=ev.source_fact_key,
                    source_range=dict(ev.source_range) if ev.source_range else None,
                    producer_id=ev.producer_id,
                    producer_version=ev.producer_version,
                    strength=ev.strength.value,
                    polarity=ev.polarity.value,
                )
                tf = {
                    "path": ev.path,
                    "source_record_type": ev.source_record_type,
                    "strength": ev.strength.value,
                    "polarity": ev.polarity.value,
                }
                rec = KnowledgeRecord.create(
                    scope=scope,
                    document_kind=KnowledgeDocumentKind.EVIDENCE,
                    canonical_reference=ev.logical_id,
                    title=ev.path,
                    text_fields=tf,
                    kind=ev.source_record_type,
                    status=ev.strength.value,
                    source_reference=source_ref,
                    safe_metadata=safe_meta,
                )
            except KnowledgeModelError as exc:
                raise SearchIntegrityError(
                    f"Evidence record creation failed for {ev.logical_id}: {exc}",
                    safe_details={"logical_id": ev.logical_id, "error": str(exc)},
                ) from exc
            evidence_records.append(rec)

        # 4. Project Unresolved Relationships
        unres_records: list[KnowledgeRecord] = []
        for unres in document.unresolved_relationships:
            safe_meta, omitted = filter_safe_metadata(unres.metadata)
            total_omitted.update(omitted)
            tf = {
                "kind": unres.kind.value,
                "status": unres.status.value,
                "source_logical_id": unres.source_logical_id,
                "target_descriptor": unres.target_descriptor,
                "reason": unres.reason.value,
            }
            title = f"Unresolved: {unres.target_descriptor}"
            try:
                rec = KnowledgeRecord.create(
                    scope=scope,
                    document_kind=KnowledgeDocumentKind.UNRESOLVED,
                    canonical_reference=unres.logical_id,
                    title=title,
                    text_fields=tf,
                    kind=unres.kind.value,
                    status=unres.status.value,
                    source_logical_id=unres.source_logical_id,
                    evidence_ids=unres.evidence_ids,
                    safe_metadata=safe_meta,
                )
            except KnowledgeModelError as exc:
                raise SearchIntegrityError(
                    f"Unresolved record creation failed for {unres.logical_id}: {exc}",
                    safe_details={"logical_id": unres.logical_id, "error": str(exc)},
                ) from exc
            unres_records.append(rec)

        # 5. Project Conflicts
        conf_records: list[KnowledgeRecord] = []
        for conf in document.conflicts:
            safe_meta, omitted = filter_safe_metadata(conf.details)
            total_omitted.update(omitted)
            tf = {
                "conflict_type": conf.conflict_type,
                "subject_key": conf.subject_key,
            }
            title = f"Conflict: {conf.conflict_type}"
            try:
                rec = KnowledgeRecord.create(
                    scope=scope,
                    document_kind=KnowledgeDocumentKind.CONFLICT,
                    canonical_reference=conf.logical_id,
                    title=title,
                    text_fields=tf,
                    kind=conf.conflict_type,
                    status="conflicting",
                    evidence_ids=conf.evidence_ids,
                    safe_metadata=safe_meta,
                )
            except KnowledgeModelError as exc:
                raise SearchIntegrityError(
                    f"Conflict record creation failed for {conf.logical_id}: {exc}",
                    safe_details={"logical_id": conf.logical_id, "error": str(exc)},
                ) from exc
            conf_records.append(rec)

        # 6. Project Architecture Summary Document
        summary_tf = {
            "analyzer_version": document.analyzer_version,
            "architecture_schema_version": document.architecture_schema_version,
            "configuration_fingerprint": document.configuration_fingerprint,
            "content_digest": document.content_digest,
            "ir_schema_version": document.ir_schema_version,
            "status": "published",
        }
        summary_meta = {
            "source_referenced": "architecture_model",
        }
        try:
            summary_record = KnowledgeRecord.create(
                scope=scope,
                document_kind=KnowledgeDocumentKind.ARCHITECTURE_SUMMARY,
                canonical_reference=SUMMARY_CANONICAL_REFERENCE,
                title="Architecture Summary",
                text_fields=summary_tf,
                kind="architecture_summary",
                status="published",
                safe_metadata=summary_meta,
            )
        except KnowledgeModelError as exc:
            raise SearchIntegrityError(
                f"Architecture summary record creation failed: {exc}",
                safe_details={"error": str(exc)},
            ) from exc

        # 7. Aggregate counts and build projection
        all_records = tuple(
            entity_records
            + rel_records
            + evidence_records
            + unres_records
            + conf_records
            + [summary_record]
        )

        counts = KnowledgeCounts(
            entities=len(entity_records),
            relationships=len(rel_records),
            evidence=len(evidence_records),
            unresolved=len(unres_records),
            conflicts=len(conf_records),
            architecture_summaries=1,
            total_records=len(all_records),
        )

        sorted_records = tuple(
            sorted(
                all_records,
                key=lambda r: (r.document_kind.value, r.knowledge_key),
            )
        )

        projection_digest = compute_projection_digest(
            c1_version=C1_CONTRACT_VERSION,
            scope=scope,
            source_content_digest=document.content_digest,
            records=sorted_records,
            counts=counts,
        )

        clean_omitted = {k: v for k, v in sorted(total_omitted.items()) if v > 0}

        return KnowledgeProjection(
            c1_version=C1_CONTRACT_VERSION,
            scope=scope,
            records=sorted_records,
            counts=counts,
            projection_digest=projection_digest,
            source_content_digest=document.content_digest,
            omitted_metadata_counts=clean_omitted,
        )

    def _validate_scope(
        self,
        *,
        document: ArchitectureDocument,
        scope: VersionScope,
    ) -> None:
        """Verify strict identity and digest alignment between document and scope."""
        if document.architecture_version_id != scope.architecture_version_id:
            raise SearchIntegrityError(
                f"Architecture version mismatch: document "
                f"{document.architecture_version_id} != "
                f"scope {scope.architecture_version_id}",
                safe_details={
                    "expected": str(scope.architecture_version_id),
                    "actual": str(document.architecture_version_id),
                },
            )
        if document.project_id != scope.project_id:
            raise SearchIntegrityError(
                f"Project ID mismatch: document {document.project_id} != "
                f"scope {scope.project_id}",
                safe_details={
                    "expected": str(scope.project_id),
                    "actual": str(document.project_id),
                },
            )
        if document.repository_id != scope.repository_id:
            raise SearchIntegrityError(
                f"Repository ID mismatch: document {document.repository_id} != "
                f"scope {scope.repository_id}",
                safe_details={
                    "expected": str(scope.repository_id),
                    "actual": str(document.repository_id),
                },
            )
        if document.analysis_id != scope.analysis_id:
            raise SearchIntegrityError(
                f"Analysis ID mismatch: document {document.analysis_id} != "
                f"scope {scope.analysis_id}",
                safe_details={
                    "expected": str(scope.analysis_id),
                    "actual": str(document.analysis_id),
                },
            )
        if document.snapshot_id != scope.snapshot_id:
            raise SearchIntegrityError(
                f"Snapshot ID mismatch: document {document.snapshot_id} != "
                f"scope {scope.snapshot_id}",
                safe_details={
                    "expected": str(scope.snapshot_id),
                    "actual": str(document.snapshot_id),
                },
            )
        if document.content_digest != scope.canonical_digest:
            raise SearchIntegrityError(
                f"Content digest mismatch: document {document.content_digest} != "
                f"scope {scope.canonical_digest}",
                safe_details={
                    "expected": scope.canonical_digest,
                    "actual": document.content_digest,
                },
            )
        if document.configuration_fingerprint != scope.configuration_fingerprint:
            raise SearchIntegrityError(
                "Configuration fingerprint mismatch: document "
                f"{document.configuration_fingerprint} != "
                f"scope {scope.configuration_fingerprint}",
                safe_details={
                    "expected": scope.configuration_fingerprint,
                    "actual": document.configuration_fingerprint,
                },
            )

    def _validate_capacity(
        self,
        *,
        document: ArchitectureDocument,
        canonical_source_bytes: bytes | None,
    ) -> None:
        """Enforce strict frozen capacity caps, failing closed on violation."""
        if len(document.entities) > MAX_ENTITIES:
            raise SearchCapacityExceededError(
                f"Entity count {len(document.entities)} exceeds limit {MAX_ENTITIES}",
                safe_details={"count": len(document.entities), "limit": MAX_ENTITIES},
            )
        if len(document.relationships) > MAX_RELATIONSHIPS:
            raise SearchCapacityExceededError(
                f"Relationship count {len(document.relationships)} "
                f"exceeds limit {MAX_RELATIONSHIPS}",
                safe_details={
                    "count": len(document.relationships),
                    "limit": MAX_RELATIONSHIPS,
                },
            )
        if len(document.evidence) > MAX_EVIDENCE:
            raise SearchCapacityExceededError(
                f"Evidence count {len(document.evidence)} exceeds limit {MAX_EVIDENCE}",
                safe_details={"count": len(document.evidence), "limit": MAX_EVIDENCE},
            )
        if len(document.unresolved_relationships) > MAX_UNRESOLVED:
            raise SearchCapacityExceededError(
                f"Unresolved relationship count "
                f"{len(document.unresolved_relationships)} "
                f"exceeds limit {MAX_UNRESOLVED}",
                safe_details={
                    "count": len(document.unresolved_relationships),
                    "limit": MAX_UNRESOLVED,
                },
            )
        if len(document.conflicts) > MAX_CONFLICTS:
            raise SearchCapacityExceededError(
                f"Conflict count {len(document.conflicts)} "
                f"exceeds limit {MAX_CONFLICTS}",
                safe_details={
                    "count": len(document.conflicts),
                    "limit": MAX_CONFLICTS,
                },
            )
        if (
            canonical_source_bytes is not None
            and len(canonical_source_bytes) > MAX_CANONICAL_SOURCE_BYTES
        ):
            raise SearchCapacityExceededError(
                f"Canonical source size {len(canonical_source_bytes)} "
                f"bytes exceeds limit {MAX_CANONICAL_SOURCE_BYTES} bytes",
                safe_details={
                    "size_bytes": len(canonical_source_bytes),
                    "limit_bytes": MAX_CANONICAL_SOURCE_BYTES,
                },
            )


__all__ = [
    "ALLOWED_METADATA_KEYS",
    "MAX_CANONICAL_SOURCE_BYTES",
    "MAX_CONFLICTS",
    "MAX_ENTITIES",
    "MAX_EVIDENCE",
    "MAX_METADATA_STRING_LENGTH",
    "MAX_RELATIONSHIPS",
    "MAX_UNRESOLVED",
    "KnowledgeProjector",
    "filter_safe_metadata",
]
