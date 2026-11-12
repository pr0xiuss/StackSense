"""Deterministic P4-P1 projection mapping, immutable records, and canonical digests."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID

from backend.platform.analysis.architecture.model import (
    ArchitectureDocument,
    ArchitectureEntityKind,
    ArchitectureFactStatus,
    ArchitectureRelationshipKind,
)
from backend.platform.analysis.architecture.persistence import architecture_resource_id
from backend.platform.graph.model import (
    ProjectionCounts,
)

# Manifest private states
MANIFEST_STATE_BUILDING: Final = "BUILDING"
MANIFEST_STATE_READY: Final = "READY"

# Frozen P3 hard upper bounds
MAX_ENTITIES: Final = 25_000
MAX_RELATIONSHIPS: Final = 50_000
MAX_EVIDENCE: Final = 75_000
MAX_UNRESOLVED_RELATIONSHIPS: Final = 10_000
MAX_CONFLICTS: Final = 5_000
MAX_SERIALIZED_SOURCE_BYTES: Final = 128 * 1024 * 1024  # 128 MiB

# Candidate operational caps (measurement candidates)
MAX_META_KEY_BYTES: Final = 64
MAX_META_STRING_BYTES: Final = 2048
MAX_META_LIST_ITEMS: Final = 64
MAX_META_RECORD_BYTES: Final = 16384
MAX_PROJECTED_PROPERTIES_BYTES: Final = 1048576  # 1 MiB

# Metadata allowlist
METADATA_STRING_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "application_namespace",
        "runtime_role",
        "source_root",
        "framework",
        "architectural_role",
        "qualified_name",
        "method",
        "path",
        "handler",
        "mount_path",
        "declared_path",
        "database_engine",
        "external_kind",
        "unresolved_reason",
        "infrastructure_kind",
        "dependency_name",
        "identity_anchor",
        "promotion_rule_id",
    }
)

METADATA_BOOLEAN_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "manifest_declared",
        "source_referenced",
        "usage_evidence",
    }
)

METADATA_STRING_LIST_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "role_inference_signals",
        "transformation_rule_ids",
    }
)

ALL_ALLOWED_METADATA_FIELDS: Final[frozenset[str]] = (
    METADATA_STRING_FIELDS | METADATA_BOOLEAN_FIELDS | METADATA_STRING_LIST_FIELDS
)

HOST_PATH_SIGNATURES: Final[tuple[str, ...]] = (
    "/home/",
    "/Users/",
    "/var/",
    "/tmp/",
    "/etc/",
    "/root/",
    "/usr/",
    "/opt/",
    "/private/",
    "/proc/",
    "/sys/",
)

HOST_PATH_PREFIXES: Final[tuple[str, ...]] = (
    "home/",
    "Users/",
    "var/",
    "tmp/",
    "etc/",
    "root/",
    "usr/",
    "opt/",
    "private/",
    "proc/",
    "sys/",
)

HOST_PATH_EXACT: Final[frozenset[str]] = frozenset(
    {
        "/home",
        "/Users",
        "/var",
        "/tmp",
        "/etc",
        "/root",
        "/usr",
        "/opt",
        "/private",
        "/proc",
        "/sys",
    }
)

_WINDOWS_DRIVE_PATTERN: Final = re.compile(r"^[a-zA-Z]:")
_URI_SCHEME_PATTERN: Final = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


class ProjectionError(Exception):
    """Base exception for all projection mapping and execution errors."""

    def __init__(self, message: str, *, code: str = "graph_internal_error") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ProjectionContractError(ProjectionError):
    """Permanent error when projection contract or referential invariant is violated."""

    def __init__(
        self, message: str, *, code: str = "projection_contract_mismatch"
    ) -> None:
        super().__init__(message, code=code)


class ProjectionMetadataError(ProjectionError):
    """Raised when metadata violates the allowlist, caps, or field-semantic rules."""

    def __init__(
        self, message: str, *, code: str = "projection_metadata_invalid"
    ) -> None:
        super().__init__(message, code=code)


class ProjectionCapacityExceededError(ProjectionError):
    """Raised when input document or element counts exceed hard limits."""

    def __init__(
        self, message: str, *, code: str = "projection_capacity_exceeded"
    ) -> None:
        super().__init__(message, code=code)


class ProjectionSourceMismatchError(ProjectionError):
    """Raised when source counts, schema, or content digest mismatch."""

    def __init__(
        self, message: str, *, code: str = "projection_source_mismatch"
    ) -> None:
        super().__init__(message, code=code)


@dataclass(frozen=True, slots=True)
class ProjectedNodeRecord:
    """Immutable representation of one projected ArchitectureEntity node."""

    project_id: UUID
    architecture_version_id: UUID
    generation_id: UUID
    generation_key: str
    projection_key: str
    architecture_entity_id: UUID
    logical_id: str
    semantic_signature: str
    canonical_kind: str
    name: str
    namespace: tuple[str, ...]
    fact_status: str
    evidence_logical_ids: tuple[str, ...]
    properties: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProjectedRelationshipRecord:
    """Immutable representation of one projected ARCH_RELATIONSHIP edge."""

    project_id: UUID
    architecture_version_id: UUID
    generation_id: UUID
    generation_key: str
    projection_key: str
    architecture_relationship_id: UUID
    logical_id: str
    canonical_kind: str
    status: str
    source_logical_id: str
    target_logical_id: str
    source_projection_key: str
    target_projection_key: str
    evidence_logical_ids: tuple[str, ...]
    properties: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProjectionSummaryDigests:
    """Deterministic summary digests for non-projected items."""

    evidence_summary_digest: str
    unresolved_summary_digest: str
    conflict_summary_digest: str


@dataclass(frozen=True, slots=True)
class ProjectionPlan:
    """Complete, immutable projection plan ready for transactional Neo4j write."""

    project_id: UUID
    architecture_version_id: UUID
    generation_id: UUID
    generation_key: str
    expected_counts: ProjectionCounts
    nodes: tuple[ProjectedNodeRecord, ...]
    relationships: tuple[ProjectedRelationshipRecord, ...]
    key_set_digest: str
    endpoint_digest: str
    evidence_summary_digest: str
    unresolved_summary_digest: str
    conflict_summary_digest: str
    payload_digest: str
    source_content_digest: str = ""


def _check_no_nul(name: str, value: str) -> None:
    if "\0" in value:
        raise ProjectionContractError(
            f"NUL character is strictly forbidden in {name}",
            code="projection_contract_mismatch",
        )


def _check_no_control_chars(field_name: str, value: str) -> None:
    for char in value:
        code = ord(char)
        if (
            code < 32
            or (127 <= code <= 159)
            or unicodedata.category(char) in ("Cc", "Cs")
        ):
            raise ProjectionMetadataError(
                f"Control character forbidden in metadata field '{field_name}'",
                code="projection_metadata_invalid",
            )


def compute_generation_key(
    project_id: UUID | str,
    architecture_version_id: UUID | str,
    generation_id: UUID | str,
) -> str:
    """Generate unambiguous SHA-256 generation key for ProjectionManifest."""
    p_id = str(project_id).lower()
    a_id = str(architecture_version_id).lower()
    g_id = str(generation_id).lower()

    _check_no_nul("project_id", p_id)
    _check_no_nul("architecture_version_id", a_id)
    _check_no_nul("generation_id", g_id)

    payload = f"{p_id}\0{a_id}\0{g_id}".encode()
    return hashlib.sha256(payload).hexdigest().lower()


def compute_node_key(
    project_id: UUID | str,
    architecture_version_id: UUID | str,
    generation_id: UUID | str,
    entity_logical_id: str,
) -> str:
    """Generate unambiguous SHA-256 node key for ArchitectureEntity."""
    p_id = str(project_id).lower()
    a_id = str(architecture_version_id).lower()
    g_id = str(generation_id).lower()
    l_id = unicodedata.normalize("NFC", str(entity_logical_id))

    _check_no_nul("project_id", p_id)
    _check_no_nul("architecture_version_id", a_id)
    _check_no_nul("generation_id", g_id)
    _check_no_nul("entity_logical_id", l_id)

    payload = f"{p_id}\0{a_id}\0{g_id}\0{l_id}".encode()
    return hashlib.sha256(payload).hexdigest().lower()


def compute_edge_key(
    project_id: UUID | str,
    architecture_version_id: UUID | str,
    generation_id: UUID | str,
    relationship_logical_id: str,
) -> str:
    """Generate unambiguous SHA-256 edge key for ARCH_RELATIONSHIP."""
    p_id = str(project_id).lower()
    a_id = str(architecture_version_id).lower()
    g_id = str(generation_id).lower()
    l_id = unicodedata.normalize("NFC", str(relationship_logical_id))

    _check_no_nul("project_id", p_id)
    _check_no_nul("architecture_version_id", a_id)
    _check_no_nul("generation_id", g_id)
    _check_no_nul("relationship_logical_id", l_id)

    payload = f"{p_id}\0{a_id}\0{g_id}\0{l_id}".encode()
    return hashlib.sha256(payload).hexdigest().lower()


def _normalize_for_canonical_json(val: Any) -> Any:
    if isinstance(val, str):
        return unicodedata.normalize("NFC", val)
    if isinstance(val, UUID):
        return str(val).lower()
    if isinstance(val, (tuple, list)):
        return [_normalize_for_canonical_json(item) for item in val]
    if isinstance(val, Mapping):
        return {
            unicodedata.normalize("NFC", str(k)): _normalize_for_canonical_json(v)
            for k, v in val.items()
        }
    return val


def canonical_json_bytes(data: Any) -> bytes:
    """Serialize data to canonical JSON bytes with sorted keys and NFC normalization."""
    normalized = _normalize_for_canonical_json(data)
    return json.dumps(
        normalized,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def validate_source_root(value: Any) -> str:
    """Validate repository-relative application root against strict safety rules."""
    if not isinstance(value, str):
        raise ProjectionMetadataError(
            "source_root must be a string", code="projection_metadata_invalid"
        )
    val = unicodedata.normalize("NFC", value)
    if not val:
        raise ProjectionMetadataError(
            "source_root cannot be empty", code="projection_metadata_invalid"
        )

    _check_no_nul("source_root", val)
    _check_no_control_chars("source_root", val)

    if val.startswith("/"):
        raise ProjectionMetadataError(
            "source_root cannot have leading forward slash",
            code="projection_metadata_invalid",
        )
    if "\\" in val:
        raise ProjectionMetadataError(
            "source_root cannot contain backslashes",
            code="projection_metadata_invalid",
        )
    if val.startswith(("//", "\\\\")):
        raise ProjectionMetadataError(
            "source_root cannot have UNC prefix",
            code="projection_metadata_invalid",
        )
    if _WINDOWS_DRIVE_PATTERN.match(val):
        raise ProjectionMetadataError(
            "source_root cannot contain Windows drive prefix",
            code="projection_metadata_invalid",
        )
    if _URI_SCHEME_PATTERN.match(val):
        raise ProjectionMetadataError(
            "source_root cannot contain URI scheme prefix",
            code="projection_metadata_invalid",
        )

    segments = val.split("/")
    for segment in segments:
        if not segment:
            raise ProjectionMetadataError(
                "source_root cannot contain empty path segments",
                code="projection_metadata_invalid",
            )
        if segment in (".", ".."):
            raise ProjectionMetadataError(
                "source_root cannot contain dot or dot-dot path segments",
                code="projection_metadata_invalid",
            )

    if val.startswith(HOST_PATH_PREFIXES) or any(
        sig in f"/{val}/" for sig in HOST_PATH_SIGNATURES
    ):
        raise ProjectionMetadataError(
            "source_root matches host path guard",
            code="projection_metadata_invalid",
        )

    return val


def validate_route_path(field_name: str, value: Any) -> str:
    """Validate canonical HTTP route path against strict route-shape rules."""
    if not isinstance(value, str):
        raise ProjectionMetadataError(
            f"{field_name} must be a string", code="projection_metadata_invalid"
        )
    val = unicodedata.normalize("NFC", value)
    if not val:
        raise ProjectionMetadataError(
            f"{field_name} cannot be empty", code="projection_metadata_invalid"
        )

    _check_no_nul(field_name, val)
    _check_no_control_chars(field_name, val)

    if not val.startswith("/"):
        raise ProjectionMetadataError(
            f"{field_name} must start with route forward slash",
            code="projection_metadata_invalid",
        )
    if "\\" in val:
        raise ProjectionMetadataError(
            f"{field_name} cannot contain backslashes",
            code="projection_metadata_invalid",
        )
    if _WINDOWS_DRIVE_PATTERN.match(val):
        raise ProjectionMetadataError(
            f"{field_name} cannot contain Windows drive prefix",
            code="projection_metadata_invalid",
        )
    if _URI_SCHEME_PATTERN.match(val):
        raise ProjectionMetadataError(
            f"{field_name} cannot contain URI scheme prefix",
            code="projection_metadata_invalid",
        )

    segments = val.split("/")
    for i, segment in enumerate(segments):
        # Leading / gives empty string at segments[0] (expected).
        # Trailing / gives empty string at segments[-1] (allowed trailing slash).
        if not segment:
            if i != 0 and i != len(segments) - 1:
                raise ProjectionMetadataError(
                    f"{field_name} cannot contain empty interior path segments",
                    code="projection_metadata_invalid",
                )
            continue
        if segment in (".", ".."):
            raise ProjectionMetadataError(
                f"{field_name} cannot contain dot or dot-dot path segments",
                code="projection_metadata_invalid",
            )

    if val in HOST_PATH_EXACT or any(
        val.startswith(sig) for sig in HOST_PATH_SIGNATURES
    ):
        raise ProjectionMetadataError(
            f"{field_name} matches host path guard",
            code="projection_metadata_invalid",
        )

    return val


def normalize_metadata(
    raw_metadata: Mapping[str, Any],
    *,
    max_key_bytes: int = MAX_META_KEY_BYTES,
    max_string_bytes: int = MAX_META_STRING_BYTES,
    max_list_items: int = MAX_META_LIST_ITEMS,
    max_record_bytes: int = MAX_META_RECORD_BYTES,
) -> dict[str, Any]:
    """Validate and normalize metadata against allowlist, caps, and field rules."""
    if not isinstance(raw_metadata, Mapping):
        raise ProjectionMetadataError(
            "metadata must be a mapping", code="projection_metadata_invalid"
        )

    try:
        raw_dict = dict(raw_metadata)
        raw_bytes = json.dumps(raw_dict, ensure_ascii=False).encode("utf-8")
    except TypeError, ValueError:
        raise ProjectionMetadataError(
            "metadata cannot be serialized to JSON",
            code="projection_metadata_invalid",
        ) from None

    if len(raw_bytes) > max_record_bytes:
        raise ProjectionCapacityExceededError(
            "metadata record exceeds maximum allowed byte capacity",
            code="projection_capacity_exceeded",
        )

    normalized: dict[str, Any] = {}
    for key, val in raw_metadata.items():
        if not isinstance(key, str):
            raise ProjectionMetadataError(
                "metadata keys must be strings", code="projection_metadata_invalid"
            )
        key_norm = unicodedata.normalize("NFC", key)
        _check_no_nul("metadata key", key_norm)
        _check_no_control_chars("metadata key", key_norm)

        key_bytes = key_norm.encode("utf-8")
        if len(key_bytes) > max_key_bytes:
            raise ProjectionCapacityExceededError(
                f"metadata key '{key_norm}' exceeds {max_key_bytes} bytes",
                code="projection_capacity_exceeded",
            )

        if key_norm not in ALL_ALLOWED_METADATA_FIELDS:
            raise ProjectionMetadataError(
                f"metadata field '{key_norm}' is not permitted by allowlist",
                code="projection_metadata_invalid",
            )

        prop_name = f"meta__{key_norm}"

        if key_norm in METADATA_STRING_FIELDS:
            if not isinstance(val, str):
                raise ProjectionMetadataError(
                    f"metadata field '{key_norm}' must be a string",
                    code="projection_metadata_invalid",
                )
            if key_norm == "source_root":
                val_norm = validate_source_root(val)
            elif key_norm in ("path", "mount_path", "declared_path"):
                val_norm = validate_route_path(key_norm, val)
            else:
                val_norm = unicodedata.normalize("NFC", val)
                _check_no_nul(key_norm, val_norm)
                _check_no_control_chars(key_norm, val_norm)

            val_bytes = val_norm.encode("utf-8")
            if len(val_bytes) > max_string_bytes:
                raise ProjectionCapacityExceededError(
                    f"metadata string for '{key_norm}' exceeds limit",
                    code="projection_capacity_exceeded",
                )
            normalized[prop_name] = val_norm

        elif key_norm in METADATA_BOOLEAN_FIELDS:
            if type(val) is not bool:
                raise ProjectionMetadataError(
                    f"metadata field '{key_norm}' must be a boolean",
                    code="projection_metadata_invalid",
                )
            normalized[prop_name] = val

        elif key_norm in METADATA_STRING_LIST_FIELDS:
            if not isinstance(val, (list, tuple)):
                raise ProjectionMetadataError(
                    f"metadata field '{key_norm}' must be a list of strings",
                    code="projection_metadata_invalid",
                )
            if len(val) > max_list_items:
                raise ProjectionCapacityExceededError(
                    f"metadata list '{key_norm}' exceeds {max_list_items} items",
                    code="projection_capacity_exceeded",
                )
            normalized_list: list[str] = []
            for idx, item in enumerate(val):
                if not isinstance(item, str):
                    raise ProjectionMetadataError(
                        f"item at index {idx} in '{key_norm}' must be a string",
                        code="projection_metadata_invalid",
                    )
                item_norm = unicodedata.normalize("NFC", item)
                _check_no_nul(f"{key_norm}[{idx}]", item_norm)
                _check_no_control_chars(f"{key_norm}[{idx}]", item_norm)
                item_bytes = item_norm.encode("utf-8")
                if len(item_bytes) > max_string_bytes:
                    raise ProjectionCapacityExceededError(
                        f"item at index {idx} in '{key_norm}' exceeds limit",
                        code="projection_capacity_exceeded",
                    )
                normalized_list.append(item_norm)
            normalized[prop_name] = normalized_list

    return normalized


def compute_key_set_digest(
    node_keys: Iterable[str],
    relationship_keys: Iterable[str],
) -> str:
    """Compute SHA-256 key-set digest from sorted node and relationship keys."""
    sorted_node_keys = sorted(node_keys)
    sorted_rel_keys = sorted(relationship_keys)
    payload = {
        "node_keys": sorted_node_keys,
        "relationship_keys": sorted_rel_keys,
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest().lower()


def compute_endpoint_digest(
    records: Iterable[ProjectedRelationshipRecord | Mapping[str, Any]],
) -> str:
    """Compute SHA-256 endpoint digest from sorted relationship endpoint records."""
    endpoint_records: list[dict[str, str]] = []
    for r in records:
        if isinstance(r, ProjectedRelationshipRecord):
            endpoint_records.append(
                {
                    "kind": r.canonical_kind,
                    "relationship_key": r.projection_key,
                    "source_key": r.source_projection_key,
                    "target_key": r.target_projection_key,
                }
            )
        elif isinstance(r, Mapping):
            endpoint_records.append(
                {
                    "kind": str(r["kind"]),
                    "relationship_key": str(r["relationship_key"]),
                    "source_key": str(r["source_key"]),
                    "target_key": str(r["target_key"]),
                }
            )
        else:
            raise TypeError(f"Unsupported record type: {type(r)}")

    endpoint_records.sort(key=lambda rec: rec["relationship_key"])
    return hashlib.sha256(canonical_json_bytes(endpoint_records)).hexdigest().lower()


def compute_evidence_summary_digest(doc: ArchitectureDocument) -> str:
    """Derive deterministic evidence summary digest from ArchitectureDocument."""
    # Map evidence_logical_id -> owning entity/relationship logical IDs
    owning_entities: dict[str, set[str]] = {}
    owning_relationships: dict[str, set[str]] = {}

    for entity in doc.entities:
        for ev_id in entity.evidence_ids:
            owning_entities.setdefault(ev_id, set()).add(entity.logical_id)

    for rel in doc.relationships:
        for ev_id in rel.evidence_ids:
            owning_relationships.setdefault(ev_id, set()).add(rel.logical_id)

    evidence_records: list[dict[str, Any]] = []
    for ev in doc.evidence:
        ev_logical_id = unicodedata.normalize("NFC", str(ev.logical_id))
        evidence_records.append(
            {
                "evidence_logical_id": ev_logical_id,
                "owning_entity_logical_ids": sorted(
                    owning_entities.get(ev.logical_id, ())
                ),
                "owning_relationship_logical_ids": sorted(
                    owning_relationships.get(ev.logical_id, ())
                ),
            }
        )

    evidence_records.sort(key=lambda rec: rec["evidence_logical_id"])
    return hashlib.sha256(canonical_json_bytes(evidence_records)).hexdigest().lower()


def compute_unresolved_summary_digest(doc: ArchitectureDocument) -> str:
    """Derive unresolved summary digest from ArchitectureDocument."""
    unresolved_records: list[dict[str, Any]] = []
    for item in doc.unresolved_relationships:
        logical_id = unicodedata.normalize("NFC", str(item.logical_id))
        unresolved_records.append(
            {
                "evidence_logical_ids": sorted(
                    unicodedata.normalize("NFC", str(e)) for e in item.evidence_ids
                ),
                "kind": str(item.kind),
                "logical_id": logical_id,
                "status": str(item.status),
            }
        )

    unresolved_records.sort(key=lambda rec: rec["logical_id"])
    return hashlib.sha256(canonical_json_bytes(unresolved_records)).hexdigest().lower()


def compute_conflict_summary_digest(doc: ArchitectureDocument) -> str:
    """Derive deterministic conflict summary digest from ArchitectureDocument."""
    conflict_records: list[dict[str, Any]] = []
    for item in doc.conflicts:
        logical_id = unicodedata.normalize("NFC", str(item.logical_id))
        conflict_records.append(
            {
                "conflict_type": str(item.conflict_type),
                "evidence_logical_ids": sorted(
                    unicodedata.normalize("NFC", str(e)) for e in item.evidence_ids
                ),
                "logical_id": logical_id,
                "subject_key": unicodedata.normalize("NFC", str(item.subject_key)),
            }
        )

    conflict_records.sort(key=lambda rec: rec["logical_id"])
    return hashlib.sha256(canonical_json_bytes(conflict_records)).hexdigest().lower()


def compute_payload_digest(
    *,
    project_id: UUID,
    architecture_version_id: UUID,
    generation_id: UUID,
    generation_key: str,
    counts: ProjectionCounts,
    nodes: Sequence[ProjectedNodeRecord],
    relationships: Sequence[ProjectedRelationshipRecord],
    evidence_summary_digest: str,
    unresolved_summary_digest: str,
    conflict_summary_digest: str,
) -> str:
    """Compute SHA-256 payload digest combining header, elements, and summaries."""
    sorted_nodes = sorted(nodes, key=lambda n: n.projection_key)
    sorted_relationships = sorted(relationships, key=lambda r: r.projection_key)

    nodes_repr = [
        {
            "architecture_entity_id": str(n.architecture_entity_id).lower(),
            "canonical_kind": n.canonical_kind,
            "evidence_logical_ids": sorted(n.evidence_logical_ids),
            "fact_status": n.fact_status,
            "generation_id": str(n.generation_id).lower(),
            "generation_key": n.generation_key,
            "logical_id": n.logical_id,
            "name": n.name,
            "namespace": list(n.namespace),
            "project_id": str(n.project_id).lower(),
            "projection_key": n.projection_key,
            "properties": n.properties,
            "semantic_signature": n.semantic_signature,
        }
        for n in sorted_nodes
    ]

    relationships_repr = [
        {
            "architecture_relationship_id": str(r.architecture_relationship_id).lower(),
            "canonical_kind": r.canonical_kind,
            "evidence_logical_ids": sorted(r.evidence_logical_ids),
            "generation_id": str(r.generation_id).lower(),
            "generation_key": r.generation_key,
            "logical_id": r.logical_id,
            "project_id": str(r.project_id).lower(),
            "projection_key": r.projection_key,
            "properties": r.properties,
            "source_logical_id": r.source_logical_id,
            "source_projection_key": r.source_projection_key,
            "status": r.status,
            "target_logical_id": r.target_logical_id,
            "target_projection_key": r.target_projection_key,
        }
        for r in sorted_relationships
    ]

    payload = {
        "counts": {
            "conflicts": counts.conflicts,
            "entities": counts.entities,
            "evidence": counts.evidence,
            "relationships": counts.relationships,
            "unresolved": counts.unresolved,
        },
        "generation_header": {
            "architecture_version_id": str(architecture_version_id).lower(),
            "generation_id": str(generation_id).lower(),
            "generation_key": generation_key,
            "project_id": str(project_id).lower(),
        },
        "nodes": nodes_repr,
        "relationships": relationships_repr,
        "summary_digests": {
            "conflict_summary_digest": conflict_summary_digest,
            "evidence_summary_digest": evidence_summary_digest,
            "unresolved_summary_digest": unresolved_summary_digest,
        },
    }

    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest().lower()


def build_projection_plan(
    doc: ArchitectureDocument,
    *,
    generation_id: UUID,
    expected_counts: ProjectionCounts | None = None,
    max_projected_properties_bytes: int = MAX_PROJECTED_PROPERTIES_BYTES,
) -> ProjectionPlan:
    """Build immutable projection plan from an ArchitectureDocument."""
    if doc.architecture_schema_version != "1.0.0":
        raise ProjectionContractError(
            f"Unsupported schema version: {doc.architecture_schema_version}",
            code="graph_schema_incompatible",
        )

    # Recheck frozen P3 hard maxima
    if len(doc.entities) > MAX_ENTITIES:
        raise ProjectionCapacityExceededError(
            f"Entity count {len(doc.entities)} exceeds maximum {MAX_ENTITIES}",
            code="projection_capacity_exceeded",
        )
    if len(doc.relationships) > MAX_RELATIONSHIPS:
        raise ProjectionCapacityExceededError(
            f"Relationship count {len(doc.relationships)} exceeds max",
            code="projection_capacity_exceeded",
        )
    if len(doc.evidence) > MAX_EVIDENCE:
        raise ProjectionCapacityExceededError(
            f"Evidence count {len(doc.evidence)} exceeds maximum {MAX_EVIDENCE}",
            code="projection_capacity_exceeded",
        )
    if len(doc.unresolved_relationships) > MAX_UNRESOLVED_RELATIONSHIPS:
        raise ProjectionCapacityExceededError(
            f"Unresolved count {len(doc.unresolved_relationships)} exceeds max",
            code="projection_capacity_exceeded",
        )
    if len(doc.conflicts) > MAX_CONFLICTS:
        raise ProjectionCapacityExceededError(
            f"Conflict count {len(doc.conflicts)} exceeds maximum {MAX_CONFLICTS}",
            code="projection_capacity_exceeded",
        )

    actual_counts = ProjectionCounts(
        entities=len(doc.entities),
        relationships=len(doc.relationships),
        evidence=len(doc.evidence),
        unresolved=len(doc.unresolved_relationships),
        conflicts=len(doc.conflicts),
    )

    if expected_counts is not None and expected_counts != actual_counts:
        raise ProjectionSourceMismatchError(
            f"Counts {actual_counts} do not match expected {expected_counts}",
            code="projection_source_mismatch",
        )

    effective_counts = expected_counts if expected_counts is not None else actual_counts

    project_id = doc.project_id
    version_id = doc.architecture_version_id
    generation_key = compute_generation_key(project_id, version_id, generation_id)

    # Map Entities to ProjectedNodeRecords
    entity_by_logical_id: dict[str, ProjectedNodeRecord] = {}
    node_keys: set[str] = set()

    for entity in doc.entities:
        logical_id = unicodedata.normalize("NFC", str(entity.logical_id))
        _check_no_nul("entity logical_id", logical_id)
        if not logical_id:
            raise ProjectionContractError(
                "Entity logical ID cannot be empty",
                code="projection_contract_mismatch",
            )
        if logical_id in entity_by_logical_id:
            raise ProjectionContractError(
                f"Duplicate entity logical ID '{logical_id}'",
                code="projection_contract_mismatch",
            )

        node_key = compute_node_key(project_id, version_id, generation_id, logical_id)
        if node_key in node_keys:
            raise ProjectionContractError(
                f"Duplicate node key collision for entity '{logical_id}'",
                code="projection_contract_mismatch",
            )
        node_keys.add(node_key)

        stable_entity_id = architecture_resource_id(version_id, "entity", logical_id)

        meta_props = normalize_metadata(entity.metadata)

        canonical_kind_val = (
            entity.kind.value
            if isinstance(entity.kind, ArchitectureEntityKind)
            else str(entity.kind)
        )
        fact_status_val = (
            entity.status.value
            if isinstance(entity.status, ArchitectureFactStatus)
            else str(entity.status)
        )

        name_norm = unicodedata.normalize("NFC", str(entity.name))
        _check_no_nul("entity name", name_norm)
        _check_no_control_chars("entity name", name_norm)

        sig_norm = unicodedata.normalize("NFC", str(entity.semantic_signature))
        _check_no_nul("entity semantic_signature", sig_norm)

        namespace_tuple = tuple(
            unicodedata.normalize("NFC", str(ns)) for ns in entity.namespace
        )
        for ns in namespace_tuple:
            _check_no_nul("entity namespace", ns)
            _check_no_control_chars("entity namespace", ns)

        evidence_ids_tuple = tuple(
            sorted(unicodedata.normalize("NFC", str(ev)) for ev in entity.evidence_ids)
        )
        for ev in evidence_ids_tuple:
            _check_no_nul("entity evidence_id", ev)

        core_props: dict[str, Any] = {
            "project_id": str(project_id).lower(),
            "architecture_version_id": str(version_id).lower(),
            "generation_id": str(generation_id).lower(),
            "generation_key": generation_key,
            "projection_key": node_key,
            "architecture_entity_id": str(stable_entity_id).lower(),
            "logical_id": logical_id,
            "semantic_signature": sig_norm,
            "canonical_kind": canonical_kind_val,
            "name": name_norm,
            "namespace": list(namespace_tuple),
            "fact_status": fact_status_val,
            "evidence_logical_ids": list(evidence_ids_tuple),
        }
        all_props = {**core_props, **meta_props}

        serialized_props = json.dumps(all_props, ensure_ascii=False).encode("utf-8")
        if len(serialized_props) > max_projected_properties_bytes:
            raise ProjectionCapacityExceededError(
                f"Node '{logical_id}' properties exceed cap",
                code="projection_capacity_exceeded",
            )

        record = ProjectedNodeRecord(
            project_id=project_id,
            architecture_version_id=version_id,
            generation_id=generation_id,
            generation_key=generation_key,
            projection_key=node_key,
            architecture_entity_id=stable_entity_id,
            logical_id=logical_id,
            semantic_signature=sig_norm,
            canonical_kind=canonical_kind_val,
            name=name_norm,
            namespace=namespace_tuple,
            fact_status=fact_status_val,
            evidence_logical_ids=evidence_ids_tuple,
            properties=all_props,
        )
        entity_by_logical_id[logical_id] = record

    # Map Relationships to ProjectedRelationshipRecords
    relationships_list: list[ProjectedRelationshipRecord] = []
    rel_keys: set[str] = set()
    rel_logical_ids: set[str] = set()

    for rel in doc.relationships:
        logical_id = unicodedata.normalize("NFC", str(rel.logical_id))
        _check_no_nul("relationship logical_id", logical_id)
        if not logical_id:
            raise ProjectionContractError(
                "Relationship logical ID cannot be empty",
                code="projection_contract_mismatch",
            )
        if logical_id in rel_logical_ids:
            raise ProjectionContractError(
                f"Duplicate relationship logical ID '{logical_id}'",
                code="projection_contract_mismatch",
            )
        rel_logical_ids.add(logical_id)

        edge_key = compute_edge_key(project_id, version_id, generation_id, logical_id)
        if edge_key in rel_keys:
            raise ProjectionContractError(
                f"Duplicate edge key collision for relationship '{logical_id}'",
                code="projection_contract_mismatch",
            )
        rel_keys.add(edge_key)

        stable_rel_id = architecture_resource_id(version_id, "relationship", logical_id)

        src_id = unicodedata.normalize("NFC", str(rel.source_logical_id))
        tgt_id = unicodedata.normalize("NFC", str(rel.target_logical_id))

        if src_id not in entity_by_logical_id:
            raise ProjectionContractError(
                f"Relationship '{logical_id}' missing source '{src_id}'",
                code="projection_contract_mismatch",
            )
        if tgt_id not in entity_by_logical_id:
            raise ProjectionContractError(
                f"Relationship '{logical_id}' missing target '{tgt_id}'",
                code="projection_contract_mismatch",
            )

        src_node = entity_by_logical_id[src_id]
        tgt_node = entity_by_logical_id[tgt_id]

        meta_props = normalize_metadata(rel.metadata)

        canonical_kind_val = (
            rel.kind.value
            if isinstance(rel.kind, ArchitectureRelationshipKind)
            else str(rel.kind)
        )
        status_val = (
            rel.status.value
            if isinstance(rel.status, ArchitectureFactStatus)
            else str(rel.status)
        )

        evidence_ids_tuple = tuple(
            sorted(unicodedata.normalize("NFC", str(ev)) for ev in rel.evidence_ids)
        )
        for ev in evidence_ids_tuple:
            _check_no_nul("relationship evidence_id", ev)

        core_props = {
            "project_id": str(project_id).lower(),
            "architecture_version_id": str(version_id).lower(),
            "generation_id": str(generation_id).lower(),
            "generation_key": generation_key,
            "projection_key": edge_key,
            "architecture_relationship_id": str(stable_rel_id).lower(),
            "logical_id": logical_id,
            "canonical_kind": canonical_kind_val,
            "status": status_val,
            "source_logical_id": src_id,
            "target_logical_id": tgt_id,
            "source_projection_key": src_node.projection_key,
            "target_projection_key": tgt_node.projection_key,
            "evidence_logical_ids": list(evidence_ids_tuple),
        }
        all_props = {**core_props, **meta_props}

        serialized_props = json.dumps(all_props, ensure_ascii=False).encode("utf-8")
        if len(serialized_props) > max_projected_properties_bytes:
            raise ProjectionCapacityExceededError(
                f"Relationship '{logical_id}' properties exceed cap",
                code="projection_capacity_exceeded",
            )

        rel_record = ProjectedRelationshipRecord(
            project_id=project_id,
            architecture_version_id=version_id,
            generation_id=generation_id,
            generation_key=generation_key,
            projection_key=edge_key,
            architecture_relationship_id=stable_rel_id,
            logical_id=logical_id,
            canonical_kind=canonical_kind_val,
            status=status_val,
            source_logical_id=src_id,
            target_logical_id=tgt_id,
            source_projection_key=src_node.projection_key,
            target_projection_key=tgt_node.projection_key,
            evidence_logical_ids=evidence_ids_tuple,
            properties=all_props,
        )
        relationships_list.append(rel_record)

    sorted_nodes = tuple(
        sorted(entity_by_logical_id.values(), key=lambda n: n.projection_key)
    )
    sorted_relationships = tuple(
        sorted(relationships_list, key=lambda r: r.projection_key)
    )

    key_set_digest = compute_key_set_digest(
        (n.projection_key for n in sorted_nodes),
        (r.projection_key for r in sorted_relationships),
    )
    endpoint_digest = compute_endpoint_digest(sorted_relationships)
    evidence_summary_digest = compute_evidence_summary_digest(doc)
    unresolved_summary_digest = compute_unresolved_summary_digest(doc)
    conflict_summary_digest = compute_conflict_summary_digest(doc)

    payload_digest = compute_payload_digest(
        project_id=project_id,
        architecture_version_id=version_id,
        generation_id=generation_id,
        generation_key=generation_key,
        counts=effective_counts,
        nodes=sorted_nodes,
        relationships=sorted_relationships,
        evidence_summary_digest=evidence_summary_digest,
        unresolved_summary_digest=unresolved_summary_digest,
        conflict_summary_digest=conflict_summary_digest,
    )

    return ProjectionPlan(
        project_id=project_id,
        architecture_version_id=version_id,
        generation_id=generation_id,
        generation_key=generation_key,
        expected_counts=effective_counts,
        nodes=sorted_nodes,
        relationships=sorted_relationships,
        key_set_digest=key_set_digest,
        endpoint_digest=endpoint_digest,
        evidence_summary_digest=evidence_summary_digest,
        unresolved_summary_digest=unresolved_summary_digest,
        conflict_summary_digest=conflict_summary_digest,
        payload_digest=payload_digest,
        source_content_digest=doc.content_digest,
    )


__all__ = [
    "ALL_ALLOWED_METADATA_FIELDS",
    "HOST_PATH_EXACT",
    "HOST_PATH_PREFIXES",
    "HOST_PATH_SIGNATURES",
    "MANIFEST_STATE_BUILDING",
    "MANIFEST_STATE_READY",
    "MAX_CONFLICTS",
    "MAX_ENTITIES",
    "MAX_EVIDENCE",
    "MAX_META_KEY_BYTES",
    "MAX_META_LIST_ITEMS",
    "MAX_META_RECORD_BYTES",
    "MAX_META_STRING_BYTES",
    "MAX_PROJECTED_PROPERTIES_BYTES",
    "MAX_RELATIONSHIPS",
    "MAX_SERIALIZED_SOURCE_BYTES",
    "MAX_UNRESOLVED_RELATIONSHIPS",
    "METADATA_BOOLEAN_FIELDS",
    "METADATA_STRING_FIELDS",
    "METADATA_STRING_LIST_FIELDS",
    "ProjectedNodeRecord",
    "ProjectedRelationshipRecord",
    "ProjectionCapacityExceededError",
    "ProjectionContractError",
    "ProjectionError",
    "ProjectionMetadataError",
    "ProjectionPlan",
    "ProjectionSourceMismatchError",
    "ProjectionSummaryDigests",
    "build_projection_plan",
    "canonical_json_bytes",
    "compute_conflict_summary_digest",
    "compute_edge_key",
    "compute_endpoint_digest",
    "compute_evidence_summary_digest",
    "compute_generation_key",
    "compute_key_set_digest",
    "compute_node_key",
    "compute_payload_digest",
    "compute_unresolved_summary_digest",
    "normalize_metadata",
    "validate_route_path",
    "validate_source_root",
]
