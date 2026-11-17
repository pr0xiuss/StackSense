"""Tests for P5-C1 search request, hit, page, status, and error contracts."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.platform.delivery.contracts import (
    ArtifactReference,
    HandlerProfile,
    OutputDigests,
    WorkKind,
    WorkSlot,
)
from backend.platform.knowledge.contracts import (
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_SEARCH_TIMEOUT_SECONDS,
    MAX_SEARCH_CURSOR_LENGTH,
    MAX_SEARCH_LIMIT,
    MAX_SEARCH_QUERY_LENGTH,
    MAX_SEARCH_TIMEOUT_SECONDS,
    CapabilityState,
    ResolvedSearchGeneration,
    SearchBackendUnavailableError,
    SearchCapabilities,
    SearchCapabilityUnavailableError,
    SearchCapacityExceededError,
    SearchCursorExpiredError,
    SearchCursorInvalidError,
    SearchDeadlineExceededError,
    SearchError,
    SearchGenerationChangedError,
    SearchHit,
    SearchIntegrityError,
    SearchNotReadyError,
    SearchPage,
    SearchRequest,
    SearchStatus,
)
from backend.platform.knowledge.model import (
    C1_CONTRACT_VERSION,
    KnowledgeDocumentKind,
)
from tests.p5.knowledge.conftest import make_test_scope


def test_error_taxonomy_hierarchy():
    classes = [
        SearchNotReadyError,
        SearchGenerationChangedError,
        SearchCursorExpiredError,
        SearchCursorInvalidError,
        SearchIntegrityError,
        SearchCapacityExceededError,
        SearchBackendUnavailableError,
        SearchDeadlineExceededError,
        SearchCapabilityUnavailableError,
    ]
    for cls in classes:
        err = cls("test message", safe_details={"key": "val"})
        assert isinstance(err, SearchError)
        assert isinstance(err, Exception)
        assert err.code is not None
        assert err.safe_details == {"key": "val"}
        assert str(err) == "test message"


def test_search_capabilities_defaults():
    caps = SearchCapabilities()
    assert caps.lexical == CapabilityState.AVAILABLE
    assert caps.semantic == CapabilityState.UNAVAILABLE
    assert caps.hybrid == CapabilityState.UNAVAILABLE
    assert caps.semantic_reason == "provider_not_approved"
    assert caps.hybrid_reason == "provider_not_approved"

    # Immutability
    with pytest.raises(ValidationError):
        caps.lexical = CapabilityState.DISABLED  # type: ignore[misc]


def test_search_request_bounds():
    p_id = uuid4()
    v_id = uuid4()

    # Valid default request
    req = SearchRequest(project_id=p_id, architecture_version_id=v_id, q="WebService")
    assert req.q == "WebService"
    assert req.project_id == p_id
    assert req.architecture_version_id == v_id
    assert req.limit == DEFAULT_SEARCH_LIMIT
    assert req.timeout_seconds == DEFAULT_SEARCH_TIMEOUT_SECONDS
    assert req.document_kinds is None
    assert req.cursor is None

    # Max limit accepted
    req_max = SearchRequest(
        project_id=p_id,
        architecture_version_id=v_id,
        q="WebService",
        limit=MAX_SEARCH_LIMIT,
    )
    assert req_max.limit == 100

    # Limit > 100 rejected
    with pytest.raises(ValidationError):
        SearchRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            q="WebService",
            limit=101,
        )

    # Limit < 1 rejected
    with pytest.raises(ValidationError):
        SearchRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            q="WebService",
            limit=0,
        )

    # Max timeout accepted
    req_tout = SearchRequest(
        project_id=p_id,
        architecture_version_id=v_id,
        q="WebService",
        timeout_seconds=MAX_SEARCH_TIMEOUT_SECONDS,
    )
    assert req_tout.timeout_seconds == 5.0

    # Timeout > 5.0 rejected
    with pytest.raises(ValidationError):
        SearchRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            q="WebService",
            timeout_seconds=5.1,
        )

    # Timeout <= 0 rejected
    with pytest.raises(ValidationError):
        SearchRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            q="WebService",
            timeout_seconds=0.0,
        )

    # Query length limit
    with pytest.raises(ValidationError):
        SearchRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            q="x" * (MAX_SEARCH_QUERY_LENGTH + 1),
        )

    # Cursor length limit
    with pytest.raises(ValidationError):
        SearchRequest(
            project_id=p_id,
            architecture_version_id=v_id,
            q="WebService",
            cursor="c" * (MAX_SEARCH_CURSOR_LENGTH + 1),
        )

    # Kind filter
    req_kinds = SearchRequest(
        project_id=p_id,
        architecture_version_id=v_id,
        q="WebService",
        document_kinds=(
            KnowledgeDocumentKind.ENTITY,
            KnowledgeDocumentKind.RELATIONSHIP,
        ),
    )
    assert req_kinds.document_kinds == (
        KnowledgeDocumentKind.ENTITY,
        KnowledgeDocumentKind.RELATIONSHIP,
    )


def test_search_hit_validation():
    scope = make_test_scope()
    hit = SearchHit(
        knowledge_key="a" * 64,
        document_kind=KnowledgeDocumentKind.ENTITY,
        canonical_reference="architecture://entity/service/web",
        title="WebService",
        score=1.5,
        rank_tier=1,
        scope=scope,
    )
    assert hit.title == "WebService"
    assert hit.score == 1.5
    assert hit.rank_tier == 1
    assert hit.scope == scope

    # Negative score rejected
    with pytest.raises(ValidationError):
        SearchHit(
            knowledge_key="a" * 64,
            document_kind=KnowledgeDocumentKind.ENTITY,
            canonical_reference="architecture://entity/service/web",
            title="WebService",
            score=-0.1,
            scope=scope,
        )


def test_search_page_validation():
    scope = make_test_scope()
    gen_id = uuid4()
    hit = SearchHit(
        knowledge_key="a" * 64,
        document_kind=KnowledgeDocumentKind.ENTITY,
        canonical_reference="architecture://entity/service/web",
        title="WebService",
        score=1.0,
        scope=scope,
    )
    page = SearchPage(
        c1_version=C1_CONTRACT_VERSION,
        scope=scope,
        generation_id=gen_id,
        items=(hit,),
        total_hits=1,
        has_more=False,
    )
    assert page.total_hits == 1
    assert page.generation_id == gen_id
    assert len(page.items) == 1
    assert page.has_more is False
    assert page.next_cursor is None

    # Negative total_hits rejected
    with pytest.raises(ValidationError):
        SearchPage(
            c1_version=C1_CONTRACT_VERSION,
            scope=scope,
            generation_id=gen_id,
            items=(),
            total_hits=-1,
            has_more=False,
        )


def test_search_status():
    scope = make_test_scope()
    status = SearchStatus(
        scope=scope,
        resource_state="COMPLETED",
        freshness="CURRENT",
        is_readable=True,
        is_current_version=True,
    )
    assert status.is_readable is True
    assert status.resource_state == "COMPLETED"
    assert status.freshness == "CURRENT"


def test_resolved_search_generation():
    from tests.p5.knowledge.conftest import make_test_profile

    scope = make_test_scope()
    profile = make_test_profile()
    gen_id = uuid4()
    art_ref = ArtifactReference(
        scope=scope,
        binding=HandlerProfile(
            slot=WorkSlot(kind=WorkKind.SEARCH),
            profile=profile,
        ),
        input_fingerprint="1" * 64,
        resource_id=uuid4(),
        candidate_id=uuid4(),
        generation_id=gen_id,
        artifact_id=uuid4(),
        size_bytes=1024,
        digests=OutputDigests(content="2" * 64),
        sealed=True,
    )

    resolved = ResolvedSearchGeneration(
        reference=art_ref,
        index_name="stacksense-test-idx",
        index_uuid="idx-9999",
        generation_id=gen_id,
    )
    assert resolved.generation_id == gen_id
    assert resolved.index_uuid == "idx-9999"
    assert resolved.reference == art_ref
