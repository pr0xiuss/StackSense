"""Unit tests for query lifecycle, pointer switch, deadline, and degradation.

Validates:
1. Historical STALE resource reads resolve last verified generation.
2. In-flight pointer change raises GraphGenerationChangedError across all operations.
3. Cursors fail closed after pointer switch for all paginated operations.
4. Monotonic operation deadline budget expires cleanly at each execution phase.
5. Structured observer records telemetry without leaking credentials or properties.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

import pytest

from backend.platform.config import Settings
from backend.platform.graph.cursor import compute_query_fingerprint, encode_cursor
from backend.platform.graph.model import (
    GRAPH_SCHEMA_VERSION,
    PROJECTOR_VERSION,
    ProjectionCounts,
)
from backend.platform.graph.query_contracts import (
    BoundedPathsRequest,
    ContainmentDirection,
    ContainmentRequest,
    DependenciesRequest,
    DependentsRequest,
    GraphGenerationChangedError,
    GraphNode,
    GraphQueryTimeoutError,
    GraphReadScope,
    GraphSubgraph,
    GraphWindowRequest,
    NeighborhoodRequest,
    NodeDetailRequest,
    TraversalDirection,
)
from backend.platform.graph.query_repository import (
    FakeGraphGenerationReader,
    FakeGraphQueryRepository,
)
from backend.platform.graph.query_service import (
    DefaultLoggingGraphQueryObserver,
    GraphQueryService,
)


def _make_scope(
    *,
    project_id: UUID | None = None,
    architecture_version_id: UUID | None = None,
    generation_id: UUID | None = None,
    state: str = "COMPLETED",
) -> GraphReadScope:
    return GraphReadScope(
        project_id=project_id or uuid4(),
        architecture_version_id=architecture_version_id or uuid4(),
        generation_id=generation_id or uuid4(),
        resource_state=state,
        graph_schema_version=GRAPH_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        counts=ProjectionCounts(
            entities=2,
            relationships=1,
            evidence=1,
            unresolved=0,
            conflicts=0,
        ),
    )


def _make_node(scope: GraphReadScope, name: str) -> GraphNode:
    return GraphNode(
        architecture_entity_id=uuid4(),
        logical_id=f"comp.{name}",
        canonical_kind="service",
        name=name,
        namespace="com.example",
        fact_status="canonical",
        semantic_signature="sig-1",
        evidence_logical_ids=("ev-1",),
        metadata={"domain": "test"},
    )


def test_stale_resource_read_succeeds() -> None:
    """Historical STALE resources remain queryable against last verified generation."""
    settings = Settings()
    scope = _make_scope(state="STALE")
    reader = FakeGraphGenerationReader()
    reader.set_scope(scope)

    repo = FakeGraphQueryRepository()
    node = _make_node(scope, "LegacyService")
    repo.nodes[node.architecture_entity_id] = node

    service = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key="secret" * 6,
    )

    req = GraphWindowRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
    )
    result = service.get_window(req)
    assert result.scope.resource_state == "STALE"
    assert len(result.nodes) == 1
    assert result.nodes[0].name == "LegacyService"


@pytest.mark.parametrize(
    "operation_name",
    [
        "window",
        "node_detail",
        "neighborhood",
        "dependencies",
        "dependents",
        "containment",
        "bounded_paths",
    ],
)
def test_in_flight_generation_change_fails_closed_across_all_operations(
    operation_name: str,
) -> None:
    """Every operation double-reads PostgreSQL pointer and fails closed if changed."""
    settings = Settings()
    scope = _make_scope()

    class PointerSwitchedReader(FakeGraphGenerationReader):
        def verify_generation_still_active(
            self,
            project_id: UUID,
            architecture_version_id: UUID,
            generation_id: UUID,
            *,
            timeout_seconds: float | None = None,
        ) -> bool:
            # Active pointer changed to a new generation G' during query
            return False

    reader = PointerSwitchedReader()
    reader.set_scope(scope)

    repo = FakeGraphQueryRepository()
    node = _make_node(scope, "Anchor")
    repo.nodes[node.architecture_entity_id] = node

    service = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key="secret" * 6,
    )

    p_id = scope.project_id
    v_id = scope.architecture_version_id
    e_id = node.architecture_entity_id

    with pytest.raises(
        GraphGenerationChangedError, match="changed during query execution"
    ):
        if operation_name == "window":
            service.get_window(
                GraphWindowRequest(project_id=p_id, architecture_version_id=v_id)
            )
        elif operation_name == "node_detail":
            service.get_node_detail(
                NodeDetailRequest(
                    project_id=p_id, architecture_version_id=v_id, entity_id=e_id
                )
            )
        elif operation_name == "neighborhood":
            service.get_neighborhood(
                NeighborhoodRequest(
                    project_id=p_id,
                    architecture_version_id=v_id,
                    entity_id=e_id,
                    direction=TraversalDirection.OUTGOING,
                    depth=1,
                )
            )
        elif operation_name == "dependencies":
            service.get_dependencies(
                DependenciesRequest(
                    project_id=p_id,
                    architecture_version_id=v_id,
                    entity_id=e_id,
                    depth=1,
                )
            )
        elif operation_name == "dependents":
            service.get_dependents(
                DependentsRequest(
                    project_id=p_id,
                    architecture_version_id=v_id,
                    entity_id=e_id,
                    depth=1,
                )
            )
        elif operation_name == "containment":
            service.get_containment(
                ContainmentRequest(
                    project_id=p_id,
                    architecture_version_id=v_id,
                    entity_id=e_id,
                    direction=ContainmentDirection.BOTH,
                    depth=1,
                )
            )
        elif operation_name == "bounded_paths":
            service.get_bounded_paths(
                BoundedPathsRequest(
                    project_id=p_id,
                    architecture_version_id=v_id,
                    source_entity_id=e_id,
                    target_entity_id=e_id,
                    max_depth=1,
                )
            )


@pytest.mark.parametrize(
    "operation",
    ["window", "neighborhood", "dependencies", "dependents", "containment"],
)
def test_cursor_after_pointer_switch_fails_closed(operation: str) -> None:
    """A continuation cursor bound to G1 must fail closed when G2 becomes active."""
    settings = Settings()
    g1_scope = _make_scope()
    g2_scope = _make_scope(
        project_id=g1_scope.project_id,
        architecture_version_id=g1_scope.architecture_version_id,
    )

    # Active generation in PostgreSQL is now G2
    reader = FakeGraphGenerationReader()
    reader.set_scope(g2_scope)

    repo = FakeGraphQueryRepository()
    node = _make_node(g2_scope, "NodeX")
    repo.nodes[node.architecture_entity_id] = node

    secret = "secret" * 6
    service = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key=secret,
    )

    p_id = g1_scope.project_id
    v_id = g1_scope.architecture_version_id
    e_id = node.architecture_entity_id

    if operation == "window":
        base_req = GraphWindowRequest(project_id=p_id, architecture_version_id=v_id)
        params_fp = {
            "operation": operation,
            "node_limit": base_req.node_limit,
            "edge_limit": base_req.edge_limit,
            "page_size": base_req.page_size,
            "kinds": None,
        }
    elif operation == "neighborhood":
        base_req = NeighborhoodRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            entity_id=e_id,
            direction=TraversalDirection.OUTGOING,
            depth=1,
        )
        params_fp = {
            "operation": operation,
            "entity_id": base_req.entity_id,
            "direction": base_req.direction,
            "depth": base_req.depth,
            "node_limit": base_req.node_limit,
            "edge_limit": base_req.edge_limit,
            "kinds": None,
        }
    elif operation == "dependencies":
        base_req = DependenciesRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            entity_id=e_id,
            depth=1,
        )
        params_fp = {
            "operation": operation,
            "entity_id": base_req.entity_id,
            "depth": base_req.depth,
            "node_limit": base_req.node_limit,
            "edge_limit": base_req.edge_limit,
            "kinds": None,
        }
    elif operation == "dependents":
        base_req = DependentsRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            entity_id=e_id,
            depth=1,
        )
        params_fp = {
            "operation": operation,
            "entity_id": base_req.entity_id,
            "depth": base_req.depth,
            "node_limit": base_req.node_limit,
            "edge_limit": base_req.edge_limit,
            "kinds": None,
        }
    elif operation == "containment":
        base_req = ContainmentRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            entity_id=e_id,
            direction=ContainmentDirection.BOTH,
            depth=1,
        )
        params_fp = {
            "operation": operation,
            "entity_id": base_req.entity_id,
            "direction": base_req.direction,
            "depth": base_req.depth,
            "node_limit": base_req.node_limit,
            "edge_limit": base_req.edge_limit,
        }

    fp = compute_query_fingerprint(params_fp)
    g1_cursor = encode_cursor(
        position={"depth": 1, "last_rel_key": "rel123"},
        scope=g1_scope,
        operation=operation,
        fingerprint=fp,
        secret_key=secret,
        ttl_seconds=900,
    )

    # Using G1 cursor when active generation is G2 must raise
    # GraphGenerationChangedError
    with pytest.raises(
        GraphGenerationChangedError, match="Active projection generation changed"
    ):
        if operation == "window":
            service.get_window(
                GraphWindowRequest(
                    project_id=p_id,
                    architecture_version_id=v_id,
                    cursor=g1_cursor,
                )
            )
        elif operation == "neighborhood":
            service.get_neighborhood(
                NeighborhoodRequest(
                    project_id=p_id,
                    architecture_version_id=v_id,
                    entity_id=e_id,
                    direction=TraversalDirection.OUTGOING,
                    depth=1,
                    cursor=g1_cursor,
                )
            )
        elif operation == "dependencies":
            service.get_dependencies(
                DependenciesRequest(
                    project_id=p_id,
                    architecture_version_id=v_id,
                    entity_id=e_id,
                    depth=1,
                    cursor=g1_cursor,
                )
            )
        elif operation == "dependents":
            service.get_dependents(
                DependentsRequest(
                    project_id=p_id,
                    architecture_version_id=v_id,
                    entity_id=e_id,
                    depth=1,
                    cursor=g1_cursor,
                )
            )
        elif operation == "containment":
            service.get_containment(
                ContainmentRequest(
                    project_id=p_id,
                    architecture_version_id=v_id,
                    entity_id=e_id,
                    direction=ContainmentDirection.BOTH,
                    depth=1,
                    cursor=g1_cursor,
                )
            )


def test_deadline_budget_exhaustion_at_each_phase() -> None:
    settings = Settings()
    scope = _make_scope()

    # 1. Timeout during initial PostgreSQL read
    class SlowReader(FakeGraphGenerationReader):
        def resolve_active_generation(
            self,
            project_id: UUID,
            architecture_version_id: UUID,
            *,
            timeout_seconds: float | None = None,
        ) -> GraphReadScope:
            raise GraphQueryTimeoutError("Initial generation resolution timed out")

    svc1 = GraphQueryService(
        settings=settings,
        generation_reader=SlowReader(),
        query_repository=FakeGraphQueryRepository(),
        cursor_secret_key="secret" * 6,
    )
    with pytest.raises(GraphQueryTimeoutError, match="resolution timed out"):
        svc1.get_window(
            GraphWindowRequest(
                project_id=scope.project_id,
                architecture_version_id=scope.architecture_version_id,
            )
        )

    # 2. Timeout during Neo4j preflight
    class PreflightTimeoutRepo(FakeGraphQueryRepository):
        def verify_manifest_ready(
            self, scope: GraphReadScope, *, timeout_seconds: float
        ) -> bool:
            raise GraphQueryTimeoutError("Neo4j manifest preflight timed out")

    reader = FakeGraphGenerationReader()
    reader.set_scope(scope)
    svc2 = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=PreflightTimeoutRepo(),
        cursor_secret_key="secret" * 6,
    )
    with pytest.raises(GraphQueryTimeoutError, match="preflight timed out"):
        svc2.get_window(
            GraphWindowRequest(
                project_id=scope.project_id,
                architecture_version_id=scope.architecture_version_id,
            )
        )

    # 3. Timeout during Neo4j query execution
    class ExecutionTimeoutRepo(FakeGraphQueryRepository):
        def query_window(
            self,
            scope: GraphReadScope,
            request: GraphWindowRequest,
            position: dict[str, Any] | None,
            *,
            timeout_seconds: float,
        ) -> tuple[GraphSubgraph, dict[str, Any] | None]:
            raise GraphQueryTimeoutError("Neo4j execution timed out")

    svc3 = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=ExecutionTimeoutRepo(),
        cursor_secret_key="secret" * 6,
    )
    with pytest.raises(GraphQueryTimeoutError, match="execution timed out"):
        svc3.get_window(
            GraphWindowRequest(
                project_id=scope.project_id,
                architecture_version_id=scope.architecture_version_id,
            )
        )

    # 4. Timeout during double read
    class SlowDoubleReader(FakeGraphGenerationReader):
        def verify_generation_still_active(
            self,
            project_id: UUID,
            architecture_version_id: UUID,
            generation_id: UUID,
            *,
            timeout_seconds: float | None = None,
        ) -> bool:
            raise GraphQueryTimeoutError("Double read verification timed out")

    reader_slow_double = SlowDoubleReader()
    reader_slow_double.set_scope(scope)
    svc4 = GraphQueryService(
        settings=settings,
        generation_reader=reader_slow_double,
        query_repository=FakeGraphQueryRepository(),
        cursor_secret_key="secret" * 6,
    )
    with pytest.raises(
        GraphQueryTimeoutError, match="Double read verification timed out"
    ):
        svc4.get_window(
            GraphWindowRequest(
                project_id=scope.project_id,
                architecture_version_id=scope.architecture_version_id,
            )
        )


def test_default_logging_observer_telemetry(caplog: pytest.LogCaptureFixture) -> None:
    observer = DefaultLoggingGraphQueryObserver()
    p_id = uuid4()
    v_id = uuid4()
    g_id = uuid4()

    with caplog.at_level(logging.INFO, logger="stacksense.graph.query"):
        observer.on_query_start("window", p_id, v_id)
        observer.on_query_success("window", p_id, v_id, g_id, 45.2, 10, 5, False)
        observer.on_query_error("window", p_id, v_id, "graph_node_not_found", 12.5)

    logs = caplog.text
    # Telemetry properties must appear
    assert "graph_query_start operation=window" in logs
    assert f"project_id={p_id}" in logs
    assert f"architecture_version_id={v_id}" in logs
    assert f"generation_id={g_id}" in logs
    assert "duration_ms=45.20 nodes=10 edges=5 truncated=False" in logs
    assert "code=graph_node_not_found" in logs

    # Ensure sensitive items are NEVER logged
    assert "MATCH" not in logs
    assert "RETURN" not in logs
    assert "password" not in logs.lower()
    assert "secret" not in logs.lower()
