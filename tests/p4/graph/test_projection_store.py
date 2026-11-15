"""Unit tests for Neo4j projection store adapter, batching, fencing, and cleanup."""

from __future__ import annotations

from typing import Any

import pytest

from backend.platform.config import Settings
from backend.platform.graph.model import (
    ProjectionCounts,
)
from backend.platform.graph.projection import (
    MANIFEST_STATE_BUILDING,
    MANIFEST_STATE_READY,
    build_projection_plan,
)
from backend.platform.graph.projection_store import (
    GraphWriteIncompleteError,
    ManifestLockError,
    Neo4jProjectionStore,
    ProjectionStoreStateError,
    StaleFenceError,
    compute_fence_digest,
)
from tests.fixtures.p4.graph.fixtures import (
    DEFAULT_GENERATION_ID,
    DEFAULT_PROJECT_ID,
    DEFAULT_VERSION_ID,
    small_document,
)


class _FakeRecord:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def data(self) -> dict[str, Any]:
        return dict(self._data)


class _FakeResult:
    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self._records = [_FakeRecord(r) for r in (records or [])]

    def single(self, strict: bool = False) -> _FakeRecord | None:
        if not self._records:
            return None
        return self._records[0]

    def data(self) -> list[dict[str, Any]]:
        return [r.data() for r in self._records]

    def consume(self) -> None:
        pass


class _FakeTransaction:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session
        self.committed = False
        self.rolled_back = False

    def run(self, query: Any, **parameters: Any) -> _FakeResult:
        return self._session.handle_run(query, parameters)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def __enter__(self) -> _FakeTransaction:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.rollback()


class _FakeSession:
    def __init__(self) -> None:
        self.queries_run: list[tuple[str, dict[str, Any]]] = []
        self.responses: dict[str, list[dict[str, Any]]] = {}
        self.active_tx: _FakeTransaction | None = None
        self.closed = False

    def handle_run(self, query: Any, parameters: dict[str, Any]) -> _FakeResult:
        query_text = query.text if hasattr(query, "text") else str(query)
        self.queries_run.append((query_text, parameters))

        for prefix, records in self.responses.items():
            if prefix in query_text:
                return _FakeResult(records)
        return _FakeResult([])

    def run(self, query: Any, **parameters: Any) -> _FakeResult:
        return self.handle_run(query, parameters)

    def begin_transaction(
        self, timeout: float | None = None, **kwargs: Any
    ) -> _FakeTransaction:
        self.active_tx = _FakeTransaction(self)
        return self.active_tx

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


class _FakeDriver:
    def __init__(self) -> None:
        self.session_instance = _FakeSession()

    def session(self, database: str | None = None) -> _FakeSession:
        return self.session_instance

    def close(self) -> None:
        self.session_instance.close()


@pytest.fixture
def mock_store() -> tuple[Neo4jProjectionStore, _FakeSession]:
    driver = _FakeDriver()
    settings = Settings(neo4j_database="neo4j")
    store = Neo4jProjectionStore(driver=driver, settings=settings)  # type: ignore[arg-type]
    return store, driver.session_instance


def test_claim_candidate_creates_new_manifest(
    mock_store: tuple[Neo4jProjectionStore, _FakeSession],
) -> None:
    store, session = mock_store
    session.responses["MERGE (m:ProjectionManifest"] = [
        {
            "created": True,
            "state": MANIFEST_STATE_BUILDING,
            "project_id": str(DEFAULT_PROJECT_ID).lower(),
            "architecture_version_id": str(DEFAULT_VERSION_ID).lower(),
            "generation_id": str(DEFAULT_GENERATION_ID).lower(),
            "fence_digest": compute_fence_digest("token-1"),
        }
    ]

    counts = ProjectionCounts(
        entities=2, relationships=1, evidence=1, unresolved=0, conflicts=0
    )
    store.claim_candidate(
        project_id=DEFAULT_PROJECT_ID,
        architecture_version_id=DEFAULT_VERSION_ID,
        generation_id=DEFAULT_GENERATION_ID,
        resource_id=DEFAULT_PROJECT_ID,
        attempt_id=DEFAULT_VERSION_ID,
        lease_token="token-1",
        source_content_digest="sha-src",
        expected_counts=counts,
        expected_key_set_digest="key-digest",
        expected_endpoint_digest="ep-digest",
        expected_payload_digest="payload-digest",
        expected_evidence_summary_digest="evidence-digest",
        expected_unresolved_summary_digest="unresolved-digest",
        expected_conflict_summary_digest="conflict-digest",
    )

    assert len(session.queries_run) == 1
    query, params = session.queries_run[0]
    assert "MERGE (m:ProjectionManifest" in query
    assert params["state_building"] == MANIFEST_STATE_BUILDING
    assert params["fence_digest"] == compute_fence_digest("token-1")
    assert params["resource_id"] == str(DEFAULT_PROJECT_ID)
    assert params["attempt_id"] == str(DEFAULT_VERSION_ID)
    assert params["projection_contract_version"] == "1.0.0"
    assert params["expected_evidence_summary_digest"] == "evidence-digest"


def test_claim_candidate_replaces_fence_on_existing_building_manifest(
    mock_store: tuple[Neo4jProjectionStore, _FakeSession],
) -> None:
    store, session = mock_store
    session.responses["MERGE (m:ProjectionManifest"] = [
        {
            "created": False,
            "state": MANIFEST_STATE_BUILDING,
            "project_id": str(DEFAULT_PROJECT_ID).lower(),
            "architecture_version_id": str(DEFAULT_VERSION_ID).lower(),
            "generation_id": str(DEFAULT_GENERATION_ID).lower(),
            "resource_id": str(DEFAULT_PROJECT_ID).lower(),
            "attempt_id": str(DEFAULT_VERSION_ID).lower(),
            "source_content_digest": "sha-src",
            "source_schema_version": "1.0.0",
            "graph_schema_version": "1.0.0",
            "projector_version": "1.0.0",
            "projection_contract_version": "1.0.0",
            "expected_entities_count": 2,
            "expected_relationships_count": 1,
            "expected_evidence_count": 1,
            "expected_unresolved_count": 0,
            "expected_conflicts_count": 0,
            "expected_key_set_digest": "key-digest",
            "expected_endpoint_digest": "ep-digest",
            "expected_payload_digest": "payload-digest",
            "expected_evidence_summary_digest": "evidence-digest",
            "expected_unresolved_summary_digest": "unresolved-digest",
            "expected_conflict_summary_digest": "conflict-digest",
            "fence_digest": compute_fence_digest("old-token"),
        }
    ]

    counts = ProjectionCounts(
        entities=2, relationships=1, evidence=1, unresolved=0, conflicts=0
    )
    store.claim_candidate(
        project_id=DEFAULT_PROJECT_ID,
        architecture_version_id=DEFAULT_VERSION_ID,
        generation_id=DEFAULT_GENERATION_ID,
        resource_id=DEFAULT_PROJECT_ID,
        attempt_id=DEFAULT_VERSION_ID,
        lease_token="new-token",
        source_content_digest="sha-src",
        expected_counts=counts,
        expected_key_set_digest="key-digest",
        expected_endpoint_digest="ep-digest",
        expected_payload_digest="payload-digest",
        expected_evidence_summary_digest="evidence-digest",
        expected_unresolved_summary_digest="unresolved-digest",
        expected_conflict_summary_digest="conflict-digest",
    )

    assert len(session.queries_run) == 2
    query2, params2 = session.queries_run[1]
    assert "SET m.fence_digest = $fence_digest" in query2
    assert params2["fence_digest"] == compute_fence_digest("new-token")


def test_claim_candidate_fails_if_already_ready(
    mock_store: tuple[Neo4jProjectionStore, _FakeSession],
) -> None:
    store, session = mock_store
    session.responses["MERGE (m:ProjectionManifest"] = [
        {
            "created": False,
            "state": MANIFEST_STATE_READY,
            "project_id": str(DEFAULT_PROJECT_ID).lower(),
            "architecture_version_id": str(DEFAULT_VERSION_ID).lower(),
            "generation_id": str(DEFAULT_GENERATION_ID).lower(),
            "fence_digest": None,
        }
    ]

    counts = ProjectionCounts(
        entities=2, relationships=1, evidence=1, unresolved=0, conflicts=0
    )
    with pytest.raises(ProjectionStoreStateError, match="READY"):
        store.claim_candidate(
            project_id=DEFAULT_PROJECT_ID,
            architecture_version_id=DEFAULT_VERSION_ID,
            generation_id=DEFAULT_GENERATION_ID,
            resource_id=DEFAULT_PROJECT_ID,
            attempt_id=DEFAULT_VERSION_ID,
            lease_token="token-1",
            source_content_digest="sha-src",
            expected_counts=counts,
            expected_key_set_digest="key-digest",
            expected_endpoint_digest="ep-digest",
            expected_payload_digest="payload-digest",
            expected_evidence_summary_digest="evidence-digest",
            expected_unresolved_summary_digest="unresolved-digest",
            expected_conflict_summary_digest="conflict-digest",
        )


def test_write_nodes_checks_manifest_lock_and_fencing(
    mock_store: tuple[Neo4jProjectionStore, _FakeSession],
) -> None:
    store, session = mock_store
    doc = small_document()
    plan = build_projection_plan(
        doc,
        generation_id=DEFAULT_GENERATION_ID,
    )

    fence_digest = compute_fence_digest("valid-token")
    session.responses["lock_epoch = coalesce(m.lock_epoch, 0) + 1"] = [
        {
            "state": MANIFEST_STATE_BUILDING,
            "fence_digest": fence_digest,
            "project_id": str(DEFAULT_PROJECT_ID).lower(),
            "architecture_version_id": str(DEFAULT_VERSION_ID).lower(),
            "generation_id": str(DEFAULT_GENERATION_ID).lower(),
        }
    ]
    session.responses["UNWIND $batch AS item"] = [{"written_count": len(plan.nodes)}]

    written = store.write_nodes(
        project_id=DEFAULT_PROJECT_ID,
        architecture_version_id=DEFAULT_VERSION_ID,
        generation_id=DEFAULT_GENERATION_ID,
        lease_token="valid-token",
        nodes=plan.nodes,
        batch_size=500,
    )

    assert written == len(plan.nodes)
    assert len(session.queries_run) == 2
    # First query was manifest lock
    assert "lock_epoch" in session.queries_run[0][0]
    # Second query was nodes batch
    assert "MERGE (n:ArchitectureEntity" in session.queries_run[1][0]


def test_write_nodes_rejects_stale_fence(
    mock_store: tuple[Neo4jProjectionStore, _FakeSession],
) -> None:
    store, session = mock_store
    doc = small_document()
    plan = build_projection_plan(
        doc,
        generation_id=DEFAULT_GENERATION_ID,
    )

    # Manifest holds newer fence
    newer_fence = compute_fence_digest("superseding-token")
    session.responses["lock_epoch = coalesce(m.lock_epoch, 0) + 1"] = [
        {
            "state": MANIFEST_STATE_BUILDING,
            "fence_digest": newer_fence,
            "project_id": str(DEFAULT_PROJECT_ID).lower(),
            "architecture_version_id": str(DEFAULT_VERSION_ID).lower(),
            "generation_id": str(DEFAULT_GENERATION_ID).lower(),
        }
    ]

    with pytest.raises(StaleFenceError, match="stale worker"):
        store.write_nodes(
            project_id=DEFAULT_PROJECT_ID,
            architecture_version_id=DEFAULT_VERSION_ID,
            generation_id=DEFAULT_GENERATION_ID,
            lease_token="old-token",
            nodes=plan.nodes,
        )


def test_write_nodes_fails_if_manifest_missing(
    mock_store: tuple[Neo4jProjectionStore, _FakeSession],
) -> None:
    store, session = mock_store
    doc = small_document()
    plan = build_projection_plan(
        doc,
        generation_id=DEFAULT_GENERATION_ID,
    )

    session.responses["lock_epoch = coalesce(m.lock_epoch, 0) + 1"] = []

    with pytest.raises(ManifestLockError, match="does not exist"):
        store.write_nodes(
            project_id=DEFAULT_PROJECT_ID,
            architecture_version_id=DEFAULT_VERSION_ID,
            generation_id=DEFAULT_GENERATION_ID,
            lease_token="any-token",
            nodes=plan.nodes,
        )


def test_write_relationships_checks_endpoints(
    mock_store: tuple[Neo4jProjectionStore, _FakeSession],
) -> None:
    store, session = mock_store
    doc = small_document()
    plan = build_projection_plan(
        doc,
        generation_id=DEFAULT_GENERATION_ID,
    )

    fence_digest = compute_fence_digest("valid-token")
    session.responses["lock_epoch = coalesce(m.lock_epoch, 0) + 1"] = [
        {
            "state": MANIFEST_STATE_BUILDING,
            "fence_digest": fence_digest,
            "project_id": str(DEFAULT_PROJECT_ID).lower(),
            "architecture_version_id": str(DEFAULT_VERSION_ID).lower(),
            "generation_id": str(DEFAULT_GENERATION_ID).lower(),
        }
    ]
    # Return 0 written, simulating missing endpoint
    session.responses["MERGE (s)-[r:ARCH_RELATIONSHIP"] = [{"written_count": 0}]

    with pytest.raises(GraphWriteIncompleteError, match="endpoint missing"):
        store.write_relationships(
            project_id=DEFAULT_PROJECT_ID,
            architecture_version_id=DEFAULT_VERSION_ID,
            generation_id=DEFAULT_GENERATION_ID,
            lease_token="valid-token",
            relationships=plan.relationships,
        )


def test_reset_candidate_boundedly_deletes_edges_and_nodes_preserving_manifest(
    mock_store: tuple[Neo4jProjectionStore, _FakeSession],
) -> None:
    store, session = mock_store
    fence_digest = compute_fence_digest("valid-token")
    session.responses["lock_epoch = coalesce(m.lock_epoch, 0) + 1"] = [
        {
            "state": MANIFEST_STATE_BUILDING,
            "fence_digest": fence_digest,
            "project_id": str(DEFAULT_PROJECT_ID).lower(),
            "architecture_version_id": str(DEFAULT_VERSION_ID).lower(),
            "generation_id": str(DEFAULT_GENERATION_ID).lower(),
        }
    ]
    # First relationship delete page returns 5, next returns 0
    # First node delete page returns 3, next returns 0
    rel_responses = iter([{"deleted_count": 5}, {"deleted_count": 0}])
    node_responses = iter([{"deleted_count": 3}, {"deleted_count": 0}])

    def dynamic_handle(query: Any, params: dict[str, Any]) -> _FakeResult:
        query_text = query.text if hasattr(query, "text") else str(query)
        session.queries_run.append((query_text, params))
        if "lock_epoch" in query_text:
            return _FakeResult(
                session.responses["lock_epoch = coalesce(m.lock_epoch, 0) + 1"]
            )
        if "DELETE r" in query_text:
            return _FakeResult([next(rel_responses)])
        if "DELETE n" in query_text:
            return _FakeResult([next(node_responses)])
        return _FakeResult([])

    session.handle_run = dynamic_handle  # type: ignore[assignment]

    deleted = store.reset_candidate(
        project_id=DEFAULT_PROJECT_ID,
        architecture_version_id=DEFAULT_VERSION_ID,
        generation_id=DEFAULT_GENERATION_ID,
        lease_token="valid-token",
        page_size=500,
    )

    assert deleted == 8
    # Manifest was NOT deleted in reset
    assert not any("DELETE m" in q for q, _ in session.queries_run)


def test_finalize_manifest_transitions_to_ready(
    mock_store: tuple[Neo4jProjectionStore, _FakeSession],
) -> None:
    store, session = mock_store
    session.responses["SET m.state = $state_ready"] = [{"state": MANIFEST_STATE_READY}]

    counts = ProjectionCounts(
        entities=2, relationships=1, evidence=1, unresolved=0, conflicts=0
    )
    store.finalize_manifest(
        project_id=DEFAULT_PROJECT_ID,
        architecture_version_id=DEFAULT_VERSION_ID,
        generation_id=DEFAULT_GENERATION_ID,
        lease_token="token-1",
        actual_counts=counts,
        actual_key_set_digest="key-digest",
        actual_endpoint_digest="ep-digest",
        actual_payload_digest="payload-digest",
        actual_evidence_summary_digest="evidence-digest",
        actual_unresolved_summary_digest="unresolved-digest",
        actual_conflict_summary_digest="conflict-digest",
    )

    assert len(session.queries_run) == 1
    query, params = session.queries_run[0]
    assert "m.state = $state_ready" in query
    assert params["state_ready"] == MANIFEST_STATE_READY
    assert params["fence_digest"] == compute_fence_digest("token-1")
    assert params["actual_evidence_summary_digest"] == "evidence-digest"


def test_finalize_manifest_raises_on_stale_fence(
    mock_store: tuple[Neo4jProjectionStore, _FakeSession],
) -> None:
    store, session = mock_store
    session.responses["SET m.state = $state_ready"] = []  # No row updated

    counts = ProjectionCounts(
        entities=2, relationships=1, evidence=1, unresolved=0, conflicts=0
    )
    with pytest.raises(StaleFenceError, match="fence lost"):
        store.finalize_manifest(
            project_id=DEFAULT_PROJECT_ID,
            architecture_version_id=DEFAULT_VERSION_ID,
            generation_id=DEFAULT_GENERATION_ID,
            lease_token="stale-token",
            actual_counts=counts,
            actual_key_set_digest="key-digest",
            actual_endpoint_digest="ep-digest",
            actual_payload_digest="payload-digest",
            actual_evidence_summary_digest="evidence-digest",
            actual_unresolved_summary_digest="unresolved-digest",
            actual_conflict_summary_digest="conflict-digest",
        )


def test_delete_generation_removes_relationships_nodes_and_manifest(
    mock_store: tuple[Neo4jProjectionStore, _FakeSession],
) -> None:
    store, session = mock_store
    rel_responses = iter([{"deleted_count": 2}, {"deleted_count": 0}])
    node_responses = iter([{"deleted_count": 4}, {"deleted_count": 0}])

    def dynamic_handle(query: Any, params: dict[str, Any]) -> _FakeResult:
        query_text = query.text if hasattr(query, "text") else str(query)
        session.queries_run.append((query_text, params))
        if "DELETE r" in query_text:
            return _FakeResult([next(rel_responses)])
        if "DELETE n" in query_text:
            return _FakeResult([next(node_responses)])
        if "DELETE m" in query_text:
            return _FakeResult([{"deleted_count": 1}])
        return _FakeResult([])

    session.handle_run = dynamic_handle  # type: ignore[assignment]

    deleted = store.delete_generation(
        project_id=DEFAULT_PROJECT_ID,
        architecture_version_id=DEFAULT_VERSION_ID,
        generation_id=DEFAULT_GENERATION_ID,
    )

    assert deleted == 7
    # Verified that manifest DELETE was issued
    assert any("DELETE m" in q for q, _ in session.queries_run)
