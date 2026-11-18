"""M3/M6 consumer contract fixture: no storage, ES or M1 lifecycle imports.

These tests exercise public DTO/port interoperability, not production storage.
The real producer/reader boundaries are separately covered by real-service tests.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.platform.knowledge.contracts import (
    SearchCapabilities,
    SearchCursorExpiredError,
    SearchCursorInvalidError,
    SearchGenerationChangedError,
    SearchHit,
    SearchPage,
    SearchReadPort,
    SearchRequest,
    SearchStatus,
    SearchStatusPort,
)
from backend.platform.knowledge.model import (
    KnowledgeDocumentKind,
    KnowledgeProjection,
    KnowledgeRecord,
    SourceReferenceDescriptor,
    compute_projection_digest,
)
from backend.platform.knowledge.projection import KnowledgeProjector
from tests.p5.knowledge.conftest import make_test_scope


def consume_page(port: SearchReadPort, request: SearchRequest, actor):
    """Representative consumer uses only typed public request/response fields."""
    page = port.search(request, actor_id=actor)
    wire = SearchPage.model_validate_json(page.model_dump_json())
    assert wire.scope.project_id == request.project_id
    assert wire.scope.architecture_version_id == request.architecture_version_id
    return wire


def test_consumer_requests_pages_and_handles_typed_failure_without_storage():
    scope, generation, actor = make_test_scope(), uuid4(), uuid4()
    request = SearchRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        q="Service",
        document_kinds=(KnowledgeDocumentKind.ENTITY,),
        limit=1,
    )

    class FixturePort:
        def search(self, request, *, actor_id=None):
            assert actor_id == actor
            if request.cursor == "opaque-expired":
                raise SearchCursorExpiredError()
            return SearchPage(
                scope=scope,
                generation_id=generation,
                index_uuid="fixture-index-uuid",
                items=(
                    SearchHit(
                        knowledge_key="a" * 64,
                        document_kind=KnowledgeDocumentKind.ENTITY,
                        canonical_reference="architecture://service",
                        title="Service",
                        score=2.0,
                        scope=scope,
                    ),
                ),
                total_hits=2,
                has_more=request.cursor is None,
                next_cursor="opaque-continuation" if request.cursor is None else None,
            )

    first = consume_page(FixturePort(), request, actor)
    assert first.generation_id == generation
    resumed = SearchRequest.model_validate_json(
        request.model_copy(update={"cursor": first.next_cursor}).model_dump_json()
    )
    last = consume_page(FixturePort(), resumed, actor)
    assert not last.has_more and last.generation_id == generation
    assert last.index_uuid == first.index_uuid == "fixture-index-uuid"
    with pytest.raises(SearchCursorExpiredError):
        consume_page(
            FixturePort(),
            request.model_copy(update={"cursor": "opaque-expired"}),
            actor,
        )


@pytest.mark.parametrize(
    "freshness", ["CURRENT", "STALE", "BUILDING", "FAILED", "UNAVAILABLE", "UNKNOWN"]
)
def test_consumer_status_wire_vocabulary(freshness):
    scope = make_test_scope()

    class FixtureStatus:
        def get_status(self, project_id, architecture_version_id):
            assert (project_id, architecture_version_id) == (
                scope.project_id,
                scope.architecture_version_id,
            )
            return SearchStatus(
                scope=scope,
                resource_state="PENDING",
                freshness=freshness,
                capabilities=SearchCapabilities(),
            )

    port: SearchStatusPort = FixtureStatus()
    status = port.get_status(scope.project_id, scope.architecture_version_id)
    wire = SearchStatus.model_validate_json(status.model_dump_json())
    assert wire.freshness == freshness
    assert wire.capabilities.semantic.value == "unavailable"
    assert wire.capabilities.semantic_reason == "provider_not_approved"


@pytest.mark.parametrize(
    "error,code",
    [
        (SearchCursorExpiredError, "search_cursor_expired"),
        (SearchCursorInvalidError, "search_cursor_invalid"),
        (SearchGenerationChangedError, "search_generation_changed"),
    ],
)
def test_consumer_distinguishes_restart_conditions(error, code):
    assert error().code == code


def test_all_record_kinds_roundtrip_preserve_provenance(sample_doc_and_scope):
    document, scope = sample_doc_and_scope
    result = KnowledgeProjector().project(document, scope)
    assert {r.document_kind for r in result.records} == set(KnowledgeDocumentKind)
    decoded = KnowledgeProjection.model_validate_json(result.model_dump_json())
    assert decoded == result
    evidence = next(
        r for r in decoded.records if r.document_kind == KnowledgeDocumentKind.EVIDENCE
    )
    assert (
        evidence.source_reference.source_record_type
        == document.evidence[0].source_record_type
    )
    assert (
        evidence.source_reference.source_fact_key
        == document.evidence[0].source_fact_key
    )
    assert evidence.source_reference.source_range == dict(
        document.evidence[0].source_range
    )
    assert not hasattr(evidence, "source_body")


def test_inventory_evidence_does_not_invent_fact_or_producer():
    source = SourceReferenceDescriptor(
        source_record_type="inventory", path="src/main.py"
    )
    decoded = SourceReferenceDescriptor.model_validate_json(source.model_dump_json())
    assert decoded.source_fact_key is None
    assert decoded.producer_id is None and decoded.producer_version is None
    assert decoded.source_record_type == "inventory"


@pytest.mark.parametrize("change", ["scope", "count", "duplicate", "source_digest"])
def test_projection_rejects_consistent_hash_with_invalid_structure(
    sample_doc_and_scope, change
):
    document, scope = sample_doc_and_scope
    projection = KnowledgeProjector().project(document, scope)
    values = dict(projection)
    if change == "scope":
        values["scope"] = make_test_scope()
        values["source_content_digest"] = values["scope"].canonical_digest
    elif change == "count":
        values["records"] = values["records"][:-1]
    elif change == "duplicate":
        values["records"] = (
            (values["records"][0],) + values["records"][1:-1] + (values["records"][0],)
        )
    else:
        values["source_content_digest"] = "e" * 64
    values["projection_digest"] = compute_projection_digest(
        c1_version="1.0.0",
        scope=values["scope"],
        source_content_digest=values["source_content_digest"],
        records=values["records"],
        counts=values["counts"],
    )
    with pytest.raises(ValidationError):
        KnowledgeProjection.model_validate(values)


def test_record_rejects_rehashed_foreign_key(sample_scope):
    record = KnowledgeRecord.create(
        scope=sample_scope,
        document_kind=KnowledgeDocumentKind.ENTITY,
        canonical_reference="architecture://entity",
        title="Entity",
    )
    forged = record.model_copy(update={"knowledge_key": "f" * 64})
    forged = forged.model_copy(
        update={"record_digest": forged.compute_semantic_digest()}
    )
    with pytest.raises(ValidationError, match="knowledge key"):
        KnowledgeRecord.model_validate(forged)


@pytest.mark.parametrize(
    "change", ["foreign_scope", "duplicate", "cursor", "total", "score"]
)
def test_page_rejects_invalid_consumer_payload(change):
    scope = make_test_scope()
    hit = SearchHit(
        knowledge_key="a" * 64,
        document_kind=KnowledgeDocumentKind.ENTITY,
        canonical_reference="architecture://entity",
        title="Entity",
        score=1.0,
        scope=scope,
    )
    values = dict(
        scope=scope,
        generation_id=uuid4(),
        index_uuid="fixture-index-uuid",
        items=(hit,),
        total_hits=1,
        has_more=False,
    )
    if change == "foreign_scope":
        values["scope"] = make_test_scope()
    elif change == "duplicate":
        values.update(items=(hit, hit), total_hits=2)
    elif change == "cursor":
        values["has_more"] = True
    elif change == "total":
        values["total_hits"] = 0
    else:
        values["items"] = (hit.model_copy(update={"score": float("inf")}),)
    with pytest.raises(ValidationError):
        SearchPage.model_validate(values)


def test_status_rejects_unapproved_resource_vocabulary():
    with pytest.raises(ValidationError):
        SearchStatus(
            scope=make_test_scope(), resource_state="READY", freshness="CURRENT"
        )


@pytest.mark.parametrize("index", [None, ""])
def test_page_requires_exact_index_identity(index):
    values = dict(
        scope=make_test_scope(),
        generation_id=uuid4(),
        items=(),
        total_hits=0,
        has_more=False,
    )
    if index is not None:
        values["index_uuid"] = index
    with pytest.raises(ValidationError):
        SearchPage.model_validate(values)
