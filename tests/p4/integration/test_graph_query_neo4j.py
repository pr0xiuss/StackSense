"""Real Neo4j Community 5.26.33 integration tests for M3 query engine.

Validates:
1. Manifest preflight (READY, BUILDING, missing, schema incompatibility).
2. Exact-scope single node inspection (get_node_detail).
3. Keyset-paginated node window and induced edges (query_window).
4. Structural expansion (query_neighborhood) with direction and explicit containment.
5. Outgoing dependency traversal (query_dependencies) excluding containment.
6. Incoming dependent traversal (query_dependents) preserving source->target direction.
7. Containment hierarchy navigation (query_containment) traversing only contains.
8. Directed simple paths up to depth 5 (query_bounded_paths).
9. Generation coexistence and cross-generation isolation (G1 vs G2).
10. Transaction timeout enforcement and error mapping.
"""

from __future__ import annotations

import os
import time
from collections.abc import Generator
from typing import Any
from uuid import UUID, uuid4

import pytest
from dotenv import dotenv_values
from neo4j import Driver
from neo4j.exceptions import TransientError
from pydantic import SecretStr

from backend.platform.config import Settings
from backend.platform.graph.cursor import encode_cursor
from backend.platform.graph.model import (
    GRAPH_SCHEMA_VERSION,
    PROJECTOR_VERSION,
    ProjectionCounts,
)
from backend.platform.graph.neo4j import Neo4jInfrastructure
from backend.platform.graph.projection import (
    MANIFEST_STATE_BUILDING,
    MANIFEST_STATE_READY,
    compute_edge_key,
    compute_generation_key,
    compute_node_key,
)
from backend.platform.graph.query_contracts import (
    BoundedPathsRequest,
    ContainmentDirection,
    ContainmentRequest,
    DependenciesRequest,
    DependentsRequest,
    GraphNodeNotFoundError,
    GraphProjectionNotReadyError,
    GraphQueryTimeoutError,
    GraphReadScope,
    GraphRelationshipKind,
    GraphSchemaIncompatibleError,
    GraphWindowRequest,
    NeighborhoodRequest,
    NodeDetailRequest,
    TraversalDirection,
)
from backend.platform.graph.query_repository import Neo4jGraphQueryRepository


def _integration_settings() -> Settings:
    uri = os.getenv("NEO4J_TEST_URI") or os.getenv("NEO4J_URI")
    password = os.getenv("NEO4J_TEST_PASSWORD") or os.getenv("NEO4J_PASSWORD")
    if not uri or not password:
        dotenv_vals = dotenv_values(".env")
        uri = dotenv_vals.get("NEO4J_URI")
        password = dotenv_vals.get("NEO4J_PASSWORD")
    if not uri or not password:
        pytest.skip("Neo4j URI and password required for integration tests")

    return Settings(
        neo4j_uri=uri,
        neo4j_user=os.getenv("NEO4J_TEST_USER", "neo4j"),
        neo4j_password=SecretStr(password),
        neo4j_database=os.getenv("NEO4J_TEST_DATABASE", "neo4j"),
        graph_query_max_timeout_seconds=5.0,
    )


@pytest.fixture(scope="module")
def neo4j_env() -> Generator[tuple[Driver, Settings]]:
    settings = _integration_settings()
    infra = Neo4jInfrastructure(settings)
    try:
        infra.initialize()
        yield infra.driver, settings
    finally:
        infra.close()


def _make_scope(
    *,
    project_id: UUID | None = None,
    architecture_version_id: UUID | None = None,
    generation_id: UUID | None = None,
    schema_version: str = GRAPH_SCHEMA_VERSION,
    projector_version: str = PROJECTOR_VERSION,
) -> GraphReadScope:
    return GraphReadScope(
        project_id=project_id or uuid4(),
        architecture_version_id=architecture_version_id or uuid4(),
        generation_id=generation_id or uuid4(),
        resource_state="COMPLETED",
        graph_schema_version=schema_version,
        projector_version=projector_version,
        counts=ProjectionCounts(
            entities=6,
            relationships=7,
            evidence=1,
            unresolved=0,
            conflicts=0,
        ),
    )


class GraphFixtureData:
    def __init__(
        self,
        scope: GraphReadScope,
        node_ids: dict[str, UUID],
        edge_ids: dict[str, UUID],
    ) -> None:
        self.scope = scope
        self.node_ids = node_ids
        self.edge_ids = edge_ids


@pytest.fixture
def test_graph(
    neo4j_env: tuple[Driver, Settings],
) -> Generator[GraphFixtureData]:
    driver, settings = neo4j_env
    scope = _make_scope()
    p_id = str(scope.project_id).lower()
    a_id = str(scope.architecture_version_id).lower()
    g_id = str(scope.generation_id).lower()
    gen_key = compute_generation_key(p_id, a_id, g_id)

    # Define 6 nodes
    node_names = [
        "Gateway",
        "AuthService",
        "UserService",
        "Database",
        "Cache",
        "CoreModule",
    ]
    node_kinds = ["service", "service", "service", "datastore", "cache", "module"]
    node_ids = {name: uuid4() for name in node_names}
    node_pks = {
        name: compute_node_key(p_id, a_id, g_id, f"logical.{name}")
        for name in node_names
    }

    # Define relationships
    # 1. Gateway -> AuthService (calls)
    # 2. AuthService -> UserService (calls)
    # 3. UserService -> Database (calls)
    # 4. AuthService -> Cache (uses)
    # 5. CoreModule -> AuthService (contains)
    # 6. CoreModule -> UserService (contains)
    # 7. UserService -> Gateway (calls - cycle!)
    edges_def = [
        ("Gateway", "AuthService", "calls", GraphRelationshipKind.CALLS),
        ("AuthService", "UserService", "calls", GraphRelationshipKind.CALLS),
        ("UserService", "Database", "calls", GraphRelationshipKind.CALLS),
        ("AuthService", "Cache", "uses", GraphRelationshipKind.USES),
        ("CoreModule", "AuthService", "contains", GraphRelationshipKind.CONTAINS),
        ("CoreModule", "UserService", "contains", GraphRelationshipKind.CONTAINS),
        ("UserService", "Gateway", "calls_cycle", GraphRelationshipKind.CALLS),
    ]
    edge_ids = {f"{s}->{t}:{name}": uuid4() for s, t, name, _ in edges_def}

    with driver.session(database=settings.neo4j_database) as session:
        # Write READY manifest
        session.run(
            "CREATE (m:ProjectionManifest { "
            "    project_id: $project_id, "
            "    architecture_version_id: $architecture_version_id, "
            "    generation_id: $generation_id, "
            "    generation_key: $generation_key, "
            "    state: $state, "
            "    graph_schema_version: $schema_ver, "
            "    projector_version: $projector_ver "
            "})",
            project_id=p_id,
            architecture_version_id=a_id,
            generation_id=g_id,
            generation_key=gen_key,
            state=MANIFEST_STATE_READY,
            schema_ver=GRAPH_SCHEMA_VERSION,
            projector_ver=PROJECTOR_VERSION,
        )

        # Write nodes
        for name, kind in zip(node_names, node_kinds, strict=True):
            session.run(
                "CREATE (n:ArchitectureEntity { "
                "    project_id: $project_id, "
                "    architecture_version_id: $architecture_version_id, "
                "    generation_id: $generation_id, "
                "    generation_key: $generation_key, "
                "    projection_key: $projection_key, "
                "    architecture_entity_id: $entity_id, "
                "    logical_id: $logical_id, "
                "    canonical_kind: $canonical_kind, "
                "    name: $name, "
                "    namespace: 'com.example', "
                "    fact_status: 'canonical', "
                "    semantic_signature: 'sig-test', "
                "    evidence_logical_ids: ['ev-node-1'], "
                "    custom_tag: 'test' "
                "})",
                project_id=p_id,
                architecture_version_id=a_id,
                generation_id=g_id,
                generation_key=gen_key,
                projection_key=node_pks[name],
                entity_id=str(node_ids[name]).lower(),
                logical_id=f"logical.{name}",
                canonical_kind=kind,
                name=name,
            )

        # Write edges
        for s, t, rel_name, rel_kind in edges_def:
            rel_key = f"{s}->{t}:{rel_name}"
            e_id = edge_ids[rel_key]
            e_pk = compute_edge_key(p_id, a_id, g_id, f"rel.{rel_key}")
            session.run(
                "MATCH (src:ArchitectureEntity { projection_key: $src_pk }), "
                "      (tgt:ArchitectureEntity { projection_key: $tgt_pk }) "
                "CREATE (src)-[r:ARCH_RELATIONSHIP { "
                "    project_id: $project_id, "
                "    architecture_version_id: $architecture_version_id, "
                "    generation_id: $generation_id, "
                "    generation_key: $generation_key, "
                "    projection_key: $projection_key, "
                "    architecture_relationship_id: $relationship_id, "
                "    logical_id: $logical_id, "
                "    canonical_kind: $canonical_kind, "
                "    status: 'canonical', "
                "    source_projection_key: $src_pk, "
                "    target_projection_key: $tgt_pk, "
                "    evidence_logical_ids: ['ev-edge-1'] "
                "}]->(tgt)",
                project_id=p_id,
                architecture_version_id=a_id,
                generation_id=g_id,
                generation_key=gen_key,
                projection_key=e_pk,
                src_pk=node_pks[s],
                tgt_pk=node_pks[t],
                relationship_id=str(e_id).lower(),
                logical_id=f"rel.{rel_key}",
                canonical_kind=rel_kind.value,
            )

    yield GraphFixtureData(scope, node_ids, edge_ids)

    # Cleanup test generation
    with driver.session(database=settings.neo4j_database) as session:
        session.run(
            "MATCH (n:ArchitectureEntity { generation_id: $g_id }) DETACH DELETE n",
            g_id=g_id,
        )
        session.run(
            "MATCH (m:ProjectionManifest { generation_id: $g_id }) DELETE m",
            g_id=g_id,
        )


def test_real_neo4j_manifest_preflight(
    neo4j_env: tuple[Driver, Settings],
    test_graph: GraphFixtureData,
) -> None:
    driver, settings = neo4j_env
    repo = Neo4jGraphQueryRepository(driver, database=settings.neo4j_database)

    # 1. Ready manifest succeeds
    assert repo.verify_manifest_ready(test_graph.scope, timeout_seconds=5.0) is True

    # 2. Incompatible schema version raises GraphSchemaIncompatibleError
    incompatible_scope = _make_scope(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        generation_id=test_graph.scope.generation_id,
        schema_version="9.9.9",
    )
    with pytest.raises(GraphSchemaIncompatibleError):
        repo.verify_manifest_ready(incompatible_scope, timeout_seconds=5.0)

    # 3. Incompatible projector version also fails closed.
    incompatible_projector_scope = _make_scope(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        generation_id=test_graph.scope.generation_id,
        projector_version="9.9.9",
    )
    with pytest.raises(GraphSchemaIncompatibleError):
        repo.verify_manifest_ready(incompatible_projector_scope, timeout_seconds=5.0)

    # 4. Missing generation raises GraphProjectionNotReadyError
    missing_scope = _make_scope()
    with pytest.raises(GraphProjectionNotReadyError):
        repo.verify_manifest_ready(missing_scope, timeout_seconds=5.0)


def test_real_neo4j_manifest_building_state_raises(
    neo4j_env: tuple[Driver, Settings],
) -> None:
    driver, settings = neo4j_env
    repo = Neo4jGraphQueryRepository(driver, database=settings.neo4j_database)
    scope = _make_scope()
    p_id = str(scope.project_id).lower()
    a_id = str(scope.architecture_version_id).lower()
    g_id = str(scope.generation_id).lower()
    gen_key = compute_generation_key(p_id, a_id, g_id)

    with driver.session(database=settings.neo4j_database) as session:
        session.run(
            "CREATE (m:ProjectionManifest { "
            "    project_id: $project_id, "
            "    architecture_version_id: $architecture_version_id, "
            "    generation_id: $generation_id, "
            "    generation_key: $generation_key, "
            "    state: $state, "
            "    graph_schema_version: $schema_ver, "
            "    projector_version: $projector_ver "
            "})",
            project_id=p_id,
            architecture_version_id=a_id,
            generation_id=g_id,
            generation_key=gen_key,
            state=MANIFEST_STATE_BUILDING,
            schema_ver=GRAPH_SCHEMA_VERSION,
            projector_ver=PROJECTOR_VERSION,
        )

    try:
        with pytest.raises(GraphProjectionNotReadyError, match="not ready"):
            repo.verify_manifest_ready(scope, timeout_seconds=5.0)
    finally:
        with driver.session(database=settings.neo4j_database) as session:
            session.run(
                "MATCH (m:ProjectionManifest { generation_id: $g_id }) DELETE m",
                g_id=g_id,
            )


def test_real_neo4j_get_node_detail(
    neo4j_env: tuple[Driver, Settings],
    test_graph: GraphFixtureData,
) -> None:
    driver, settings = neo4j_env
    repo = Neo4jGraphQueryRepository(driver, database=settings.neo4j_database)

    gateway_id = test_graph.node_ids["Gateway"]
    req = NodeDetailRequest(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        entity_id=gateway_id,
    )
    node = repo.get_node_detail(test_graph.scope, req, timeout_seconds=5.0)

    assert node is not None
    assert node.architecture_entity_id == gateway_id
    assert node.name == "Gateway"
    assert node.canonical_kind == "service"
    assert node.metadata.get("custom_tag") == "test"
    # Ensure internal projection keys are stripped
    assert "projection_key" not in node.metadata
    assert "generation_key" not in node.metadata

    # Missing node returns None
    missing_req = NodeDetailRequest(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        entity_id=uuid4(),
    )
    assert (
        repo.get_node_detail(test_graph.scope, missing_req, timeout_seconds=5.0) is None
    )


def test_real_neo4j_query_window_and_pagination(
    neo4j_env: tuple[Driver, Settings],
    test_graph: GraphFixtureData,
) -> None:
    driver, settings = neo4j_env
    repo = Neo4jGraphQueryRepository(driver, database=settings.neo4j_database)

    # Page 1: limit 3 nodes
    req = GraphWindowRequest(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        node_limit=3,
        edge_limit=10,
    )
    subgraph, next_pos = repo.query_window(
        test_graph.scope, req, None, timeout_seconds=5.0
    )

    assert len(subgraph.nodes) == 3
    assert subgraph.truncated is True
    assert next_pos is not None
    assert "node_cursor" in next_pos

    # Page 2: advance cursor
    req2 = GraphWindowRequest(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        node_limit=3,
        edge_limit=10,
    )
    subgraph2, next_pos2 = repo.query_window(
        test_graph.scope, req2, next_pos, timeout_seconds=5.0
    )
    assert len(subgraph2.nodes) == 3
    # Distinct node IDs across pages
    page1_ids = {n.architecture_entity_id for n in subgraph.nodes}
    page2_ids = {n.architecture_entity_id for n in subgraph2.nodes}
    assert page1_ids.isdisjoint(page2_ids)


def test_real_neo4j_dense_window_continuation_is_compact_and_complete(
    neo4j_env: tuple[Driver, Settings],
    test_graph: GraphFixtureData,
) -> None:
    driver, settings = neo4j_env
    repo = Neo4jGraphQueryRepository(driver, database=settings.neo4j_database)
    request = GraphWindowRequest(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        node_limit=5,
        edge_limit=1,
        page_size=5,
    )

    position: dict[str, Any] | None = None
    seen_node_ids: set[UUID] = set()
    for _ in range(20):
        subgraph, position = repo.query_window(
            test_graph.scope,
            request,
            position,
            timeout_seconds=5.0,
        )
        page_node_ids = {node.architecture_entity_id for node in subgraph.nodes}
        seen_node_ids.update(page_node_ids)
        assert all(
            edge.source_entity_id in page_node_ids
            and edge.target_entity_id in page_node_ids
            for edge in subgraph.edges
        )

        if position is None:
            break
        assert "window_node_keys" not in position
        encode_cursor(
            scope=test_graph.scope,
            operation="window",
            fingerprint="f" * 64,
            position=position,
            secret_key="dense-window-test-secret-key-32-bytes",
        )
    else:
        pytest.fail("window continuation did not terminate")

    assert seen_node_ids == set(test_graph.node_ids.values())


def test_real_neo4j_query_neighborhood(
    neo4j_env: tuple[Driver, Settings],
    test_graph: GraphFixtureData,
) -> None:
    driver, settings = neo4j_env
    repo = Neo4jGraphQueryRepository(driver, database=settings.neo4j_database)
    auth_id = test_graph.node_ids["AuthService"]

    # Outgoing depth 1 without containment -> finds UserService (calls) and Cache (uses)
    req = NeighborhoodRequest(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        entity_id=auth_id,
        direction=TraversalDirection.OUTGOING,
        depth=1,
    )
    subgraph, _ = repo.query_neighborhood(
        test_graph.scope, req, None, timeout_seconds=5.0
    )
    node_names = {n.name for n in subgraph.nodes}
    assert "AuthService" in node_names
    assert "UserService" in node_names
    assert "Cache" in node_names
    assert "Gateway" not in node_names  # Incoming calls
    assert "CoreModule" not in node_names  # Incoming contains

    # Both direction with explicit containment
    req_both = NeighborhoodRequest(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        entity_id=auth_id,
        direction=TraversalDirection.BOTH,
        depth=1,
        relationship_kinds=(
            GraphRelationshipKind.CALLS,
            GraphRelationshipKind.USES,
            GraphRelationshipKind.CONTAINS,
        ),
    )
    subgraph_both, _ = repo.query_neighborhood(
        test_graph.scope, req_both, None, timeout_seconds=5.0
    )
    both_names = {n.name for n in subgraph_both.nodes}
    assert "AuthService" in both_names
    assert "UserService" in both_names
    assert "Cache" in both_names
    assert "Gateway" in both_names  # Incoming calls
    assert "CoreModule" in both_names  # Incoming contains


def test_real_neo4j_traversal_continuation_preserves_edges_and_endpoint_closure(
    neo4j_env: tuple[Driver, Settings],
    test_graph: GraphFixtureData,
) -> None:
    driver, settings = neo4j_env
    repo = Neo4jGraphQueryRepository(driver, database=settings.neo4j_database)
    request = NeighborhoodRequest(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        entity_id=test_graph.node_ids["AuthService"],
        direction=TraversalDirection.OUTGOING,
        depth=1,
        node_limit=2,
        edge_limit=1,
    )

    position: dict[str, Any] | None = None
    seen_edges: set[UUID] = set()
    for _ in range(4):
        subgraph, position = repo.query_neighborhood(
            test_graph.scope,
            request,
            position,
            timeout_seconds=5.0,
        )
        page_nodes = {node.architecture_entity_id for node in subgraph.nodes}
        assert all(
            edge.source_entity_id in page_nodes and edge.target_entity_id in page_nodes
            for edge in subgraph.edges
        )
        page_edges = {edge.architecture_relationship_id for edge in subgraph.edges}
        assert seen_edges.isdisjoint(page_edges)
        seen_edges.update(page_edges)
        if position is None:
            break
    else:
        pytest.fail("traversal continuation did not terminate")

    assert seen_edges == {
        test_graph.edge_ids["AuthService->UserService:calls"],
        test_graph.edge_ids["AuthService->Cache:uses"],
    }


def test_real_neo4j_query_dependencies(
    neo4j_env: tuple[Driver, Settings],
    test_graph: GraphFixtureData,
) -> None:
    driver, settings = neo4j_env
    repo = Neo4jGraphQueryRepository(driver, database=settings.neo4j_database)
    gateway_id = test_graph.node_ids["Gateway"]

    # Gateway -> AuthService (depth 1) -> UserService, Cache (depth 2)
    # -> Database (depth 3)
    req = DependenciesRequest(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        entity_id=gateway_id,
        depth=3,
    )
    subgraph, _ = repo.query_dependencies(
        test_graph.scope, req, None, timeout_seconds=5.0
    )
    names = {n.name for n in subgraph.nodes}
    assert "Gateway" in names
    assert "AuthService" in names
    assert "UserService" in names
    assert "Cache" in names
    assert "Database" in names
    assert "CoreModule" not in names  # Contains never returned


def test_real_neo4j_query_dependents(
    neo4j_env: tuple[Driver, Settings],
    test_graph: GraphFixtureData,
) -> None:
    driver, settings = neo4j_env
    repo = Neo4jGraphQueryRepository(driver, database=settings.neo4j_database)
    db_id = test_graph.node_ids["Database"]

    # Database <- UserService (depth 1) <- AuthService (depth 2) <- Gateway (depth 3)
    req = DependentsRequest(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        entity_id=db_id,
        depth=3,
    )
    subgraph, _ = repo.query_dependents(
        test_graph.scope, req, None, timeout_seconds=5.0
    )
    names = {n.name for n in subgraph.nodes}
    assert "Database" in names
    assert "UserService" in names
    assert "AuthService" in names
    assert "Gateway" in names
    assert "CoreModule" not in names

    # Verify edge direction: source is dependent (UserService),
    # target is dependency (Database)
    for edge in subgraph.edges:
        if edge.target_entity_id == db_id:
            assert edge.source_entity_id == test_graph.node_ids["UserService"]


def test_real_neo4j_query_containment(
    neo4j_env: tuple[Driver, Settings],
    test_graph: GraphFixtureData,
) -> None:
    driver, settings = neo4j_env
    repo = Neo4jGraphQueryRepository(driver, database=settings.neo4j_database)
    core_id = test_graph.node_ids["CoreModule"]
    auth_id = test_graph.node_ids["AuthService"]

    # Children of CoreModule -> AuthService and UserService
    req_children = ContainmentRequest(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        entity_id=core_id,
        direction=ContainmentDirection.CHILDREN,
        depth=1,
    )
    subgraph_children, _ = repo.query_containment(
        test_graph.scope, req_children, None, timeout_seconds=5.0
    )
    child_names = {n.name for n in subgraph_children.nodes}
    assert child_names == {"CoreModule", "AuthService", "UserService"}

    # Parents of AuthService -> CoreModule
    req_parents = ContainmentRequest(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        entity_id=auth_id,
        direction=ContainmentDirection.PARENTS,
        depth=1,
    )
    subgraph_parents, _ = repo.query_containment(
        test_graph.scope, req_parents, None, timeout_seconds=5.0
    )
    parent_names = {n.name for n in subgraph_parents.nodes}
    assert parent_names == {"AuthService", "CoreModule"}


def test_real_neo4j_query_bounded_paths(
    neo4j_env: tuple[Driver, Settings],
    test_graph: GraphFixtureData,
) -> None:
    driver, settings = neo4j_env
    repo = Neo4jGraphQueryRepository(driver, database=settings.neo4j_database)
    gateway_id = test_graph.node_ids["Gateway"]
    db_id = test_graph.node_ids["Database"]

    # Gateway -> AuthService -> UserService -> Database (hop count 3)
    req = BoundedPathsRequest(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        source_entity_id=gateway_id,
        target_entity_id=db_id,
        max_depth=4,
    )
    result = repo.query_bounded_paths(test_graph.scope, req, timeout_seconds=5.0)

    assert result.total_paths_found == 1
    assert result.paths[0].hop_count == 3
    path_node_names = [n.name for n in result.paths[0].nodes]
    assert path_node_names == ["Gateway", "AuthService", "UserService", "Database"]
    assert len(result.paths[0].edges) == 3

    # Same source and target entity -> 0-hop path with 1 node
    same_req = BoundedPathsRequest(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        source_entity_id=gateway_id,
        target_entity_id=gateway_id,
        max_depth=3,
    )
    same_result = repo.query_bounded_paths(
        test_graph.scope, same_req, timeout_seconds=5.0
    )
    assert same_result.total_paths_found == 1
    assert same_result.paths[0].hop_count == 0
    assert len(same_result.paths[0].nodes) == 1

    # Missing node raises GraphNodeNotFoundError
    missing_req = BoundedPathsRequest(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        source_entity_id=gateway_id,
        target_entity_id=uuid4(),
        max_depth=3,
    )
    with pytest.raises(GraphNodeNotFoundError):
        repo.query_bounded_paths(test_graph.scope, missing_req, timeout_seconds=5.0)


def test_real_neo4j_coexisting_generations_isolation(
    neo4j_env: tuple[Driver, Settings],
    test_graph: GraphFixtureData,
) -> None:
    driver, settings = neo4j_env
    repo = Neo4jGraphQueryRepository(driver, database=settings.neo4j_database)

    # Create coexisting generation G2 under same project and version
    g2_scope = _make_scope(
        project_id=test_graph.scope.project_id,
        architecture_version_id=test_graph.scope.architecture_version_id,
        generation_id=uuid4(),
    )
    p_id = str(g2_scope.project_id).lower()
    a_id = str(g2_scope.architecture_version_id).lower()
    g2_id = str(g2_scope.generation_id).lower()
    gen_key_2 = compute_generation_key(p_id, a_id, g2_id)
    g2_node_id = uuid4()
    g2_pk = compute_node_key(p_id, a_id, g2_id, "logical.G2UniqueService")

    with driver.session(database=settings.neo4j_database) as session:
        session.run(
            "CREATE (m:ProjectionManifest { "
            "    project_id: $p_id, "
            "    architecture_version_id: $a_id, "
            "    generation_id: $g2_id, "
            "    generation_key: $gen_key, "
            "    state: $state, "
            "    graph_schema_version: $schema_ver, "
            "    projector_version: $projector_ver "
            "})",
            p_id=p_id,
            a_id=a_id,
            g2_id=g2_id,
            gen_key=gen_key_2,
            state=MANIFEST_STATE_READY,
            schema_ver=GRAPH_SCHEMA_VERSION,
            projector_ver=PROJECTOR_VERSION,
        )
        session.run(
            "CREATE (n:ArchitectureEntity { "
            "    project_id: $p_id, "
            "    architecture_version_id: $a_id, "
            "    generation_id: $g2_id, "
            "    generation_key: $gen_key, "
            "    projection_key: $pk, "
            "    architecture_entity_id: $entity_id, "
            "    logical_id: 'logical.G2UniqueService', "
            "    canonical_kind: 'service', "
            "    name: 'G2UniqueService', "
            "    namespace: 'com.example', "
            "    fact_status: 'canonical', "
            "    semantic_signature: 'sig-g2' "
            "})",
            p_id=p_id,
            a_id=a_id,
            g2_id=g2_id,
            gen_key=gen_key_2,
            pk=g2_pk,
            entity_id=str(g2_node_id).lower(),
        )

    try:
        # G1 window query does NOT see G2UniqueService
        req_g1 = GraphWindowRequest(
            project_id=test_graph.scope.project_id,
            architecture_version_id=test_graph.scope.architecture_version_id,
            node_limit=50,
        )
        g1_subgraph, _ = repo.query_window(
            test_graph.scope, req_g1, None, timeout_seconds=5.0
        )
        g1_names = {n.name for n in g1_subgraph.nodes}
        assert "G2UniqueService" not in g1_names

        # G2 window query ONLY sees G2UniqueService
        req_g2 = GraphWindowRequest(
            project_id=g2_scope.project_id,
            architecture_version_id=g2_scope.architecture_version_id,
            node_limit=50,
        )
        g2_subgraph, _ = repo.query_window(g2_scope, req_g2, None, timeout_seconds=5.0)
        g2_names = {n.name for n in g2_subgraph.nodes}
        assert g2_names == {"G2UniqueService"}
    finally:
        with driver.session(database=settings.neo4j_database) as session:
            session.run(
                "MATCH (n:ArchitectureEntity { generation_id: $g2_id }) "
                "DETACH DELETE n",
                g2_id=g2_id,
            )
            session.run(
                "MATCH (m:ProjectionManifest { generation_id: $g2_id }) DELETE m",
                g2_id=g2_id,
            )


def test_real_neo4j_error_mapping_transaction_timeout(
    neo4j_env: tuple[Driver, Settings],
) -> None:
    driver, settings = neo4j_env
    repo = Neo4jGraphQueryRepository(driver, database=settings.neo4j_database)

    err = TransientError("Database transaction timed out")
    with pytest.raises(GraphQueryTimeoutError, match="timed out"):
        repo._handle_neo4j_error(err)


def test_real_neo4j_deadline_cancels_server_work(
    neo4j_env: tuple[Driver, Settings],
) -> None:
    driver, settings = neo4j_env
    repo = Neo4jGraphQueryRepository(driver, database=settings.neo4j_database)
    started = time.monotonic()

    with pytest.raises(GraphQueryTimeoutError):
        with repo._bounded_transaction(0.02) as (tx, _):
            tx.run("UNWIND range(1, 100000000) AS n RETURN sum(n) AS total").consume()

    # The driver may spend a bounded interval closing the cancelled Bolt
    # connection, but the intentionally huge query must not run to completion.
    assert time.monotonic() - started < 1.5
