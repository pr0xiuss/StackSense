"""Unit tests for P5-C3 retrieval contracts, schemas, and serialization.

Adheres to §7A.4, §7A.8, and §7A.11 of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from backend.platform.knowledge.retrieval_contracts import (
    C3_CONTRACT_VERSION,
    CanonicalFactView,
    Coverage,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    RetrievalCapacityExceededError,
    RetrievalCursorExpiredError,
    RetrievalDeadlineExceededError,
    RetrievalGenerationChangedError,
    RetrievalIntegrityFailedError,
    RetrievalInvalidRequestError,
    RetrievalNotFoundError,
    RetrievalOperation,
    RetrievalOutcome,
    RetrievalScope,
    RetrievalUnavailableError,
    SubjectSelector,
)


def _make_sample_scope(*, project_id: UUID | None = None) -> RetrievalScope:
    return RetrievalScope(
        project_id=project_id or uuid4(),
        repository_id=uuid4(),
        analysis_id=uuid4(),
        snapshot_id=uuid4(),
        architecture_version_id=uuid4(),
        sequence_number=1,
        canonical_digest="a" * 64,
        architecture_schema_version="1.0.0",
        ir_schema_version="1.0.0",
        published_at=datetime.now(UTC),
    )


def test_retrieval_scope_strict_validation():
    scope = _make_sample_scope()
    assert len(scope.canonical_digest) == 64
    assert scope.sequence_number >= 1

    # Disallow extra fields
    with pytest.raises(ValidationError):
        RetrievalScope(
            **scope.model_dump(),
            extra_field="disallowed",
        )

    # Disallow invalid digest length
    with pytest.raises(ValidationError):
        RetrievalScope(
            **{**scope.model_dump(), "canonical_digest": "short"},
        )


def test_subject_selector_union_shapes():
    # 1. record_id shape
    rec_id = uuid4()
    sel_id = SubjectSelector.from_record_id("entity", rec_id)
    assert sel_id.selector_type == "record_id"
    assert sel_id.record_id == rec_id
    assert sel_id.logical_id is None
    assert sel_id.name is None

    # 2. logical_id shape
    sel_lid = SubjectSelector.from_logical_id("entity", "entity://core/service")
    assert sel_lid.selector_type == "logical_id"
    assert sel_lid.logical_id == "entity://core/service"
    assert sel_lid.record_id is None

    # 3. entity_name shape
    sel_name = SubjectSelector.from_entity_name(
        "AuthService", namespace=("core", "auth")
    )
    assert sel_name.selector_type == "entity_name"
    assert sel_name.name == "AuthService"
    assert sel_name.namespace == ("core", "auth")
    assert sel_name.record_kind == "entity"

    # Conflicting fields rejected
    with pytest.raises(ValidationError):
        SubjectSelector(
            selector_type="record_id",
            record_kind="entity",
            record_id=rec_id,
            logical_id="conflict",
        )

    with pytest.raises(ValidationError):
        SubjectSelector(
            selector_type="entity_name",
            record_kind="relationship",  # Only entity allowed for entity_name
            name="RelName",
        )


def test_immutable_views_extra_fields_forbidden():
    fact = CanonicalFactView(
        record_id=uuid4(),
        logical_id="entity://svc",
        kind="service",
        name="Service",
        status="CONFIRMED",
    )
    # Mutation blocked by frozen=True
    with pytest.raises(ValidationError):
        fact.name = "Mutated"  # type: ignore[misc]

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        CanonicalFactView(
            record_id=uuid4(),
            logical_id="entity://svc",
            kind="service",
            name="Service",
            status="CONFIRMED",
            extra="disallowed",
        )


def test_knowledge_query_request_validation():
    prj = uuid4()
    ver = uuid4()

    # Paths requires both subject and target
    with pytest.raises(ValidationError):
        KnowledgeQueryRequest(
            project_id=prj,
            architecture_version_id=ver,
            operation=RetrievalOperation.PATHS,
            subject=SubjectSelector.from_logical_id("entity", "entity://a"),
            target=None,
        )

    # Dependencies requires subject
    with pytest.raises(ValidationError):
        KnowledgeQueryRequest(
            project_id=prj,
            architecture_version_id=ver,
            operation=RetrievalOperation.DEPENDENCIES,
            subject=None,
        )

    # Valid request
    req = KnowledgeQueryRequest(
        project_id=prj,
        architecture_version_id=ver,
        operation=RetrievalOperation.LOOKUP,
        q="Service",
        limit=50,
    )
    assert req.operation == RetrievalOperation.LOOKUP
    assert req.limit == 50


def test_knowledge_query_response_wire_roundtrip():
    scope = _make_sample_scope()
    resp = KnowledgeQueryResponse(
        scope=scope,
        operation=RetrievalOperation.LOOKUP,
        outcome=RetrievalOutcome.COMPLETE,
        facts=(
            CanonicalFactView(
                record_id=uuid4(),
                logical_id="entity://test",
                kind="component",
                name="TestComponent",
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
    wire_json = resp.model_dump_json()
    rehydrated = KnowledgeQueryResponse.model_validate_json(wire_json)
    assert rehydrated.c3_version == C3_CONTRACT_VERSION
    assert rehydrated.scope.project_id == scope.project_id
    assert len(rehydrated.facts) == 1
    assert rehydrated.facts[0].logical_id == "entity://test"
    assert rehydrated.outcome == RetrievalOutcome.COMPLETE


def test_error_taxonomy_codes():
    err1 = RetrievalInvalidRequestError("Bad input", safe_details={"field": "q"})
    assert err1.code == "retrieval_invalid_request"
    assert err1.safe_details["field"] == "q"

    err2 = RetrievalCursorExpiredError()
    assert err2.code == "retrieval_cursor_expired"

    err3 = RetrievalGenerationChangedError()
    assert err3.code == "retrieval_generation_changed"

    err4 = RetrievalNotFoundError()
    assert err4.code == "retrieval_not_found"

    err5 = RetrievalCapacityExceededError()
    assert err5.code == "retrieval_capacity_exceeded"

    err6 = RetrievalDeadlineExceededError()
    assert err6.code == "retrieval_deadline_exceeded"

    err7 = RetrievalUnavailableError()
    assert err7.code == "retrieval_unavailable"

    err8 = RetrievalIntegrityFailedError()
    assert err8.code == "retrieval_integrity_failed"
