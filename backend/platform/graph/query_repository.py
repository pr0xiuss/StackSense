"""M3 graph generation reader and query repository ports and adapters.

This module provides:
1. GraphGenerationReader protocol and SqlAlchemyGraphGenerationReader adapter
   over the frozen M1 tables, allowing M3 to read active generations safely.
2. GraphQueryRepository protocol defining the frozen retrieval operations.
3. Neo4jGraphQueryRepository adapter executing parameterized, scope-indexed
   Cypher queries under whole-operation deadlines and cancellation guards.
4. In-memory test fakes for isolated testing.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, NoReturn, Protocol
from uuid import UUID

from neo4j import Driver
from neo4j.exceptions import ClientError, DriverError, Neo4jError, TransientError
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from backend.platform.graph.model import (
    PROJECTION_TYPE,
    ProjectionCounts,
    ProjectionPublicState,
)
from backend.platform.graph.persistence import GraphProjectionResourceModel
from backend.platform.graph.projection import MANIFEST_STATE_READY
from backend.platform.graph.query_contracts import (
    BoundedPathsRequest,
    ContainmentDirection,
    ContainmentRequest,
    DependenciesRequest,
    DependentsRequest,
    GraphEdge,
    GraphNode,
    GraphNodeNotFoundError,
    GraphPath,
    GraphPathResult,
    GraphProjectionNotFoundError,
    GraphProjectionNotReadyError,
    GraphQueryIntegrityError,
    GraphQueryTimeoutError,
    GraphReadScope,
    GraphRelationshipKind,
    GraphSchemaIncompatibleError,
    GraphSubgraph,
    GraphUnavailableError,
    GraphWindowRequest,
    NeighborhoodRequest,
    NodeDetailRequest,
)

logger = logging.getLogger(__name__)

# Properties stripped from raw Neo4j records to avoid leaking internal keys
_INTERNAL_PROJECTION_PROPERTIES: frozenset[str] = frozenset(
    {
        "project_id",
        "architecture_version_id",
        "generation_id",
        "generation_key",
        "projection_key",
        "architecture_entity_id",
        "architecture_relationship_id",
        "logical_id",
        "canonical_kind",
        "name",
        "namespace",
        "fact_status",
        "semantic_signature",
        "status",
        "source_logical_id",
        "target_logical_id",
        "source_projection_key",
        "target_projection_key",
        "evidence_logical_ids",
    }
)


def _map_node(props: dict[str, Any]) -> GraphNode:
    """Map a raw Neo4j ArchitectureEntity properties map to a GraphNode DTO."""
    raw_ns = props.get("namespace", "")
    if isinstance(raw_ns, (list, tuple)):
        ns_str = ".".join(str(x) for x in raw_ns if str(x))
    else:
        ns_str = str(raw_ns)

    metadata = {
        k: v for k, v in props.items() if k not in _INTERNAL_PROJECTION_PROPERTIES
    }

    raw_evidence = props.get("evidence_logical_ids") or ()
    evidence_ids = tuple(str(x) for x in raw_evidence)

    try:
        return GraphNode(
            architecture_entity_id=UUID(str(props["architecture_entity_id"])),
            logical_id=str(props["logical_id"]),
            canonical_kind=str(props["canonical_kind"]),
            name=str(props["name"]),
            namespace=ns_str,
            fact_status=str(props.get("fact_status", "")),
            semantic_signature=str(props.get("semantic_signature", "")),
            evidence_logical_ids=evidence_ids,
            metadata=metadata,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GraphQueryIntegrityError(
            "Projected graph node record is structurally invalid"
        ) from exc


def _map_edge(
    props: dict[str, Any],
    source_entity_id: UUID,
    target_entity_id: UUID,
) -> GraphEdge:
    """Map a raw Neo4j ARCH_RELATIONSHIP properties map to a GraphEdge DTO."""
    metadata = {
        k: v for k, v in props.items() if k not in _INTERNAL_PROJECTION_PROPERTIES
    }

    raw_evidence = props.get("evidence_logical_ids") or ()
    evidence_ids = tuple(str(x) for x in raw_evidence)

    try:
        return GraphEdge(
            architecture_relationship_id=UUID(
                str(props["architecture_relationship_id"])
            ),
            logical_id=str(props["logical_id"]),
            canonical_kind=str(props["canonical_kind"]),
            status=str(props.get("status", "")),
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            evidence_logical_ids=evidence_ids,
            metadata=metadata,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GraphQueryIntegrityError(
            "Projected graph relationship record is structurally invalid"
        ) from exc


class GraphGenerationReader(Protocol):
    """Port for resolving and verifying exact Architecture Version active
    generations.
    """

    def resolve_active_generation(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        *,
        timeout_seconds: float | None = None,
    ) -> GraphReadScope:
        """Resolve the active generation for an exact Architecture Version."""
        ...

    def verify_generation_still_active(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        *,
        timeout_seconds: float | None = None,
    ) -> bool:
        """Verify that a captured generation remains active and readable."""
        ...


class SqlAlchemyGraphGenerationReader:
    """Read-only generation resolution adapter over frozen M1 PostgreSQL tables."""

    def __init__(
        self,
        session: Session,
        *,
        statement_timeout_ms: int | None = None,
    ) -> None:
        self._session = session
        self._statement_timeout_ms = statement_timeout_ms

    def _apply_timeout(self, timeout_seconds: float | None) -> None:
        ms: int | None = None
        if timeout_seconds is not None:
            ms = max(1, int(timeout_seconds * 1000))
        elif self._statement_timeout_ms is not None:
            ms = self._statement_timeout_ms

        if ms is not None and self._session.bind is not None:
            dialect_name = getattr(self._session.bind.dialect, "name", "")
            if dialect_name == "postgresql":
                self._session.execute(text(f"SET LOCAL statement_timeout = {ms}"))

    def _translate_timeout(self, exc: DBAPIError) -> NoReturn:
        self._session.rollback()
        sqlstate = getattr(exc.orig, "sqlstate", None)
        if sqlstate == "57014":
            raise GraphQueryTimeoutError(
                "Graph generation lookup exceeded total deadline"
            ) from exc
        raise exc

    def resolve_active_generation(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        *,
        timeout_seconds: float | None = None,
    ) -> GraphReadScope:
        try:
            self._apply_timeout(timeout_seconds)

            stmt = select(GraphProjectionResourceModel).where(
                GraphProjectionResourceModel.architecture_version_id
                == architecture_version_id,
                GraphProjectionResourceModel.projection_type == PROJECTION_TYPE,
            )
            resource = self._session.scalar(stmt)
        except DBAPIError as exc:
            self._translate_timeout(exc)

        if resource is None:
            raise GraphProjectionNotFoundError(
                f"Graph projection resource not found for architecture version "
                f"{architecture_version_id}"
            )

        if resource.project_id != project_id:
            raise GraphProjectionNotFoundError(
                f"Graph projection resource not found for architecture version "
                f"{architecture_version_id} in project {project_id}"
            )

        readable_states = {
            ProjectionPublicState.COMPLETED.value,
            ProjectionPublicState.STALE.value,
        }
        if resource.state not in readable_states:
            raise GraphProjectionNotReadyError(
                f"Graph projection for architecture version {architecture_version_id} "
                f"is in state '{resource.state}', not ready for queries"
            )

        if resource.active_generation_id is None:
            raise GraphProjectionNotReadyError(
                f"Graph projection for architecture version {architecture_version_id} "
                "has no active generation"
            )

        if (
            resource.active_projector_version is None
            or resource.active_graph_schema_version is None
            or resource.active_entity_count is None
            or resource.active_relationship_count is None
            or resource.active_evidence_count is None
            or resource.active_unresolved_count is None
            or resource.active_conflict_count is None
        ):
            raise GraphQueryIntegrityError(
                f"Graph projection for architecture version "
                f"{architecture_version_id} has active generation but incomplete "
                f"verification counts or schema versions"
            )

        counts = ProjectionCounts(
            entities=resource.active_entity_count,
            relationships=resource.active_relationship_count,
            evidence=resource.active_evidence_count,
            unresolved=resource.active_unresolved_count,
            conflicts=resource.active_conflict_count,
        )

        return GraphReadScope(
            project_id=resource.project_id,
            architecture_version_id=resource.architecture_version_id,
            generation_id=resource.active_generation_id,
            resource_state=resource.state,
            graph_schema_version=resource.active_graph_schema_version,
            projector_version=resource.active_projector_version,
            counts=counts,
        )

    def verify_generation_still_active(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        *,
        timeout_seconds: float | None = None,
    ) -> bool:
        try:
            self._apply_timeout(timeout_seconds)

            stmt = select(
                GraphProjectionResourceModel.active_generation_id,
                GraphProjectionResourceModel.state,
                GraphProjectionResourceModel.project_id,
            ).where(
                GraphProjectionResourceModel.architecture_version_id
                == architecture_version_id,
                GraphProjectionResourceModel.projection_type == PROJECTION_TYPE,
            )
            row = self._session.execute(stmt).one_or_none()
        except DBAPIError as exc:
            self._translate_timeout(exc)
        if row is None:
            return False

        active_gen, state, row_project_id = row
        if row_project_id != project_id:
            return False

        readable_states = {
            ProjectionPublicState.COMPLETED.value,
            ProjectionPublicState.STALE.value,
        }
        return active_gen == generation_id and state in readable_states


class GraphQueryRepository(Protocol):
    """Port for executing controlled graph queries against the storage engine."""

    def verify_manifest_ready(
        self,
        scope: GraphReadScope,
        *,
        timeout_seconds: float,
    ) -> bool:
        """Verify that the matching ProjectionManifest is READY in graph storage."""
        ...

    def get_node_detail(
        self,
        scope: GraphReadScope,
        request: NodeDetailRequest,
        *,
        timeout_seconds: float,
    ) -> GraphNode | None:
        """Retrieve a single entity by stable UUID within exact scope."""
        ...

    def query_window(
        self,
        scope: GraphReadScope,
        request: GraphWindowRequest,
        position: dict[str, Any] | None,
        *,
        timeout_seconds: float,
    ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
        """Query deterministic bounded node window and induced canonical edges."""
        ...

    def query_neighborhood(
        self,
        scope: GraphReadScope,
        request: NeighborhoodRequest,
        position: dict[str, Any] | None,
        *,
        timeout_seconds: float,
    ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
        """Query bounded structural expansion around an anchor node."""
        ...

    def query_dependencies(
        self,
        scope: GraphReadScope,
        request: DependenciesRequest,
        position: dict[str, Any] | None,
        *,
        timeout_seconds: float,
    ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
        """Query outgoing static dependencies of an entity."""
        ...

    def query_dependents(
        self,
        scope: GraphReadScope,
        request: DependentsRequest,
        position: dict[str, Any] | None,
        *,
        timeout_seconds: float,
    ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
        """Query incoming static dependents of an entity."""
        ...

    def query_containment(
        self,
        scope: GraphReadScope,
        request: ContainmentRequest,
        position: dict[str, Any] | None,
        *,
        timeout_seconds: float,
    ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
        """Query containment hierarchy around an entity."""
        ...

    def query_bounded_paths(
        self,
        scope: GraphReadScope,
        request: BoundedPathsRequest,
        *,
        timeout_seconds: float,
    ) -> GraphPathResult:
        """Find deterministic static paths between source and target entities."""
        ...


# --- Neo4j Graph Query Repository ---


_MANIFEST_PREFLIGHT_QUERY = (
    "MATCH (m:ProjectionManifest { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}) "
    "RETURN m.state AS state, "
    "       m.graph_schema_version AS graph_schema_version, "
    "       m.projector_version AS projector_version"
)

_NODE_DETAIL_QUERY = (
    "MATCH (n:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id, "
    "    architecture_entity_id: $entity_id "
    "}) "
    "RETURN properties(n) AS properties"
)

_WINDOW_NODES_QUERY = (
    "MATCH (n:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}) "
    "WHERE ($cursor IS NULL OR n.projection_key > $cursor) "
    "RETURN n.projection_key AS projection_key, properties(n) AS properties "
    "ORDER BY n.projection_key ASC "
    "LIMIT $limit"
)

_WINDOW_BOUNDED_NODES_QUERY = (
    "MATCH (n:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}) "
    "WHERE ($window_start IS NULL OR n.projection_key > $window_start) "
    "  AND n.projection_key <= $window_end "
    "RETURN n.projection_key AS projection_key, properties(n) AS properties "
    "ORDER BY n.projection_key ASC"
)

_WINDOW_INDUCED_EDGES_QUERY = (
    "MATCH (s:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "})-[r:ARCH_RELATIONSHIP { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}]->(t:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}) "
    "WHERE s.projection_key IN $node_keys "
    "  AND t.projection_key IN $node_keys "
    "  AND ($kinds IS NULL OR r.canonical_kind IN $kinds) "
    "  AND ($cursor IS NULL OR r.projection_key > $cursor) "
    "RETURN r.projection_key AS projection_key, "
    "       s.architecture_entity_id AS source_entity_id, "
    "       t.architecture_entity_id AS target_entity_id, "
    "       properties(r) AS properties "
    "ORDER BY r.projection_key ASC "
    "LIMIT $limit"
)

_ONE_HOP_OUTGOING_QUERY = (
    "MATCH (s:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "})-[r:ARCH_RELATIONSHIP { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}]->(t:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}) "
    "WHERE s.projection_key IN $frontier_keys "
    "  AND ($kinds IS NULL OR r.canonical_kind IN $kinds) "
    "RETURN s.projection_key AS source_key, "
    "       s.architecture_entity_id AS source_entity_id, "
    "       properties(s) AS source_props, "
    "       r.projection_key AS rel_key, "
    "       properties(r) AS rel_props, "
    "       t.projection_key AS target_key, "
    "       t.architecture_entity_id AS target_entity_id, "
    "       properties(t) AS target_props "
    "ORDER BY r.projection_key ASC"
)

_ONE_HOP_INCOMING_QUERY = (
    "MATCH (s:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "})-[r:ARCH_RELATIONSHIP { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}]->(t:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}) "
    "WHERE t.projection_key IN $frontier_keys "
    "  AND ($kinds IS NULL OR r.canonical_kind IN $kinds) "
    "RETURN s.projection_key AS source_key, "
    "       s.architecture_entity_id AS source_entity_id, "
    "       properties(s) AS source_props, "
    "       r.projection_key AS rel_key, "
    "       properties(r) AS rel_props, "
    "       t.projection_key AS target_key, "
    "       t.architecture_entity_id AS target_entity_id, "
    "       properties(t) AS target_props "
    "ORDER BY r.projection_key ASC"
)

_PATH_TEMPLATES: dict[int, str] = {
    1: (
        "MATCH (n0:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id, "
        "    architecture_entity_id: $src_id "
        "})-[r1:ARCH_RELATIONSHIP { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "}]->(n1:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id, "
        "    architecture_entity_id: $tgt_id "
        "}) "
        "WHERE ($kinds IS NULL OR r1.canonical_kind IN $kinds) "
        "RETURN 1 AS hop_count, "
        "       [properties(n0), properties(n1)] AS nodes, "
        "       [properties(r1)] AS edges, "
        "       [r1.projection_key] AS edge_keys "
        "ORDER BY r1.projection_key ASC "
        "LIMIT $limit"
    ),
    2: (
        "MATCH (n0:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id, "
        "    architecture_entity_id: $src_id "
        "})-[r1:ARCH_RELATIONSHIP { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "}]->(n1:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "})-[r2:ARCH_RELATIONSHIP { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "}]->(n2:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id, "
        "    architecture_entity_id: $tgt_id "
        "}) "
        "WHERE n0 <> n1 AND n1 <> n2 AND n0 <> n2 "
        "  AND ($kinds IS NULL OR ( "
        "      r1.canonical_kind IN $kinds AND r2.canonical_kind IN $kinds "
        "  )) "
        "RETURN 2 AS hop_count, "
        "       [properties(n0), properties(n1), properties(n2)] AS nodes, "
        "       [properties(r1), properties(r2)] AS edges, "
        "       [r1.projection_key, r2.projection_key] AS edge_keys "
        "ORDER BY r1.projection_key ASC, r2.projection_key ASC "
        "LIMIT $limit"
    ),
    3: (
        "MATCH (n0:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id, "
        "    architecture_entity_id: $src_id "
        "})-[r1:ARCH_RELATIONSHIP { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "}]->(n1:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "})-[r2:ARCH_RELATIONSHIP { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "}]->(n2:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "})-[r3:ARCH_RELATIONSHIP { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "}]->(n3:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id, "
        "    architecture_entity_id: $tgt_id "
        "}) "
        "WHERE n0 <> n1 AND n1 <> n2 AND n2 <> n3 "
        "  AND n0 <> n2 AND n0 <> n3 AND n1 <> n3 "
        "  AND ($kinds IS NULL OR ( "
        "      r1.canonical_kind IN $kinds "
        "      AND r2.canonical_kind IN $kinds "
        "      AND r3.canonical_kind IN $kinds "
        "  )) "
        "RETURN 3 AS hop_count, "
        "       [properties(n0), properties(n1), "
        "        properties(n2), properties(n3)] AS nodes, "
        "       [properties(r1), properties(r2), properties(r3)] AS edges, "
        "       [r1.projection_key, r2.projection_key, r3.projection_key] AS edge_keys "
        "ORDER BY r1.projection_key ASC, r2.projection_key ASC, r3.projection_key ASC "
        "LIMIT $limit"
    ),
    4: (
        "MATCH (n0:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id, "
        "    architecture_entity_id: $src_id "
        "})-[r1:ARCH_RELATIONSHIP { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "}]->(n1:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "})-[r2:ARCH_RELATIONSHIP { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "}]->(n2:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "})-[r3:ARCH_RELATIONSHIP { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "}]->(n3:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "})-[r4:ARCH_RELATIONSHIP { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "}]->(n4:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id, "
        "    architecture_entity_id: $tgt_id "
        "}) "
        "WHERE n0 <> n1 AND n1 <> n2 AND n2 <> n3 AND n3 <> n4 "
        "  AND n0 <> n2 AND n0 <> n3 AND n0 <> n4 "
        "  AND n1 <> n3 AND n1 <> n4 AND n2 <> n4 "
        "  AND ($kinds IS NULL OR ( "
        "      r1.canonical_kind IN $kinds "
        "      AND r2.canonical_kind IN $kinds "
        "      AND r3.canonical_kind IN $kinds "
        "      AND r4.canonical_kind IN $kinds "
        "  )) "
        "RETURN 4 AS hop_count, "
        "       [properties(n0), properties(n1), properties(n2), "
        "        properties(n3), properties(n4)] AS nodes, "
        "       [properties(r1), properties(r2), "
        "        properties(r3), properties(r4)] AS edges, "
        "       [r1.projection_key, r2.projection_key, "
        "        r3.projection_key, r4.projection_key] AS edge_keys "
        "ORDER BY r1.projection_key ASC, r2.projection_key ASC, "
        "         r3.projection_key ASC, r4.projection_key ASC "
        "LIMIT $limit"
    ),
    5: (
        "MATCH (n0:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id, "
        "    architecture_entity_id: $src_id "
        "})-[r1:ARCH_RELATIONSHIP { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "}]->(n1:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "})-[r2:ARCH_RELATIONSHIP { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "}]->(n2:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "})-[r3:ARCH_RELATIONSHIP { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "}]->(n3:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "})-[r4:ARCH_RELATIONSHIP { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "}]->(n4:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "})-[r5:ARCH_RELATIONSHIP { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id "
        "}]->(n5:ArchitectureEntity { "
        "    project_id: $project_id, "
        "    architecture_version_id: $architecture_version_id, "
        "    generation_id: $generation_id, "
        "    architecture_entity_id: $tgt_id "
        "}) "
        "WHERE n0 <> n1 AND n1 <> n2 AND n2 <> n3 AND n3 <> n4 AND n4 <> n5 "
        "  AND n0 <> n2 AND n0 <> n3 AND n0 <> n4 AND n0 <> n5 "
        "  AND n1 <> n3 AND n1 <> n4 AND n1 <> n5 "
        "  AND n2 <> n4 AND n2 <> n5 AND n3 <> n5 "
        "  AND ($kinds IS NULL OR ( "
        "      r1.canonical_kind IN $kinds "
        "      AND r2.canonical_kind IN $kinds "
        "      AND r3.canonical_kind IN $kinds "
        "      AND r4.canonical_kind IN $kinds "
        "      AND r5.canonical_kind IN $kinds "
        "  )) "
        "RETURN 5 AS hop_count, "
        "       [properties(n0), properties(n1), properties(n2), "
        "        properties(n3), properties(n4), properties(n5)] AS nodes, "
        "       [properties(r1), properties(r2), properties(r3), "
        "        properties(r4), properties(r5)] AS edges, "
        "       [r1.projection_key, r2.projection_key, r3.projection_key, "
        "        r4.projection_key, r5.projection_key] AS edge_keys "
        "ORDER BY r1.projection_key ASC, r2.projection_key ASC, "
        "         r3.projection_key ASC, r4.projection_key ASC, "
        "         r5.projection_key ASC "
        "LIMIT $limit"
    ),
}


class Neo4jGraphQueryRepository:
    """Read-only Neo4j query repository executing fixed Cypher templates."""

    def __init__(
        self,
        driver: Driver,
        *,
        database: str = "neo4j",
    ) -> None:
        self._driver = driver
        self._database = database

    def _scope_params(self, scope: GraphReadScope) -> dict[str, Any]:
        return {
            "project_id": str(scope.project_id).lower(),
            "architecture_version_id": str(scope.architecture_version_id).lower(),
            "generation_id": str(scope.generation_id).lower(),
        }

    @contextmanager
    def _bounded_transaction(
        self, timeout_seconds: float
    ) -> Iterator[tuple[Any, float]]:
        """Open a transaction that is cancelled when its remaining budget expires.

        Neo4j's transaction timeout constrains server execution, while ``cancel``
        also interrupts connection acquisition and client-side result consumption.
        Callers receive the absolute monotonic deadline so mapping loops can enforce
        the same budget.
        """
        deadline = time.monotonic() + timeout_seconds
        expired = threading.Event()
        session = self._driver.session(database=self._database)

        def cancel_session() -> None:
            expired.set()
            try:
                session.cancel()
            except Exception:
                # The owning request observes ``expired`` and returns the typed
                # timeout; cancellation is best-effort if the driver already
                # closed the session concurrently.
                pass

        timer = threading.Timer(timeout_seconds, cancel_session)
        timer.daemon = True
        timer.start()
        try:
            with session:
                with session.begin_transaction(timeout=timeout_seconds) as tx:
                    yield tx, deadline
            if expired.is_set() or time.monotonic() >= deadline:
                raise GraphQueryTimeoutError(
                    "Graph query operation exceeded total deadline"
                )
        except Exception as exc:
            if expired.is_set() or time.monotonic() >= deadline:
                raise GraphQueryTimeoutError(
                    "Graph query operation exceeded total deadline"
                ) from exc
            raise
        finally:
            timer.cancel()

    @staticmethod
    def _check_deadline(deadline: float) -> None:
        if time.monotonic() >= deadline:
            raise GraphQueryTimeoutError(
                "Graph query operation exceeded total deadline"
            )

    def _handle_neo4j_error(self, err: Exception) -> None:
        if isinstance(err, (TransientError, ClientError)):
            code = getattr(err, "code", "")
            msg = str(err).lower()
            if "transactiontimedout" in code.lower() or "timed out" in msg:
                raise GraphQueryTimeoutError(
                    "Query execution timed out in graph storage"
                )
        if isinstance(err, (DriverError, Neo4jError)):
            raise GraphUnavailableError(
                f"Graph query storage error: {type(err).__name__}"
            )
        raise err

    def verify_manifest_ready(
        self,
        scope: GraphReadScope,
        *,
        timeout_seconds: float,
    ) -> bool:
        params = self._scope_params(scope)
        try:
            with self._bounded_transaction(timeout_seconds) as (tx, deadline):
                result = tx.run(_MANIFEST_PREFLIGHT_QUERY, **params)
                row = result.single()
                self._check_deadline(deadline)
                if row is None:
                    raise GraphProjectionNotReadyError(
                        "Projection manifest not found for generation "
                        f"{scope.generation_id}"
                    )
                state = row["state"]
                if state != MANIFEST_STATE_READY:
                    raise GraphProjectionNotReadyError(
                        f"Projection manifest for generation {scope.generation_id} "
                        f"is in state '{state}', not ready for queries"
                    )
                schema_ver = row["graph_schema_version"]
                if schema_ver != scope.graph_schema_version:
                    raise GraphSchemaIncompatibleError(
                        f"Graph schema version mismatch: stored '{schema_ver}', "
                        f"expected '{scope.graph_schema_version}'"
                    )
                projector_ver = row["projector_version"]
                if projector_ver != scope.projector_version:
                    raise GraphSchemaIncompatibleError(
                        "Graph projector version mismatch: stored "
                        f"'{projector_ver}', expected '{scope.projector_version}'"
                    )
                return True
        except GraphProjectionNotReadyError, GraphSchemaIncompatibleError:
            raise
        except Exception as exc:
            self._handle_neo4j_error(exc)
            return False

    def get_node_detail(
        self,
        scope: GraphReadScope,
        request: NodeDetailRequest,
        *,
        timeout_seconds: float,
    ) -> GraphNode | None:
        params = self._scope_params(scope)
        params["entity_id"] = str(request.entity_id).lower()

        try:
            with self._bounded_transaction(timeout_seconds) as (tx, deadline):
                result = tx.run(_NODE_DETAIL_QUERY, **params)
                row = result.single()
                self._check_deadline(deadline)
                if row is None:
                    return None
                return _map_node(row["properties"])
        except Exception as exc:
            self._handle_neo4j_error(exc)
            return None

    def query_window(
        self,
        scope: GraphReadScope,
        request: GraphWindowRequest,
        position: dict[str, Any] | None,
        *,
        timeout_seconds: float,
    ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
        params = self._scope_params(scope)
        pos = dict(position or {})

        window_start = pos.get("window_start")
        window_end = pos.get("window_end")
        next_node_cursor = pos.get("next_node_cursor")
        edge_cursor = pos.get("edge_cursor")
        node_cursor = pos.get("node_cursor")

        try:
            with self._bounded_transaction(timeout_seconds) as (tx, deadline):
                nodes: list[GraphNode] = []
                node_keys: list[str] = []
                has_more_nodes = next_node_cursor is not None
                page_node_limit = min(request.node_limit, request.page_size)

                if window_end is not None:
                    # Recreate the immutable node window from compact key bounds.
                    result = tx.run(
                        _WINDOW_BOUNDED_NODES_QUERY,
                        **params,
                        window_start=window_start,
                        window_end=window_end,
                    )
                    for row in result:
                        self._check_deadline(deadline)
                        nodes.append(_map_node(row["properties"]))
                        node_keys.append(row["projection_key"])
                else:
                    result = tx.run(
                        _WINDOW_NODES_QUERY,
                        **params,
                        cursor=node_cursor,
                        limit=page_node_limit + 1,
                    )
                    for row in result:
                        self._check_deadline(deadline)
                        if len(nodes) < page_node_limit:
                            nodes.append(_map_node(row["properties"]))
                            node_keys.append(row["projection_key"])
                        else:
                            has_more_nodes = True
                    window_start = node_cursor
                    window_end = node_keys[-1] if node_keys else None
                    next_node_cursor = window_end if has_more_nodes else None

                edges: list[GraphEdge] = []
                has_more_edges = False
                last_edge_key: str | None = None
                if node_keys:
                    kinds_param = (
                        [k.value for k in request.canonical_kinds]
                        if request.canonical_kinds
                        else None
                    )
                    result = tx.run(
                        _WINDOW_INDUCED_EDGES_QUERY,
                        **params,
                        node_keys=node_keys,
                        kinds=kinds_param,
                        cursor=edge_cursor,
                        limit=request.edge_limit + 1,
                    )
                    for row in result:
                        self._check_deadline(deadline)
                        if len(edges) < request.edge_limit:
                            src_id = UUID(str(row["source_entity_id"]))
                            tgt_id = UUID(str(row["target_entity_id"]))
                            edges.append(_map_edge(row["properties"], src_id, tgt_id))
                            last_edge_key = row["projection_key"]
                        else:
                            has_more_edges = True

                next_pos: dict[str, Any] | None = None
                if has_more_edges and last_edge_key is not None:
                    next_pos = {
                        "window_start": window_start,
                        "window_end": window_end,
                        "next_node_cursor": next_node_cursor,
                        "edge_cursor": last_edge_key,
                    }
                elif has_more_nodes and next_node_cursor is not None:
                    next_pos = {"node_cursor": next_node_cursor}

                truncated = next_pos is not None
                subgraph = GraphSubgraph(
                    scope=scope,
                    nodes=tuple(nodes),
                    edges=tuple(edges),
                    total_manifest_nodes=scope.counts.entities,
                    total_manifest_edges=scope.counts.relationships,
                    loaded_nodes=len(nodes),
                    loaded_edges=len(edges),
                    truncated=truncated,
                    next_cursor=None,
                )
                return subgraph, next_pos
        except Exception as exc:
            self._handle_neo4j_error(exc)
            raise

    def _execute_traversal(
        self,
        scope: GraphReadScope,
        *,
        anchor_id: UUID,
        direction: str,  # "outgoing", "incoming", "both"
        depth: int,
        node_limit: int,
        edge_limit: int,
        kinds: Sequence[str] | None,
        position: dict[str, Any] | None,
        timeout_seconds: float,
    ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
        params = self._scope_params(scope)
        pos = dict(position or {})
        cursor_depth = pos.get("depth")
        cursor_last_rel = pos.get("last_rel_key")

        try:
            with self._bounded_transaction(timeout_seconds) as (tx, deadline):
                # 1. Fetch anchor node
                anchor_row = tx.run(
                    "MATCH (n:ArchitectureEntity { "
                    "    project_id: $project_id, "
                    "    architecture_version_id: $architecture_version_id, "
                    "    generation_id: $generation_id, "
                    "    architecture_entity_id: $entity_id "
                    "}) "
                    "RETURN n.projection_key AS projection_key, "
                    "       properties(n) AS properties",
                    **params,
                    entity_id=str(anchor_id).lower(),
                ).single()
                self._check_deadline(deadline)

                if anchor_row is None:
                    raise GraphNodeNotFoundError(
                        f"Anchor node {anchor_id} not found in scope"
                    )

                anchor_key = anchor_row["projection_key"]
                anchor_node = _map_node(anchor_row["properties"])

                collected_nodes: dict[str, GraphNode] = (
                    {} if cursor_depth is not None else {anchor_key: anchor_node}
                )
                collected_edges: dict[str, GraphEdge] = {}
                frontier_keys = {anchor_key}
                visited_node_keys: set[str] = {anchor_key}
                visited_rel_keys: set[str] = set()

                truncated = False
                next_pos: dict[str, Any] | None = None
                last_emitted_depth: int | None = None
                last_emitted_rel: str | None = None

                # 2. Hop by hop BFS traversal
                for current_depth in range(1, depth + 1):
                    if not frontier_keys:
                        break
                    if (
                        len(collected_nodes) >= node_limit
                        and len(collected_edges) >= edge_limit
                    ):
                        truncated = True
                        break

                    next_frontier_keys: set[str] = set()
                    candidates: list[dict[str, Any]] = []

                    # Query outgoing edges if requested
                    if direction in ("outgoing", "both"):
                        out_rows = tx.run(
                            _ONE_HOP_OUTGOING_QUERY,
                            **params,
                            frontier_keys=list(frontier_keys),
                            kinds=list(kinds) if kinds else None,
                        )
                        for row in out_rows:
                            self._check_deadline(deadline)
                            candidates.append(
                                {
                                    "source_key": row["source_key"],
                                    "target_key": row["target_key"],
                                    "neighbor_key": row["target_key"],
                                    "source_entity_id": UUID(
                                        str(row["source_entity_id"])
                                    ),
                                    "target_entity_id": UUID(
                                        str(row["target_entity_id"])
                                    ),
                                    "source_props": row["source_props"],
                                    "target_props": row["target_props"],
                                    "rel_key": row["rel_key"],
                                    "rel_props": row["rel_props"],
                                }
                            )

                    # Query incoming edges if requested
                    if direction in ("incoming", "both"):
                        in_rows = tx.run(
                            _ONE_HOP_INCOMING_QUERY,
                            **params,
                            frontier_keys=list(frontier_keys),
                            kinds=list(kinds) if kinds else None,
                        )
                        for row in in_rows:
                            self._check_deadline(deadline)
                            candidates.append(
                                {
                                    "source_key": row["source_key"],
                                    "target_key": row["target_key"],
                                    "neighbor_key": row["source_key"],
                                    "source_entity_id": UUID(
                                        str(row["source_entity_id"])
                                    ),
                                    "target_entity_id": UUID(
                                        str(row["target_entity_id"])
                                    ),
                                    "source_props": row["source_props"],
                                    "target_props": row["target_props"],
                                    "rel_key": row["rel_key"],
                                    "rel_props": row["rel_props"],
                                }
                            )

                    # Sort candidates deterministically by rel_key and neighbor_key
                    candidates.sort(key=lambda c: (c["rel_key"], c["neighbor_key"]))

                    for cand in candidates:
                        self._check_deadline(deadline)
                        rel_key = cand["rel_key"]
                        neighbor_key = cand["neighbor_key"]

                        if rel_key in visited_rel_keys:
                            continue
                        visited_rel_keys.add(rel_key)

                        # Skip if behind cursor position
                        if cursor_depth is not None and cursor_last_rel:
                            if current_depth < cursor_depth or (
                                current_depth == cursor_depth
                                and rel_key <= cursor_last_rel
                            ):
                                if neighbor_key not in visited_node_keys:
                                    visited_node_keys.add(neighbor_key)
                                    next_frontier_keys.add(neighbor_key)
                                continue

                        # Cap enforcement
                        if len(collected_edges) >= edge_limit:
                            truncated = True
                            break

                        missing_keys = [
                            key
                            for key in (cand["source_key"], cand["target_key"])
                            if key not in collected_nodes
                        ]
                        if len(collected_nodes) + len(set(missing_keys)) > node_limit:
                            truncated = True
                            break

                        if cand["source_key"] not in collected_nodes:
                            collected_nodes[cand["source_key"]] = _map_node(
                                cand["source_props"]
                            )
                        if cand["target_key"] not in collected_nodes:
                            collected_nodes[cand["target_key"]] = _map_node(
                                cand["target_props"]
                            )

                        edge = _map_edge(
                            cand["rel_props"],
                            cand["source_entity_id"],
                            cand["target_entity_id"],
                        )
                        collected_edges[rel_key] = edge
                        last_emitted_depth = current_depth
                        last_emitted_rel = rel_key

                        if neighbor_key not in visited_node_keys:
                            visited_node_keys.add(neighbor_key)
                            next_frontier_keys.add(neighbor_key)

                    if truncated:
                        if last_emitted_depth is not None and last_emitted_rel:
                            next_pos = {
                                "depth": last_emitted_depth,
                                "last_rel_key": last_emitted_rel,
                            }
                        elif cursor_depth is not None and cursor_last_rel:
                            next_pos = {
                                "depth": cursor_depth,
                                "last_rel_key": cursor_last_rel,
                            }
                        break

                    frontier_keys = next_frontier_keys

                subgraph = GraphSubgraph(
                    scope=scope,
                    nodes=tuple(collected_nodes.values()),
                    edges=tuple(collected_edges.values()),
                    total_manifest_nodes=scope.counts.entities,
                    total_manifest_edges=scope.counts.relationships,
                    loaded_nodes=len(collected_nodes),
                    loaded_edges=len(collected_edges),
                    truncated=truncated,
                    next_cursor=None,
                )
                return subgraph, next_pos
        except GraphNodeNotFoundError:
            raise
        except Exception as exc:
            self._handle_neo4j_error(exc)
            raise

    def query_neighborhood(
        self,
        scope: GraphReadScope,
        request: NeighborhoodRequest,
        position: dict[str, Any] | None,
        *,
        timeout_seconds: float,
    ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
        kinds = (
            [k.value for k in request.relationship_kinds]
            if request.relationship_kinds
            else [
                k.value
                for k in GraphRelationshipKind
                if k != GraphRelationshipKind.CONTAINS
            ]
        )
        return self._execute_traversal(
            scope,
            anchor_id=request.entity_id,
            direction=request.direction.value,
            depth=request.depth,
            node_limit=request.node_limit,
            edge_limit=request.edge_limit,
            kinds=kinds,
            position=position,
            timeout_seconds=timeout_seconds,
        )

    def query_dependencies(
        self,
        scope: GraphReadScope,
        request: DependenciesRequest,
        position: dict[str, Any] | None,
        *,
        timeout_seconds: float,
    ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
        kinds = (
            [k.value for k in request.relationship_kinds]
            if request.relationship_kinds
            else [
                k.value
                for k in GraphRelationshipKind
                if k != GraphRelationshipKind.CONTAINS
            ]
        )
        return self._execute_traversal(
            scope,
            anchor_id=request.entity_id,
            direction="outgoing",
            depth=request.depth,
            node_limit=request.node_limit,
            edge_limit=request.edge_limit,
            kinds=kinds,
            position=position,
            timeout_seconds=timeout_seconds,
        )

    def query_dependents(
        self,
        scope: GraphReadScope,
        request: DependentsRequest,
        position: dict[str, Any] | None,
        *,
        timeout_seconds: float,
    ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
        kinds = (
            [k.value for k in request.relationship_kinds]
            if request.relationship_kinds
            else [
                k.value
                for k in GraphRelationshipKind
                if k != GraphRelationshipKind.CONTAINS
            ]
        )
        return self._execute_traversal(
            scope,
            anchor_id=request.entity_id,
            direction="incoming",
            depth=request.depth,
            node_limit=request.node_limit,
            edge_limit=request.edge_limit,
            kinds=kinds,
            position=position,
            timeout_seconds=timeout_seconds,
        )

    def query_containment(
        self,
        scope: GraphReadScope,
        request: ContainmentRequest,
        position: dict[str, Any] | None,
        *,
        timeout_seconds: float,
    ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
        # Containment uses ONLY 'contains'
        # children -> outgoing, parents -> incoming, both -> both
        dir_map = {
            ContainmentDirection.CHILDREN: "outgoing",
            ContainmentDirection.PARENTS: "incoming",
            ContainmentDirection.BOTH: "both",
        }
        direction = dir_map[request.direction]
        return self._execute_traversal(
            scope,
            anchor_id=request.entity_id,
            direction=direction,
            depth=request.depth,
            node_limit=request.node_limit,
            edge_limit=request.edge_limit,
            kinds=[GraphRelationshipKind.CONTAINS.value],
            position=position,
            timeout_seconds=timeout_seconds,
        )

    def query_bounded_paths(
        self,
        scope: GraphReadScope,
        request: BoundedPathsRequest,
        *,
        timeout_seconds: float,
    ) -> GraphPathResult:
        params = self._scope_params(scope)
        src_id = str(request.source_entity_id).lower()
        tgt_id = str(request.target_entity_id).lower()

        try:
            with self._bounded_transaction(timeout_seconds) as (tx, deadline):
                # Edge case: source == target
                if request.source_entity_id == request.target_entity_id:
                    node_row = tx.run(
                        "MATCH (n:ArchitectureEntity { "
                        "    project_id: $project_id, "
                        "    architecture_version_id: $architecture_version_id, "
                        "    generation_id: $generation_id, "
                        "    architecture_entity_id: $src_id "
                        "}) "
                        "RETURN properties(n) AS properties",
                        **params,
                        src_id=src_id,
                    ).single()
                    self._check_deadline(deadline)

                    if node_row is None:
                        raise GraphNodeNotFoundError(
                            f"Source node {request.source_entity_id} "
                            "not found in scope"
                        )
                    single_node = _map_node(node_row["properties"])
                    zero_path = GraphPath(
                        nodes=(single_node,),
                        edges=(),
                        hop_count=0,
                    )
                    return GraphPathResult(
                        scope=scope,
                        paths=(zero_path,),
                        total_paths_found=1,
                        truncated=False,
                    )

                # Verify source and target nodes exist in scope
                src_exists = tx.run(
                    "MATCH (n:ArchitectureEntity { "
                    "    project_id: $project_id, "
                    "    architecture_version_id: $architecture_version_id, "
                    "    generation_id: $generation_id, "
                    "    architecture_entity_id: $src_id "
                    "}) RETURN count(n) AS c",
                    **params,
                    src_id=src_id,
                ).single()
                self._check_deadline(deadline)
                if not src_exists or src_exists["c"] == 0:
                    raise GraphNodeNotFoundError(
                        f"Source node {request.source_entity_id} not found in scope"
                    )

                tgt_exists = tx.run(
                    "MATCH (n:ArchitectureEntity { "
                    "    project_id: $project_id, "
                    "    architecture_version_id: $architecture_version_id, "
                    "    generation_id: $generation_id, "
                    "    architecture_entity_id: $tgt_id "
                    "}) RETURN count(n) AS c",
                    **params,
                    tgt_id=tgt_id,
                ).single()
                self._check_deadline(deadline)
                if not tgt_exists or tgt_exists["c"] == 0:
                    raise GraphNodeNotFoundError(
                        f"Target node {request.target_entity_id} not found in scope"
                    )

                kinds_list = (
                    [k.value for k in request.relationship_kinds]
                    if request.relationship_kinds
                    else [
                        k.value
                        for k in GraphRelationshipKind
                        if k != GraphRelationshipKind.CONTAINS
                    ]
                )

                all_paths: list[GraphPath] = []
                truncated = False

                # Run templates for each hop count 1..max_depth
                for h in range(1, request.max_depth + 1):
                    if h not in _PATH_TEMPLATES:
                        continue
                    rem_limit = request.path_limit - len(all_paths)
                    if rem_limit <= 0:
                        truncated = True
                        break

                    template = _PATH_TEMPLATES[h]
                    rows = tx.run(
                        template,
                        **params,
                        src_id=src_id,
                        tgt_id=tgt_id,
                        kinds=kinds_list,
                        limit=rem_limit + 1,
                    )
                    for row in rows:
                        self._check_deadline(deadline)
                        if len(all_paths) < request.path_limit:
                            path_nodes = tuple(_map_node(p) for p in row["nodes"])
                            path_edges_list: list[GraphEdge] = []
                            for idx, e_prop in enumerate(row["edges"]):
                                s_id = path_nodes[idx].architecture_entity_id
                                t_id = path_nodes[idx + 1].architecture_entity_id
                                path_edges_list.append(_map_edge(e_prop, s_id, t_id))
                            all_paths.append(
                                GraphPath(
                                    nodes=path_nodes,
                                    edges=tuple(path_edges_list),
                                    hop_count=row["hop_count"],
                                )
                            )
                        else:
                            truncated = True
                            break

                return GraphPathResult(
                    scope=scope,
                    paths=tuple(all_paths),
                    total_paths_found=len(all_paths),
                    truncated=truncated,
                )
        except GraphNodeNotFoundError:
            raise
        except Exception as exc:
            self._handle_neo4j_error(exc)
            raise


# --- Test Fakes ---


class FakeGraphGenerationReader:
    """In-memory test double for GraphGenerationReader."""

    def __init__(
        self, scopes: dict[tuple[UUID, UUID], GraphReadScope] | None = None
    ) -> None:
        self._scopes: dict[tuple[UUID, UUID], GraphReadScope] = dict(scopes or {})
        self._unready_states: dict[tuple[UUID, UUID], str] = {}

    def set_scope(self, scope: GraphReadScope) -> None:
        self._scopes[(scope.project_id, scope.architecture_version_id)] = scope
        self._unready_states.pop(
            (scope.project_id, scope.architecture_version_id), None
        )

    def set_unready(
        self, project_id: UUID, architecture_version_id: UUID, state: str
    ) -> None:
        self._unready_states[(project_id, architecture_version_id)] = state
        self._scopes.pop((project_id, architecture_version_id), None)

    def resolve_active_generation(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        *,
        timeout_seconds: float | None = None,
    ) -> GraphReadScope:
        key = (project_id, architecture_version_id)
        if key in self._unready_states:
            raise GraphProjectionNotReadyError(
                f"Projection is in state '{self._unready_states[key]}'"
            )
        if key not in self._scopes:
            raise GraphProjectionNotFoundError(
                f"Projection not found for version {architecture_version_id}"
            )
        return self._scopes[key]

    def verify_generation_still_active(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        *,
        timeout_seconds: float | None = None,
    ) -> bool:
        key = (project_id, architecture_version_id)
        scope = self._scopes.get(key)
        if scope is None:
            return False
        return scope.generation_id == generation_id


class FakeGraphQueryRepository:
    """In-memory test double for GraphQueryRepository."""

    def __init__(self) -> None:
        self.manifest_ready = True
        self.nodes: dict[UUID, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        self.simulated_timeout = False

    def verify_manifest_ready(
        self,
        scope: GraphReadScope,
        *,
        timeout_seconds: float,
    ) -> bool:
        if self.simulated_timeout:
            raise GraphQueryTimeoutError("Simulated timeout in verify_manifest_ready")
        if not self.manifest_ready:
            raise GraphProjectionNotReadyError("Manifest not ready in fake")
        return True

    def get_node_detail(
        self,
        scope: GraphReadScope,
        request: NodeDetailRequest,
        *,
        timeout_seconds: float,
    ) -> GraphNode | None:
        if self.simulated_timeout:
            raise GraphQueryTimeoutError("Simulated timeout in get_node_detail")
        return self.nodes.get(request.entity_id)

    def query_window(
        self,
        scope: GraphReadScope,
        request: GraphWindowRequest,
        position: dict[str, Any] | None,
        *,
        timeout_seconds: float,
    ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
        if self.simulated_timeout:
            raise GraphQueryTimeoutError("Simulated timeout in query_window")
        nodes_list = list(self.nodes.values())[: request.node_limit]
        edges_list = self.edges[: request.edge_limit]
        subgraph = GraphSubgraph(
            scope=scope,
            nodes=tuple(nodes_list),
            edges=tuple(edges_list),
            total_manifest_nodes=len(self.nodes),
            total_manifest_edges=len(self.edges),
            loaded_nodes=len(nodes_list),
            loaded_edges=len(edges_list),
            truncated=len(self.nodes) > request.node_limit,
            next_cursor=None,
        )
        next_pos = {"node_cursor": "fake_next"} if subgraph.truncated else None
        return subgraph, next_pos

    def query_neighborhood(
        self,
        scope: GraphReadScope,
        request: NeighborhoodRequest,
        position: dict[str, Any] | None,
        *,
        timeout_seconds: float,
    ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
        if self.simulated_timeout:
            raise GraphQueryTimeoutError("Simulated timeout in query_neighborhood")
        anchor = self.nodes.get(request.entity_id)
        if anchor is None:
            raise GraphNodeNotFoundError(f"Anchor {request.entity_id} not found")
        subgraph = GraphSubgraph(
            scope=scope,
            nodes=(anchor,),
            edges=(),
            total_manifest_nodes=len(self.nodes),
            total_manifest_edges=len(self.edges),
            loaded_nodes=1,
            loaded_edges=0,
            truncated=False,
            next_cursor=None,
        )
        return subgraph, None

    def query_dependencies(
        self,
        scope: GraphReadScope,
        request: DependenciesRequest,
        position: dict[str, Any] | None,
        *,
        timeout_seconds: float,
    ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
        if self.simulated_timeout:
            raise GraphQueryTimeoutError("Simulated timeout in query_dependencies")
        anchor = self.nodes.get(request.entity_id)
        if anchor is None:
            raise GraphNodeNotFoundError(f"Anchor {request.entity_id} not found")
        subgraph = GraphSubgraph(
            scope=scope,
            nodes=(anchor,),
            edges=(),
            total_manifest_nodes=len(self.nodes),
            total_manifest_edges=len(self.edges),
            loaded_nodes=1,
            loaded_edges=0,
            truncated=False,
            next_cursor=None,
        )
        return subgraph, None

    def query_dependents(
        self,
        scope: GraphReadScope,
        request: DependentsRequest,
        position: dict[str, Any] | None,
        *,
        timeout_seconds: float,
    ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
        if self.simulated_timeout:
            raise GraphQueryTimeoutError("Simulated timeout in query_dependents")
        anchor = self.nodes.get(request.entity_id)
        if anchor is None:
            raise GraphNodeNotFoundError(f"Anchor {request.entity_id} not found")
        subgraph = GraphSubgraph(
            scope=scope,
            nodes=(anchor,),
            edges=(),
            total_manifest_nodes=len(self.nodes),
            total_manifest_edges=len(self.edges),
            loaded_nodes=1,
            loaded_edges=0,
            truncated=False,
            next_cursor=None,
        )
        return subgraph, None

    def query_containment(
        self,
        scope: GraphReadScope,
        request: ContainmentRequest,
        position: dict[str, Any] | None,
        *,
        timeout_seconds: float,
    ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
        if self.simulated_timeout:
            raise GraphQueryTimeoutError("Simulated timeout in query_containment")
        anchor = self.nodes.get(request.entity_id)
        if anchor is None:
            raise GraphNodeNotFoundError(f"Anchor {request.entity_id} not found")
        subgraph = GraphSubgraph(
            scope=scope,
            nodes=(anchor,),
            edges=(),
            total_manifest_nodes=len(self.nodes),
            total_manifest_edges=len(self.edges),
            loaded_nodes=1,
            loaded_edges=0,
            truncated=False,
            next_cursor=None,
        )
        return subgraph, None

    def query_bounded_paths(
        self,
        scope: GraphReadScope,
        request: BoundedPathsRequest,
        *,
        timeout_seconds: float,
    ) -> GraphPathResult:
        if self.simulated_timeout:
            raise GraphQueryTimeoutError("Simulated timeout in query_bounded_paths")
        if (
            request.source_entity_id not in self.nodes
            or request.target_entity_id not in self.nodes
        ):
            raise GraphNodeNotFoundError("Source or target node not found in fake")
        if request.source_entity_id == request.target_entity_id:
            node = self.nodes[request.source_entity_id]
            return GraphPathResult(
                scope=scope,
                paths=(GraphPath(nodes=(node,), edges=(), hop_count=0),),
                total_paths_found=1,
                truncated=False,
            )
        return GraphPathResult(
            scope=scope,
            paths=(),
            total_paths_found=0,
            truncated=False,
        )


__all__ = [
    "FakeGraphGenerationReader",
    "FakeGraphQueryRepository",
    "GraphGenerationReader",
    "GraphQueryRepository",
    "Neo4jGraphQueryRepository",
    "SqlAlchemyGraphGenerationReader",
]
