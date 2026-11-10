"""SQLAlchemy persistence and atomic publication for Architecture Model v1."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.platform.analysis.architecture.identity import HistoricalIdentityRecord
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
    ValidatedArchitectureModel,
)
from backend.platform.analysis.architecture.repository import (
    ArchitecturePage,
    ArchitecturePersistenceIntegrityError,
    ArchitecturePublicationRepository,
    ArchitectureVersionRecord,
    ArchitectureVersionState,
    ArchitectureVersionStateError,
)
from backend.platform.projects.infra.base import Base


class ArchitectureVersionModel(Base):
    """Durable internal header for one immutable Architecture Version."""

    __tablename__ = "architecture_versions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    repository_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    snapshot_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    configuration_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    analyzer_version: Mapped[str] = mapped_column(String(64), nullable=False)
    ir_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    architecture_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    completeness: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_diagnostic_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    entity_count: Mapped[int] = mapped_column(Integer, nullable=False)
    relationship_count: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unresolved_relationship_count: Mapped[int] = mapped_column(Integer, nullable=False)
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False)
    diagnostic_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("analysis_diagnostics.id", ondelete="SET NULL"),
        nullable=True,
    )
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("analysis_id", name="uq_architecture_versions_analysis"),
        UniqueConstraint(
            "repository_id",
            "sequence_number",
            name="uq_architecture_versions_repository_sequence",
        ),
        CheckConstraint(
            "state IN ('building', 'validating', 'validation_failed', 'published')",
            name="ck_architecture_versions_state",
        ),
        CheckConstraint(
            "sequence_number > 0", name="ck_architecture_versions_sequence_positive"
        ),
        CheckConstraint(
            "entity_count >= 0 AND relationship_count >= 0 "
            "AND evidence_count >= 0 AND unresolved_relationship_count >= 0 "
            "AND conflict_count >= 0",
            name="ck_architecture_versions_counts_nonnegative",
        ),
        Index(
            "ix_architecture_versions_project_repository_sequence",
            "project_id",
            "repository_id",
            "sequence_number",
        ),
        Index(
            "ix_architecture_versions_project_state",
            "project_id",
            "state",
        ),
    )


class ArchitectureEvidenceModel(Base):
    __tablename__ = "architecture_evidence"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    logical_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_evidence_key: Mapped[str] = mapped_column(Text, nullable=False)
    source_record_type: Mapped[str] = mapped_column(String(100), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    source_fact_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_range: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    producer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    producer_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    strength: Mapped[str] = mapped_column(String(64), nullable=False)
    polarity: Mapped[str] = mapped_column(String(32), nullable=False)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "version_id", "logical_id", name="uq_architecture_evidence_logical"
        ),
        Index("ix_architecture_evidence_version", "version_id"),
    )


class ArchitectureEntityModel(Base):
    __tablename__ = "architecture_entities"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    logical_id: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    namespace: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ir_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "version_id", "logical_id", name="uq_architecture_entities_logical"
        ),
        Index("ix_architecture_entities_version_kind", "version_id", "kind"),
    )


class ArchitectureRelationshipModel(Base):
    __tablename__ = "architecture_relationships"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    logical_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source_entity_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_entity_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ir_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "version_id", "logical_id", name="uq_architecture_relationships_logical"
        ),
        Index("ix_architecture_relationships_version_kind", "version_id", "kind"),
        Index("ix_architecture_relationships_source", "version_id", "source_entity_id"),
        Index("ix_architecture_relationships_target", "version_id", "target_entity_id"),
    )


class ArchitectureUnresolvedRelationshipModel(Base):
    __tablename__ = "architecture_unresolved_relationships"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    logical_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source_entity_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_descriptor: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ir_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    candidate_references: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "version_id",
            "logical_id",
            name="uq_architecture_unresolved_logical",
        ),
        Index("ix_architecture_unresolved_version", "version_id"),
    )


class ArchitectureConflictModel(Base):
    __tablename__ = "architecture_conflicts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    logical_id: Mapped[str] = mapped_column(Text, nullable=False)
    conflict_type: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_key: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "version_id", "logical_id", name="uq_architecture_conflicts_logical"
        ),
        Index("ix_architecture_conflicts_version", "version_id"),
    )


class ArchitectureEntityEvidenceModel(Base):
    __tablename__ = "architecture_entity_evidence"

    entity_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    evidence_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_evidence.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ArchitectureRelationshipEvidenceModel(Base):
    __tablename__ = "architecture_relationship_evidence"

    relationship_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_relationships.id", ondelete="CASCADE"),
        primary_key=True,
    )
    evidence_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_evidence.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ArchitectureUnresolvedEvidenceModel(Base):
    __tablename__ = "architecture_unresolved_evidence"

    unresolved_relationship_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_unresolved_relationships.id", ondelete="CASCADE"),
        primary_key=True,
    )
    evidence_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_evidence.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ArchitectureConflictEvidenceModel(Base):
    __tablename__ = "architecture_conflict_evidence"

    conflict_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_conflicts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    evidence_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("architecture_evidence.id", ondelete="CASCADE"),
        primary_key=True,
    )


class SqlAlchemyArchitectureRepository(ArchitecturePublicationRepository):
    """SQLAlchemy adapter; its caller owns commits and rollbacks."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def reserve_version(
        self, document: ArchitectureDocument
    ) -> ArchitectureVersionRecord:
        existing = self._get_by_analysis(document.analysis_id, lock=True)
        if existing is not None:
            self._assert_same_content(existing, document)
            return self._to_record(existing)

        self._lock_repository_sequence(document.repository_id)
        sequence = self._next_sequence(document.repository_id)
        now = datetime.now(UTC)
        model = ArchitectureVersionModel(
            id=document.architecture_version_id,
            analysis_id=document.analysis_id,
            project_id=document.project_id,
            repository_id=document.repository_id,
            snapshot_id=document.snapshot_id,
            sequence_number=sequence,
            state=ArchitectureVersionState.BUILDING.value,
            configuration_fingerprint=document.configuration_fingerprint,
            analyzer_version=document.analyzer_version,
            ir_schema_version=document.ir_schema_version,
            architecture_schema_version=document.architecture_schema_version,
            content_digest=document.content_digest,
            completeness=document.to_dict()["completeness"],
            source_diagnostic_ids=list(document.source_diagnostic_ids),
            entity_count=len(document.entities),
            relationship_count=len(document.relationships),
            evidence_count=len(document.evidence),
            unresolved_relationship_count=len(document.unresolved_relationships),
            conflict_count=len(document.conflicts),
            diagnostic_id=None,
            failure_code=None,
            created_at=now,
            updated_at=now,
            published_at=None,
        )
        try:
            with self._session.begin_nested():
                self._session.add(model)
                self._session.flush()
        except IntegrityError:
            existing = self._get_by_analysis(document.analysis_id, lock=True)
            if existing is None:
                raise
            self._assert_same_content(existing, document)
            return self._to_record(existing)
        return self._to_record(model)

    def mark_validating(
        self, version_id: UUID, analysis_id: UUID
    ) -> ArchitectureVersionRecord:
        model = self._required_header(version_id, analysis_id, lock=True)
        state = ArchitectureVersionState(model.state)
        if state is ArchitectureVersionState.BUILDING:
            model.state = ArchitectureVersionState.VALIDATING.value
            model.updated_at = datetime.now(UTC)
            self._session.flush()
        elif state not in {
            ArchitectureVersionState.VALIDATING,
            ArchitectureVersionState.PUBLISHED,
        }:
            raise ArchitectureVersionStateError(
                f"cannot validate Architecture Version in state {state.value}"
            )
        return self._to_record(model)

    def mark_validation_failed(
        self,
        version_id: UUID,
        analysis_id: UUID,
        *,
        diagnostic_id: UUID,
        failure_code: str,
    ) -> ArchitectureVersionRecord:
        if re.fullmatch(r"[a-z][a-z0-9_]{0,99}", failure_code) is None:
            raise ArchitecturePersistenceIntegrityError(
                "validation failure code must be a safe canonical identifier"
            )
        model = self._required_header(version_id, analysis_id, lock=True)
        state = ArchitectureVersionState(model.state)
        if state is ArchitectureVersionState.VALIDATION_FAILED:
            if (
                model.diagnostic_id != diagnostic_id
                or model.failure_code != failure_code
            ):
                raise ArchitecturePersistenceIntegrityError(
                    "validation-failure retry conflicts with durable failure metadata"
                )
            return self._to_record(model)
        if state not in {
            ArchitectureVersionState.BUILDING,
            ArchitectureVersionState.VALIDATING,
        }:
            raise ArchitectureVersionStateError(
                f"cannot fail Architecture Version in state {state.value}"
            )
        if self._child_count(version_id) != 0:
            raise ArchitecturePersistenceIntegrityError(
                "validation-failed Architecture Version must not retain child rows"
            )
        model.state = ArchitectureVersionState.VALIDATION_FAILED.value
        model.diagnostic_id = diagnostic_id
        model.failure_code = failure_code
        model.updated_at = datetime.now(UTC)
        self._session.flush()
        return self._to_record(model)

    def publish(
        self, validated: ValidatedArchitectureModel
    ) -> ArchitectureVersionRecord:
        document = validated.document
        model = self._required_header(
            document.architecture_version_id,
            document.analysis_id,
            lock=True,
        )
        self._assert_same_content(model, document)
        state = ArchitectureVersionState(model.state)
        if state is ArchitectureVersionState.PUBLISHED:
            return self._to_record(model)
        if state is not ArchitectureVersionState.VALIDATING:
            raise ArchitectureVersionStateError(
                f"cannot publish Architecture Version in state {state.value}"
            )
        if self._child_count(model.id) != 0:
            raise ArchitecturePersistenceIntegrityError(
                "unpublished Architecture Version already contains child rows"
            )

        self._insert_document(document)
        self._session.flush()
        self._verify_counts(model, document)
        rehydrated = self._load_document(model)
        if rehydrated.content_digest != document.content_digest:
            raise ArchitecturePersistenceIntegrityError(
                "persisted Architecture Model digest does not match validated content"
            )
        now = datetime.now(UTC)
        model.state = ArchitectureVersionState.PUBLISHED.value
        model.updated_at = now
        model.published_at = now
        self._session.flush()
        return self._to_record(model)

    def get_version(
        self, version_id: UUID, project_id: UUID
    ) -> ArchitectureVersionRecord | None:
        model = self._session.scalar(
            select(ArchitectureVersionModel).where(
                ArchitectureVersionModel.id == version_id,
                ArchitectureVersionModel.project_id == project_id,
            )
        )
        return None if model is None else self._to_record(model)

    def get_published_for_analysis(
        self, analysis_id: UUID, project_id: UUID
    ) -> ArchitectureVersionRecord | None:
        model = self._session.scalar(
            select(ArchitectureVersionModel).where(
                ArchitectureVersionModel.analysis_id == analysis_id,
                ArchitectureVersionModel.project_id == project_id,
                ArchitectureVersionModel.state
                == ArchitectureVersionState.PUBLISHED.value,
            )
        )
        return None if model is None else self._to_record(model)

    def load_published_document(
        self, version_id: UUID, project_id: UUID
    ) -> ArchitectureDocument | None:
        model = self._session.scalar(
            select(ArchitectureVersionModel).where(
                ArchitectureVersionModel.id == version_id,
                ArchitectureVersionModel.project_id == project_id,
                ArchitectureVersionModel.state
                == ArchitectureVersionState.PUBLISHED.value,
            )
        )
        return None if model is None else self._load_document(model)

    def list_published_entities(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        kind: str | None = None,
        status: str | None = None,
    ) -> ArchitecturePage[ArchitectureEntity]:
        if not self._is_published(version_id, project_id):
            return ArchitecturePage((), 0)
        filters = [ArchitectureEntityModel.version_id == version_id]
        if kind is not None:
            filters.append(ArchitectureEntityModel.kind == kind)
        if status is not None:
            filters.append(ArchitectureEntityModel.status == status)
        total = int(
            self._session.scalar(
                select(func.count())
                .select_from(ArchitectureEntityModel)
                .where(*filters)
            )
            or 0
        )
        models = tuple(
            self._session.scalars(
                select(ArchitectureEntityModel)
                .where(*filters)
                .order_by(ArchitectureEntityModel.logical_id)
                .offset(offset)
                .limit(limit)
            )
        )
        associations = self._association_logical_map(
            ArchitectureEntityEvidenceModel.entity_id,
            ArchitectureEntityEvidenceModel.evidence_id,
            tuple(item.id for item in models),
        )
        return ArchitecturePage(
            tuple(self._entity(item, associations.get(item.id, ())) for item in models),
            total,
        )

    def get_published_entity(
        self, version_id: UUID, entity_id: UUID, project_id: UUID
    ) -> ArchitectureEntity | None:
        if not self._is_published(version_id, project_id):
            return None
        model = self._session.scalar(
            select(ArchitectureEntityModel).where(
                ArchitectureEntityModel.id == entity_id,
                ArchitectureEntityModel.version_id == version_id,
            )
        )
        if model is None:
            return None
        associations = self._association_logical_map(
            ArchitectureEntityEvidenceModel.entity_id,
            ArchitectureEntityEvidenceModel.evidence_id,
            (model.id,),
        )
        return self._entity(model, associations.get(model.id, ()))

    def list_published_relationships(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        kind: str | None = None,
        status: str | None = None,
    ) -> ArchitecturePage[ArchitectureRelationship]:
        if not self._is_published(version_id, project_id):
            return ArchitecturePage((), 0)
        filters = [ArchitectureRelationshipModel.version_id == version_id]
        if kind is not None:
            filters.append(ArchitectureRelationshipModel.kind == kind)
        if status is not None:
            filters.append(ArchitectureRelationshipModel.status == status)
        total = int(
            self._session.scalar(
                select(func.count())
                .select_from(ArchitectureRelationshipModel)
                .where(*filters)
            )
            or 0
        )
        models = tuple(
            self._session.scalars(
                select(ArchitectureRelationshipModel)
                .where(*filters)
                .order_by(ArchitectureRelationshipModel.logical_id)
                .offset(offset)
                .limit(limit)
            )
        )
        entity_ids = tuple(
            {
                entity_id
                for item in models
                for entity_id in (item.source_entity_id, item.target_entity_id)
            }
        )
        logical_by_id: dict[UUID, str] = (
            {
                entity_id: logical_id
                for entity_id, logical_id in self._session.execute(
                    select(
                        ArchitectureEntityModel.id, ArchitectureEntityModel.logical_id
                    ).where(ArchitectureEntityModel.id.in_(entity_ids))
                ).all()
            }
            if entity_ids
            else {}
        )
        associations = self._association_logical_map(
            ArchitectureRelationshipEvidenceModel.relationship_id,
            ArchitectureRelationshipEvidenceModel.evidence_id,
            tuple(item.id for item in models),
        )
        return ArchitecturePage(
            tuple(
                self._relationship(
                    item,
                    logical_by_id,
                    associations.get(item.id, ()),
                )
                for item in models
            ),
            total,
        )

    def list_published_evidence(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        entity_id: UUID | None = None,
    ) -> ArchitecturePage[ArchitectureEvidence]:
        if not self._is_published(version_id, project_id):
            return ArchitecturePage((), 0)
        if entity_id is None:
            total, models = self._paged_models(
                ArchitectureEvidenceModel, version_id, limit, offset
            )
            return ArchitecturePage(
                tuple(self._evidence(item) for item in models), total
            )

        evidence_subq = select(ArchitectureEntityEvidenceModel.evidence_id).where(
            ArchitectureEntityEvidenceModel.entity_id == entity_id
        )
        filters = [
            ArchitectureEvidenceModel.version_id == version_id,
            ArchitectureEvidenceModel.id.in_(evidence_subq),
        ]
        total = int(
            self._session.scalar(
                select(func.count())
                .select_from(ArchitectureEvidenceModel)
                .where(*filters)
            )
            or 0
        )
        models = tuple(
            self._session.scalars(
                select(ArchitectureEvidenceModel)
                .where(*filters)
                .order_by(ArchitectureEvidenceModel.logical_id)
                .offset(offset)
                .limit(limit)
            )
        )
        return ArchitecturePage(tuple(self._evidence(item) for item in models), total)

    def list_published_unresolved(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> ArchitecturePage[ArchitectureUnresolvedRelationship]:
        if not self._is_published(version_id, project_id):
            return ArchitecturePage((), 0)
        total, models = self._paged_models(
            ArchitectureUnresolvedRelationshipModel, version_id, limit, offset
        )
        entity_ids = tuple({item.source_entity_id for item in models})
        logical_by_id: dict[UUID, str] = (
            {
                entity_id: logical_id
                for entity_id, logical_id in self._session.execute(
                    select(
                        ArchitectureEntityModel.id, ArchitectureEntityModel.logical_id
                    ).where(ArchitectureEntityModel.id.in_(entity_ids))
                ).all()
            }
            if entity_ids
            else {}
        )
        associations = self._association_logical_map(
            ArchitectureUnresolvedEvidenceModel.unresolved_relationship_id,
            ArchitectureUnresolvedEvidenceModel.evidence_id,
            tuple(item.id for item in models),
        )
        return ArchitecturePage(
            tuple(
                self._unresolved(
                    item,
                    logical_by_id[item.source_entity_id],
                    associations.get(item.id, ()),
                )
                for item in models
            ),
            total,
        )

    def list_published_conflicts(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> ArchitecturePage[ArchitectureConflict]:
        if not self._is_published(version_id, project_id):
            return ArchitecturePage((), 0)
        total, models = self._paged_models(
            ArchitectureConflictModel, version_id, limit, offset
        )
        associations = self._association_logical_map(
            ArchitectureConflictEvidenceModel.conflict_id,
            ArchitectureConflictEvidenceModel.evidence_id,
            tuple(item.id for item in models),
        )
        return ArchitecturePage(
            tuple(
                self._conflict(item, associations.get(item.id, ())) for item in models
            ),
            total,
        )

    def list_latest_identities(
        self, project_id: UUID, repository_id: UUID
    ) -> tuple[HistoricalIdentityRecord, ...]:
        """Return exact identities from the latest published repository version."""
        latest_version_id = self._session.scalar(
            select(ArchitectureVersionModel.id)
            .where(
                ArchitectureVersionModel.project_id == project_id,
                ArchitectureVersionModel.repository_id == repository_id,
                ArchitectureVersionModel.state
                == ArchitectureVersionState.PUBLISHED.value,
            )
            .order_by(ArchitectureVersionModel.sequence_number.desc())
            .limit(1)
        )
        if latest_version_id is None:
            return ()
        records = self._session.scalars(
            select(ArchitectureEntityModel)
            .where(ArchitectureEntityModel.version_id == latest_version_id)
            .order_by(ArchitectureEntityModel.logical_id)
        )
        return tuple(
            HistoricalIdentityRecord(
                logical_id=item.logical_id,
                semantic_signature=item.semantic_signature,
                kind=ArchitectureEntityKind(item.kind),
            )
            for item in records
        )

    def _is_published(self, version_id: UUID, project_id: UUID) -> bool:
        return (
            self._session.scalar(
                select(ArchitectureVersionModel.id).where(
                    ArchitectureVersionModel.id == version_id,
                    ArchitectureVersionModel.project_id == project_id,
                    ArchitectureVersionModel.state
                    == ArchitectureVersionState.PUBLISHED.value,
                )
            )
            is not None
        )

    def _paged_models(
        self, model_type: Any, version_id: UUID, limit: int, offset: int
    ) -> tuple[int, tuple[Any, ...]]:
        total = int(
            self._session.scalar(
                select(func.count())
                .select_from(model_type)
                .where(model_type.version_id == version_id)
            )
            or 0
        )
        models = tuple(
            self._session.scalars(
                select(model_type)
                .where(model_type.version_id == version_id)
                .order_by(model_type.logical_id)
                .offset(offset)
                .limit(limit)
            )
        )
        return total, models

    def _insert_document(self, document: ArchitectureDocument) -> None:
        version_id = document.architecture_version_id
        evidence_ids = {
            item.logical_id: architecture_resource_id(
                version_id, "evidence", item.logical_id
            )
            for item in document.evidence
        }
        entity_ids = {
            item.logical_id: architecture_resource_id(
                version_id, "entity", item.logical_id
            )
            for item in document.entities
        }
        relationship_ids = {
            item.logical_id: architecture_resource_id(
                version_id, "relationship", item.logical_id
            )
            for item in document.relationships
        }
        unresolved_ids = {
            item.logical_id: architecture_resource_id(
                version_id, "unresolved", item.logical_id
            )
            for item in document.unresolved_relationships
        }
        conflict_ids = {
            item.logical_id: architecture_resource_id(
                version_id, "conflict", item.logical_id
            )
            for item in document.conflicts
        }

        self._session.add_all(
            ArchitectureEvidenceModel(
                id=evidence_ids[item.logical_id],
                version_id=version_id,
                logical_id=item.logical_id,
                source_evidence_key=item.source_evidence_key,
                source_record_type=item.source_record_type,
                path=item.path,
                artifact_id=item.artifact_id,
                source_fact_key=item.source_fact_key,
                source_range=_plain_mapping(item.source_range),
                producer_id=item.producer_id,
                producer_version=item.producer_version,
                strength=item.strength.value,
                polarity=item.polarity.value,
                safe_metadata=_plain_mapping(item.metadata),
            )
            for item in document.evidence
        )
        self._session.add_all(
            ArchitectureEntityModel(
                id=entity_ids[item.logical_id],
                version_id=version_id,
                logical_id=item.logical_id,
                semantic_signature=item.semantic_signature,
                kind=item.kind.value,
                name=item.name,
                namespace=list(item.namespace),
                status=item.status.value,
                source_ir_keys=list(item.source_ir_keys),
                safe_metadata=_plain_mapping(item.metadata),
            )
            for item in document.entities
        )
        self._session.flush()
        self._session.add_all(
            ArchitectureRelationshipModel(
                id=relationship_ids[item.logical_id],
                version_id=version_id,
                logical_id=item.logical_id,
                kind=item.kind.value,
                source_entity_id=entity_ids[item.source_logical_id],
                target_entity_id=entity_ids[item.target_logical_id],
                status=item.status.value,
                source_ir_keys=list(item.source_ir_keys),
                safe_metadata=_plain_mapping(item.metadata),
            )
            for item in document.relationships
        )
        self._session.add_all(
            ArchitectureUnresolvedRelationshipModel(
                id=unresolved_ids[item.logical_id],
                version_id=version_id,
                logical_id=item.logical_id,
                kind=item.kind.value,
                source_entity_id=entity_ids[item.source_logical_id],
                target_descriptor=item.target_descriptor,
                reason=item.reason.value,
                status=item.status.value,
                source_ir_keys=list(item.source_ir_keys),
                candidate_references=list(item.candidate_references),
                safe_metadata=_plain_mapping(item.metadata),
            )
            for item in document.unresolved_relationships
        )
        self._session.add_all(
            ArchitectureConflictModel(
                id=conflict_ids[item.logical_id],
                version_id=version_id,
                logical_id=item.logical_id,
                conflict_type=item.conflict_type,
                subject_key=item.subject_key,
                details=_plain_mapping(item.details),
            )
            for item in document.conflicts
        )
        self._session.flush()

        self._session.add_all(
            ArchitectureEntityEvidenceModel(
                entity_id=entity_ids[item.logical_id],
                evidence_id=evidence_ids[evidence_id],
            )
            for item in document.entities
            for evidence_id in item.evidence_ids
        )
        self._session.add_all(
            ArchitectureRelationshipEvidenceModel(
                relationship_id=relationship_ids[item.logical_id],
                evidence_id=evidence_ids[evidence_id],
            )
            for item in document.relationships
            for evidence_id in item.evidence_ids
        )
        self._session.add_all(
            ArchitectureUnresolvedEvidenceModel(
                unresolved_relationship_id=unresolved_ids[item.logical_id],
                evidence_id=evidence_ids[evidence_id],
            )
            for item in document.unresolved_relationships
            for evidence_id in item.evidence_ids
        )
        self._session.add_all(
            ArchitectureConflictEvidenceModel(
                conflict_id=conflict_ids[item.logical_id],
                evidence_id=evidence_ids[evidence_id],
            )
            for item in document.conflicts
            for evidence_id in item.evidence_ids
        )

    def _load_document(self, version: ArchitectureVersionModel) -> ArchitectureDocument:
        evidence_models = list(
            self._session.scalars(
                select(ArchitectureEvidenceModel)
                .where(ArchitectureEvidenceModel.version_id == version.id)
                .order_by(ArchitectureEvidenceModel.logical_id)
            )
        )
        entity_models = list(
            self._session.scalars(
                select(ArchitectureEntityModel)
                .where(ArchitectureEntityModel.version_id == version.id)
                .order_by(ArchitectureEntityModel.logical_id)
            )
        )
        relationship_models = list(
            self._session.scalars(
                select(ArchitectureRelationshipModel)
                .where(ArchitectureRelationshipModel.version_id == version.id)
                .order_by(ArchitectureRelationshipModel.logical_id)
            )
        )
        unresolved_models = list(
            self._session.scalars(
                select(ArchitectureUnresolvedRelationshipModel)
                .where(ArchitectureUnresolvedRelationshipModel.version_id == version.id)
                .order_by(ArchitectureUnresolvedRelationshipModel.logical_id)
            )
        )
        conflict_models = list(
            self._session.scalars(
                select(ArchitectureConflictModel)
                .where(ArchitectureConflictModel.version_id == version.id)
                .order_by(ArchitectureConflictModel.logical_id)
            )
        )
        evidence_logical_by_id = {item.id: item.logical_id for item in evidence_models}
        entity_logical_by_id = {item.id: item.logical_id for item in entity_models}

        entity_evidence = self._association_map(
            ArchitectureEntityEvidenceModel.entity_id,
            ArchitectureEntityEvidenceModel.evidence_id,
            evidence_logical_by_id,
            tuple(item.id for item in entity_models),
        )
        relationship_evidence = self._association_map(
            ArchitectureRelationshipEvidenceModel.relationship_id,
            ArchitectureRelationshipEvidenceModel.evidence_id,
            evidence_logical_by_id,
            tuple(item.id for item in relationship_models),
        )
        unresolved_evidence = self._association_map(
            ArchitectureUnresolvedEvidenceModel.unresolved_relationship_id,
            ArchitectureUnresolvedEvidenceModel.evidence_id,
            evidence_logical_by_id,
            tuple(item.id for item in unresolved_models),
        )
        conflict_evidence = self._association_map(
            ArchitectureConflictEvidenceModel.conflict_id,
            ArchitectureConflictEvidenceModel.evidence_id,
            evidence_logical_by_id,
            tuple(item.id for item in conflict_models),
        )

        return ArchitectureDocument(
            architecture_version_id=version.id,
            analysis_id=version.analysis_id,
            project_id=version.project_id,
            repository_id=version.repository_id,
            snapshot_id=version.snapshot_id,
            configuration_fingerprint=version.configuration_fingerprint,
            analyzer_version=version.analyzer_version,
            ir_schema_version=version.ir_schema_version,
            architecture_schema_version=version.architecture_schema_version,
            entities=tuple(
                ArchitectureEntity(
                    logical_id=item.logical_id,
                    semantic_signature=item.semantic_signature,
                    kind=ArchitectureEntityKind(item.kind),
                    name=item.name,
                    namespace=tuple(item.namespace),
                    status=ArchitectureFactStatus(item.status),
                    evidence_ids=entity_evidence.get(item.id, ()),
                    source_ir_keys=tuple(item.source_ir_keys),
                    metadata=item.safe_metadata,
                )
                for item in entity_models
            ),
            relationships=tuple(
                ArchitectureRelationship(
                    logical_id=item.logical_id,
                    kind=ArchitectureRelationshipKind(item.kind),
                    source_logical_id=entity_logical_by_id[item.source_entity_id],
                    target_logical_id=entity_logical_by_id[item.target_entity_id],
                    status=ArchitectureFactStatus(item.status),
                    evidence_ids=relationship_evidence.get(item.id, ()),
                    source_ir_keys=tuple(item.source_ir_keys),
                    metadata=item.safe_metadata,
                )
                for item in relationship_models
            ),
            evidence=tuple(
                ArchitectureEvidence(
                    logical_id=item.logical_id,
                    source_evidence_key=item.source_evidence_key,
                    source_record_type=item.source_record_type,
                    path=item.path,
                    artifact_id=item.artifact_id,
                    source_fact_key=item.source_fact_key,
                    source_range=item.source_range,
                    producer_id=item.producer_id,
                    producer_version=item.producer_version,
                    strength=ArchitectureEvidenceStrength(item.strength),
                    polarity=ArchitectureEvidencePolarity(item.polarity),
                    metadata=item.safe_metadata,
                )
                for item in evidence_models
            ),
            unresolved_relationships=tuple(
                ArchitectureUnresolvedRelationship(
                    logical_id=item.logical_id,
                    kind=ArchitectureRelationshipKind(item.kind),
                    source_logical_id=entity_logical_by_id[item.source_entity_id],
                    target_descriptor=item.target_descriptor,
                    reason=ArchitectureUnresolvedReason(item.reason),
                    status=ArchitectureFactStatus(item.status),
                    evidence_ids=unresolved_evidence.get(item.id, ()),
                    source_ir_keys=tuple(item.source_ir_keys),
                    candidate_references=tuple(item.candidate_references),
                    metadata=item.safe_metadata,
                )
                for item in unresolved_models
            ),
            conflicts=tuple(
                ArchitectureConflict(
                    logical_id=item.logical_id,
                    conflict_type=item.conflict_type,
                    subject_key=item.subject_key,
                    evidence_ids=conflict_evidence.get(item.id, ()),
                    details=item.details,
                )
                for item in conflict_models
            ),
            completeness=ArchitectureCompleteness(**version.completeness),
            source_diagnostic_ids=tuple(version.source_diagnostic_ids),
            content_digest=version.content_digest,
        )

    def _association_map(
        self,
        owner_column: Any,
        evidence_column: Any,
        evidence_logical_by_id: dict[UUID, str],
        owner_ids: tuple[UUID, ...],
    ) -> dict[UUID, tuple[str, ...]]:
        if not owner_ids:
            return {}
        result: dict[UUID, list[str]] = {}
        rows = self._session.execute(
            select(owner_column, evidence_column).where(owner_column.in_(owner_ids))
        ).all()
        for owner_id, evidence_id in rows:
            if evidence_id not in evidence_logical_by_id:
                continue
            result.setdefault(owner_id, []).append(evidence_logical_by_id[evidence_id])
        return {key: tuple(sorted(values)) for key, values in result.items()}

    def _association_logical_map(
        self,
        owner_column: Any,
        evidence_column: Any,
        owner_ids: tuple[UUID, ...],
    ) -> dict[UUID, tuple[str, ...]]:
        if not owner_ids:
            return {}
        rows = self._session.execute(
            select(owner_column, ArchitectureEvidenceModel.logical_id)
            .join(
                ArchitectureEvidenceModel,
                evidence_column == ArchitectureEvidenceModel.id,
            )
            .where(owner_column.in_(owner_ids))
        ).all()
        result: dict[UUID, list[str]] = {}
        for owner_id, logical_id in rows:
            result.setdefault(owner_id, []).append(logical_id)
        return {key: tuple(sorted(values)) for key, values in result.items()}

    @staticmethod
    def _entity(
        item: ArchitectureEntityModel, evidence_ids: tuple[str, ...]
    ) -> ArchitectureEntity:
        return ArchitectureEntity(
            logical_id=item.logical_id,
            semantic_signature=item.semantic_signature,
            kind=ArchitectureEntityKind(item.kind),
            name=item.name,
            namespace=tuple(item.namespace),
            status=ArchitectureFactStatus(item.status),
            evidence_ids=evidence_ids,
            source_ir_keys=tuple(item.source_ir_keys),
            metadata=item.safe_metadata,
        )

    @staticmethod
    def _relationship(
        item: ArchitectureRelationshipModel,
        entity_logical_by_id: dict[UUID, str],
        evidence_ids: tuple[str, ...],
    ) -> ArchitectureRelationship:
        return ArchitectureRelationship(
            logical_id=item.logical_id,
            kind=ArchitectureRelationshipKind(item.kind),
            source_logical_id=entity_logical_by_id[item.source_entity_id],
            target_logical_id=entity_logical_by_id[item.target_entity_id],
            status=ArchitectureFactStatus(item.status),
            evidence_ids=evidence_ids,
            source_ir_keys=tuple(item.source_ir_keys),
            metadata=item.safe_metadata,
        )

    @staticmethod
    def _evidence(item: ArchitectureEvidenceModel) -> ArchitectureEvidence:
        return ArchitectureEvidence(
            logical_id=item.logical_id,
            source_evidence_key=item.source_evidence_key,
            source_record_type=item.source_record_type,
            path=item.path,
            artifact_id=item.artifact_id,
            source_fact_key=item.source_fact_key,
            source_range=item.source_range,
            producer_id=item.producer_id,
            producer_version=item.producer_version,
            strength=ArchitectureEvidenceStrength(item.strength),
            polarity=ArchitectureEvidencePolarity(item.polarity),
            metadata=item.safe_metadata,
        )

    @staticmethod
    def _unresolved(
        item: ArchitectureUnresolvedRelationshipModel,
        source_logical_id: str,
        evidence_ids: tuple[str, ...],
    ) -> ArchitectureUnresolvedRelationship:
        return ArchitectureUnresolvedRelationship(
            logical_id=item.logical_id,
            kind=ArchitectureRelationshipKind(item.kind),
            source_logical_id=source_logical_id,
            target_descriptor=item.target_descriptor,
            reason=ArchitectureUnresolvedReason(item.reason),
            status=ArchitectureFactStatus(item.status),
            evidence_ids=evidence_ids,
            source_ir_keys=tuple(item.source_ir_keys),
            candidate_references=tuple(item.candidate_references),
            metadata=item.safe_metadata,
        )

    @staticmethod
    def _conflict(
        item: ArchitectureConflictModel, evidence_ids: tuple[str, ...]
    ) -> ArchitectureConflict:
        return ArchitectureConflict(
            logical_id=item.logical_id,
            conflict_type=item.conflict_type,
            subject_key=item.subject_key,
            evidence_ids=evidence_ids,
            details=item.details,
        )

    def _verify_counts(
        self, header: ArchitectureVersionModel, document: ArchitectureDocument
    ) -> None:
        checks = (
            (ArchitectureEntityModel, header.entity_count, len(document.entities)),
            (
                ArchitectureRelationshipModel,
                header.relationship_count,
                len(document.relationships),
            ),
            (ArchitectureEvidenceModel, header.evidence_count, len(document.evidence)),
            (
                ArchitectureUnresolvedRelationshipModel,
                header.unresolved_relationship_count,
                len(document.unresolved_relationships),
            ),
            (ArchitectureConflictModel, header.conflict_count, len(document.conflicts)),
        )
        for model_type, declared, expected in checks:
            actual = self._session.scalar(
                select(func.count())
                .select_from(model_type)
                .where(model_type.version_id == header.id)
            )
            if actual != expected or declared != expected:
                raise ArchitecturePersistenceIntegrityError(
                    "persisted Architecture Model counts do not match validated content"
                )

    def _child_count(self, version_id: UUID) -> int:
        return sum(
            int(
                self._session.scalar(
                    select(func.count())
                    .select_from(model_type)
                    .where(model_type.version_id == version_id)
                )
                or 0
            )
            for model_type in (
                ArchitectureEntityModel,
                ArchitectureRelationshipModel,
                ArchitectureEvidenceModel,
                ArchitectureUnresolvedRelationshipModel,
                ArchitectureConflictModel,
            )
        )

    def _required_header(
        self, version_id: UUID, analysis_id: UUID, *, lock: bool
    ) -> ArchitectureVersionModel:
        statement = select(ArchitectureVersionModel).where(
            ArchitectureVersionModel.id == version_id,
            ArchitectureVersionModel.analysis_id == analysis_id,
        )
        if lock:
            statement = statement.with_for_update()
        model = self._session.scalar(statement)
        if model is None:
            raise ArchitectureVersionStateError("Architecture Version header not found")
        return model

    def _get_by_analysis(
        self, analysis_id: UUID, *, lock: bool
    ) -> ArchitectureVersionModel | None:
        statement = select(ArchitectureVersionModel).where(
            ArchitectureVersionModel.analysis_id == analysis_id
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def _lock_repository_sequence(self, repository_id: UUID) -> None:
        if (
            self._session.bind is None
            or self._session.bind.dialect.name != "postgresql"
        ):
            return
        lock_key = int.from_bytes(
            hashlib.sha256(repository_id.bytes).digest()[:8],
            byteorder="big",
            signed=True,
        )
        self._session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key}
        )

    def _next_sequence(self, repository_id: UUID) -> int:
        current = self._session.scalar(
            select(func.max(ArchitectureVersionModel.sequence_number)).where(
                ArchitectureVersionModel.repository_id == repository_id
            )
        )
        return int(current or 0) + 1

    @staticmethod
    def _assert_same_content(
        model: ArchitectureVersionModel, document: ArchitectureDocument
    ) -> None:
        identity = (
            model.project_id,
            model.repository_id,
            model.snapshot_id,
            model.configuration_fingerprint,
            model.analyzer_version,
            model.ir_schema_version,
            model.architecture_schema_version,
            model.content_digest,
        )
        supplied = (
            document.project_id,
            document.repository_id,
            document.snapshot_id,
            document.configuration_fingerprint,
            document.analyzer_version,
            document.ir_schema_version,
            document.architecture_schema_version,
            document.content_digest,
        )
        if identity != supplied:
            raise ArchitecturePersistenceIntegrityError(
                "analysis already owns a different immutable Architecture Version"
            )

    @staticmethod
    def _to_record(model: ArchitectureVersionModel) -> ArchitectureVersionRecord:
        return ArchitectureVersionRecord(
            id=model.id,
            analysis_id=model.analysis_id,
            project_id=model.project_id,
            repository_id=model.repository_id,
            snapshot_id=model.snapshot_id,
            sequence_number=model.sequence_number,
            state=ArchitectureVersionState(model.state),
            configuration_fingerprint=model.configuration_fingerprint,
            analyzer_version=model.analyzer_version,
            ir_schema_version=model.ir_schema_version,
            architecture_schema_version=model.architecture_schema_version,
            content_digest=model.content_digest,
            completeness=dict(model.completeness),
            source_diagnostic_ids=tuple(model.source_diagnostic_ids),
            entity_count=model.entity_count,
            relationship_count=model.relationship_count,
            evidence_count=model.evidence_count,
            unresolved_relationship_count=model.unresolved_relationship_count,
            conflict_count=model.conflict_count,
            diagnostic_id=model.diagnostic_id,
            failure_code=model.failure_code,
            created_at=_ensure_utc(model.created_at),
            updated_at=_ensure_utc(model.updated_at),
            published_at=(
                None if model.published_at is None else _ensure_utc(model.published_at)
            ),
        )


def architecture_resource_id(
    version_id: UUID, record_type: str, logical_id: str
) -> UUID:
    """Generate a stable persistence UUID, distinct from the canonical logical ID."""
    return uuid5(version_id, f"{record_type}\0{logical_id}")


def _plain_mapping(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(key): _plain_mapping(item) for key, item in value.items()}
    if hasattr(value, "items"):
        return {str(key): _plain_mapping(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain_mapping(item) for item in value]
    return value


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


__all__ = [
    "ArchitectureConflictEvidenceModel",
    "ArchitectureConflictModel",
    "ArchitectureEntityEvidenceModel",
    "ArchitectureEntityModel",
    "ArchitectureEvidenceModel",
    "ArchitectureRelationshipEvidenceModel",
    "ArchitectureRelationshipModel",
    "ArchitectureUnresolvedEvidenceModel",
    "ArchitectureUnresolvedRelationshipModel",
    "ArchitectureVersionModel",
    "architecture_resource_id",
    "SqlAlchemyArchitectureRepository",
]
