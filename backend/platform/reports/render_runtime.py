"""Supervised isolated runtime for bounded PDF rendering execution."""

from __future__ import annotations

import concurrent.futures
from time import monotonic

from backend.platform.delivery.contracts import ExecutionControl
from backend.platform.reports.configuration import ReportLimits
from backend.platform.reports.contracts import (
    PreparedReport,
    RenderedReport,
    ReportContractError,
)
from backend.platform.reports.pdf import ReportLabPdfRenderer


class IsolatedReportRenderRuntime:
    """Supervises PDF rendering under strict execution and deadline bounds."""

    def __init__(self, limits: ReportLimits | None = None) -> None:
        self.limits = limits or ReportLimits()
        self.renderer = ReportLabPdfRenderer()

    def execute_render(
        self,
        prepared: PreparedReport,
        timeout_seconds: float | None = None,
        control: ExecutionControl | None = None,
    ) -> RenderedReport:
        """Execute rendering with watchdog deadline enforcement and checkpoints."""
        effective_timeout = min(
            timeout_seconds or self.limits.render_timeout_seconds,
            self.limits.render_timeout_seconds,
        )

        start_time = monotonic()
        deadline = start_time + effective_timeout

        if control and control.should_stop():
            control.checkpoint()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.renderer.render, prepared, deadline, control)
            try:
                rendered = future.result(timeout=effective_timeout)
                return rendered
            except concurrent.futures.TimeoutError as exc:
                if control:
                    # Signal deadline exceeded if control supports it
                    try:
                        control.checkpoint()
                    except Exception:
                        pass
                raise TimeoutError(
                    f"PDF rendering exceeded deadline of {effective_timeout}s"
                ) from exc
            except Exception as exc:
                if isinstance(exc, (ReportContractError, TimeoutError)):
                    raise
                raise ReportContractError(f"Rendering execution failed: {exc}") from exc
