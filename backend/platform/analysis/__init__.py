"""StackSense Analysis Foundation & Execution Infrastructure (Module 1)."""

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
from backend.platform.analysis.domain.analysis import (
    Analysis,
    AnalysisCompleteness,
    AnalysisConfiguration,
    AnalysisProgress,
)
from backend.platform.analysis.domain.constants import (
    ANALYSIS_TRANSITION_MATRIX,
    ANALYZER_VERSION,
    ARCHITECTURE_SCHEMA_VERSION,
    DEFAULT_ARTIFACT_PAGE_SIZE,
    DEFAULT_MAX_ANALYSIS_DURATION_SECONDS,
    DEFAULT_MAX_DIAGNOSTICS_PER_ANALYSIS,
    DEFAULT_STAGE_TIMEOUT_SECONDS,
    F1_CONTRACT_VERSION,
    IR_SCHEMA_VERSION,
    JOB_TRANSITION_MATRIX,
    MAX_READ_BYTES_LIMIT,
    STAGE_TRANSITION_MATRIX,
    TERMINAL_ANALYSIS_STATES,
    TERMINAL_JOB_STATES,
    TERMINAL_STAGE_STATES,
    AnalysisStageName,
    AnalysisStatus,
    DiagnosticCategory,
    DiagnosticScope,
    DiagnosticSeverity,
    FailureRetryability,
    JobStatus,
    StageStatus,
)
from backend.platform.analysis.domain.diagnostic import (
    AnalysisDiagnostic,
    BoundedDiagnosticCollector,
)
from backend.platform.analysis.domain.event import (
    AnalysisEvent,
    AnalysisEventType,
)
from backend.platform.analysis.domain.input import (
    AnalysisArtifact,
    AnalysisInput,
    ArtifactCatalog,
    ArtifactContentReader,
)
from backend.platform.analysis.domain.job import (
    AnalysisJob,
    AnalysisStage,
)
from backend.platform.analysis.infra.queue import (
    AnalysisJobPayload,
    AnalysisQueuePublisher,
)
from backend.platform.analysis.repositories.analysis_repo import AnalysisRepository
from backend.platform.analysis.repositories.diagnostic_repo import DiagnosticRepository
from backend.platform.analysis.repositories.event_repo import EventRepository
from backend.platform.analysis.repositories.job_repo import (
    JobRepository,
    StageRepository,
)

__all__ = [
    "ANALYSIS_TRANSITION_MATRIX",
    "ANALYZER_VERSION",
    "ARCHITECTURE_SCHEMA_VERSION",
    "Analysis",
    "AnalysisArtifact",
    "AnalysisCompleteness",
    "AnalysisConfiguration",
    "AnalysisDiagnostic",
    "AnalysisEvent",
    "AnalysisEventType",
    "AnalysisInput",
    "AnalysisInputFactory",
    "AnalysisJob",
    "AnalysisJobPayload",
    "AnalysisOrchestrator",
    "AnalysisProgress",
    "AnalysisQueuePublisher",
    "AnalysisRepository",
    "AnalysisStage",
    "AnalysisStageHandler",
    "AnalysisStageName",
    "AnalysisStatus",
    "ArtifactCatalog",
    "ArtifactContentReader",
    "BoundedDiagnosticCollector",
    "DEFAULT_ARTIFACT_PAGE_SIZE",
    "DEFAULT_MAX_ANALYSIS_DURATION_SECONDS",
    "DEFAULT_MAX_DIAGNOSTICS_PER_ANALYSIS",
    "DEFAULT_STAGE_TIMEOUT_SECONDS",
    "DiagnosticCategory",
    "DiagnosticRepository",
    "DiagnosticScope",
    "DiagnosticSeverity",
    "EventRepository",
    "ExecutionContext",
    "F1_CONTRACT_VERSION",
    "FailureRetryability",
    "IR_SCHEMA_VERSION",
    "JOB_TRANSITION_MATRIX",
    "JobRecoveryService",
    "JobRepository",
    "JobStatus",
    "LifecycleEventEmitter",
    "MAX_READ_BYTES_LIMIT",
    "STAGE_TRANSITION_MATRIX",
    "StageExecutionResult",
    "StageHandlerRegistry",
    "StageRepository",
    "StageStatus",
    "StorageArtifactContentReader",
    "TERMINAL_ANALYSIS_STATES",
    "TERMINAL_JOB_STATES",
    "TERMINAL_STAGE_STATES",
]
