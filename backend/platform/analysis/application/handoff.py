"""M1-owned internal stage handoff protocols and attempt-scoped store.

Provides attempt-isolated transport for immutable stage results (F2, F3) without
modifying frozen F1 contracts or public event domains.
"""

from __future__ import annotations

from threading import RLock
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from backend.platform.analysis.architecture.model import ResolvedArchitectureInput
from backend.platform.analysis.inspection.model import RepositoryInspectionResult
from backend.platform.analysis.ir.model import IRDocument

if TYPE_CHECKING:
    from backend.platform.analysis.architecture.identity import (
        IdentityResolutionService,
    )
    from backend.platform.analysis.domain.input import AnalysisInput
    from backend.platform.analysis.inspection.handlers import M2ExecutionCoordinator
    from backend.platform.analysis.ir.service import IRConstructionService


class F2ResultReader(Protocol):
    """Protocol for reading immutable F2 repository inspection results."""

    def read_f2_result(
        self,
        analysis_id: UUID,
        job_id: UUID,
        analysis_input: AnalysisInput | None = None,
    ) -> RepositoryInspectionResult:
        """Retrieve the immutable F2 inspection result for an execution attempt."""
        ...


class F3ResultWriter(Protocol):
    """Protocol for writing immutable F3 intermediate representation documents."""

    def write_f3_result(
        self, analysis_id: UUID, job_id: UUID, result: IRDocument
    ) -> None:
        """Store the validated immutable F3 IR document for an execution attempt."""
        ...


class F3ResultReader(Protocol):
    """Protocol for reading immutable F3 intermediate representation documents."""

    def read_f3_result(
        self,
        analysis_id: UUID,
        job_id: UUID,
        analysis_input: AnalysisInput | None = None,
    ) -> IRDocument:
        """Retrieve the validated immutable F3 IR document for an execution attempt."""
        ...


class ResolvedArchitectureResultWriter(Protocol):
    """Protocol for the immutable identity-resolution stage result."""

    def write_resolved_architecture_result(
        self,
        analysis_id: UUID,
        job_id: UUID,
        result: ResolvedArchitectureInput,
    ) -> None: ...


class ResolvedArchitectureResultReader(Protocol):
    """M1-owned read/replay boundary between M4's two mandatory stages."""

    def read_resolved_architecture_result(
        self,
        analysis_id: UUID,
        job_id: UUID,
        analysis_input: AnalysisInput | None = None,
    ) -> ResolvedArchitectureInput: ...


class AnalysisAttemptStore:
    """Thread-safe attempt-scoped store implementing F2/F3 handoff protocols.

    Maintains attempt-isolated stage outputs in memory during analysis execution.
    Does not expose stage results outside the executing attempt lifecycle.
    """

    def __init__(
        self,
        m2_coordinator: M2ExecutionCoordinator | None = None,
        ir_service: IRConstructionService | None = None,
        identity_service: IdentityResolutionService | None = None,
    ) -> None:
        self._m2_coordinator = m2_coordinator
        self._ir_service = ir_service
        self._identity_service = identity_service
        self._f2_results: dict[tuple[UUID, UUID], RepositoryInspectionResult] = {}
        self._f3_results: dict[tuple[UUID, UUID], IRDocument] = {}
        self._resolved_architecture_results: dict[
            tuple[UUID, UUID], ResolvedArchitectureInput
        ] = {}
        self._lock = RLock()

    def set_f2_result(
        self,
        analysis_id: UUID,
        job_id: UUID,
        result: RepositoryInspectionResult,
    ) -> None:
        """Explicitly register an F2 result for testing or manual handoff."""
        if not isinstance(result, RepositoryInspectionResult):
            msg = f"Expected RepositoryInspectionResult, got {type(result).__name__}"
            raise TypeError(msg)
        if result.analysis_id != analysis_id:
            raise ValueError("F2 result analysis identity does not match attempt")
        with self._lock:
            key = (analysis_id, job_id)
            previous = self._f2_results.get(key)
            if (
                previous is not None
                and previous.to_canonical_json() != result.to_canonical_json()
            ):
                raise ValueError("Cannot replace immutable F2 result for an attempt")
            self._f2_results[key] = result

    def read_f2_result(
        self,
        analysis_id: UUID,
        job_id: UUID,
        analysis_input: AnalysisInput | None = None,
    ) -> RepositoryInspectionResult:
        """Retrieve F2, rebuilding a lost non-persisted value through M1 only."""
        with self._lock:
            if (analysis_id, job_id) in self._f2_results:
                result = self._f2_results[(analysis_id, job_id)]
                self._validate_f2_identity(result, analysis_input)
                return result

        if self._m2_coordinator is not None:
            try:
                result = self._m2_coordinator.handoff.require_result(
                    analysis_id, job_id
                )
                self._validate_f2_identity(result, analysis_input)
                return result
            except (LookupError, ValueError) as err:
                if analysis_input is None:
                    msg = (
                        "F2 inspection result unavailable from M2 handoff for "
                        f"attempt ({analysis_id}, {job_id}): {err}"
                    )
                    raise LookupError(msg) from err

                signature = self._m2_coordinator.signature(analysis_input)
                execution = self._m2_coordinator.rebuild_lost_result(
                    analysis_input,
                    job_id=job_id,
                    expected_signature=signature,
                )
                self._validate_f2_identity(execution.result, analysis_input)
                return execution.result

        msg = (
            f"F2 inspection result unavailable for attempt "
            f"({analysis_id}, {job_id})"
        )
        raise LookupError(msg)

    def write_f3_result(
        self, analysis_id: UUID, job_id: UUID, result: IRDocument
    ) -> None:
        """Store the validated immutable F3 IR document for the given attempt."""
        if not isinstance(result, IRDocument):
            msg = f"Expected IRDocument, got {type(result).__name__}"
            raise TypeError(msg)
        if result.analysis_id != analysis_id:
            raise ValueError("F3 result analysis identity does not match attempt")
        with self._lock:
            key = (analysis_id, job_id)
            previous = self._f3_results.get(key)
            if (
                previous is not None
                and previous.to_canonical_json() != result.to_canonical_json()
            ):
                raise ValueError("Cannot replace immutable F3 result for an attempt")
            self._f3_results[key] = result

    def read_f3_result(
        self,
        analysis_id: UUID,
        job_id: UUID,
        analysis_input: AnalysisInput | None = None,
    ) -> IRDocument:
        """Retrieve F3, replaying M3 through M1 after non-persisted loss."""
        with self._lock:
            res = self._f3_results.get((analysis_id, job_id))
            if res is not None:
                self._validate_f3_identity(res, analysis_input)
                return res

        if analysis_input is None or self._ir_service is None:
            msg = (
                f"F3 IR document unavailable for attempt " f"({analysis_id}, {job_id})"
            )
            raise LookupError(msg)

        f2_result = self.read_f2_result(
            analysis_id,
            job_id,
            analysis_input,
        )
        replayed = self._ir_service.construct(
            f2_result,
            expected_schema_version=analysis_input.ir_schema_version,
        )
        self._validate_f3_identity(replayed, analysis_input)
        self.write_f3_result(analysis_id, job_id, replayed)
        return replayed

    def has_f3_result(self, analysis_id: UUID, job_id: UUID) -> bool:
        """Check whether an F3 result exists for the given attempt."""
        with self._lock:
            return (analysis_id, job_id) in self._f3_results

    def write_resolved_architecture_result(
        self,
        analysis_id: UUID,
        job_id: UUID,
        result: ResolvedArchitectureInput,
    ) -> None:
        """Store an immutable identity-resolution result for this attempt."""
        if not isinstance(result, ResolvedArchitectureInput):
            raise TypeError(
                "Expected ResolvedArchitectureInput, " f"got {type(result).__name__}"
            )
        if result.analysis_id != analysis_id:
            raise ValueError("Resolved result identity does not match attempt")
        with self._lock:
            key = (analysis_id, job_id)
            previous = self._resolved_architecture_results.get(key)
            if (
                previous is not None
                and previous.to_canonical_json() != result.to_canonical_json()
            ):
                raise ValueError(
                    "Cannot replace immutable resolved result for an attempt"
                )
            self._resolved_architecture_results[key] = result

    def read_resolved_architecture_result(
        self,
        analysis_id: UUID,
        job_id: UUID,
        analysis_input: AnalysisInput | None = None,
    ) -> ResolvedArchitectureInput:
        """Read or replay M4 identity resolution without reopening a stage."""
        with self._lock:
            result = self._resolved_architecture_results.get((analysis_id, job_id))
            if result is not None:
                self._validate_resolved_identity(result, analysis_input)
                return result
        if analysis_input is None or self._identity_service is None:
            raise LookupError(
                "Resolved Architecture input unavailable for attempt "
                f"({analysis_id}, {job_id})"
            )
        f3_result = self.read_f3_result(analysis_id, job_id, analysis_input)
        result = self._identity_service.resolve(f3_result)
        self._validate_resolved_identity(result, analysis_input)
        self.write_resolved_architecture_result(analysis_id, job_id, result)
        return result

    def release(self, analysis_id: UUID, job_id: UUID) -> None:
        """Release all attempt-scoped stage results to prevent memory leaks."""
        with self._lock:
            self._f2_results.pop((analysis_id, job_id), None)
            self._f3_results.pop((analysis_id, job_id), None)
            self._resolved_architecture_results.pop((analysis_id, job_id), None)
        if self._m2_coordinator is not None:
            self._m2_coordinator.release_attempt(analysis_id, job_id)

    def _validate_f2_identity(
        self,
        result: RepositoryInspectionResult,
        analysis_input: AnalysisInput | None,
    ) -> None:
        """Reject a stale or incompatible F2 value before downstream use."""
        if analysis_input is None or self._m2_coordinator is None:
            return
        expected_values = {
            "analysis_id": analysis_input.analysis_id,
            "project_id": analysis_input.project_id,
            "repository_id": analysis_input.repository_id,
            "snapshot_id": analysis_input.snapshot_id,
            "analyzer_version": analysis_input.analyzer_version,
        }
        for field_name, expected in expected_values.items():
            if getattr(result, field_name) != expected:
                raise LookupError(f"F2 {field_name} does not match AnalysisInput")
        expected_signature = self._m2_coordinator.signature(analysis_input)
        if result.configuration_fingerprint != (
            expected_signature.configuration_fingerprint
        ):
            raise LookupError(
                "F2 configuration fingerprint does not match AnalysisInput"
            )

    def _validate_f3_identity(
        self,
        result: IRDocument,
        analysis_input: AnalysisInput | None,
    ) -> None:
        if analysis_input is None:
            return
        expected = {
            "analysis_id": analysis_input.analysis_id,
            "project_id": analysis_input.project_id,
            "repository_id": analysis_input.repository_id,
            "snapshot_id": analysis_input.snapshot_id,
            "analyzer_version": analysis_input.analyzer_version,
            "ir_schema_version": analysis_input.ir_schema_version,
        }
        for field_name, value in expected.items():
            if getattr(result, field_name) != value:
                raise LookupError(f"F3 {field_name} does not match AnalysisInput")
        if self._m2_coordinator is not None:
            expected_fingerprint = self._m2_coordinator.signature(
                analysis_input
            ).configuration_fingerprint
            if result.configuration_fingerprint != expected_fingerprint:
                raise LookupError(
                    "F3 configuration fingerprint does not match AnalysisInput"
                )

    @staticmethod
    def _validate_resolved_identity(
        result: ResolvedArchitectureInput,
        analysis_input: AnalysisInput | None,
    ) -> None:
        if analysis_input is None:
            return
        expected = {
            "analysis_id": analysis_input.analysis_id,
            "project_id": analysis_input.project_id,
            "repository_id": analysis_input.repository_id,
            "snapshot_id": analysis_input.snapshot_id,
            "analyzer_version": analysis_input.analyzer_version,
            "ir_schema_version": analysis_input.ir_schema_version,
        }
        for field_name, value in expected.items():
            if getattr(result, field_name) != value:
                raise LookupError(
                    f"Resolved Architecture {field_name} does not match AnalysisInput"
                )


__all__ = [
    "AnalysisAttemptStore",
    "F2ResultReader",
    "F3ResultReader",
    "F3ResultWriter",
    "ResolvedArchitectureResultReader",
    "ResolvedArchitectureResultWriter",
]
