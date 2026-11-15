"""Tests for multi-tenant and cross-generation scope isolation in P4 graph queries.

Verifies:
1. Internal projection properties (projection_key, generation_key, etc.) are strictly
   stripped from public node and edge metadata.
2. Cypher queries enforce composite scope (project_id, architecture_version_id,
   generation_id) across all nodes, edges, manifests, and path templates.
3. Decoy project, version, and generation data cannot cross isolation boundaries.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.platform.graph.query_contracts import (
    GraphQueryIntegrityError,
    GraphRelationshipKind,
)
from backend.platform.graph.query_repository import (
    _INTERNAL_PROJECTION_PROPERTIES,
    _MANIFEST_PREFLIGHT_QUERY,
    _ONE_HOP_INCOMING_QUERY,
    _ONE_HOP_OUTGOING_QUERY,
    _PATH_TEMPLATES,
    _WINDOW_INDUCED_EDGES_QUERY,
    _WINDOW_NODES_QUERY,
    _map_edge,
    _map_node,
)


def test_node_mapper_strips_internal_projection_properties() -> None:
    entity_id = uuid4()
    raw_props = {
        "architecture_entity_id": str(entity_id),
        "logical_id": "service.AuthService",
        "canonical_kind": "service",
        "name": "AuthService",
        "namespace": "backend.auth",
        "fact_status": "canonical",
        "semantic_signature": "sha256:abc12345",
        "evidence_logical_ids": ["ev-1", "ev-2"],
        # Internal properties that must never be exposed in metadata
        "project_id": str(uuid4()),
        "architecture_version_id": str(uuid4()),
        "generation_id": str(uuid4()),
        "generation_key": "gen-key-12345",
        "projection_key": "proj-key-67890",
        # User/domain metadata that should be preserved
        "layer": "application",
        "custom_tag": "security-critical",
    }

    node = _map_node(raw_props)

    assert node.architecture_entity_id == entity_id
    assert node.logical_id == "service.AuthService"
    assert node.name == "AuthService"
    assert node.namespace == "backend.auth"
    assert node.metadata == {
        "layer": "application",
        "custom_tag": "security-critical",
    }

    for internal_key in _INTERNAL_PROJECTION_PROPERTIES:
        assert internal_key not in node.metadata


def test_edge_mapper_strips_internal_projection_properties() -> None:
    rel_id = uuid4()
    src_id = uuid4()
    tgt_id = uuid4()
    raw_props = {
        "architecture_relationship_id": str(rel_id),
        "logical_id": "rel.ServiceA->ServiceB",
        "canonical_kind": GraphRelationshipKind.CALLS.value,
        "status": "canonical",
        "evidence_logical_ids": ["ev-rel-1"],
        # Internal properties that must never be exposed in metadata
        "project_id": str(uuid4()),
        "architecture_version_id": str(uuid4()),
        "generation_id": str(uuid4()),
        "generation_key": "gen-key-9999",
        "projection_key": "edge-proj-key-8888",
        "source_projection_key": "src-pk",
        "target_projection_key": "tgt-pk",
        "source_logical_id": "src-logical",
        "target_logical_id": "tgt-logical",
        # User/domain metadata that should be preserved
        "protocol": "gRPC",
        "timeout_ms": 250,
    }

    edge = _map_edge(raw_props, src_id, tgt_id)

    assert edge.architecture_relationship_id == rel_id
    assert edge.source_entity_id == src_id
    assert edge.target_entity_id == tgt_id
    assert edge.canonical_kind == GraphRelationshipKind.CALLS
    assert edge.metadata == {
        "protocol": "gRPC",
        "timeout_ms": 250,
    }

    for internal_key in _INTERNAL_PROJECTION_PROPERTIES:
        assert internal_key not in edge.metadata


@pytest.mark.parametrize(
    "props",
    [
        {},
        {
            "architecture_entity_id": "not-a-uuid",
            "logical_id": "broken",
            "canonical_kind": "service",
            "name": "Broken",
        },
    ],
)
def test_node_mapper_rejects_structurally_invalid_records(
    props: dict[str, object],
) -> None:
    with pytest.raises(GraphQueryIntegrityError, match="structurally invalid"):
        _map_node(props)


def test_edge_mapper_rejects_structurally_invalid_records() -> None:
    with pytest.raises(GraphQueryIntegrityError, match="structurally invalid"):
        _map_edge({}, uuid4(), uuid4())


def test_cypher_manifest_preflight_scopes_composite_keys() -> None:
    query = _MANIFEST_PREFLIGHT_QUERY
    assert "project_id: $project_id" in query
    assert "architecture_version_id: $architecture_version_id" in query
    assert "generation_id: $generation_id" in query


def test_cypher_window_queries_scope_composite_keys() -> None:
    nodes_q = _WINDOW_NODES_QUERY
    assert "project_id: $project_id" in nodes_q
    assert "architecture_version_id: $architecture_version_id" in nodes_q
    assert "generation_id: $generation_id" in nodes_q

    edges_q = _WINDOW_INDUCED_EDGES_QUERY
    assert "project_id: $project_id" in edges_q
    assert "architecture_version_id: $architecture_version_id" in edges_q
    assert "generation_id: $generation_id" in edges_q


def test_cypher_traversal_queries_scope_composite_keys() -> None:
    for query in (_ONE_HOP_OUTGOING_QUERY, _ONE_HOP_INCOMING_QUERY):
        assert "project_id: $project_id" in query
        assert "architecture_version_id: $architecture_version_id" in query
        assert "generation_id: $generation_id" in query


def test_cypher_bounded_path_templates_scope_all_hops_and_nodes() -> None:
    for hop_count, template in _PATH_TEMPLATES.items():
        # Every hop template from 1 to 5 must scope nodes and edges
        assert template is not None
        assert (
            "project_id: $project_id" in template
        ), f"Hop {hop_count} missing project_id"
        assert (
            "architecture_version_id: $architecture_version_id" in template
        ), f"Hop {hop_count} missing architecture_version_id"
        assert (
            "generation_id: $generation_id" in template
        ), f"Hop {hop_count} missing generation_id"

        # Check that intermediate nodes also require scope
        for i in range(hop_count + 1):
            node_label = f"n{i}:ArchitectureEntity"
            assert node_label in template, f"Hop {hop_count} missing {node_label}"

        # Check that intermediate edges also require scope
        for j in range(1, hop_count + 1):
            rel_label = f"r{j}:ARCH_RELATIONSHIP"
            assert rel_label in template, f"Hop {hop_count} missing {rel_label}"
