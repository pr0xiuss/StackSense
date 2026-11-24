"""Bounded child-process rendering, without inherited credentials or providers."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from threading import BoundedSemaphore
from time import monotonic

from backend.platform.delivery.contracts import ExecutionControl
from backend.platform.reports.configuration import ReportLimits
from backend.platform.reports.contracts import (
    PreparedReport,
    RenderedReport,
    ReportContractError,
)

_LOCAL_RENDER_GATE = BoundedSemaphore(1)

_CHILD = """
import sys, os, resource, socket, builtins, io, json, struct
sys.path[:0] = TRUSTED_PATHS
from backend.platform.reports.pdf import ReportLabPdfRenderer
from backend.platform.reports.contracts import PreparedReport
from backend.platform.reports.configuration import ReportLimits
limits = ReportLimits.model_validate_json(LIMITS_JSON)
resource.setrlimit(resource.RLIMIT_AS, (limits.child_memory_limit_mb*1048576,)*2)
resource.setrlimit(resource.RLIMIT_CPU, (limits.render_timeout_seconds+1,)*2)
resource.setrlimit(resource.RLIMIT_FSIZE, (limits.max_pdf_bytes+16384,)*2)
resource.setrlimit(resource.RLIMIT_CORE, (0,0))
def denied(*args, **kwargs): raise PermissionError('report_renderer_io_denied')
socket.socket = denied
socket.create_connection = denied
builtins.open = denied
io.open = denied
os.open = denied
os.environ.clear()
chunks = []
size = 0
while True:
    chunk = sys.stdin.buffer.read(65536)
    if not chunk: break
    size += len(chunk)
    if size > INPUT_MAX: raise ValueError('report_limit_exceeded')
    chunks.append(chunk)
payload = b''.join(chunks)
value = json.loads(payload)
prepared = PreparedReport.model_validate_json(json.dumps(value['prepared']))
result = ReportLabPdfRenderer(limits).render(prepared, DEADLINE)
metadata = result.model_dump_json(exclude={'pdf_bytes'}).encode()
sys.stdout.buffer.write(struct.pack('!I',len(metadata))+metadata)
sys.stdout.buffer.write(result.pdf_bytes)
"""


class IsolatedReportRenderRuntime:
    def __init__(self, limits: ReportLimits | None = None) -> None:
        self.limits = limits or ReportLimits()

    def render(
        self,
        prepared: PreparedReport,
        deadline: float,
        control: ExecutionControl | None = None,
    ) -> RenderedReport:
        return self.execute_render(prepared, max(0, deadline - monotonic()), control)

    def execute_render(
        self,
        prepared: PreparedReport,
        timeout_seconds: float | None = None,
        control: ExecutionControl | None = None,
    ) -> RenderedReport:
        budget = min(
            self.limits.render_timeout_seconds,
            (
                timeout_seconds
                if timeout_seconds is not None
                else self.limits.render_timeout_seconds
            ),
        )
        deadline = monotonic() + budget
        acquired = False
        try:
            while not acquired:
                if control:
                    control.checkpoint()
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError("report_timeout")
                acquired = _LOCAL_RENDER_GATE.acquire(timeout=min(0.05, remaining))
            return self._execute_render(
                prepared, max(0, deadline - monotonic()), control
            )
        finally:
            if acquired:
                _LOCAL_RENDER_GATE.release()

    def _execute_render(
        self,
        prepared: PreparedReport,
        timeout_seconds: float | None = None,
        control: ExecutionControl | None = None,
    ) -> RenderedReport:
        import json

        import reportlab  # type: ignore[import-untyped]


        if sys.platform != "linux":
            raise ReportContractError("report_runtime_unavailable")
        prepared = PreparedReport.model_validate(prepared)
        budget = min(
            self.limits.render_timeout_seconds,
            (
                timeout_seconds
                if timeout_seconds is not None
                else self.limits.render_timeout_seconds
            ),
        )
        if budget <= 0:
            raise TimeoutError("report_timeout")
        deadline = monotonic() + budget
        payload = json.dumps(
            {
                "prepared": json.loads(prepared.model_dump_json()),
                "limits": self.limits.model_dump(mode="json"),
            }
        ).encode()
        maximum = self.limits.max_spec_bytes + self.limits.max_embedded_assets_bytes * 2
        if len(payload) > maximum:
            raise ReportContractError("report_limit_exceeded")
        trusted = [
            str(Path(__file__).resolve().parents[3]),
            str(Path(reportlab.__file__).resolve().parents[1]),
        ]
        script = (
            _CHILD.replace("TRUSTED_PATHS", repr(trusted))
            .replace("INPUT_MAX", str(maximum))
            .replace("DEADLINE", repr(deadline))
            .replace("LIMITS_JSON", repr(self.limits.model_dump_json()))
        )
        with tempfile.TemporaryDirectory(prefix="stacksense-report-") as scratch:
            with (Path(scratch) / "render.pdf").open("w+b") as stream:
                process = subprocess.Popen(
                    [sys.executable, "-I", "-c", script],
                    stdin=subprocess.PIPE,
                    stdout=stream,
                    stderr=subprocess.DEVNULL,
                    cwd=scratch,
                    env={"LANG": "C.UTF-8", "TZ": "UTC"},
                    start_new_session=True,
                    close_fds=True,
                )
                try:
                    pending: bytes | None = payload
                    while True:
                        if control:
                            control.checkpoint()
                        remaining = deadline - monotonic()
                        if remaining <= 0:
                            raise TimeoutError("report_timeout")
                        try:
                            process.communicate(
                                input=pending, timeout=min(0.05, remaining)
                            )
                            break
                        except subprocess.TimeoutExpired:
                            pending = None
                    if process.returncode != 0:
                        raise ReportContractError("report_render_failed")
                    stream.seek(0)
                    import struct

                    header = stream.read(4)
                    if len(header) != 4:
                        raise ReportContractError("report_render_failed")
                    metadata_size = struct.unpack("!I", header)[0]
                    if metadata_size > 16384:
                        raise ReportContractError("report_limit_exceeded")
                    metadata = json.loads(stream.read(metadata_size))
                    data = stream.read(self.limits.max_pdf_bytes + 1)
                    if len(data) > self.limits.max_pdf_bytes:
                        raise ReportContractError("report_limit_exceeded")
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=self.limits.watchdog_kill_grace_seconds)
                    if process.stdin:
                        process.stdin.close()
        result = RenderedReport(pdf_bytes=data, **metadata)
        if (
            result.report_spec_digest != prepared.spec.report_spec_digest
            or result.renderer_profile_digest != prepared.renderer_profile_digest
        ):
            raise ReportContractError("report_integrity_error")
        if monotonic() >= deadline:
            raise TimeoutError("report_timeout")
        return result
