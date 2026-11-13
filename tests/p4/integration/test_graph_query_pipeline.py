"""End-to-end integration test combining real PostgreSQL and real Neo4j.

Validates the full P4-Q1 query pipeline:
1. Exact-version generation resolution from PostgreSQL authority.
2. Neo4j manifest preflight and controlled query execution.
3. Candidate G2 build coexistence while G1 serves traffic.
4. Active pointer switch from G1 to G2 in PostgreSQL immediately shifts reads.
5. Invalidation of G1 cursors following pointer switch to G2.
6. Historical STALE resource queryability.
7. Clean isolation and database cleanup on completion.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from neo4j import Driver
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.platform.analysis.architecture.persistence import ArchitectureVersionModel
from backend.platform.analysis.infra.lifecycle_model import AnalysisModel
from backend.platform.config import Settings
from backend.platform.graph.cursor import compute_query_fingerprint, encode_cursor
from backend.platform.graph.model import (
    GRAPH_SCHEMA_VERSION,
    PROJECTOR_VERSION,
    ActivationDisposition,
    ProjectionActorType,
    ProjectionCounts,
    VerificationReceipt,
)
from backend.platform.graph.neo4j import Neo4jInfrastructure
from backend.platform.graph.persistence import (
    GraphProjectionAttemptModel,
    GraphProjectionResourceModel,
    SqlAlchemyGraphProjectionRepository,
)
from backend.platform.graph.projection import (
    MANIFEST_STATE_READY,
    compute_edge_key,
    compute_generation_key,
    compute_node_key,
)
from backend.platform.graph.query_contracts import (
    GraphGenerationChangedError,
    GraphWindowRequest,
)
from backend.platform.graph.query_repository import (
    Neo4jGraphQueryRepository,
    SqlAlchemyGraphGenerationReader,
)
from backend.platform.graph.query_service import GraphQueryService
from backend.platform.graph.queue import ProjectionWorkPayload
from backend.platform.graph.source import PublishedArchitectureHeader


def _database_url() -> str:
    value = os.getenv("STACKSENSE_TEST_DATABASE_URL")
    if value is None:
        configured = dotenv_values(".env").get("DATABASE_URL")
        if not isinstance(configured, str) or not configured:
            raise RuntimeError("DATABASE_URL is required for PostgreSQL integration")
        value = configured
    return value.replace("postgresql://", "postgresql+psycopg://", 1)


@pytest.fixture(scope="module")
def postgres_session_factory() -> Generator[sessionmaker[Session]]:
    try:
        url = _database_url()
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect():
            pass
    except Exception as exc:
        pytest.skip(f"PostgreSQL not reachable: {exc}")

    factory = sessionmaker(engine)
    yield factory
    engine.dispose()


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


def _publish_architecture(session: Session) -> PublishedArchitectureHeader:
    now = datetime.now(UTC)
    analysis_id = uuid4()
    project_id = uuid4()
    repository_id = uuid4()
    snapshot_id = uuid4()
    version_id = uuid4()

    session.add(
        AnalysisModel(
            id=analysis_id,
            project_id=project_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            status="completed",
            configuration={},
            completeness={},
            published_version_id=None,
            error_code=None,
            error_message=None,
            idempotency_key=None,
            version=1,
            created_at=now,
            updated_at=now,
            started_at=now,
            completed_at=now,
        )
    )
    session.flush()

    session.add(
        ArchitectureVersionModel(
            id=version_id,
            analysis_id=analysis_id,
            project_id=project_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            sequence_number=1,
            state="published",
            configuration_fingerprint="configuration",
            analyzer_version="1.0.0",
            ir_schema_version="1.0.0",
            architecture_schema_version="1.0.0",
            content_digest="source-digest",
            completeness={},
            source_diagnostic_ids=[],
            entity_count=2,
            relationship_count=1,
            evidence_count=1,
            unresolved_relationship_count=0,
            conflict_count=0,
            diagnostic_id=None,
            failure_code=None,
            created_at=now,
            updated_at=now,
            published_at=now,
        )
    )
    session.commit()

    return PublishedArchitectureHeader(
        contract_version="1.0.0",
        architecture_version_id=version_id,
        analysis_id=analysis_id,
        project_id=project_id,
        repository_id=repository_id,
        snapshot_id=snapshot_id,
        sequence_number=1,
        published_at=now,
        configuration_fingerprint="configuration",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        content_digest="source-digest",
        counts=ProjectionCounts(2, 1, 1, 0, 0),
    )


def test_real_postgresql_and_neo4j_query_pipeline(
    postgres_session_factory: sessionmaker[Session],
    neo4j_env: tuple[Driver, Settings],
) -> None:
    driver, settings = neo4j_env

    with postgres_session_factory() as session:
        # 1. Publish architecture in PostgreSQL
        header = _publish_architecture(session)
        lifecycle_repo = SqlAlchemyGraphProjectionRepository(session)
        ensure_res = lifecycle_repo.ensure_with_initial_attempt(
            header, correlation_id="pipeline-test"
        )
        session.commit()

        resource_id = ensure_res.resource.id
        attempt_g1 = session.scalars(
            select(GraphProjectionAttemptModel).where(
                GraphProjectionAttemptModel.resource_id == resource_id
            )
        ).one()

        g1_id = attempt_g1.generation_id
        p_id = str(header.project_id).lower()
        a_id = str(header.architecture_version_id).lower()
        g1_str = str(g1_id).lower()

        # 2. Activate G1 in PostgreSQL
        now = datetime.now(UTC)
        lease_g1 = lifecycle_repo.acquire_lease(
            ProjectionWorkPayload(
                contract_version="1.0.0",
                projection_id=resource_id,
                architecture_version_id=header.architecture_version_id,
                project_id=header.project_id,
                generation_id=g1_id,
                attempt_id=attempt_g1.id,
                correlation_id="pipeline-test",
            ).to_claim(),
            worker_id="pipeline-worker",
            now=now,
            duration=timedelta(minutes=5),
        )
        assert lease_g1 is not None

        receipt_g1 = VerificationReceipt(
            resource_id=resource_id,
            attempt_id=attempt_g1.id,
            generation_id=g1_id,
            project_id=header.project_id,
            architecture_version_id=header.architecture_version_id,
            lease_owner=lease_g1.worker_id,
            lease_token=lease_g1.token,
            contract_version="1.0.0",
            source_content_digest=header.content_digest,
            source_schema_version=header.architecture_schema_version,
            graph_schema_version=GRAPH_SCHEMA_VERSION,
            projector_version=PROJECTOR_VERSION,
            verified=True,
            expected_counts=header.counts,
            actual_counts=header.counts,
            expected_key_set_digest="keys",
            actual_key_set_digest="keys",
            expected_endpoint_digest="endpoints",
            actual_endpoint_digest="endpoints",
            expected_payload_digest="payload",
            actual_payload_digest="payload",
        )
        activation_g1 = lifecycle_repo.activate_verified(
            receipt_g1, now=now + timedelta(seconds=1)
        )
        session.commit()
        assert activation_g1.disposition == ActivationDisposition.ACTIVATED

        # 3. Seed G1 in Neo4j (READY manifest, OrderService -> PaymentService)
        gen_key_1 = compute_generation_key(p_id, a_id, g1_str)
        pk_order_1 = compute_node_key(p_id, a_id, g1_str, "logical.OrderService")
        pk_payment_1 = compute_node_key(p_id, a_id, g1_str, "logical.PaymentService")
        pk_edge_1 = compute_edge_key(p_id, a_id, g1_str, "rel.Order->Payment")

        with driver.session(database=settings.neo4j_database) as neo_session:
            neo_session.run(
                "CREATE (m:ProjectionManifest { "
                "    project_id: $p_id, "
                "    architecture_version_id: $a_id, "
                "    generation_id: $g_id, "
                "    generation_key: $gen_key, "
                "    state: $state, "
                "    graph_schema_version: $schema_ver "
                "})",
                p_id=p_id,
                a_id=a_id,
                g_id=g1_str,
                gen_key=gen_key_1,
                state=MANIFEST_STATE_READY,
                schema_ver=GRAPH_SCHEMA_VERSION,
            )
            neo_session.run(
                "CREATE (n1:ArchitectureEntity { "
                "    project_id: $p_id, "
                "    architecture_version_id: $a_id, "
                "    generation_id: $g_id, "
                "    generation_key: $gen_key, "
                "    projection_key: $pk1, "
                "    architecture_entity_id: $e1_id, "
                "    logical_id: 'logical.OrderService', "
                "    canonical_kind: 'service', "
                "    name: 'OrderService', "
                "    namespace: 'backend.orders', "
                "    fact_status: 'canonical', "
                "    semantic_signature: 'sig-order' "
                "}), (n2:ArchitectureEntity { "
                "    project_id: $p_id, "
                "    architecture_version_id: $a_id, "
                "    generation_id: $g_id, "
                "    generation_key: $gen_key, "
                "    projection_key: $pk2, "
                "    architecture_entity_id: $e2_id, "
                "    logical_id: 'logical.PaymentService', "
                "    canonical_kind: 'service', "
                "    name: 'PaymentService', "
                "    namespace: 'backend.payments', "
                "    fact_status: 'canonical', "
                "    semantic_signature: 'sig-payment' "
                "})",
                p_id=p_id,
                a_id=a_id,
                g_id=g1_str,
                gen_key=gen_key_1,
                pk1=pk_order_1,
                pk2=pk_payment_1,
                e1_id=str(uuid4()).lower(),
                e2_id=str(uuid4()).lower(),
            )
            neo_session.run(
                "MATCH (s:ArchitectureEntity { projection_key: $pk1 }), "
                "      (t:ArchitectureEntity { projection_key: $pk2 }) "
                "CREATE (s)-[:ARCH_RELATIONSHIP { "
                "    project_id: $p_id, "
                "    architecture_version_id: $a_id, "
                "    generation_id: $g_id, "
                "    generation_key: $gen_key, "
                "    projection_key: $epk, "
                "    architecture_relationship_id: $rel_id, "
                "    logical_id: 'rel.Order->Payment', "
                "    canonical_kind: 'calls', "
                "    status: 'canonical', "
                "    source_projection_key: $pk1, "
                "    target_projection_key: $pk2 "
                "}]->(t)",
                p_id=p_id,
                a_id=a_id,
                g_id=g1_str,
                gen_key=gen_key_1,
                pk1=pk_order_1,
                pk2=pk_payment_1,
                epk=pk_edge_1,
                rel_id=str(uuid4()).lower(),
            )

        try:
            # 4. Execute query using real GraphQueryService against G1
            reader = SqlAlchemyGraphGenerationReader(session)
            repo = Neo4jGraphQueryRepository(driver, database=settings.neo4j_database)
            secret = "pipeline-cursor-secret-key-32-chars!"
            service = GraphQueryService(
                settings=settings,
                generation_reader=reader,
                query_repository=repo,
                cursor_secret_key=secret,
            )

            req = GraphWindowRequest(
                project_id=header.project_id,
                architecture_version_id=header.architecture_version_id,
            )
            subgraph_g1 = service.get_window(req)
            assert subgraph_g1.scope.generation_id == g1_id
            assert len(subgraph_g1.nodes) == 2
            assert len(subgraph_g1.edges) == 1
            names_g1 = {n.name for n in subgraph_g1.nodes}
            assert names_g1 == {"OrderService", "PaymentService"}

            # 5. Issue a continuation cursor bound to G1
            fp = compute_query_fingerprint(
                {
                    "operation": "window",
                    "node_limit": req.node_limit,
                    "edge_limit": req.edge_limit,
                    "page_size": req.page_size,
                    "kinds": None,
                }
            )
            scope_g1 = reader.resolve_active_generation(
                header.project_id, header.architecture_version_id
            )
            cursor_g1 = encode_cursor(
                position={"node_cursor": "pos1"},
                scope=scope_g1,
                operation="window",
                fingerprint=fp,
                secret_key=secret,
                ttl_seconds=900,
            )

            # 6. Rebuild as candidate generation G2
            attempt_g2 = lifecycle_repo.create_rebuild_attempt(
                resource_id=resource_id,
                actor_type=ProjectionActorType.SYSTEM,
                actor_id=None,
                actor_role=None,
                correlation_id="pipeline-rebuild",
            )
            session.commit()
            assert attempt_g2 is not None
            g2_id = attempt_g2.generation_id
            g2_str = str(g2_id).lower()

            # Seed G2 in Neo4j with READY manifest and new node InventoryService
            gen_key_2 = compute_generation_key(p_id, a_id, g2_str)
            pk_inv_2 = compute_node_key(p_id, a_id, g2_str, "logical.InventoryService")

            with driver.session(database=settings.neo4j_database) as neo_session:
                neo_session.run(
                    "CREATE (m:ProjectionManifest { "
                    "    project_id: $p_id, "
                    "    architecture_version_id: $a_id, "
                    "    generation_id: $g_id, "
                    "    generation_key: $gen_key, "
                    "    state: $state, "
                    "    graph_schema_version: $schema_ver "
                    "})",
                    p_id=p_id,
                    a_id=a_id,
                    g_id=g2_str,
                    gen_key=gen_key_2,
                    state=MANIFEST_STATE_READY,
                    schema_ver=GRAPH_SCHEMA_VERSION,
                )
                neo_session.run(
                    "CREATE (n:ArchitectureEntity { "
                    "    project_id: $p_id, "
                    "    architecture_version_id: $a_id, "
                    "    generation_id: $g_id, "
                    "    generation_key: $gen_key, "
                    "    projection_key: $pk, "
                    "    architecture_entity_id: $e_id, "
                    "    logical_id: 'logical.InventoryService', "
                    "    canonical_kind: 'service', "
                    "    name: 'InventoryService', "
                    "    namespace: 'backend.inventory', "
                    "    fact_status: 'canonical', "
                    "    semantic_signature: 'sig-inv' "
                    "})",
                    p_id=p_id,
                    a_id=a_id,
                    g_id=g2_str,
                    gen_key=gen_key_2,
                    pk=pk_inv_2,
                    e_id=str(uuid4()).lower(),
                )

            # Before activation: traffic still routes to G1!
            still_g1 = service.get_window(req)
            assert still_g1.scope.generation_id == g1_id

            # 7. Activate G2 in PostgreSQL
            now_g2 = datetime.now(UTC)
            lease_g2 = lifecycle_repo.acquire_lease(
                ProjectionWorkPayload(
                    contract_version="1.0.0",
                    projection_id=resource_id,
                    architecture_version_id=header.architecture_version_id,
                    project_id=header.project_id,
                    generation_id=attempt_g2.generation_id,
                    attempt_id=attempt_g2.id,
                    correlation_id="pipeline-rebuild",
                ).to_claim(),
                worker_id="pipeline-worker-2",
                now=now_g2,
                duration=timedelta(minutes=5),
            )
            assert lease_g2 is not None

            receipt_g2 = VerificationReceipt(
                resource_id=resource_id,
                attempt_id=attempt_g2.id,
                generation_id=attempt_g2.generation_id,
                project_id=header.project_id,
                architecture_version_id=header.architecture_version_id,
                lease_owner=lease_g2.worker_id,
                lease_token=lease_g2.token,
                contract_version="1.0.0",
                source_content_digest=header.content_digest,
                source_schema_version=header.architecture_schema_version,
                graph_schema_version=GRAPH_SCHEMA_VERSION,
                projector_version=PROJECTOR_VERSION,
                verified=True,
                expected_counts=header.counts,
                actual_counts=header.counts,
                expected_key_set_digest="keys2",
                actual_key_set_digest="keys2",
                expected_endpoint_digest="endpoints2",
                actual_endpoint_digest="endpoints2",
                expected_payload_digest="payload2",
                actual_payload_digest="payload2",
            )
            activation_g2 = lifecycle_repo.activate_verified(
                receipt_g2, now=now_g2 + timedelta(seconds=1)
            )
            session.commit()
            assert activation_g2.disposition == ActivationDisposition.ACTIVATED

            # 8. Query immediately shifts to G2
            subgraph_g2 = service.get_window(req)
            assert subgraph_g2.scope.generation_id == attempt_g2.generation_id
            names_g2 = {n.name for n in subgraph_g2.nodes}
            assert names_g2 == {"InventoryService"}

            # 9. Cursor from G1 now fails closed!
            req_with_old_cursor = GraphWindowRequest(
                project_id=header.project_id,
                architecture_version_id=header.architecture_version_id,
                cursor=cursor_g1,
            )
            with pytest.raises(
                GraphGenerationChangedError,
                match="Active projection generation changed",
            ):
                service.get_window(req_with_old_cursor)

            # 10. Historical STALE queryability
            resource_model = session.get(GraphProjectionResourceModel, resource_id)
            assert resource_model is not None
            resource_model.state = "STALE"
            session.commit()

            stale_subgraph = service.get_window(req)
            assert stale_subgraph.scope.resource_state == "STALE"
            assert stale_subgraph.scope.generation_id == attempt_g2.generation_id
            assert {n.name for n in stale_subgraph.nodes} == {"InventoryService"}

        finally:
            # 11. Cleanup Neo4j
            with driver.session(database=settings.neo4j_database) as neo_session:
                neo_session.run(
                    "MATCH (n:ArchitectureEntity { project_id: $p_id }) "
                    "DETACH DELETE n",
                    p_id=p_id,
                )
                neo_session.run(
                    "MATCH (m:ProjectionManifest { project_id: $p_id }) DELETE m",
                    p_id=p_id,
                )

            # 12. Cleanup PostgreSQL
            session.rollback()
            session.query(GraphProjectionAttemptModel).filter(
                GraphProjectionAttemptModel.resource_id == resource_id
            ).delete()
            session.query(GraphProjectionResourceModel).filter(
                GraphProjectionResourceModel.id == resource_id
            ).delete()
            session.query(ArchitectureVersionModel).filter(
                ArchitectureVersionModel.id == header.architecture_version_id
            ).delete()
            session.query(AnalysisModel).filter(
                AnalysisModel.id == header.analysis_id
            ).delete()
            session.commit()
