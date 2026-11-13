"""Real PostgreSQL evidence for M3 generation resolution and exact-version reads."""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.platform.analysis.architecture.persistence import ArchitectureVersionModel
from backend.platform.analysis.infra.lifecycle_model import AnalysisModel
from backend.platform.graph.model import (
    GRAPH_SCHEMA_VERSION,
    PROJECTION_CONTRACT_VERSION,
    PROJECTOR_VERSION,
    ActivationDisposition,
    ProjectionCounts,
    ProjectionPublicState,
    VerificationReceipt,
)
from backend.platform.graph.persistence import (
    GraphProjectionAttemptModel,
    GraphProjectionResourceModel,
    SqlAlchemyGraphProjectionRepository,
)
from backend.platform.graph.query_contracts import (
    GraphProjectionNotFoundError,
    GraphProjectionNotReadyError,
)
from backend.platform.graph.query_repository import SqlAlchemyGraphGenerationReader
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
            entity_count=10,
            relationship_count=15,
            evidence_count=20,
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
        counts=ProjectionCounts(10, 15, 20, 0, 0),
    )


def test_real_postgres_generation_resolution_lifecycle(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    with postgres_session_factory() as session:
        header = _publish_architecture(session)
        lifecycle_repo = SqlAlchemyGraphProjectionRepository(session)
        ensure_result = lifecycle_repo.ensure_with_initial_attempt(
            header, correlation_id="m3-test-1"
        )
        session.commit()
        resource_id = ensure_result.resource.id

        reader = SqlAlchemyGraphGenerationReader(session)

        # 1. Resource in initial state (PENDING) must be rejected
        with pytest.raises(GraphProjectionNotReadyError, match="not ready"):
            reader.resolve_active_generation(
                header.project_id,
                header.architecture_version_id,
            )

        # 2. Acquire lease and activate verified generation
        attempts = tuple(
            session.scalars(
                select(GraphProjectionAttemptModel).where(
                    GraphProjectionAttemptModel.resource_id == resource_id
                )
            )
        )
        assert len(attempts) == 1
        attempt = attempts[0]
        attempt_id = attempt.id
        generation_id = attempt.generation_id
        now = datetime.now(UTC)

        lease = lifecycle_repo.acquire_lease(
            ProjectionWorkPayload(
                projection_id=resource_id,
                attempt_id=attempt_id,
                project_id=header.project_id,
                architecture_version_id=header.architecture_version_id,
                generation_id=generation_id,
                contract_version="1.0.0",
                correlation_id=attempt.correlation_id,
            ).to_claim(),
            worker_id="m3-worker",
            now=now,
            duration=timedelta(minutes=5),
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

        activation = lifecycle_repo.activate_verified(
            receipt, now=now + timedelta(seconds=1)
        )
        assert activation.disposition == ActivationDisposition.ACTIVATED
        session.commit()

    # 3. Fresh session: resolve active generation for COMPLETED resource
    with postgres_session_factory() as session:
        reader = SqlAlchemyGraphGenerationReader(session)
        scope = reader.resolve_active_generation(
            header.project_id,
            header.architecture_version_id,
        )
        assert scope.project_id == header.project_id
        assert scope.architecture_version_id == header.architecture_version_id
        assert scope.generation_id == generation_id
        assert scope.resource_state == ProjectionPublicState.COMPLETED.value
        assert scope.counts.entities == 10
        assert scope.counts.relationships == 15
        assert scope.counts.evidence == 20

        # Verify generation is still active
        is_active = reader.verify_generation_still_active(
            header.project_id,
            header.architecture_version_id,
            generation_id,
        )
        assert is_active is True

        # Inactive generation returns False
        assert (
            reader.verify_generation_still_active(
                header.project_id,
                header.architecture_version_id,
                uuid4(),
            )
            is False
        )

        # 4. Scope isolation: decoy project returns GraphProjectionNotFoundError
        decoy_project_id = uuid4()
        with pytest.raises(GraphProjectionNotFoundError):
            reader.resolve_active_generation(
                decoy_project_id,
                header.architecture_version_id,
            )

        assert (
            reader.verify_generation_still_active(
                decoy_project_id,
                header.architecture_version_id,
                generation_id,
            )
            is False
        )

        # 5. STALE resource with active generation remains readable (§7D.C3)
        res_model = session.get(GraphProjectionResourceModel, resource_id)
        assert res_model is not None
        res_model.state = ProjectionPublicState.STALE.value
        session.commit()

        stale_scope = reader.resolve_active_generation(
            header.project_id,
            header.architecture_version_id,
        )
        assert stale_scope.resource_state == ProjectionPublicState.STALE.value
        assert stale_scope.generation_id == generation_id
        assert (
            reader.verify_generation_still_active(
                header.project_id,
                header.architecture_version_id,
                generation_id,
            )
            is True
        )
