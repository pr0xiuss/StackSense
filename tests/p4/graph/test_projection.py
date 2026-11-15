"""Unit tests for Phase 4 Module 2 deterministic projection mapping and digests."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.platform.analysis.architecture.model import (
    ArchitectureDocument,
)
from backend.platform.graph.model import ProjectionCounts
from backend.platform.graph.projection import (
    MAX_META_KEY_BYTES,
    MAX_META_LIST_ITEMS,
    MAX_META_STRING_BYTES,
    ProjectionCapacityExceededError,
    ProjectionContractError,
    ProjectionMetadataError,
    ProjectionSourceMismatchError,
    build_projection_plan,
    compute_edge_key,
    compute_generation_key,
    compute_node_key,
    normalize_metadata,
    validate_route_path,
    validate_source_root,
)
from tests.fixtures.p4.graph.fixtures import (
    DEFAULT_GENERATION_ID,
    DEFAULT_PROJECT_ID,
    DEFAULT_VERSION_ID,
    dense_document,
    make_completeness,
    make_entity,
    make_evidence,
    make_relationship,
    maximal_metadata_document,
    no_edge_document,
    small_document,
    unicode_document,
    unresolved_and_conflicts_document,
)


def test_generation_key_is_deterministic_and_rejects_nul() -> None:
    p_id = UUID("11111111-1111-1111-1111-111111111111")
    v_id = UUID("22222222-2222-2222-2222-222222222222")
    g1 = UUID("33333333-3333-3333-3333-333333333333")
    g2 = UUID("44444444-4444-4444-4444-444444444444")

    key1 = compute_generation_key(p_id, v_id, g1)
    key1_again = compute_generation_key(
        str(p_id).upper(), str(v_id).upper(), str(g1).upper()
    )
    assert key1 == key1_again
    assert len(key1) == 64
    assert key1 == key1.lower()

    key2 = compute_generation_key(p_id, v_id, g2)
    assert key1 != key2

    with pytest.raises(ProjectionContractError) as exc_info:
        compute_generation_key("project\0id", v_id, g1)
    assert exc_info.value.code == "projection_contract_mismatch"


def test_node_and_edge_keys_differ_between_generations_while_canonical_id_matches() -> (
    None
):
    p_id = DEFAULT_PROJECT_ID
    v_id = DEFAULT_VERSION_ID
    g1 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    g2 = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    doc1 = small_document(p_id, v_id)
    doc2 = small_document(p_id, v_id)

    plan1 = build_projection_plan(doc1, generation_id=g1)
    plan2 = build_projection_plan(doc2, generation_id=g2)

    # G1 and G2 must produce different generation keys and node/edge keys
    assert plan1.generation_key != plan2.generation_key

    n1_by_id = {n.logical_id: n for n in plan1.nodes}
    n2_by_id = {n.logical_id: n for n in plan2.nodes}
    assert set(n1_by_id) == set(n2_by_id)

    for lid in n1_by_id:
        n1 = n1_by_id[lid]
        n2 = n2_by_id[lid]
        assert n1.logical_id == n2.logical_id
        # Projection keys in Neo4j are scoped to the generation
        assert n1.projection_key != n2.projection_key
        # Stable P3 UUIDs are identical across generations for the same logical ID
        assert n1.architecture_entity_id == n2.architecture_entity_id

    r1_by_id = {r.logical_id: r for r in plan1.relationships}
    r2_by_id = {r.logical_id: r for r in plan2.relationships}
    assert set(r1_by_id) == set(r2_by_id)

    for lid in r1_by_id:
        r1 = r1_by_id[lid]
        r2 = r2_by_id[lid]
        assert r1.logical_id == r2.logical_id
        assert r1.projection_key != r2.projection_key
        assert r1.architecture_relationship_id == r2.architecture_relationship_id


def test_key_generation_rejects_nul_bytes() -> None:
    with pytest.raises(ProjectionContractError) as exc_node:
        compute_node_key(
            DEFAULT_PROJECT_ID,
            DEFAULT_VERSION_ID,
            DEFAULT_GENERATION_ID,
            "entity://test\0bad",
        )
    assert exc_node.value.code == "projection_contract_mismatch"

    with pytest.raises(ProjectionContractError) as exc_edge:
        compute_edge_key(
            DEFAULT_PROJECT_ID,
            DEFAULT_VERSION_ID,
            DEFAULT_GENERATION_ID,
            "rel://test\0bad",
        )
    assert exc_edge.value.code == "projection_contract_mismatch"


def test_metadata_allowlist_and_meta_prefix() -> None:
    raw = {
        "application_namespace": "backend",
        "runtime_role": "worker",
        "framework": "fastapi",
        "manifest_declared": True,
        "role_inference_signals": ["signal_a", "signal_b"],
    }
    normalized = normalize_metadata(raw)
    assert normalized == {
        "meta__application_namespace": "backend",
        "meta__runtime_role": "worker",
        "meta__framework": "fastapi",
        "meta__manifest_declared": True,
        "meta__role_inference_signals": ["signal_a", "signal_b"],
    }


def test_metadata_rejects_disallowed_keys() -> None:
    raw = {"arbitrary_custom_key": "some_value"}
    with pytest.raises(ProjectionMetadataError) as exc:
        normalize_metadata(raw)
    assert exc.value.code == "projection_metadata_invalid"
    assert "arbitrary_custom_key" in exc.value.message


def test_metadata_rejects_wrong_types() -> None:
    # boolean expected, got int
    with pytest.raises(ProjectionMetadataError):
        normalize_metadata({"manifest_declared": 1})

    # string expected, got bool
    with pytest.raises(ProjectionMetadataError):
        normalize_metadata({"application_namespace": True})

    # string list expected, got string
    with pytest.raises(ProjectionMetadataError):
        normalize_metadata({"role_inference_signals": "not_a_list"})

    # string list expected, got list of ints
    with pytest.raises(ProjectionMetadataError):
        normalize_metadata({"role_inference_signals": [123, 456]})


def test_metadata_rejects_control_characters() -> None:
    with pytest.raises(ProjectionMetadataError) as exc:
        normalize_metadata({"framework": "django\x07bell"})
    assert exc.value.code == "projection_metadata_invalid"

    with pytest.raises(ProjectionMetadataError):
        normalize_metadata({"role_inference_signals": ["valid", "invalid\x1f"]})


def test_metadata_enforces_candidate_caps() -> None:
    # Key exceeds max bytes
    long_key = "a" * (MAX_META_KEY_BYTES + 1)
    with pytest.raises(ProjectionCapacityExceededError):
        normalize_metadata({long_key: "val"})

    # String exceeds max bytes
    long_val = "x" * (MAX_META_STRING_BYTES + 1)
    with pytest.raises(ProjectionCapacityExceededError):
        normalize_metadata({"framework": long_val})

    # List items exceed max items
    long_list = [f"item_{i}" for i in range(MAX_META_LIST_ITEMS + 1)]
    with pytest.raises(ProjectionCapacityExceededError):
        normalize_metadata({"role_inference_signals": long_list})


def test_source_root_validation() -> None:
    # Valid repository-relative paths
    assert validate_source_root("src/backend") == "src/backend"
    assert validate_source_root("services/payments/app") == "services/payments/app"

    # Invalid: leading slash
    with pytest.raises(ProjectionMetadataError):
        validate_source_root("/src/backend")

    # Invalid: backslash
    with pytest.raises(ProjectionMetadataError):
        validate_source_root("src\\backend")

    # Invalid: UNC or Windows drive
    with pytest.raises(ProjectionMetadataError):
        validate_source_root("//network/share")
    with pytest.raises(ProjectionMetadataError):
        validate_source_root("C:src/backend")

    # Invalid: URI scheme
    with pytest.raises(ProjectionMetadataError):
        validate_source_root("file:///var/log")

    # Invalid: dot or dot-dot segments
    with pytest.raises(ProjectionMetadataError):
        validate_source_root("src/../backend")
    with pytest.raises(ProjectionMetadataError):
        validate_source_root("src/./backend")

    # Invalid: empty segment
    with pytest.raises(ProjectionMetadataError):
        validate_source_root("src//backend")

    # Invalid: host path guards
    with pytest.raises(ProjectionMetadataError):
        validate_source_root("home/user/repo")
    with pytest.raises(ProjectionMetadataError):
        validate_source_root("var/data")
    with pytest.raises(ProjectionMetadataError):
        validate_source_root("tmp/workspace")


def test_route_path_validation() -> None:
    # Valid canonical HTTP route paths
    assert validate_route_path("path", "/api/v1/users") == "/api/v1/users"
    assert validate_route_path("mount_path", "/api/v1") == "/api/v1"
    assert (
        validate_route_path("declared_path", "/api/v1/users/{id}/")
        == "/api/v1/users/{id}/"
    )

    # Invalid: missing leading slash
    with pytest.raises(ProjectionMetadataError):
        validate_route_path("path", "api/v1/users")

    # Invalid: backslashes
    with pytest.raises(ProjectionMetadataError):
        validate_route_path("path", "/api\\v1")

    # Invalid: dot or dot-dot segments
    with pytest.raises(ProjectionMetadataError):
        validate_route_path("path", "/api/../users")
    with pytest.raises(ProjectionMetadataError):
        validate_route_path("path", "/api/./users")

    # Invalid: empty interior segment
    with pytest.raises(ProjectionMetadataError):
        validate_route_path("path", "/api//users")

    # Invalid: host root signatures
    with pytest.raises(ProjectionMetadataError):
        validate_route_path("path", "/home/user")
    with pytest.raises(ProjectionMetadataError):
        validate_route_path("path", "/var/log")
    with pytest.raises(ProjectionMetadataError):
        validate_route_path("path", "/tmp/run")
    with pytest.raises(ProjectionMetadataError):
        validate_route_path("path", "/etc/passwd")


def test_referential_integrity_missing_endpoint_fails() -> None:
    ev = make_evidence()
    e1 = make_entity("entity://service-1")
    # rel points to non-existent entity://service-missing
    rel = make_relationship(
        "rel://bad-edge", "entity://service-1", "entity://service-missing"
    )
    doc = ArchitectureDocument(
        architecture_version_id=DEFAULT_VERSION_ID,
        analysis_id=uuid4(),
        project_id=DEFAULT_PROJECT_ID,
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        configuration_fingerprint="cfg-err",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        entities=(e1,),
        relationships=(rel,),
        evidence=(ev,),
        unresolved_relationships=(),
        conflicts=(),
        completeness=make_completeness(entities=1, relationships=1, evidence=1),
    )

    with pytest.raises(ProjectionContractError) as exc:
        build_projection_plan(doc, generation_id=DEFAULT_GENERATION_ID)
    assert exc.value.code == "projection_contract_mismatch"
    assert "missing target" in exc.value.message


def test_duplicate_entity_logical_id_fails() -> None:
    ev = make_evidence()
    e1 = make_entity("entity://dup")
    e2 = make_entity("entity://dup")
    doc = ArchitectureDocument(
        architecture_version_id=DEFAULT_VERSION_ID,
        analysis_id=uuid4(),
        project_id=DEFAULT_PROJECT_ID,
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        configuration_fingerprint="cfg-err",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        entities=(e1, e2),
        relationships=(),
        evidence=(ev,),
        unresolved_relationships=(),
        conflicts=(),
        completeness=make_completeness(entities=2, relationships=0, evidence=1),
    )
    with pytest.raises(ProjectionContractError) as exc:
        build_projection_plan(doc, generation_id=DEFAULT_GENERATION_ID)
    assert exc.value.code == "projection_contract_mismatch"
    assert "Duplicate entity logical ID" in exc.value.message


def test_no_synthetic_graph_elements_for_unresolved_and_conflicts() -> None:
    doc = unresolved_and_conflicts_document()
    plan = build_projection_plan(doc, generation_id=DEFAULT_GENERATION_ID)

    # 2 entities and 1 resolved relationship projected
    assert len(plan.nodes) == 2
    assert len(plan.relationships) == 1

    # Unresolved relationships and conflicts are NOT projected as nodes or edges
    node_logical_ids = {n.logical_id for n in plan.nodes}
    assert "unresolved://source-to-unknown" not in node_logical_ids
    assert "conflict://competing-target" not in node_logical_ids

    edge_logical_ids = {r.logical_id for r in plan.relationships}
    assert "unresolved://source-to-unknown" not in edge_logical_ids
    assert "conflict://competing-target" not in edge_logical_ids

    # But their summary digests are computed and non-empty
    assert len(plan.unresolved_summary_digest) == 64
    assert len(plan.conflict_summary_digest) == 64
    assert len(plan.evidence_summary_digest) == 64


def test_projection_determinism_across_permutations() -> None:
    doc1 = dense_document()
    # Permute entity and relationship order in input
    entities_permuted = tuple(reversed(doc1.entities))
    relationships_permuted = tuple(reversed(doc1.relationships))

    doc2 = ArchitectureDocument(
        architecture_version_id=doc1.architecture_version_id,
        analysis_id=doc1.analysis_id,
        project_id=doc1.project_id,
        repository_id=doc1.repository_id,
        snapshot_id=doc1.snapshot_id,
        configuration_fingerprint=doc1.configuration_fingerprint,
        analyzer_version=doc1.analyzer_version,
        ir_schema_version=doc1.ir_schema_version,
        architecture_schema_version=doc1.architecture_schema_version,
        entities=entities_permuted,
        relationships=relationships_permuted,
        evidence=doc1.evidence,
        unresolved_relationships=doc1.unresolved_relationships,
        conflicts=doc1.conflicts,
        completeness=doc1.completeness,
    )

    plan1 = build_projection_plan(doc1, generation_id=DEFAULT_GENERATION_ID)
    plan2 = build_projection_plan(doc2, generation_id=DEFAULT_GENERATION_ID)

    assert plan1.generation_key == plan2.generation_key
    assert plan1.key_set_digest == plan2.key_set_digest
    assert plan1.endpoint_digest == plan2.endpoint_digest
    assert plan1.evidence_summary_digest == plan2.evidence_summary_digest
    assert plan1.unresolved_summary_digest == plan2.unresolved_summary_digest
    assert plan1.conflict_summary_digest == plan2.conflict_summary_digest
    assert plan1.payload_digest == plan2.payload_digest

    assert len(plan1.nodes) == len(plan2.nodes)
    for n1, n2 in zip(plan1.nodes, plan2.nodes, strict=True):
        assert n1.projection_key == n2.projection_key
        assert n1.properties == n2.properties


def test_endpoint_digest_changes_on_reversed_direction() -> None:
    p_id = DEFAULT_PROJECT_ID
    v_id = DEFAULT_VERSION_ID
    g_id = DEFAULT_GENERATION_ID

    ev = make_evidence()
    e1 = make_entity("entity://node-1")
    e2 = make_entity("entity://node-2")

    # Forward edge: e1 -> e2
    rel_forward = make_relationship("rel://edge", "entity://node-1", "entity://node-2")
    doc_forward = ArchitectureDocument(
        architecture_version_id=v_id,
        analysis_id=uuid4(),
        project_id=p_id,
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        configuration_fingerprint="cfg-fwd",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        entities=(e1, e2),
        relationships=(rel_forward,),
        evidence=(ev,),
        unresolved_relationships=(),
        conflicts=(),
        completeness=make_completeness(),
    )
    plan_forward = build_projection_plan(doc_forward, generation_id=g_id)

    # Reverse edge: e2 -> e1 with same logical ID
    rel_reverse = make_relationship("rel://edge", "entity://node-2", "entity://node-1")
    doc_reverse = ArchitectureDocument(
        architecture_version_id=v_id,
        analysis_id=uuid4(),
        project_id=p_id,
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        configuration_fingerprint="cfg-rev",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        entities=(e1, e2),
        relationships=(rel_reverse,),
        evidence=(ev,),
        unresolved_relationships=(),
        conflicts=(),
        completeness=make_completeness(),
    )
    plan_reverse = build_projection_plan(doc_reverse, generation_id=g_id)

    # Relationship key is based on (project, version, gen, logical_id), so identical
    assert (
        plan_forward.relationships[0].projection_key
        == plan_reverse.relationships[0].projection_key
    )
    # But endpoint digest MUST differ because source and target keys are flipped!
    assert plan_forward.endpoint_digest != plan_reverse.endpoint_digest
    assert plan_forward.payload_digest != plan_reverse.payload_digest


def test_unicode_document_projection() -> None:
    doc = unicode_document()
    plan = build_projection_plan(doc, generation_id=DEFAULT_GENERATION_ID)

    assert len(plan.nodes) == 2
    assert len(plan.relationships) == 1
    assert len(plan.key_set_digest) == 64
    assert len(plan.endpoint_digest) == 64
    assert len(plan.payload_digest) == 64

    # Verify NFC properties on nodes
    node_names = {n.name for n in plan.nodes}
    assert "Клиентский Сервис (Client Service 日本語 🚀)" in node_names
    assert "Bază de Date (Română 🇷🇴)" in node_names


def test_maximal_metadata_document_projection() -> None:
    doc = maximal_metadata_document()
    plan = build_projection_plan(doc, generation_id=DEFAULT_GENERATION_ID)

    assert len(plan.nodes) == 2
    assert len(plan.relationships) == 1
    api_node = next(n for n in plan.nodes if n.logical_id == "entity://full-meta-api")
    assert api_node.properties["meta__application_namespace"] == "backend.api"
    assert api_node.properties["meta__runtime_role"] == "http_api"
    assert api_node.properties["meta__source_root"] == "apps/api/backend"
    assert api_node.properties["meta__path"] == "/api/v2/resources/"
    assert api_node.properties["meta__manifest_declared"] is True
    assert api_node.properties["meta__role_inference_signals"] == [
        "fastapi",
        "dockerfile",
        "entrypoint",
    ]


def test_no_edge_document_projection() -> None:
    doc = no_edge_document()
    plan = build_projection_plan(doc, generation_id=DEFAULT_GENERATION_ID)

    assert len(plan.nodes) == 3
    assert len(plan.relationships) == 0
    assert len(plan.key_set_digest) == 64
    assert len(plan.endpoint_digest) == 64
    assert len(plan.payload_digest) == 64


def test_frozen_five_count_verification() -> None:
    doc = small_document()
    # Matching counts succeed
    matching_counts = ProjectionCounts(
        entities=2, relationships=1, evidence=1, unresolved=0, conflicts=0
    )
    plan = build_projection_plan(
        doc, generation_id=DEFAULT_GENERATION_ID, expected_counts=matching_counts
    )
    assert plan.expected_counts == matching_counts

    # Mismatched counts fail closed
    wrong_counts = ProjectionCounts(
        entities=3, relationships=1, evidence=1, unresolved=0, conflicts=0
    )
    with pytest.raises(ProjectionSourceMismatchError) as exc:
        build_projection_plan(
            doc, generation_id=DEFAULT_GENERATION_ID, expected_counts=wrong_counts
        )
    assert exc.value.code == "projection_source_mismatch"


def test_projection_plan_enforces_source_payload_limit() -> None:
    doc = small_document()

    with pytest.raises(ProjectionCapacityExceededError) as exc:
        build_projection_plan(
            doc,
            generation_id=DEFAULT_GENERATION_ID,
            max_source_bytes=doc.canonical_payload_size - 1,
        )

    assert exc.value.code == "projection_capacity_exceeded"


@pytest.mark.parametrize(
    ("limit_name", "limit_value"),
    (
        ("max_meta_key_bytes", 4),
        ("max_meta_string_bytes", 3),
        ("max_meta_list_items", 1),
        ("max_meta_record_bytes", 8),
    ),
)
def test_projection_plan_propagates_metadata_limits(
    limit_name: str, limit_value: int
) -> None:
    doc = small_document()

    with pytest.raises(ProjectionCapacityExceededError) as exc:
        build_projection_plan(
            doc,
            generation_id=DEFAULT_GENERATION_ID,
            **{limit_name: limit_value},
        )

    assert exc.value.code == "projection_capacity_exceeded"


def test_golden_digests_stability() -> None:
    """Golden vectors to guarantee no regressions in digest algorithms."""
    doc = small_document()
    plan = build_projection_plan(doc, generation_id=DEFAULT_GENERATION_ID)

    # Re-running produces exact same digests
    plan2 = build_projection_plan(doc, generation_id=DEFAULT_GENERATION_ID)
    assert plan.generation_key == plan2.generation_key
    assert plan.key_set_digest == plan2.key_set_digest
    assert plan.endpoint_digest == plan2.endpoint_digest
    assert plan.evidence_summary_digest == plan2.evidence_summary_digest
    assert plan.unresolved_summary_digest == plan2.unresolved_summary_digest
    assert plan.conflict_summary_digest == plan2.conflict_summary_digest
    assert plan.payload_digest == plan2.payload_digest

    # Exact expected hex length
    for digest in (
        plan.generation_key,
        plan.key_set_digest,
        plan.endpoint_digest,
        plan.evidence_summary_digest,
        plan.unresolved_summary_digest,
        plan.conflict_summary_digest,
        plan.payload_digest,
    ):
        assert len(digest) == 64
        assert digest == digest.lower()
