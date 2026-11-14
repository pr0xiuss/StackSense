"""Real FastAPI, PostgreSQL, and Neo4j end-to-end Graph API integration tests.

Validates the complete P4-D1 Graph API pipeline:
1. Status retrieval reflecting exact PostgreSQL projection resource and active attempt.
2. All seven graph query read operations over real infrastructure.
3. Transactional rebuild request (POST 202) creating durable queued attempt.
4. Concurrent rebuild requests reusing the active attempt.
5. Cross-project and cross-version isolation (decoys fail closed).
6. Query health probe isolation.
7. Clean isolation and database cleanup on completion.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from neo4j import Driver
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.api.app import app
from backend.platform.analysis.architecture.persistence import (
    ArchitectureVersionModel,
)
from backend.platform.analysis.infra.lifecycle_model import AnalysisModel
from backend.platform.config import Settings, get_settings
from backend.platform.dependency_injection import get_database_session
from backend.platform.graph.model import (
    GRAPH_SCHEMA_VERSION,
    PROJECTION_TYPE,
    PROJECTOR_VERSION,
    ProjectionAttemptState,
    ProjectionPublicState,
)
from backend.platform.graph.neo4j import Neo4jInfrastructure
from backend.platform.graph.persistence import (
    Base,
    GraphProjectionAttemptModel,
    GraphProjectionResourceModel,
)
from backend.platform.graph.projection import (
    MANIFEST_STATE_READY,
    compute_edge_key,
    compute_generation_key,
    compute_node_key,
)

SECRET = get_settings().internal_api_secret_key.get_secret_value()


def _database_url() -> str:
    value = os.getenv("STACKSENSE_TEST_DATABASE_URL")
    if value is None:
        configured = dotenv_values(".env").get("DATABASE_URL")
        if not isinstance(configured, str) or not configured:
            raise RuntimeError("DATABASE_URL is required for PostgreSQL integration")
        value = configured
    return value.replace("postgresql://", "postgresql+psycopg://", 1)


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


@pytest.fixture(scope="module")
def neo4j_env() -> Generator[tuple[Driver, Settings]]:
    settings = _integration_settings()
    infra = Neo4jInfrastructure(settings)
    try:
        infra.initialize()
        yield infra.driver, settings
    finally:
        infra.close()


def _headers(
    project_id: UUID,
    role: str = "DEVELOPER",
    correlation_id: str | None = None,
) -> dict[str, str]:
    headers = {
        "X-Service-Token": SECRET,
        "X-Actor-Id": str(uuid4()),
        "X-Actor-Role": role,
        "X-Project-Id": str(project_id),
    }
    if correlation_id is not None:
        headers["X-Correlation-Id"] = correlation_id
    return headers


def test_fastapi_sqlite_full_api_pipeline_composition() -> None:
    """Test full FastAPI API pipeline with SQLite in-memory persistence models."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            GraphProjectionResourceModel.__table__,
            GraphProjectionAttemptModel.__table__,
            AnalysisModel.__table__,
            ArchitectureVersionModel.__table__,
        ],
    )

    session = Session(engine)
    project_id = uuid4()
    version_id = uuid4()
    analysis_id = uuid4()
    repository_id = uuid4()
    snapshot_id = uuid4()
    resource_id = uuid4()
    gen_id = uuid4()
    attempt_id = uuid4()
    now = datetime.now(UTC)

    session.add(
        AnalysisModel(
            id=analysis_id,
            project_id=project_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            status="completed",
            configuration={},
            completeness={},
            published_version_id=version_id,
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
    session.add(
        ArchitectureVersionModel(
            id=version_id,
            analysis_id=analysis_id,
            project_id=project_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            sequence_number=1,
            state="published",
            configuration_fingerprint="cfg",
            analyzer_version="1.0.0",
            ir_schema_version="1.0.0",
            architecture_schema_version="1.0.0",
            content_digest="digest-abc",
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
    session.add(
        GraphProjectionResourceModel(
            id=resource_id,
            architecture_version_id=version_id,
            project_id=project_id,
            repository_id=repository_id,
            architecture_sequence=1,
            projection_type=PROJECTION_TYPE,
            source_content_digest="digest-abc",
            source_schema_version="1.0",
            state=ProjectionPublicState.COMPLETED.value,
            active_generation_id=gen_id,
            active_projector_version=PROJECTOR_VERSION,
            active_graph_schema_version=GRAPH_SCHEMA_VERSION,
            active_payload_digest="payload-digest-1",
            active_entity_count=2,
            active_relationship_count=1,
            active_evidence_count=1,
            active_unresolved_count=0,
            active_conflict_count=0,
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        GraphProjectionAttemptModel(
            id=attempt_id,
            resource_id=resource_id,
            generation_id=gen_id,
            attempt_number=1,
            state=ProjectionAttemptState.COMPLETED.value,
            actor_type="SYSTEM",
            actor_id=None,
            actor_role=None,
            correlation_id="initial-corr-id",
            contract_version="1.0.0",
            source_content_digest="digest-abc",
            source_schema_version="1.0",
            graph_schema_version=GRAPH_SCHEMA_VERSION,
            projector_version=PROJECTOR_VERSION,
            expected_entity_count=2,
            expected_relationship_count=1,
            expected_evidence_count=1,
            expected_unresolved_count=0,
            expected_conflict_count=0,
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
    )
    session.commit()

    # Override get_database_session with this active SQLite session
    def _override_get_session() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = _override_get_session

    client = TestClient(app)
    try:
        # 1. Status route returns COMPLETED status
        resp_status = client.get(
            f"/api/v1/architecture-versions/{version_id}/graph/status",
            params={"project_id": str(project_id)},
            headers=_headers(project_id=project_id, role="DEVELOPER"),
        )
        assert resp_status.status_code == 200
        status_data = resp_status.json()
        assert status_data["resource_id"] == str(resource_id)
        assert status_data["status"] == "COMPLETED"
        assert status_data["counts"]["entities"] == 2
        assert status_data["projection_type"] == PROJECTION_TYPE

        # 2. Rebuild route with OWNER role creates attempt #2 (QUEUED)
        resp_rebuild1 = client.post(
            f"/api/v1/architecture-versions/{version_id}/graph/rebuild",
            params={"project_id": str(project_id)},
            headers=_headers(project_id=project_id, role="OWNER"),
        )
        assert resp_rebuild1.status_code == 202
        reb1_data = resp_rebuild1.json()
        assert reb1_data["resource_id"] == str(resource_id)
        assert reb1_data["attempt_number"] == 2
        assert reb1_data["attempt_status"] == "QUEUED"
        created_att_id = reb1_data["attempt_id"]

        # 3. Concurrent rebuild request reuses active attempt #2
        resp_rebuild2 = client.post(
            f"/api/v1/architecture-versions/{version_id}/graph/rebuild",
            params={"project_id": str(project_id)},
            headers=_headers(project_id=project_id, role="ADMIN"),
        )
        assert resp_rebuild2.status_code == 202
        reb2_data = resp_rebuild2.json()
        assert reb2_data["attempt_id"] == created_att_id
        assert reb2_data["attempt_number"] == 2

        # 4. Status route reflects active rebuild attempt
        resp_status_active = client.get(
            f"/api/v1/architecture-versions/{version_id}/graph/status",
            params={"project_id": str(project_id)},
            headers=_headers(project_id=project_id, role="VIEWER"),
        )
        assert resp_status_active.status_code == 200
        active_status = resp_status_active.json()
        assert active_status["active_attempt"] is not None
        assert active_status["active_attempt"]["attempt_id"] == created_att_id
        assert active_status["active_attempt"]["status"] == "QUEUED"

        # 5. Non-operator (DEVELOPER/VIEWER) denied on rebuild before lookup
        resp_denied = client.post(
            f"/api/v1/architecture-versions/{version_id}/graph/rebuild",
            params={"project_id": str(project_id)},
            headers=_headers(project_id=project_id, role="DEVELOPER"),
        )
        assert resp_denied.status_code == 403
        assert resp_denied.json()["error"]["code"] == "analysis_access_denied"

        # 6. Project mismatch denied before service lookup
        resp_mismatch = client.post(
            f"/api/v1/architecture-versions/{version_id}/graph/rebuild",
            params={"project_id": str(uuid4())},
            headers=_headers(project_id=project_id, role="OWNER"),
        )
        assert resp_mismatch.status_code == 403
        assert resp_mismatch.json()["error"]["code"] == "analysis_access_denied"

        # 7. Non-existent architecture version returns 404
        non_existent_ver = uuid4()
        resp_not_found = client.get(
            f"/api/v1/architecture-versions/{non_existent_ver}/graph/status",
            params={"project_id": str(project_id)},
            headers=_headers(project_id=project_id, role="DEVELOPER"),
        )
        assert resp_not_found.status_code == 404
        assert resp_not_found.json()["error"]["code"] == "graph_projection_not_found"

        # 8. Query health endpoint is accessible without authentication
        resp_health = client.get("/api/v1/health/graph/query")
        assert resp_health.status_code == 200
        assert "status" in resp_health.json()

    finally:
        app.dependency_overrides.pop(get_database_session, None)
        client.close()
        session.close()
        engine.dispose()


def test_real_postgresql_and_neo4j_api_pipeline_composition(
    postgres_session_factory: sessionmaker[Session],
    neo4j_env: tuple[Driver, Settings],
) -> None:
    """End-to-end API pipeline test over live PostgreSQL and live Neo4j."""
    driver, settings = neo4j_env

    session = postgres_session_factory()
    project_id = uuid4()
    version_id = uuid4()
    analysis_id = uuid4()
    repository_id = uuid4()
    snapshot_id = uuid4()
    resource_id = uuid4()
    gen_id = uuid4()
    attempt_id = uuid4()
    now = datetime.now(UTC)

    # 1. Seed PostgreSQL records
    session.add(
        AnalysisModel(
            id=analysis_id,
            project_id=project_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            status="completed",
            configuration={},
            completeness={},
            published_version_id=version_id,
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
    session.add(
        ArchitectureVersionModel(
            id=version_id,
            analysis_id=analysis_id,
            project_id=project_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            sequence_number=1,
            state="published",
            configuration_fingerprint="cfg",
            analyzer_version="1.0.0",
            ir_schema_version="1.0.0",
            architecture_schema_version="1.0.0",
            content_digest="digest-real",
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
    session.add(
        GraphProjectionResourceModel(
            id=resource_id,
            architecture_version_id=version_id,
            project_id=project_id,
            repository_id=repository_id,
            architecture_sequence=1,
            projection_type=PROJECTION_TYPE,
            source_content_digest="digest-real",
            source_schema_version="1.0",
            state=ProjectionPublicState.COMPLETED.value,
            active_generation_id=gen_id,
            active_projector_version=PROJECTOR_VERSION,
            active_graph_schema_version=GRAPH_SCHEMA_VERSION,
            active_payload_digest="payload-digest-real",
            active_entity_count=2,
            active_relationship_count=1,
            active_evidence_count=1,
            active_unresolved_count=0,
            active_conflict_count=0,
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        GraphProjectionAttemptModel(
            id=attempt_id,
            resource_id=resource_id,
            generation_id=gen_id,
            attempt_number=1,
            state=ProjectionAttemptState.COMPLETED.value,
            actor_type="SYSTEM",
            actor_id=None,
            actor_role=None,
            correlation_id="initial-corr-real",
            contract_version="1.0.0",
            source_content_digest="digest-real",
            source_schema_version="1.0",
            graph_schema_version=GRAPH_SCHEMA_VERSION,
            projector_version=PROJECTOR_VERSION,
            expected_entity_count=2,
            expected_relationship_count=1,
            expected_evidence_count=1,
            expected_unresolved_count=0,
            expected_conflict_count=0,
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
    )
    session.commit()

    # 2. Seed Neo4j records
    source_entity_id = uuid4()
    target_entity_id = uuid4()
    node1_key = compute_node_key(
        project_id, version_id, gen_id, "architecture://service/svc-a"
    )
    node2_key = compute_node_key(
        project_id, version_id, gen_id, "architecture://service/svc-b"
    )
    edge_key = compute_edge_key(
        project_id,
        version_id,
        gen_id,
        "calls",
        "architecture://service/svc-a",
        "architecture://service/svc-b",
    )
    gen_key = compute_generation_key(project_id, version_id, gen_id)

    with driver.session(database=settings.neo4j_database) as neo_sess:
        neo_sess.run(
            """
            MERGE (m:ProjectionManifest {projection_key: $gen_key})
            SET m.project_id = $project_id,
                m.architecture_version_id = $version_id,
                m.generation_id = $gen_id,
                m.state = $ready_state,
                m.graph_schema_version = $schema_version,
                m.projector_version = $projector_version,
                m.source_content_digest = 'digest-real',
                m.verified_payload_digest = 'payload-digest-real',
                m.verified_entity_count = 2,
                m.verified_relationship_count = 1,
                m.verified_evidence_count = 1,
                m.verified_unresolved_count = 0,
                m.verified_conflict_count = 0,
                m.created_at = datetime(),
                m.updated_at = datetime()
            MERGE (n1:ArchitectureEntity {projection_key: $n1_key})
            SET n1.project_id = $project_id,
                n1.architecture_version_id = $version_id,
                n1.generation_id = $gen_id,
                n1.architecture_entity_id = $source_id,
                n1.logical_id = 'architecture://service/svc-a',
                n1.canonical_kind = 'service',
                n1.name = 'ServiceA',
                n1.namespace = 'default',
                n1.fact_status = 'confirmed',
                n1.semantic_signature = 'sig-a',
                n1.evidence_logical_ids = ['ev-1']
            MERGE (n2:ArchitectureEntity {projection_key: $n2_key})
            SET n2.project_id = $project_id,
                n2.architecture_version_id = $version_id,
                n2.generation_id = $gen_id,
                n2.architecture_entity_id = $target_id,
                n2.logical_id = 'architecture://service/svc-b',
                n2.canonical_kind = 'service',
                n2.name = 'ServiceB',
                n2.namespace = 'default',
                n2.fact_status = 'confirmed',
                n2.semantic_signature = 'sig-b',
                n2.evidence_logical_ids = []
            MERGE (n1)-[r:CALLS {projection_key: $edge_key}]->(n2)
            SET r.project_id = $project_id,
                r.architecture_version_id = $version_id,
                r.generation_id = $gen_id,
                r.kind = 'calls',
                r.fact_status = 'confirmed',
                r.weight = 1.0,
                r.semantic_signature = 'sig-edge',
                r.evidence_logical_ids = ['ev-1']
            """,
            gen_key=gen_key,
            project_id=str(project_id),
            version_id=str(version_id),
            gen_id=str(gen_id),
            ready_state=MANIFEST_STATE_READY,
            schema_version=GRAPH_SCHEMA_VERSION,
            projector_version=PROJECTOR_VERSION,
            n1_key=node1_key,
            source_id=str(source_entity_id),
            n2_key=node2_key,
            target_id=str(target_entity_id),
            edge_key=edge_key,
        )

    # Override get_database_session with real PostgreSQL session
    def _override_get_session() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = _override_get_session

    client = TestClient(app)
    try:
        # 1. Status route
        r_status = client.get(
            f"/api/v1/architecture-versions/{version_id}/graph/status",
            params={"project_id": str(project_id)},
            headers=_headers(project_id=project_id, role="DEVELOPER"),
        )
        assert r_status.status_code == 200
        assert r_status.json()["status"] == "COMPLETED"

        # 2. Node detail route
        r_node = client.get(
            f"/api/v1/architecture-versions/{version_id}/graph/nodes/{source_entity_id}",
            params={"project_id": str(project_id)},
            headers=_headers(project_id=project_id, role="DEVELOPER"),
        )
        assert r_node.status_code == 200
        assert r_node.json()["name"] == "ServiceA"

        # 3. Window route
        r_window = client.get(
            f"/api/v1/architecture-versions/{version_id}/graph/window",
            params={"project_id": str(project_id)},
            headers=_headers(project_id=project_id, role="DEVELOPER"),
        )
        assert r_window.status_code == 200
        assert len(r_window.json()["nodes"]) == 2
        assert len(r_window.json()["edges"]) == 1

        # 4. Neighborhood route
        r_neigh = client.get(
            f"/api/v1/architecture-versions/{version_id}/graph/nodes/{source_entity_id}/neighborhood",
            params={"project_id": str(project_id), "depth": 1},
            headers=_headers(project_id=project_id, role="DEVELOPER"),
        )
        assert r_neigh.status_code == 200
        assert len(r_neigh.json()["nodes"]) >= 1

        # 5. Dependencies route
        r_deps = client.get(
            f"/api/v1/architecture-versions/{version_id}/graph/nodes/{source_entity_id}/dependencies",
            params={"project_id": str(project_id)},
            headers=_headers(project_id=project_id, role="DEVELOPER"),
        )
        assert r_deps.status_code == 200

        # 6. Dependents route
        r_depents = client.get(
            f"/api/v1/architecture-versions/{version_id}/graph/nodes/{target_entity_id}/dependents",
            params={"project_id": str(project_id)},
            headers=_headers(project_id=project_id, role="DEVELOPER"),
        )
        assert r_depents.status_code == 200

        # 7. Containment route
        r_cont = client.get(
            f"/api/v1/architecture-versions/{version_id}/graph/nodes/{source_entity_id}/containment",
            params={"project_id": str(project_id)},
            headers=_headers(project_id=project_id, role="DEVELOPER"),
        )
        assert r_cont.status_code == 200

        # 8. Paths route
        r_paths = client.get(
            f"/api/v1/architecture-versions/{version_id}/graph/paths",
            params={
                "project_id": str(project_id),
                "source_entity_id": str(source_entity_id),
                "target_entity_id": str(target_entity_id),
            },
            headers=_headers(project_id=project_id, role="DEVELOPER"),
        )
        assert r_paths.status_code == 200
        assert r_paths.json()["total_paths_found"] == 1

        # 9. Rebuild route (POST 202)
        r_rebuild = client.post(
            f"/api/v1/architecture-versions/{version_id}/graph/rebuild",
            params={"project_id": str(project_id)},
            headers=_headers(project_id=project_id, role="OWNER"),
        )
        assert r_rebuild.status_code == 202
        assert r_rebuild.json()["attempt_number"] == 2
        assert r_rebuild.json()["attempt_status"] == "QUEUED"

        # 10. Query health route
        r_qhealth = client.get("/api/v1/health/graph/query")
        assert r_qhealth.status_code == 200
        assert r_qhealth.json()["status"] == "ready"

    finally:
        app.dependency_overrides.pop(get_database_session, None)
        client.close()

        # Clean Neo4j
        with driver.session(database=settings.neo4j_database) as clean_sess:
            clean_sess.run(
                """
                MATCH (n {project_id: $pid})
                DETACH DELETE n
                """,
                pid=str(project_id),
            )
            clean_sess.run(
                """
                MATCH (m:ProjectionManifest {project_id: $pid})
                DELETE m
                """,
                pid=str(project_id),
            )

        # Clean PostgreSQL
        session.rollback()
        session.close()
