"""P5-C1 knowledge model, immutable records, canonical hashing, and manifest.

This module defines the frozen domain vocabulary and deterministic records for
Phase 5 Module 2 (Knowledge Projection & Search Index), adhering to §7.4 of
PROJECT_CONTEXT.md.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from enum import StrEnum
from typing import Annotated, Any, Final, Literal, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

from backend.platform.delivery.contracts import (
    Digest,
    ProducerProfile,
    VersionScope,
)

C1_CONTRACT_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
SUMMARY_CANONICAL_REFERENCE: Final[str] = "__architecture_summary__"

PositiveInt = Annotated[StrictInt, Field(gt=0)]
NonnegativeInt = Annotated[StrictInt, Field(ge=0)]

_HOST_PATH_RE = re.compile(
    r"(?:^[A-Za-z]:[/\\])|(?:^/(?:home|Users|var|tmp|etc|root|usr|opt)/)"
    r"|(?:^\\\\)|(?:^//)"
)
_SENSITIVE_KEY_RE = re.compile(
    r"(?:password|passwd|secret|token|private_key|\bauth\b|auth_|api_key|credential|certificate_key)",
    re.I,
)


class KnowledgeModelError(ValueError):
    """Base error for knowledge model contract violations."""


class KnowledgeDocumentKind(StrEnum):
    """Closed document kind vocabulary for the search projection."""

    ENTITY = "entity"
    RELATIONSHIP = "relationship"
    EVIDENCE = "evidence"
    UNRESOLVED = "unresolved"
    CONFLICT = "conflict"
    ARCHITECTURE_SUMMARY = "architecture_summary"


class SourceReferenceDescriptor(BaseModel):
    """Safe repository-relative source provenance without source text bodies."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    source_record_type: str
    path: str
    artifact_id: UUID | None = None
    source_fact_key: str | None = None
    source_range: dict[str, int] | None = None
    producer_id: str | None = None
    producer_version: str | None = None
    strength: str | None = None
    polarity: str | None = None

    @field_validator("path")
    @classmethod
    def _validate_safe_path(cls, v: str) -> str:
        raw = v.replace("\\", "/")
        if raw.startswith("/"):
            raise KnowledgeModelError("path must be repository-relative")
        if ".." in raw.split("/"):
            raise KnowledgeModelError("path must not contain '..'")
        if _HOST_PATH_RE.search(raw):
            raise KnowledgeModelError("path must not contain host absolute prefixes")
        return raw


class KnowledgeCounts(BaseModel):
    """Deterministic counts of projected knowledge records."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    entities: NonnegativeInt
    relationships: NonnegativeInt
    evidence: NonnegativeInt
    unresolved: NonnegativeInt
    conflicts: NonnegativeInt
    architecture_summaries: NonnegativeInt
    total_records: NonnegativeInt

    @model_validator(mode="after")
    def _validate_total(self) -> Self:
        summed = (
            self.entities
            + self.relationships
            + self.evidence
            + self.unresolved
            + self.conflicts
            + self.architecture_summaries
        )
        if self.total_records != summed:
            raise KnowledgeModelError(
                f"total_records {self.total_records} does not match "
                f"sum of counts {summed}"
            )
        return self


def canonical_json(value: Any) -> str:
    """Serialize value to deterministic canonical JSON with sorted keys."""
    return json.dumps(
        _to_canonical_obj(value),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def _to_canonical_obj(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _to_canonical_obj(value.model_dump(mode="json"))
    if isinstance(value, UUID):
        return str(value).lower()
    if isinstance(value, StrEnum):
        return str(value.value)
    if isinstance(value, (int, bool)) or value is None:
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise KnowledgeModelError("non-finite float in canonical JSON")
        return value
    if isinstance(value, str):
        value.encode("utf-8", errors="strict")
        return value
    if isinstance(value, dict):
        return {str(k): _to_canonical_obj(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_to_canonical_obj(v) for v in value]
    if isinstance(value, (set, frozenset)):
        items = [_to_canonical_obj(v) for v in value]
        return sorted(items, key=lambda x: str(x))
    raise KnowledgeModelError(f"unsupported canonical JSON type: {type(value)}")


def compute_knowledge_key(
    *,
    c1_version: str,
    project_id: UUID,
    architecture_version_id: UUID,
    document_kind: KnowledgeDocumentKind,
    canonical_reference: str,
) -> str:
    """Compute deterministic SHA-256 knowledge key for a document."""
    payload = {
        "c1_version": c1_version,
        "identity": [
            str(project_id).lower(),
            str(architecture_version_id).lower(),
            str(document_kind.value),
            canonical_reference,
        ],
    }
    encoded = canonical_json(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compute_storage_key(
    *,
    c1_version: str,
    knowledge_key: str,
    generation_id: UUID,
) -> str:
    """Compute generation-scoped storage key used as Elasticsearch _id."""
    payload = {
        "c1_version": c1_version,
        "identity": [
            knowledge_key,
            str(generation_id).lower(),
        ],
    }
    encoded = canonical_json(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class KnowledgeRecord(BaseModel):
    """Immutable projected knowledge record representing a searchable element."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    c1_version: Literal["1.0.0"] = C1_CONTRACT_VERSION
    scope: VersionScope
    document_kind: KnowledgeDocumentKind
    canonical_reference: str
    knowledge_key: Digest
    title: str
    text_fields: dict[str, str] = Field(default_factory=dict)
    kind: str | None = None
    status: str | None = None
    source_logical_id: str | None = None
    target_logical_id: str | None = None
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    source_reference: SourceReferenceDescriptor | None = None
    safe_metadata: dict[str, Any] = Field(default_factory=dict)
    record_digest: Digest

    @field_validator("evidence_ids", mode="after")
    @classmethod
    def _sort_evidence_ids(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(v)))

    @model_validator(mode="after")
    def _validate_record_digest(self) -> Self:
        expected = self.compute_semantic_digest()
        if self.record_digest != expected:
            raise KnowledgeModelError(
                f"record_digest {self.record_digest} does not match computed {expected}"
            )
        return self

    @classmethod
    def create(
        cls,
        *,
        scope: VersionScope,
        document_kind: KnowledgeDocumentKind,
        canonical_reference: str,
        title: str,
        text_fields: dict[str, str] | None = None,
        kind: str | None = None,
        status: str | None = None,
        source_logical_id: str | None = None,
        target_logical_id: str | None = None,
        evidence_ids: tuple[str, ...] = (),
        source_reference: SourceReferenceDescriptor | None = None,
        safe_metadata: dict[str, Any] | None = None,
    ) -> KnowledgeRecord:
        """Create a KnowledgeRecord with deterministic key and verified digest."""
        k_key = compute_knowledge_key(
            c1_version=C1_CONTRACT_VERSION,
            project_id=scope.project_id,
            architecture_version_id=scope.architecture_version_id,
            document_kind=document_kind,
            canonical_reference=canonical_reference,
        )
        safe_tf = dict(text_fields) if text_fields else {}
        safe_meta = dict(safe_metadata) if safe_metadata else {}
        sorted_evidence = tuple(sorted(set(evidence_ids)))
        payload = {
            "c1_version": C1_CONTRACT_VERSION,
            "scope_identity": scope.semantic_identity(),
            "document_kind": document_kind.value,
            "canonical_reference": canonical_reference,
            "knowledge_key": k_key,
            "title": title,
            "text_fields": dict(sorted(safe_tf.items())),
            "kind": kind,
            "status": status,
            "source_logical_id": source_logical_id,
            "target_logical_id": target_logical_id,
            "evidence_ids": list(sorted_evidence),
            "source_reference": (
                source_reference.model_dump(mode="json") if source_reference else None
            ),
            "safe_metadata": dict(sorted(safe_meta.items())),
        }
        digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        return cls(
            c1_version=C1_CONTRACT_VERSION,
            scope=scope,
            document_kind=document_kind,
            canonical_reference=canonical_reference,
            knowledge_key=k_key,
            title=title,
            text_fields=safe_tf,
            kind=kind,
            status=status,
            source_logical_id=source_logical_id,
            target_logical_id=target_logical_id,
            evidence_ids=sorted_evidence,
            source_reference=source_reference,
            safe_metadata=safe_meta,
            record_digest=digest,
        )

    def semantic_payload(self) -> dict[str, Any]:
        """Cover allowlisted semantic payload fields and scope semantic identity."""
        return {
            "c1_version": self.c1_version,
            "scope_identity": self.scope.semantic_identity(),
            "document_kind": self.document_kind.value,
            "canonical_reference": self.canonical_reference,
            "knowledge_key": self.knowledge_key,
            "title": self.title,
            "text_fields": dict(sorted(self.text_fields.items())),
            "kind": self.kind,
            "status": self.status,
            "source_logical_id": self.source_logical_id,
            "target_logical_id": self.target_logical_id,
            "evidence_ids": list(self.evidence_ids),
            "source_reference": (
                self.source_reference.model_dump(mode="json")
                if self.source_reference
                else None
            ),
            "safe_metadata": dict(sorted(self.safe_metadata.items())),
        }

    def compute_semantic_digest(self) -> str:
        """Compute the record's SHA-256 semantic digest."""
        encoded = canonical_json(self.semantic_payload()).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_stored_envelope(
        self,
        *,
        generation_id: UUID,
        index_uuid: str,
    ) -> dict[str, Any]:
        """Generate the exact Elasticsearch _source document envelope."""
        storage_k = compute_storage_key(
            c1_version=self.c1_version,
            knowledge_key=self.knowledge_key,
            generation_id=generation_id,
        )
        env = {
            "c1_version": self.c1_version,
            "project_id": str(self.scope.project_id).lower(),
            "architecture_version_id": str(self.scope.architecture_version_id).lower(),
            "repository_id": str(self.scope.repository_id).lower(),
            "snapshot_id": str(self.scope.snapshot_id).lower(),
            "analysis_id": str(self.scope.analysis_id).lower(),
            "generation_id": str(generation_id).lower(),
            "index_uuid": index_uuid,
            "document_kind": self.document_kind.value,
            "canonical_reference": self.canonical_reference,
            "knowledge_key": self.knowledge_key,
            "storage_key": storage_k,
            "title": self.title,
            "text_fields": dict(sorted(self.text_fields.items())),
            "kind": self.kind,
            "status": self.status,
            "source_logical_id": self.source_logical_id,
            "target_logical_id": self.target_logical_id,
            "evidence_ids": list(self.evidence_ids),
            "source_reference": (
                self.source_reference.model_dump(mode="json")
                if self.source_reference
                else None
            ),
            "safe_metadata": dict(sorted(self.safe_metadata.items())),
            "record_semantic_digest": self.record_digest,
        }
        return env


def compute_projection_digest(
    *,
    c1_version: str,
    scope: VersionScope,
    source_content_digest: str,
    records: tuple[KnowledgeRecord, ...],
    counts: KnowledgeCounts,
) -> str:
    """Compute deterministic SHA-256 projection digest over canonical records."""
    sorted_records = sorted(
        records, key=lambda r: (r.document_kind.value, r.knowledge_key)
    )
    payload = {
        "c1_version": c1_version,
        "scope_identity": scope.semantic_identity(),
        "source_content_digest": source_content_digest,
        "counts": counts.model_dump(mode="json"),
        "record_digests": [[r.knowledge_key, r.record_digest] for r in sorted_records],
    }
    encoded = canonical_json(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class KnowledgeProjection(BaseModel):
    """Immutable collection of all projected records for an Architecture Version."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    c1_version: Literal["1.0.0"] = C1_CONTRACT_VERSION
    scope: VersionScope
    records: tuple[KnowledgeRecord, ...]
    counts: KnowledgeCounts
    projection_digest: Digest
    source_content_digest: Digest
    omitted_metadata_counts: dict[str, int] = Field(default_factory=dict)

    @field_validator("records", mode="after")
    @classmethod
    def _sort_records(
        cls, v: tuple[KnowledgeRecord, ...]
    ) -> tuple[KnowledgeRecord, ...]:
        return tuple(sorted(v, key=lambda r: (r.document_kind.value, r.knowledge_key)))

    @model_validator(mode="after")
    def _validate_projection_digest(self) -> Self:
        expected = compute_projection_digest(
            c1_version=self.c1_version,
            scope=self.scope,
            source_content_digest=self.source_content_digest,
            records=self.records,
            counts=self.counts,
        )
        if self.projection_digest != expected:
            raise KnowledgeModelError(
                f"projection_digest {self.projection_digest} does not match "
                f"computed {expected}"
            )
        return self


class SearchManifest(BaseModel):
    """Immutable primary artifact descriptor durably binding index & verification."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    c1_version: Literal["1.0.0"] = C1_CONTRACT_VERSION
    scope: VersionScope
    profile: ProducerProfile
    input_fingerprint: Digest
    candidate_id: UUID
    generation_id: UUID
    artifact_id: UUID
    index_name: str
    index_uuid: str
    settings_hash: Digest
    mapping_hash: Digest
    counts: KnowledgeCounts
    key_set_digest: Digest
    payload_digest: Digest
    projection_digest: Digest
    verifier_version: str
    seal_protocol_version: str
    sealed_at: AwareDatetime | None = None

    def to_canonical_bytes(self) -> bytes:
        """Return canonical UTF-8 bytes of this manifest."""
        data = self.model_dump(mode="json")
        return canonical_json(data).encode("utf-8")

    def content_digest(self) -> str:
        """Compute the SHA-256 digest of the canonical manifest bytes."""
        return hashlib.sha256(self.to_canonical_bytes()).hexdigest()

    def size_bytes(self) -> int:
        """Return length in bytes of the canonical manifest representation."""
        return len(self.to_canonical_bytes())


class SearchVerificationResult(BaseModel):
    """Independent verification receipt validating candidate before publication."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    c1_version: Literal["1.0.0"] = C1_CONTRACT_VERSION
    scope: VersionScope
    attempt_id: UUID
    candidate_id: UUID
    generation_id: UUID
    profile: ProducerProfile
    index_uuid: str
    expected_counts: KnowledgeCounts
    actual_counts: KnowledgeCounts
    expected_key_set_digest: Digest
    actual_key_set_digest: Digest
    expected_payload_digest: Digest
    actual_payload_digest: Digest
    mapping_version: str
    verifier_version: str
    seal_version: str
    verified: bool
    failure_code: str | None = None
    failure_reason: str | None = None


__all__ = [
    "C1_CONTRACT_VERSION",
    "SUMMARY_CANONICAL_REFERENCE",
    "KnowledgeCounts",
    "KnowledgeDocumentKind",
    "KnowledgeModelError",
    "KnowledgeProjection",
    "KnowledgeRecord",
    "SearchManifest",
    "SearchVerificationResult",
    "SourceReferenceDescriptor",
    "canonical_json",
    "compute_knowledge_key",
    "compute_projection_digest",
    "compute_storage_key",
]
