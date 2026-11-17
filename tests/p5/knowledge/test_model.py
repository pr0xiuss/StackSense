"""Tests for P5-C1 knowledge models, canonical hashing, and manifest serialization."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from backend.platform.knowledge.model import (
    C1_CONTRACT_VERSION,
    SUMMARY_CANONICAL_REFERENCE,
    KnowledgeCounts,
    KnowledgeDocumentKind,
    KnowledgeModelError,
    KnowledgeProjection,
    KnowledgeRecord,
    SearchManifest,
    SearchVerificationResult,
    SourceReferenceDescriptor,
    canonical_json,
    compute_knowledge_key,
    compute_projection_digest,
    compute_storage_key,
)
from tests.p5.knowledge.conftest import (
    make_test_profile,
    make_test_scope,
)


def test_canonical_json_determinism():
    data1 = {"b": 2, "a": 1, "c": [3, 2, 1], "d": {"y": "yes", "x": "no"}}
    data2 = {"c": [3, 2, 1], "d": {"x": "no", "y": "yes"}, "a": 1, "b": 2}
    assert canonical_json(data1) == canonical_json(data2)
    assert canonical_json(data1) == '{"a":1,"b":2,"c":[3,2,1],"d":{"x":"no","y":"yes"}}'


def test_canonical_json_uuid_and_enum():
    uid = UUID("12345678-1234-5678-1234-567812345678")
    result = canonical_json({"id": uid, "kind": KnowledgeDocumentKind.ENTITY})
    assert result == '{"id":"12345678-1234-5678-1234-567812345678","kind":"entity"}'


def test_canonical_json_set_sorting():
    result = canonical_json({"items": {"beta", "alpha", "gamma"}})
    assert result == '{"items":["alpha","beta","gamma"]}'


def test_canonical_json_rejects_non_finite_float():
    with pytest.raises(KnowledgeModelError, match="non-finite float"):
        canonical_json({"val": float("nan")})

    with pytest.raises(KnowledgeModelError, match="non-finite float"):
        canonical_json({"val": float("inf")})


def test_compute_knowledge_key_determinism():
    p_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    v_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    ref = "architecture://entity/service/web"

    k1 = compute_knowledge_key(
        c1_version="1.0.0",
        project_id=p_id,
        architecture_version_id=v_id,
        document_kind=KnowledgeDocumentKind.ENTITY,
        canonical_reference=ref,
    )
    k2 = compute_knowledge_key(
        c1_version="1.0.0",
        project_id=p_id,
        architecture_version_id=v_id,
        document_kind=KnowledgeDocumentKind.ENTITY,
        canonical_reference=ref,
    )
    assert k1 == k2
    assert len(k1) == 64

    # Different reference changes key
    k3 = compute_knowledge_key(
        c1_version="1.0.0",
        project_id=p_id,
        architecture_version_id=v_id,
        document_kind=KnowledgeDocumentKind.ENTITY,
        canonical_reference="architecture://entity/service/db",
    )
    assert k1 != k3


def test_compute_storage_key_determinism():
    k_key = "a" * 64
    gen_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

    s1 = compute_storage_key(
        c1_version="1.0.0",
        knowledge_key=k_key,
        generation_id=gen_id,
    )
    s2 = compute_storage_key(
        c1_version="1.0.0",
        knowledge_key=k_key,
        generation_id=gen_id,
    )
    assert s1 == s2
    assert len(s1) == 64

    # Different generation changes storage key
    gen_id_other = uuid4()
    s3 = compute_storage_key(
        c1_version="1.0.0",
        knowledge_key=k_key,
        generation_id=gen_id_other,
    )
    assert s1 != s3


def test_source_reference_descriptor_path_safety():
    # Valid repo-relative path passes
    desc = SourceReferenceDescriptor(
        source_record_type="entity",
        path="src/backend/app.py",
        strength="direct_source",
        polarity="supporting",
    )
    assert desc.path == "src/backend/app.py"

    # Backslashes normalized to slashes
    desc2 = SourceReferenceDescriptor(
        source_record_type="entity",
        path=r"src\backend\app.py",
    )
    assert desc2.path == "src/backend/app.py"

    # Leading slash rejected
    with pytest.raises(ValidationError):
        SourceReferenceDescriptor(source_record_type="entity", path="/etc/passwd")

    # Path traversal rejected
    with pytest.raises(ValidationError):
        SourceReferenceDescriptor(
            source_record_type="entity", path="src/../../etc/passwd"
        )

    # Windows drive letter rejected
    with pytest.raises(ValidationError):
        SourceReferenceDescriptor(
            source_record_type="entity", path=r"C:\Windows\System32"
        )

    # Unix host path rejected
    with pytest.raises(ValidationError):
        SourceReferenceDescriptor(
            source_record_type="entity", path="/home/user/file.txt"
        )


def test_knowledge_counts_validation():
    # Valid counts
    counts = KnowledgeCounts(
        entities=10,
        relationships=5,
        evidence=8,
        unresolved=2,
        conflicts=1,
        architecture_summaries=1,
        total_records=27,
    )
    assert counts.total_records == 27

    # Total records mismatch rejected
    with pytest.raises(ValidationError):
        KnowledgeCounts(
            entities=10,
            relationships=5,
            evidence=8,
            unresolved=2,
            conflicts=1,
            architecture_summaries=1,
            total_records=99,
        )

    # Negative count rejected
    with pytest.raises(ValidationError):
        KnowledgeCounts(
            entities=-1,
            relationships=5,
            evidence=8,
            unresolved=2,
            conflicts=1,
            architecture_summaries=1,
            total_records=15,
        )


def test_knowledge_record_creation_and_digest():
    scope = make_test_scope()
    rec = KnowledgeRecord.create(
        scope=scope,
        document_kind=KnowledgeDocumentKind.ENTITY,
        canonical_reference="architecture://entity/service/web",
        title="WebService",
        text_fields={"name": "WebService", "kind": "service"},
        kind="service",
        status="confirmed",
        evidence_ids=("ev://2", "ev://1"),
        safe_metadata={"framework": "fastapi"},
    )

    assert rec.c1_version == C1_CONTRACT_VERSION
    assert rec.title == "WebService"
    assert rec.evidence_ids == ("ev://1", "ev://2")  # Sorted and deduped
    assert len(rec.record_digest) == 64
    assert rec.compute_semantic_digest() == rec.record_digest

    # Tampered digest rejected
    with pytest.raises(ValidationError):
        KnowledgeRecord(
            c1_version=rec.c1_version,
            scope=rec.scope,
            document_kind=rec.document_kind,
            canonical_reference=rec.canonical_reference,
            knowledge_key=rec.knowledge_key,
            title=rec.title,
            text_fields=rec.text_fields,
            evidence_ids=rec.evidence_ids,
            safe_metadata=rec.safe_metadata,
            record_digest="0" * 64,  # Tampered!
        )


def test_knowledge_record_envelope():
    scope = make_test_scope()
    rec = KnowledgeRecord.create(
        scope=scope,
        document_kind=KnowledgeDocumentKind.ENTITY,
        canonical_reference="architecture://entity/service/web",
        title="WebService",
    )
    gen_id = uuid4()
    envelope = rec.to_stored_envelope(generation_id=gen_id, index_uuid="idx-uuid-1")

    assert envelope["c1_version"] == C1_CONTRACT_VERSION
    assert envelope["generation_id"] == str(gen_id).lower()
    assert envelope["index_uuid"] == "idx-uuid-1"
    assert envelope["storage_key"] == compute_storage_key(
        c1_version=C1_CONTRACT_VERSION,
        knowledge_key=rec.knowledge_key,
        generation_id=gen_id,
    )
    assert envelope["record_semantic_digest"] == rec.record_digest


def test_knowledge_record_immutability():
    scope = make_test_scope()
    rec = KnowledgeRecord.create(
        scope=scope,
        document_kind=KnowledgeDocumentKind.ENTITY,
        canonical_reference="architecture://entity/service/web",
        title="WebService",
    )
    with pytest.raises(ValidationError):
        rec.title = "Changed"  # type: ignore[misc]


def test_knowledge_projection_sorting_and_digest():
    scope = make_test_scope()
    r1 = KnowledgeRecord.create(
        scope=scope,
        document_kind=KnowledgeDocumentKind.ENTITY,
        canonical_reference="architecture://entity/service/b",
        title="B",
    )
    r2 = KnowledgeRecord.create(
        scope=scope,
        document_kind=KnowledgeDocumentKind.ENTITY,
        canonical_reference="architecture://entity/service/a",
        title="A",
    )
    summary = KnowledgeRecord.create(
        scope=scope,
        document_kind=KnowledgeDocumentKind.ARCHITECTURE_SUMMARY,
        canonical_reference=SUMMARY_CANONICAL_REFERENCE,
        title="Architecture Summary",
    )

    records = (r1, r2, summary)
    counts = KnowledgeCounts(
        entities=2,
        relationships=0,
        evidence=0,
        unresolved=0,
        conflicts=0,
        architecture_summaries=1,
        total_records=3,
    )
    source_digest = "e" * 64
    proj_digest = compute_projection_digest(
        c1_version=C1_CONTRACT_VERSION,
        scope=scope,
        source_content_digest=source_digest,
        records=records,
        counts=counts,
    )

    proj = KnowledgeProjection(
        c1_version=C1_CONTRACT_VERSION,
        scope=scope,
        records=records,
        counts=counts,
        projection_digest=proj_digest,
        source_content_digest=source_digest,
    )

    # Records sorted by kind and knowledge_key
    assert len(proj.records) == 3
    # Tampered projection_digest rejected
    with pytest.raises(ValidationError):
        KnowledgeProjection(
            c1_version=C1_CONTRACT_VERSION,
            scope=scope,
            records=records,
            counts=counts,
            projection_digest="f" * 64,
            source_content_digest=source_digest,
        )


def test_search_manifest_serialization():
    scope = make_test_scope()
    profile = make_test_profile()
    counts = KnowledgeCounts(
        entities=1,
        relationships=0,
        evidence=0,
        unresolved=0,
        conflicts=0,
        architecture_summaries=1,
        total_records=2,
    )

    manifest = SearchManifest(
        c1_version=C1_CONTRACT_VERSION,
        scope=scope,
        profile=profile,
        input_fingerprint="1" * 64,
        candidate_id=uuid4(),
        generation_id=uuid4(),
        artifact_id=uuid4(),
        index_name="stacksense-search-test",
        index_uuid="uuid-idx-1234",
        settings_hash="2" * 64,
        mapping_hash="3" * 64,
        counts=counts,
        key_set_digest="4" * 64,
        payload_digest="5" * 64,
        projection_digest="6" * 64,
        verifier_version="1.0.0",
        seal_protocol_version="1.0.0",
    )

    b = manifest.to_canonical_bytes()
    assert isinstance(b, bytes)
    assert manifest.size_bytes() == len(b)
    digest = manifest.content_digest()
    assert len(digest) == 64


def test_search_verification_result():
    scope = make_test_scope()
    profile = make_test_profile()
    counts = KnowledgeCounts(
        entities=1,
        relationships=0,
        evidence=0,
        unresolved=0,
        conflicts=0,
        architecture_summaries=1,
        total_records=2,
    )

    # Verified result
    res_ok = SearchVerificationResult(
        c1_version=C1_CONTRACT_VERSION,
        scope=scope,
        attempt_id=uuid4(),
        candidate_id=uuid4(),
        generation_id=uuid4(),
        profile=profile,
        index_uuid="uuid-idx-1234",
        expected_counts=counts,
        actual_counts=counts,
        expected_key_set_digest="a" * 64,
        actual_key_set_digest="a" * 64,
        expected_payload_digest="b" * 64,
        actual_payload_digest="b" * 64,
        mapping_version="1.0.0",
        verifier_version="1.0.0",
        seal_version="1.0.0",
        verified=True,
    )
    assert res_ok.verified is True
    assert res_ok.failure_code is None

    # Failed verification result
    res_failed = SearchVerificationResult(
        c1_version=C1_CONTRACT_VERSION,
        scope=scope,
        attempt_id=uuid4(),
        candidate_id=uuid4(),
        generation_id=uuid4(),
        profile=profile,
        index_uuid="uuid-idx-1234",
        expected_counts=counts,
        actual_counts=counts,
        expected_key_set_digest="a" * 64,
        actual_key_set_digest="f" * 64,
        expected_payload_digest="b" * 64,
        actual_payload_digest="b" * 64,
        mapping_version="1.0.0",
        verifier_version="1.0.0",
        seal_version="1.0.0",
        verified=False,
        failure_code="key_set_digest_mismatch",
        failure_reason="Actual key set digest did not match expected",
    )
    assert res_failed.verified is False
    assert res_failed.failure_code == "key_set_digest_mismatch"
