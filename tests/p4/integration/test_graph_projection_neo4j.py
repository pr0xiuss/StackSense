"""Integration tests against real Neo4j Community instance for M2 projection."""

from __future__ import annotations

import os
from collections.abc import Generator
from uuid import uuid4

import pytest
from pydantic import SecretStr

from backend.platform.config import Settings
from backend.platform.graph.model import (
    SOURCE_CONTRACT_VERSION,
)
from backend.platform.graph.neo4j import Neo4jInfrastructure
from backend.platform.graph.projection import (
    MANIFEST_STATE_BUILDING,
    MANIFEST_STATE_READY,
    build_projection_plan,
)
from backend.platform.graph.projection_store import (
    Neo4jProjectionStore,
    StaleFenceError,
)
from backend.platform.graph.verification import (
    GRAPH_VERIFICATION_PAYLOAD_MISMATCH,
    GraphVerifier,
)
from tests.fixtures.p4.graph.fixtures import (
    small_document,
)


def _integration_settings() -> Settings:
    uri = os.getenv("NEO4J_TEST_URI") or os.getenv("NEO4J_URI")
    password = os.getenv("NEO4J_TEST_PASSWORD") or os.getenv("NEO4J_PASSWORD")
    if not uri or not password:
        pytest.skip("NEO4J_TEST_URI and NEO4J_TEST_PASSWORD are required")
    return Settings(
        neo4j_uri=uri,
        neo4j_user=os.getenv("NEO4J_TEST_USER", "neo4j"),
        neo4j_password=SecretStr(password),
        neo4j_database=os.getenv("NEO4J_TEST_DATABASE", "neo4j"),
        graph_projection_query_timeout_seconds=30.0,
    )


@pytest.fixture
def neo4j_env() -> (
    Generator[tuple[Neo4jInfrastructure, Neo4jProjectionStore, GraphVerifier]]
):
    settings = _integration_settings()
    infra = Neo4jInfrastructure(settings)
    try:
        infra.initialize()
        store = Neo4jProjectionStore(driver=infra.driver, settings=settings)
        verifier = GraphVerifier(store=store)
        yield infra, store, verifier
    finally:
        infra.close()


def test_real_neo4j_full_projection_and_verification(
    neo4j_env: tuple[Neo4jInfrastructure, Neo4jProjectionStore, GraphVerifier],
) -> None:
    infra, store, verifier = neo4j_env
    gen_id = uuid4()
    doc = small_document()
    plan = build_projection_plan(doc, generation_id=gen_id)

    lease_token = "integration-token-1"

    try:
        # 1. Claim candidate
        store.claim_candidate(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=lease_token,
            source_content_digest=plan.source_content_digest,
            expected_counts=plan.expected_counts,
            expected_key_set_digest=plan.key_set_digest,
            expected_endpoint_digest=plan.endpoint_digest,
            expected_payload_digest=plan.payload_digest,
        )

        manifest_before = store.get_manifest(plan.generation_key)
        assert manifest_before is not None
        assert manifest_before["state"] == MANIFEST_STATE_BUILDING

        # 2. Write nodes and relationships
        written_nodes = store.write_nodes(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=lease_token,
            nodes=plan.nodes,
            batch_size=500,
        )
        assert written_nodes == len(plan.nodes)

        written_rels = store.write_relationships(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=lease_token,
            relationships=plan.relationships,
            batch_size=500,
        )
        assert written_rels == len(plan.relationships)

        # 3. Independent read-back verification
        result = verifier.verify_candidate(plan=plan, lease_token=lease_token)
        assert result.verified is True
        assert result.failure_code is None
        assert result.actual_counts == plan.expected_counts
        assert result.actual_key_set_digest == plan.key_set_digest
        assert result.actual_endpoint_digest == plan.endpoint_digest
        assert result.actual_payload_digest == plan.payload_digest

        # Verify manifest transitioned to READY and fence cleared
        manifest_after = store.get_manifest(plan.generation_key)
        assert manifest_after is not None
        assert manifest_after["state"] == MANIFEST_STATE_READY
        assert manifest_after["fence_digest"] is None

        # Verify receipt translation
        receipt = result.to_receipt(
            resource_id=uuid4(),
            attempt_id=uuid4(),
            generation_id=plan.generation_id,
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            lease_owner="test-worker",
            lease_token=lease_token,
            source_content_digest=plan.source_content_digest,
            source_schema_version=SOURCE_CONTRACT_VERSION,
        )
        assert receipt.verified is True
        assert receipt.summaries_match() is True

    finally:
        store.delete_generation(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
        )


def test_real_neo4j_candidate_coexistence(
    neo4j_env: tuple[Neo4jInfrastructure, Neo4jProjectionStore, GraphVerifier],
) -> None:
    infra, store, verifier = neo4j_env
    g1 = uuid4()
    g2 = uuid4()

    doc = small_document()
    p1 = build_projection_plan(doc, generation_id=g1)
    p2 = build_projection_plan(doc, generation_id=g2)

    t1 = "token-g1"
    t2 = "token-g2"

    try:
        # Write and verify G1
        store.claim_candidate(
            project_id=p1.project_id,
            architecture_version_id=p1.architecture_version_id,
            generation_id=p1.generation_id,
            lease_token=t1,
            source_content_digest=p1.source_content_digest,
            expected_counts=p1.expected_counts,
            expected_key_set_digest=p1.key_set_digest,
            expected_endpoint_digest=p1.endpoint_digest,
            expected_payload_digest=p1.payload_digest,
        )
        store.write_nodes(
            project_id=p1.project_id,
            architecture_version_id=p1.architecture_version_id,
            generation_id=p1.generation_id,
            lease_token=t1,
            nodes=p1.nodes,
        )
        store.write_relationships(
            project_id=p1.project_id,
            architecture_version_id=p1.architecture_version_id,
            generation_id=p1.generation_id,
            lease_token=t1,
            relationships=p1.relationships,
        )
        res1 = verifier.verify_candidate(plan=p1, lease_token=t1)
        assert res1.verified is True

        # Write and verify G2 in the same project and version
        store.claim_candidate(
            project_id=p2.project_id,
            architecture_version_id=p2.architecture_version_id,
            generation_id=p2.generation_id,
            lease_token=t2,
            source_content_digest=p2.source_content_digest,
            expected_counts=p2.expected_counts,
            expected_key_set_digest=p2.key_set_digest,
            expected_endpoint_digest=p2.endpoint_digest,
            expected_payload_digest=p2.payload_digest,
        )
        store.write_nodes(
            project_id=p2.project_id,
            architecture_version_id=p2.architecture_version_id,
            generation_id=p2.generation_id,
            lease_token=t2,
            nodes=p2.nodes,
        )
        store.write_relationships(
            project_id=p2.project_id,
            architecture_version_id=p2.architecture_version_id,
            generation_id=p2.generation_id,
            lease_token=t2,
            relationships=p2.relationships,
        )
        res2 = verifier.verify_candidate(plan=p2, lease_token=t2)
        assert res2.verified is True

        # Assert both exist independently in Neo4j
        m1 = store.get_manifest(p1.generation_key)
        m2 = store.get_manifest(p2.generation_key)
        assert m1 is not None and m1["state"] == MANIFEST_STATE_READY
        assert m2 is not None and m2["state"] == MANIFEST_STATE_READY

        n1_total, _ = store.count_nodes(
            project_id=p1.project_id,
            architecture_version_id=p1.architecture_version_id,
            generation_id=p1.generation_id,
        )
        n2_total, _ = store.count_nodes(
            project_id=p2.project_id,
            architecture_version_id=p2.architecture_version_id,
            generation_id=p2.generation_id,
        )
        assert n1_total == len(p1.nodes)
        assert n2_total == len(p2.nodes)

    finally:
        store.delete_generation(
            project_id=p1.project_id,
            architecture_version_id=p1.architecture_version_id,
            generation_id=p1.generation_id,
        )
        store.delete_generation(
            project_id=p2.project_id,
            architecture_version_id=p2.architecture_version_id,
            generation_id=p2.generation_id,
        )


def test_real_neo4j_transactional_fence_race(
    neo4j_env: tuple[Neo4jInfrastructure, Neo4jProjectionStore, GraphVerifier],
) -> None:
    infra, store, verifier = neo4j_env
    gen_id = uuid4()
    doc = small_document()
    plan = build_projection_plan(doc, generation_id=gen_id)

    token_old = "worker-token-old"
    token_new = "worker-token-new"

    try:
        # Worker 1 claims candidate
        store.claim_candidate(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=token_old,
            source_content_digest=plan.source_content_digest,
            expected_counts=plan.expected_counts,
            expected_key_set_digest=plan.key_set_digest,
            expected_endpoint_digest=plan.endpoint_digest,
            expected_payload_digest=plan.payload_digest,
        )

        # Worker 1 writes nodes
        store.write_nodes(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=token_old,
            nodes=plan.nodes,
        )

        # Worker 2 supersedes claim with token_new
        store.claim_candidate(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=token_new,
            source_content_digest=plan.source_content_digest,
            expected_counts=plan.expected_counts,
            expected_key_set_digest=plan.key_set_digest,
            expected_endpoint_digest=plan.endpoint_digest,
            expected_payload_digest=plan.payload_digest,
        )

        # Worker 1 attempts relationship write -> rejected with StaleFenceError!
        with pytest.raises(StaleFenceError, match="fence mismatch"):
            store.write_relationships(
                project_id=plan.project_id,
                architecture_version_id=plan.architecture_version_id,
                generation_id=plan.generation_id,
                lease_token=token_old,
                relationships=plan.relationships,
            )

        # Worker 2 resets candidate and writes both nodes and relationships
        store.reset_candidate(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=token_new,
        )
        store.write_nodes(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=token_new,
            nodes=plan.nodes,
        )
        store.write_relationships(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=token_new,
            relationships=plan.relationships,
        )

        res = verifier.verify_candidate(plan=plan, lease_token=token_new)
        assert res.verified is True

    finally:
        store.delete_generation(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
        )


def test_real_neo4j_deliberate_corruption_detection(
    neo4j_env: tuple[Neo4jInfrastructure, Neo4jProjectionStore, GraphVerifier],
) -> None:
    infra, store, verifier = neo4j_env
    gen_id = uuid4()
    doc = small_document()
    plan = build_projection_plan(doc, generation_id=gen_id)
    token = "token-corruption-test"

    try:
        # Write candidate
        store.claim_candidate(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=token,
            source_content_digest=plan.source_content_digest,
            expected_counts=plan.expected_counts,
            expected_key_set_digest=plan.key_set_digest,
            expected_endpoint_digest=plan.endpoint_digest,
            expected_payload_digest=plan.payload_digest,
        )
        store.write_nodes(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=token,
            nodes=plan.nodes,
        )
        store.write_relationships(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=token,
            relationships=plan.relationships,
        )

        # Deliberately mutate a property on one node directly in Neo4j
        settings = _integration_settings()
        with infra.driver.session(database=settings.neo4j_database) as session:
            session.run(
                "MATCH (n:ArchitectureEntity {projection_key: $key}) "
                "SET n.name = 'TamperedDirectInNeo4j'",
                key=plan.nodes[0].projection_key,
            ).consume()

        # Run independent verifier -> must fail closed with payload digest mismatch!
        res = verifier.verify_candidate(plan=plan, lease_token=token)
        assert res.verified is False
        assert res.failure_code == GRAPH_VERIFICATION_PAYLOAD_MISMATCH

        # Manifest must remain in BUILDING and NOT become READY
        manifest = store.get_manifest(plan.generation_key)
        assert manifest is not None
        assert manifest["state"] == MANIFEST_STATE_BUILDING

    finally:
        store.delete_generation(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
        )


def test_real_neo4j_idempotent_retry_and_cleanup(
    neo4j_env: tuple[Neo4jInfrastructure, Neo4jProjectionStore, GraphVerifier],
) -> None:
    infra, store, verifier = neo4j_env
    gen_id = uuid4()
    doc = small_document()
    plan = build_projection_plan(doc, generation_id=gen_id)
    token = "token-retry-test"

    try:
        # Write once
        store.claim_candidate(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=token,
            source_content_digest=plan.source_content_digest,
            expected_counts=plan.expected_counts,
            expected_key_set_digest=plan.key_set_digest,
            expected_endpoint_digest=plan.endpoint_digest,
            expected_payload_digest=plan.payload_digest,
        )
        store.write_nodes(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=token,
            nodes=plan.nodes,
        )
        store.write_relationships(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=token,
            relationships=plan.relationships,
        )

        # Retry exact write without reset -> MERGE ensures no duplicates
        store.write_nodes(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=token,
            nodes=plan.nodes,
        )
        store.write_relationships(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            lease_token=token,
            relationships=plan.relationships,
        )

        res = verifier.verify_candidate(plan=plan, lease_token=token)
        assert res.verified is True

        # Now test bounded cleanup
        deleted_count = store.delete_generation(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
        )
        assert deleted_count == len(plan.nodes) + len(plan.relationships) + 1

        # Check nodes, relationships, and manifest are completely gone
        total_nodes, _ = store.count_nodes(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
        )
        total_rels, _ = store.count_relationships(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
        )
        assert total_nodes == 0
        assert total_rels == 0
        assert store.get_manifest(plan.generation_key) is None

    finally:
        store.delete_generation(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
        )
