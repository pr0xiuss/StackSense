"""Stage handler registry for deterministic stage execution without importing M2-M4."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.platform.analysis.application.execution import (
    AnalysisStageHandler,
    ExecutionContext,
    StageExecutionResult,
)
from backend.platform.analysis.domain.constants import AnalysisStageName, StageStatus
from backend.platform.errors import AnalysisConfigurationError

if TYPE_CHECKING:
    pass


class StageHandlerRegistry:
    """Registry maintaining mappings of stage names to execution handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, AnalysisStageHandler] = {}

    def register(self, handler: AnalysisStageHandler) -> None:
        """Register an execution handler for its declared stage_name."""
        self._handlers[handler.stage_name] = handler

    def get(self, stage_name: str) -> AnalysisStageHandler | None:
        """Retrieve handler registered for stage_name, or None if not registered."""
        return self._handlers.get(stage_name)

    def has_handler(self, stage_name: str) -> bool:
        """Return True if a handler is registered for stage_name."""
        return stage_name in self._handlers

    def registered_stages(self) -> tuple[str, ...]:
        """Return all registered stage names."""
        return tuple(self._handlers.keys())


class InputValidationStageHandler(AnalysisStageHandler):
    """Validate the immutable F1 input boundary before downstream analysis."""

    @property
    def stage_name(self) -> str:
        return AnalysisStageName.INPUT_VALIDATION.value

    def execute(self, context: ExecutionContext) -> StageExecutionResult:
        context.check_cancellation()
        analysis_input = context.input

        if analysis_input.analysis_id != context.analysis_id:
            raise AnalysisConfigurationError(
                "AnalysisInput analysis_id does not match the executing analysis."
            )
        if analysis_input.project_id != context.project_id:
            raise AnalysisConfigurationError(
                "AnalysisInput project_id does not match the executing project."
            )
        if analysis_input.artifact_catalog.total_files != analysis_input.total_files:
            raise AnalysisConfigurationError(
                "AnalysisInput artifact count does not match its immutable manifest."
            )
        if analysis_input.artifact_catalog.total_bytes != analysis_input.total_bytes:
            raise AnalysisConfigurationError(
                "AnalysisInput byte count does not match its immutable manifest."
            )

        context.report_progress(1, 1, "Validated immutable analysis input.")
        return StageExecutionResult(
            stage_name=self.stage_name,
            status=StageStatus.COMPLETED,
            processed_items=1,
            total_items=1,
        )


def register_input_validation_handler(registry: StageHandlerRegistry) -> None:
    """Register the M1-owned immutable input validation stage."""
    registry.register(InputValidationStageHandler())


class FakeStageHandler(AnalysisStageHandler):
    """Configurable fake stage handler for testing without downstream deps."""

    def __init__(
        self,
        stage_name: str,
        *,
        is_mandatory: bool = True,
        status: StageStatus = StageStatus.COMPLETED,
        processed_items: int = 10,
        total_items: int = 10,
        error_code: str | None = None,
        error_message: str | None = None,
        output_summary: dict[str, object] | None = None,
        custom_execute_hook: object | None = None,
    ) -> None:
        self._stage_name = stage_name
        self._is_mandatory = is_mandatory
        self._status = status
        self._processed_items = processed_items
        self._total_items = total_items
        self._error_code = error_code
        self._error_message = error_message
        self._output_summary = output_summary or {}
        self._custom_execute_hook = custom_execute_hook

    @property
    def stage_name(self) -> str:
        return self._stage_name

    @property
    def is_mandatory(self) -> bool:
        return self._is_mandatory

    def execute(self, context: ExecutionContext) -> StageExecutionResult:
        context.check_cancellation()
        context.report_progress(
            self._processed_items,
            self._total_items,
            f"Executed stage {self._stage_name}",
        )

        if callable(self._custom_execute_hook):
            self._custom_execute_hook(context)

        return StageExecutionResult(
            stage_name=self._stage_name,
            status=self._status,
            processed_items=self._processed_items,
            total_items=self._total_items,
            output_summary=dict(self._output_summary),
            error_code=self._error_code,
            error_message=self._error_message,
        )


def create_fake_handler_registry(
    *,
    override_status: dict[str, StageStatus] | None = None,
    override_handlers: dict[str, AnalysisStageHandler] | None = None,
) -> StageHandlerRegistry:
    """Create a fully populated registry of fake handlers for all pipeline stages."""
    registry = StageHandlerRegistry()
    overrides = override_status or {}
    custom_handlers = override_handlers or {}

    stage_names = [
        AnalysisStageName.INPUT_VALIDATION.value,
        AnalysisStageName.INVENTORY.value,
        AnalysisStageName.LANGUAGE_DETECTION.value,
        AnalysisStageName.FRAMEWORK_DETECTION.value,
        AnalysisStageName.SYNTAX_EXTRACTION.value,
        AnalysisStageName.IR_CONSTRUCTION.value,
        AnalysisStageName.IDENTITY_RESOLUTION.value,
        AnalysisStageName.ARCHITECTURE_BUILD.value,
    ]

    for name in stage_names:
        if name in custom_handlers:
            registry.register(custom_handlers[name])
        else:
            status = overrides.get(name, StageStatus.COMPLETED)
            registry.register(FakeStageHandler(stage_name=name, status=status))

    return registry
