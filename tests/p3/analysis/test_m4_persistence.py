"""M4 Batch 3 persistence, publication, rollback, and isolation tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.platform.analysis.architecture.model import (
    ARCHITECTURE_SCHEMA_VERSION,
    ArchitectureCapacityError,
    ArchitectureCompleteness,
    ArchitectureConflict,
    ArchitectureDocument,
    ArchitectureEntity,
    ArchitectureEntityKind,
    ArchitectureEvidence,
    ArchitectureFactStatus,
    ArchitectureRelationship,
    ArchitectureRelationshipKind,
    ArchitectureUnresolvedReason,
    ArchitectureUnresolvedRelationship,
    ValidatedArchitectureModel,
    build_entity_logical_id,
    build_evidence_logical_id,
    build_relationship_logical_id,
    semantic_signature,
)
from backend.platform.analysis.architecture.persistence import (
    ArchitectureConflictModel,
    ArchitectureEntityModel,
    ArchitectureEvidenceModel,
    ArchitectureRelationshipModel,
    ArchitectureUnresolvedRelationshipModel,
    SqlAlchemyArchitectureRepository,
)
from backend.platform.analysis.architecture.repository import (
    ArchitecturePersistenceIntegrityError,
    ArchitectureVersionState,
    ArchitectureVersionStateError,
)
from backend.platform.analysis.architecture.service import (
    ArchitecturePublicationService,
    ArchitectureQueryService,
)
from backend.platform.analysis.architecture.validator import (
    ArchitectureCapacityConfig,
    ArchitectureValidator,
)
from backend.platform.analysis.domain.constants import IR_SCHEMA_VERSION
from backend.platform.analysis.infra.analysis_repository import (
    SqlAlchemyAnalysisRepository,
)
from backend.platform.analysis.infra.lifecycle_model import (
    AnalysisDiagnosticModel,
    AnalysisModel,
)
from backend.platform.config import Settings
from backend.platform.errors import ArchitectureResultNotFoundError
from backend.platform.projects.infra.base import Base


def _analysis(session: Session, document: ArchitectureDocument) -> None:
    now = datetime.now(UTC)
    session.add(
        AnalysisModel(
            id=document.analysis_id,
            project_id=document.project_id,
            repository_id=document.repository_id,
            snapshot_id=document.snapshot_id,
            status="running",
            configuration={},
            completeness=None,
            published_version_id=None,
            error_code=None,
            error_message=None,
            idempotency_key=None,
            version=1,
            created_at=now,
            updated_at=now,
            started_at=now,
            completed_at=None,
        )
    )
    session.commit()


def _document(
    *,
    analysis_id: UUID | None = None,
    project_id: UUID | None = None,
    repository_id: UUID | None = None,
    version_id: UUID | None = None,
) -> ArchitectureDocument:
    analysis_id = analysis_id or uuid4()
    project_id = project_id or uuid4()
    repository_id = repository_id or uuid4()
    snapshot_id = uuid4()
    version_id = version_id or uuid4()
    source_id = build_entity_logical_id(
        project_id=project_id,
        repository_id=repository_id,
        kind=ArchitectureEntityKind.SERVICE,
        namespace_parts=("application", "api"),
        anchor_parts=("service",),
    )
    target_id = build_entity_logical_id(
        project_id=project_id,
        repository_id=repository_id,
        kind=ArchitectureEntityKind.EXTERNAL_API,
        namespace_parts=("external", "payments"),
        anchor_parts=("payments-api",),
    )
    evidence_id = build_evidence_logical_id(snapshot_id, "source:app.py:1")
    relationship_id = build_relationship_logical_id(
        project_id=project_id,
        repository_id=repository_id,
        kind=ArchitectureRelationshipKind.CONNECTS_TO,
        source_logical_id=source_id,
        target_logical_id=target_id,
    )
    unresolved_id = build_relationship_logical_id(
        project_id=project_id,
        repository_id=repository_id,
        kind=ArchitectureRelationshipKind.CONNECTS_TO,
        source_logical_id=source_id,
        target_logical_id=None,
        unresolved_descriptor="dynamic-host",
    )
    entities = (
        ArchitectureEntity(
            logical_id=source_id,
            semantic_signature=semantic_signature({"entity": "service"}),
            kind=ArchitectureEntityKind.SERVICE,
            name="API service",
            namespace=("application", "api"),
            status=ArchitectureFactStatus.CONFIRMED,
            evidence_ids=(evidence_id,),
            source_ir_keys=("service",),
            metadata={"rule_id": "m4.test.service.v1"},
        ),
        ArchitectureEntity(
            logical_id=target_id,
            semantic_signature=semantic_signature({"entity": "payments-api"}),
            kind=ArchitectureEntityKind.EXTERNAL_API,
            name="Payments API",
            namespace=("external", "payments"),
            status=ArchitectureFactStatus.SUPPORTED,
            evidence_ids=(evidence_id,),
            source_ir_keys=("payments-api",),
            metadata={"rule_id": "m4.test.external-api.v1"},
        ),
    )
    return ArchitectureDocument(
        architecture_version_id=version_id,
        analysis_id=analysis_id,
        project_id=project_id,
        repository_id=repository_id,
        snapshot_id=snapshot_id,
        configuration_fingerprint="f" * 64,
        analyzer_version="0.1.0",
        ir_schema_version=IR_SCHEMA_VERSION,
        architecture_schema_version=ARCHITECTURE_SCHEMA_VERSION,
        entities=entities,
        relationships=(
            ArchitectureRelationship(
                logical_id=relationship_id,
                kind=ArchitectureRelationshipKind.CONNECTS_TO,
                source_logical_id=source_id,
                target_logical_id=target_id,
                status=ArchitectureFactStatus.CONFIRMED,
                evidence_ids=(evidence_id,),
                source_ir_keys=("static-reference",),
                metadata={"rule_id": "m4.test.connects-to.v1"},
            ),
        ),
        evidence=(
            ArchitectureEvidence(
                logical_id=evidence_id,
                source_evidence_key="source:app.py:1",
                source_record_type="syntax_fact",
                path="src/app.py",
                source_fact_key="call:payments",
                source_range={"start_line": 1, "start_column": 0},
                producer_id="python-ast",
                producer_version="3.14",
                metadata={"fact_kind": "call"},
            ),
        ),
        unresolved_relationships=(
            ArchitectureUnresolvedRelationship(
                logical_id=unresolved_id,
                kind=ArchitectureRelationshipKind.CONNECTS_TO,
                source_logical_id=source_id,
                target_descriptor="dynamic-host",
                reason=ArchitectureUnresolvedReason.DYNAMIC,
                status=ArchitectureFactStatus.UNRESOLVED,
                evidence_ids=(evidence_id,),
                source_ir_keys=("dynamic-reference",),
                candidate_references=("configured-host",),
                metadata={"rule_id": "m4.test.dynamic.v1"},
            ),
        ),
        conflicts=(
            ArchitectureConflict(
                logical_id="conflict://payments-target",
                conflict_type="competing_target",
                subject_key="payments-target",
                evidence_ids=(evidence_id,),
                details={"rule_id": "m4.test.conflict.v1"},
            ),
        ),
        completeness=ArchitectureCompleteness(
            total_inventory_artifacts=1,
            analyzed_artifacts=1,
            failed_artifacts=0,
            total_syntax_documents=1,
            total_syntax_facts=4,
            source_entities=2,
            source_relationships=1,
            source_unresolved_references=1,
            source_conflicts=1,
            architecture_entities=2,
            architecture_relationships=1,
            architecture_unresolved_relationships=1,
            architecture_conflicts=1,
            is_partial=False,
        ),
    )


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value
    engine.dispose()


def _service(
    session: Session,
) -> tuple[SqlAlchemyArchitectureRepository, ArchitecturePublicationService]:
    repository = SqlAlchemyArchitectureRepository(session)
    return repository, ArchitecturePublicationService(
        repository,
        validator=ArchitectureValidator(ArchitectureCapacityConfig()),
        publication_linker=SqlAlchemyAnalysisRepository(session),
        checkpoint=session.commit,
        rollback=session.rollback,
    )


def _validated(document: ArchitectureDocument) -> ValidatedArchitectureModel:
    return ArchitectureValidator(ArchitectureCapacityConfig()).validate(document)


def test_production_settings_expose_owner_approved_capacity_defaults() -> None:
    settings = Settings()
    capacity = ArchitectureCapacityConfig.from_settings(settings)

    assert settings.architecture_max_entities == 25_000
    assert settings.architecture_max_relationships == 50_000
    assert settings.architecture_max_evidence == 75_000
    assert settings.architecture_max_unresolved_relationships == 10_000
    assert settings.architecture_max_conflicts == 5_000
    assert settings.architecture_max_serialized_bytes == 128 * 1024 * 1024
    assert capacity == ArchitectureCapacityConfig()


def test_architecture_tables_are_registered_with_shared_metadata() -> None:
    expected = {
        "architecture_versions",
        "architecture_entities",
        "architecture_relationships",
        "architecture_evidence",
        "architecture_unresolved_relationships",
        "architecture_conflicts",
        "architecture_entity_evidence",
        "architecture_relationship_evidence",
        "architecture_unresolved_evidence",
        "architecture_conflict_evidence",
    }

    assert expected <= set(Base.metadata.tables)


def test_publication_round_trip_is_complete_idempotent_and_project_scoped(
    session: Session,
) -> None:
    document = _document()
    _analysis(session, document)
    repository, service = _service(session)

    building = service.reserve_candidate(document)
    assert building.state is ArchitectureVersionState.BUILDING
    validating = service.begin_validation(
        document.architecture_version_id, document.analysis_id
    )
    assert validating.state is ArchitectureVersionState.VALIDATING
    published = service.publish(_validated(document))
    assert published.state is ArchitectureVersionState.PUBLISHED
    assert published.sequence_number == 1
    linked_analysis = session.get(AnalysisModel, document.analysis_id)
    assert linked_analysis is not None
    assert linked_analysis.published_version_id == document.architecture_version_id

    replay = service.publish(_validated(document))
    assert replay == published
    restored = repository.load_published_document(
        document.architecture_version_id, document.project_id
    )
    assert restored is not None
    assert restored.to_canonical_json() == document.to_canonical_json()
    assert (
        repository.load_published_document(document.architecture_version_id, uuid4())
        is None
    )
    assert repository.get_published_for_analysis(document.analysis_id, uuid4()) is None
    history = repository.list_latest_identities(
        document.project_id, document.repository_id
    )
    assert tuple(item.logical_id for item in history) == tuple(
        item.logical_id for item in document.entities
    )
    assert repository.list_latest_identities(uuid4(), document.repository_id) == ()


def test_publication_failure_rolls_back_every_child_and_leaves_validating_header(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _document()
    _analysis(session, document)
    repository, service = _service(session)
    service.reserve_candidate(document)
    service.begin_validation(document.architecture_version_id, document.analysis_id)

    def fail_after_inserts(*_args: object) -> None:
        raise RuntimeError("injected publication failure")

    monkeypatch.setattr(repository, "_verify_counts", fail_after_inserts)
    with pytest.raises(RuntimeError, match="injected publication failure"):
        service.publish(_validated(document))

    header = repository.get_version(
        document.architecture_version_id, document.project_id
    )
    assert header is not None
    assert header.state is ArchitectureVersionState.VALIDATING
    for model_type in (
        ArchitectureEntityModel,
        ArchitectureRelationshipModel,
        ArchitectureEvidenceModel,
        ArchitectureUnresolvedRelationshipModel,
        ArchitectureConflictModel,
    ):
        assert session.scalar(select(func.count()).select_from(model_type)) == 0
    assert (
        repository.load_published_document(
            document.architecture_version_id, document.project_id
        )
        is None
    )


def test_publication_link_failure_rolls_back_model_and_analysis_pointer(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _document()
    _analysis(session, document)
    repository, service = _service(session)
    service.reserve_candidate(document)
    service.begin_validation(document.architecture_version_id, document.analysis_id)

    def reject_link(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected pointer-link failure")

    monkeypatch.setattr(
        service._publication_linker, "link_published_version", reject_link
    )
    with pytest.raises(RuntimeError, match="pointer-link failure"):
        service.publish(_validated(document))

    header = repository.get_version(
        document.architecture_version_id, document.project_id
    )
    analysis = session.get(AnalysisModel, document.analysis_id)
    assert header is not None
    assert header.state is ArchitectureVersionState.VALIDATING
    assert analysis is not None
    assert analysis.published_version_id is None
    assert (
        session.scalar(select(func.count()).select_from(ArchitectureEntityModel)) == 0
    )


def test_query_service_exposes_only_published_project_scoped_paginated_results(
    session: Session,
) -> None:
    document = _document()
    _analysis(session, document)
    repository, publication = _service(session)
    publication.reserve_candidate(document)

    query = ArchitectureQueryService(repository)
    with pytest.raises(
        ArchitectureResultNotFoundError, match="Published Architecture Model not found"
    ):
        query.get_version(document.architecture_version_id, document.project_id)

    publication.begin_validation(document.architecture_version_id, document.analysis_id)
    publication.publish(_validated(document))

    def fail_full_rehydration(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("paged query must not load the complete model")

    repository.load_published_document = fail_full_rehydration  # type: ignore[method-assign,assignment]

    version = query.get_for_analysis(document.analysis_id, document.project_id)
    assert version.id == document.architecture_version_id
    assert version.entity_count == 2
    first_page = query.list_entities(version.id, document.project_id, limit=1, offset=0)
    second_page = query.list_entities(
        version.id, document.project_id, limit=1, offset=1
    )
    assert first_page.total == 2
    assert len(first_page.items) == 1
    assert len(second_page.items) == 1
    assert first_page.items[0].id != second_page.items[0].id
    with pytest.raises(
        ArchitectureResultNotFoundError, match="Published Architecture Model not found"
    ):
        query.get_version(version.id, uuid4())


def test_publication_revalidates_capacity_and_never_partially_persists(
    session: Session,
) -> None:
    document = _document()
    _analysis(session, document)
    repository = SqlAlchemyArchitectureRepository(session)
    service = ArchitecturePublicationService(
        repository,
        validator=ArchitectureValidator(ArchitectureCapacityConfig(max_entities=1)),
        publication_linker=SqlAlchemyAnalysisRepository(session),
        checkpoint=session.commit,
        rollback=session.rollback,
    )
    service.reserve_candidate(document)
    service.begin_validation(document.architecture_version_id, document.analysis_id)

    with pytest.raises(
        ArchitectureCapacityError,
        match="architecture capacity exceeded: entities=2, limit=1",
    ):
        service.publish(ValidatedArchitectureModel(document))

    header = repository.get_version(
        document.architecture_version_id, document.project_id
    )
    assert header is not None
    assert header.state is ArchitectureVersionState.VALIDATING
    assert (
        session.scalar(select(func.count()).select_from(ArchitectureEntityModel)) == 0
    )


def test_validation_failure_is_terminal_auditable_and_has_no_model_rows(
    session: Session,
) -> None:
    document = _document()
    _analysis(session, document)
    repository, service = _service(session)
    service.reserve_candidate(document)
    service.begin_validation(document.architecture_version_id, document.analysis_id)
    diagnostic_id = uuid4()
    session.add(
        AnalysisDiagnosticModel(
            id=diagnostic_id,
            analysis_id=document.analysis_id,
            job_id=None,
            stage="architecture_builder",
            code="ARCHITECTURE_VALIDATION_FAILED",
            category="validation",
            severity="error",
            scope="stage",
            message="Architecture candidate failed deterministic validation.",
            retryability="non_retryable",
            details={},
            artifact_id=None,
            artifact_path=None,
            source_line=None,
            source_column=None,
            created_at=datetime.now(UTC),
        )
    )
    session.commit()

    failed = service.record_validation_failure(
        document.architecture_version_id,
        document.analysis_id,
        diagnostic_id=diagnostic_id,
        failure_code="architecture_validation_failed",
    )
    assert failed.state is ArchitectureVersionState.VALIDATION_FAILED
    assert failed.diagnostic_id == diagnostic_id
    assert (
        repository.load_published_document(
            document.architecture_version_id, document.project_id
        )
        is None
    )
    with pytest.raises(ArchitectureVersionStateError):
        service.publish(_validated(document))


def test_validation_failure_rejects_unsafe_failure_code(session: Session) -> None:
    document = _document()
    _analysis(session, document)
    _, service = _service(session)
    service.reserve_candidate(document)
    service.begin_validation(document.architecture_version_id, document.analysis_id)

    with pytest.raises(
        ArchitecturePersistenceIntegrityError,
        match="safe canonical identifier",
    ):
        service.record_validation_failure(
            document.architecture_version_id,
            document.analysis_id,
            diagnostic_id=uuid4(),
            failure_code="secret token=do-not-store",
        )


def test_same_analysis_with_different_content_fails_closed(session: Session) -> None:
    document = _document()
    _analysis(session, document)
    _, service = _service(session)
    service.reserve_candidate(document)
    changed_entity = replace(document.entities[0], name="Changed service")
    conflicting = replace(
        document,
        entities=(changed_entity, document.entities[1]),
        content_digest="",
    )

    with pytest.raises(ArchitecturePersistenceIntegrityError):
        service.reserve_candidate(conflicting)


def test_repository_sequence_is_monotonic_per_repository(session: Session) -> None:
    repository_id = uuid4()
    first = _document(repository_id=repository_id)
    second = _document(repository_id=repository_id)
    _analysis(session, first)
    _analysis(session, second)
    _, service = _service(session)

    assert service.reserve_candidate(first).sequence_number == 1
    assert service.reserve_candidate(second).sequence_number == 2


def test_repository_exposes_no_mutation_api_for_published_models(
    session: Session,
) -> None:
    repository, _ = _service(session)

    assert not hasattr(repository, "update_published")
    assert not hasattr(repository, "delete_version")
