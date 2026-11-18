"""Tests for SearchReader lexical search, exact-ID ranking, and HMAC pagination."""

from __future__ import annotations

import time
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import (
    AttemptIdentity,
    CandidateSeal,
    HandlerProfile,
    OutputDigests,
    PreparedOutput,
    WorkKind,
    WorkSlot,
)
from backend.platform.delivery.publication import PublicationContext
from backend.platform.knowledge.contracts import (
    SearchCursorExpiredError,
    SearchCursorInvalidError,
    SearchDeadlineExceededError,
    SearchGenerationChangedError,
    SearchNotReadyError,
    SearchRequest,
)
from backend.platform.knowledge.elasticsearch import InMemorySearchBackend
from backend.platform.knowledge.persistence import SEARCH_TABLES
from backend.platform.knowledge.reader import (
    SearchReader,
    decode_cursor,
    encode_cursor,
)
from backend.platform.knowledge.repository import (
    SearchPublicationPort,
    SqlAlchemySearchRepository,
)
from tests.p5.knowledge.conftest import (
    make_test_profile,
    make_test_scope,
)


@pytest.fixture
def reader_env():
    engine = create_engine("sqlite:///:memory:")
    for table in SEARCH_TABLES:
        table.create(engine)
    session = Session(engine)

    backend = InMemorySearchBackend()
    repo = SqlAlchemySearchRepository(session)
    reader = SearchReader(
        backend=backend,
        repository=repo,
        cursor_secret="test-secret-key-32-bytes-long-1234",
        cursor_ttl_seconds=120,
    )

    yield reader, backend, repo, session
    session.close()
    engine.dispose()


def stage_and_publish_test_index(
    repo: SqlAlchemySearchRepository,
    backend: InMemorySearchBackend,
    session: Session,
    scope,
    records: list[dict],
) -> tuple[UUID, UUID, str]:
    """Helper to stage and publish an index with specific stored records."""
    resource = repo.ensure_resource(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
    )
    gen_id = uuid4()
    cand_id = uuid4()
    idx_name = f"test-index-{gen_id.hex[:8]}"

    from backend.platform.knowledge.elasticsearch import (
        SEARCH_INDEX_MAPPINGS,
        SEARCH_INDEX_SETTINGS,
    )

    idx_uuid = backend.create_index(
        idx_name, SEARCH_INDEX_SETTINGS, SEARCH_INDEX_MAPPINGS
    )
    from backend.platform.knowledge.model import KnowledgeDocumentKind, KnowledgeRecord

    records = [
        KnowledgeRecord.create(
            scope=scope,
            document_kind=KnowledgeDocumentKind(record["document_kind"]),
            canonical_reference=record["canonical_reference"],
            title=record["title"],
            kind=record.get("kind"),
            status=record.get("status"),
            text_fields=record.get("text_fields", {}),
        ).to_stored_envelope(generation_id=gen_id, index_uuid=idx_uuid)
        for record in records
    ]
    backend.bulk_index_records(idx_name, records)
    backend.drain_and_seal_index(idx_name)

    # Stage candidate
    from tests.p5.knowledge.test_repository import make_dummy_manifest

    profile = make_test_profile()
    manifest = make_dummy_manifest(scope, profile, cand_id, gen_id)
    repo.stage_candidate(
        resource_id=resource.id,
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        candidate_id=cand_id,
        attempt_id=uuid4(),
        artifact_id=manifest.artifact_id,
        generation_id=gen_id,
        index_name=idx_name,
        index_uuid=idx_uuid,
        counts=manifest.counts,
        manifest=manifest,
    )

    # Publish via port
    port = SearchPublicationPort(session, backend=backend)
    binding = HandlerProfile(
        slot=WorkSlot(kind=WorkKind.SEARCH),
        profile=profile,
    )
    from backend.platform.delivery.contracts import WorkIdentity

    work = WorkIdentity(
        scope=scope,
        binding=binding,
        input_fingerprint="1" * 64,
        bundle_id=uuid4(),
        bundle_fingerprint="b" * 64,
        work_id=uuid4(),
        run_number=1,
    )
    attempt = AttemptIdentity(
        work=work,
        attempt_id=uuid4(),
        ordinal=1,
        fence=1,
        dispatch_epoch=uuid4(),
        candidate_id=cand_id,
    )
    manifest = manifest.model_copy(
        update={"attempt": attempt, "index_name": idx_name, "index_uuid": idx_uuid}
    )
    generation = repo.get_generation(gen_id)
    generation.attempt_id = attempt.attempt_id
    generation.manifest_bytes = manifest.to_canonical_bytes()
    generation.manifest_digest = manifest.content_digest()
    prepared = PreparedOutput(
        attempt=attempt,
        candidate=CandidateSeal(
            generation_id=gen_id,
            artifact_id=manifest.artifact_id,
            size_bytes=manifest.size_bytes(),
            digests=OutputDigests(content=manifest.content_digest()),
            sealed=True,
        ),
    )
    from datetime import UTC, datetime, timedelta

    pub_ctx = PublicationContext(
        transaction_id=uuid4(),
        attempt=attempt,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )
    port.publish_prepared(prepared, pub_ctx)
    session.commit()
    return resource.id, gen_id, idx_name


def test_search_not_ready_error(reader_env):
    reader, backend, repo, session = reader_env
    scope = make_test_scope()

    request = SearchRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        q="test",
    )
    with pytest.raises(SearchNotReadyError):
        reader.search(request)


def test_search_exact_id_ranking_and_text_match(reader_env):
    reader, backend, repo, session = reader_env
    scope = make_test_scope()

    records = [
        {
            "c1_version": "1.0.0",
            "project_id": str(scope.project_id),
            "architecture_version_id": str(scope.architecture_version_id),
            "repository_id": str(scope.repository_id),
            "snapshot_id": str(scope.snapshot_id),
            "analysis_id": str(scope.analysis_id),
            "document_kind": "entity",
            "canonical_reference": "entity:auth_service",
            "title": "Auth Service Component",
            "kind": "service",
            "status": "active",
            "knowledge_key": "1" * 64,
            "storage_key": "s1",
            "text_fields": {"description": "Handles authentication and tokens"},
            "record_semantic_digest": "d1",
        },
        {
            "c1_version": "1.0.0",
            "project_id": str(scope.project_id),
            "architecture_version_id": str(scope.architecture_version_id),
            "repository_id": str(scope.repository_id),
            "snapshot_id": str(scope.snapshot_id),
            "analysis_id": str(scope.analysis_id),
            "document_kind": "entity",
            "canonical_reference": "entity:user_service",
            "title": "User Service",
            "kind": "service",
            "status": "active",
            "knowledge_key": "2" * 64,
            "storage_key": "s2",
            "text_fields": {
                "description": "Communicates with entity:auth_service for validation"
            },
            "record_semantic_digest": "d2",
        },
    ]

    _, gen_id, _ = stage_and_publish_test_index(repo, backend, session, scope, records)

    # 1. Exact canonical reference match
    req1 = SearchRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        q="entity:auth_service",
    )
    page1 = reader.search(req1)
    assert page1.total_hits == 2
    # Tier 1 exact match should rank first
    assert page1.items[0].canonical_reference == "entity:auth_service"
    assert page1.items[0].rank_tier == 1
    # Tier 2 text substring match should rank second
    assert page1.items[1].canonical_reference == "entity:user_service"
    assert page1.items[1].rank_tier == 2

    # Verify read pin was cleaned up
    assert repo.get_active_read_pin_count(gen_id) == 0


def test_c1_consumer_port_with_actual_reader(reader_env):
    from tests.p5.knowledge.test_c1_consumers import consume_page

    reader, backend, repo, session = reader_env
    scope, actor = make_test_scope(), uuid4()
    rows = [
        {
            "document_kind": "entity",
            "canonical_reference": f"entity:{i}",
            "title": f"Service {i}",
            "kind": "service",
            "status": "confirmed",
        }
        for i in range(3)
    ]
    _, generation, index_name = stage_and_publish_test_index(
        repo, backend, session, scope, rows
    )
    exact_index_uuid = backend.inspect_index(index_name)["uuid"]
    request = SearchRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        q="Service",
        limit=1,
    )
    seen = set()
    while True:
        page = consume_page(reader, request, actor)
        assert page.generation_id == generation
        assert page.index_uuid == exact_index_uuid
        assert not seen.intersection(hit.knowledge_key for hit in page.items)
        seen.update(hit.knowledge_key for hit in page.items)
        if not page.has_more:
            break
        request = SearchRequest.model_validate_json(
            request.model_copy(update={"cursor": page.next_cursor}).model_dump_json()
        )
    assert len(seen) == 3
    assert repo.get_active_read_pin_count(generation) == 0


@pytest.mark.parametrize("loss", ["replacement", "index_missing", "index_recreated"])
def test_pinned_continuation_never_switches_generation_or_index(reader_env, loss):
    from backend.platform.knowledge.contracts import (
        SearchBackendUnavailableError,
        SearchGenerationChangedError,
        SearchIntegrityError,
    )
    from backend.platform.knowledge.elasticsearch import (
        SEARCH_INDEX_MAPPINGS,
        SEARCH_INDEX_SETTINGS,
    )

    reader, backend, repo, session = reader_env
    scope, actor = make_test_scope(), uuid4()
    rows = [
        {
            "document_kind": "entity",
            "canonical_reference": f"entity:{i}",
            "title": f"Service {i}",
        }
        for i in range(2)
    ]
    _, generation, index = stage_and_publish_test_index(
        repo, backend, session, scope, rows
    )
    request = SearchRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        q="Service",
        limit=1,
    )
    first = reader.search(request, actor_id=actor)
    assert first.has_more and first.generation_id == generation
    if loss == "replacement":
        stage_and_publish_test_index(repo, backend, session, scope, rows)
        expected = SearchGenerationChangedError
    else:
        backend.delete_index(index)
        if loss == "index_recreated":
            backend.create_index(index, SEARCH_INDEX_SETTINGS, SEARCH_INDEX_MAPPINGS)
            backend.drain_and_seal_index(index)
            expected = SearchIntegrityError
        else:
            expected = SearchBackendUnavailableError
    with pytest.raises(expected):
        reader.search(
            request.model_copy(update={"cursor": first.next_cursor}), actor_id=actor
        )


def test_search_pagination_cursor(reader_env):
    reader, backend, repo, session = reader_env
    scope = make_test_scope()

    # Create 5 records
    records = []
    for i in range(5):
        records.append(
            {
                "c1_version": "1.0.0",
                "project_id": str(scope.project_id),
                "architecture_version_id": str(scope.architecture_version_id),
                "repository_id": str(scope.repository_id),
                "snapshot_id": str(scope.snapshot_id),
                "analysis_id": str(scope.analysis_id),
                "document_kind": "entity",
                "canonical_reference": f"entity:component_{i}",
                "title": f"Component {i}",
                "kind": "component",
                "status": "active",
                "knowledge_key": f"{i}" * 64,
                "storage_key": f"s_{i}",
                "text_fields": {"description": "Shared component description"},
                "record_semantic_digest": f"d_{i}",
            }
        )

    _, gen_id, _ = stage_and_publish_test_index(repo, backend, session, scope, records)

    # Page 1: limit 2
    req_p1 = SearchRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        q="component",
        limit=2,
    )
    page1 = reader.search(req_p1)
    assert len(page1.items) == 2
    assert page1.total_hits == 5
    assert page1.has_more is True
    assert page1.next_cursor is not None

    # Page 2: resume with cursor
    req_p2 = SearchRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        q="component",
        limit=2,
        cursor=page1.next_cursor,
    )
    page2 = reader.search(req_p2)
    assert len(page2.items) == 2
    assert page2.has_more is True
    assert page2.items[0].canonical_reference != page1.items[0].canonical_reference

    # Page 3: final item
    req_p3 = SearchRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        q="component",
        limit=2,
        cursor=page2.next_cursor,
    )
    page3 = reader.search(req_p3)
    assert len(page3.items) == 1
    assert page3.has_more is False
    assert page3.next_cursor is None


def test_cursor_security_validations():
    gen_id = uuid4()
    proj_id = uuid4()
    arch_id = uuid4()
    secret = "test-secret"
    qh = "1" * 64

    cursor = encode_cursor(
        generation_id=gen_id,
        project_id=proj_id,
        architecture_version_id=arch_id,
        state={"pit": "fixture-pit", "after": [1, "key"], "pin": str(uuid4())},
        query_hash=qh,
        secret=secret,
        ttl_seconds=60.0,
    )

    # Valid decode
    fields = decode_cursor(
        cursor,
        expected_generation_id=gen_id,
        expected_project_id=proj_id,
        expected_architecture_version_id=arch_id,
        expected_query_hash=qh,
        secret=secret,
    )
    assert fields["state"]["after"] == [1, "key"]

    # 1. Tampered signature
    with pytest.raises(SearchCursorInvalidError):
        decode_cursor(
            cursor,
            expected_generation_id=gen_id,
            expected_project_id=proj_id,
            expected_architecture_version_id=arch_id,
            expected_query_hash=qh,
            secret="wrong-secret",
        )

    # 2. Scope mismatch
    with pytest.raises(SearchCursorInvalidError):
        decode_cursor(
            cursor,
            expected_generation_id=gen_id,
            expected_project_id=uuid4(),
            expected_architecture_version_id=arch_id,
            expected_query_hash=qh,
            secret=secret,
        )

    # 3. Query mismatch
    with pytest.raises(SearchCursorInvalidError):
        decode_cursor(
            cursor,
            expected_generation_id=gen_id,
            expected_project_id=proj_id,
            expected_architecture_version_id=arch_id,
            expected_query_hash="2" * 64,
            secret=secret,
        )

    # 4. Generation changed
    with pytest.raises(SearchGenerationChangedError):
        decode_cursor(
            cursor,
            expected_generation_id=uuid4(),
            expected_project_id=proj_id,
            expected_architecture_version_id=arch_id,
            expected_query_hash=qh,
            secret=secret,
        )

    # 5. Expired cursor
    expired_cursor = encode_cursor(
        generation_id=gen_id,
        project_id=proj_id,
        architecture_version_id=arch_id,
        state={"pit": "fixture-pit", "after": [1, "key"], "pin": str(uuid4())},
        query_hash=qh,
        secret=secret,
        ttl_seconds=-10.0,
    )
    with pytest.raises(SearchCursorExpiredError):
        decode_cursor(
            expired_cursor,
            expected_generation_id=gen_id,
            expected_project_id=proj_id,
            expected_architecture_version_id=arch_id,
            expected_query_hash=qh,
            secret=secret,
        )


def test_search_deadline_exceeded(reader_env):
    reader, backend, repo, session = reader_env
    scope = make_test_scope()
    _, gen_id, _ = stage_and_publish_test_index(repo, backend, session, scope, [])

    req = SearchRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        q="test",
        timeout_seconds=0.0001,
    )
    time.sleep(0.001)
    with pytest.raises(SearchDeadlineExceededError):
        reader.search(req)
