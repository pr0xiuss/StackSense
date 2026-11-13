"""Unit tests for P4-Q1 graph query contracts, closed vocabularies, limits, and DTOs."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.platform.graph.model import ProjectionCounts
from backend.platform.graph.query_contracts import (
    ALL_APPROVED_RELATIONSHIP_KINDS,
    APPROVED_DEPENDENCY_RELATIONSHIP_KINDS,
    DEFAULT_QUERY_DEPTH,
    DEFAULT_QUERY_EDGES,
    DEFAULT_QUERY_NODES,
    DEFAULT_QUERY_PAGE_SIZE,
    DEFAULT_QUERY_PATHS,
    DEFAULT_QUERY_TIMEOUT_SECONDS,
    MAX_CURSOR_LENGTH,
    MAX_QUERY_DEPTH,
    MAX_QUERY_EDGES,
    MAX_QUERY_NODES,
    MAX_QUERY_PAGE_SIZE,
    MAX_QUERY_PATHS,
    MAX_QUERY_TIMEOUT_SECONDS,
    P4_Q1_CONTRACT_VERSION,
    BoundedPathsRequest,
    ContainmentDirection,
    ContainmentRequest,
    DependenciesRequest,
    DependentsRequest,
    GraphCursorExpiredError,
    GraphCursorInvalidError,
    GraphCursorScopeMismatchError,
    GraphEdge,
    GraphGenerationChangedError,
    GraphNode,
    GraphNodeNotFoundError,
    GraphPath,
    GraphPathResult,
    GraphProjectionNotFoundError,
    GraphProjectionNotReadyError,
    GraphQueryError,
    GraphQueryIntegrityError,
    GraphQueryLimitExceededError,
    GraphQueryTimeoutError,
    GraphReadScope,
    GraphRelationshipKind,
    GraphSchemaIncompatibleError,
    GraphSubgraph,
    GraphUnavailableError,
    GraphWindowRequest,
    NeighborhoodRequest,
    NodeDetailRequest,
    TraversalDirection,
)


def test_contract_version_and_vocabularies() -> None:
    assert P4_Q1_CONTRACT_VERSION == "1.0.0"

    # Directions
    assert set(TraversalDirection) == {"incoming", "outgoing", "both"}
    assert set(ContainmentDirection) == {"parents", "children", "both"}

    # Relationship kinds: exactly 13 approved kinds
    assert len(ALL_APPROVED_RELATIONSHIP_KINDS) == 13
    assert GraphRelationshipKind.CONTAINS in ALL_APPROVED_RELATIONSHIP_KINDS

    # 12 dependency kinds - CONTAINS is strictly excluded
    assert len(APPROVED_DEPENDENCY_RELATIONSHIP_KINDS) == 12
    assert GraphRelationshipKind.CONTAINS not in APPROVED_DEPENDENCY_RELATIONSHIP_KINDS
    assert (
        APPROVED_DEPENDENCY_RELATIONSHIP_KINDS | {GraphRelationshipKind.CONTAINS}
        == ALL_APPROVED_RELATIONSHIP_KINDS
    )


def test_approved_defaults_and_maxima() -> None:
    assert DEFAULT_QUERY_DEPTH == 1
    assert MAX_QUERY_DEPTH == 5
    assert DEFAULT_QUERY_NODES == 100
    assert MAX_QUERY_NODES == 500
    assert DEFAULT_QUERY_EDGES == 200
    assert MAX_QUERY_EDGES == 1_000
    assert DEFAULT_QUERY_PATHS == 5
    assert MAX_QUERY_PATHS == 25
    assert DEFAULT_QUERY_PAGE_SIZE == 50
    assert MAX_QUERY_PAGE_SIZE == 100
    assert DEFAULT_QUERY_TIMEOUT_SECONDS == 2.0
    assert MAX_QUERY_TIMEOUT_SECONDS == 5.0
    assert MAX_CURSOR_LENGTH == 2048


def test_graph_read_scope_immutability() -> None:
    scope = GraphReadScope(
        project_id=uuid4(),
        architecture_version_id=uuid4(),
        generation_id=uuid4(),
        resource_state="COMPLETED",
        graph_schema_version="1.0.0",
        projector_version="1.0.0",
        counts=ProjectionCounts(10, 20, 30, 0, 0),
    )
    with pytest.raises(ValidationError):
        scope.resource_state = "STALE"  # type: ignore[misc]


def test_graph_node_and_edge_immutability() -> None:
    node = GraphNode(
        architecture_entity_id=uuid4(),
        logical_id="backend.service",
        canonical_kind="service",
        name="AuthService",
        namespace="backend",
        fact_status="verified",
        semantic_signature="sig-123",
        evidence_logical_ids=("ev-1", "ev-2"),
        metadata={"layer": "application"},
    )
    with pytest.raises(ValidationError):
        node.name = "OtherService"  # type: ignore[misc]

    edge = GraphEdge(
        architecture_relationship_id=uuid4(),
        logical_id="rel-1",
        canonical_kind="calls",
        status="active",
        source_entity_id=node.architecture_entity_id,
        target_entity_id=uuid4(),
        evidence_logical_ids=("ev-1",),
        metadata={},
    )
    with pytest.raises(ValidationError):
        edge.canonical_kind = "depends_on"  # type: ignore[misc]


def test_graph_subgraph_and_path_result() -> None:
    scope = GraphReadScope(
        project_id=uuid4(),
        architecture_version_id=uuid4(),
        generation_id=uuid4(),
        resource_state="COMPLETED",
        graph_schema_version="1.0.0",
        projector_version="1.0.0",
        counts=ProjectionCounts(0, 0, 0, 0, 0),
    )
    subgraph = GraphSubgraph(
        scope=scope,
        nodes=(),
        edges=(),
        total_manifest_nodes=0,
        total_manifest_edges=0,
        loaded_nodes=0,
        loaded_edges=0,
        truncated=False,
        next_cursor=None,
    )
    assert subgraph.loaded_nodes == 0
    assert subgraph.truncated is False

    path = GraphPath(nodes=(), edges=(), hop_count=0)
    path_result = GraphPathResult(
        scope=scope,
        paths=(path,),
        total_paths_found=1,
        truncated=False,
    )
    assert path_result.total_paths_found == 1


def test_graph_window_request_validation() -> None:
    req = GraphWindowRequest(
        project_id=uuid4(),
        architecture_version_id=uuid4(),
        canonical_kinds=(
            GraphRelationshipKind.CALLS,
            GraphRelationshipKind.CALLS,
            GraphRelationshipKind.IMPORTS,
        ),
    )
    assert req.node_limit == DEFAULT_QUERY_NODES
    assert req.edge_limit == DEFAULT_QUERY_EDGES
    assert req.page_size == DEFAULT_QUERY_PAGE_SIZE
    # Duplicates removed, sorted canonically
    assert req.canonical_kinds == (
        GraphRelationshipKind.CALLS,
        GraphRelationshipKind.IMPORTS,
    )

    # Exceeding bounds
    with pytest.raises(ValidationError):
        GraphWindowRequest(
            project_id=uuid4(),
            architecture_version_id=uuid4(),
            node_limit=MAX_QUERY_NODES + 1,
        )

    with pytest.raises(ValidationError):
        GraphWindowRequest(
            project_id=uuid4(),
            architecture_version_id=uuid4(),
            timeout_seconds=MAX_QUERY_TIMEOUT_SECONDS + 0.1,
        )

    # Oversized cursor
    with pytest.raises(GraphQueryLimitExceededError):
        GraphWindowRequest(
            project_id=uuid4(),
            architecture_version_id=uuid4(),
            cursor="x" * 2049,
        )


def test_neighborhood_request_allows_explicit_contains() -> None:
    req = NeighborhoodRequest(
        project_id=uuid4(),
        architecture_version_id=uuid4(),
        entity_id=uuid4(),
        direction=TraversalDirection.OUTGOING,
        depth=3,
        relationship_kinds=(
            GraphRelationshipKind.CONTAINS,
            GraphRelationshipKind.CALLS,
        ),
    )
    assert req.direction == TraversalDirection.OUTGOING
    assert req.depth == 3
    assert req.relationship_kinds == (
        GraphRelationshipKind.CALLS,
        GraphRelationshipKind.CONTAINS,
    )


def test_dependencies_request_rejects_contains() -> None:
    with pytest.raises(
        GraphQueryLimitExceededError,
        match="Hierarchy kind 'contains' is not permitted",
    ):
        DependenciesRequest(
            project_id=uuid4(),
            architecture_version_id=uuid4(),
            entity_id=uuid4(),
            relationship_kinds=(
                GraphRelationshipKind.CALLS,
                GraphRelationshipKind.CONTAINS,
            ),
        )

    # Valid dependency kinds pass
    req = DependenciesRequest(
        project_id=uuid4(),
        architecture_version_id=uuid4(),
        entity_id=uuid4(),
        relationship_kinds=(GraphRelationshipKind.CALLS, GraphRelationshipKind.USES),
    )
    assert req.relationship_kinds == (
        GraphRelationshipKind.CALLS,
        GraphRelationshipKind.USES,
    )


def test_dependents_request_rejects_contains() -> None:
    with pytest.raises(
        GraphQueryLimitExceededError,
        match="Hierarchy kind 'contains' is not permitted",
    ):
        DependentsRequest(
            project_id=uuid4(),
            architecture_version_id=uuid4(),
            entity_id=uuid4(),
            relationship_kinds=(GraphRelationshipKind.CONTAINS,),
        )


def test_bounded_paths_request_rejects_contains_and_validates_depth() -> None:
    with pytest.raises(
        GraphQueryLimitExceededError,
        match="Hierarchy kind 'contains' is not permitted",
    ):
        BoundedPathsRequest(
            project_id=uuid4(),
            architecture_version_id=uuid4(),
            source_entity_id=uuid4(),
            target_entity_id=uuid4(),
            relationship_kinds=(GraphRelationshipKind.CONTAINS,),
        )

    with pytest.raises(ValidationError):
        BoundedPathsRequest(
            project_id=uuid4(),
            architecture_version_id=uuid4(),
            source_entity_id=uuid4(),
            target_entity_id=uuid4(),
            max_depth=6,  # MAX is 5
        )


def test_containment_request_validation() -> None:
    req = ContainmentRequest(
        project_id=uuid4(),
        architecture_version_id=uuid4(),
        entity_id=uuid4(),
        direction=ContainmentDirection.PARENTS,
    )
    assert req.direction == ContainmentDirection.PARENTS
    assert req.depth == DEFAULT_QUERY_DEPTH


def test_node_detail_request_validation() -> None:
    req = NodeDetailRequest(
        project_id=uuid4(),
        architecture_version_id=uuid4(),
        entity_id=uuid4(),
    )
    assert req.timeout_seconds == DEFAULT_QUERY_TIMEOUT_SECONDS


def test_error_taxonomy_codes_and_hierarchy() -> None:
    error_specs = [
        (GraphProjectionNotFoundError, "graph_projection_not_found"),
        (GraphProjectionNotReadyError, "graph_projection_not_ready"),
        (GraphNodeNotFoundError, "graph_node_not_found"),
        (GraphCursorInvalidError, "graph_cursor_invalid"),
        (GraphCursorScopeMismatchError, "graph_cursor_scope_mismatch"),
        (GraphCursorExpiredError, "graph_cursor_expired"),
        (GraphGenerationChangedError, "graph_generation_changed"),
        (GraphQueryLimitExceededError, "graph_query_limit_exceeded"),
        (GraphQueryTimeoutError, "graph_query_timeout"),
        (GraphUnavailableError, "graph_unavailable"),
        (GraphSchemaIncompatibleError, "graph_schema_incompatible"),
        (GraphQueryIntegrityError, "graph_query_integrity_error"),
    ]

    for err_cls, expected_code in error_specs:
        err = err_cls("test message", safe_details={"field": "value"})
        assert isinstance(err, GraphQueryError)
        assert err.code == expected_code
        assert err.message == "test message"
        assert err.safe_details == {"field": "value"}


def test_all_query_errors_exported_from_graph_root() -> None:
    import backend.platform.graph as graph_pkg

    error_classes = [
        GraphProjectionNotFoundError,
        GraphProjectionNotReadyError,
        GraphNodeNotFoundError,
        GraphCursorInvalidError,
        GraphCursorScopeMismatchError,
        GraphCursorExpiredError,
        GraphGenerationChangedError,
        GraphQueryLimitExceededError,
        GraphQueryTimeoutError,
        GraphUnavailableError,
        GraphSchemaIncompatibleError,
        GraphQueryIntegrityError,
    ]
    for err_cls in error_classes:
        assert getattr(graph_pkg, err_cls.__name__) is err_cls
        assert err_cls.__name__ in graph_pkg.__all__
