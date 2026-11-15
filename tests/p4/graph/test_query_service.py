"""Unit tests for GraphQueryService application orchestration."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.platform.config import Settings
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
    GraphCursorInvalidError,
    GraphEdge,
    GraphGenerationChangedError,
    GraphNode,
    GraphNodeNotFoundError,
    GraphProjectionNotFoundError,
    GraphProjectionNotReadyError,
    GraphQueryTimeoutError,
    GraphReadScope,
    GraphRelationshipKind,
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
    GraphQueryObserver,
    GraphQueryService,
)


class RecordingQueryObserver(GraphQueryObserver):
    """Observer that records query events for test verification."""

    def __init__(self) -> None:
        self.starts: list[tuple[str, UUID, UUID]] = []
        self.successes: list[tuple[str, UUID, UUID, UUID, float, int, int, bool]] = []
        self.errors: list[tuple[str, UUID, UUID, str, float]] = []

    def on_query_start(
        self,
        operation: str,
        project_id: UUID,
        architecture_version_id: UUID,
    ) -> None:
        self.starts.append((operation, project_id, architecture_version_id))

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
        self.successes.append(
            (
                operation,
                project_id,
                architecture_version_id,
                generation_id,
                duration_ms,
                nodes_count,
                edges_count,
                truncated,
            )
        )

    def on_query_error(
        self,
        operation: str,
        project_id: UUID,
        architecture_version_id: UUID,
        error_code: str,
        duration_ms: float,
    ) -> None:
        self.errors.append(
            (
                operation,
                project_id,
                architecture_version_id,
                error_code,
                duration_ms,
            )
        )


def _make_scope(
    *,
    project_id: UUID | None = None,
    architecture_version_id: UUID | None = None,
    generation_id: UUID | None = None,
) -> GraphReadScope:
    return GraphReadScope(
        project_id=project_id or uuid4(),
        architecture_version_id=architecture_version_id or uuid4(),
        generation_id=generation_id or uuid4(),
        resource_state="COMPLETED",
        graph_schema_version=GRAPH_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        counts=ProjectionCounts(
            entities=3,
            relationships=2,
            evidence=1,
            unresolved=0,
            conflicts=0,
        ),
    )


def _make_node(
    scope: GraphReadScope,
    *,
    entity_id: UUID | None = None,
    logical_id: str = "comp.Service",
    kind: str = "component",
    name: str = "Service",
) -> GraphNode:
    eid = entity_id or uuid4()
    return GraphNode(
        architecture_entity_id=eid,
        logical_id=logical_id,
        canonical_kind=kind,
        name=name,
        namespace="com.example",
        fact_status="canonical",
        semantic_signature="sig-123",
        evidence_logical_ids=("ev-1",),
        metadata={"custom": "val"},
    )


def _make_edge(
    scope: GraphReadScope,
    source: GraphNode,
    target: GraphNode,
    *,
    edge_id: UUID | None = None,
    kind: GraphRelationshipKind = GraphRelationshipKind.CALLS,
) -> GraphEdge:
    return GraphEdge(
        architecture_relationship_id=edge_id or uuid4(),
        logical_id=f"rel.{source.name}->{target.name}",
        canonical_kind=kind,
        status="canonical",
        source_entity_id=source.architecture_entity_id,
        target_entity_id=target.architecture_entity_id,
        evidence_logical_ids=("ev-edge-1",),
        metadata={"edge_meta": "yes"},
    )


def test_service_get_window_success() -> None:
    settings = Settings()
    scope = _make_scope()
    reader = FakeGraphGenerationReader()
    reader.set_scope(scope)

    repo = FakeGraphQueryRepository()
    node1 = _make_node(scope, name="N1")
    node2 = _make_node(scope, name="N2")
    edge = _make_edge(scope, node1, node2)
    repo.nodes[node1.architecture_entity_id] = node1
    repo.nodes[node2.architecture_entity_id] = node2
    repo.edges.append(edge)

    observer = RecordingQueryObserver()
    service = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key="a" * 32,
        observer=observer,
    )

    req = GraphWindowRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        node_limit=100,
        edge_limit=100,
    )
    result = service.get_window(req)

    assert result.scope == scope
    assert len(result.nodes) == 2
    assert len(result.edges) == 1
    assert result.truncated is False
    assert result.next_cursor is None

    assert len(observer.starts) == 1
    assert len(observer.successes) == 1
    assert observer.successes[0][0] == "window"
    assert observer.successes[0][5] == 2  # nodes count
    assert observer.successes[0][6] == 1  # edges count


def test_service_get_window_pagination_and_cursor() -> None:
    settings = Settings()
    scope = _make_scope()
    reader = FakeGraphGenerationReader()
    reader.set_scope(scope)

    repo = FakeGraphQueryRepository()
    # Add 5 nodes
    for i in range(5):
        n = _make_node(scope, name=f"Node_{i}")
        repo.nodes[n.architecture_entity_id] = n

    service = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key="b" * 32,
    )

    req = GraphWindowRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        node_limit=2,
    )
    result = service.get_window(req)

    assert result.truncated is True
    assert result.next_cursor is not None
    assert len(result.nodes) == 2

    # Request second page with next_cursor
    req2 = GraphWindowRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        node_limit=2,
        cursor=result.next_cursor,
    )
    result2 = service.get_window(req2)
    assert result2.scope == scope


def test_service_get_window_tampered_cursor_fails() -> None:
    settings = Settings()
    scope = _make_scope()
    reader = FakeGraphGenerationReader()
    reader.set_scope(scope)
    repo = FakeGraphQueryRepository()

    service = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key="c" * 32,
    )

    req = GraphWindowRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        cursor="invalid-tampered-cursor",
    )
    with pytest.raises(GraphCursorInvalidError):
        service.get_window(req)


def test_service_get_node_detail_success_and_not_found() -> None:
    settings = Settings()
    scope = _make_scope()
    reader = FakeGraphGenerationReader()
    reader.set_scope(scope)
    repo = FakeGraphQueryRepository()

    node = _make_node(scope, name="Anchor")
    repo.nodes[node.architecture_entity_id] = node

    service = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key="d" * 32,
    )

    # Success
    req = NodeDetailRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        entity_id=node.architecture_entity_id,
    )
    found = service.get_node_detail(req)
    assert found.architecture_entity_id == node.architecture_entity_id

    # Not found
    missing_id = uuid4()
    req_missing = NodeDetailRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        entity_id=missing_id,
    )
    with pytest.raises(GraphNodeNotFoundError):
        service.get_node_detail(req_missing)


def test_service_get_neighborhood() -> None:
    settings = Settings()
    scope = _make_scope()
    reader = FakeGraphGenerationReader()
    reader.set_scope(scope)
    repo = FakeGraphQueryRepository()

    node = _make_node(scope, name="Anchor")
    repo.nodes[node.architecture_entity_id] = node

    service = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key="e" * 32,
    )

    req = NeighborhoodRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        entity_id=node.architecture_entity_id,
        direction=TraversalDirection.OUTGOING,
        depth=1,
    )
    subgraph = service.get_neighborhood(req)
    assert len(subgraph.nodes) == 1
    assert subgraph.nodes[0].architecture_entity_id == node.architecture_entity_id


def test_service_get_dependencies() -> None:
    settings = Settings()
    scope = _make_scope()
    reader = FakeGraphGenerationReader()
    reader.set_scope(scope)
    repo = FakeGraphQueryRepository()

    node = _make_node(scope, name="Anchor")
    repo.nodes[node.architecture_entity_id] = node

    service = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key="f" * 32,
    )

    req = DependenciesRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        entity_id=node.architecture_entity_id,
        depth=2,
    )
    subgraph = service.get_dependencies(req)
    assert len(subgraph.nodes) == 1


def test_service_get_dependents() -> None:
    settings = Settings()
    scope = _make_scope()
    reader = FakeGraphGenerationReader()
    reader.set_scope(scope)
    repo = FakeGraphQueryRepository()

    node = _make_node(scope, name="Anchor")
    repo.nodes[node.architecture_entity_id] = node

    service = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key="g" * 32,
    )

    req = DependentsRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        entity_id=node.architecture_entity_id,
        depth=3,
    )
    subgraph = service.get_dependents(req)
    assert len(subgraph.nodes) == 1


def test_service_get_containment() -> None:
    settings = Settings()
    scope = _make_scope()
    reader = FakeGraphGenerationReader()
    reader.set_scope(scope)
    repo = FakeGraphQueryRepository()

    node = _make_node(scope, name="Module")
    repo.nodes[node.architecture_entity_id] = node

    service = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key="h" * 32,
    )

    req = ContainmentRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        entity_id=node.architecture_entity_id,
        direction=ContainmentDirection.BOTH,
        depth=2,
    )
    subgraph = service.get_containment(req)
    assert len(subgraph.nodes) == 1


def test_service_get_bounded_paths() -> None:
    settings = Settings()
    scope = _make_scope()
    reader = FakeGraphGenerationReader()
    reader.set_scope(scope)
    repo = FakeGraphQueryRepository()

    node = _make_node(scope, name="SameSrcTgt")
    repo.nodes[node.architecture_entity_id] = node

    service = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key="i" * 32,
    )

    req = BoundedPathsRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        source_entity_id=node.architecture_entity_id,
        target_entity_id=node.architecture_entity_id,
        max_depth=3,
    )
    result = service.get_bounded_paths(req)
    assert result.total_paths_found == 1
    assert result.paths[0].hop_count == 0
    assert len(result.paths[0].nodes) == 1


def test_service_double_read_detects_generation_change() -> None:
    settings = Settings()
    scope = _make_scope()

    class SwitchingGenerationReader(FakeGraphGenerationReader):
        def verify_generation_still_active(
            self,
            project_id: UUID,
            architecture_version_id: UUID,
            generation_id: UUID,
            *,
            timeout_seconds: float | None = None,
        ) -> bool:
            # Simulate active generation changing during query execution
            return False

    reader = SwitchingGenerationReader()
    reader.set_scope(scope)
    repo = FakeGraphQueryRepository()
    node = _make_node(scope)
    repo.nodes[node.architecture_entity_id] = node

    service = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key="j" * 32,
    )

    req = GraphWindowRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
    )
    with pytest.raises(
        GraphGenerationChangedError, match="changed during query execution"
    ):
        service.get_window(req)


def test_service_manifest_preflight_unready_raises() -> None:
    settings = Settings()
    scope = _make_scope()
    reader = FakeGraphGenerationReader()
    reader.set_scope(scope)
    repo = FakeGraphQueryRepository()
    repo.manifest_ready = False

    service = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key="k" * 32,
    )

    req = GraphWindowRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
    )
    with pytest.raises(GraphProjectionNotReadyError):
        service.get_window(req)


def test_service_timeout_handling() -> None:
    settings = Settings()
    scope = _make_scope()
    reader = FakeGraphGenerationReader()
    reader.set_scope(scope)
    repo = FakeGraphQueryRepository()
    repo.simulated_timeout = True

    service = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key="l" * 32,
    )

    req = GraphWindowRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
    )
    with pytest.raises(GraphQueryTimeoutError):
        service.get_window(req)


def test_service_observer_error_reporting() -> None:
    settings = Settings()
    scope = _make_scope()
    reader = FakeGraphGenerationReader()
    # Missing scope raises GraphProjectionNotFoundError
    repo = FakeGraphQueryRepository()
    observer = RecordingQueryObserver()

    service = GraphQueryService(
        settings=settings,
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key="m" * 32,
        observer=observer,
    )

    req = GraphWindowRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
    )
    with pytest.raises(GraphProjectionNotFoundError):
        service.get_window(req)

    assert len(observer.starts) == 1
    assert len(observer.errors) == 1
    assert observer.errors[0][0] == "window"
    assert observer.errors[0][3] == "graph_projection_not_found"
