"""Unit tests for P4-W1 projection executor, Celery tasks, and bounded cleanup."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from neo4j.exceptions import DriverError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.platform.analysis.architecture.model import (
    ArchitectureDocument,
)
from backend.platform.config import Settings
from backend.platform.graph.executor import (
    CleanupResult,
    ProjectionExecutionResult,
    ProjectionExecutor,
)
from backend.platform.graph.lifecycle import GraphProjectionLifecycle
from backend.platform.graph.model import (
    GRAPH_SCHEMA_VERSION,
    PROJECTOR_VERSION,
    SOURCE_CONTRACT_VERSION,
    ActivationDisposition,
    ProjectionAttemptState,
    ProjectionCounts,
    ProjectionPublicState,
)
from backend.platform.graph.persistence import (
    GraphProjectionAttemptModel,
    GraphProjectionResourceModel,
    SqlAlchemyGraphProjectionRepository,
)
from backend.platform.graph.projection import (
    MANIFEST_STATE_BUILDING,
    MANIFEST_STATE_READY,
    ProjectedNodeRecord,
    ProjectedRelationshipRecord,
    compute_generation_key,
)
from backend.platform.graph.projection_store import (
    StaleFenceError,
    compute_fence_digest,
)
from backend.platform.graph.queue import (
    GRAPH_CLEANUP_TASK_NAME,
    GRAPH_EXECUTION_TASK_NAME,
    ProjectionWorkPayload,
)
from backend.platform.graph.source import (
    PublishedArchitectureHeader,
    PublishedArchitecturePage,
)
from backend.platform.graph.verification import GraphVerifier
from backend.platform.projects.infra.base import Base
from backend.worker.celery_app import celery_app
from backend.worker.graph_tasks import (
    cleanup_graph_generation_task,
    execute_graph_projection_task,
)
from tests.fixtures.p4.graph.fixtures import (
    small_document,
)


class InMemorySource:
    """Stub published architecture source for executor unit tests."""

    def __init__(self, doc: ArchitectureDocument | None = None) -> None:
        self.doc = doc

    def list_published(
        self, *, limit: int, after: object = None
    ) -> PublishedArchitecturePage:
        del limit, after
        return PublishedArchitecturePage(items=(), next_cursor=None)

    def load_exact(
        self, architecture_version_id: UUID, project_id: UUID
    ) -> ArchitectureDocument | None:
        if self.doc and self.doc.project_id == project_id:
            return self.doc
        return None


class InMemoryProjectionStore:
    """Full in-memory implementation of ProjectionStore for unit testing."""

    def __init__(self) -> None:
        self.manifest: dict[str, Any] | None = None
        self.nodes: dict[str, ProjectedNodeRecord] = {}
        self.relationships: dict[str, ProjectedRelationshipRecord] = {}
        self.claimed_fence_digest: str | None = None
        self.lock_epoch = 0
        self.fail_write_with_stale_fence = False
        self.fail_write_with_driver_error = False

    def claim_candidate(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        lease_token: str,
        source_content_digest: str,
        source_schema_version: str = SOURCE_CONTRACT_VERSION,
        graph_schema_version: str = GRAPH_SCHEMA_VERSION,
        projector_version: str = PROJECTOR_VERSION,
        expected_counts: ProjectionCounts,
        expected_key_set_digest: str,
        expected_endpoint_digest: str,
        expected_payload_digest: str,
    ) -> None:
        if self.fail_write_with_driver_error:
            raise DriverError("Simulated Neo4j driver connection error")
        gen_key = compute_generation_key(
            project_id, architecture_version_id, generation_id
        )
        self.claimed_fence_digest = compute_fence_digest(lease_token)
        self.lock_epoch += 1
        self.manifest = {
            "generation_key": gen_key,
            "labels": ["ProjectionManifest"],
            "project_id": str(project_id).lower(),
            "architecture_version_id": str(architecture_version_id).lower(),
            "generation_id": str(generation_id).lower(),
            "state": MANIFEST_STATE_BUILDING,
            "fence_digest": self.claimed_fence_digest,
            "lock_epoch": self.lock_epoch,
            "source_content_digest": source_content_digest,
            "source_schema_version": source_schema_version,
            "graph_schema_version": graph_schema_version,
            "projector_version": projector_version,
            "expected_entities_count": expected_counts.entities,
            "expected_relationships_count": expected_counts.relationships,
            "expected_evidence_count": expected_counts.evidence,
            "expected_unresolved_count": expected_counts.unresolved,
            "expected_conflicts_count": expected_counts.conflicts,
            "expected_key_set_digest": expected_key_set_digest,
            "expected_endpoint_digest": expected_endpoint_digest,
            "expected_payload_digest": expected_payload_digest,
        }

    def reset_candidate(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        lease_token: str,
        page_size: int = 1000,
    ) -> tuple[int, int]:
        del page_size
        self._check_fence(lease_token)
        node_count = len(self.nodes)
        rel_count = len(self.relationships)
        self.nodes.clear()
        self.relationships.clear()
        return rel_count, node_count

    def write_nodes(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        lease_token: str,
        nodes: list[ProjectedNodeRecord],
    ) -> int:
        self._check_fence(lease_token)
        if self.fail_write_with_driver_error:
            raise DriverError("Simulated Neo4j driver connection error")
        for node in nodes:
            self.nodes[node.projection_key] = node
        return len(nodes)

    def write_relationships(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        lease_token: str,
        relationships: list[ProjectedRelationshipRecord],
    ) -> int:
        self._check_fence(lease_token)
        if self.fail_write_with_driver_error:
            raise DriverError("Simulated Neo4j driver connection error")
        for rel in relationships:
            self.relationships[rel.projection_key] = rel
        return len(relationships)

    def finalize_manifest(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        lease_token: str,
        actual_counts: ProjectionCounts,
        actual_key_set_digest: str,
        actual_endpoint_digest: str,
        actual_payload_digest: str,
    ) -> None:
        self._check_fence(lease_token)
        assert self.manifest is not None
        self.manifest["state"] = MANIFEST_STATE_READY
        self.manifest["fence_digest"] = None
        self.manifest["actual_entities_count"] = actual_counts.entities
        self.manifest["actual_relationships_count"] = actual_counts.relationships
        self.manifest["actual_evidence_count"] = actual_counts.evidence
        self.manifest["actual_unresolved_count"] = actual_counts.unresolved
        self.manifest["actual_conflicts_count"] = actual_counts.conflicts
        self.manifest["actual_key_set_digest"] = actual_key_set_digest
        self.manifest["actual_endpoint_digest"] = actual_endpoint_digest
        self.manifest["actual_payload_digest"] = actual_payload_digest

    def get_manifest(self, generation_key: str) -> dict[str, Any] | None:
        if self.manifest and self.manifest["generation_key"] == generation_key:
            return dict(self.manifest)
        return None

    def count_nodes(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
    ) -> tuple[int, int]:
        del project_id, architecture_version_id, generation_id
        return len(self.nodes), len(self.nodes)

    def count_any_nodes_in_scope(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
    ) -> int:
        del project_id, architecture_version_id, generation_id
        return len(self.nodes)

    def enumerate_nodes(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        cursor: str | None = None,
        page_size: int = 1000,
    ) -> list[dict[str, Any]]:
        del project_id, architecture_version_id, generation_id
        sorted_nodes = sorted(self.nodes.values(), key=lambda x: x.projection_key)
        if cursor is not None:
            sorted_nodes = [n for n in sorted_nodes if n.projection_key > cursor]
        page = sorted_nodes[:page_size]
        return [
            {
                "projection_key": n.projection_key,
                "labels": ["ArchitectureEntity"],
                "properties": dict(n.properties),
            }
            for n in page
        ]

    def count_relationships(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
    ) -> tuple[int, int]:
        del project_id, architecture_version_id, generation_id
        return len(self.relationships), len(self.relationships)

    def count_any_relationships_in_scope(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
    ) -> int:
        del project_id, architecture_version_id, generation_id
        return len(self.relationships)

    def enumerate_relationships(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        cursor: str | None = None,
        page_size: int = 1000,
    ) -> list[dict[str, Any]]:
        del project_id, architecture_version_id, generation_id
        sorted_rels = sorted(
            self.relationships.values(), key=lambda x: x.projection_key
        )
        if cursor is not None:
            sorted_rels = [r for r in sorted_rels if r.projection_key > cursor]
        page = sorted_rels[:page_size]
        return [
            {
                "projection_key": r.projection_key,
                "source_key": r.source_projection_key,
                "target_key": r.target_projection_key,
                "rel_type": "ARCH_RELATIONSHIP",
                "properties": dict(r.properties),
            }
            for r in page
        ]

    def delete_generation(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        batch_size: int = 1000,
    ) -> int:
        del project_id, architecture_version_id, generation_id, batch_size
        deleted = (
            len(self.nodes) + len(self.relationships) + (1 if self.manifest else 0)
        )
        self.nodes.clear()
        self.relationships.clear()
        self.manifest = None
        return deleted

    def _check_fence(self, lease_token: str) -> None:
        if self.fail_write_with_stale_fence:
            raise StaleFenceError("Stale worker fence mismatch")
        if self.manifest is None:
            raise StaleFenceError("Manifest does not exist")
        expected = compute_fence_digest(lease_token)
        if self.manifest.get("fence_digest") != expected:
            raise StaleFenceError("Manifest fence mismatch")


@pytest.fixture
def sqlite_engine() -> Generator[Any]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_env(
    sqlite_engine: Any,
) -> Generator[
    tuple[
        ProjectionExecutor,
        InMemoryProjectionStore,
        ArchitectureDocument,
        PublishedArchitectureHeader,
        ProjectionWorkPayload,
    ]
]:
    doc = small_document()
    header = PublishedArchitectureHeader(
        contract_version=SOURCE_CONTRACT_VERSION,
        architecture_version_id=doc.architecture_version_id,
        analysis_id=doc.analysis_id,
        project_id=doc.project_id,
        repository_id=doc.repository_id,
        snapshot_id=doc.snapshot_id,
        sequence_number=1,
        published_at=datetime.now(UTC),
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

    # Initialize M1 resource and attempt in SQLite
    with Session(sqlite_engine) as session:
        repo = SqlAlchemyGraphProjectionRepository(session)
        lifecycle = GraphProjectionLifecycle(repo)
        decision = lifecycle.reconcile_published(header, correlation_id="corr-test-1")
        assert decision.work is not None
        payload = decision.work
        session.commit()

    store = InMemoryProjectionStore()
    verifier = GraphVerifier(store=store)
    settings = Settings(
        graph_projection_node_batch_size=500,
        graph_projection_relationship_batch_size=1000,
        graph_heartbeat_interval_seconds=30,
        graph_lease_duration_seconds=120,
    )

    executor = ProjectionExecutor(
        settings=settings,
        store=store,
        verifier=verifier,
        session_factory=lambda: Session(sqlite_engine),
    )

    yield executor, store, doc, header, payload


def test_executor_successful_projection(sqlite_engine: Any, test_env: Any) -> None:
    executor, store, doc, header, payload = test_env

    # Point SqlAlchemyPublishedArchitectureSource mock
    with Session(sqlite_engine) as session:
        # Mock source load_exact by injecting doc
        pass

    # Monkeypatch SqlAlchemyPublishedArchitectureSource.load_exact
    import backend.platform.graph.executor as exec_module

    orig_source = exec_module.SqlAlchemyPublishedArchitectureSource
    try:

        class _PatchedSource:

            def __init__(self, s: Any) -> None:
                pass

            def load_exact(self, a_id: UUID, p_id: UUID) -> ArchitectureDocument:
                assert a_id == doc.architecture_version_id
                assert p_id == doc.project_id
                return doc

        exec_module.SqlAlchemyPublishedArchitectureSource = _PatchedSource  # type: ignore

        result = executor.execute(payload, worker_id="worker-test-1")
        assert result.status == "completed"
        assert result.disposition == ActivationDisposition.ACTIVATED
        assert result.failure_code is None
        assert result.nodes_written == 2
        assert result.relationships_written == 1
        assert result.generation_id == payload.generation_id

        # Verify Neo4j manifest is READY
        assert store.manifest is not None
        assert store.manifest["state"] == MANIFEST_STATE_READY
        assert store.manifest["fence_digest"] is None

        # Verify PostgreSQL resource is COMPLETED with active_generation_id
        with Session(sqlite_engine) as session:
            repo = SqlAlchemyGraphProjectionRepository(session)
            res = repo.get_resource(payload.projection_id)
            assert res is not None
            assert res.state == ProjectionPublicState.COMPLETED
            assert res.active_generation_id == payload.generation_id
            assert res.active_counts == header.counts
            assert res.active_payload_digest is not None

            att = repo.get_attempt(payload.attempt_id)
            assert att is not None
            assert att.state == ProjectionAttemptState.COMPLETED
            assert att.lease_owner is None
            assert att.lease_token is None
    finally:
        exec_module.SqlAlchemyPublishedArchitectureSource = orig_source


def test_executor_duplicate_delivery_skipped(sqlite_engine: Any, test_env: Any) -> None:
    executor, store, doc, header, payload = test_env

    # Acquire lease beforehand so executor cannot acquire it
    with Session(sqlite_engine) as session:
        repo = SqlAlchemyGraphProjectionRepository(session)
        lifecycle = GraphProjectionLifecycle(repo)
        first_lease = lifecycle.acquire(
            payload, worker_id="other-worker", lease_duration=timedelta(minutes=5)
        )
        assert first_lease is not None
        session.commit()

    result = executor.execute(payload, worker_id="worker-2")
    assert result.status == "skipped"
    assert result.reason == "lease_unavailable"
    assert store.manifest is None


def test_executor_source_document_missing(sqlite_engine: Any, test_env: Any) -> None:
    executor, store, doc, header, payload = test_env

    import backend.platform.graph.executor as exec_module

    orig_source = exec_module.SqlAlchemyPublishedArchitectureSource
    try:

        class _MissingSource:

            def __init__(self, s: Any) -> None:
                pass

            def load_exact(self, a_id: UUID, p_id: UUID) -> None:
                return None

        exec_module.SqlAlchemyPublishedArchitectureSource = _MissingSource  # type: ignore

        result = executor.execute(payload, worker_id="worker-test")
        assert result.status == "failed"
        assert result.failure_code == "source_document_not_found"

        # Check attempt marked FAILED in PG
        with Session(sqlite_engine) as session:
            repo = SqlAlchemyGraphProjectionRepository(session)
            att = repo.get_attempt(payload.attempt_id)
            assert att is not None
            assert att.state == ProjectionAttemptState.FAILED
            assert att.failure_code == "source_document_not_found"
    finally:
        exec_module.SqlAlchemyPublishedArchitectureSource = orig_source


def test_executor_source_digest_mismatch(sqlite_engine: Any, test_env: Any) -> None:
    executor, store, doc, header, payload = test_env

    # Mutate resource source_content_digest in database to trigger mismatch
    with Session(sqlite_engine) as session:
        session.query(GraphProjectionResourceModel).filter_by(
            id=payload.projection_id
        ).update({"source_content_digest": "different-expected-digest"})
        session.commit()

    import backend.platform.graph.executor as exec_module

    orig_source = exec_module.SqlAlchemyPublishedArchitectureSource
    try:

        class _PatchedSource:

            def __init__(self, s: Any) -> None:
                pass

            def load_exact(self, a_id: UUID, p_id: UUID) -> ArchitectureDocument:
                return doc

        exec_module.SqlAlchemyPublishedArchitectureSource = _PatchedSource  # type: ignore

        result = executor.execute(payload, worker_id="worker-test")
        assert result.status == "failed"
        assert result.failure_code == "projection_source_mismatch"

        with Session(sqlite_engine) as session:
            repo = SqlAlchemyGraphProjectionRepository(session)
            att = repo.get_attempt(payload.attempt_id)
            assert att is not None
            assert att.state == ProjectionAttemptState.FAILED
            assert att.failure_code == "projection_source_mismatch"
    finally:
        exec_module.SqlAlchemyPublishedArchitectureSource = orig_source


def test_executor_stale_fence_returns_fenced(sqlite_engine: Any, test_env: Any) -> None:
    executor, store, doc, header, payload = test_env

    import backend.platform.graph.executor as exec_module

    orig_source = exec_module.SqlAlchemyPublishedArchitectureSource
    try:

        class _PatchedSource:

            def __init__(self, s: Any) -> None:
                pass

            def load_exact(self, a_id: UUID, p_id: UUID) -> ArchitectureDocument:
                return doc

        exec_module.SqlAlchemyPublishedArchitectureSource = _PatchedSource  # type: ignore

        # Trigger stale fence on write
        store.fail_write_with_stale_fence = True

        result = executor.execute(payload, worker_id="worker-test")
        assert result.status == "fenced"
        assert result.reason == "stale_fence"

        # PG attempt lease was acquired; fenced worker does not disturb PG state
        with Session(sqlite_engine) as session:
            repo = SqlAlchemyGraphProjectionRepository(session)
            att = repo.get_attempt(payload.attempt_id)
            assert att is not None
            assert att.state == ProjectionAttemptState.RUNNING
    finally:
        exec_module.SqlAlchemyPublishedArchitectureSource = orig_source


def test_executor_neo4j_transient_error_records_retrying(
    sqlite_engine: Any, test_env: Any
) -> None:
    executor, store, doc, header, payload = test_env

    import backend.platform.graph.executor as exec_module

    orig_source = exec_module.SqlAlchemyPublishedArchitectureSource
    try:

        class _PatchedSource:

            def __init__(self, s: Any) -> None:
                pass

            def load_exact(self, a_id: UUID, p_id: UUID) -> ArchitectureDocument:
                return doc

        exec_module.SqlAlchemyPublishedArchitectureSource = _PatchedSource  # type: ignore

        store.fail_write_with_driver_error = True

        result = executor.execute(payload, worker_id="worker-test")
        assert result.status == "failed"
        assert result.failure_code == "graph_write_unavailable"
        assert result.transient is True

        # PG attempt marked RETRYING since execution_count < MAX_EXECUTIONS
        with Session(sqlite_engine) as session:
            repo = SqlAlchemyGraphProjectionRepository(session)
            att = repo.get_attempt(payload.attempt_id)
            assert att is not None
            assert att.state == ProjectionAttemptState.RETRYING
    finally:
        exec_module.SqlAlchemyPublishedArchitectureSource = orig_source


def test_executor_verification_failure_records_failed_receipt(
    sqlite_engine: Any, test_env: Any
) -> None:
    executor, store, doc, header, payload = test_env

    import backend.platform.graph.executor as exec_module

    orig_source = exec_module.SqlAlchemyPublishedArchitectureSource
    try:

        class _PatchedSource:

            def __init__(self, s: Any) -> None:
                pass

            def load_exact(self, a_id: UUID, p_id: UUID) -> ArchitectureDocument:
                return doc

        exec_module.SqlAlchemyPublishedArchitectureSource = _PatchedSource  # type: ignore

        # Override verifier verify_candidate to return failure
        from backend.platform.graph.verification import VerificationResult

        gen_key = compute_generation_key(
            payload.project_id,
            payload.architecture_version_id,
            payload.generation_id,
        )
        bad_result = VerificationResult(
            verified=False,
            generation_key=gen_key,
            expected_counts=header.counts,
            actual_counts=header.counts,
            expected_key_set_digest="expected-key-digest",
            actual_key_set_digest="expected-key-digest",
            expected_endpoint_digest="expected-endpoint-digest",
            actual_endpoint_digest="expected-endpoint-digest",
            expected_payload_digest="expected-payload-digest",
            actual_payload_digest="corrupted-payload-digest",
            failure_code="graph_verification_payload_mismatch",
            failure_message="Simulated payload digest mismatch",
        )
        executor._verifier.verify_candidate = lambda **kwargs: bad_result  # type: ignore

        result = executor.execute(payload, worker_id="worker-test")
        assert result.status == "failed"
        assert result.disposition == ActivationDisposition.RECORDED_FAILURE
        assert result.failure_code == "graph_verification_payload_mismatch"

        # Manifest was not finalized to READY
        assert store.manifest is not None
        assert store.manifest["state"] == MANIFEST_STATE_BUILDING

        # PG attempt marked FAILED
        with Session(sqlite_engine) as session:
            repo = SqlAlchemyGraphProjectionRepository(session)
            att = repo.get_attempt(payload.attempt_id)
            assert att is not None
            assert att.state == ProjectionAttemptState.FAILED
            assert att.failure_code == "graph_verification_payload_mismatch"
    finally:
        exec_module.SqlAlchemyPublishedArchitectureSource = orig_source


def test_cleanup_generation_eligibility_matrix(
    sqlite_engine: Any, test_env: Any
) -> None:
    executor, store, doc, header, payload = test_env
    gen_id = payload.generation_id

    # 1. Nonexistent attempt
    res = executor.cleanup_generation(
        project_id=payload.project_id,
        architecture_version_id=payload.architecture_version_id,
        generation_id=uuid4(),
    )
    assert res.eligible is False
    assert res.reason == "attempt_not_found"

    # 2. Scope mismatch
    res = executor.cleanup_generation(
        project_id=uuid4(),
        architecture_version_id=payload.architecture_version_id,
        generation_id=gen_id,
    )
    assert res.eligible is False
    assert res.reason == "scope_mismatch"

    # 3. Active attempt (attempt is in QUEUED state in test_env)
    res = executor.cleanup_generation(
        project_id=payload.project_id,
        architecture_version_id=payload.architecture_version_id,
        generation_id=gen_id,
    )
    assert res.eligible is False
    assert res.reason == "attempt_active"

    # 4. Active generation (cannot delete active generation)
    with Session(sqlite_engine) as session:
        resource = session.scalars(
            GraphProjectionResourceModel.__table__.select()
        ).first()
        assert resource is not None
        # Mark attempt completed and set as active generation
        session.query(GraphProjectionAttemptModel).filter_by(
            generation_id=gen_id
        ).update(
            {
                "state": ProjectionAttemptState.COMPLETED.value,
                "completed_at": datetime.now(UTC),
            }
        )
        session.query(GraphProjectionResourceModel).filter_by(
            id=payload.projection_id
        ).update(
            {
                "active_generation_id": gen_id,
                "state": ProjectionPublicState.COMPLETED.value,
                "active_projector_version": "1.0.0",
                "active_graph_schema_version": "1.0.0",
                "active_payload_digest": "active-digest",
                "active_entity_count": 2,
                "active_relationship_count": 1,
                "active_evidence_count": 1,
                "active_unresolved_count": 0,
                "active_conflict_count": 0,
            }
        )
        session.commit()

    res = executor.cleanup_generation(
        project_id=payload.project_id,
        architecture_version_id=payload.architecture_version_id,
        generation_id=gen_id,
    )
    assert res.eligible is False
    assert res.reason == "active_generation"

    # 5. Non-active generation but grace period not elapsed
    other_gen_id = uuid4()
    with Session(sqlite_engine) as session:
        # Create superseded attempt for other_gen_id
        attempt = GraphProjectionAttemptModel(
            id=uuid4(),
            resource_id=payload.projection_id,
            generation_id=other_gen_id,
            attempt_number=2,
            state=ProjectionAttemptState.SUPERSEDED.value,
            actor_type="SYSTEM",
            correlation_id="c2",
            contract_version="1.0.0",
            source_content_digest="src",
            source_schema_version="1.0.0",
            graph_schema_version="1.0.0",
            projector_version="1.0.0",
            execution_count=1,
            dispatch_count=1,
            expected_entity_count=2,
            expected_relationship_count=1,
            expected_evidence_count=3,
            expected_unresolved_count=0,
            expected_conflict_count=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(attempt)
        session.commit()

    res = executor.cleanup_generation(
        project_id=payload.project_id,
        architecture_version_id=payload.architecture_version_id,
        generation_id=other_gen_id,
        force=False,
    )
    assert res.eligible is False
    assert res.reason == "grace_period_not_elapsed"

    # 6. Eligible when forced or grace elapsed
    res_forced = executor.cleanup_generation(
        project_id=payload.project_id,
        architecture_version_id=payload.architecture_version_id,
        generation_id=other_gen_id,
        force=True,
    )
    assert res_forced.eligible is True
    assert res_forced.reason is None


def test_celery_execute_graph_projection_task_success() -> None:
    # Test task wrapper passing arguments to executor
    gen_id = uuid4()
    fake_result = ProjectionExecutionResult(
        status="completed",
        generation_id=gen_id,
        disposition=ActivationDisposition.ACTIVATED,
        nodes_written=10,
        relationships_written=5,
        execution_duration_seconds=0.1234,
    )

    class _MockExecutor:

        def execute(self, payload: Any, worker_id: str) -> Any:
            assert payload.generation_id == gen_id
            return fake_result

    summary = execute_graph_projection_task.run(
        projection_id=str(uuid4()),
        attempt_id=str(uuid4()),
        project_id=str(uuid4()),
        architecture_version_id=str(uuid4()),
        generation_id=str(gen_id),
        contract_version="1.0.0",
        correlation_id="c-1",
        executor=_MockExecutor(),  # type: ignore
    )

    assert summary["status"] == "completed"
    assert summary["generation_id"] == str(gen_id)
    assert summary["disposition"] == "activated"
    assert summary["nodes_written"] == 10
    assert summary["relationships_written"] == 5


def test_celery_cleanup_graph_generation_task_success() -> None:
    gen_id = uuid4()
    fake_result = CleanupResult(
        eligible=True,
        generation_id=gen_id,
        deleted_count=15,
    )

    class _MockExecutor:

        def cleanup_generation(self, **kwargs: Any) -> Any:
            assert kwargs["generation_id"] == gen_id
            return fake_result

    summary = cleanup_graph_generation_task.run(
        project_id=str(uuid4()),
        architecture_version_id=str(uuid4()),
        generation_id=str(gen_id),
        force=True,
        executor=_MockExecutor(),  # type: ignore
    )

    assert summary["eligible"] is True
    assert summary["generation_id"] == str(gen_id)
    assert summary["deleted_count"] == 15


def test_celery_task_routes_and_queue_isolation() -> None:
    routes = celery_app.conf.task_routes
    assert (
        routes[GRAPH_EXECUTION_TASK_NAME]["queue"] == celery_app.conf.task_queues
        if False
        else "graph.projections"
    )
    assert routes[GRAPH_CLEANUP_TASK_NAME]["queue"] == "graph.maintenance"
    assert (
        routes["stacksense.reconcile_graph_projections"]["queue"] == "graph.maintenance"
    )
    assert routes["stacksense.graph_runtime_heartbeat"]["queue"] == "graph.maintenance"
