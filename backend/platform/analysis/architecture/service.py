"""Application coordination for durable Architecture Version publication."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from uuid import UUID

from backend.platform.analysis.architecture.dto import (
    ArchitectureCollectionResponse,
    ArchitectureConflictResponse,
    ArchitectureEntityResponse,
    ArchitectureEvidenceResponse,
    ArchitectureRelationshipResponse,
    ArchitectureUnresolvedResponse,
    ArchitectureVersionResponse,
)
from backend.platform.analysis.architecture.model import (
    ArchitectureDocument,
    ValidatedArchitectureModel,
)
from backend.platform.analysis.architecture.persistence import architecture_resource_id
from backend.platform.analysis.architecture.repository import (
    ArchitecturePublicationRepository,
    ArchitectureVersionRecord,
    ArchitectureVersionState,
)
from backend.platform.analysis.architecture.validator import ArchitectureValidator
from backend.platform.analysis.repositories.analysis_repo import (
    AnalysisPublicationLinker,
)
from backend.platform.errors import ArchitectureResultNotFoundError

ArchitectureItemResponse = (
    ArchitectureEntityResponse
    | ArchitectureRelationshipResponse
    | ArchitectureEvidenceResponse
    | ArchitectureUnresolvedResponse
    | ArchitectureConflictResponse
)


class ArchitecturePublicationService:
    """Enforce the approved commit boundaries around Architecture persistence."""

    def __init__(
        self,
        repository: ArchitecturePublicationRepository,
        *,
        validator: ArchitectureValidator,
        publication_linker: AnalysisPublicationLinker,
        checkpoint: Callable[[], None],
        rollback: Callable[[], None],
    ) -> None:
        self._repository = repository
        self._validator = validator
        self._publication_linker = publication_linker
        self._checkpoint = checkpoint
        self._rollback = rollback

    def reserve_candidate(
        self, document: ArchitectureDocument
    ) -> ArchitectureVersionRecord:
        """Durably reserve the BUILDING header before publication work."""
        try:
            record = self._repository.reserve_version(document)
            self._checkpoint()
            return record
        except Exception:
            self._rollback()
            raise

    def begin_validation(
        self, version_id: UUID, analysis_id: UUID
    ) -> ArchitectureVersionRecord:
        """Durably transition the header to VALIDATING."""
        try:
            record = self._repository.mark_validating(version_id, analysis_id)
            self._checkpoint()
            return record
        except Exception:
            self._rollback()
            raise

    def record_validation_failure(
        self,
        version_id: UUID,
        analysis_id: UUID,
        *,
        diagnostic_id: UUID,
        failure_code: str,
    ) -> ArchitectureVersionRecord:
        """Finalize failure after the diagnostic was independently checkpointed."""
        try:
            record = self._repository.mark_validation_failed(
                version_id,
                analysis_id,
                diagnostic_id=diagnostic_id,
                failure_code=failure_code,
            )
            self._checkpoint()
            return record
        except Exception:
            self._rollback()
            raise

    def publish(
        self, validated: ValidatedArchitectureModel
    ) -> ArchitectureVersionRecord:
        """Publish all canonical rows in one transaction or expose none of them."""
        try:
            verified = self._validator.validate(validated.document)
            record = self._repository.publish(verified)
            self._publication_linker.link_published_version(
                record.analysis_id,
                record.project_id,
                record.id,
            )
            self._checkpoint()
            return record
        except Exception:
            self._rollback()
            raise


class ArchitectureQueryService:
    """Project-scoped read service exposing published Architecture Models only."""

    def __init__(self, repository: ArchitecturePublicationRepository) -> None:
        self._repository = repository

    def get_for_analysis(
        self, analysis_id: UUID, project_id: UUID
    ) -> ArchitectureVersionResponse:
        record = self._repository.get_published_for_analysis(analysis_id, project_id)
        if record is None:
            raise ArchitectureResultNotFoundError(
                details={"analysis_id": str(analysis_id)}
            )
        return _version_response(record)

    def get_version(
        self, version_id: UUID, project_id: UUID
    ) -> ArchitectureVersionResponse:
        record = self._repository.get_version(version_id, project_id)
        if record is None or record.state is not ArchitectureVersionState.PUBLISHED:
            raise ArchitectureResultNotFoundError(
                details={"architecture_version_id": str(version_id)}
            )
        return _version_response(record)

    def list_entities(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        kind: str | None = None,
        status: str | None = None,
    ) -> ArchitectureCollectionResponse:
        page = self._repository.list_published_entities(
            version_id,
            project_id,
            limit=limit,
            offset=offset,
            kind=kind,
            status=status,
        )
        self._require_page_version(version_id, project_id)
        items = [
            ArchitectureEntityResponse(
                id=architecture_resource_id(version_id, "entity", item.logical_id),
                logical_id=item.logical_id,
                kind=item.kind.value,
                name=item.name,
                namespace=item.namespace,
                status=item.status.value,
                evidence_ids=item.evidence_ids,
                source_ir_keys=item.source_ir_keys,
                metadata=dict(item.metadata),
            )
            for item in page.items
        ]
        return _collection(items, page.total, limit, offset)

    def get_entity(
        self, version_id: UUID, entity_id: UUID, project_id: UUID
    ) -> ArchitectureEntityResponse:
        item = self._repository.get_published_entity(version_id, entity_id, project_id)
        if item is None:
            raise ArchitectureResultNotFoundError(details={"entity_id": str(entity_id)})
        return ArchitectureEntityResponse(
            id=architecture_resource_id(version_id, "entity", item.logical_id),
            logical_id=item.logical_id,
            kind=item.kind.value,
            name=item.name,
            namespace=item.namespace,
            status=item.status.value,
            evidence_ids=item.evidence_ids,
            source_ir_keys=item.source_ir_keys,
            metadata=dict(item.metadata),
        )

    def list_relationships(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        kind: str | None = None,
        status: str | None = None,
    ) -> ArchitectureCollectionResponse:
        page = self._repository.list_published_relationships(
            version_id,
            project_id,
            limit=limit,
            offset=offset,
            kind=kind,
            status=status,
        )
        self._require_page_version(version_id, project_id)
        items = [
            ArchitectureRelationshipResponse(
                id=architecture_resource_id(
                    version_id, "relationship", item.logical_id
                ),
                logical_id=item.logical_id,
                kind=item.kind.value,
                source_logical_id=item.source_logical_id,
                target_logical_id=item.target_logical_id,
                status=item.status.value,
                evidence_ids=item.evidence_ids,
                source_ir_keys=item.source_ir_keys,
                metadata=dict(item.metadata),
            )
            for item in page.items
        ]
        return _collection(items, page.total, limit, offset)

    def list_evidence(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> ArchitectureCollectionResponse:
        page = self._repository.list_published_evidence(
            version_id, project_id, limit=limit, offset=offset
        )
        self._require_page_version(version_id, project_id)
        items = [
            ArchitectureEvidenceResponse(
                id=architecture_resource_id(version_id, "evidence", item.logical_id),
                logical_id=item.logical_id,
                source_record_type=item.source_record_type,
                path=item.path,
                artifact_id=item.artifact_id,
                source_fact_key=item.source_fact_key,
                source_range=(
                    None if item.source_range is None else dict(item.source_range)
                ),
                producer_id=item.producer_id,
                producer_version=item.producer_version,
                strength=item.strength.value,
                polarity=item.polarity.value,
                metadata=dict(item.metadata),
            )
            for item in page.items
        ]
        return _collection(items, page.total, limit, offset)

    def list_unresolved(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> ArchitectureCollectionResponse:
        page = self._repository.list_published_unresolved(
            version_id, project_id, limit=limit, offset=offset
        )
        self._require_page_version(version_id, project_id)
        items = [
            ArchitectureUnresolvedResponse(
                id=architecture_resource_id(version_id, "unresolved", item.logical_id),
                logical_id=item.logical_id,
                kind=item.kind.value,
                source_logical_id=item.source_logical_id,
                target_descriptor=item.target_descriptor,
                reason=item.reason.value,
                status=item.status.value,
                evidence_ids=item.evidence_ids,
                candidate_references=item.candidate_references,
                metadata=dict(item.metadata),
            )
            for item in page.items
        ]
        return _collection(items, page.total, limit, offset)

    def list_conflicts(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> ArchitectureCollectionResponse:
        page = self._repository.list_published_conflicts(
            version_id, project_id, limit=limit, offset=offset
        )
        self._require_page_version(version_id, project_id)
        items = [
            ArchitectureConflictResponse(
                id=architecture_resource_id(version_id, "conflict", item.logical_id),
                logical_id=item.logical_id,
                conflict_type=item.conflict_type,
                subject_key=item.subject_key,
                evidence_ids=item.evidence_ids,
                details=dict(item.details),
            )
            for item in page.items
        ]
        return _collection(items, page.total, limit, offset)

    def _require_page_version(self, version_id: UUID, project_id: UUID) -> None:
        record = self._repository.get_version(version_id, project_id)
        if record is None or record.state is not ArchitectureVersionState.PUBLISHED:
            raise ArchitectureResultNotFoundError(
                details={"architecture_version_id": str(version_id)}
            )


def _version_response(record: ArchitectureVersionRecord) -> ArchitectureVersionResponse:
    if record.published_at is None:
        raise ArchitectureResultNotFoundError()
    return ArchitectureVersionResponse(
        id=record.id,
        analysis_id=record.analysis_id,
        project_id=record.project_id,
        repository_id=record.repository_id,
        snapshot_id=record.snapshot_id,
        sequence_number=record.sequence_number,
        architecture_schema_version=record.architecture_schema_version,
        ir_schema_version=record.ir_schema_version,
        content_digest=record.content_digest,
        entity_count=record.entity_count,
        relationship_count=record.relationship_count,
        evidence_count=record.evidence_count,
        unresolved_relationship_count=record.unresolved_relationship_count,
        conflict_count=record.conflict_count,
        completeness=record.completeness,
        published_at=record.published_at,
    )


def _collection(
    items: Sequence[ArchitectureItemResponse], total: int, limit: int, offset: int
) -> ArchitectureCollectionResponse:
    return ArchitectureCollectionResponse(
        items=list(items), total=total, limit=limit, offset=offset
    )


__all__ = ["ArchitecturePublicationService", "ArchitectureQueryService"]
