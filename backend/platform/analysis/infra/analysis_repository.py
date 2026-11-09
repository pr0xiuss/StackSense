"""SQLAlchemy implementation of AnalysisRepository."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.platform.analysis.domain.analysis import (
    Analysis,
    AnalysisCompleteness,
    AnalysisConfiguration,
)
from backend.platform.analysis.domain.constants import AnalysisStatus
from backend.platform.analysis.infra.lifecycle_model import AnalysisModel
from backend.platform.analysis.repositories.analysis_repo import (
    AnalysisPublicationLinker,
    AnalysisRepository,
)
from backend.platform.errors import AnalysisStateConflictError


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class SqlAlchemyAnalysisRepository(AnalysisRepository, AnalysisPublicationLinker):
    """PostgreSQL-backed implementation of AnalysisRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _config_to_dict(config: AnalysisConfiguration) -> dict[str, Any]:
        return {
            "include_paths": list(config.include_paths),
            "exclude_paths": list(config.exclude_paths),
            "max_file_size_bytes": config.max_file_size_bytes,
            "timeout_seconds": config.timeout_seconds,
            "custom_rules": [list(r) for r in config.custom_rules],
        }

    @staticmethod
    def _dict_to_config(data: dict[str, Any] | None) -> AnalysisConfiguration:
        if not data:
            return AnalysisConfiguration()
        return AnalysisConfiguration(
            include_paths=tuple(data.get("include_paths", ())),
            exclude_paths=tuple(data.get("exclude_paths", ())),
            max_file_size_bytes=data.get("max_file_size_bytes", 5 * 1024 * 1024),
            timeout_seconds=data.get("timeout_seconds", 1800),
            custom_rules=tuple(tuple(r) for r in data.get("custom_rules", ())),
        )

    @staticmethod
    def _completeness_to_dict(
        completeness: AnalysisCompleteness | None,
    ) -> dict[str, Any] | None:
        if completeness is None:
            return None
        return {
            "analyzed_files_count": completeness.analyzed_files_count,
            "unsupported_files_count": completeness.unsupported_files_count,
            "failed_files_count": completeness.failed_files_count,
            "excluded_files_count": completeness.excluded_files_count,
            "is_partial": completeness.is_partial,
            "details": [list(d) for d in completeness.details],
        }

    @staticmethod
    def _dict_to_completeness(
        data: dict[str, Any] | None,
    ) -> AnalysisCompleteness | None:
        if data is None:
            return None
        return AnalysisCompleteness(
            analyzed_files_count=data.get("analyzed_files_count", 0),
            unsupported_files_count=data.get("unsupported_files_count", 0),
            failed_files_count=data.get("failed_files_count", 0),
            excluded_files_count=data.get("excluded_files_count", 0),
            is_partial=data.get("is_partial", False),
            details=tuple(tuple(d) for d in data.get("details", ())),
        )

    def _to_domain(self, model: AnalysisModel) -> Analysis:
        created_at = _ensure_utc(model.created_at)
        assert created_at is not None
        updated_at = _ensure_utc(model.updated_at)
        assert updated_at is not None
        return Analysis(
            id=model.id,
            project_id=model.project_id,
            repository_id=model.repository_id,
            snapshot_id=model.snapshot_id,
            status=AnalysisStatus(model.status),
            configuration=self._dict_to_config(model.configuration),
            created_at=created_at,
            updated_at=updated_at,
            started_at=_ensure_utc(model.started_at),
            completed_at=_ensure_utc(model.completed_at),
            completeness=self._dict_to_completeness(model.completeness),
            published_version_id=model.published_version_id,
            error_message=model.error_message,
            error_code=model.error_code,
            version=model.version,
        )

    def save(
        self,
        analysis: Analysis,
        *,
        idempotency_key: str | None = None,
    ) -> Analysis:
        """Persist a new analysis record."""
        model = AnalysisModel(
            id=analysis.id,
            project_id=analysis.project_id,
            repository_id=analysis.repository_id,
            snapshot_id=analysis.snapshot_id,
            status=analysis.status.value,
            configuration=self._config_to_dict(analysis.configuration),
            completeness=self._completeness_to_dict(analysis.completeness),
            published_version_id=analysis.published_version_id,
            error_code=analysis.error_code,
            error_message=analysis.error_message,
            idempotency_key=idempotency_key,
            version=analysis.version,
            created_at=analysis.created_at,
            updated_at=analysis.updated_at,
            started_at=analysis.started_at,
            completed_at=analysis.completed_at,
        )
        try:
            with self._session.begin_nested():
                self._session.add(model)
                self._session.flush()
        except IntegrityError:
            if idempotency_key is None:
                raise
            existing = self.get_by_idempotency_key(analysis.project_id, idempotency_key)
            if existing is None:
                raise
            return existing
        return analysis

    def get_by_id(self, analysis_id: UUID, project_id: UUID) -> Analysis | None:
        """Retrieve an analysis by identifier within the owning project."""
        stmt = select(AnalysisModel).where(
            AnalysisModel.id == analysis_id,
            AnalysisModel.project_id == project_id,
        )
        model = self._session.scalar(stmt)
        if model is None:
            return None
        return self._to_domain(model)

    def get_by_idempotency_key(
        self,
        project_id: UUID,
        idempotency_key: str,
    ) -> Analysis | None:
        """Retrieve an existing analysis by idempotency key within project."""
        stmt = select(AnalysisModel).where(
            AnalysisModel.project_id == project_id,
            AnalysisModel.idempotency_key == idempotency_key,
        )
        model = self._session.scalar(stmt)
        if model is None:
            return None
        return self._to_domain(model)

    def update(self, analysis: Analysis, expected_version: int) -> Analysis:
        """Update an existing analysis using optimistic concurrency check."""
        stmt = (
            update(AnalysisModel)
            .where(
                AnalysisModel.id == analysis.id,
                AnalysisModel.version == expected_version,
            )
            .values(
                status=analysis.status.value,
                configuration=self._config_to_dict(analysis.configuration),
                completeness=self._completeness_to_dict(analysis.completeness),
                published_version_id=analysis.published_version_id,
                error_code=analysis.error_code,
                error_message=analysis.error_message,
                version=analysis.version,
                updated_at=analysis.updated_at,
                started_at=analysis.started_at,
                completed_at=analysis.completed_at,
            )
        )
        result = self._session.execute(stmt)
        if isinstance(result, CursorResult) and result.rowcount == 0:
            raise AnalysisStateConflictError(
                message=(
                    f"Concurrency conflict: expected version {expected_version} "
                    f"for analysis '{analysis.id}'."
                ),
                details={
                    "analysis_id": str(analysis.id),
                    "expected_version": expected_version,
                },
            )
        self._session.flush()
        return analysis

    def list_by_project(
        self,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        status: AnalysisStatus | None = None,
        repository_id: UUID | None = None,
    ) -> list[Analysis]:
        """List analyses for a project with deterministic pagination."""
        stmt = (
            select(AnalysisModel)
            .where(AnalysisModel.project_id == project_id)
            .order_by(AnalysisModel.created_at.desc(), AnalysisModel.id)
            .offset(offset)
            .limit(limit)
        )
        if repository_id is not None:
            stmt = stmt.where(AnalysisModel.repository_id == repository_id)
        if status is not None:
            stmt = stmt.where(AnalysisModel.status == status.value)

        models = self._session.scalars(stmt).all()
        return [self._to_domain(m) for m in models]

    def count_by_project(
        self,
        project_id: UUID,
        status: AnalysisStatus | None = None,
        repository_id: UUID | None = None,
    ) -> int:
        """Count analyses for a project with optional status filtering."""
        stmt = select(func.count(AnalysisModel.id)).where(
            AnalysisModel.project_id == project_id,
        )
        if repository_id is not None:
            stmt = stmt.where(AnalysisModel.repository_id == repository_id)
        if status is not None:
            stmt = stmt.where(AnalysisModel.status == status.value)
        return self._session.scalar(stmt) or 0

    def link_published_version(
        self,
        analysis_id: UUID,
        project_id: UUID,
        version_id: UUID,
    ) -> None:
        """Atomically and optimistically assign the published version pointer."""
        now = datetime.now(UTC)
        statement = (
            update(AnalysisModel)
            .where(
                AnalysisModel.id == analysis_id,
                AnalysisModel.project_id == project_id,
                AnalysisModel.status == AnalysisStatus.RUNNING.value,
                AnalysisModel.published_version_id.is_(None),
            )
            .values(
                published_version_id=version_id,
                version=AnalysisModel.version + 1,
                updated_at=now,
            )
        )
        result = self._session.execute(statement)
        if isinstance(result, CursorResult) and result.rowcount == 0:
            existing = self._session.scalar(
                select(AnalysisModel).where(
                    AnalysisModel.id == analysis_id,
                    AnalysisModel.project_id == project_id,
                )
            )
            if (
                existing is not None
                and existing.status == AnalysisStatus.RUNNING.value
                and existing.published_version_id == version_id
            ):
                return
            raise AnalysisStateConflictError(
                message=(
                    "Analysis must be running with an empty or identical "
                    "published-version pointer."
                ),
                details={"analysis_id": str(analysis_id)},
            )
        self._session.flush()
