"""Real PostgreSQL and Neo4j end-to-end projection pipeline integration tests."""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from dotenv import dotenv_values
from pydantic import SecretStr
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from backend.platform.analysis.architecture.model import ArchitectureDocument
from backend.platform.analysis.architecture.persistence import (
    ArchitectureVersionModel,
)
from backend.platform.analysis.infra.lifecycle_model import AnalysisModel
from backend.platform.config import Settings
from backend.platform.graph.executor import (
    ProjectionExecutor,
)
from backend.platform.graph.lifecycle import GraphProjectionLifecycle
from backend.platform.graph.model import (
    SOURCE_CONTRACT_VERSION,
    ActivationDisposition,
    ProjectionAttemptState,
    ProjectionCounts,
    ProjectionPublicState,
)
from backend.platform.graph.neo4j import Neo4jInfrastructure
from backend.platform.graph.persistence import (
    GraphProjectionAttemptModel,
    GraphProjectionResourceModel,
    SqlAlchemyGraphProjectionRepository,
)
from backend.platform.graph.projection import (
    MANIFEST_STATE_READY,
    build_projection_plan,
)
from backend.platform.graph.projection_store import Neo4jProjectionStore
from backend.platform.graph.source import (
    PublishedArchitectureHeader,
)
from backend.platform.graph.verification import GraphVerifier
from tests.fixtures.p4.graph.fixtures import small_document


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
        pytest.skip("NEO4J_TEST_URI and NEO4J_TEST_PASSWORD are required")
    return Settings(
        neo4j_uri=uri,
        neo4j_user=os.getenv("NEO4J_TEST_USER", "neo4j"),
        neo4j_password=SecretStr(password),
        neo4j_database=os.getenv("NEO4J_TEST_DATABASE", "neo4j"),
        graph_projection_query_timeout_seconds=30.0,
        graph_projection_cleanup_grace_seconds=86400,
    )


@pytest.fixture
def pipeline_env() -> Generator[
    tuple[
        Any,
        Neo4jInfrastructure,
        Neo4jProjectionStore,
        GraphVerifier,
        ProjectionExecutor,
    ]
]:
    settings = _integration_settings()
    engine = create_engine(_database_url())
    infra = Neo4jInfrastructure(settings)

    try:
        infra.initialize()
        store = Neo4jProjectionStore(driver=infra.driver, settings=settings)
        verifier = GraphVerifier(store=store)
        executor = ProjectionExecutor(
            settings=settings,
            store=store,
            verifier=verifier,
            session_factory=lambda: Session(engine),
        )
        yield engine, infra, store, verifier, executor
    finally:
        infra.close()
        engine.dispose()


def _publish_fixture_in_postgres(
    session: Session, doc: ArchitectureDocument
) -> PublishedArchitectureHeader:
    now = datetime.now(UTC)
    session.add(
        AnalysisModel(
            id=doc.analysis_id,
            project_id=doc.project_id,
            repository_id=doc.repository_id,
            snapshot_id=doc.snapshot_id,
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
            id=doc.architecture_version_id,
            analysis_id=doc.analysis_id,
            project_id=doc.project_id,
            repository_id=doc.repository_id,
            snapshot_id=doc.snapshot_id,
            sequence_number=1,
            state="published",
            configuration_fingerprint=doc.configuration_fingerprint,
            analyzer_version=doc.analyzer_version,
            ir_schema_version=doc.ir_schema_version,
            architecture_schema_version=doc.architecture_schema_version,
            content_digest=doc.content_digest,
            completeness={},
            source_diagnostic_ids=[],
            entity_count=len(doc.entities),
            relationship_count=len(doc.relationships),
            evidence_count=len(doc.evidence),
            unresolved_relationship_count=len(doc.unresolved_relationships),
            conflict_count=len(doc.conflicts),
            diagnostic_id=None,
            failure_code=None,
            created_at=now,
            updated_at=now,
            published_at=now,
        )
    )
    session.commit()

    return PublishedArchitectureHeader(
        contract_version=SOURCE_CONTRACT_VERSION,
        architecture_version_id=doc.architecture_version_id,
        analysis_id=doc.analysis_id,
        project_id=doc.project_id,
        repository_id=doc.repository_id,
        snapshot_id=doc.snapshot_id,
        sequence_number=1,
        published_at=now,
        configuration_fingerprint=doc.configuration_fingerprint,
        analyzer_version=doc.analyzer_version,
        ir_schema_version=doc.ir_schema_version,
        architecture_schema_version=doc.architecture_schema_version,
        content_digest=doc.content_digest,
        counts=ProjectionCounts(
            entities=len(doc.entities),
            relationships=len(doc.relationships),
            evidence=len(doc.evidence),
            unresolved=len(doc.unresolved_relationships),
            conflicts=len(doc.conflicts),
        ),
    )


def test_real_pipeline_full_execution_and_m1_activation(
    pipeline_env: Any,
) -> None:
    engine, infra, store, verifier, executor = pipeline_env

    project_id = uuid4()
    version_id = uuid4()
    doc = small_document(project_id=project_id, version_id=version_id)

    with Session(engine) as session:
        header = _publish_fixture_in_postgres(session, doc)
        repo = SqlAlchemyGraphProjectionRepository(session)
        lifecycle = GraphProjectionLifecycle(repo)
        decision = lifecycle.reconcile_published(
            header, correlation_id="pipeline-corr-1"
        )
        assert decision.work is not None
        payload = decision.work
        session.commit()

    import backend.platform.graph.executor as exec_module

    orig_source = exec_module.SqlAlchemyPublishedArchitectureSource
    try:

        class _RealTestSource:
            def __init__(self, s: Any) -> None:
                pass

            def load_exact(self, a_id: UUID, p_id: UUID) -> ArchitectureDocument | None:
                if a_id == version_id and p_id == project_id:
                    return doc
                return None

        exec_module.SqlAlchemyPublishedArchitectureSource = _RealTestSource  # type: ignore

        # Execute projection through executor
        result = executor.execute(payload, worker_id="pipeline-worker-1")

        assert result.status == "completed"
        assert result.disposition == ActivationDisposition.ACTIVATED
        assert result.failure_code is None
        assert result.nodes_written == 2
        assert result.relationships_written == 1

        # Check Neo4j manifest is READY
        plan = build_projection_plan(doc, generation_id=payload.generation_id)
        manifest = store.get_manifest(plan.generation_key)
        assert manifest is not None
        assert manifest["state"] == MANIFEST_STATE_READY
        assert manifest["fence_digest"] is None

        # Check PostgreSQL state
        with Session(engine) as session:
            repo = SqlAlchemyGraphProjectionRepository(session)
            resource = repo.get_resource(payload.projection_id)
            assert resource is not None
            assert resource.state == ProjectionPublicState.COMPLETED
            assert resource.active_generation_id == payload.generation_id
            assert resource.active_counts == header.counts

            attempt = repo.get_attempt(payload.attempt_id)
            assert attempt is not None
            assert attempt.state == ProjectionAttemptState.COMPLETED
            assert attempt.lease_owner is None
    finally:
        exec_module.SqlAlchemyPublishedArchitectureSource = orig_source
        # Cleanup Neo4j
        store.delete_generation(
            project_id=project_id,
            architecture_version_id=version_id,
            generation_id=payload.generation_id,
        )
        # Cleanup Postgres
        with Session(engine) as session:
            session.execute(
                delete(GraphProjectionResourceModel).where(
                    GraphProjectionResourceModel.id == payload.projection_id
                )
            )
            session.execute(
                delete(ArchitectureVersionModel).where(
                    ArchitectureVersionModel.id == version_id
                )
            )
            session.execute(
                delete(AnalysisModel).where(AnalysisModel.id == doc.analysis_id)
            )
            session.commit()


def test_real_pipeline_failed_rebuild_preserves_prior_active_generation(
    pipeline_env: Any,
) -> None:
    engine, infra, store, verifier, executor = pipeline_env

    project_id = uuid4()
    version_id = uuid4()
    doc = small_document(project_id=project_id, version_id=version_id)

    # 1. First generation G1 succeeds and becomes active
    with Session(engine) as session:
        header = _publish_fixture_in_postgres(session, doc)
        repo = SqlAlchemyGraphProjectionRepository(session)
        lifecycle = GraphProjectionLifecycle(repo)
        decision1 = lifecycle.reconcile_published(header, correlation_id="c1")
        assert decision1.work is not None
        payload1 = decision1.work
        session.commit()

    import backend.platform.graph.executor as exec_module

    orig_source = exec_module.SqlAlchemyPublishedArchitectureSource
    try:

        class _RealTestSource:
            def __init__(self, s: Any) -> None:
                pass

            def load_exact(self, a_id: UUID, p_id: UUID) -> ArchitectureDocument | None:
                return doc

        exec_module.SqlAlchemyPublishedArchitectureSource = _RealTestSource  # type: ignore

        result1 = executor.execute(payload1, worker_id="w-1")
        assert result1.status == "completed"

        # 2. Rebuild attempt G2 is created for the same resource
        with Session(engine) as session:
            repo = SqlAlchemyGraphProjectionRepository(session)
            lifecycle = GraphProjectionLifecycle(repo)
            attempt2, payload2 = lifecycle.request_rebuild(
                payload1.projection_id,
                actor_id=uuid4(),
                actor_role="admin",
                correlation_id="c2",
            )
            session.commit()

        # 3. Simulate G2 failure during verification
        from backend.platform.graph.verification import VerificationResult

        gen_key2 = build_projection_plan(
            doc, generation_id=payload2.generation_id
        ).generation_key
        bad_result = VerificationResult(
            verified=False,
            generation_key=gen_key2,
            expected_counts=header.counts,
            actual_counts=header.counts,
            expected_key_set_digest="keys",
            actual_key_set_digest="keys",
            expected_endpoint_digest="endpoints",
            actual_endpoint_digest="endpoints",
            expected_payload_digest="payload",
            actual_payload_digest="tampered",
            failure_code="graph_verification_payload_mismatch",
            failure_message="Deliberate corruption in rebuild test",
        )
        executor._verifier.verify_candidate = lambda **kwargs: bad_result  # type: ignore

        result2 = executor.execute(payload2, worker_id="w-2")
        assert result2.status == "failed"
        assert result2.disposition == ActivationDisposition.RECORDED_FAILURE

        # 4. Assert prior generation G1 remains ACTIVE on PostgreSQL resource!
        with Session(engine) as session:
            repo = SqlAlchemyGraphProjectionRepository(session)
            resource = repo.get_resource(payload1.projection_id)
            assert resource is not None
            assert resource.active_generation_id == payload1.generation_id
            assert resource.state == ProjectionPublicState.COMPLETED
            assert resource.last_failure_code == "graph_verification_payload_mismatch"

            # G2 attempt is FAILED
            att2 = repo.get_attempt(payload2.attempt_id)
            assert att2 is not None
            assert att2.state == ProjectionAttemptState.FAILED

        # 5. Assert G1 in Neo4j remains READY and intact
        plan1 = build_projection_plan(doc, generation_id=payload1.generation_id)
        m1 = store.get_manifest(plan1.generation_key)
        assert m1 is not None
        assert m1["state"] == MANIFEST_STATE_READY
    finally:
        exec_module.SqlAlchemyPublishedArchitectureSource = orig_source
        store.delete_generation(
            project_id=project_id,
            architecture_version_id=version_id,
            generation_id=payload1.generation_id,
        )
        store.delete_generation(
            project_id=project_id,
            architecture_version_id=version_id,
            generation_id=payload2.generation_id,
        )
        with Session(engine) as session:
            session.execute(
                delete(GraphProjectionResourceModel).where(
                    GraphProjectionResourceModel.id == payload1.projection_id
                )
            )
            session.execute(
                delete(ArchitectureVersionModel).where(
                    ArchitectureVersionModel.id == version_id
                )
            )
            session.execute(
                delete(AnalysisModel).where(AnalysisModel.id == doc.analysis_id)
            )
            session.commit()


def test_real_pipeline_cleanup_eligible_generation(
    pipeline_env: Any,
) -> None:
    engine, infra, store, verifier, executor = pipeline_env

    project_id = uuid4()
    version_id = uuid4()
    doc = small_document(project_id=project_id, version_id=version_id)

    # Project G1 and activate
    with Session(engine) as session:
        header = _publish_fixture_in_postgres(session, doc)
        repo = SqlAlchemyGraphProjectionRepository(session)
        lifecycle = GraphProjectionLifecycle(repo)
        decision = lifecycle.reconcile_published(header, correlation_id="clean")
        assert decision.work is not None
        payload = decision.work
        session.commit()

    import backend.platform.graph.executor as exec_module

    orig_source = exec_module.SqlAlchemyPublishedArchitectureSource
    try:

        class _RealTestSource:
            def __init__(self, s: Any) -> None:
                pass

            def load_exact(self, a_id: UUID, p_id: UUID) -> ArchitectureDocument | None:
                return doc

        exec_module.SqlAlchemyPublishedArchitectureSource = _RealTestSource  # type: ignore

        result = executor.execute(payload, worker_id="w-1")
        assert result.status == "completed"

        # Create obsolete/failed generation G2 in Neo4j and PG
        g2_id = uuid4()
        g2_attempt_id = uuid4()
        with Session(engine) as session:
            session.add(
                GraphProjectionAttemptModel(
                    id=g2_attempt_id,
                    resource_id=payload.projection_id,
                    generation_id=g2_id,
                    attempt_number=2,
                    state=ProjectionAttemptState.FAILED.value,
                    actor_type="SYSTEM",
                    correlation_id="c2",
                    contract_version="1.0.0",
                    source_content_digest="src",
                    source_schema_version="1.0.0",
                    graph_schema_version="1.0.0",
                    projector_version="1.0.0",
                    execution_count=3,
                    dispatch_count=3,
                    expected_entity_count=2,
                    expected_relationship_count=1,
                    expected_evidence_count=1,
                    expected_unresolved_count=0,
                    expected_conflict_count=0,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            session.commit()

        # Seed candidate in Neo4j for G2
        plan2 = build_projection_plan(doc, generation_id=g2_id)
        store.claim_candidate(
            project_id=project_id,
            architecture_version_id=version_id,
            generation_id=g2_id,
            resource_id=payload.projection_id,
            attempt_id=g2_attempt_id,
            lease_token="temp-token",
            source_content_digest=plan2.source_content_digest,
            expected_counts=plan2.expected_counts,
            expected_key_set_digest=plan2.key_set_digest,
            expected_endpoint_digest=plan2.endpoint_digest,
            expected_payload_digest=plan2.payload_digest,
            expected_evidence_summary_digest=plan2.evidence_summary_digest,
            expected_unresolved_summary_digest=plan2.unresolved_summary_digest,
            expected_conflict_summary_digest=plan2.conflict_summary_digest,
        )
        store.write_nodes(
            project_id=project_id,
            architecture_version_id=version_id,
            generation_id=g2_id,
            lease_token="temp-token",
            nodes=plan2.nodes,
        )

        # Cleanup G2 with force=True
        clean_res = executor.cleanup_generation(
            project_id=project_id,
            architecture_version_id=version_id,
            generation_id=g2_id,
            force=True,
        )
        assert clean_res.eligible is True
        assert clean_res.deleted_count > 0

        # Verify G2 is gone from Neo4j
        assert store.get_manifest(plan2.generation_key) is None

        # Verify G1 manifest still exists in Neo4j
        plan1 = build_projection_plan(doc, generation_id=payload.generation_id)
        assert store.get_manifest(plan1.generation_key) is not None
    finally:
        exec_module.SqlAlchemyPublishedArchitectureSource = orig_source
        store.delete_generation(
            project_id=project_id,
            architecture_version_id=version_id,
            generation_id=payload.generation_id,
        )
        store.delete_generation(
            project_id=project_id,
            architecture_version_id=version_id,
            generation_id=g2_id,
        )
        with Session(engine) as session:
            session.execute(
                delete(GraphProjectionResourceModel).where(
                    GraphProjectionResourceModel.id == payload.projection_id
                )
            )
            session.execute(
                delete(ArchitectureVersionModel).where(
                    ArchitectureVersionModel.id == version_id
                )
            )
            session.execute(
                delete(AnalysisModel).where(AnalysisModel.id == doc.analysis_id)
            )
            session.commit()
