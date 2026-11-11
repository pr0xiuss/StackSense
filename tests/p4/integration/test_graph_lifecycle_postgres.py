"""Real PostgreSQL evidence for M1 lifecycle constraints and concurrency."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, delete, inspect, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from backend.platform.analysis.architecture.persistence import ArchitectureVersionModel
from backend.platform.analysis.infra.lifecycle_model import AnalysisModel
from backend.platform.graph.lifecycle import GraphProjectionReconciler
from backend.platform.graph.model import (
    GRAPH_SCHEMA_VERSION,
    PROJECTION_CONTRACT_VERSION,
    PROJECTOR_VERSION,
    ActivationDisposition,
    ProjectionCounts,
    VerificationReceipt,
)
from backend.platform.graph.persistence import (
    GraphProjectionAttemptModel,
    GraphProjectionResourceModel,
    SqlAlchemyGraphProjectionRepository,
)
from backend.platform.graph.queue import (
    InMemoryProjectionPublisher,
    ProjectionWorkPayload,
)
from backend.platform.graph.source import (
    PublishedArchitectureHeader,
    PublishedArchitecturePage,
)


def _database_url() -> str:
    value = os.getenv("STACKSENSE_TEST_DATABASE_URL")
    if value is None:
        configured = dotenv_values(".env").get("DATABASE_URL")
        if not isinstance(configured, str) or not configured:
            raise RuntimeError("DATABASE_URL is required for PostgreSQL integration")
        value = configured
    return value.replace("postgresql://", "postgresql+psycopg://", 1)


def _published(session: Session) -> PublishedArchitectureHeader:
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
            evidence_count=3,
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
        counts=ProjectionCounts(2, 1, 3, 0, 0),
    )


def test_postgres_schema_and_concurrent_ensure_are_idempotent() -> None:
    engine = create_engine(_database_url(), pool_pre_ping=True)
    factory = sessionmaker(engine)
    with factory() as session:
        header = _published(session)

    def ensure(correlation: str) -> tuple[UUID, bool]:
        with factory() as session:
            result = SqlAlchemyGraphProjectionRepository(
                session
            ).ensure_with_initial_attempt(header, correlation_id=correlation)
            session.commit()
            return result.resource.id, result.created

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(ensure, ("concurrent-one", "concurrent-two")))

    assert results[0][0] == results[1][0]
    assert sorted(created for _, created in results) == [False, True]
    inspector = inspect(engine)
    assert inspector.has_table("graph_runtime_capabilities")
    runtime_pk = inspector.get_pk_constraint("graph_runtime_capabilities")
    assert runtime_pk["constrained_columns"] == ["capability", "worker_id"]
    indexes = {
        item["name"]: item
        for item in inspector.get_indexes("graph_projection_attempts")
    }
    assert indexes["uq_graph_attempt_one_active"]["unique"]
    assert "state" in str(indexes["uq_graph_attempt_one_active"]["dialect_options"])
    foreign_keys = {
        item["name"]: item
        for item in inspector.get_foreign_keys("graph_projection_resources")
    }
    active_fk = foreign_keys["fk_graph_resource_active_generation"]
    assert active_fk["referred_table"] == "graph_projection_attempts"
    assert active_fk["options"]["deferrable"] is True
    assert active_fk["options"]["initially"] == "DEFERRED"
    resource_checks = {
        item["name"]
        for item in inspector.get_check_constraints("graph_projection_resources")
    }
    attempt_checks = {
        item["name"]
        for item in inspector.get_check_constraints("graph_projection_attempts")
    }
    assert "ck_graph_resource_active_summary" in resource_checks
    assert "ck_graph_resource_state_active_generation" in resource_checks
    assert "ck_graph_attempt_actual_counts" in attempt_checks
    assert "ck_graph_attempt_actor_fields" in attempt_checks
    assert "ck_graph_attempt_lease_state" in attempt_checks

    first_session = factory()
    second_session = factory()
    try:
        first_writer = first_session.get(GraphProjectionResourceModel, results[0][0])
        second_writer = second_session.get(GraphProjectionResourceModel, results[0][0])
        assert first_writer is not None and second_writer is not None
        first_writer.last_failure_message = "first writer"
        first_session.commit()
        second_writer.last_failure_message = "stale writer"
        with pytest.raises(StaleDataError):
            second_session.commit()
        second_session.rollback()
    finally:
        first_session.close()
        second_session.close()

    with factory() as session:
        resource = session.scalar(
            select(GraphProjectionResourceModel).where(
                GraphProjectionResourceModel.architecture_version_id
                == header.architecture_version_id
            )
        )
        assert resource is not None
        attempts = tuple(
            session.scalars(
                select(GraphProjectionAttemptModel).where(
                    GraphProjectionAttemptModel.resource_id == resource.id
                )
            )
        )
        assert len(attempts) == 1
        resource_id = resource.id
        attempt_id = attempts[0].id
        generation_id = attempts[0].generation_id
        repository = SqlAlchemyGraphProjectionRepository(session)
        now = datetime.now(UTC)
        lease = repository.acquire_lease(
            ProjectionWorkPayload(
                projection_id=resource_id,
                attempt_id=attempt_id,
                project_id=header.project_id,
                architecture_version_id=header.architecture_version_id,
                generation_id=generation_id,
                contract_version="1.0.0",
                correlation_id=attempts[0].correlation_id,
            ).to_claim(),
            worker_id="worker",
            now=now,
            duration=timedelta(minutes=1),
        )
        assert lease is not None
        session.commit()

    receipt = VerificationReceipt(
        resource_id=resource_id,
        attempt_id=attempt_id,
        generation_id=generation_id,
        project_id=header.project_id,
        architecture_version_id=header.architecture_version_id,
        lease_owner=lease.worker_id,
        lease_token=lease.token,
        contract_version=PROJECTION_CONTRACT_VERSION,
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

    def activate(_: int) -> ActivationDisposition:
        with factory() as session:
            result = SqlAlchemyGraphProjectionRepository(session).activate_verified(
                receipt,
                now=now + timedelta(seconds=1),
            )
            session.commit()
            return result.disposition

    with ThreadPoolExecutor(max_workers=2) as executor:
        dispositions = tuple(executor.map(activate, (1, 2)))
    assert sorted(dispositions) == sorted(
        (ActivationDisposition.ACTIVATED, ActivationDisposition.ALREADY_ACTIVATED)
    )

    with factory() as session:
        session.execute(
            delete(GraphProjectionResourceModel).where(
                GraphProjectionResourceModel.id == resource_id
            )
        )
        session.execute(
            delete(ArchitectureVersionModel).where(
                ArchitectureVersionModel.id == header.architecture_version_id
            )
        )
        session.execute(
            delete(AnalysisModel).where(AnalysisModel.id == header.analysis_id)
        )
        session.commit()
    engine.dispose()


def test_real_postgres_concurrent_reconcilers_create_one_durable_attempt() -> None:
    engine = create_engine(_database_url(), pool_pre_ping=True)
    factory = sessionmaker(engine)
    with factory() as session:
        header = _published(session)
    barrier = Barrier(2)

    class ConcurrentSource:
        def list_published(self, *, limit: int, after: object = None):
            del limit, after
            barrier.wait(timeout=5)
            return PublishedArchitecturePage(items=(header,), next_cursor=None)

        def load_exact(self, architecture_version_id: UUID, project_id: UUID):
            del architecture_version_id, project_id
            return None

    def reconcile(correlation: str) -> int:
        with factory() as session:
            summary = GraphProjectionReconciler(
                source=ConcurrentSource(),
                repository=SqlAlchemyGraphProjectionRepository(session),
                publisher=InMemoryProjectionPublisher(),
                checkpoint=session.commit,
                rollback=session.rollback,
                execution_ready=lambda: False,
                page_size=100,
                recovery_batch_size=100,
                dispatch_recovery_after=timedelta(seconds=30),
                retry_backoff=timedelta(seconds=5),
            ).reconcile(correlation_id=correlation)
            return summary.resources_created

    with ThreadPoolExecutor(max_workers=2) as executor:
        created = tuple(executor.map(reconcile, ("reconciler-one", "reconciler-two")))
    assert sorted(created) == [0, 1]

    with factory() as session:
        resource = session.scalar(
            select(GraphProjectionResourceModel).where(
                GraphProjectionResourceModel.architecture_version_id
                == header.architecture_version_id
            )
        )
        assert resource is not None
        attempts = tuple(
            session.scalars(
                select(GraphProjectionAttemptModel).where(
                    GraphProjectionAttemptModel.resource_id == resource.id
                )
            )
        )
        assert len(attempts) == 1
        session.delete(resource)
        session.flush()
        session.execute(
            delete(ArchitectureVersionModel).where(
                ArchitectureVersionModel.id == header.architecture_version_id
            )
        )
        session.execute(
            delete(AnalysisModel).where(AnalysisModel.id == header.analysis_id)
        )
        session.commit()
    engine.dispose()
