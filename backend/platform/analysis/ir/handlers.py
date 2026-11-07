"""Thin stage handler adapter and registration for Intermediate Representation.

Receives M1-owned F2ResultReader and F3ResultWriter ports, executes stateless M3
construction, and publishes validated immutable F3 documents to the attempt store.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from backend.platform.analysis.application.execution import (
    AnalysisStageHandler,
    ExecutionContext,
    StageExecutionResult,
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
from backend.platform.analysis.domain.event import AnalysisEventType
from backend.platform.analysis.ir.model import (
    IRCapacityLimitError,
    IRConstructionError,
    IRValidationError,
)
from backend.platform.analysis.ir.service import IRConstructionService
from backend.platform.errors import AnalysisCancelledError

if TYPE_CHECKING:
    from backend.platform.analysis.application.handoff import (
        F2ResultReader,
        F3ResultWriter,
    )
    from backend.platform.analysis.application.registry import StageHandlerRegistry

logger = logging.getLogger(__name__)


class IRConstructionStageHandler(AnalysisStageHandler):
    """M1-compatible stage adapter executing IR construction from F2 inspection."""

    def __init__(
        self,
        f2_reader: F2ResultReader,
        f3_writer: F3ResultWriter,
        service: IRConstructionService | None = None,
    ) -> None:
        self._f2_reader = f2_reader
        self._f3_writer = f3_writer
        self._service = service or IRConstructionService()

    @property
    def stage_name(self) -> str:
        """Canonical stage name per master.txt Section 9."""
        return AnalysisStageName.IR_CONSTRUCTION.value

    @property
    def is_mandatory(self) -> bool:
        """IR construction is mandatory for architecture model analysis."""
        return True

    def execute(self, context: ExecutionContext) -> StageExecutionResult:
        """Execute IR construction stage against the provided ExecutionContext."""
        context.check_cancellation()
        context.report_progress(0, 1, "Beginning IR construction")

        # 1. Retrieve F2 inspection result from attempt handoff
        try:
            f2_result = self._f2_reader.read_f2_result(
                context.analysis_id, context.job_id
            )
        except LookupError as err:
            logger.warning(
                "F2 handoff unavailable in stage %s: %s",
                self.stage_name,
                err,
            )
            diag = AnalysisDiagnostic(
                id=uuid4(),
                analysis_id=context.analysis_id,
                job_id=context.job_id,
                stage=self.stage_name,
                code="F2_HANDOFF_UNAVAILABLE",
                category=DiagnosticCategory.ORCHESTRATION,
                severity=DiagnosticSeverity.ERROR,
                scope=DiagnosticScope.STAGE,
                message=f"F2 inspection result unavailable for attempt: {err}",
                retryability=FailureRetryability.NON_RETRYABLE,
                created_at=datetime.now(UTC),
            )
            context.record_diagnostic(diag)
            return StageExecutionResult(
                stage_name=self.stage_name,
                status=StageStatus.FAILED,
                error_code="F2_UNAVAILABLE",
                error_message=str(err),
            )

        # 2. Consumer boundary verification
        if f2_result.analysis_id != context.analysis_id:
            msg = (
                f"F2 analysis_id ({f2_result.analysis_id}) does not match "
                f"context analysis_id ({context.analysis_id})"
            )
            diag = AnalysisDiagnostic(
                id=uuid4(),
                analysis_id=context.analysis_id,
                job_id=context.job_id,
                stage=self.stage_name,
                code="F2_IDENTITY_MISMATCH",
                category=DiagnosticCategory.ORCHESTRATION,
                severity=DiagnosticSeverity.ERROR,
                scope=DiagnosticScope.STAGE,
                message=msg,
                retryability=FailureRetryability.NON_RETRYABLE,
                created_at=datetime.now(UTC),
            )
            context.record_diagnostic(diag)
            return StageExecutionResult(
                stage_name=self.stage_name,
                status=StageStatus.FAILED,
                error_code="F2_IDENTITY_MISMATCH",
                error_message=msg,
            )

        if f2_result.snapshot_id != context.input.snapshot_id:
            msg = (
                f"F2 snapshot_id ({f2_result.snapshot_id}) does not match "
                f"input snapshot_id ({context.input.snapshot_id})"
            )
            diag = AnalysisDiagnostic(
                id=uuid4(),
                analysis_id=context.analysis_id,
                job_id=context.job_id,
                stage=self.stage_name,
                code="F2_SNAPSHOT_MISMATCH",
                category=DiagnosticCategory.ORCHESTRATION,
                severity=DiagnosticSeverity.ERROR,
                scope=DiagnosticScope.STAGE,
                message=msg,
                retryability=FailureRetryability.NON_RETRYABLE,
                created_at=datetime.now(UTC),
            )
            context.record_diagnostic(diag)
            return StageExecutionResult(
                stage_name=self.stage_name,
                status=StageStatus.FAILED,
                error_code="F2_SNAPSHOT_MISMATCH",
                error_message=msg,
            )

        context.check_cancellation()

        # 3. Construct and validate F3 IRDocument
        try:
            ir_doc = self._service.construct(f2_result)
        except AnalysisCancelledError:
            raise
        except IRCapacityLimitError as err:
            logger.error(
                "IR capacity limit exceeded in stage %s: %s",
                self.stage_name,
                err,
            )
            diag = AnalysisDiagnostic(
                id=uuid4(),
                analysis_id=context.analysis_id,
                job_id=context.job_id,
                stage=self.stage_name,
                code="IR_CAPACITY_LIMIT_EXCEEDED",
                category=DiagnosticCategory.RESOURCE,
                severity=DiagnosticSeverity.ERROR,
                scope=DiagnosticScope.STAGE,
                message=str(err),
                retryability=FailureRetryability.NON_RETRYABLE,
                created_at=datetime.now(UTC),
            )
            context.record_diagnostic(diag)
            return StageExecutionResult(
                stage_name=self.stage_name,
                status=StageStatus.FAILED,
                error_code="IR_CAPACITY_EXCEEDED",
                error_message=str(err),
            )
        except (IRValidationError, IRConstructionError, ValueError) as err:
            logger.error("IR construction failed in stage %s: %s", self.stage_name, err)
            diag = AnalysisDiagnostic(
                id=uuid4(),
                analysis_id=context.analysis_id,
                job_id=context.job_id,
                stage=self.stage_name,
                code="IR_CONSTRUCTION_ERROR",
                category=DiagnosticCategory.ANALYSIS,
                severity=DiagnosticSeverity.ERROR,
                scope=DiagnosticScope.STAGE,
                message=str(err),
                retryability=FailureRetryability.NON_RETRYABLE,
                created_at=datetime.now(UTC),
            )
            context.record_diagnostic(diag)
            return StageExecutionResult(
                stage_name=self.stage_name,
                status=StageStatus.FAILED,
                error_code="IR_CONSTRUCTION_FAILED",
                error_message=str(err),
            )

        context.check_cancellation()

        # 4. Publish immutable F3 document to attempt handoff
        self._f3_writer.write_f3_result(context.analysis_id, context.job_id, ir_doc)

        # 5. Report progress and complete
        entity_count = len(ir_doc.entities)
        context.report_progress(
            entity_count,
            entity_count,
            f"Constructed {entity_count} Intermediate Representation entities",
        )
        context.record_event(
            AnalysisEventType.ANALYSIS_STAGE_COMPLETED,
            {
                "stage": self.stage_name,
                "entities_count": entity_count,
                "relationships_count": len(ir_doc.relationships),
                "is_partial": ir_doc.completeness.is_partial,
            },
        )

        return StageExecutionResult(
            stage_name=self.stage_name,
            status=StageStatus.COMPLETED,
            processed_items=entity_count,
            total_items=entity_count,
            output_summary={
                "total_entities": entity_count,
                "total_relationships": len(ir_doc.relationships),
                "total_evidence": len(ir_doc.evidence),
                "total_unresolved_references": len(ir_doc.unresolved_references),
                "total_conflicts": len(ir_doc.conflicts),
                "is_partial": ir_doc.completeness.is_partial,
                "ir_schema_version": ir_doc.ir_schema_version,
            },
        )


def register_ir_stage_handler(
    registry: StageHandlerRegistry,
    f2_reader: F2ResultReader,
    f3_writer: F3ResultWriter,
    service: IRConstructionService | None = None,
) -> IRConstructionStageHandler:
    """Register IRConstructionStageHandler into the M1 stage handler registry."""
    handler = IRConstructionStageHandler(
        f2_reader=f2_reader,
        f3_writer=f3_writer,
        service=service,
    )
    registry.register(handler)
    return handler


__all__ = [
    "IRConstructionStageHandler",
    "register_ir_stage_handler",
]
