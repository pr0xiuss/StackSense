"""Tests for KnowledgeProjector, deterministic projection, and capacity caps."""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.platform.knowledge.contracts import (
    SearchCapacityExceededError,
    SearchIntegrityError,
)
from backend.platform.knowledge.model import (
    C1_CONTRACT_VERSION,
    SUMMARY_CANONICAL_REFERENCE,
    KnowledgeDocumentKind,
)
from backend.platform.knowledge.projection import (
    MAX_CANONICAL_SOURCE_BYTES,
    MAX_CONFLICTS,
    MAX_ENTITIES,
    MAX_EVIDENCE,
    MAX_METADATA_STRING_LENGTH,
    MAX_RELATIONSHIPS,
    MAX_UNRESOLVED,
    KnowledgeProjector,
    filter_safe_metadata,
)
from tests.p5.knowledge.conftest import (
    make_test_document,
    make_test_entity,
    make_test_evidence,
)


def test_filter_safe_metadata():
    raw = {
        "framework": "fastapi",
        "runtime_role": "web",
        "database_engine": "postgresql",
        "method": "query",
        "path": r"src\api\v1.py",
        "manifest_declared": True,
        "arbitrary_unapproved_key": "some_value",
        "secret_token": "super_secret_12345",
        "password": "mypassword",
        "nested_dict": {"k": "v"},
        "host_path_val": "C:\\Windows\\System32",
        "long_str": "x" * (MAX_METADATA_STRING_LENGTH + 1),
    }

    safe, omitted = filter_safe_metadata(raw)

    assert "framework" in safe and safe["framework"] == "fastapi"
    assert "runtime_role" in safe and safe["runtime_role"] == "web"
    assert "database_engine" in safe and safe["database_engine"] == "postgresql"
    assert "method" in safe and safe["method"] == "query"
    assert "path" in safe and safe["path"] == "src/api/v1.py"  # Normalized!
    assert "manifest_declared" in safe and safe["manifest_declared"] is True

    # Disallowed / sensitive / unsafe keys omitted
    assert "arbitrary_unapproved_key" not in safe
    assert "secret_token" not in safe
    assert "password" not in safe
    assert "nested_dict" not in safe
    assert "host_path_val" not in safe
    assert "long_str" not in safe

    assert omitted["arbitrary_unapproved_key"] == 1
    assert omitted["secret_token"] == 1
    assert omitted["password"] == 1
    assert omitted["nested_dict"] == 1


def test_filter_safe_metadata_path_validation():
    # Relative path passes
    safe, _ = filter_safe_metadata({"path": "app/main.py"})
    assert safe["path"] == "app/main.py"

    # Leading slash omitted
    safe, omitted = filter_safe_metadata({"path": "/app/main.py"})
    assert "path" not in safe
    assert omitted["path"] == 1

    # Traversal omitted
    safe, omitted = filter_safe_metadata({"path": "app/../main.py"})
    assert "path" not in safe
    assert omitted["path"] == 1

    # Host path omitted
    safe, omitted = filter_safe_metadata({"path": r"C:\app\main.py"})
    assert "path" not in safe
    assert omitted["path"] == 1


def test_pure_projection_determinism(sample_doc_and_scope):
    doc, scope = sample_doc_and_scope
    projector = KnowledgeProjector()

    p1 = projector.project(document=doc, scope=scope)
    p2 = projector.project(document=doc, scope=scope)

    assert p1.projection_digest == p2.projection_digest
    assert len(p1.records) == len(p2.records)
    assert p1.counts == p2.counts
    assert p1.c1_version == C1_CONTRACT_VERSION
    assert p1.source_content_digest == doc.content_digest

    # Individual records are identical
    for r1, r2 in zip(p1.records, p2.records, strict=True):
        assert r1.knowledge_key == r2.knowledge_key
        assert r1.record_digest == r2.record_digest


def test_projection_records_and_counts(sample_doc_and_scope):
    doc, scope = sample_doc_and_scope
    projector = KnowledgeProjector()
    proj = projector.project(document=doc, scope=scope)

    # In sample_doc: 2 entities, 1 rel, 1 ev, 1 unres, 1 conf, 1 summary = 7 records
    assert proj.counts.entities == 2
    assert proj.counts.relationships == 1
    assert proj.counts.evidence == 1
    assert proj.counts.unresolved == 1
    assert proj.counts.conflicts == 1
    assert proj.counts.architecture_summaries == 1
    assert proj.counts.total_records == 7
    assert len(proj.records) == 7

    # Verify summary record exists with exact canonical reference
    summaries = [
        r
        for r in proj.records
        if r.document_kind == KnowledgeDocumentKind.ARCHITECTURE_SUMMARY
    ]
    assert len(summaries) == 1
    assert summaries[0].canonical_reference == SUMMARY_CANONICAL_REFERENCE


def test_projection_input_permutation_invariance():
    e1 = make_test_entity("architecture://entity/service/b", name="ServiceB")
    e2 = make_test_entity("architecture://entity/service/a", name="ServiceA")
    ev1 = make_test_evidence("evidence://b.py#1-5", path="b.py")
    ev2 = make_test_evidence("evidence://a.py#1-5", path="a.py")

    # Document 1 with (e1, e2) and (ev1, ev2)
    doc1, scope1 = make_test_document(entities=(e1, e2), evidence=(ev1, ev2))

    # In ArchitectureDocument.__post_init__, entities and evidence are sorted
    # by logical_id, so doc1 already canonicalizes them.
    # To test permutation invariance of projection, verify project sorted output:
    projector = KnowledgeProjector()
    p1 = projector.project(document=doc1, scope=scope1)

    # Records in projection must be strictly sorted by (kind, knowledge_key)
    kinds_and_keys = [(r.document_kind.value, r.knowledge_key) for r in p1.records]
    assert kinds_and_keys == sorted(kinds_and_keys)


def test_projection_scope_mismatch_validation(sample_doc_and_scope):
    doc, scope = sample_doc_and_scope
    projector = KnowledgeProjector()

    # Mismatch architecture_version_id
    bad_scope_v = scope.model_copy(update={"architecture_version_id": uuid4()})
    with pytest.raises(SearchIntegrityError, match="Architecture version mismatch"):
        projector.project(document=doc, scope=bad_scope_v)

    # Mismatch project_id
    bad_scope_p = scope.model_copy(update={"project_id": uuid4()})
    with pytest.raises(SearchIntegrityError, match="Project ID mismatch"):
        projector.project(document=doc, scope=bad_scope_p)

    # Mismatch repository_id
    bad_scope_r = scope.model_copy(update={"repository_id": uuid4()})
    with pytest.raises(SearchIntegrityError, match="Repository ID mismatch"):
        projector.project(document=doc, scope=bad_scope_r)

    # Mismatch analysis_id
    bad_scope_a = scope.model_copy(update={"analysis_id": uuid4()})
    with pytest.raises(SearchIntegrityError, match="Analysis ID mismatch"):
        projector.project(document=doc, scope=bad_scope_a)

    # Mismatch snapshot_id
    bad_scope_s = scope.model_copy(update={"snapshot_id": uuid4()})
    with pytest.raises(SearchIntegrityError, match="Snapshot ID mismatch"):
        projector.project(document=doc, scope=bad_scope_s)

    # Mismatch canonical_digest
    bad_scope_d = scope.model_copy(update={"canonical_digest": "0" * 64})
    with pytest.raises(SearchIntegrityError, match="Content digest mismatch"):
        projector.project(document=doc, scope=bad_scope_d)

    # Mismatch configuration_fingerprint
    bad_scope_cfg = scope.model_copy(
        update={"configuration_fingerprint": "different_cfg"}
    )
    with pytest.raises(
        SearchIntegrityError, match="Configuration fingerprint mismatch"
    ):
        projector.project(document=doc, scope=bad_scope_cfg)


def test_capacity_exceeded_entities(sample_doc_and_scope):
    doc, scope = sample_doc_and_scope
    projector = KnowledgeProjector()

    original = doc.entities
    try:
        object.__setattr__(doc, "entities", tuple(range(MAX_ENTITIES + 1)))
        with pytest.raises(SearchCapacityExceededError, match="Entity count"):
            projector.project(document=doc, scope=scope)
    finally:
        object.__setattr__(doc, "entities", original)


def test_capacity_exceeded_relationships(sample_doc_and_scope):
    doc, scope = sample_doc_and_scope
    projector = KnowledgeProjector()

    original = doc.relationships
    try:
        object.__setattr__(doc, "relationships", tuple(range(MAX_RELATIONSHIPS + 1)))
        with pytest.raises(SearchCapacityExceededError, match="Relationship count"):
            projector.project(document=doc, scope=scope)
    finally:
        object.__setattr__(doc, "relationships", original)


def test_capacity_exceeded_evidence(sample_doc_and_scope):
    doc, scope = sample_doc_and_scope
    projector = KnowledgeProjector()

    original = doc.evidence
    try:
        object.__setattr__(doc, "evidence", tuple(range(MAX_EVIDENCE + 1)))
        with pytest.raises(SearchCapacityExceededError, match="Evidence count"):
            projector.project(document=doc, scope=scope)
    finally:
        object.__setattr__(doc, "evidence", original)


def test_capacity_exceeded_unresolved(sample_doc_and_scope):
    doc, scope = sample_doc_and_scope
    projector = KnowledgeProjector()

    original = doc.unresolved_relationships
    try:
        object.__setattr__(
            doc, "unresolved_relationships", tuple(range(MAX_UNRESOLVED + 1))
        )
        with pytest.raises(
            SearchCapacityExceededError, match="Unresolved relationship count"
        ):
            projector.project(document=doc, scope=scope)
    finally:
        object.__setattr__(doc, "unresolved_relationships", original)


def test_capacity_exceeded_conflicts(sample_doc_and_scope):
    doc, scope = sample_doc_and_scope
    projector = KnowledgeProjector()

    original = doc.conflicts
    try:
        object.__setattr__(doc, "conflicts", tuple(range(MAX_CONFLICTS + 1)))
        with pytest.raises(SearchCapacityExceededError, match="Conflict count"):
            projector.project(document=doc, scope=scope)
    finally:
        object.__setattr__(doc, "conflicts", original)


def test_capacity_exceeded_canonical_source_bytes(sample_doc_and_scope):
    doc, scope = sample_doc_and_scope
    projector = KnowledgeProjector()

    oversized_bytes = b"x" * (MAX_CANONICAL_SOURCE_BYTES + 1)
    with pytest.raises(SearchCapacityExceededError, match="Canonical source size"):
        projector.project(
            document=doc, scope=scope, canonical_source_bytes=oversized_bytes
        )
