"""Application service orchestrating P4-Q1 graph query execution.

This module enforces:
1. Single monotonic operation deadline across all phases.
2. PostgreSQL active generation double-read consistency.
3. Keyset continuation cursor validation and generation binding.
4. Neo4j manifest preflight and controlled query execution.
5. Structured observer logging without sensitive data leakage.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Protocol
from uuid import UUID

from backend.platform.config import Settings
from backend.platform.graph.cursor import (
    compute_query_fingerprint,
    encode_cursor,
    validate_cursor,
)
from backend.platform.graph.query_contracts import (
    BoundedPathsRequest,
    ContainmentRequest,
    DependenciesRequest,
    DependentsRequest,
    GraphGenerationChangedError,
    GraphNode,
    GraphNodeNotFoundError,
    GraphPathResult,
    GraphQueryError,
    GraphQueryTimeoutError,
    GraphReadScope,
    GraphSubgraph,
    GraphWindowRequest,
    NeighborhoodRequest,
    NodeDetailRequest,
)
from backend.platform.graph.query_repository import (
    GraphGenerationReader,
    GraphQueryRepository,
)

logger = logging.getLogger("stacksense.graph.query")


class GraphQueryObserver(Protocol):
    """Observer hook for telemetry, metrics, and structured query logging."""

    def on_query_start(
        self,
        operation: str,
        project_id: UUID,
        architecture_version_id: UUID,
    ) -> None: ...

    def on_query_success(
        self,
        operation: str,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        duration_ms: float,
        nodes_count: int,
        edges_count: int,
        truncated: bool,
    ) -> None: ...

    def on_query_error(
        self,
        operation: str,
        project_id: UUID,
        architecture_version_id: UUID,
        error_code: str,
        duration_ms: float,
    ) -> None: ...


class DefaultLoggingGraphQueryObserver:
    """Safe structured logger that never exposes Cypher, credentials, or properties."""

    def on_query_start(
        self,
        operation: str,
        project_id: UUID,
        architecture_version_id: UUID,
    ) -> None:
        logger.info(
            "graph_query_start operation=%s project_id=%s architecture_version_id=%s",
            operation,
            project_id,
            architecture_version_id,
        )

    def on_query_success(
        self,
        operation: str,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        duration_ms: float,
        nodes_count: int,
        edges_count: int,
        truncated: bool,
    ) -> None:
        logger.info(
            "graph_query_success operation=%s project_id=%s architecture_version_id=%s "
            "generation_id=%s duration_ms=%.2f nodes=%d edges=%d truncated=%s",
            operation,
            project_id,
            architecture_version_id,
            generation_id,
            duration_ms,
            nodes_count,
            edges_count,
            truncated,
        )

    def on_query_error(
        self,
        operation: str,
        project_id: UUID,
        architecture_version_id: UUID,
        error_code: str,
        duration_ms: float,
    ) -> None:
        logger.warning(
            "graph_query_error operation=%s project_id=%s architecture_version_id=%s "
            "code=%s duration_ms=%.2f",
            operation,
            project_id,
            architecture_version_id,
            error_code,
            duration_ms,
        )


class GraphQueryService:
    """Application service for all P4-Q1 graph queries."""

    def __init__(
        self,
        *,
        settings: Settings,
        generation_reader: GraphGenerationReader,
        query_repository: GraphQueryRepository,
        cursor_secret_key: str | None = None,
        observer: GraphQueryObserver | None = None,
    ) -> None:
        self._settings = settings
        self._generation_reader = generation_reader
        self._query_repository = query_repository
        self._cursor_secret_key = (
            cursor_secret_key
            if cursor_secret_key is not None
            else settings.graph_query_cursor_secret_key.get_secret_value()
        )
        self._observer = observer or DefaultLoggingGraphQueryObserver()

    def _deadline_budget(self, requested_timeout: float) -> tuple[float, float]:
        """Return (deadline_timestamp, max_budget_seconds)."""
        max_allowed = self._settings.graph_query_max_timeout_seconds
        budget = min(requested_timeout, max_allowed)
        deadline = time.monotonic() + budget
        return deadline, budget

    def _check_remaining(self, deadline: float) -> float:
        """Return remaining seconds until deadline, or raise GraphQueryTimeoutError."""
        rem = deadline - time.monotonic()
        if rem <= 0:
            raise GraphQueryTimeoutError(
                "Graph query operation exceeded total deadline"
            )
        return rem

    def _verify_double_read(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        scope: GraphReadScope,
        deadline: float,
    ) -> None:
        """Re-read PostgreSQL pointer before returning result to prevent mixed
        generation reads.
        """
        rem = self._check_remaining(deadline)
        is_still_active = self._generation_reader.verify_generation_still_active(
            project_id=project_id,
            architecture_version_id=architecture_version_id,
            generation_id=scope.generation_id,
            timeout_seconds=rem,
        )
        if not is_still_active:
            raise GraphGenerationChangedError(
                "Active graph projection generation changed during query execution; "
                "please restart query"
            )

    # 1. Graph Window Overview
    def get_window(self, request: GraphWindowRequest) -> GraphSubgraph:
        operation = "window"
        start_time = time.monotonic()
        deadline, _ = self._deadline_budget(request.timeout_seconds)
        self._observer.on_query_start(
            operation, request.project_id, request.architecture_version_id
        )

        try:
            # 1. Resolve PostgreSQL generation
            scope = self._generation_reader.resolve_active_generation(
                request.project_id,
                request.architecture_version_id,
                timeout_seconds=self._check_remaining(deadline),
            )

            # 2. Validate cursor if provided
            position: dict[str, Any] | None = None
            fp = compute_query_fingerprint(
                {
                    "operation": operation,
                    "node_limit": request.node_limit,
                    "edge_limit": request.edge_limit,
                    "page_size": request.page_size,
                    "kinds": (
                        [k.value for k in request.canonical_kinds]
                        if request.canonical_kinds
                        else None
                    ),
                }
            )
            if request.cursor:
                cursor_payload = validate_cursor(
                    request.cursor,
                    secret_key=self._cursor_secret_key,
                    expected_scope=scope,
                    expected_operation=operation,
                    expected_fingerprint=fp,
                )
                position = cursor_payload.position

            # 3. Manifest preflight in Neo4j
            self._query_repository.verify_manifest_ready(
                scope, timeout_seconds=self._check_remaining(deadline)
            )

            # 4. Execute query
            subgraph, next_pos = self._query_repository.query_window(
                scope,
                request,
                position,
                timeout_seconds=self._check_remaining(deadline),
            )

            # 5. Keyset continuation cursor
            next_cursor: str | None = None
            if subgraph.truncated and next_pos is not None:
                next_cursor = encode_cursor(
                    scope=scope,
                    operation=operation,
                    fingerprint=fp,
                    position=next_pos,
                    secret_key=self._cursor_secret_key,
                    ttl_seconds=self._settings.graph_query_cursor_ttl_seconds,
                )

            final_subgraph = GraphSubgraph(
                scope=subgraph.scope,
                nodes=subgraph.nodes,
                edges=subgraph.edges,
                total_manifest_nodes=subgraph.total_manifest_nodes,
                total_manifest_edges=subgraph.total_manifest_edges,
                loaded_nodes=subgraph.loaded_nodes,
                loaded_edges=subgraph.loaded_edges,
                truncated=subgraph.truncated,
                next_cursor=next_cursor,
            )

            # 6. Final double-read verification
            self._verify_double_read(
                request.project_id,
                request.architecture_version_id,
                scope,
                deadline,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            self._observer.on_query_success(
                operation,
                request.project_id,
                request.architecture_version_id,
                scope.generation_id,
                duration_ms,
                final_subgraph.loaded_nodes,
                final_subgraph.loaded_edges,
                final_subgraph.truncated,
            )
            return final_subgraph
        except GraphQueryError as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._observer.on_query_error(
                operation,
                request.project_id,
                request.architecture_version_id,
                exc.code,
                duration_ms,
            )
            raise

    # 2. Single Node Detail
    def get_node_detail(self, request: NodeDetailRequest) -> GraphNode:
        operation = "node_detail"
        start_time = time.monotonic()
        deadline, _ = self._deadline_budget(request.timeout_seconds)
        self._observer.on_query_start(
            operation, request.project_id, request.architecture_version_id
        )

        try:
            scope = self._generation_reader.resolve_active_generation(
                request.project_id,
                request.architecture_version_id,
                timeout_seconds=self._check_remaining(deadline),
            )

            self._query_repository.verify_manifest_ready(
                scope, timeout_seconds=self._check_remaining(deadline)
            )

            node = self._query_repository.get_node_detail(
                scope,
                request,
                timeout_seconds=self._check_remaining(deadline),
            )
            if node is None:
                raise GraphNodeNotFoundError(
                    f"Node {request.entity_id} not found in scope"
                )

            self._verify_double_read(
                request.project_id,
                request.architecture_version_id,
                scope,
                deadline,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            self._observer.on_query_success(
                operation,
                request.project_id,
                request.architecture_version_id,
                scope.generation_id,
                duration_ms,
                1,
                0,
                False,
            )
            return node
        except GraphQueryError as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._observer.on_query_error(
                operation,
                request.project_id,
                request.architecture_version_id,
                exc.code,
                duration_ms,
            )
            raise

    # 3. Neighborhood
    def get_neighborhood(self, request: NeighborhoodRequest) -> GraphSubgraph:
        operation = "neighborhood"
        start_time = time.monotonic()
        deadline, _ = self._deadline_budget(request.timeout_seconds)
        self._observer.on_query_start(
            operation, request.project_id, request.architecture_version_id
        )

        try:
            scope = self._generation_reader.resolve_active_generation(
                request.project_id,
                request.architecture_version_id,
                timeout_seconds=self._check_remaining(deadline),
            )

            fp = compute_query_fingerprint(
                {
                    "operation": operation,
                    "entity_id": request.entity_id,
                    "direction": request.direction,
                    "depth": request.depth,
                    "node_limit": request.node_limit,
                    "edge_limit": request.edge_limit,
                    "kinds": (
                        [k.value for k in request.relationship_kinds]
                        if request.relationship_kinds
                        else None
                    ),
                }
            )

            position: dict[str, Any] | None = None
            if request.cursor:
                cursor_payload = validate_cursor(
                    request.cursor,
                    secret_key=self._cursor_secret_key,
                    expected_scope=scope,
                    expected_operation=operation,
                    expected_fingerprint=fp,
                )
                position = cursor_payload.position

            self._query_repository.verify_manifest_ready(
                scope, timeout_seconds=self._check_remaining(deadline)
            )

            subgraph, next_pos = self._query_repository.query_neighborhood(
                scope,
                request,
                position,
                timeout_seconds=self._check_remaining(deadline),
            )

            next_cursor: str | None = None
            if subgraph.truncated and next_pos is not None:
                next_cursor = encode_cursor(
                    scope=scope,
                    operation=operation,
                    fingerprint=fp,
                    position=next_pos,
                    secret_key=self._cursor_secret_key,
                    ttl_seconds=self._settings.graph_query_cursor_ttl_seconds,
                )

            final_subgraph = GraphSubgraph(
                scope=subgraph.scope,
                nodes=subgraph.nodes,
                edges=subgraph.edges,
                total_manifest_nodes=subgraph.total_manifest_nodes,
                total_manifest_edges=subgraph.total_manifest_edges,
                loaded_nodes=subgraph.loaded_nodes,
                loaded_edges=subgraph.loaded_edges,
                truncated=subgraph.truncated,
                next_cursor=next_cursor,
            )

            self._verify_double_read(
                request.project_id,
                request.architecture_version_id,
                scope,
                deadline,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            self._observer.on_query_success(
                operation,
                request.project_id,
                request.architecture_version_id,
                scope.generation_id,
                duration_ms,
                final_subgraph.loaded_nodes,
                final_subgraph.loaded_edges,
                final_subgraph.truncated,
            )
            return final_subgraph
        except GraphQueryError as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._observer.on_query_error(
                operation,
                request.project_id,
                request.architecture_version_id,
                exc.code,
                duration_ms,
            )
            raise

    # 4. Outgoing Dependencies
    def get_dependencies(self, request: DependenciesRequest) -> GraphSubgraph:
        operation = "dependencies"
        start_time = time.monotonic()
        deadline, _ = self._deadline_budget(request.timeout_seconds)
        self._observer.on_query_start(
            operation, request.project_id, request.architecture_version_id
        )

        try:
            scope = self._generation_reader.resolve_active_generation(
                request.project_id,
                request.architecture_version_id,
                timeout_seconds=self._check_remaining(deadline),
            )

            fp = compute_query_fingerprint(
                {
                    "operation": operation,
                    "entity_id": request.entity_id,
                    "depth": request.depth,
                    "node_limit": request.node_limit,
                    "edge_limit": request.edge_limit,
                    "kinds": (
                        [k.value for k in request.relationship_kinds]
                        if request.relationship_kinds
                        else None
                    ),
                }
            )

            position: dict[str, Any] | None = None
            if request.cursor:
                cursor_payload = validate_cursor(
                    request.cursor,
                    secret_key=self._cursor_secret_key,
                    expected_scope=scope,
                    expected_operation=operation,
                    expected_fingerprint=fp,
                )
                position = cursor_payload.position

            self._query_repository.verify_manifest_ready(
                scope, timeout_seconds=self._check_remaining(deadline)
            )

            subgraph, next_pos = self._query_repository.query_dependencies(
                scope,
                request,
                position,
                timeout_seconds=self._check_remaining(deadline),
            )

            next_cursor: str | None = None
            if subgraph.truncated and next_pos is not None:
                next_cursor = encode_cursor(
                    scope=scope,
                    operation=operation,
                    fingerprint=fp,
                    position=next_pos,
                    secret_key=self._cursor_secret_key,
                    ttl_seconds=self._settings.graph_query_cursor_ttl_seconds,
                )

            final_subgraph = GraphSubgraph(
                scope=subgraph.scope,
                nodes=subgraph.nodes,
                edges=subgraph.edges,
                total_manifest_nodes=subgraph.total_manifest_nodes,
                total_manifest_edges=subgraph.total_manifest_edges,
                loaded_nodes=subgraph.loaded_nodes,
                loaded_edges=subgraph.loaded_edges,
                truncated=subgraph.truncated,
                next_cursor=next_cursor,
            )

            self._verify_double_read(
                request.project_id,
                request.architecture_version_id,
                scope,
                deadline,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            self._observer.on_query_success(
                operation,
                request.project_id,
                request.architecture_version_id,
                scope.generation_id,
                duration_ms,
                final_subgraph.loaded_nodes,
                final_subgraph.loaded_edges,
                final_subgraph.truncated,
            )
            return final_subgraph
        except GraphQueryError as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._observer.on_query_error(
                operation,
                request.project_id,
                request.architecture_version_id,
                exc.code,
                duration_ms,
            )
            raise

    # 5. Incoming Dependents
    def get_dependents(self, request: DependentsRequest) -> GraphSubgraph:
        operation = "dependents"
        start_time = time.monotonic()
        deadline, _ = self._deadline_budget(request.timeout_seconds)
        self._observer.on_query_start(
            operation, request.project_id, request.architecture_version_id
        )

        try:
            scope = self._generation_reader.resolve_active_generation(
                request.project_id,
                request.architecture_version_id,
                timeout_seconds=self._check_remaining(deadline),
            )

            fp = compute_query_fingerprint(
                {
                    "operation": operation,
                    "entity_id": request.entity_id,
                    "depth": request.depth,
                    "node_limit": request.node_limit,
                    "edge_limit": request.edge_limit,
                    "kinds": (
                        [k.value for k in request.relationship_kinds]
                        if request.relationship_kinds
                        else None
                    ),
                }
            )

            position: dict[str, Any] | None = None
            if request.cursor:
                cursor_payload = validate_cursor(
                    request.cursor,
                    secret_key=self._cursor_secret_key,
                    expected_scope=scope,
                    expected_operation=operation,
                    expected_fingerprint=fp,
                )
                position = cursor_payload.position

            self._query_repository.verify_manifest_ready(
                scope, timeout_seconds=self._check_remaining(deadline)
            )

            subgraph, next_pos = self._query_repository.query_dependents(
                scope,
                request,
                position,
                timeout_seconds=self._check_remaining(deadline),
            )

            next_cursor: str | None = None
            if subgraph.truncated and next_pos is not None:
                next_cursor = encode_cursor(
                    scope=scope,
                    operation=operation,
                    fingerprint=fp,
                    position=next_pos,
                    secret_key=self._cursor_secret_key,
                    ttl_seconds=self._settings.graph_query_cursor_ttl_seconds,
                )

            final_subgraph = GraphSubgraph(
                scope=subgraph.scope,
                nodes=subgraph.nodes,
                edges=subgraph.edges,
                total_manifest_nodes=subgraph.total_manifest_nodes,
                total_manifest_edges=subgraph.total_manifest_edges,
                loaded_nodes=subgraph.loaded_nodes,
                loaded_edges=subgraph.loaded_edges,
                truncated=subgraph.truncated,
                next_cursor=next_cursor,
            )

            self._verify_double_read(
                request.project_id,
                request.architecture_version_id,
                scope,
                deadline,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            self._observer.on_query_success(
                operation,
                request.project_id,
                request.architecture_version_id,
                scope.generation_id,
                duration_ms,
                final_subgraph.loaded_nodes,
                final_subgraph.loaded_edges,
                final_subgraph.truncated,
            )
            return final_subgraph
        except GraphQueryError as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._observer.on_query_error(
                operation,
                request.project_id,
                request.architecture_version_id,
                exc.code,
                duration_ms,
            )
            raise

    # 6. Containment Hierarchy
    def get_containment(self, request: ContainmentRequest) -> GraphSubgraph:
        operation = "containment"
        start_time = time.monotonic()
        deadline, _ = self._deadline_budget(request.timeout_seconds)
        self._observer.on_query_start(
            operation, request.project_id, request.architecture_version_id
        )

        try:
            scope = self._generation_reader.resolve_active_generation(
                request.project_id,
                request.architecture_version_id,
                timeout_seconds=self._check_remaining(deadline),
            )

            fp = compute_query_fingerprint(
                {
                    "operation": operation,
                    "entity_id": request.entity_id,
                    "direction": request.direction,
                    "depth": request.depth,
                    "node_limit": request.node_limit,
                    "edge_limit": request.edge_limit,
                }
            )

            position: dict[str, Any] | None = None
            if request.cursor:
                cursor_payload = validate_cursor(
                    request.cursor,
                    secret_key=self._cursor_secret_key,
                    expected_scope=scope,
                    expected_operation=operation,
                    expected_fingerprint=fp,
                )
                position = cursor_payload.position

            self._query_repository.verify_manifest_ready(
                scope, timeout_seconds=self._check_remaining(deadline)
            )

            subgraph, next_pos = self._query_repository.query_containment(
                scope,
                request,
                position,
                timeout_seconds=self._check_remaining(deadline),
            )

            next_cursor: str | None = None
            if subgraph.truncated and next_pos is not None:
                next_cursor = encode_cursor(
                    scope=scope,
                    operation=operation,
                    fingerprint=fp,
                    position=next_pos,
                    secret_key=self._cursor_secret_key,
                    ttl_seconds=self._settings.graph_query_cursor_ttl_seconds,
                )

            final_subgraph = GraphSubgraph(
                scope=subgraph.scope,
                nodes=subgraph.nodes,
                edges=subgraph.edges,
                total_manifest_nodes=subgraph.total_manifest_nodes,
                total_manifest_edges=subgraph.total_manifest_edges,
                loaded_nodes=subgraph.loaded_nodes,
                loaded_edges=subgraph.loaded_edges,
                truncated=subgraph.truncated,
                next_cursor=next_cursor,
            )

            self._verify_double_read(
                request.project_id,
                request.architecture_version_id,
                scope,
                deadline,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            self._observer.on_query_success(
                operation,
                request.project_id,
                request.architecture_version_id,
                scope.generation_id,
                duration_ms,
                final_subgraph.loaded_nodes,
                final_subgraph.loaded_edges,
                final_subgraph.truncated,
            )
            return final_subgraph
        except GraphQueryError as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._observer.on_query_error(
                operation,
                request.project_id,
                request.architecture_version_id,
                exc.code,
                duration_ms,
            )
            raise

    # 7. Bounded Paths
    def get_bounded_paths(self, request: BoundedPathsRequest) -> GraphPathResult:
        operation = "paths"
        start_time = time.monotonic()
        deadline, _ = self._deadline_budget(request.timeout_seconds)
        self._observer.on_query_start(
            operation, request.project_id, request.architecture_version_id
        )

        try:
            scope = self._generation_reader.resolve_active_generation(
                request.project_id,
                request.architecture_version_id,
                timeout_seconds=self._check_remaining(deadline),
            )

            self._query_repository.verify_manifest_ready(
                scope, timeout_seconds=self._check_remaining(deadline)
            )

            result = self._query_repository.query_bounded_paths(
                scope,
                request,
                timeout_seconds=self._check_remaining(deadline),
            )

            self._verify_double_read(
                request.project_id,
                request.architecture_version_id,
                scope,
                deadline,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            self._observer.on_query_success(
                operation,
                request.project_id,
                request.architecture_version_id,
                scope.generation_id,
                duration_ms,
                sum(len(p.nodes) for p in result.paths),
                sum(len(p.edges) for p in result.paths),
                result.truncated,
            )
            return result
        except GraphQueryError as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._observer.on_query_error(
                operation,
                request.project_id,
                request.architecture_version_id,
                exc.code,
                duration_ms,
            )
            raise


__all__ = [
    "DefaultLoggingGraphQueryObserver",
    "GraphQueryObserver",
    "GraphQueryService",
]
