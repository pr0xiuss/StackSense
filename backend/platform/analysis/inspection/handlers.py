"""Thin M1-compatible stage adapters and attempt-scoped immutable M2 handoff."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from threading import RLock
from typing import TYPE_CHECKING
from uuid import UUID

import tree_sitter

from backend.platform.analysis.application.execution import (
    AnalysisStageHandler,
    ExecutionContext,
    StageExecutionResult,
)
from backend.platform.analysis.domain.constants import AnalysisStageName, StageStatus
from backend.platform.analysis.domain.input import AnalysisInput
from backend.platform.analysis.inspection.detection import DetectionService
from backend.platform.analysis.inspection.inventory import InventoryBuilder
from backend.platform.analysis.inspection.model import RepositoryInspectionResult
from backend.platform.analysis.inspection.service import (
    InspectionPreparation,
    RepositoryInspectionExecution,
    RepositoryInspectionService,
)
from backend.platform.analysis.syntax.javascript import TreeSitterJsTsAdapter
from backend.platform.analysis.syntax.model import SyntaxDocument
from backend.platform.analysis.syntax.python import PythonAstAdapter

if TYPE_CHECKING:
    from backend.platform.analysis.application.registry import StageHandlerRegistry


@dataclass(frozen=True, slots=True)
class M2ExecutionSignature:
    """Identity required for deterministic production or recovery rebuilding."""

    analysis_id: UUID
    snapshot_id: UUID
    source_hash: str
    input_fingerprint: str
    configuration_fingerprint: str
    analyzer_version: str
    parser_versions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _AttemptState:
    signature: M2ExecutionSignature
    preparation: InspectionPreparation | None = None
    result: RepositoryInspectionResult | None = None
    inventory_ready: bool = False
    language_detection_ready: bool = False
    framework_detection_ready: bool = False


class M2AttemptHandoff:
    """Thread-safe result handoff scoped by one analysis/job execution attempt."""

    def __init__(self) -> None:
        self._states: dict[tuple[UUID, UUID], _AttemptState] = {}
        self._lock = RLock()

    def put_state(
        self,
        analysis_id: UUID,
        job_id: UUID,
        state: _AttemptState,
    ) -> None:
        if state.signature.analysis_id != analysis_id:
            raise ValueError("M2 handoff analysis identity mismatch")
        with self._lock:
            previous = self._states.get((analysis_id, job_id))
            if previous is not None and previous.signature != state.signature:
                raise ValueError("M2 handoff signature mismatch")
            self._states[(analysis_id, job_id)] = state

    def get_state(self, analysis_id: UUID, job_id: UUID) -> _AttemptState | None:
        with self._lock:
            return self._states.get((analysis_id, job_id))

    def require_result(
        self, analysis_id: UUID, job_id: UUID
    ) -> RepositoryInspectionResult:
        state = self.get_state(analysis_id, job_id)
        if state is None or state.result is None:
            raise LookupError("Immutable F2 handoff is unavailable")
        return state.result

    def drop_result(self, analysis_id: UUID, job_id: UUID) -> None:
        """Model loss of the non-persisted F2 value while retaining its receipt."""
        with self._lock:
            state = self._states.get((analysis_id, job_id))
            if state is not None:
                self._states[(analysis_id, job_id)] = replace(state, result=None)

    def release(self, analysis_id: UUID, job_id: UUID) -> None:
        """Remove all non-persisted values for a completed execution attempt."""
        with self._lock:
            self._states.pop((analysis_id, job_id), None)


class M2ExecutionCoordinator:
    """Own staged M2 production and the M1-invoked recovery-only rebuild path."""

    def __init__(
        self,
        service: RepositoryInspectionService | None = None,
        handoff: M2AttemptHandoff | None = None,
    ) -> None:
        self._service = service or RepositoryInspectionService.from_settings()
        self.handoff = handoff or M2AttemptHandoff()
        self._detection = DetectionService()

    @staticmethod
    def signature(analysis_input: AnalysisInput) -> M2ExecutionSignature:
        config_json = json.dumps(
            asdict(analysis_input.effective_configuration),
            sort_keys=True,
            separators=(",", ":"),
        )
        fingerprint = hashlib.sha256(config_json.encode("utf-8")).hexdigest()
        input_json = json.dumps(
            {
                "analysis_id": str(analysis_input.analysis_id),
                "project_id": str(analysis_input.project_id),
                "repository_id": str(analysis_input.repository_id),
                "snapshot_id": str(analysis_input.snapshot_id),
                "revision_identifier": analysis_input.revision_identifier,
                "source_hash": analysis_input.source_hash,
                "total_files": analysis_input.total_files,
                "total_bytes": analysis_input.total_bytes,
                "artifacts": [
                    {
                        "id": str(artifact.id),
                        "revision_id": str(artifact.revision_id),
                        "path": artifact.path,
                        "size_bytes": artifact.size_bytes,
                        "content_hash": artifact.content_hash,
                        "category": artifact.category.value,
                        "support_level": artifact.support_level.value,
                    }
                    for artifact in analysis_input.artifact_catalog.artifacts
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        versions = (
            f"{PythonAstAdapter.adapter_id}:{PythonAstAdapter.adapter_version}",
            (
                f"{TreeSitterJsTsAdapter.adapter_id}:"
                f"{TreeSitterJsTsAdapter.adapter_version}:abi-"
                f"{int(tree_sitter.LANGUAGE_VERSION)}"
            ),
        )
        return M2ExecutionSignature(
            analysis_id=analysis_input.analysis_id,
            snapshot_id=analysis_input.snapshot_id,
            source_hash=analysis_input.source_hash,
            input_fingerprint=hashlib.sha256(input_json.encode("utf-8")).hexdigest(),
            configuration_fingerprint=fingerprint,
            analyzer_version=analysis_input.analyzer_version,
            parser_versions=versions,
        )

    def run_inventory(self, context: ExecutionContext) -> StageExecutionResult:
        context.check_cancellation()
        signature = self.signature(context.input)
        inventory, _ = InventoryBuilder(
            context.input.effective_configuration
        ).build_inventory(context.input.artifact_catalog.artifacts)
        preparation = InspectionPreparation(inventory, (), (), ())
        self.handoff.put_state(
            context.analysis_id,
            context.job_id,
            _AttemptState(signature, preparation, inventory_ready=True),
        )
        context.report_progress(len(inventory), len(inventory), "Inventory classified")
        return _completed(AnalysisStageName.INVENTORY, len(inventory))

    def run_language_detection(self, context: ExecutionContext) -> StageExecutionResult:
        context.check_cancellation()
        state = self._state_with_inventory(context)
        assert state.preparation is not None
        inventory = state.preparation.inventory
        languages = self._detection.detect_languages(inventory)
        runtimes = self._detection.detect_runtimes(inventory)
        preparation = replace(
            state.preparation,
            languages=languages,
            runtimes=runtimes,
        )
        self.handoff.put_state(
            context.analysis_id,
            context.job_id,
            replace(
                state,
                preparation=preparation,
                language_detection_ready=True,
            ),
        )
        context.report_progress(
            len(inventory), len(inventory), "Languages and runtimes detected"
        )
        return _completed(AnalysisStageName.LANGUAGE_DETECTION, len(inventory))

    def run_framework_detection(
        self, context: ExecutionContext
    ) -> StageExecutionResult:
        context.check_cancellation()
        state = self._state_with_languages(context)
        assert state.preparation is not None
        manifest_documents: list[SyntaxDocument] = []
        candidates, _, diagnostics = self._detection.detect_framework_candidates(
            context.input.artifact_catalog.artifacts,
            state.preparation.inventory,
            context.input.content_reader,
            context.analysis_id,
            manifest_documents=manifest_documents,
        )
        for diagnostic in diagnostics:
            context.record_diagnostic(diagnostic)
        preparation = replace(
            state.preparation,
            framework_candidates=candidates,
            diagnostics=diagnostics,
            manifest_documents=tuple(manifest_documents),
        )
        self.handoff.put_state(
            context.analysis_id,
            context.job_id,
            replace(
                state,
                preparation=preparation,
                framework_detection_ready=True,
            ),
        )
        total = len(state.preparation.inventory)
        context.report_progress(total, total, "Framework candidates detected")
        return _completed(AnalysisStageName.FRAMEWORK_DETECTION, total)

    def run_syntax_extraction(self, context: ExecutionContext) -> StageExecutionResult:
        state = self._state_with_frameworks(context)
        assert state.preparation is not None
        execution = self._service.inspect(
            context.input,
            configuration_fingerprint=state.signature.configuration_fingerprint,
            preparation=state.preparation,
            report_progress=context.report_progress,
            check_cancellation=context.check_cancellation,
        )
        for diagnostic in execution.diagnostics:
            if diagnostic not in state.preparation.diagnostics:
                context.record_diagnostic(diagnostic)
        self.handoff.put_state(
            context.analysis_id,
            context.job_id,
            replace(state, result=execution.result),
        )
        processed = execution.result.coverage.processed_artifacts
        total = execution.result.coverage.total_artifacts
        return StageExecutionResult(
            stage_name=AnalysisStageName.SYNTAX_EXTRACTION.value,
            status=StageStatus.COMPLETED,
            processed_items=processed,
            total_items=total,
            output_summary={
                "f2_version": execution.result.f2_version,
                "syntax_documents": len(execution.result.syntax_documents),
                "failed_artifacts": execution.result.coverage.failed_artifacts,
            },
        )

    def rebuild_lost_result(
        self,
        analysis_input: AnalysisInput,
        *,
        job_id: UUID,
        expected_signature: M2ExecutionSignature,
    ) -> RepositoryInspectionExecution:
        """Recovery-only rebuild called by M1 composition before an M3 consumer.

        This method does not receive an ExecutionContext and therefore cannot reopen
        stages, mutate lifecycle state, report progress, or emit public events.
        """
        actual = self.signature(analysis_input)
        if actual != expected_signature:
            raise ValueError("M2 recovery signature mismatch")
        execution = self._service.inspect(
            analysis_input,
            configuration_fingerprint=actual.configuration_fingerprint,
        )
        self.handoff.put_state(
            analysis_input.analysis_id,
            job_id,
            _AttemptState(
                actual,
                result=execution.result,
                inventory_ready=True,
                language_detection_ready=True,
                framework_detection_ready=True,
            ),
        )
        return execution

    def release_attempt(self, analysis_id: UUID, job_id: UUID) -> None:
        """Release an attempt after its downstream consumer has finished."""
        self.handoff.release(analysis_id, job_id)

    def _state_with_inventory(self, context: ExecutionContext) -> _AttemptState:
        signature = self.signature(context.input)
        state = self.handoff.get_state(context.analysis_id, context.job_id)
        if state is not None:
            if state.signature != signature:
                raise ValueError("M2 stage signature mismatch")
            if state.preparation is not None and state.inventory_ready:
                return state
        inventory, _ = InventoryBuilder(
            context.input.effective_configuration
        ).build_inventory(context.input.artifact_catalog.artifacts)
        state = _AttemptState(
            signature,
            InspectionPreparation(inventory, (), (), ()),
            inventory_ready=True,
        )
        self.handoff.put_state(context.analysis_id, context.job_id, state)
        return state

    def _state_with_languages(self, context: ExecutionContext) -> _AttemptState:
        state = self._state_with_inventory(context)
        assert state.preparation is not None
        if state.language_detection_ready:
            return state
        preparation = replace(
            state.preparation,
            languages=self._detection.detect_languages(state.preparation.inventory),
            runtimes=self._detection.detect_runtimes(state.preparation.inventory),
        )
        state = replace(
            state,
            preparation=preparation,
            language_detection_ready=True,
        )
        self.handoff.put_state(context.analysis_id, context.job_id, state)
        return state

    def _state_with_frameworks(self, context: ExecutionContext) -> _AttemptState:
        state = self._state_with_languages(context)
        assert state.preparation is not None
        if state.framework_detection_ready:
            return state
        manifest_documents: list[SyntaxDocument] = []
        candidates, _, diagnostics = self._detection.detect_framework_candidates(
            context.input.artifact_catalog.artifacts,
            state.preparation.inventory,
            context.input.content_reader,
            context.analysis_id,
            manifest_documents=manifest_documents,
        )
        preparation = replace(
            state.preparation,
            framework_candidates=candidates,
            diagnostics=diagnostics,
            manifest_documents=tuple(manifest_documents),
        )
        state = replace(
            state,
            preparation=preparation,
            framework_detection_ready=True,
        )
        self.handoff.put_state(context.analysis_id, context.job_id, state)
        return state


class _M2StageHandler(AnalysisStageHandler):
    def __init__(
        self,
        stage_name: AnalysisStageName,
        coordinator: M2ExecutionCoordinator,
    ) -> None:
        self._stage_name = stage_name
        self._coordinator = coordinator

    @property
    def stage_name(self) -> str:
        return self._stage_name.value

    def execute(self, context: ExecutionContext) -> StageExecutionResult:
        methods = {
            AnalysisStageName.INVENTORY: self._coordinator.run_inventory,
            AnalysisStageName.LANGUAGE_DETECTION: (
                self._coordinator.run_language_detection
            ),
            AnalysisStageName.FRAMEWORK_DETECTION: (
                self._coordinator.run_framework_detection
            ),
            AnalysisStageName.SYNTAX_EXTRACTION: (
                self._coordinator.run_syntax_extraction
            ),
        }
        return methods[self._stage_name](context)


def create_m2_stage_handlers(
    coordinator: M2ExecutionCoordinator,
) -> tuple[AnalysisStageHandler, ...]:
    """Create the four existing M2 stage adapters in lifecycle order."""
    return tuple(
        _M2StageHandler(stage, coordinator)
        for stage in (
            AnalysisStageName.INVENTORY,
            AnalysisStageName.LANGUAGE_DETECTION,
            AnalysisStageName.FRAMEWORK_DETECTION,
            AnalysisStageName.SYNTAX_EXTRACTION,
        )
    )


def register_m2_stage_handlers(
    registry: StageHandlerRegistry,
    coordinator: M2ExecutionCoordinator,
) -> None:
    """Register M2 handlers without coupling the coordinator to M1's registry."""
    for handler in create_m2_stage_handlers(coordinator):
        registry.register(handler)


def _completed(stage: AnalysisStageName, item_count: int) -> StageExecutionResult:
    return StageExecutionResult(
        stage_name=stage.value,
        status=StageStatus.COMPLETED,
        processed_items=item_count,
        total_items=item_count,
    )
