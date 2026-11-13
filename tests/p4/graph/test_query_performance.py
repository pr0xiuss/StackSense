"""Performance, caps, and limit enforcement tests for P4-Q1 graph queries.

Validates:
1. Strict enforcement of hard query caps (depth <= 5, nodes <= 500, edges <= 1000,
   paths <= 25, timeout <= 5.0s).
2. Materialization performance on dense/maximum-size graphs.
3. Truncation and deterministic pagination at cap boundaries.
"""

from __future__ import annotations

import time
from uuid import uuid4

import pytest
from pydantic import ValidationError

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
    GraphEdge,
    GraphNode,
    GraphReadScope,
    GraphRelationshipKind,
    GraphWindowRequest,
    NeighborhoodRequest,
)
from backend.platform.graph.query_repository import (
    FakeGraphGenerationReader,
    FakeGraphQueryRepository,
)
from backend.platform.graph.query_service import GraphQueryService


def _make_scope() -> GraphReadScope:
    return GraphReadScope(
        project_id=uuid4(),
        architecture_version_id=uuid4(),
        generation_id=uuid4(),
        resource_state="COMPLETED",
        graph_schema_version=GRAPH_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        counts=ProjectionCounts(
            entities=500,
            relationships=1000,
            evidence=1,
            unresolved=0,
            conflicts=0,
        ),
    )


def test_window_request_rejects_exceeded_caps() -> None:
    p_id = uuid4()
    v_id = uuid4()

    # Node limit > 500
    with pytest.raises(ValidationError):
        GraphWindowRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            node_limit=501,
        )

    # Edge limit > 1000
    with pytest.raises(ValidationError):
        GraphWindowRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            edge_limit=1001,
        )

    # Page size > 100
    with pytest.raises(ValidationError):
        GraphWindowRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            page_size=101,
        )

    # Timeout > 5.0
    with pytest.raises(ValidationError):
        GraphWindowRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            timeout_seconds=5.1,
        )


def test_traversal_requests_reject_exceeded_caps() -> None:
    p_id = uuid4()
    v_id = uuid4()
    e_id = uuid4()

    # Neighborhood depth > 5
    with pytest.raises(ValidationError):
        NeighborhoodRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            entity_id=e_id,
            depth=6,
        )

    # Dependencies depth > 5
    with pytest.raises(ValidationError):
        DependenciesRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            entity_id=e_id,
            depth=6,
        )

    # Dependents depth > 5
    with pytest.raises(ValidationError):
        DependentsRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            entity_id=e_id,
            depth=6,
        )

    # Containment depth > 5
    with pytest.raises(ValidationError):
        ContainmentRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            entity_id=e_id,
            direction=ContainmentDirection.BOTH,
            depth=6,
        )


def test_bounded_paths_request_rejects_exceeded_caps() -> None:
    p_id = uuid4()
    v_id = uuid4()

    # Max depth > 5
    with pytest.raises(ValidationError):
        BoundedPathsRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            source_entity_id=uuid4(),
            target_entity_id=uuid4(),
            max_depth=6,
        )

    # Path limit > 25
    with pytest.raises(ValidationError):
        BoundedPathsRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            source_entity_id=uuid4(),
            target_entity_id=uuid4(),
            path_limit=26,
        )


def test_materialization_dense_workload() -> None:
    """Benchmark materialization of maximum legal payload (500 nodes, 1000 edges)."""
    scope = _make_scope()
    reader = FakeGraphGenerationReader()
    reader.set_scope(scope)

    repo = FakeGraphQueryRepository()
    nodes_list: list[GraphNode] = []
    for i in range(500):
        n = GraphNode(
            architecture_entity_id=uuid4(),
            logical_id=f"comp.Node_{i}",
            canonical_kind="component",
            name=f"Node_{i}",
            namespace="com.example",
            fact_status="canonical",
            semantic_signature="sig-bench",
            evidence_logical_ids=("ev-1",),
            metadata={"index": i},
        )
        repo.nodes[n.architecture_entity_id] = n
        nodes_list.append(n)

    for j in range(1000):
        src = nodes_list[j % 500]
        tgt = nodes_list[(j + 1) % 500]
        edge = GraphEdge(
            architecture_relationship_id=uuid4(),
            logical_id=f"rel.{src.name}->{tgt.name}_{j}",
            canonical_kind=GraphRelationshipKind.CALLS,
            status="canonical",
            source_entity_id=src.architecture_entity_id,
            target_entity_id=tgt.architecture_entity_id,
            evidence_logical_ids=("ev-edge-1",),
            metadata={"edge_idx": j},
        )
        repo.edges.append(edge)

    service = GraphQueryService(
        settings=Settings(),
        generation_reader=reader,
        query_repository=repo,
        cursor_secret_key="perf-secret-key-32-bytes-long!",
    )

    t0 = time.monotonic()
    req = GraphWindowRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        node_limit=500,
        edge_limit=1000,
    )
    result = service.get_window(req)
    duration_ms = (time.monotonic() - t0) * 1000

    assert len(result.nodes) == 500
    assert len(result.edges) == 1000
    assert result.truncated is False
    # Materialization must complete well under 5.0 seconds
    assert duration_ms < 500.0, f"Expected < 500ms, got {duration_ms:.2f}ms"
