"""Constants, vocabularies, and lifecycle enums for Analysis Foundation & Execution."""

from enum import StrEnum

# --- Contract & Version Constants ---
ANALYZER_VERSION: str = "0.1.0"
IR_SCHEMA_VERSION: str = "1.0.0"
ARCHITECTURE_SCHEMA_VERSION: str = "1.0.0"
F1_CONTRACT_VERSION: str = "1.0.0"

# --- Baseline Execution & Resource Limits ---
DEFAULT_MAX_ANALYSIS_DURATION_SECONDS: int = 1800  # 30 minutes (master.txt §9.38)
DEFAULT_STAGE_TIMEOUT_SECONDS: int = 600  # 10 minutes default stage timeout
DEFAULT_MAX_DIAGNOSTICS_PER_ANALYSIS: int = 1000  # Bounded diagnostic capacity
DEFAULT_ARTIFACT_PAGE_SIZE: int = 1000  # Bounded artifact pagination limit
MAX_READ_BYTES_LIMIT: int = 50 * 1024 * 1024  # 50 MB bounded read limit per file

# --- Intermediate Representation (M3) Capacity Limits ---
DEFAULT_IR_MAX_ENTITIES: int = 150_000
DEFAULT_IR_MAX_RELATIONSHIPS: int = 500_000
DEFAULT_IR_MAX_EVIDENCE: int = 500_000
DEFAULT_IR_MAX_UNRESOLVED_REFERENCES: int = 150_000
DEFAULT_IR_MAX_CONFLICTS: int = 25_000
DEFAULT_IR_MAX_SERIALIZED_BYTES: int = 512 * 1024 * 1024  # 512 MB


class AnalysisStatus(StrEnum):
    """Canonical Analysis lifecycle states per master.txt §9.8 and Section 9.

    Golden paths:
      CREATED -> QUEUED -> RUNNING -> COMPLETED
      CREATED -> FAILED
      QUEUED -> CANCELLED
      RUNNING -> CANCEL_REQUESTED -> CANCELLED
      RUNNING -> TIMEOUT -> FAILED
      RUNNING -> PARTIAL -> COMPLETED_WITH_WARNINGS
      RUNNING -> FAILED
    """

    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL = "partial"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


TERMINAL_ANALYSIS_STATES: frozenset[AnalysisStatus] = frozenset(
    {
        AnalysisStatus.COMPLETED,
        AnalysisStatus.COMPLETED_WITH_WARNINGS,
        AnalysisStatus.FAILED,
        AnalysisStatus.CANCELLED,
    }
)

ANALYSIS_TRANSITION_MATRIX: dict[AnalysisStatus, frozenset[AnalysisStatus]] = {
    AnalysisStatus.CREATED: frozenset(
        {
            AnalysisStatus.QUEUED,
            AnalysisStatus.FAILED,
        }
    ),
    AnalysisStatus.QUEUED: frozenset(
        {
            AnalysisStatus.RUNNING,
            AnalysisStatus.CANCELLED,
        }
    ),
    AnalysisStatus.RUNNING: frozenset(
        {
            AnalysisStatus.COMPLETED,
            AnalysisStatus.PARTIAL,
            AnalysisStatus.CANCEL_REQUESTED,
            AnalysisStatus.TIMEOUT,
            AnalysisStatus.FAILED,
        }
    ),
    AnalysisStatus.CANCEL_REQUESTED: frozenset(
        {
            AnalysisStatus.CANCELLED,
        }
    ),
    AnalysisStatus.TIMEOUT: frozenset(
        {
            AnalysisStatus.FAILED,
        }
    ),
    AnalysisStatus.PARTIAL: frozenset(
        {
            AnalysisStatus.COMPLETED_WITH_WARNINGS,
            AnalysisStatus.FAILED,
        }
    ),
    AnalysisStatus.COMPLETED: frozenset(),
    AnalysisStatus.COMPLETED_WITH_WARNINGS: frozenset(),
    AnalysisStatus.FAILED: frozenset(),
    AnalysisStatus.CANCELLED: frozenset(),
}


class JobStatus(StrEnum):
    """Background Job execution states per Section 9 and M1 persistence contract."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_JOB_STATES: frozenset[JobStatus] = frozenset(
    {
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    }
)

JOB_TRANSITION_MATRIX: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.PENDING: frozenset(
        {
            JobStatus.QUEUED,
            JobStatus.RUNNING,
            JobStatus.CANCELLED,
            JobStatus.FAILED,
        }
    ),
    JobStatus.QUEUED: frozenset(
        {
            JobStatus.RUNNING,
            JobStatus.CANCELLED,
            JobStatus.FAILED,
        }
    ),
    JobStatus.RUNNING: frozenset(
        {
            JobStatus.RETRYING,
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        }
    ),
    JobStatus.RETRYING: frozenset(
        {
            JobStatus.QUEUED,
            JobStatus.RUNNING,
            JobStatus.FAILED,
        }
    ),
    JobStatus.COMPLETED: frozenset(),
    JobStatus.FAILED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
}


class StageStatus(StrEnum):
    """Canonical Analysis Stage lifecycle states per master.txt §9.21 and Appendix C."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


TERMINAL_STAGE_STATES: frozenset[StageStatus] = frozenset(
    {
        StageStatus.COMPLETED,
        StageStatus.FAILED,
        StageStatus.SKIPPED,
        StageStatus.CANCELLED,
    }
)

STAGE_TRANSITION_MATRIX: dict[StageStatus, frozenset[StageStatus]] = {
    StageStatus.PENDING: frozenset(
        {
            StageStatus.QUEUED,
            StageStatus.RUNNING,
            StageStatus.SKIPPED,
            StageStatus.CANCELLED,
        }
    ),
    StageStatus.QUEUED: frozenset(
        {
            StageStatus.RUNNING,
            StageStatus.SKIPPED,
            StageStatus.CANCELLED,
        }
    ),
    StageStatus.RUNNING: frozenset(
        {
            StageStatus.COMPLETED,
            StageStatus.FAILED,
            StageStatus.CANCELLED,
        }
    ),
    StageStatus.COMPLETED: frozenset(),
    StageStatus.FAILED: frozenset(),
    StageStatus.SKIPPED: frozenset(),
    StageStatus.CANCELLED: frozenset(),
}


class AnalysisStageName(StrEnum):
    """Standard sequential stage names for the analysis engine."""

    INPUT_VALIDATION = "input_validation"
    INVENTORY = "inventory"
    LANGUAGE_DETECTION = "language_detection"
    FRAMEWORK_DETECTION = "framework_detection"
    SYNTAX_EXTRACTION = "syntax_extraction"
    IR_CONSTRUCTION = "ir_construction"
    IDENTITY_RESOLUTION = "identity_resolution"
    ARCHITECTURE_BUILD = "architecture_build"
    PROJECTION = "projection"
    DOCUMENTATION_ENRICHMENT = "documentation_enrichment"


class DiagnosticSeverity(StrEnum):
    """Diagnostic severity levels per master.txt Appendix I.6."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DiagnosticScope(StrEnum):
    """Diagnostic scopes per master.txt Appendix I.5."""

    FILE = "file"
    ARTIFACT = "artifact"
    STAGE = "stage"
    JOB = "job"
    ANALYSIS = "analysis"
    REQUEST = "request"
    RESOURCE = "resource"
    TENANT = "tenant"
    SYSTEM = "system"


class DiagnosticCategory(StrEnum):
    """Diagnostic categories per master.txt Appendix I.3."""

    INPUT = "input"
    ARTIFACT = "artifact"
    PARSING = "parsing"
    ANALYSIS = "analysis"
    ORCHESTRATION = "orchestration"
    DEPENDENCY = "dependency"
    INFRASTRUCTURE = "infrastructure"
    SECURITY = "security"
    AUTHORIZATION = "authorization"
    CONFIGURATION = "configuration"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    SYSTEM = "system"


class FailureRetryability(StrEnum):
    """Classification of failure retryability per master.txt Appendix I.1."""

    NON_RETRYABLE = "non_retryable"
    RETRYABLE = "retryable"
    CONDITIONALLY_RETRYABLE = "conditionally_retryable"
