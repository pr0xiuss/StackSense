"""Immutable Architecture Model v1 foundation records and canonical identities."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum, StrEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID

from backend.platform.analysis.domain.constants import ARCHITECTURE_SCHEMA_VERSION


class ArchitectureModelError(ValueError):
    """Raised when an Architecture Model foundation invariant is violated."""


class ArchitectureIdentityCollisionError(ArchitectureModelError):
    """Raised when distinct semantic identities cannot be safely disambiguated."""


class ArchitectureValidationError(ArchitectureModelError):
    """Raised when a candidate Architecture Model violates the v1 contract."""


class ArchitectureCapacityError(ArchitectureValidationError):
    """Raised when an Architecture Model exceeds an approved resource limit."""

    code = "architecture_capacity_exceeded"

    def __init__(self, *, dimension: str, actual: int, limit: int) -> None:
        self.dimension = dimension
        self.actual = actual
        self.limit = limit
        display_dimension = dimension.replace("_", " ")
        super().__init__(
            "architecture capacity exceeded: "
            f"{display_dimension}={actual}, limit={limit}"
        )

    @property
    def diagnostic_details(self) -> dict[str, int | str]:
        """Return safe deterministic metadata for the shared diagnostic contract."""
        return {
            "dimension": self.dimension,
            "actual": self.actual,
            "limit": self.limit,
        }


class ArchitectureEntityKind(StrEnum):
    APPLICATION = "application"
    FRONTEND_APPLICATION = "frontend_application"
    SERVICE = "service"
    MODULE = "module"
    COMPONENT = "component"
    CONTROLLER = "controller"
    ENDPOINT = "endpoint"
    WORKER = "worker"
    DATA_REPOSITORY = "data_repository"
    DATABASE = "database"
    MESSAGE_BROKER = "message_broker"
    QUEUE = "queue"
    TOPIC = "topic"
    EXTERNAL_SERVICE = "external_service"
    EXTERNAL_API = "external_api"
    LIBRARY = "library"
    CONFIGURATION_COMPONENT = "configuration_component"
    UNKNOWN = "unknown"


class ArchitectureRelationshipKind(StrEnum):
    CONTAINS = "contains"
    DEPENDS_ON = "depends_on"
    IMPORTS = "imports"
    CALLS = "calls"
    EXPOSES = "exposes"
    CONSUMES = "consumes"
    PRODUCES = "produces"
    CONNECTS_TO = "connects_to"
    PERSISTS_TO = "persists_to"
    USES = "uses"
    EXTENDS = "extends"
    IMPLEMENTS = "implements"
    ROUTES_TO = "routes_to"


class ArchitectureFactStatus(StrEnum):
    CONFIRMED = "confirmed"
    SUPPORTED = "supported"
    INFERRED = "inferred"
    UNRESOLVED = "unresolved"
    CONFLICTING = "conflicting"


class ArchitectureEvidenceStrength(StrEnum):
    DIRECT_SOURCE = "direct_source"
    FRAMEWORK_STRUCTURAL = "framework_structural"
    CONFIGURATION = "configuration"
    DEPENDENCY = "dependency"
    DOCUMENTATION = "documentation"

    @property
    def rank(self) -> int:
        return {
            ArchitectureEvidenceStrength.DIRECT_SOURCE: 5,
            ArchitectureEvidenceStrength.FRAMEWORK_STRUCTURAL: 4,
            ArchitectureEvidenceStrength.CONFIGURATION: 3,
            ArchitectureEvidenceStrength.DEPENDENCY: 2,
            ArchitectureEvidenceStrength.DOCUMENTATION: 1,
        }[self]


class ArchitectureEvidencePolarity(StrEnum):
    SUPPORTING = "supporting"
    CONFLICTING = "conflicting"


class ArchitectureUnresolvedReason(StrEnum):
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    DYNAMIC = "dynamic"
    UNSUPPORTED = "unsupported"
    INCOMPLETE_INPUT = "incomplete_input"


_HOST_PATH_RE = re.compile(
    r"(?:^[A-Za-z]:[/\\])|(?:^/(?:home|Users|var|tmp|etc|root|usr|opt)/)"
    r"|(?:^\\\\)|(?:^//)"
)
_SENSITIVE_KEY_RE = re.compile(
    r"(?:password|passwd|secret|token|private_key|\bauth\b|auth_|api_key|credential|certificate_key)",
    re.I,
)
_UNRESERVED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"


def _normalize_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ArchitectureModelError(f"{field_name} must be a string")
    normalized = unicodedata.normalize("NFC", value)
    try:
        normalized.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise ArchitectureModelError(f"{field_name} is not valid Unicode") from exc
    if not normalized:
        raise ArchitectureModelError(f"{field_name} must not be empty")
    if _HOST_PATH_RE.search(normalized):
        raise ArchitectureModelError(f"{field_name} contains a host absolute path")
    return normalized


def encode_identity_component(value: str, *, compound: bool = False) -> str:
    """Normalize to NFC/UTF-8 and percent-encode with uppercase hex bytes."""
    normalized = _normalize_text(value, field_name="identity component")
    safe = {ord(character) for character in _UNRESERVED}
    if compound:
        safe.remove(ord("~"))
    return "".join(
        chr(byte) if byte in safe else f"%{byte:02X}"
        for byte in normalized.encode("utf-8", "strict")
    )


def _normalize_path(value: str) -> str:
    raw = _normalize_text(value, field_name="path").replace("\\", "/")
    if raw.startswith("/"):
        raise ArchitectureModelError("path must be repository-relative")
    parts: list[str] = []
    for part in raw.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise ArchitectureModelError("path must not contain '..'")
        parts.append(part)
    if not parts:
        raise ArchitectureModelError("path must not be empty after normalization")
    return "/".join(parts)


def normalize_route_path(value: str) -> str:
    """Normalize a static route without erasing a meaningful trailing slash."""
    route = _normalize_text(value, field_name="route path").replace("\\", "/")
    trailing = route.endswith("/") and route != "/"
    route = "/" + "/".join(part for part in route.split("/") if part)
    if trailing:
        route += "/"
    return route or "/"


def canonical_semantic_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        _json_value(value),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def semantic_signature(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_semantic_json(value).encode("utf-8")).hexdigest()


def build_entity_logical_id(
    *,
    project_id: UUID,
    repository_id: UUID,
    kind: ArchitectureEntityKind,
    namespace_parts: tuple[str, ...],
    anchor_parts: tuple[str, ...],
    disambiguator: str | None = None,
) -> str:
    if not namespace_parts or not anchor_parts:
        raise ArchitectureModelError("namespace and anchor components are required")
    namespace = "~".join(
        encode_identity_component(part, compound=True) for part in namespace_parts
    )
    anchor = "~".join(
        encode_identity_component(part, compound=True) for part in anchor_parts
    )
    logical_id = (
        f"architecture://project/{str(project_id).lower()}"
        f"/repository/{str(repository_id).lower()}"
        f"/{kind.value}/{namespace}/{anchor}"
    )
    if disambiguator is not None:
        logical_id += f"/disambiguator/{encode_identity_component(disambiguator)}"
    return logical_id


def build_relationship_logical_id(
    *,
    project_id: UUID,
    repository_id: UUID,
    kind: ArchitectureRelationshipKind,
    source_logical_id: str,
    target_logical_id: str | None,
    unresolved_descriptor: str | None = None,
) -> str:
    if (target_logical_id is None) == (unresolved_descriptor is None):
        raise ArchitectureModelError(
            "relationship requires exactly one target or unresolved descriptor"
        )
    target = target_logical_id or f"unresolved:{unresolved_descriptor}"
    signature = semantic_signature(
        {"kind": kind.value, "source": source_logical_id, "target": target}
    )
    return build_entity_logical_id(
        project_id=project_id,
        repository_id=repository_id,
        kind=ArchitectureEntityKind.UNKNOWN,
        namespace_parts=("relationship", kind.value),
        anchor_parts=(signature,),
    ).replace("/unknown/", "/relationship/", 1)


def build_evidence_logical_id(snapshot_id: UUID, source_evidence_key: str) -> str:
    return (
        f"evidence://snapshot/{str(snapshot_id).lower()}/"
        f"{encode_identity_component(source_evidence_key)}"
    )


def _freeze_metadata(data: Mapping[str, Any]) -> MappingProxyType[str, Any]:
    frozen: dict[str, Any] = {}
    for key, value in sorted(data.items()):
        if not isinstance(key, str) or _SENSITIVE_KEY_RE.search(key):
            raise ArchitectureModelError(f"unsafe metadata key: {key!r}")
        frozen[key] = _freeze_value(key, value)
    return MappingProxyType(frozen)


def _freeze_value(key: str, value: Any) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ArchitectureModelError(
                f"metadata {key!r} contains a non-finite number"
            )
        return value
    if isinstance(value, str):
        normalized = unicodedata.normalize("NFC", value)
        if _HOST_PATH_RE.search(normalized):
            raise ArchitectureModelError(f"metadata {key!r} contains a host path")
        return normalized
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_value(key, item) for item in value)
    if isinstance(value, Mapping):
        return _freeze_metadata(value)
    raise ArchitectureModelError(f"unsupported metadata value for {key!r}")


@dataclass(frozen=True)
class ArchitectureEvidence:
    logical_id: str
    source_evidence_key: str
    source_record_type: str
    path: str
    artifact_id: UUID | None = None
    source_fact_key: str | None = None
    source_range: Mapping[str, int] | None = None
    producer_id: str | None = None
    producer_version: str | None = None
    strength: ArchitectureEvidenceStrength = ArchitectureEvidenceStrength.DIRECT_SOURCE
    polarity: ArchitectureEvidencePolarity = ArchitectureEvidencePolarity.SUPPORTING
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("logical_id", "source_evidence_key", "source_record_type"):
            _normalize_text(getattr(self, name), field_name=name)
        if not isinstance(self.strength, ArchitectureEvidenceStrength):
            raise ArchitectureModelError("invalid architecture evidence strength")
        if not isinstance(self.polarity, ArchitectureEvidencePolarity):
            raise ArchitectureModelError("invalid architecture evidence polarity")
        object.__setattr__(self, "path", _normalize_path(self.path))
        if self.source_range is not None:
            object.__setattr__(
                self, "source_range", _freeze_metadata(self.source_range)
            )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class ArchitectureEntity:
    logical_id: str
    semantic_signature: str
    kind: ArchitectureEntityKind
    name: str
    namespace: tuple[str, ...]
    status: ArchitectureFactStatus
    evidence_ids: tuple[str, ...]
    source_ir_keys: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _normalize_text(self.logical_id, field_name="logical_id")
        _normalize_text(self.name, field_name="name")
        if len(self.semantic_signature) != 64:
            raise ArchitectureModelError("semantic signature must be SHA-256 hex")
        object.__setattr__(self, "namespace", tuple(self.namespace))
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))
        object.__setattr__(
            self, "source_ir_keys", tuple(sorted(set(self.source_ir_keys)))
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class ArchitectureRelationship:
    logical_id: str
    kind: ArchitectureRelationshipKind
    source_logical_id: str
    target_logical_id: str
    status: ArchitectureFactStatus
    evidence_ids: tuple[str, ...]
    source_ir_keys: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("logical_id", "source_logical_id", "target_logical_id"):
            _normalize_text(getattr(self, name), field_name=name)
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))
        object.__setattr__(
            self, "source_ir_keys", tuple(sorted(set(self.source_ir_keys)))
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class ArchitectureUnresolvedRelationship:
    logical_id: str
    kind: ArchitectureRelationshipKind
    source_logical_id: str
    target_descriptor: str
    reason: ArchitectureUnresolvedReason
    status: ArchitectureFactStatus
    evidence_ids: tuple[str, ...]
    source_ir_keys: tuple[str, ...]
    candidate_references: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "logical_id",
            "source_logical_id",
            "target_descriptor",
        ):
            _normalize_text(getattr(self, name), field_name=name)
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))
        object.__setattr__(
            self, "source_ir_keys", tuple(sorted(set(self.source_ir_keys)))
        )
        object.__setattr__(
            self,
            "candidate_references",
            tuple(sorted(set(self.candidate_references))),
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class ArchitectureConflict:
    logical_id: str
    conflict_type: str
    subject_key: str
    evidence_ids: tuple[str, ...]
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("logical_id", "conflict_type", "subject_key"):
            _normalize_text(getattr(self, name), field_name=name)
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))
        object.__setattr__(self, "details", _freeze_metadata(self.details))


@dataclass(frozen=True)
class ArchitectureCompleteness:
    total_inventory_artifacts: int
    analyzed_artifacts: int
    failed_artifacts: int
    total_syntax_documents: int
    total_syntax_facts: int
    source_entities: int
    source_relationships: int
    source_unresolved_references: int
    source_conflicts: int
    architecture_entities: int
    architecture_relationships: int
    architecture_unresolved_relationships: int
    architecture_conflicts: int
    is_partial: bool

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if item.name != "is_partial" and (not isinstance(value, int) or value < 0):
                raise ArchitectureModelError(
                    f"completeness {item.name} must be a non-negative integer"
                )


@dataclass(frozen=True)
class ArchitectureIdentityConflict:
    logical_id: str
    semantic_signatures: tuple[str, ...]
    source_ir_keys: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    reason: str = "post_canonicalization_collision"

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "semantic_signatures", tuple(sorted(set(self.semantic_signatures)))
        )
        object.__setattr__(
            self, "source_ir_keys", tuple(sorted(set(self.source_ir_keys)))
        )
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))


@dataclass(frozen=True)
class ResolvedArchitectureInput:
    analysis_id: UUID
    project_id: UUID
    repository_id: UUID
    snapshot_id: UUID
    configuration_fingerprint: str
    analyzer_version: str
    ir_schema_version: str
    architecture_schema_version: str
    entities: tuple[ArchitectureEntity, ...]
    evidence: tuple[ArchitectureEvidence, ...]
    conflicts: tuple[ArchitectureIdentityConflict, ...] = ()
    source_diagnostic_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.architecture_schema_version != ARCHITECTURE_SCHEMA_VERSION:
            raise ArchitectureModelError("unsupported architecture schema version")
        object.__setattr__(
            self, "entities", tuple(sorted(self.entities, key=lambda x: x.logical_id))
        )
        object.__setattr__(
            self, "evidence", tuple(sorted(self.evidence, key=lambda x: x.logical_id))
        )
        object.__setattr__(
            self, "conflicts", tuple(sorted(self.conflicts, key=lambda x: x.logical_id))
        )
        object.__setattr__(
            self,
            "source_diagnostic_ids",
            tuple(sorted(set(self.source_diagnostic_ids))),
        )
        ids = [entity.logical_id for entity in self.entities]
        if len(ids) != len(set(ids)):
            raise ArchitectureIdentityCollisionError(
                "resolved entity IDs are not unique"
            )

    def to_dict(self) -> dict[str, Any]:
        return _json_value(self)  # type: ignore[no-any-return]

    def to_canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )


@dataclass(frozen=True)
class ArchitectureDocument:
    architecture_version_id: UUID
    analysis_id: UUID
    project_id: UUID
    repository_id: UUID
    snapshot_id: UUID
    configuration_fingerprint: str
    analyzer_version: str
    ir_schema_version: str
    architecture_schema_version: str
    entities: tuple[ArchitectureEntity, ...]
    relationships: tuple[ArchitectureRelationship, ...]
    evidence: tuple[ArchitectureEvidence, ...]
    unresolved_relationships: tuple[ArchitectureUnresolvedRelationship, ...]
    conflicts: tuple[ArchitectureConflict, ...]
    completeness: ArchitectureCompleteness
    source_diagnostic_ids: tuple[str, ...] = ()
    content_digest: str = ""

    def __post_init__(self) -> None:
        if self.architecture_schema_version != ARCHITECTURE_SCHEMA_VERSION:
            raise ArchitectureModelError("unsupported architecture schema version")
        if not self.configuration_fingerprint:
            raise ArchitectureModelError("configuration fingerprint must not be empty")
        object.__setattr__(
            self,
            "entities",
            tuple(sorted(self.entities, key=lambda item: item.logical_id)),
        )
        object.__setattr__(
            self,
            "relationships",
            tuple(sorted(self.relationships, key=lambda item: item.logical_id)),
        )
        object.__setattr__(
            self,
            "evidence",
            tuple(sorted(self.evidence, key=lambda item: item.logical_id)),
        )
        object.__setattr__(
            self,
            "unresolved_relationships",
            tuple(
                sorted(
                    self.unresolved_relationships,
                    key=lambda item: item.logical_id,
                )
            ),
        )
        object.__setattr__(
            self,
            "conflicts",
            tuple(sorted(self.conflicts, key=lambda item: item.logical_id)),
        )
        object.__setattr__(
            self,
            "source_diagnostic_ids",
            tuple(sorted(set(self.source_diagnostic_ids))),
        )
        semantic_json = json.dumps(
            _json_value(self.semantic_payload()),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        expected_digest = hashlib.sha256(semantic_json.encode("utf-8")).hexdigest()
        if self.content_digest and self.content_digest != expected_digest:
            raise ArchitectureModelError("architecture content digest mismatch")
        object.__setattr__(self, "content_digest", expected_digest)
        object.__setattr__(self, "_semantic_content_digest", expected_digest)
        added_pairs = (
            f'"architecture_version_id":{json.dumps(str(self.architecture_version_id))}',
            f'"content_digest":{json.dumps(expected_digest)}',
        )
        object.__setattr__(
            self,
            "_canonical_payload_size",
            len(semantic_json.encode("utf-8"))
            + sum(len(pair.encode("utf-8")) for pair in added_pairs)
            + len(added_pairs),
        )

    def semantic_payload(self) -> dict[str, Any]:
        """Return canonical content, excluding persistence identity and digest."""
        return {
            "analysis_id": self.analysis_id,
            "project_id": self.project_id,
            "repository_id": self.repository_id,
            "snapshot_id": self.snapshot_id,
            "configuration_fingerprint": self.configuration_fingerprint,
            "analyzer_version": self.analyzer_version,
            "ir_schema_version": self.ir_schema_version,
            "architecture_schema_version": self.architecture_schema_version,
            "entities": self.entities,
            "relationships": self.relationships,
            "evidence": self.evidence,
            "unresolved_relationships": self.unresolved_relationships,
            "conflicts": self.conflicts,
            "completeness": self.completeness,
            "source_diagnostic_ids": self.source_diagnostic_ids,
        }

    def calculate_content_digest(self) -> str:
        cached = getattr(self, "_semantic_content_digest", None)
        if isinstance(cached, str):
            return cached
        return hashlib.sha256(
            json.dumps(
                _json_value(self.semantic_payload()),
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    @property
    def canonical_payload_size(self) -> int:
        """Exact canonical UTF-8 payload size calculated during construction."""
        return self._canonical_payload_size  # type: ignore[attr-defined,no-any-return]

    def to_dict(self) -> dict[str, Any]:
        return _json_value(self)  # type: ignore[no-any-return]

    def to_canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )


@dataclass(frozen=True)
class ValidatedArchitectureModel:
    """Marker returned only after complete deterministic model validation."""

    document: ArchitectureDocument


def _json_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): _json_value(v) for k, v in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _json_value(getattr(value, item.name)) for item in fields(value)
        }
    return value


__all__ = [
    "ARCHITECTURE_SCHEMA_VERSION",
    "ArchitectureCapacityError",
    "ArchitectureCompleteness",
    "ArchitectureConflict",
    "ArchitectureDocument",
    "ArchitectureEntity",
    "ArchitectureEntityKind",
    "ArchitectureEvidence",
    "ArchitectureEvidencePolarity",
    "ArchitectureEvidenceStrength",
    "ArchitectureFactStatus",
    "ArchitectureIdentityCollisionError",
    "ArchitectureIdentityConflict",
    "ArchitectureModelError",
    "ArchitectureRelationship",
    "ArchitectureRelationshipKind",
    "ArchitectureUnresolvedReason",
    "ArchitectureUnresolvedRelationship",
    "ArchitectureValidationError",
    "ResolvedArchitectureInput",
    "ValidatedArchitectureModel",
    "build_entity_logical_id",
    "build_evidence_logical_id",
    "build_relationship_logical_id",
    "canonical_semantic_json",
    "encode_identity_component",
    "normalize_route_path",
    "semantic_signature",
]
