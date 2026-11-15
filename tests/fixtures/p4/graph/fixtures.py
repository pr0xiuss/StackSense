"""Deterministic test fixtures for Phase 4 Module 2 graph projection."""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID, uuid4

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

DEFAULT_PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")
DEFAULT_VERSION_ID = UUID("22222222-2222-2222-2222-222222222222")
DEFAULT_GENERATION_ID = UUID("33333333-3333-3333-3333-333333333333")


def make_completeness(
    *,
    entities: int = 2,
    relationships: int = 1,
    evidence: int = 1,
    unresolved: int = 0,
    conflicts: int = 0,
) -> ArchitectureCompleteness:
    return ArchitectureCompleteness(
        total_inventory_artifacts=1,
        analyzed_artifacts=1,
        failed_artifacts=0,
        total_syntax_documents=1,
        total_syntax_facts=4,
        source_entities=entities,
        source_relationships=relationships,
        source_unresolved_references=unresolved,
        source_conflicts=conflicts,
        architecture_entities=entities,
        architecture_relationships=relationships,
        architecture_unresolved_relationships=unresolved,
        architecture_conflicts=conflicts,
        is_partial=False,
    )


def make_evidence(
    logical_id: str = "evidence://file1#1-10",
    *,
    path: str = "src/app.py",
) -> ArchitectureEvidence:
    return ArchitectureEvidence(
        logical_id=logical_id,
        source_evidence_key="ev-key-1",
        source_record_type="entity",
        path=path,
        artifact_id=uuid4(),
        source_fact_key="fact-1",
        source_range={"start_line": 1, "start_col": 1, "end_line": 10, "end_col": 1},
        producer_id="p3.analyzer",
        producer_version="1.0.0",
        strength=ArchitectureEvidenceStrength.DIRECT_SOURCE,
        polarity=ArchitectureEvidencePolarity.SUPPORTING,
        metadata={},
    )


def make_entity(
    logical_id: str,
    *,
    kind: ArchitectureEntityKind = ArchitectureEntityKind.SERVICE,
    name: str = "Service",
    namespace: tuple[str, ...] = ("app",),
    status: ArchitectureFactStatus = ArchitectureFactStatus.CONFIRMED,
    evidence_ids: tuple[str, ...] = ("evidence://file1#1-10",),
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


def make_relationship(
    logical_id: str,
    source_id: str,
    target_id: str,
    *,
    kind: ArchitectureRelationshipKind = ArchitectureRelationshipKind.CALLS,
    status: ArchitectureFactStatus = ArchitectureFactStatus.CONFIRMED,
    evidence_ids: tuple[str, ...] = ("evidence://file1#1-10",),
    metadata: dict[str, Any] | None = None,
) -> ArchitectureRelationship:
    return ArchitectureRelationship(
        logical_id=logical_id,
        kind=kind,
        source_logical_id=source_id,
        target_logical_id=target_id,
        status=status,
        evidence_ids=evidence_ids,
        source_ir_keys=("ir:rel:1",),
        metadata=metadata or {},
    )


def small_document(
    project_id: UUID = DEFAULT_PROJECT_ID,
    version_id: UUID = DEFAULT_VERSION_ID,
) -> ArchitectureDocument:
    """Minimal document with 2 entities and 1 connecting relationship."""
    ev = make_evidence()
    e1 = make_entity(
        "entity://web",
        kind=ArchitectureEntityKind.SERVICE,
        name="WebService",
        metadata={
            "application_namespace": "web",
            "runtime_role": "frontend_gateway",
            "source_root": "services/web",
            "framework": "fastapi",
            "manifest_declared": True,
            "role_inference_signals": ["fastapi_app", "main_router"],
        },
    )
    e2 = make_entity(
        "entity://db",
        kind=ArchitectureEntityKind.DATABASE,
        name="PostgresDatabase",
        metadata={
            "database_engine": "postgresql",
            "source_referenced": True,
        },
    )
    rel = make_relationship(
        "rel://web-calls-db",
        "entity://web",
        "entity://db",
        kind=ArchitectureRelationshipKind.CALLS,
        metadata={
            "transformation_rule_ids": ["m4.rule.call.v1"],
        },
    )
    return ArchitectureDocument(
        architecture_version_id=version_id,
        analysis_id=uuid4(),
        project_id=project_id,
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        configuration_fingerprint="cfg-test-v1",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        entities=(e1, e2),
        relationships=(rel,),
        evidence=(ev,),
        unresolved_relationships=(),
        conflicts=(),
        completeness=make_completeness(entities=2, relationships=1, evidence=1),
    )


def no_edge_document(
    project_id: UUID = DEFAULT_PROJECT_ID,
    version_id: UUID = DEFAULT_VERSION_ID,
) -> ArchitectureDocument:
    """Document with 3 entities and 0 relationships."""
    ev = make_evidence()
    e1 = make_entity("entity://service-a", name="ServiceA")
    e2 = make_entity("entity://service-b", name="ServiceB")
    e3 = make_entity("entity://service-c", name="ServiceC")
    return ArchitectureDocument(
        architecture_version_id=version_id,
        analysis_id=uuid4(),
        project_id=project_id,
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        configuration_fingerprint="cfg-test-no-edge",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        entities=(e1, e2, e3),
        relationships=(),
        evidence=(ev,),
        unresolved_relationships=(),
        conflicts=(),
        completeness=make_completeness(entities=3, relationships=0, evidence=1),
    )


def dense_document(
    project_id: UUID = DEFAULT_PROJECT_ID,
    version_id: UUID = DEFAULT_VERSION_ID,
    node_count: int = 5,
) -> ArchitectureDocument:
    """Document with dense directed mesh of relationships."""
    ev = make_evidence()
    entities = [
        make_entity(f"entity://node-{i}", name=f"Node-{i}") for i in range(node_count)
    ]
    relationships = []
    rel_idx = 0
    for i in range(node_count):
        for j in range(node_count):
            if i != j:
                relationships.append(
                    make_relationship(
                        f"rel://mesh-{rel_idx}",
                        f"entity://node-{i}",
                        f"entity://node-{j}",
                    )
                )
                rel_idx += 1
    return ArchitectureDocument(
        architecture_version_id=version_id,
        analysis_id=uuid4(),
        project_id=project_id,
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        configuration_fingerprint="cfg-dense-mesh",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        entities=tuple(entities),
        relationships=tuple(relationships),
        evidence=(ev,),
        unresolved_relationships=(),
        conflicts=(),
        completeness=make_completeness(
            entities=node_count,
            relationships=len(relationships),
            evidence=1,
        ),
    )


def unicode_document(
    project_id: UUID = DEFAULT_PROJECT_ID,
    version_id: UUID = DEFAULT_VERSION_ID,
) -> ArchitectureDocument:
    """Document with extensive non-ASCII Unicode characters and normalized paths."""
    ev = make_evidence("evidence://unicode-éàç#1-5")
    e1 = make_entity(
        "entity://сервис-клиентов",
        name="Клиентский Сервис (Client Service 日本語 🚀)",
        namespace=("облако", "регион-1"),
        metadata={
            "application_namespace": "сервис_клиентов",
            "runtime_role": "микросервис",
            "source_root": "путь/к/исходникам",
            "framework": "джанго",
            "path": "/клиенты/список/",
            "mount_path": "/api/v1/клиенты",
            "declared_path": "/api/v1/клиенты/{id}",
            "manifest_declared": True,
            "role_inference_signals": ["сигнал_1", "сигнал_2"],
        },
        evidence_ids=("evidence://unicode-éàç#1-5",),
    )
    e2 = make_entity(
        "entity://bază-date",
        name="Bază de Date (Română 🇷🇴)",
        namespace=("date",),
        metadata={
            "database_engine": "postgresql",
            "source_referenced": False,
        },
        evidence_ids=("evidence://unicode-éàç#1-5",),
    )
    rel = make_relationship(
        "rel://клиент-accesa-bază",
        "entity://сервис-клиентов",
        "entity://bază-date",
        metadata={
            "transformation_rule_ids": ["правило_трансформации_v1"],
        },
        evidence_ids=("evidence://unicode-éàç#1-5",),
    )
    return ArchitectureDocument(
        architecture_version_id=version_id,
        analysis_id=uuid4(),
        project_id=project_id,
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        configuration_fingerprint="cfg-unicode-v1",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        entities=(e1, e2),
        relationships=(rel,),
        evidence=(ev,),
        unresolved_relationships=(),
        conflicts=(),
        completeness=make_completeness(entities=2, relationships=1, evidence=1),
    )


def maximal_metadata_document(
    project_id: UUID = DEFAULT_PROJECT_ID,
    version_id: UUID = DEFAULT_VERSION_ID,
) -> ArchitectureDocument:
    """Document exercising every allowlisted metadata field."""
    ev = make_evidence()
    e1 = make_entity(
        "entity://full-meta-api",
        name="FullMetadataApi",
        metadata={
            "application_namespace": "backend.api",
            "runtime_role": "http_api",
            "source_root": "apps/api/backend",
            "framework": "fastapi",
            "architectural_role": "gateway",
            "qualified_name": "apps.api.backend.main.app",
            "method": "POST",
            "path": "/api/v2/resources/",
            "handler": "handle_post_resources",
            "mount_path": "/api/v2",
            "declared_path": "/api/v2/resources/{resource_id}",
            "database_engine": "none",
            "external_kind": "internal",
            "unresolved_reason": "none",
            "infrastructure_kind": "container",
            "dependency_name": "uvicorn",
            "identity_anchor": "anchor-api-v2",
            "promotion_rule_id": "rule-promote-v1",
            "manifest_declared": True,
            "source_referenced": True,
            "usage_evidence": True,
            "role_inference_signals": ["fastapi", "dockerfile", "entrypoint"],
            "transformation_rule_ids": ["tf-1", "tf-2"],
        },
    )
    e2 = make_entity(
        "entity://full-meta-worker",
        name="FullMetadataWorker",
        metadata={
            "application_namespace": "backend.worker",
            "runtime_role": "queue_consumer",
            "source_root": "apps/worker",
            "framework": "celery",
            "manifest_declared": False,
            "source_referenced": True,
            "usage_evidence": False,
        },
    )
    rel = make_relationship(
        "rel://api-dispatches-worker",
        "entity://full-meta-api",
        "entity://full-meta-worker",
        metadata={
            "transformation_rule_ids": ["tf-celery-dispatch"],
        },
    )
    return ArchitectureDocument(
        architecture_version_id=version_id,
        analysis_id=uuid4(),
        project_id=project_id,
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        configuration_fingerprint="cfg-max-meta",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        entities=(e1, e2),
        relationships=(rel,),
        evidence=(ev,),
        unresolved_relationships=(),
        conflicts=(),
        completeness=make_completeness(entities=2, relationships=1, evidence=1),
    )


def unresolved_and_conflicts_document(
    project_id: UUID = DEFAULT_PROJECT_ID,
    version_id: UUID = DEFAULT_VERSION_ID,
) -> ArchitectureDocument:
    """Document with resolved relationships, unresolved relationships, and conflicts."""
    ev1 = make_evidence("evidence://file1#1-10")
    ev2 = make_evidence("evidence://file2#20-30")
    e1 = make_entity("entity://source-service", evidence_ids=("evidence://file1#1-10",))
    e2 = make_entity("entity://target-service", evidence_ids=("evidence://file1#1-10",))
    rel = make_relationship(
        "rel://resolved-edge",
        "entity://source-service",
        "entity://target-service",
        evidence_ids=("evidence://file1#1-10",),
    )
    unres = ArchitectureUnresolvedRelationship(
        logical_id="unresolved://source-to-unknown",
        kind=ArchitectureRelationshipKind.CALLS,
        source_logical_id="entity://source-service",
        target_descriptor="external-third-party-api",
        reason=ArchitectureUnresolvedReason.NOT_FOUND,
        status=ArchitectureFactStatus.INFERRED,
        evidence_ids=("evidence://file2#20-30",),
        source_ir_keys=("ir:unres:1",),
        candidate_references=(),
        metadata={},
    )
    conflict = ArchitectureConflict(
        logical_id="conflict://competing-target",
        conflict_type="competing_target",
        subject_key="subject-target-key",
        evidence_ids=("evidence://file2#20-30",),
        details={"rule": "conflict.v1"},
    )
    return ArchitectureDocument(
        architecture_version_id=version_id,
        analysis_id=uuid4(),
        project_id=project_id,
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        configuration_fingerprint="cfg-unres-conflict",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        entities=(e1, e2),
        relationships=(rel,),
        evidence=(ev1, ev2),
        unresolved_relationships=(unres,),
        conflicts=(conflict,),
        completeness=make_completeness(
            entities=2,
            relationships=1,
            evidence=2,
            unresolved=1,
            conflicts=1,
        ),
    )
