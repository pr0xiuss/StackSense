"""Execution context, stage handler protocol, and result contracts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from backend.platform.analysis.domain.constants import StageStatus
from backend.platform.analysis.domain.diagnostic import AnalysisDiagnostic
from backend.platform.analysis.domain.event import AnalysisEventType
from backend.platform.analysis.domain.input import AnalysisInput
from backend.platform.errors import AnalysisCancelledError


class ExecutionContext(ABC):
    """Execution context provided to stage handlers at runtime."""

    @property
    @abstractmethod
    def analysis_id(self) -> UUID:
        """Identifier of the executing analysis."""
        raise NotImplementedError

    @property
    @abstractmethod
    def project_id(self) -> UUID:
        """Identifier of the owning project."""
        raise NotImplementedError

    @property
    @abstractmethod
    def job_id(self) -> UUID:
        """Identifier of the executing background job."""
        raise NotImplementedError

    @property
    @abstractmethod
    def stage_id(self) -> UUID:
        """Identifier of the executing stage."""
        raise NotImplementedError

    @property
    @abstractmethod
    def stage_name(self) -> str:
        """Name of the executing stage."""
        raise NotImplementedError

    @property
    @abstractmethod
    def input(self) -> AnalysisInput:
        """Authoritative immutable analysis input bundle."""
        raise NotImplementedError

    @abstractmethod
    def is_cancellation_requested(self) -> bool:
        """Check whether cooperative cancellation has been requested."""
        raise NotImplementedError

    def check_cancellation(self) -> None:
        """Raise AnalysisCancelledError if cancellation was requested."""
        if self.is_cancellation_requested():
            raise AnalysisCancelledError(
                message=(
                    f"Analysis cancellation checkpoint triggered in stage "
                    f"'{self.stage_name}'."
                ),
                details={
                    "analysis_id": str(self.analysis_id),
                    "stage_id": str(self.stage_id),
                    "stage_name": self.stage_name,
                },
            )

    @abstractmethod
    def report_progress(
        self,
        processed_items: int,
        total_items: int,
        message: str | None = None,
    ) -> None:
        """Report measurable progress for the executing stage."""
        raise NotImplementedError

    @abstractmethod
    def record_diagnostic(self, diagnostic: AnalysisDiagnostic) -> None:
        """Record an analysis diagnostic."""
        raise NotImplementedError

    @abstractmethod
    def record_event(
        self,
        event_type: AnalysisEventType,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Record a durable lifecycle event."""
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class StageExecutionResult:
    """Outcome produced by an AnalysisStageHandler."""

    stage_name: str
    status: StageStatus
    processed_items: int = 0
    total_items: int = 0
    output_summary: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    error_code: str | None = None


class AnalysisStageHandler(ABC):
    """Abstract port for analysis stage execution (implemented by M2-M4)."""

    @property
    @abstractmethod
    def stage_name(self) -> str:
        """Canonical stage name handled by this provider."""
        raise NotImplementedError

    @property
    def is_mandatory(self) -> bool:
        """Whether this stage is mandatory for analysis completion."""
        return True

    @property
    def requires_published_architecture(self) -> bool:
        """Whether successful execution requires the durable M4 publication link."""
        return False

    @abstractmethod
    def execute(self, context: ExecutionContext) -> StageExecutionResult:
        """Execute stage processing logic against the provided ExecutionContext."""
        raise NotImplementedError
