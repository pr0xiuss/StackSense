"""M6 and future P6 consumer contract fixture for P5-C3 retrieval interfaces.

Adheres to §7A.3, §7A.11, and §7A.12 of PROJECT_CONTEXT.md.
Proves that downstream consumers interact only with public C3 typed DTOs,
protocols, and safe error codes without importing private persistence,
Elasticsearch, or Neo4j internals.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from backend.platform.knowledge.retrieval_contracts import (
    CanonicalFactView,
    Coverage,
    KnowledgeQueryPort,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    RetrievalCursorExpiredError,
    RetrievalError,
    RetrievalGenerationChangedError,
    RetrievalNotFoundError,
    RetrievalOperation,
    RetrievalOutcome,
    RetrievalPrincipal,
    RetrievalScope,
    RetrievalUnavailableError,
    SubjectSelector,
)


class MockM6Consumer:
    """Representative downstream M6 presentation layer consumer."""

    def __init__(self, query_port: KnowledgeQueryPort) -> None:
        self.query_port = query_port

    def fetch_entity_overview(
        self,
        project_id: UUID,
        version_id: UUID,
        entity_id: UUID,
        *,
        actor_id: UUID,
    ) -> dict:
        principal = RetrievalPrincipal(
            actor_id=actor_id,
            project_id=project_id,
            role="viewer",
        )
        request = KnowledgeQueryRequest(
            project_id=project_id,
            architecture_version_id=version_id,
            operation=RetrievalOperation.LOOKUP,
            subject=SubjectSelector.from_record_id("entity", entity_id),
        )
        response = self.query_port.query(request, principal=principal)
        # Verify JSON serializability for Express HTTP gateway
        wire_json = response.model_dump_json()
        deserialized = KnowledgeQueryResponse.model_validate_json(wire_json)

        return {
            "status": deserialized.outcome.value,
            "facts": [f.model_dump() for f in deserialized.facts],
            "has_more": bool(deserialized.next_cursor),
        }


def test_m6_consumer_interaction_and_serialization():
    prj = uuid4()
    ver = uuid4()
    ent_id = uuid4()
    scope = RetrievalScope(
        project_id=prj,
        repository_id=uuid4(),
        analysis_id=uuid4(),
        snapshot_id=uuid4(),
        architecture_version_id=ver,
        sequence_number=1,
        canonical_digest="d" * 64,
        architecture_schema_version="1.0.0",
        ir_schema_version="1.0.0",
        published_at=datetime.now(UTC),
    )

    class FakeQueryPort(KnowledgeQueryPort):
        def query(self, request, *, principal):
            return KnowledgeQueryResponse(
                scope=scope,
                operation=request.operation,
                outcome=RetrievalOutcome.COMPLETE,
                facts=(
                    CanonicalFactView(
                        record_id=ent_id,
                        logical_id="entity://api",
                        kind="service",
                        name="ApiService",
                        status="CONFIRMED",
                    ),
                ),
                coverage=Coverage(
                    considered_count=1,
                    selected_count=1,
                    scanned_count=1,
                    exhausted=True,
                ),
            )

    consumer = MockM6Consumer(FakeQueryPort())
    result = consumer.fetch_entity_overview(prj, ver, ent_id, actor_id=uuid4())

    assert result["status"] == "complete"
    assert len(result["facts"]) == 1
    assert result["facts"][0]["logical_id"] == "entity://api"
    assert result["has_more"] is False


def test_future_p6_consumer_rejects_unsupported_c3_version():
    scope = RetrievalScope(
        project_id=uuid4(),
        repository_id=uuid4(),
        analysis_id=uuid4(),
        snapshot_id=uuid4(),
        architecture_version_id=uuid4(),
        sequence_number=1,
        canonical_digest="e" * 64,
        architecture_schema_version="1.0.0",
        ir_schema_version="1.0.0",
        published_at=datetime.now(UTC),
    )

    # Unsupported contract version rejected at consumer validation
    with pytest.raises(ValidationError):
        KnowledgeQueryResponse(
            c3_version="2.0.0",  # type: ignore[arg-type]
            scope=scope,
            operation=RetrievalOperation.LOOKUP,
            coverage=Coverage(),
        )


def test_consumer_handles_typed_retrieval_errors_without_storage_imports():
    class FailingQueryPort(KnowledgeQueryPort):
        def __init__(self, exc: RetrievalError) -> None:
            self.exc = exc

        def query(self, request, *, principal):
            raise self.exc

    principal = RetrievalPrincipal(actor_id=uuid4(), project_id=uuid4(), role="viewer")
    req = KnowledgeQueryRequest(
        project_id=principal.project_id,
        architecture_version_id=uuid4(),
        operation=RetrievalOperation.LOOKUP,
    )

    # 404
    p404 = FailingQueryPort(RetrievalNotFoundError("Entity not found"))
    with pytest.raises(RetrievalNotFoundError) as exc_info:
        p404.query(req, principal=principal)
    assert exc_info.value.code == "retrieval_not_found"

    # 409
    p409 = FailingQueryPort(RetrievalGenerationChangedError())
    with pytest.raises(RetrievalGenerationChangedError) as exc_info:
        p409.query(req, principal=principal)
    assert exc_info.value.code == "retrieval_generation_changed"

    # 410
    p410 = FailingQueryPort(RetrievalCursorExpiredError())
    with pytest.raises(RetrievalCursorExpiredError) as exc_info:
        p410.query(req, principal=principal)
    assert exc_info.value.code == "retrieval_cursor_expired"

    # 503
    p503 = FailingQueryPort(RetrievalUnavailableError("Backend offline"))
    with pytest.raises(RetrievalUnavailableError) as exc_info:
        p503.query(req, principal=principal)
    assert exc_info.value.code == "retrieval_unavailable"
