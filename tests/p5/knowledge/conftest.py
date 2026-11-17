"""Reusable fixtures and canonical helpers for P5-C1 knowledge tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from backend.platform.analysis.architecture.model import (
    ArchitectureCompleteness,
    ArchitectureConflict,
    ArchitectureDocument,
    ArchitectureEntity,
    ArchitectureEntityKind,
    ArchitectureEvidence,
    ArchitectureEvidencePolarity,
    ArchitectureEvidenceStrength,
    ArchitectureFactStatus,
    ArchitectureRelationship,
    ArchitectureRelationshipKind,
    ArchitectureUnresolvedReason,
    ArchitectureUnresolvedRelationship,
)
from backend.platform.delivery.contracts import (
    ProducerProfile,
    VersionScope,
)


def make_test_scope(
    *,
    project_id: UUID | None = None,
    architecture_version_id: UUID | None = None,
    repository_id: UUID | None = None,
    analysis_id: UUID | None = None,
    snapshot_id: UUID | None = None,
    canonical_digest: str | None = None,
    configuration_fingerprint: str = "cfg-fingerprint-v1",
) -> VersionScope:
    return VersionScope(
        project_id=project_id or uuid4(),
        repository_id=repository_id or uuid4(),
        analysis_id=analysis_id or uuid4(),
        snapshot_id=snapshot_id or uuid4(),
        architecture_version_id=architecture_version_id or uuid4(),
        sequence_number=1,
        published_at=datetime.now(UTC),
        canonical_digest=canonical_digest or ("d" * 64),
        source_contract_version="1.0.0",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        configuration_fingerprint=configuration_fingerprint,
    )


def make_test_profile(
    *,
    producer_id: str = "knowledge-projector",
    producer_version: str = "1.0.0",
    generator_version: str = "1.0.0",
    output_schema_version: str = "1.0.0",
    configuration_fingerprint: str | None = None,
) -> ProducerProfile:
    return ProducerProfile(
        producer_id=producer_id,
        producer_version=producer_version,
        generator_version=generator_version,
        output_schema_version=output_schema_version,
        configuration_fingerprint=configuration_fingerprint or ("a" * 64),
    )


def make_test_evidence(
    logical_id: str = "evidence://src/core/app.py#1-10",
    *,
    path: str = "src/core/app.py",
    source_record_type: str = "entity",
    strength: ArchitectureEvidenceStrength = ArchitectureEvidenceStrength.DIRECT_SOURCE,
    polarity: ArchitectureEvidencePolarity = ArchitectureEvidencePolarity.SUPPORTING,
    metadata: dict[str, Any] | None = None,
) -> ArchitectureEvidence:
    return ArchitectureEvidence(
        logical_id=logical_id,
        source_evidence_key="ev-key-1",
        source_record_type=source_record_type,
        path=path,
        artifact_id=uuid4(),
        source_fact_key="fact-1",
        source_range={"start_line": 1, "start_col": 1, "end_line": 10, "end_col": 1},
        producer_id="p3.analyzer",
        producer_version="1.0.0",
        strength=strength,
        polarity=polarity,
        metadata=metadata or {},
    )


def make_test_entity(
    logical_id: str = "architecture://entity/service/web",
    *,
    name: str = "WebService",
    kind: ArchitectureEntityKind = ArchitectureEntityKind.SERVICE,
    namespace: tuple[str, ...] = ("app", "web"),
    status: ArchitectureFactStatus = ArchitectureFactStatus.CONFIRMED,
    evidence_ids: tuple[str, ...] = ("evidence://src/core/app.py#1-10",),
    metadata: dict[str, Any] | None = None,
) -> ArchitectureEntity:
    sig = hashlib.sha256(f"sig:{logical_id}".encode()).hexdigest().lower()
    return ArchitectureEntity(
        logical_id=logical_id,
        semantic_signature=sig,
        kind=kind,
        name=name,
        namespace=namespace,
        status=status,
        evidence_ids=evidence_ids,
        source_ir_keys=("ir:entity:1",),
        metadata=metadata or {},
    )


def make_test_relationship(
    logical_id: str = "architecture://rel/calls/web-to-db",
    source_logical_id: str = "architecture://entity/service/web",
    target_logical_id: str = "architecture://entity/service/db",
    *,
    kind: ArchitectureRelationshipKind = ArchitectureRelationshipKind.CALLS,
    status: ArchitectureFactStatus = ArchitectureFactStatus.CONFIRMED,
    evidence_ids: tuple[str, ...] = ("evidence://src/core/app.py#1-10",),
    metadata: dict[str, Any] | None = None,
) -> ArchitectureRelationship:
    return ArchitectureRelationship(
        logical_id=logical_id,
        kind=kind,
        source_logical_id=source_logical_id,
        target_logical_id=target_logical_id,
        status=status,
        evidence_ids=evidence_ids,
        source_ir_keys=("ir:rel:1",),
        metadata=metadata or {},
    )


def make_test_unresolved(
    logical_id: str = "architecture://unresolved/rel/external-api",
    source_logical_id: str = "architecture://entity/service/web",
    target_descriptor: str = "https://api.external.com/v1",
    *,
    kind: ArchitectureRelationshipKind = ArchitectureRelationshipKind.CALLS,
    reason: ArchitectureUnresolvedReason = ArchitectureUnresolvedReason.AMBIGUOUS,
    status: ArchitectureFactStatus = ArchitectureFactStatus.UNRESOLVED,
    evidence_ids: tuple[str, ...] = ("evidence://src/core/app.py#1-10",),
    metadata: dict[str, Any] | None = None,
) -> ArchitectureUnresolvedRelationship:
    return ArchitectureUnresolvedRelationship(
        logical_id=logical_id,
        kind=kind,
        source_logical_id=source_logical_id,
        target_descriptor=target_descriptor,
        reason=reason,
        status=status,
        evidence_ids=evidence_ids,
        source_ir_keys=("ir:unres:1",),
        metadata=metadata or {},
    )


def make_test_conflict(
    logical_id: str = "architecture://conflict/call-type-ambiguity",
    *,
    conflict_type: str = "role_ambiguity",
    subject_key: str = "architecture://entity/service/web",
    evidence_ids: tuple[str, ...] = ("evidence://src/core/app.py#1-10",),
    details: dict[str, Any] | None = None,
) -> ArchitectureConflict:
    return ArchitectureConflict(
        logical_id=logical_id,
        conflict_type=conflict_type,
        subject_key=subject_key,
        evidence_ids=evidence_ids,
        details=details or {},
    )


def make_test_completeness() -> ArchitectureCompleteness:
    return ArchitectureCompleteness(
        total_inventory_artifacts=5,
        analyzed_artifacts=5,
        failed_artifacts=0,
        total_syntax_documents=5,
        total_syntax_facts=10,
        source_entities=2,
        source_relationships=1,
        source_unresolved_references=1,
        source_conflicts=1,
        architecture_entities=2,
        architecture_relationships=1,
        architecture_unresolved_relationships=1,
        architecture_conflicts=1,
        is_partial=False,
    )


def make_test_document(
    *,
    scope: VersionScope | None = None,
    entities: tuple[ArchitectureEntity, ...] | None = None,
    relationships: tuple[ArchitectureRelationship, ...] | None = None,
    evidence: tuple[ArchitectureEvidence, ...] | None = None,
    unresolved_relationships: (
        tuple[ArchitectureUnresolvedRelationship, ...] | None
    ) = None,
    conflicts: tuple[ArchitectureConflict, ...] | None = None,
) -> tuple[ArchitectureDocument, VersionScope]:
    v_id = uuid4()
    p_id = uuid4()
    r_id = uuid4()
    a_id = uuid4()
    s_id = uuid4()
    cfg_fp = "cfg-fingerprint-v1"

    ev = evidence if evidence is not None else (make_test_evidence(),)
    ents = (
        entities
        if entities is not None
        else (
            make_test_entity(
                "architecture://entity/service/web",
                name="WebService",
                metadata={"framework": "fastapi", "runtime_role": "web"},
            ),
            make_test_entity(
                "architecture://entity/service/db",
                name="DatabaseService",
                kind=ArchitectureEntityKind.DATABASE,
                metadata={"database_engine": "postgresql"},
            ),
        )
    )
    rels = (
        relationships
        if relationships is not None
        else (
            make_test_relationship(
                "architecture://rel/calls/web-to-db",
                "architecture://entity/service/web",
                "architecture://entity/service/db",
                metadata={"method": "query"},
            ),
        )
    )
    unres = (
        unresolved_relationships
        if unresolved_relationships is not None
        else (make_test_unresolved(),)
    )
    confs = conflicts if conflicts is not None else (make_test_conflict(),)

    doc = ArchitectureDocument(
        architecture_version_id=v_id,
        analysis_id=a_id,
        project_id=p_id,
        repository_id=r_id,
        snapshot_id=s_id,
        configuration_fingerprint=cfg_fp,
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        entities=ents,
        relationships=rels,
        evidence=ev,
        unresolved_relationships=unres,
        conflicts=confs,
        completeness=make_test_completeness(),
    )

    actual_scope = VersionScope(
        project_id=p_id,
        repository_id=r_id,
        analysis_id=a_id,
        snapshot_id=s_id,
        architecture_version_id=v_id,
        sequence_number=1,
        published_at=datetime.now(UTC),
        canonical_digest=doc.content_digest,
        source_contract_version="1.0.0",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        configuration_fingerprint=cfg_fp,
    )
    return doc, actual_scope


@pytest.fixture
def sample_scope() -> VersionScope:
    return make_test_scope()


@pytest.fixture
def sample_profile() -> ProducerProfile:
    return make_test_profile()


@pytest.fixture
def sample_doc_and_scope() -> tuple[ArchitectureDocument, VersionScope]:
    return make_test_document()
