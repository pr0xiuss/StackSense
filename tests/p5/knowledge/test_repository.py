"""Tests for SearchRepository and enlisted SearchPublicationPort."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import (
    AttemptIdentity,
    CandidateSeal,
    DeliveryExecutionFailure,
    HandlerProfile,
    OutputDigests,
    PreparedOutput,
    WorkIdentity,
    WorkKind,
    WorkSlot,
)
from backend.platform.delivery.publication import PublicationContext
from backend.platform.knowledge.model import (
    KnowledgeCounts,
    SearchManifest,
)
from backend.platform.knowledge.persistence import (
    SEARCH_TABLES,
    SearchPublicationReceiptModel,
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
def repo_session():
    engine = create_engine("sqlite:///:memory:")
    for table in SEARCH_TABLES:
        table.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def make_dummy_manifest(scope, profile, candidate_id, generation_id):
    from backend.platform.knowledge.elasticsearch import (
        SEARCH_INDEX_MAPPINGS,
        SEARCH_INDEX_SETTINGS,
        compute_mapping_hash,
        compute_settings_hash,
    )

    counts = KnowledgeCounts(
        entities=1,
        relationships=0,
        evidence=0,
        unresolved=0,
        conflicts=0,
        architecture_summaries=1,
        total_records=2,
    )
    return SearchManifest(
        c1_version="1.0.0",
        scope=scope,
        profile=profile,
        input_fingerprint="1" * 64,
        candidate_id=candidate_id,
        generation_id=generation_id,
        artifact_id=uuid4(),
        index_name="test-idx",
        index_uuid="uuid-1234",
        settings_hash=compute_settings_hash(SEARCH_INDEX_SETTINGS),
        mapping_hash=compute_mapping_hash(SEARCH_INDEX_MAPPINGS),
        counts=counts,
        key_set_digest="4" * 64,
        payload_digest="5" * 64,
        projection_digest="6" * 64,
        verifier_version="1.0.0",
        seal_protocol_version="1.0.0",
        sealed_at=datetime.now(UTC),
    )


def test_search_repository_stage_and_active(repo_session):
    repo = SqlAlchemySearchRepository(repo_session)
    scope = make_test_scope()
    profile = make_test_profile()

    resource = repo.ensure_resource(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
    )
    assert resource.status == "PENDING"
    assert resource.active_generation_id is None

    gen_id = uuid4()
    cand_id = uuid4()
    manifest = make_dummy_manifest(scope, profile, cand_id, gen_id)

    gen = repo.stage_candidate(
        resource_id=resource.id,
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        candidate_id=cand_id,
        attempt_id=uuid4(),
        artifact_id=uuid4(),
        generation_id=gen_id,
        index_name="test-idx",
        index_uuid="uuid-1234",
        counts=manifest.counts,
        manifest=manifest,
    )
    assert gen.state == "SEALED"

    # Not active yet
    assert (
        repo.get_active_generation(
            project_id=scope.project_id,
            architecture_version_id=scope.architecture_version_id,
        )
        is None
    )

    # Mark cleanup succeeds for unactivated generation
    repo.mark_cleanup(gen_id)
    assert gen.state == "CLEANUP_MARKED"


def test_search_publication_port_activation(repo_session):
    from backend.platform.knowledge.elasticsearch import (
        SEARCH_INDEX_MAPPINGS,
        SEARCH_INDEX_SETTINGS,
        InMemorySearchBackend,
    )

    backend = InMemorySearchBackend()
    physical = backend.create_index(
        "test-idx", SEARCH_INDEX_SETTINGS, SEARCH_INDEX_MAPPINGS
    )
    backend.drain_and_seal_index("test-idx")
    repo = SqlAlchemySearchRepository(repo_session)
    scope = make_test_scope()
    profile = make_test_profile()

    resource = repo.ensure_resource(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
    )

    gen_id = uuid4()
    cand_id = uuid4()
    attempt_id = uuid4()
    manifest = make_dummy_manifest(scope, profile, cand_id, gen_id).model_copy(
        update={"index_uuid": physical}
    )

    gen = repo.stage_candidate(
        resource_id=resource.id,
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        candidate_id=cand_id,
        attempt_id=attempt_id,
        artifact_id=manifest.artifact_id,
        generation_id=gen_id,
        index_name="test-idx",
        index_uuid=physical,
        counts=manifest.counts,
        manifest=manifest,
    )

    # Construct M1 execution context objects
    binding = HandlerProfile(
        slot=WorkSlot(kind=WorkKind.SEARCH),
        profile=profile,
    )
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
        attempt_id=attempt_id,
        ordinal=1,
        fence=1,
        dispatch_epoch=uuid4(),
        candidate_id=cand_id,
    )
    manifest = manifest.model_copy(update={"attempt": attempt})
    gen.manifest_bytes = manifest.to_canonical_bytes()
    gen.manifest_digest = manifest.content_digest()
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
    pub_ctx = PublicationContext(
        transaction_id=uuid4(),
        attempt=attempt,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )

    port = SearchPublicationPort(repo_session, backend=backend)
    accepted = port.publish_prepared(prepared, pub_ctx)

    assert accepted.reference.generation_id == gen_id
    assert accepted.reference.candidate_id == cand_id

    # Verify DB state
    assert gen.state == "ACTIVE"
    assert resource.active_generation_id == gen_id
    assert resource.status == "COMPLETED"

    # Verify receipt exists
    receipt = repo_session.scalar(
        select(SearchPublicationReceiptModel).where(
            SearchPublicationReceiptModel.candidate_id == cand_id
        )
    )
    assert receipt is not None

    # Readiness validation passes
    ready_val = port.validate_ready(accepted.reference, pub_ctx)
    assert ready_val.reference == accepted.reference


def test_search_publication_rejects_unsealed_or_cleanup_marked(repo_session):
    repo = SqlAlchemySearchRepository(repo_session)
    scope = make_test_scope()
    profile = make_test_profile()
    resource = repo.ensure_resource(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
    )

    gen_id = uuid4()
    cand_id = uuid4()
    attempt_id = uuid4()
    manifest = make_dummy_manifest(scope, profile, cand_id, gen_id)

    gen = repo.stage_candidate(
        resource_id=resource.id,
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        candidate_id=cand_id,
        attempt_id=attempt_id,
        artifact_id=manifest.artifact_id,
        generation_id=gen_id,
        index_name="test-idx",
        index_uuid="uuid-1234",
        counts=manifest.counts,
        manifest=manifest,
    )

    binding = HandlerProfile(
        slot=WorkSlot(kind=WorkKind.SEARCH),
        profile=profile,
    )
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
        attempt_id=attempt_id,
        ordinal=1,
        fence=1,
        dispatch_epoch=uuid4(),
        candidate_id=cand_id,
    )
    manifest = manifest.model_copy(update={"attempt": attempt})
    gen.manifest_bytes = manifest.to_canonical_bytes()
    gen.manifest_digest = manifest.content_digest()
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

    # 1. Reject if marked for cleanup
    repo.mark_cleanup(gen_id)
    pub_ctx = PublicationContext(
        transaction_id=uuid4(),
        attempt=attempt,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )
    port = SearchPublicationPort(repo_session)
    with pytest.raises(DeliveryExecutionFailure) as exc_info:
        port.publish_prepared(prepared, pub_ctx)
    assert exc_info.value.failure.code == "candidate_cleanup_marked"

    # 2. Reject if past deadline
    gen.state = "SEALED"
    expired_ctx = PublicationContext(
        transaction_id=uuid4(),
        attempt=attempt,
        deadline=datetime.now(UTC) - timedelta(seconds=1),
    )
    with pytest.raises(DeliveryExecutionFailure) as exc_info2:
        port.publish_prepared(prepared, expired_ctx)
    assert exc_info2.value.failure.code == "publication_deadline_exceeded"
