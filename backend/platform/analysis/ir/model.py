"""Canonical F3 Intermediate Representation (IR) models, enums, keys, and serialization.

Governed by master.txt Section 11 and PROJECT_CONTEXT.md Phase 3 Module 3.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum, StrEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID

from backend.platform.analysis.domain.constants import (
    ANALYZER_VERSION as ANALYZER_VERSION,
)
from backend.platform.analysis.domain.constants import (
    IR_SCHEMA_VERSION as IR_SCHEMA_VERSION,
)
from backend.platform.analysis.syntax.model import SourceRange


class IRValidationError(ValueError):
    """Raised when an IR document or record violates structural or schema invariants."""


class IRCapacityLimitError(IRValidationError):
    """Raised when an IR document exceeds numeric capacity limits."""


class IRConstructionError(RuntimeError):
    """Raised when IR construction cannot proceed due to contract or input failure."""


# --- Vocabulary Enums (master.txt Section 11 & PROJECT_CONTEXT.md §4.5.2) ---


class IREntityKind(StrEnum):
    """Supported entity categories in the Intermediate Representation."""

    REPOSITORY = "repository"
    SNAPSHOT = "snapshot"
    ARTIFACT = "artifact"
    APPLICATION = "application"
    MODULE = "module"
    SYMBOL = "symbol"
    COMPONENT = "component"
    ENDPOINT = "endpoint"
    EXTERNAL_SYSTEM = "external_system"
    DATABASE = "database"
    MESSAGE_INFRASTRUCTURE = "message_infrastructure"
    CONFIGURATION = "configuration"


class IRRelationshipKind(StrEnum):
    """Supported relationship kinds between IR entities."""

    CONTAINS = "contains"
    DECLARES = "declares"
    IMPORTS = "imports"
    EXPORTS = "exports"
    STATIC_CALL_REFERENCE = "static_call_reference"
    INHERITS = "inherits"
    COMPOSES = "composes"
    DECLARES_ROUTE = "declares_route"
    USES_FRAMEWORK = "uses_framework"
    DECLARES_DEPENDENCY = "declares_dependency"
    SOURCE_REFERENCES_DEPENDENCY = "source_references_dependency"


class IRFactStatus(StrEnum):
    """Static-analysis fact status per master.txt Section 11 and context §4.5.3."""

    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    UNRESOLVED = "unresolved"
    CONFLICTING = "conflicting"


class IREvidenceStrength(StrEnum):
    """Named ordered evidence strengths (strongest to weakest)."""

    DIRECT_SOURCE = "direct_source"
    FRAMEWORK_STRUCTURAL = "framework_structural"
    CONFIGURATION = "configuration"
    DEPENDENCY = "dependency"
    DOCUMENTATION = "documentation"

    def is_stronger(self, other: IREvidenceStrength) -> bool:
        """Return True if this strength is strictly stronger than other."""
        return _STRENGTH_RANKS[self] > _STRENGTH_RANKS[other]


_STRENGTH_RANKS: dict[IREvidenceStrength, int] = {
    IREvidenceStrength.DIRECT_SOURCE: 5,
    IREvidenceStrength.FRAMEWORK_STRUCTURAL: 4,
    IREvidenceStrength.CONFIGURATION: 3,
    IREvidenceStrength.DEPENDENCY: 2,
    IREvidenceStrength.DOCUMENTATION: 1,
}


def is_stronger(a: IREvidenceStrength, b: IREvidenceStrength) -> bool:
    """Return True if evidence strength a is strictly stronger than b."""
    return _STRENGTH_RANKS[a] > _STRENGTH_RANKS[b]


class IRUnresolvedReason(StrEnum):
    """Reason why an IR reference could not be resolved in the document scope."""

    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    DYNAMIC = "dynamic"
    UNSUPPORTED = "unsupported"
    INCOMPLETE_INPUT = "incomplete_input"


# --- Metadata Safety and Immutability Validation ---

_UNSAFE_HOST_PATH_RE = re.compile(
    r"(?:^[a-zA-Z]:[/\\])"
    r"|(?:^/(?:home|Users|var|tmp|etc|usr|opt|root|bin|sbin|dev|proc|sys)/)"
    r"|(?:^\\\\(?:\?\\|[^\\]+\\[^\\]+))"
    r"|(?:^//(?:\?//|[^/]+/[^/]+))",
    re.IGNORECASE,
)

_SENSITIVE_KEY_RE = re.compile(
    r"(?:password|passwd|secret|token|private_key|\bauth\b|auth_|api_key|credential|certificate_key)",
    re.IGNORECASE,
)


def validate_safe_string(name: str, value: str | None) -> str | None:
    """Validate that an individual string field contains no prohibited host paths."""
    if value is None:
        return None
    if _UNSAFE_HOST_PATH_RE.search(value):
        msg = f"Field {name!r} contains prohibited host absolute path: {value!r}"
        raise IRValidationError(msg)
    return value


def _validate_safe_metadata_value(key: str, value: Any) -> Any:
    """Recursively validate metadata value against safety and host leakage policies."""
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        if _UNSAFE_HOST_PATH_RE.search(value):
            msg = (
                f"Metadata contains prohibited host absolute path: "
                f"key={key!r}, value={value!r}"
            )
            raise IRValidationError(msg)
        return value
    if isinstance(value, (list, tuple)):
        return tuple(_validate_safe_metadata_value(key, item) for item in value)
    if isinstance(value, Mapping):
        return _freeze_metadata(value)
    raise IRValidationError(
        f"Unsupported metadata type for key={key!r}: {type(value).__name__}"
    )


def _freeze_metadata(data: Mapping[str, Any]) -> MappingProxyType[str, Any]:
    """Validate metadata mapping keys and recursively freeze into MappingProxyType."""
    frozen: dict[str, Any] = {}
    for k, v in sorted(data.items()):
        if not isinstance(k, str):
            raise IRValidationError(
                f"Metadata key must be a string, got {type(k).__name__}"
            )
        if _SENSITIVE_KEY_RE.search(k):
            raise IRValidationError(
                f"Metadata key contains prohibited sensitive term: {k!r}"
            )
        frozen[k] = _validate_safe_metadata_value(k, v)
    return MappingProxyType(frozen)


# --- Deterministic Snapshot-Scoped Key Builders ---


def build_entity_key(kind: IREntityKind, *parts: str) -> str:
    """Build a deterministic snapshot-scoped entity key."""
    norm_parts = [p.replace("\\", "/").strip("/").replace(" ", "_") for p in parts if p]
    if not norm_parts:
        msg = (
            f"Cannot build entity key for {kind.value} without path or "
            "identifier parts."
        )
        raise IRValidationError(msg)
    return f"{kind.value}::{'::'.join(norm_parts)}"


def build_relationship_key(
    kind: IRRelationshipKind,
    source_key: str,
    target_key: str | None,
    disambiguator: str = "",
) -> str:
    """Build a deterministic snapshot-scoped relationship key."""
    if disambiguator:
        norm_disc = disambiguator.replace("\\", "/").strip("/").replace(" ", "_")
    else:
        norm_disc = "none"
    return f"rel::{kind.value}::{source_key}::{target_key or 'unresolved'}::{norm_disc}"


def build_evidence_key(
    source_record_type: str,
    path: str,
    fact_key: str | None = None,
    disambiguator: str = "",
) -> str:
    """Build a deterministic evidence key."""
    norm_path = path.replace("\\", "/").strip("/").replace(" ", "_") or "root"
    norm_fk = fact_key.replace(" ", "_") if fact_key else "none"
    norm_disc = disambiguator.replace(" ", "_") if disambiguator else "none"
    return f"ev::{norm_path}::{source_record_type}::{norm_fk}::{norm_disc}"


def build_unresolved_key(
    source_key: str,
    relationship_kind: IRRelationshipKind,
    target_name: str,
    disambiguator: str = "",
) -> str:
    """Build a deterministic unresolved reference key."""
    norm_target = target_name.replace(" ", "_").strip()
    norm_disc = disambiguator.replace(" ", "_") if disambiguator else "none"
    return f"unres::{source_key}::{relationship_kind.value}::{norm_target}::{norm_disc}"


def build_conflict_key(
    conflict_type: str,
    subject_key: str,
    disambiguator: str = "",
) -> str:
    """Build a deterministic conflict key."""
    norm_type = conflict_type.replace(" ", "_").strip()
    norm_disc = disambiguator.replace(" ", "_") if disambiguator else "none"
    return f"conflict::{norm_type}::{subject_key}::{norm_disc}"


# --- Canonical Records ---


@dataclass(frozen=True)
class IREntity:
    """Normalized, non-authoritative candidate entity discovered during analysis."""

    ir_key: str
    kind: IREntityKind
    name: str
    qualified_name: str | None = None
    artifact_id: UUID | None = None
    module_key: str | None = None
    container_key: str | None = None
    language: str | None = None
    framework: str | None = None
    status: IRFactStatus = IRFactStatus.CONFIRMED
    evidence_keys: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.ir_key:
            raise IRValidationError("Entity ir_key must not be empty.")
        if not self.name:
            raise IRValidationError("Entity name must not be empty.")
        validate_safe_string("name", self.name)
        validate_safe_string("qualified_name", self.qualified_name)
        if not isinstance(self.kind, IREntityKind):
            raise IRValidationError(f"Invalid entity kind: {self.kind}")
        if not isinstance(self.status, IRFactStatus):
            raise IRValidationError(f"Invalid fact status: {self.status}")
        object.__setattr__(
            self, "evidence_keys", tuple(sorted(set(self.evidence_keys)))
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class IRRelationship:
    """Normalized relationship candidate between entities or toward unresolved ref."""

    ir_key: str
    kind: IRRelationshipKind
    source_key: str
    target_key: str | None = None
    unresolved_reference_key: str | None = None
    status: IRFactStatus = IRFactStatus.CONFIRMED
    evidence_keys: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.ir_key:
            raise IRValidationError("Relationship ir_key must not be empty.")
        if not self.source_key:
            raise IRValidationError("Relationship source_key must not be empty.")
        if (
            self.target_key is None
            and self.unresolved_reference_key is None
            and self.kind
            not in (
                IRRelationshipKind.DECLARES_DEPENDENCY,
                IRRelationshipKind.USES_FRAMEWORK,
            )
        ):
            raise IRValidationError(
                "Relationship must have either target_key or unresolved_reference_key."
            )
        validate_safe_string("source_key", self.source_key)
        validate_safe_string("target_key", self.target_key)
        if not isinstance(self.kind, IRRelationshipKind):
            raise IRValidationError(f"Invalid relationship kind: {self.kind}")
        if not isinstance(self.status, IRFactStatus):
            raise IRValidationError(f"Invalid fact status: {self.status}")
        object.__setattr__(
            self, "evidence_keys", tuple(sorted(set(self.evidence_keys)))
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class IREvidence:
    """Immutable evidence signal supporting or conflicting with an IR fact."""

    evidence_key: str
    artifact_id: UUID | None
    path: str
    source_record_type: str
    source_fact_key: str | None = None
    source_range: SourceRange | None = None
    parser_adapter_id: str | None = None
    parser_adapter_version: str | None = None
    grammar_abi_version: int | None = None
    framework_name: str | None = None
    supporting_fact_keys: tuple[str, ...] = ()
    upstream_analyzer_version: str = ""
    m3_transformation_version: str = ANALYZER_VERSION
    strength: IREvidenceStrength = IREvidenceStrength.DIRECT_SOURCE
    polarity: str = "supporting"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.evidence_key:
            raise IRValidationError("Evidence evidence_key must not be empty.")
        if not self.source_record_type:
            raise IRValidationError("Evidence source_record_type must not be empty.")
        if not isinstance(self.strength, IREvidenceStrength):
            raise IRValidationError(f"Invalid evidence strength: {self.strength}")
        validate_safe_string("path", self.path)
        norm_path = self.path.replace("\\", "/").strip("/")
        validate_safe_string("path", norm_path)
        object.__setattr__(self, "path", norm_path)
        object.__setattr__(
            self, "supporting_fact_keys", tuple(sorted(self.supporting_fact_keys))
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class IRUnresolvedReference:
    """Structured record of an unresolvable reference (cross-file or dynamic)."""

    unresolved_key: str
    source_key: str
    relationship_kind: IRRelationshipKind
    target_name: str
    reason: IRUnresolvedReason
    candidate_references: tuple[str, ...] = ()
    evidence_keys: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.unresolved_key:
            raise IRValidationError(
                "Unresolved reference unresolved_key must not be empty."
            )
        if not self.source_key:
            raise IRValidationError(
                "Unresolved reference source_key must not be empty."
            )
        if not isinstance(self.relationship_kind, IRRelationshipKind):
            raise IRValidationError(
                f"Invalid relationship kind: {self.relationship_kind}"
            )
        if not isinstance(self.reason, IRUnresolvedReason):
            raise IRValidationError(f"Invalid unresolved reason: {self.reason}")
        validate_safe_string("target_name", self.target_name)
        validate_safe_string("source_key", self.source_key)
        for cand in self.candidate_references:
            validate_safe_string("candidate_reference", cand)
        object.__setattr__(
            self, "candidate_references", tuple(sorted(self.candidate_references))
        )
        object.__setattr__(
            self, "evidence_keys", tuple(sorted(set(self.evidence_keys)))
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class IRConflict:
    """Record of contradictory evidence that cannot be deterministically resolved."""

    conflict_key: str
    conflict_type: str
    subject_key: str
    competing_evidence_keys: tuple[str, ...]
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.conflict_key:
            raise IRValidationError("Conflict conflict_key must not be empty.")
        if not self.conflict_type:
            raise IRValidationError("Conflict conflict_type must not be empty.")
        if not self.subject_key:
            raise IRValidationError("Conflict subject_key must not be empty.")
        object.__setattr__(
            self,
            "competing_evidence_keys",
            tuple(sorted(set(self.competing_evidence_keys))),
        )
        object.__setattr__(self, "details", _freeze_metadata(self.details))


@dataclass(frozen=True)
class IRCompleteness:
    """Aggregate discovery counters and partial execution flag for the IR document."""

    total_inventory_artifacts: int = 0
    analyzed_artifacts: int = 0
    failed_artifacts: int = 0
    total_syntax_documents: int = 0
    total_syntax_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    total_unresolved_references: int = 0
    total_conflicts: int = 0
    is_partial: bool = False


def _serialize_json_value(val: Any) -> Any:
    """Serialize IR dataclass fields and types to canonical JSON-compatible objects."""
    if isinstance(val, UUID):
        return str(val)
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, (tuple, list)):
        return [_serialize_json_value(item) for item in val]
    if isinstance(val, Mapping):
        return {k: _serialize_json_value(v) for k, v in sorted(val.items())}
    if is_dataclass(val) and not isinstance(val, type):
        return {
            field.name: _serialize_json_value(getattr(val, field.name))
            for field in fields(val)
        }
    return val


@dataclass(frozen=True)
class IRDocument:
    """Canonical root F3 Intermediate Representation document produced by Module 3."""

    analysis_id: UUID
    project_id: UUID
    repository_id: UUID
    snapshot_id: UUID
    configuration_fingerprint: str
    entities: tuple[IREntity, ...]
    relationships: tuple[IRRelationship, ...]
    evidence: tuple[IREvidence, ...]
    unresolved_references: tuple[IRUnresolvedReference, ...]
    conflicts: tuple[IRConflict, ...]
    completeness: IRCompleteness
    ir_schema_version: str = IR_SCHEMA_VERSION
    f2_version: str = "1.0.0"
    analyzer_version: str = ANALYZER_VERSION
    diagnostic_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.ir_schema_version != IR_SCHEMA_VERSION:
            msg = (
                f"Unsupported IR schema version: {self.ir_schema_version!r} "
                f"(expected {IR_SCHEMA_VERSION!r})"
            )
            raise IRValidationError(msg)
        if self.f2_version != "1.0.0":
            msg = (
                f"Unsupported F2 input contract version: {self.f2_version!r} "
                f"(expected '1.0.0')"
            )
            raise IRValidationError(msg)

        # 1. Deterministic canonical sorting
        sorted_entities = tuple(
            sorted(self.entities, key=lambda e: (e.kind.value, e.ir_key))
        )
        if self.entities != sorted_entities:
            object.__setattr__(self, "entities", sorted_entities)

        sorted_relationships = tuple(
            sorted(
                self.relationships,
                key=lambda r: (
                    r.kind.value,
                    r.source_key,
                    r.target_key or "",
                    r.ir_key,
                ),
            )
        )
        if self.relationships != sorted_relationships:
            object.__setattr__(self, "relationships", sorted_relationships)

        sorted_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda ev: (ev.path, ev.source_record_type, ev.evidence_key),
            )
        )
        if self.evidence != sorted_evidence:
            object.__setattr__(self, "evidence", sorted_evidence)

        sorted_unresolved = tuple(
            sorted(
                self.unresolved_references,
                key=lambda u: (
                    u.source_key,
                    u.relationship_kind.value,
                    u.target_name,
                    u.unresolved_key,
                ),
            )
        )
        if self.unresolved_references != sorted_unresolved:
            object.__setattr__(self, "unresolved_references", sorted_unresolved)

        sorted_conflicts = tuple(
            sorted(
                self.conflicts,
                key=lambda c: (c.conflict_type, c.subject_key, c.conflict_key),
            )
        )
        if self.conflicts != sorted_conflicts:
            object.__setattr__(self, "conflicts", sorted_conflicts)

        sorted_diags = tuple(sorted(set(self.diagnostic_ids)))
        if self.diagnostic_ids != sorted_diags:
            object.__setattr__(self, "diagnostic_ids", sorted_diags)

        # 2. Key Uniqueness Verification
        entity_keys: set[str] = set()
        for e in self.entities:
            if e.ir_key in entity_keys:
                raise IRValidationError(f"Duplicate entity ir_key: {e.ir_key}")
            entity_keys.add(e.ir_key)

        rel_keys: set[str] = set()
        for r in self.relationships:
            if r.ir_key in rel_keys:
                raise IRValidationError(f"Duplicate relationship ir_key: {r.ir_key}")
            rel_keys.add(r.ir_key)

        ev_keys: set[str] = set()
        for ev in self.evidence:
            if ev.evidence_key in ev_keys:
                raise IRValidationError(f"Duplicate evidence_key: {ev.evidence_key}")
            ev_keys.add(ev.evidence_key)

        unres_keys: set[str] = set()
        for u in self.unresolved_references:
            if u.unresolved_key in unres_keys:
                raise IRValidationError(f"Duplicate unresolved_key: {u.unresolved_key}")
            unres_keys.add(u.unresolved_key)

        conf_keys: set[str] = set()
        for c in self.conflicts:
            if c.conflict_key in conf_keys:
                raise IRValidationError(f"Duplicate conflict_key: {c.conflict_key}")
            conf_keys.add(c.conflict_key)

        # 3. Referential Integrity Checks
        for r in self.relationships:
            if r.source_key not in entity_keys:
                msg = (
                    f"Relationship {r.ir_key} references unknown source_key: "
                    f"{r.source_key}"
                )
                raise IRValidationError(msg)
            if r.target_key is not None and r.target_key not in entity_keys:
                msg = (
                    f"Relationship {r.ir_key} references unknown target_key: "
                    f"{r.target_key}"
                )
                raise IRValidationError(msg)
            if (
                r.unresolved_reference_key is not None
                and r.unresolved_reference_key not in unres_keys
            ):
                msg = (
                    f"Relationship {r.ir_key} references unknown "
                    f"unresolved_reference_key: {r.unresolved_reference_key}"
                )
                raise IRValidationError(msg)
            for k in r.evidence_keys:
                if k not in ev_keys:
                    msg = (
                        f"Relationship {r.ir_key} references unknown evidence_key: {k}"
                    )
                    raise IRValidationError(msg)

        for e in self.entities:
            for k in e.evidence_keys:
                if k not in ev_keys:
                    msg = f"Entity {e.ir_key} references unknown evidence_key: {k}"
                    raise IRValidationError(msg)

        for u in self.unresolved_references:
            if u.source_key not in entity_keys:
                msg = (
                    f"Unresolved ref {u.unresolved_key} references unknown "
                    f"source_key: {u.source_key}"
                )
                raise IRValidationError(msg)
            for k in u.evidence_keys:
                if k not in ev_keys:
                    msg = (
                        f"Unresolved ref {u.unresolved_key} references unknown "
                        f"evidence_key: {k}"
                    )
                    raise IRValidationError(msg)

        for c in self.conflicts:
            for k in c.competing_evidence_keys:
                if k not in ev_keys:
                    msg = (
                        f"Conflict {c.conflict_key} references unknown "
                        f"evidence_key: {k}"
                    )
                    raise IRValidationError(msg)

    def to_dict(self) -> dict[str, Any]:
        """Convert IR document to a serializable dictionary with sorted keys."""
        return _serialize_json_value(self)  # type: ignore[no-any-return]

    def to_canonical_json(self) -> str:
        """Serialize IR document to canonical, deterministic UTF-8 JSON."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


__all__ = [
    "ANALYZER_VERSION",
    "IR_SCHEMA_VERSION",
    "IRCompleteness",
    "IRConflict",
    "IRConstructionError",
    "IRCapacityLimitError",
    "IRDocument",
    "IREntity",
    "IREntityKind",
    "IREvidence",
    "IREvidenceStrength",
    "IRFactStatus",
    "IRRelationship",
    "IRRelationshipKind",
    "IRUnresolvedReason",
    "IRUnresolvedReference",
    "IRValidationError",
    "build_conflict_key",
    "build_entity_key",
    "build_evidence_key",
    "build_relationship_key",
    "build_unresolved_key",
    "is_stronger",
    "validate_safe_string",
]
