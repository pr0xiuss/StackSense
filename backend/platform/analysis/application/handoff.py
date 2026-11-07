"""M1-owned internal stage handoff protocols and attempt-scoped store.

Provides attempt-isolated transport for immutable stage results (F2, F3) without
modifying frozen F1 contracts or public event domains.
"""

from __future__ import annotations

from threading import RLock
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from backend.platform.analysis.inspection.model import RepositoryInspectionResult
from backend.platform.analysis.ir.model import IRDocument

if TYPE_CHECKING:
    from backend.platform.analysis.inspection.handlers import M2AttemptHandoff


class F2ResultReader(Protocol):
    """Protocol for reading immutable F2 repository inspection results."""

    def read_f2_result(
        self, analysis_id: UUID, job_id: UUID
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

    def read_f3_result(self, analysis_id: UUID, job_id: UUID) -> IRDocument:
        """Retrieve the validated immutable F3 IR document for an execution attempt."""
        ...


class AnalysisAttemptStore:
    """Thread-safe attempt-scoped store implementing F2/F3 handoff protocols.

    Maintains attempt-isolated stage outputs in memory during analysis execution.
    Does not expose stage results outside the executing attempt lifecycle.
    """

    def __init__(self, m2_handoff: M2AttemptHandoff | None = None) -> None:
        self._m2_handoff = m2_handoff
        self._f2_results: dict[tuple[UUID, UUID], RepositoryInspectionResult] = {}
        self._f3_results: dict[tuple[UUID, UUID], IRDocument] = {}
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
        with self._lock:
            self._f2_results[(analysis_id, job_id)] = result

    def read_f2_result(
        self, analysis_id: UUID, job_id: UUID
    ) -> RepositoryInspectionResult:
        """Retrieve F2 result from local store or underlying M2 handoff."""
        with self._lock:
            if (analysis_id, job_id) in self._f2_results:
                return self._f2_results[(analysis_id, job_id)]

        if self._m2_handoff is not None:
            try:
                return self._m2_handoff.require_result(analysis_id, job_id)
            except (LookupError, ValueError) as err:
                msg = (
                    f"F2 inspection result unavailable from M2 handoff for "
                    f"attempt ({analysis_id}, {job_id}): {err}"
                )
                raise LookupError(msg) from err

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
        with self._lock:
            self._f3_results[(analysis_id, job_id)] = result

    def read_f3_result(self, analysis_id: UUID, job_id: UUID) -> IRDocument:
        """Retrieve the validated immutable F3 IR document for the given attempt."""
        with self._lock:
            res = self._f3_results.get((analysis_id, job_id))
            if res is None:
                msg = (
                    f"F3 IR document unavailable for attempt "
                    f"({analysis_id}, {job_id})"
                )
                raise LookupError(msg)
            return res

    def has_f3_result(self, analysis_id: UUID, job_id: UUID) -> bool:
        """Check whether an F3 result exists for the given attempt."""
        with self._lock:
            return (analysis_id, job_id) in self._f3_results

    def release(self, analysis_id: UUID, job_id: UUID) -> None:
        """Release all attempt-scoped stage results to prevent memory leaks."""
        with self._lock:
            self._f2_results.pop((analysis_id, job_id), None)
            self._f3_results.pop((analysis_id, job_id), None)


__all__ = [
    "AnalysisAttemptStore",
    "F2ResultReader",
    "F3ResultReader",
    "F3ResultWriter",
]
