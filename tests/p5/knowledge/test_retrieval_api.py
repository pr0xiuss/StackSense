"""Unit and API integration tests for P5-C3 Controlled Retrieval FastAPI endpoints.

Adheres to §7A.8, §7A.10, §7A.11, §7A.12, and §7A.13 of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.error_handlers import register_exception_handlers
from backend.api.v1.retrieval import router as retrieval_router
from backend.platform.analysis.application.dependencies import (
    DelegatedRequestContext,
    get_delegated_context,
)
from backend.platform.knowledge.retrieval_configuration import RetrievalPolicy
from backend.platform.knowledge.retrieval_contracts import (
    CanonicalFactView,
    CanonicalReadPort,
    EvidenceItemView,
    RelationshipView,
    RetrievalCapacityExceededError,
    RetrievalCursorExpiredError,
    RetrievalCursorInvalidError,
    RetrievalDeadlineExceededError,
    RetrievalGenerationChangedError,
    RetrievalIntegrityFailedError,
    RetrievalInvalidRequestError,
    RetrievalNotFoundError,
    RetrievalScope,
    RetrievalUnavailableError,
)
from backend.platform.knowledge.retrieval_dependencies import (
    get_canonical_read_port,
    get_graph_read_port,
    get_retrieval_cursor_secret,
    get_retrieval_policy,
    get_search_read_port,
)


class MockCanonicalPort(CanonicalReadPort):
    def __init__(self, scope: RetrievalScope) -> None:
        self.scope = scope
        self.entities: list[CanonicalFactView] = []
        self.relationships: list[RelationshipView] = []
        self.evidence: list[EvidenceItemView] = []
        self.error: Exception | None = None

    def get_version(self, version_id: UUID, project_id: UUID) -> RetrievalScope:
        if self.error:
            raise self.error
        if (
            version_id != self.scope.architecture_version_id
            or project_id != self.scope.project_id
        ):
            raise RetrievalNotFoundError("Version not found")
        return self.scope

    def get_entity(
        self, version_id: UUID, entity_id: UUID, project_id: UUID
    ) -> CanonicalFactView | None:
        if self.error:
            raise self.error
        for e in self.entities:
            if e.record_id == entity_id:
                return e
        return None

    def list_entities(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        **kwargs: Any,
    ) -> tuple[tuple[CanonicalFactView, ...], int]:
        if self.error:
            raise self.error
        paged = self.entities[offset : offset + limit]
        return tuple(paged), len(self.entities)

    def list_relationships(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        **kwargs: Any,
    ) -> tuple[tuple[RelationshipView, ...], int]:
        if self.error:
            raise self.error
        paged = self.relationships[offset : offset + limit]
        return tuple(paged), len(self.relationships)

    def list_evidence(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        **kwargs: Any,
    ) -> tuple[tuple[EvidenceItemView, ...], int]:
        if self.error:
            raise self.error
        entity_id = kwargs.get("entity_id")
        items = self.evidence
        if entity_id:
            items = [ev for ev in items if str(entity_id) in ev.subject_references]
        paged = items[offset : offset + limit]
        return tuple(paged), len(items)

    def list_unresolved(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> tuple[tuple[Any, ...], int]:
        if self.error:
            raise self.error
        return (), 0

    def list_conflicts(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> tuple[tuple[Any, ...], int]:
        if self.error:
            raise self.error
        return (), 0


@pytest.fixture
def retrieval_fixture():
    project_id = uuid4()
    version_id = uuid4()
    scope = RetrievalScope(
        project_id=project_id,
        repository_id=uuid4(),
        analysis_id=uuid4(),
        snapshot_id=uuid4(),
        architecture_version_id=version_id,
        sequence_number=1,
        canonical_digest="d" * 64,
        architecture_schema_version="1.0.0",
        ir_schema_version="1.0.0",
        published_at=datetime.now(UTC),
    )

    port = MockCanonicalPort(scope)

    entity1 = CanonicalFactView(
        record_id=uuid4(),
        logical_id="architecture://entity/service/web",
        kind="service",
        name="WebService",
        namespace=("app", "web"),
        status="confirmed",
        metadata={"framework": "fastapi"},
        evidence_count=1,
        evidence_references=("ev-1",),
    )
    entity2 = CanonicalFactView(
        record_id=uuid4(),
        logical_id="architecture://entity/service/db",
        kind="database",
        name="DatabaseService",
        namespace=("app", "db"),
        status="confirmed",
        metadata={"database_engine": "postgresql"},
        evidence_count=1,
        evidence_references=("ev-2",),
    )
    port.entities.extend([entity1, entity2])

    rel = RelationshipView(
        record_id=uuid4(),
        logical_id="architecture://rel/calls/web-to-db",
        kind="calls",
        source_logical_id=entity1.logical_id,
        target_logical_id=entity2.logical_id,
        status="confirmed",
        evidence_references=("ev-1",),
    )
    port.relationships.append(rel)

    ev1 = EvidenceItemView(
        record_id=uuid4(),
        logical_id="ev-1",
        source_record_type="entity",
        path="src/web/main.py",
        source_fact_key="fact-1",
        producer_id="analyzer",
        producer_version="1.0.0",
        strength="direct_source",
        polarity="supporting",
        range_data={"line": 1},
    )
    ev2 = EvidenceItemView(
        record_id=uuid4(),
        logical_id="ev-2",
        source_record_type="entity",
        path="src/db/models.py",
        source_fact_key="fact-2",
        producer_id="analyzer",
        producer_version="1.0.0",
        strength="direct_source",
        polarity="supporting",
        range_data={"line": 10},
    )
    port.evidence.extend([ev1, ev2])

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(retrieval_router, prefix="/api/v1")

    actor_id = uuid4()
    context = DelegatedRequestContext(
        actor_id=actor_id,
        role="OWNER",
        is_service=True,
        project_id=project_id,
        correlation_id="corr-test-1",
    )

    app.dependency_overrides[get_delegated_context] = lambda: context
    app.dependency_overrides[get_canonical_read_port] = lambda: port
    app.dependency_overrides[get_search_read_port] = lambda: None
    app.dependency_overrides[get_graph_read_port] = lambda: None
    app.dependency_overrides[get_retrieval_policy] = lambda: RetrievalPolicy()
    app.dependency_overrides[get_retrieval_cursor_secret] = lambda: (
        "secret-retrieval-cursor-key-32bytes"
    )

    client = TestClient(app)
    return client, app, port, scope, entity1, entity2, rel


def test_query_endpoint_success(retrieval_fixture):
    client, _, _, scope, entity1, _, _ = retrieval_fixture
    url = (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/query"
        f"?project_id={scope.project_id}"
    )
    payload = {
        "project_id": str(scope.project_id),
        "architecture_version_id": str(scope.architecture_version_id),
        "operation": "lookup",
        "subject": {"selector_type": "logical_id", "logical_id": entity1.logical_id},
        "limit": 10,
    }

    resp = client.post(url, json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["c3_version"] == "1.0.0"
    assert data["outcome"] == "complete"
    assert data["resolved_subject"]["selected_logical_id"] == entity1.logical_id
    assert len(data["facts"]) == 1
    assert data["facts"][0]["name"] == "WebService"


def test_query_endpoint_scope_mismatch(retrieval_fixture):
    client, _, _, scope, entity1, _, _ = retrieval_fixture
    url = (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/query"
        f"?project_id={scope.project_id}"
    )
    other_project = uuid4()
    payload = {
        "project_id": str(other_project),
        "architecture_version_id": str(scope.architecture_version_id),
        "operation": "lookup",
        "subject": {"selector_type": "logical_id", "logical_id": entity1.logical_id},
    }

    resp = client.post(url, json=payload)
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"]["code"] == "retrieval_invalid_request"
    assert "scope" in data["error"]["message"].lower()


def test_query_endpoint_version_not_found(retrieval_fixture):
    client, _, port, scope, entity1, _, _ = retrieval_fixture
    unknown_version = uuid4()
    url = (
        f"/api/v1/architecture-versions/{unknown_version}/knowledge/query"
        f"?project_id={scope.project_id}"
    )
    payload = {
        "project_id": str(scope.project_id),
        "architecture_version_id": str(unknown_version),
        "operation": "lookup",
        "subject": {"selector_type": "logical_id", "logical_id": entity1.logical_id},
    }

    resp = client.post(url, json=payload)
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "retrieval_not_found"


def test_query_endpoint_invalid_payload(retrieval_fixture):
    client, _, _, scope, _, _, _ = retrieval_fixture
    url = (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/query"
        f"?project_id={scope.project_id}"
    )
    # Empty subject object
    payload = {
        "project_id": str(scope.project_id),
        "architecture_version_id": str(scope.architecture_version_id),
        "operation": "lookup",
        "subject": {},
    }

    resp = client.post(url, json=payload)
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"]["code"] == "retrieval_invalid_request"


def test_context_endpoint_success(retrieval_fixture):
    client, _, _, scope, entity1, _, _ = retrieval_fixture
    url = (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/context"
        f"?project_id={scope.project_id}"
    )
    payload = {
        "project_id": str(scope.project_id),
        "architecture_version_id": str(scope.architecture_version_id),
        "subjects": [{"selector_type": "logical_id", "logical_id": entity1.logical_id}],
        "operations": ["lookup", "relationships"],
        "include_evidence": True,
        "include_conflicts": True,
        "include_unresolved": True,
    }

    resp = client.post(url, json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["c3_version"] == "1.0.0"
    assert len(data["semantic_digest"]) == 64
    assert len(data["facts"]) >= 1
    assert data["facts"][0]["logical_id"] == entity1.logical_id
    assert len(data["relationships"]) >= 1
    assert len(data["rationales"]) >= 2
    assert data["outcome"] in ("complete", "partial")


def test_context_endpoint_scope_mismatch(retrieval_fixture):
    client, _, _, scope, entity1, _, _ = retrieval_fixture
    url = (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/context"
        f"?project_id={scope.project_id}"
    )
    payload = {
        "project_id": str(uuid4()),
        "architecture_version_id": str(scope.architecture_version_id),
        "subjects": [{"selector_type": "logical_id", "logical_id": entity1.logical_id}],
        "operations": ["lookup"],
    }

    resp = client.post(url, json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "retrieval_invalid_request"


def test_context_endpoint_missing_subjects(retrieval_fixture):
    client, _, _, scope, _, _, _ = retrieval_fixture
    url = (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/context"
        f"?project_id={scope.project_id}"
    )
    payload = {
        "project_id": str(scope.project_id),
        "architecture_version_id": str(scope.architecture_version_id),
        "subjects": [],
        "operations": ["lookup"],
    }

    resp = client.post(url, json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "retrieval_invalid_request"


def test_evidence_endpoint_success(retrieval_fixture):
    client, _, _, scope, _, _, _ = retrieval_fixture
    url = (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/evidence"
        f"?project_id={scope.project_id}&limit=10&offset=0"
    )

    resp = client.get(url)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["c3_version"] == "1.0.0"
    assert data["total_items"] == 2
    assert len(data["items"]) == 2
    assert data["has_more"] is False
    assert data["coverage"]["count_known"] is True


def test_evidence_endpoint_pagination(retrieval_fixture):
    client, _, _, scope, _, _, _ = retrieval_fixture
    url_p1 = (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/evidence"
        f"?project_id={scope.project_id}&limit=1&offset=0"
    )
    resp1 = client.get(url_p1)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1["items"]) == 1
    assert data1["has_more"] is True
    assert data1["items"][0]["logical_id"] == "ev-1"

    url_p2 = (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/evidence"
        f"?project_id={scope.project_id}&limit=1&offset=1"
    )
    resp2 = client.get(url_p2)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2["items"]) == 1
    assert data2["has_more"] is False
    assert data2["items"][0]["logical_id"] == "ev-2"


def test_evidence_endpoint_not_found(retrieval_fixture):
    client, _, _, scope, _, _, _ = retrieval_fixture
    unknown_version = uuid4()
    url = (
        f"/api/v1/architecture-versions/{unknown_version}/knowledge/evidence"
        f"?project_id={scope.project_id}"
    )
    resp = client.get(url)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "retrieval_not_found"


@pytest.mark.parametrize("role", ["OWNER", "ADMIN", "DEVELOPER", "VIEWER"])
def test_delegated_rbac_matrix_allowed_for_all_roles(retrieval_fixture, role):
    client, app, _, scope, entity1, _, _ = retrieval_fixture
    app.dependency_overrides[get_delegated_context] = lambda: DelegatedRequestContext(
        actor_id=uuid4(),
        role=role,
        is_service=True,
        project_id=scope.project_id,
        correlation_id=f"corr-{role}",
    )

    # 1. Query
    query_url = (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/query"
        f"?project_id={scope.project_id}"
    )
    q_resp = client.post(
        query_url,
        json={
            "project_id": str(scope.project_id),
            "architecture_version_id": str(scope.architecture_version_id),
            "operation": "lookup",
            "subject": {
                "selector_type": "logical_id",
                "logical_id": entity1.logical_id,
            },
        },
    )
    assert q_resp.status_code == 200

    # 2. Evidence
    ev_url = (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/evidence"
        f"?project_id={scope.project_id}"
    )
    ev_resp = client.get(ev_url)
    assert ev_resp.status_code == 200


def test_delegated_project_mismatch_forbidden(retrieval_fixture):
    client, app, _, scope, entity1, _, _ = retrieval_fixture
    foreign_project = uuid4()
    app.dependency_overrides[get_delegated_context] = lambda: DelegatedRequestContext(
        actor_id=uuid4(),
        role="OWNER",
        is_service=True,
        project_id=foreign_project,
    )

    query_url = (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/query"
        f"?project_id={scope.project_id}"
    )
    resp = client.post(
        query_url,
        json={
            "project_id": str(scope.project_id),
            "architecture_version_id": str(scope.architecture_version_id),
            "operation": "lookup",
            "subject": {
                "selector_type": "logical_id",
                "logical_id": entity1.logical_id,
            },
        },
    )
    assert resp.status_code == 403


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (RetrievalNotFoundError("missing"), 404, "retrieval_not_found"),
        (
            RetrievalGenerationChangedError("changed"),
            409,
            "retrieval_generation_changed",
        ),
        (RetrievalCursorExpiredError("expired"), 410, "retrieval_cursor_expired"),
        (RetrievalCursorInvalidError("invalid"), 422, "retrieval_cursor_invalid"),
        (
            RetrievalCapacityExceededError("too large"),
            422,
            "retrieval_capacity_exceeded",
        ),
        (
            RetrievalInvalidRequestError("bad request"),
            422,
            "retrieval_invalid_request",
        ),
        (RetrievalUnavailableError("service down"), 503, "retrieval_unavailable"),
        (RetrievalDeadlineExceededError("timeout"), 504, "retrieval_deadline_exceeded"),
        (
            RetrievalIntegrityFailedError("checksum fail"),
            500,
            "retrieval_integrity_failed",
        ),
    ],
)
def test_retrieval_error_translations(
    retrieval_fixture, error, expected_status, expected_code
):
    client, _, port, scope, entity1, _, _ = retrieval_fixture
    port.error = error

    url = (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/query"
        f"?project_id={scope.project_id}"
    )
    resp = client.post(
        url,
        json={
            "project_id": str(scope.project_id),
            "architecture_version_id": str(scope.architecture_version_id),
            "operation": "lookup",
            "subject": {
                "selector_type": "logical_id",
                "logical_id": entity1.logical_id,
            },
        },
    )
    assert resp.status_code == expected_status
    body = resp.json()
    assert body["error"]["code"] == expected_code
    assert isinstance(body["error"]["details"], dict)


def test_actor_validation_requires_actor_id(retrieval_fixture):
    client, app, _, scope, entity1, _, _ = retrieval_fixture
    # Provide context with None actor_id
    app.dependency_overrides[get_delegated_context] = lambda: DelegatedRequestContext(
        actor_id=None,
        role="OWNER",
        is_service=True,
        project_id=scope.project_id,
    )

    url = (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/query"
        f"?project_id={scope.project_id}"
    )
    resp = client.post(
        url,
        json={
            "project_id": str(scope.project_id),
            "architecture_version_id": str(scope.architecture_version_id),
            "operation": "lookup",
            "subject": {
                "selector_type": "logical_id",
                "logical_id": entity1.logical_id,
            },
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "retrieval_invalid_request"
    assert "actor" in resp.json()["error"]["message"].lower()


def test_no_secret_leak_in_error_responses(retrieval_fixture):
    client, _, port, scope, entity1, _, _ = retrieval_fixture
    # An internal error containing sensitive string
    port.error = RuntimeError("super-secret-password-12345 in db connection")

    url = (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/query"
        f"?project_id={scope.project_id}"
    )
    resp = client.post(
        url,
        json={
            "project_id": str(scope.project_id),
            "architecture_version_id": str(scope.architecture_version_id),
            "operation": "lookup",
            "subject": {
                "selector_type": "logical_id",
                "logical_id": entity1.logical_id,
            },
        },
    )
    assert resp.status_code == 500
    raw_text = resp.text
    assert "super-secret-password-12345" not in raw_text
    assert resp.json()["error"]["code"] == "retrieval_integrity_failed"
