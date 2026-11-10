"""Thin M4 stage adapters for identity resolution and model publication."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4, uuid5

from sqlalchemy.exc import OperationalError

from backend.platform.analysis.application.execution import (
    AnalysisStageHandler,
    ExecutionContext,
    StageExecutionResult,
)
from backend.platform.analysis.architecture.builder import ArchitectureBuilder
from backend.platform.analysis.architecture.identity import IdentityResolutionService
from backend.platform.analysis.architecture.model import (
    ArchitectureCapacityError,
    ArchitectureModelError,
    ArchitectureValidationError,
)
from backend.platform.analysis.architecture.repository import (
    ArchitecturePersistenceError,
)
from backend.platform.analysis.architecture.service import (
    ArchitecturePublicationService,
)
from backend.platform.analysis.domain.constants import (
    AnalysisStageName,
    DiagnosticCategory,
    DiagnosticScope,
    DiagnosticSeverity,
    FailureRetryability,
    StageStatus,
)
from backend.platform.analysis.domain.diagnostic import AnalysisDiagnostic

if TYPE_CHECKING:
    from backend.platform.analysis.application.handoff import (
        F3ResultReader,
        ResolvedArchitectureResultReader,
        ResolvedArchitectureResultWriter,
    )
    from backend.platform.analysis.application.registry import StageHandlerRegistry

logger = logging.getLogger(__name__)


def architecture_version_id(analysis_id: UUID) -> UUID:
    """Return the stable persistence identity for one Analysis result."""
    return uuid5(analysis_id, "architecture-model-v1")


class IdentityResolutionStageHandler(AnalysisStageHandler):
    """Resolve F3 candidates without taking ownership of orchestration/recovery."""

    def __init__(
        self,
        f3_reader: F3ResultReader,
        result_writer: ResolvedArchitectureResultWriter,
        service: IdentityResolutionService,
    ) -> None:
        self._f3_reader = f3_reader
        self._result_writer = result_writer
        self._service = service

    @property
    def stage_name(self) -> str:
        return AnalysisStageName.IDENTITY_RESOLUTION.value

    def execute(self, context: ExecutionContext) -> StageExecutionResult:
        context.check_cancellation()
        context.report_progress(0, 1, "Resolving architecture identities")
        try:
            source = self._f3_reader.read_f3_result(
                context.analysis_id, context.job_id, context.input
            )
            resolved = self._service.resolve(source)
            context.check_cancellation()
            self._result_writer.write_resolved_architecture_result(
                context.analysis_id, context.job_id, resolved
            )
        except OperationalError:
            raise
        except (LookupError, ValueError, ArchitectureModelError) as exc:
            return _failure(context, self.stage_name, "identity_resolution_failed", exc)
        context.report_progress(1, 1, "Architecture identities resolved")
        return StageExecutionResult(
            stage_name=self.stage_name,
            status=StageStatus.COMPLETED,
            processed_items=len(resolved.entities),
            total_items=len(resolved.entities),
        )


class ArchitectureBuildStageHandler(AnalysisStageHandler):
    """Construct, validate and atomically publish the canonical model."""

    def __init__(
        self,
        f3_reader: F3ResultReader,
        resolved_reader: ResolvedArchitectureResultReader,
        builder: ArchitectureBuilder,
        publication: ArchitecturePublicationService,
    ) -> None:
        self._f3_reader = f3_reader
        self._resolved_reader = resolved_reader
        self._builder = builder
        self._publication = publication

    @property
    def stage_name(self) -> str:
        return AnalysisStageName.ARCHITECTURE_BUILD.value

    @property
    def requires_published_architecture(self) -> bool:
        return True

    def execute(self, context: ExecutionContext) -> StageExecutionResult:
        context.check_cancellation()
        context.report_progress(0, 1, "Constructing Architecture Model")
        version_id = architecture_version_id(context.analysis_id)
        validation_started = False
        try:
            source = self._f3_reader.read_f3_result(
                context.analysis_id, context.job_id, context.input
            )
            resolved = self._resolved_reader.read_resolved_architecture_result(
                context.analysis_id, context.job_id, context.input
            )
            candidate = self._builder.construct_candidate(source, resolved, version_id)
            context.check_cancellation()
            self._publication.reserve_candidate(candidate)
            self._publication.begin_validation(version_id, context.analysis_id)
            validation_started = True
            context.check_cancellation()
            validated = self._builder.validate(candidate)
            context.check_cancellation()
            published = self._publication.publish(validated)
        except OperationalError:
            raise
        except (
            LookupError,
            ValueError,
            ArchitectureModelError,
            ArchitecturePersistenceError,
        ) as exc:
            code = (
                "architecture_capacity_exceeded"
                if isinstance(exc, ArchitectureCapacityError)
                else (
                    "architecture_validation_failed"
                    if isinstance(exc, ArchitectureValidationError)
                    else "architecture_construction_failed"
                )
            )
            diagnostic_id = uuid4()
            result = _failure(
                context,
                self.stage_name,
                code,
                exc,
                diagnostic_id=diagnostic_id,
            )
            if validation_started:
                self._publication.record_validation_failure(
                    version_id,
                    context.analysis_id,
                    diagnostic_id=diagnostic_id,
                    failure_code=code,
                )
            return result
        context.report_progress(1, 1, "Architecture Model published")
        return StageExecutionResult(
            stage_name=self.stage_name,
            status=StageStatus.COMPLETED,
            processed_items=1,
            total_items=1,
            output_summary={"architecture_version_id": str(published.id)},
        )


def register_architecture_stage_handlers(
    registry: StageHandlerRegistry,
    *,
    f3_reader: F3ResultReader,
    resolved_reader: ResolvedArchitectureResultReader,
    resolved_writer: ResolvedArchitectureResultWriter,
    identity_service: IdentityResolutionService,
    builder: ArchitectureBuilder,
    publication: ArchitecturePublicationService,
) -> None:
    """Register the two mandatory M4 stage handlers."""
    registry.register(
        IdentityResolutionStageHandler(f3_reader, resolved_writer, identity_service)
    )
    registry.register(
        ArchitectureBuildStageHandler(f3_reader, resolved_reader, builder, publication)
    )


def _failure(
    context: ExecutionContext,
    stage_name: str,
    code: str,
    exc: Exception,
    *,
    diagnostic_id: UUID | None = None,
) -> StageExecutionResult:
    """Persist a safe shared diagnostic and return a deterministic failure."""
    logger.warning("M4 stage %s failed with %s", stage_name, code)
    message = "Architecture analysis could not produce a valid canonical model."
    context.record_diagnostic(
        AnalysisDiagnostic(
            id=diagnostic_id or uuid4(),
            analysis_id=context.analysis_id,
            job_id=context.job_id,
            stage=stage_name,
            code=code,
            category=(
                DiagnosticCategory.RESOURCE
                if isinstance(exc, ArchitectureCapacityError)
                else DiagnosticCategory.ANALYSIS
            ),
            severity=DiagnosticSeverity.ERROR,
            scope=DiagnosticScope.STAGE,
            message=message,
            retryability=FailureRetryability.NON_RETRYABLE,
            created_at=datetime.now(UTC),
            details={"exception_type": type(exc).__name__},
        )
    )
    return StageExecutionResult(
        stage_name=stage_name,
        status=StageStatus.FAILED,
        error_code=code,
        error_message=message,
    )


__all__ = [
    "ArchitectureBuildStageHandler",
    "IdentityResolutionStageHandler",
    "architecture_version_id",
    "register_architecture_stage_handlers",
]
