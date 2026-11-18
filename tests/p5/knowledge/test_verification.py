"""Tests for SearchVerifier independent candidate auditing and digest checking."""

from __future__ import annotations

from uuid import uuid4

from backend.platform.knowledge.elasticsearch import (
    SEARCH_INDEX_MAPPINGS,
    SEARCH_INDEX_SETTINGS,
    InMemorySearchBackend,
)
from backend.platform.knowledge.projection import KnowledgeProjector
from backend.platform.knowledge.verification import SearchVerifier
from tests.p5.knowledge.conftest import make_test_profile


def test_search_verifier_success(sample_doc_and_scope):
    doc, scope = sample_doc_and_scope
    profile = make_test_profile()
    projector = KnowledgeProjector()
    projection = projector.project(document=doc, scope=scope, profile=profile)

    backend = InMemorySearchBackend()
    idx_name = "stacksense-search-verify-ok"
    idx_uuid = backend.create_index(
        index_name=idx_name,
        settings=SEARCH_INDEX_SETTINGS,
        mappings=SEARCH_INDEX_MAPPINGS,
    )

    gen_id = uuid4()
    cand_id = uuid4()
    envelopes = [
        r.to_stored_envelope(generation_id=gen_id, index_uuid=idx_uuid)
        for r in projection.records
    ]
    backend.bulk_index_records(idx_name, envelopes)
    backend.drain_and_seal_index(idx_name)

    verifier = SearchVerifier(backend)
    result = verifier.verify(
        scope=scope,
        profile=profile,
        candidate_id=cand_id,
        attempt_id=uuid4(),
        generation_id=gen_id,
        index_name=idx_name,
        index_uuid=idx_uuid,
        expected_projection=projection,
    )

    assert result.verified is True
    assert result.failure_code is None
    assert result.actual_counts == projection.counts
    assert result.actual_key_set_digest == result.expected_key_set_digest
    assert result.actual_payload_digest == result.expected_payload_digest


def test_search_verifier_count_mismatch(sample_doc_and_scope):
    doc, scope = sample_doc_and_scope
    profile = make_test_profile()
    projector = KnowledgeProjector()
    projection = projector.project(document=doc, scope=scope, profile=profile)

    backend = InMemorySearchBackend()
    idx_name = "stacksense-search-verify-count-err"
    idx_uuid = backend.create_index(
        index_name=idx_name,
        settings=SEARCH_INDEX_SETTINGS,
        mappings=SEARCH_INDEX_MAPPINGS,
    )

    gen_id = uuid4()
    cand_id = uuid4()
    # Omit one record during indexing
    envelopes = [
        r.to_stored_envelope(generation_id=gen_id, index_uuid=idx_uuid)
        for r in projection.records[:-1]
    ]
    backend.bulk_index_records(idx_name, envelopes)
    backend.drain_and_seal_index(idx_name)

    verifier = SearchVerifier(backend)
    result = verifier.verify(
        scope=scope,
        profile=profile,
        candidate_id=cand_id,
        attempt_id=uuid4(),
        generation_id=gen_id,
        index_name=idx_name,
        index_uuid=idx_uuid,
        expected_projection=projection,
    )

    assert result.verified is False
    assert result.failure_code == "count_mismatch"


def test_search_verifier_payload_digest_mismatch(sample_doc_and_scope):
    doc, scope = sample_doc_and_scope
    profile = make_test_profile()
    projector = KnowledgeProjector()
    projection = projector.project(document=doc, scope=scope, profile=profile)

    backend = InMemorySearchBackend()
    idx_name = "stacksense-search-verify-tamper"
    idx_uuid = backend.create_index(
        index_name=idx_name,
        settings=SEARCH_INDEX_SETTINGS,
        mappings=SEARCH_INDEX_MAPPINGS,
    )

    gen_id = uuid4()
    cand_id = uuid4()
    envelopes = [
        r.to_stored_envelope(generation_id=gen_id, index_uuid=idx_uuid)
        for r in projection.records
    ]
    # Tamper with the record semantic digest of the first document in the index
    envelopes[0]["record_semantic_digest"] = "f" * 64

    backend.bulk_index_records(idx_name, envelopes)
    backend.drain_and_seal_index(idx_name)

    verifier = SearchVerifier(backend)
    result = verifier.verify(
        scope=scope,
        profile=profile,
        candidate_id=cand_id,
        attempt_id=uuid4(),
        generation_id=gen_id,
        index_name=idx_name,
        index_uuid=idx_uuid,
        expected_projection=projection,
    )

    assert result.verified is False
    assert result.failure_code == "stored_payload_mismatch"
    # Recomputed content remains equal; only the persisted digest label was
    # corrupted. The verifier must reject that label without trusting it.
    assert result.actual_payload_digest == result.expected_payload_digest
