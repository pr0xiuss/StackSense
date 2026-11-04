"""SQLAlchemy implementation of DiagnosticRepository."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.platform.analysis.domain.constants import (
    DiagnosticCategory,
    DiagnosticScope,
    DiagnosticSeverity,
    FailureRetryability,
)
from backend.platform.analysis.domain.diagnostic import AnalysisDiagnostic
from backend.platform.analysis.infra.lifecycle_model import (
    AnalysisDiagnosticModel,
)
from backend.platform.analysis.repositories.diagnostic_repo import (
    DiagnosticRepository,
)


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class SqlAlchemyDiagnosticRepository(DiagnosticRepository):
    """PostgreSQL-backed implementation of DiagnosticRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: AnalysisDiagnosticModel) -> AnalysisDiagnostic:
        created_at = _ensure_utc(model.created_at)
        assert created_at is not None
        return AnalysisDiagnostic(
            id=model.id,
            analysis_id=model.analysis_id,
            job_id=model.job_id,
            stage=model.stage,
            code=model.code,
            category=DiagnosticCategory(model.category),
            severity=DiagnosticSeverity(model.severity),
            scope=DiagnosticScope(model.scope),
            message=model.message,
            retryability=FailureRetryability(model.retryability),
            details=model.details,
            artifact_id=model.artifact_id,
            artifact_path=model.artifact_path,
            source_line=model.source_line,
            source_column=model.source_column,
            created_at=created_at,
        )

    def save_batch(self, diagnostics: list[AnalysisDiagnostic]) -> None:
        """Persist a batch of diagnostic records."""
        for diag in diagnostics:
            model = AnalysisDiagnosticModel(
                id=diag.id,
                analysis_id=diag.analysis_id,
                job_id=diag.job_id,
                stage=diag.stage,
                code=diag.code,
                category=diag.category.value,
                severity=diag.severity.value,
                scope=diag.scope.value,
                message=diag.message,
                retryability=diag.retryability.value,
                details=diag.details,
                artifact_id=diag.artifact_id,
                artifact_path=diag.artifact_path,
                source_line=diag.source_line,
                source_column=diag.source_column,
                created_at=diag.created_at,
            )
            self._session.add(model)
        self._session.flush()

    def list_by_analysis(
        self,
        analysis_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
        severity: DiagnosticSeverity | None = None,
        stage: str | None = None,
    ) -> list[AnalysisDiagnostic]:
        """List diagnostics for an analysis with filtering and pagination."""
        stmt = (
            select(AnalysisDiagnosticModel)
            .where(AnalysisDiagnosticModel.analysis_id == analysis_id)
            .order_by(AnalysisDiagnosticModel.created_at, AnalysisDiagnosticModel.id)
            .offset(offset)
            .limit(limit)
        )
        if severity is not None:
            stmt = stmt.where(AnalysisDiagnosticModel.severity == severity.value)
        if stage is not None:
            stmt = stmt.where(AnalysisDiagnosticModel.stage == stage)

        models = self._session.scalars(stmt).all()
        return [self._to_domain(m) for m in models]

    def count_by_analysis(
        self,
        analysis_id: UUID,
        severity: DiagnosticSeverity | None = None,
    ) -> int:
        """Count diagnostics for an analysis with optional severity filter."""
        stmt = select(func.count(AnalysisDiagnosticModel.id)).where(
            AnalysisDiagnosticModel.analysis_id == analysis_id,
        )
        if severity is not None:
            stmt = stmt.where(AnalysisDiagnosticModel.severity == severity.value)
        return self._session.scalar(stmt) or 0
