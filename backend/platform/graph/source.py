"""P4-owned read adapter over frozen published Architecture Versions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from backend.platform.analysis.architecture.model import ArchitectureDocument
from backend.platform.analysis.architecture.persistence import (
    ArchitectureVersionModel,
    SqlAlchemyArchitectureRepository,
)
from backend.platform.analysis.architecture.repository import ArchitectureVersionState
from backend.platform.graph.model import SOURCE_CONTRACT_VERSION, ProjectionCounts


@dataclass(frozen=True, slots=True)
class PublishedArchitectureHeader:
    contract_version: str
    architecture_version_id: UUID
    analysis_id: UUID
    project_id: UUID
    repository_id: UUID
    snapshot_id: UUID
    sequence_number: int
    published_at: datetime
    configuration_fingerprint: str
    analyzer_version: str
    ir_schema_version: str
    architecture_schema_version: str
    content_digest: str
    counts: ProjectionCounts


@dataclass(frozen=True, slots=True)
class PublishedArchitectureCursor:
    project_id: UUID
    repository_id: UUID
    sequence_number: int
    architecture_version_id: UUID


@dataclass(frozen=True, slots=True)
class PublishedArchitecturePage:
    items: tuple[PublishedArchitectureHeader, ...]
    next_cursor: PublishedArchitectureCursor | None


class PublishedArchitectureSource(Protocol):
    def list_published(
        self,
        *,
        limit: int,
        after: PublishedArchitectureCursor | None = None,
    ) -> PublishedArchitecturePage: ...

    def load_exact(
        self, architecture_version_id: UUID, project_id: UUID
    ) -> ArchitectureDocument | None: ...


class SqlAlchemyPublishedArchitectureSource:
    """Read-only P4 adapter that does not modify frozen P3 repositories."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_published(
        self,
        *,
        limit: int,
        after: PublishedArchitectureCursor | None = None,
    ) -> PublishedArchitecturePage:
        if not 1 <= limit <= 500:
            raise ValueError("published Architecture Version page limit must be 1..500")
        statement = select(ArchitectureVersionModel).where(
            ArchitectureVersionModel.state == ArchitectureVersionState.PUBLISHED.value
        )
        if after is not None:
            statement = statement.where(self._after_cursor(after))
        statement = statement.order_by(
            ArchitectureVersionModel.project_id,
            ArchitectureVersionModel.repository_id,
            ArchitectureVersionModel.sequence_number,
            ArchitectureVersionModel.id,
        ).limit(limit + 1)
        rows = tuple(self._session.scalars(statement))
        has_more = len(rows) > limit
        selected = rows[:limit]
        items = tuple(self._header(row) for row in selected)
        next_cursor = None
        if has_more and selected:
            last = selected[-1]
            next_cursor = PublishedArchitectureCursor(
                project_id=last.project_id,
                repository_id=last.repository_id,
                sequence_number=last.sequence_number,
                architecture_version_id=last.id,
            )
        return PublishedArchitecturePage(items=items, next_cursor=next_cursor)

    def load_exact(
        self, architecture_version_id: UUID, project_id: UUID
    ) -> ArchitectureDocument | None:
        return SqlAlchemyArchitectureRepository(self._session).load_published_document(
            architecture_version_id,
            project_id,
        )

    @staticmethod
    def _after_cursor(cursor: PublishedArchitectureCursor) -> ColumnElement[bool]:
        model = ArchitectureVersionModel
        return or_(
            model.project_id > cursor.project_id,
            and_(
                model.project_id == cursor.project_id,
                model.repository_id > cursor.repository_id,
            ),
            and_(
                model.project_id == cursor.project_id,
                model.repository_id == cursor.repository_id,
                model.sequence_number > cursor.sequence_number,
            ),
            and_(
                model.project_id == cursor.project_id,
                model.repository_id == cursor.repository_id,
                model.sequence_number == cursor.sequence_number,
                model.id > cursor.architecture_version_id,
            ),
        )

    @staticmethod
    def _header(model: ArchitectureVersionModel) -> PublishedArchitectureHeader:
        if model.published_at is None:
            raise RuntimeError(
                "published Architecture Version is missing publication time"
            )
        return PublishedArchitectureHeader(
            contract_version=SOURCE_CONTRACT_VERSION,
            architecture_version_id=model.id,
            analysis_id=model.analysis_id,
            project_id=model.project_id,
            repository_id=model.repository_id,
            snapshot_id=model.snapshot_id,
            sequence_number=model.sequence_number,
            published_at=_ensure_utc(model.published_at),
            configuration_fingerprint=model.configuration_fingerprint,
            analyzer_version=model.analyzer_version,
            ir_schema_version=model.ir_schema_version,
            architecture_schema_version=model.architecture_schema_version,
            content_digest=model.content_digest,
            counts=ProjectionCounts(
                entities=model.entity_count,
                relationships=model.relationship_count,
                evidence=model.evidence_count,
                unresolved=model.unresolved_relationship_count,
                conflicts=model.conflict_count,
            ),
        )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "PublishedArchitectureCursor",
    "PublishedArchitectureHeader",
    "PublishedArchitecturePage",
    "PublishedArchitectureSource",
    "SqlAlchemyPublishedArchitectureSource",
]
