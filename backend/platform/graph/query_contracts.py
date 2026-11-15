"""P4-Q1 graph query contracts, closed vocabularies, limits, and DTOs.

This module defines the frozen transport-neutral domain contracts for Phase 4
Module 3 (Graph Query and Exploration API).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.platform.graph.model import ProjectionCounts

P4_Q1_CONTRACT_VERSION: Final[str] = "1.0.0"

# Approved defaults
DEFAULT_QUERY_DEPTH: Final[int] = 1
DEFAULT_QUERY_NODES: Final[int] = 100
DEFAULT_QUERY_EDGES: Final[int] = 200
DEFAULT_QUERY_PATHS: Final[int] = 5
DEFAULT_QUERY_PAGE_SIZE: Final[int] = 50
DEFAULT_QUERY_TIMEOUT_SECONDS: Final[float] = 2.0

# Approved hard maxima
MAX_QUERY_DEPTH: Final[int] = 5
MAX_QUERY_NODES: Final[int] = 500
MAX_QUERY_EDGES: Final[int] = 1_000
MAX_QUERY_PATHS: Final[int] = 25
MAX_QUERY_PAGE_SIZE: Final[int] = 100
MAX_QUERY_TIMEOUT_SECONDS: Final[float] = 5.0
MAX_CURSOR_LENGTH: Final[int] = 2048


class TraversalDirection(StrEnum):
    """Closed direction vocabulary for graph traversals."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"
    BOTH = "both"


class ContainmentDirection(StrEnum):
    """Closed direction vocabulary for containment hierarchy navigation."""

    PARENTS = "parents"
    CHILDREN = "children"
    BOTH = "both"


class GraphRelationshipKind(StrEnum):
    """Canonical relationship kinds allowed in the projected architecture graph.

    Contains is the sole hierarchy kind; the remaining 12 kinds form the
    approved dependency set.
    """

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


APPROVED_DEPENDENCY_RELATIONSHIP_KINDS: Final[frozenset[GraphRelationshipKind]] = (
    frozenset(
        {
            GraphRelationshipKind.DEPENDS_ON,
            GraphRelationshipKind.IMPORTS,
            GraphRelationshipKind.CALLS,
            GraphRelationshipKind.EXPOSES,
            GraphRelationshipKind.CONSUMES,
            GraphRelationshipKind.PRODUCES,
            GraphRelationshipKind.CONNECTS_TO,
            GraphRelationshipKind.PERSISTS_TO,
            GraphRelationshipKind.USES,
            GraphRelationshipKind.EXTENDS,
            GraphRelationshipKind.IMPLEMENTS,
            GraphRelationshipKind.ROUTES_TO,
        }
    )
)

ALL_APPROVED_RELATIONSHIP_KINDS: Final[frozenset[GraphRelationshipKind]] = frozenset(
    GraphRelationshipKind
)


# --- Error taxonomy (Section 7D.G) ---


class GraphQueryError(Exception):
    """Base exception for all safe M3 graph query errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.safe_details = dict(safe_details) if safe_details else {}


class GraphProjectionNotFoundError(GraphQueryError):
    """No exact project/version projection resource exists."""

    def __init__(
        self,
        message: str = "Graph projection resource not found",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="graph_projection_not_found",
            safe_details=safe_details,
        )


class GraphProjectionNotReadyError(GraphQueryError):
    """Exact resource has no readable active generation."""

    def __init__(
        self,
        message: str = "Graph projection is not ready for queries",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="graph_projection_not_ready",
            safe_details=safe_details,
        )


class GraphNodeNotFoundError(GraphQueryError):
    """Anchor/node absent in authorized exact scope."""

    def __init__(
        self,
        message: str = "Graph node not found in scope",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="graph_node_not_found",
            safe_details=safe_details,
        )


class GraphCursorInvalidError(GraphQueryError):
    """Malformed or tampered pagination cursor."""

    def __init__(
        self,
        message: str = "Pagination cursor is invalid",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="graph_cursor_invalid",
            safe_details=safe_details,
        )


class GraphCursorScopeMismatchError(GraphQueryError):
    """Cursor parameters, project, or version do not match current request."""

    def __init__(
        self,
        message: str = "Pagination cursor scope mismatch",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="graph_cursor_scope_mismatch",
            safe_details=safe_details,
        )


class GraphCursorExpiredError(GraphQueryError):
    """Valid pagination cursor exceeded TTL."""

    def __init__(
        self,
        message: str = "Pagination cursor has expired",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="graph_cursor_expired",
            safe_details=safe_details,
        )


class GraphGenerationChangedError(GraphQueryError):
    """Active projection generation changed during read or since cursor was issued."""

    def __init__(
        self,
        message: str = "Active graph generation has changed",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="graph_generation_changed",
            safe_details=safe_details,
        )


class GraphQueryLimitExceededError(GraphQueryError):
    """Request exceeds approved query bounds or uses forbidden parameters."""

    def __init__(
        self,
        message: str = "Graph query limits exceeded",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="graph_query_limit_exceeded",
            safe_details=safe_details,
        )


class GraphQueryTimeoutError(GraphQueryError):
    """Operation deadline exhausted."""

    def __init__(
        self,
        message: str = "Graph query operation timed out",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="graph_query_timeout",
            safe_details=safe_details,
        )


class GraphUnavailableError(GraphQueryError):
    """Neo4j or graph storage driver is unavailable."""

    def __init__(
        self,
        message: str = "Graph query storage is unavailable",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="graph_unavailable",
            safe_details=safe_details,
        )


class GraphSchemaIncompatibleError(GraphQueryError):
    """Graph schema or manifest is incompatible with query engine."""

    def __init__(
        self,
        message: str = "Graph schema is incompatible",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="graph_schema_incompatible",
            safe_details=safe_details,
        )


class GraphQueryIntegrityError(GraphQueryError):
    """Same-generation, scope, or referential invariant failed."""

    def __init__(
        self,
        message: str = "Graph query invariant integrity violation",
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="graph_query_integrity_error",
            safe_details=safe_details,
        )


# --- Public DTOs (Section 7D.C1) ---


class GraphReadScope(BaseModel):
    """Verified exact Architecture Version generation read scope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: UUID
    architecture_version_id: UUID
    generation_id: UUID
    resource_state: str
    graph_schema_version: str
    projector_version: str
    counts: ProjectionCounts


class GraphNode(BaseModel):
    """Projected architecture entity representation in P4-Q1."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    architecture_entity_id: UUID
    logical_id: str
    canonical_kind: str
    name: str
    namespace: str
    fact_status: str
    semantic_signature: str
    evidence_logical_ids: tuple[str, ...]
    metadata: dict[str, Any]


class GraphEdge(BaseModel):
    """Projected architecture relationship representation in P4-Q1."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    architecture_relationship_id: UUID
    logical_id: str
    canonical_kind: str
    status: str
    source_entity_id: UUID
    target_entity_id: UUID
    evidence_logical_ids: tuple[str, ...]
    metadata: dict[str, Any]


class GraphSubgraph(BaseModel):
    """Bounded, deduplicated graph window or neighborhood result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scope: GraphReadScope
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    total_manifest_nodes: int
    total_manifest_edges: int
    loaded_nodes: int
    loaded_edges: int
    truncated: bool
    next_cursor: str | None = None


class GraphPath(BaseModel):
    """Ordered sequence of nodes and directed edges forming a simple path."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    hop_count: int


class GraphPathResult(BaseModel):
    """Bounded collection of static canonical paths between two entities."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scope: GraphReadScope
    paths: tuple[GraphPath, ...]
    total_paths_found: int
    truncated: bool


# --- Request DTOs (Section 7D.D1 - D7) ---


def _normalize_kinds(
    kinds: tuple[GraphRelationshipKind, ...] | None,
) -> tuple[GraphRelationshipKind, ...] | None:
    """Normalize kind collection into deduplicated canonical enum order."""
    if kinds is None:
        return None
    # Sort by enum value for deterministic canonical ordering
    deduped = sorted(set(kinds), key=lambda k: k.value)
    return tuple(deduped)


def _validate_cursor_length(cursor: str | None) -> str | None:
    if cursor is not None and len(cursor) > MAX_CURSOR_LENGTH:
        raise GraphQueryLimitExceededError(
            f"Cursor length {len(cursor)} exceeds maximum allowed {MAX_CURSOR_LENGTH}"
        )
    return cursor


class GraphWindowRequest(BaseModel):
    """Request DTO for bounded initial graph window overview."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: UUID
    architecture_version_id: UUID
    node_limit: int = Field(default=DEFAULT_QUERY_NODES, ge=1, le=MAX_QUERY_NODES)
    edge_limit: int = Field(default=DEFAULT_QUERY_EDGES, ge=1, le=MAX_QUERY_EDGES)
    page_size: int = Field(
        default=DEFAULT_QUERY_PAGE_SIZE, ge=1, le=MAX_QUERY_PAGE_SIZE
    )
    canonical_kinds: tuple[GraphRelationshipKind, ...] | None = None
    cursor: str | None = None
    timeout_seconds: float = Field(
        default=DEFAULT_QUERY_TIMEOUT_SECONDS, gt=0, le=MAX_QUERY_TIMEOUT_SECONDS
    )

    @field_validator("canonical_kinds", mode="after")
    @classmethod
    def _validate_kinds(
        cls, v: tuple[GraphRelationshipKind, ...] | None
    ) -> tuple[GraphRelationshipKind, ...] | None:
        return _normalize_kinds(v)

    @field_validator("cursor", mode="after")
    @classmethod
    def _validate_cursor(cls, v: str | None) -> str | None:
        return _validate_cursor_length(v)


class NodeDetailRequest(BaseModel):
    """Request DTO for single entity detail inspector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: UUID
    architecture_version_id: UUID
    entity_id: UUID
    timeout_seconds: float = Field(
        default=DEFAULT_QUERY_TIMEOUT_SECONDS, gt=0, le=MAX_QUERY_TIMEOUT_SECONDS
    )


class NeighborhoodRequest(BaseModel):
    """Request DTO for structural expansion around an anchor node."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: UUID
    architecture_version_id: UUID
    entity_id: UUID
    direction: TraversalDirection = TraversalDirection.BOTH
    depth: int = Field(default=DEFAULT_QUERY_DEPTH, ge=1, le=MAX_QUERY_DEPTH)
    node_limit: int = Field(default=DEFAULT_QUERY_NODES, ge=1, le=MAX_QUERY_NODES)
    edge_limit: int = Field(default=DEFAULT_QUERY_EDGES, ge=1, le=MAX_QUERY_EDGES)
    relationship_kinds: tuple[GraphRelationshipKind, ...] | None = None
    cursor: str | None = None
    timeout_seconds: float = Field(
        default=DEFAULT_QUERY_TIMEOUT_SECONDS, gt=0, le=MAX_QUERY_TIMEOUT_SECONDS
    )

    @field_validator("relationship_kinds", mode="after")
    @classmethod
    def _validate_kinds(
        cls, v: tuple[GraphRelationshipKind, ...] | None
    ) -> tuple[GraphRelationshipKind, ...] | None:
        return _normalize_kinds(v)

    @field_validator("cursor", mode="after")
    @classmethod
    def _validate_cursor(cls, v: str | None) -> str | None:
        return _validate_cursor_length(v)


class DependenciesRequest(BaseModel):
    """Request DTO for outgoing dependency traversal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: UUID
    architecture_version_id: UUID
    entity_id: UUID
    depth: int = Field(default=DEFAULT_QUERY_DEPTH, ge=1, le=MAX_QUERY_DEPTH)
    node_limit: int = Field(default=DEFAULT_QUERY_NODES, ge=1, le=MAX_QUERY_NODES)
    edge_limit: int = Field(default=DEFAULT_QUERY_EDGES, ge=1, le=MAX_QUERY_EDGES)
    relationship_kinds: tuple[GraphRelationshipKind, ...] | None = None
    cursor: str | None = None
    timeout_seconds: float = Field(
        default=DEFAULT_QUERY_TIMEOUT_SECONDS, gt=0, le=MAX_QUERY_TIMEOUT_SECONDS
    )

    @field_validator("relationship_kinds", mode="after")
    @classmethod
    def _validate_dependency_kinds(
        cls, v: tuple[GraphRelationshipKind, ...] | None
    ) -> tuple[GraphRelationshipKind, ...] | None:
        normalized = _normalize_kinds(v)
        if normalized is not None and GraphRelationshipKind.CONTAINS in normalized:
            raise GraphQueryLimitExceededError(
                "Hierarchy kind 'contains' is not permitted in dependency queries"
            )
        return normalized

    @field_validator("cursor", mode="after")
    @classmethod
    def _validate_cursor(cls, v: str | None) -> str | None:
        return _validate_cursor_length(v)


class DependentsRequest(BaseModel):
    """Request DTO for incoming dependent traversal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: UUID
    architecture_version_id: UUID
    entity_id: UUID
    depth: int = Field(default=DEFAULT_QUERY_DEPTH, ge=1, le=MAX_QUERY_DEPTH)
    node_limit: int = Field(default=DEFAULT_QUERY_NODES, ge=1, le=MAX_QUERY_NODES)
    edge_limit: int = Field(default=DEFAULT_QUERY_EDGES, ge=1, le=MAX_QUERY_EDGES)
    relationship_kinds: tuple[GraphRelationshipKind, ...] | None = None
    cursor: str | None = None
    timeout_seconds: float = Field(
        default=DEFAULT_QUERY_TIMEOUT_SECONDS, gt=0, le=MAX_QUERY_TIMEOUT_SECONDS
    )

    @field_validator("relationship_kinds", mode="after")
    @classmethod
    def _validate_dependent_kinds(
        cls, v: tuple[GraphRelationshipKind, ...] | None
    ) -> tuple[GraphRelationshipKind, ...] | None:
        normalized = _normalize_kinds(v)
        if normalized is not None and GraphRelationshipKind.CONTAINS in normalized:
            raise GraphQueryLimitExceededError(
                "Hierarchy kind 'contains' is not permitted in dependent queries"
            )
        return normalized

    @field_validator("cursor", mode="after")
    @classmethod
    def _validate_cursor(cls, v: str | None) -> str | None:
        return _validate_cursor_length(v)


class ContainmentRequest(BaseModel):
    """Request DTO for hierarchy navigation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: UUID
    architecture_version_id: UUID
    entity_id: UUID
    direction: ContainmentDirection = ContainmentDirection.CHILDREN
    depth: int = Field(default=DEFAULT_QUERY_DEPTH, ge=1, le=MAX_QUERY_DEPTH)
    node_limit: int = Field(default=DEFAULT_QUERY_NODES, ge=1, le=MAX_QUERY_NODES)
    edge_limit: int = Field(default=DEFAULT_QUERY_EDGES, ge=1, le=MAX_QUERY_EDGES)
    cursor: str | None = None
    timeout_seconds: float = Field(
        default=DEFAULT_QUERY_TIMEOUT_SECONDS, gt=0, le=MAX_QUERY_TIMEOUT_SECONDS
    )

    @field_validator("cursor", mode="after")
    @classmethod
    def _validate_cursor(cls, v: str | None) -> str | None:
        return _validate_cursor_length(v)


class BoundedPathsRequest(BaseModel):
    """Request DTO for finding simple paths between two entities."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: UUID
    architecture_version_id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    max_depth: int = Field(default=3, ge=1, le=MAX_QUERY_DEPTH)
    path_limit: int = Field(default=DEFAULT_QUERY_PATHS, ge=1, le=MAX_QUERY_PATHS)
    relationship_kinds: tuple[GraphRelationshipKind, ...] | None = None
    timeout_seconds: float = Field(
        default=DEFAULT_QUERY_TIMEOUT_SECONDS, gt=0, le=MAX_QUERY_TIMEOUT_SECONDS
    )

    @field_validator("relationship_kinds", mode="after")
    @classmethod
    def _validate_path_kinds(
        cls, v: tuple[GraphRelationshipKind, ...] | None
    ) -> tuple[GraphRelationshipKind, ...] | None:
        normalized = _normalize_kinds(v)
        if normalized is not None and GraphRelationshipKind.CONTAINS in normalized:
            raise GraphQueryLimitExceededError(
                "Hierarchy kind 'contains' is not permitted in path queries"
            )
        return normalized


__all__ = [
    "ALL_APPROVED_RELATIONSHIP_KINDS",
    "APPROVED_DEPENDENCY_RELATIONSHIP_KINDS",
    "DEFAULT_QUERY_DEPTH",
    "DEFAULT_QUERY_EDGES",
    "DEFAULT_QUERY_NODES",
    "DEFAULT_QUERY_PAGE_SIZE",
    "DEFAULT_QUERY_PATHS",
    "DEFAULT_QUERY_TIMEOUT_SECONDS",
    "MAX_CURSOR_LENGTH",
    "MAX_QUERY_DEPTH",
    "MAX_QUERY_EDGES",
    "MAX_QUERY_NODES",
    "MAX_QUERY_PAGE_SIZE",
    "MAX_QUERY_PATHS",
    "MAX_QUERY_TIMEOUT_SECONDS",
    "P4_Q1_CONTRACT_VERSION",
    "BoundedPathsRequest",
    "ContainmentDirection",
    "ContainmentRequest",
    "DependenciesRequest",
    "DependentsRequest",
    "GraphCursorExpiredError",
    "GraphCursorInvalidError",
    "GraphCursorScopeMismatchError",
    "GraphEdge",
    "GraphGenerationChangedError",
    "GraphNode",
    "GraphNodeNotFoundError",
    "GraphPath",
    "GraphPathResult",
    "GraphProjectionNotFoundError",
    "GraphProjectionNotReadyError",
    "GraphQueryError",
    "GraphQueryIntegrityError",
    "GraphQueryLimitExceededError",
    "GraphQueryTimeoutError",
    "GraphReadScope",
    "GraphRelationshipKind",
    "GraphSchemaIncompatibleError",
    "GraphSubgraph",
    "GraphUnavailableError",
    "GraphWindowRequest",
    "NeighborhoodRequest",
    "NodeDetailRequest",
    "TraversalDirection",
]
