"""Tests for diagnostic, event, execution context, and F1 contract boundaries."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from backend.platform.analysis.application.execution import (
    AnalysisStageHandler,
    ExecutionContext,
    StageExecutionResult,
)
from backend.platform.analysis.domain.constants import (
    ANALYZER_VERSION,
    ARCHITECTURE_SCHEMA_VERSION,
    DEFAULT_MAX_DIAGNOSTICS_PER_ANALYSIS,
    F1_CONTRACT_VERSION,
    IR_SCHEMA_VERSION,
    DiagnosticCategory,
    DiagnosticScope,
    DiagnosticSeverity,
    FailureRetryability,
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
from backend.platform.analysis.domain.input import AnalysisInput
from backend.platform.errors import (
    AnalysisCancelledError,
    AnalysisIntegrityError,
)

# --- Diagnostic Contract Tests ---


def test_analysis_diagnostic_creation_and_immutability() -> None:
    now = datetime.now(UTC)
    diag = AnalysisDiagnostic(
        id=uuid4(),
        analysis_id=uuid4(),
        code="syntax_error",
        category=DiagnosticCategory.PARSING,
        severity=DiagnosticSeverity.ERROR,
        scope=DiagnosticScope.FILE,
        message="Unexpected token at line 14",
        retryability=FailureRetryability.NON_RETRYABLE,
        created_at=now,
        stage="syntax_extraction",
        details={"line": 14, "token": "foo"},
        artifact_id=uuid4(),
        artifact_path="src/index.js",
        source_line=14,
        source_column=5,
    )

    assert diag.code == "syntax_error"
    assert diag.category == DiagnosticCategory.PARSING
    assert diag.severity == DiagnosticSeverity.ERROR
    assert diag.scope == DiagnosticScope.FILE
    assert diag.retryability == FailureRetryability.NON_RETRYABLE

    with pytest.raises(AttributeError):
        diag.message = "new message"  # type: ignore[misc]


def test_bounded_diagnostic_collector_caps_and_aggregates_overflow() -> None:
    analysis_id = uuid4()
    max_limit = 5
    collector = BoundedDiagnosticCollector(
        analysis_id=analysis_id, max_diagnostics=max_limit
    )

    for i in range(max_limit):
        diag = AnalysisDiagnostic(
            id=uuid4(),
            analysis_id=analysis_id,
            code=f"code_{i}",
            category=DiagnosticCategory.PARSING,
            severity=DiagnosticSeverity.WARNING,
            scope=DiagnosticScope.FILE,
            message=f"Warning {i}",
            retryability=FailureRetryability.NON_RETRYABLE,
            created_at=datetime.now(UTC),
        )
        assert collector.add(diag) is True

    assert len(collector.diagnostics) == 5
    assert collector.is_capped is False
    assert collector.dropped_count == 0

    # Add 6th diagnostic exceeding capacity
    extra_diag = AnalysisDiagnostic(
        id=uuid4(),
        analysis_id=analysis_id,
        code="code_extra",
        category=DiagnosticCategory.PARSING,
        severity=DiagnosticSeverity.WARNING,
        scope=DiagnosticScope.FILE,
        message="Extra warning",
        retryability=FailureRetryability.NON_RETRYABLE,
        created_at=datetime.now(UTC),
    )
    assert collector.add(extra_diag) is False
    assert collector.is_capped is True
    assert collector.dropped_count == 1

    # Should have added the overflow summary diagnostic (5 original + 1 summary)
    diagnostics = collector.diagnostics
    assert len(diagnostics) == 6
    summary = diagnostics[-1]
    assert summary.code == "diagnostic_capacity_exceeded"
    assert summary.category == DiagnosticCategory.RESOURCE
    assert summary.severity == DiagnosticSeverity.WARNING


# --- Event Contract Tests ---


def test_analysis_event_creation_and_immutability() -> None:
    event_id = uuid4()
    analysis_id = uuid4()
    now = datetime.now(UTC)

    event = AnalysisEvent(
        id=event_id,
        analysis_id=analysis_id,
        sequence_number=1,
        event_type=AnalysisEventType.ANALYSIS_STARTED,
        timestamp=now,
        payload={"total_stages": 5},
    )

    assert event.sequence_number == 1
    assert event.event_type == AnalysisEventType.ANALYSIS_STARTED
    assert event.payload == {"total_stages": 5}

    with pytest.raises(AttributeError):
        event.sequence_number = 2  # type: ignore[misc]


def test_event_sequence_number_must_be_positive() -> None:
    with pytest.raises(AnalysisIntegrityError) as exc:
        AnalysisEvent(
            id=uuid4(),
            analysis_id=uuid4(),
            sequence_number=0,  # Invalid
            event_type=AnalysisEventType.ANALYSIS_CREATED,
            timestamp=datetime.now(UTC),
        )
    assert "positive" in str(exc.value.message).lower()


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "storage_key",
        "password",
        "secret",
        "token",
        "access_token",
        "source_code",
        "traceback",
    ],
)
def test_event_rejects_sensitive_payload_keys(forbidden_key: str) -> None:
    with pytest.raises(AnalysisIntegrityError) as exc:
        AnalysisEvent(
            id=uuid4(),
            analysis_id=uuid4(),
            sequence_number=1,
            event_type=AnalysisEventType.ANALYSIS_STARTED,
            timestamp=datetime.now(UTC),
            payload={forbidden_key: "leaked-secret-value"},
        )
    assert "forbidden" in str(exc.value.message).lower()


# --- Execution Context & Stage Handler Tests ---


class FakeExecutionContext(ExecutionContext):
    def __init__(
        self,
        analysis_id: UUID,
        project_id: UUID,
        job_id: UUID,
        stage_id: UUID,
        stage_name: str,
        input_bundle: AnalysisInput,
        cancellation_requested: bool = False,
    ) -> None:
        self._analysis_id = analysis_id
        self._project_id = project_id
        self._job_id = job_id
        self._stage_id = stage_id
        self._stage_name = stage_name
        self._input = input_bundle
        self._cancellation_requested = cancellation_requested
        self.reported_progress: list[tuple[int, int, str | None]] = []
        self.recorded_diagnostics: list[AnalysisDiagnostic] = []
        self.recorded_events: list[tuple[AnalysisEventType, dict[str, Any] | None]] = []

    @property
    def analysis_id(self) -> UUID:
        return self._analysis_id

    @property
    def project_id(self) -> UUID:
        return self._project_id

    @property
    def job_id(self) -> UUID:
        return self._job_id

    @property
    def stage_id(self) -> UUID:
        return self._stage_id

    @property
    def stage_name(self) -> str:
        return self._stage_name

    @property
    def input(self) -> AnalysisInput:
        return self._input

    def is_cancellation_requested(self) -> bool:
        return self._cancellation_requested

    def report_progress(
        self,
        processed_items: int,
        total_items: int,
        message: str | None = None,
    ) -> None:
        self.reported_progress.append((processed_items, total_items, message))

    def record_diagnostic(self, diagnostic: AnalysisDiagnostic) -> None:
        self.recorded_diagnostics.append(diagnostic)

    def record_event(
        self,
        event_type: AnalysisEventType,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.recorded_events.append((event_type, payload))


class FakeInventoryStageHandler(AnalysisStageHandler):
    @property
    def stage_name(self) -> str:
        return "inventory"

    def execute(self, context: ExecutionContext) -> StageExecutionResult:
        context.check_cancellation()
        context.report_progress(1, 1, "Catalog inventory completed.")
        return StageExecutionResult(
            stage_name=self.stage_name,
            status=StageStatus.COMPLETED,
            processed_items=1,
            total_items=1,
            output_summary={"artifacts_count": context.input.total_files},
        )


def test_stage_handler_execution_success() -> None:
    # Use empty/mock input bundle
    from backend.platform.analysis.domain.analysis import AnalysisConfiguration
    from backend.platform.analysis.domain.input import (
        ArtifactCatalog,
        ArtifactContentReader,
    )

    class DummyReader(ArtifactContentReader):
        def read_bytes(self, artifact: Any, max_bytes: int | None = None) -> bytes:
            return b""

        def open_stream(self, artifact: Any) -> Any:
            return None

        def exists(self, artifact: Any) -> bool:
            return True

    input_bundle = AnalysisInput(
        analysis_id=uuid4(),
        project_id=uuid4(),
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        revision_identifier="rev-1",
        source_hash="hash-1",
        total_files=0,
        total_bytes=0,
        effective_configuration=AnalysisConfiguration(),
        artifact_catalog=ArtifactCatalog(artifacts=()),
        content_reader=DummyReader(),
    )

    context = FakeExecutionContext(
        analysis_id=input_bundle.analysis_id,
        project_id=input_bundle.project_id,
        job_id=uuid4(),
        stage_id=uuid4(),
        stage_name="inventory",
        input_bundle=input_bundle,
    )

    handler = FakeInventoryStageHandler()
    result = handler.execute(context)

    assert result.stage_name == "inventory"
    assert result.status == StageStatus.COMPLETED
    assert result.processed_items == 1
    assert len(context.reported_progress) == 1


def test_stage_handler_cancellation_checkpoint_triggers() -> None:
    from backend.platform.analysis.domain.analysis import AnalysisConfiguration
    from backend.platform.analysis.domain.input import (
        ArtifactCatalog,
        ArtifactContentReader,
    )

    class DummyReader(ArtifactContentReader):
        def read_bytes(self, artifact: Any, max_bytes: int | None = None) -> bytes:
            return b""

        def open_stream(self, artifact: Any) -> Any:
            return None

        def exists(self, artifact: Any) -> bool:
            return True

    input_bundle = AnalysisInput(
        analysis_id=uuid4(),
        project_id=uuid4(),
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        revision_identifier="rev-1",
        source_hash="hash-1",
        total_files=0,
        total_bytes=0,
        effective_configuration=AnalysisConfiguration(),
        artifact_catalog=ArtifactCatalog(artifacts=()),
        content_reader=DummyReader(),
    )

    context = FakeExecutionContext(
        analysis_id=input_bundle.analysis_id,
        project_id=input_bundle.project_id,
        job_id=uuid4(),
        stage_id=uuid4(),
        stage_name="inventory",
        input_bundle=input_bundle,
        cancellation_requested=True,  # Simulate cancellation
    )

    handler = FakeInventoryStageHandler()
    with pytest.raises(AnalysisCancelledError) as exc:
        handler.execute(context)

    assert exc.value.code == "analysis_cancelled"


# --- F1 Freeze Constants Verification ---


def test_f1_freeze_version_constants() -> None:
    assert ANALYZER_VERSION == "0.1.0"
    assert IR_SCHEMA_VERSION == "1.0.0"
    assert ARCHITECTURE_SCHEMA_VERSION == "1.0.0"
    assert F1_CONTRACT_VERSION == "1.0.0"
    assert DEFAULT_MAX_DIAGNOSTICS_PER_ANALYSIS == 1000
