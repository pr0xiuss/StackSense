"""Application layer contracts and services for Analysis Foundation."""

from backend.platform.analysis.application.dto import (
    AnalysisCompletenessResponse,
    AnalysisDiagnosticResponse,
    AnalysisEventResponse,
    AnalysisJobResponse,
    AnalysisListResponse,
    AnalysisResponse,
    AnalysisStageResponse,
    CancelAnalysisRequest,
    CreateAnalysisRequest,
)
from backend.platform.analysis.application.events import (
    LifecycleEventEmitter,
)
from backend.platform.analysis.application.execution import (
    AnalysisStageHandler,
    ExecutionContext,
    StageExecutionResult,
)
from backend.platform.analysis.application.input_factory import (
    AnalysisInputFactory,
    StorageArtifactContentReader,
    is_safe_relative_path,
)
from backend.platform.analysis.application.lifecycle_service import (
    AnalysisLifecycleService,
)
from backend.platform.analysis.application.orchestrator import (
    AnalysisOrchestrator,
)
from backend.platform.analysis.application.recovery import (
    JobRecoveryService,
)
from backend.platform.analysis.application.registry import (
    StageHandlerRegistry,
)

__all__ = [
    "AnalysisCompletenessResponse",
    "AnalysisDiagnosticResponse",
    "AnalysisEventResponse",
    "AnalysisInputFactory",
    "AnalysisJobResponse",
    "AnalysisLifecycleService",
    "AnalysisListResponse",
    "AnalysisOrchestrator",
    "AnalysisResponse",
    "AnalysisStageHandler",
    "AnalysisStageResponse",
    "CancelAnalysisRequest",
    "CreateAnalysisRequest",
    "ExecutionContext",
    "JobRecoveryService",
    "LifecycleEventEmitter",
    "StageExecutionResult",
    "StageHandlerRegistry",
    "StorageArtifactContentReader",
    "is_safe_relative_path",
]
