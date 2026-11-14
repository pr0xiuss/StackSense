"""Fail-closed OS-isolated parser executor for untrusted source code."""

from __future__ import annotations

import base64
import json
import os
import queue
import struct
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4, uuid5

from backend.platform.analysis.domain.constants import (
    DiagnosticCategory,
    DiagnosticScope,
    DiagnosticSeverity,
    FailureRetryability,
)
from backend.platform.analysis.domain.diagnostic import AnalysisDiagnostic
from backend.platform.analysis.syntax.base import (
    ParserAdapter,
    ParserRequest,
    ParserResult,
    create_parsing_diagnostic,
    sanitize_diagnostic_text,
)
from backend.platform.analysis.syntax.javascript import TreeSitterJsTsAdapter
from backend.platform.analysis.syntax.model import (
    DeclarationFact,
    DeclarationKind,
    ExportFact,
    ExportKind,
    ImportFact,
    ImportKind,
    ParseStatus,
    ReferenceFact,
    ReferenceKind,
    SourceEncodingMetadata,
    SourceRange,
    SyntaxDocument,
    SyntaxFact,
)
from backend.platform.analysis.syntax.python import PythonAstAdapter


class ResultSizeExceededError(Exception):
    """Raised when parser stdout exceeds the configured IPC byte ceiling."""


class StderrOverflowError(Exception):
    """Raised when parser stderr exceeds the configured ceiling."""


class IsolationConfigurationError(Exception):
    """Raised when OS-level process isolation or limit configuration fails."""


_FRAME_HEADER = struct.Struct(">Q")


class _PersistentParserSession:
    """One reusable, sandboxed parser child owned by a single parent thread."""

    def __init__(
        self,
        *,
        python_executable: str,
        environment: dict[str, str],
        max_memory_mb: int,
        per_request_timeout_seconds: float,
        max_requests: int,
        max_stdout_bytes: int,
        max_stderr_bytes: int,
    ) -> None:
        self._max_requests = max_requests
        self._max_stdout_bytes = max_stdout_bytes
        self._max_stderr_bytes = max_stderr_bytes
        self._request_count = 0
        self._closed = False
        self._stderr = bytearray()
        self._stderr_overflow = threading.Event()
        cpu_budget = max(1.0, per_request_timeout_seconds * max_requests)
        command = [
            python_executable,
            "-m",
            "backend.platform.analysis.syntax.worker",
            "--serve",
            str(max_memory_mb),
            str(cpu_budget),
            str(max_requests),
        ]
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            env=environment,
            close_fds=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr,
            name=f"parser-stderr-{self._process.pid}",
            daemon=True,
        )
        self._stderr_thread.start()

    @property
    def usable(self) -> bool:
        return (
            not self._closed
            and self._request_count < self._max_requests
            and self._process.poll() is None
        )

    def _drain_stderr(self) -> None:
        stream = self._process.stderr
        if stream is None:
            return
        try:
            while True:
                chunk = stream.read(65_536)
                if not chunk:
                    return
                if len(self._stderr) + len(chunk) > self._max_stderr_bytes:
                    self._stderr_overflow.set()
                    self._terminate()
                    return
                self._stderr.extend(chunk)
        except Exception:
            return

    @staticmethod
    def _read_exact(stream: Any, size: int) -> bytes:
        chunks: list[bytes] = []
        remaining = size
        while remaining:
            chunk = stream.read(remaining)
            if not chunk:
                raise EOFError("Parser response frame ended unexpectedly")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _read_response(self) -> bytes:
        stream = self._process.stdout
        if stream is None:
            raise IsolationConfigurationError("Parser child stdout is unavailable")
        header = self._read_exact(stream, _FRAME_HEADER.size)
        response_size = _FRAME_HEADER.unpack(header)[0]
        if response_size > self._max_stdout_bytes:
            raise ResultSizeExceededError(
                "Parser IPC output size exceeded allowed ceiling of "
                f"{self._max_stdout_bytes} bytes"
            )
        return self._read_exact(stream, response_size)

    def execute(self, payload: bytes, timeout_seconds: float) -> bytes:
        if not self.usable:
            raise IsolationConfigurationError("Parser worker session is unavailable")
        stream = self._process.stdin
        if stream is None:
            raise IsolationConfigurationError("Parser child stdin is unavailable")
        result: list[bytes] = []
        error: list[BaseException] = []

        def write_request() -> None:
            try:
                stream.write(_FRAME_HEADER.pack(len(payload)))
                stream.write(payload)
                stream.flush()
            except BaseException as exc:
                error.append(exc)

        def read_response() -> None:
            try:
                result.append(self._read_response())
            except BaseException as exc:  # retained and re-raised by owner thread
                error.append(exc)

        started = time.monotonic()
        writer = threading.Thread(target=write_request, daemon=True)
        reader = threading.Thread(target=read_response, daemon=True)
        writer.start()
        reader.start()
        writer.join(timeout=timeout_seconds)
        remaining = max(0.0, timeout_seconds - (time.monotonic() - started))
        reader.join(timeout=remaining)
        if writer.is_alive() or reader.is_alive():
            self._terminate()
            writer.join(timeout=2.0)
            reader.join(timeout=2.0)
            raise subprocess.TimeoutExpired(
                cmd=self._process.args, timeout=timeout_seconds
            )
        if self._stderr_overflow.is_set():
            raise StderrOverflowError(
                "Parser stderr exceeded allowed ceiling of "
                f"{self._max_stderr_bytes} bytes"
            )
        if error:
            self._terminate()
            raise error[0]
        if not result:
            self._terminate()
            raise IsolationConfigurationError("Parser worker returned no response")
        self._request_count += 1
        return result[0]

    def _terminate(self) -> None:
        if self._process.poll() is None:
            try:
                self._process.kill()
            except Exception:
                pass

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._process.poll() is None and self._process.stdin is not None:
            try:
                self._process.stdin.write(_FRAME_HEADER.pack(0))
                self._process.stdin.flush()
                self._process.wait(timeout=1.0)
            except Exception:
                self._terminate()
        try:
            self._process.wait(timeout=2.0)
        except Exception:
            self._terminate()
        for stream in (
            self._process.stdin,
            self._process.stdout,
            self._process.stderr,
        ):
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
        self._stderr_thread.join(timeout=2.0)


class ParserExecutor:
    """Manages parsing execution within hard OS process and timeout boundaries."""

    def __init__(
        self,
        python_executable: str | None = None,
        default_timeout_seconds: float = 30.0,
        max_file_size_bytes: int = 5 * 1024 * 1024,
        max_memory_mb: int = 512,
        max_ipc_result_bytes: int = 50 * 1024 * 1024,
        max_stderr_bytes: int = 1024 * 1024,
        max_facts_per_artifact: int = 25_000,
        worker_count: int = 4,
        worker_max_requests: int = 64,
    ) -> None:
        self._python_executable = python_executable or sys.executable
        self._default_timeout_seconds = default_timeout_seconds
        self._max_file_size_bytes = max_file_size_bytes
        self._max_memory_mb = max_memory_mb
        self._max_ipc_result_bytes = max_ipc_result_bytes
        self._max_stderr_bytes = max_stderr_bytes
        if max_facts_per_artifact <= 0:
            raise ValueError("max_facts_per_artifact must be positive")
        if worker_count <= 0 or worker_max_requests <= 0:
            raise ValueError("Parser worker limits must be positive")
        self._max_facts_per_artifact = max_facts_per_artifact
        self._worker_count = worker_count
        self._worker_max_requests = worker_max_requests
        self._isolation_available: bool | None = None
        self._in_process_adapters: dict[str, ParserAdapter] = {
            "python": PythonAstAdapter(),
            "javascript": TreeSitterJsTsAdapter(),
            "typescript": TreeSitterJsTsAdapter(),
            "jsx": TreeSitterJsTsAdapter(),
            "tsx": TreeSitterJsTsAdapter(),
        }

    @property
    def worker_count(self) -> int:
        """Configured upper bound for concurrent isolated parser workers."""
        return self._worker_count

    @classmethod
    def from_settings(
        cls,
        settings: Any = None,
        python_executable: str | None = None,
        max_ipc_result_bytes: int | None = None,
    ) -> ParserExecutor:
        """Construct a ParserExecutor wired to platform settings."""
        if settings is None:
            from backend.platform.config import get_settings

            settings = get_settings()

        kwargs: dict[str, Any] = {
            "default_timeout_seconds": settings.parser_per_file_timeout_seconds,
            "max_file_size_bytes": settings.parser_max_file_size_bytes,
            "max_memory_mb": settings.parser_max_memory_mb,
            "max_stderr_bytes": getattr(
                settings, "parser_max_stderr_bytes", 1024 * 1024
            ),
            "max_facts_per_artifact": settings.parser_max_facts_per_artifact,
            "worker_count": settings.parser_worker_count,
            "worker_max_requests": settings.parser_worker_max_requests,
        }
        if python_executable is not None:
            kwargs["python_executable"] = python_executable
        if max_ipc_result_bytes is not None:
            kwargs["max_ipc_result_bytes"] = max_ipc_result_bytes

        return cls(**kwargs)

    def _build_sanitized_environment(self) -> dict[str, str]:
        """Construct a minimal allowlisted environment free of credentials or tokens."""
        allowlist_prefixes = (
            "SYSTEMROOT",
            "COMSPEC",
            "WINDIR",
            "TMP",
            "TEMP",
            "SYSTEMDRIVE",
            "TMPDIR",
            "LANG",
            "LC_",
        )
        denylist_substrings = (
            "SECRET",
            "KEY",
            "TOKEN",
            "PASSWORD",
            "CREDENTIAL",
            "DATABASE",
            "POSTGRES",
            "CELERY",
            "RABBITMQ",
            "AMQP",
            "AWS",
            "AZURE",
            "GCP",
            "GITHUB",
        )

        clean_env: dict[str, str] = {}
        for k, v in os.environ.items():
            k_upper = k.upper()
            if any(k_upper.startswith(prefix) for prefix in allowlist_prefixes):
                if not any(deny in k_upper for deny in denylist_substrings):
                    clean_env[k] = v

        # Add repository root to PYTHONPATH
        repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        clean_env["PYTHONPATH"] = str(repo_root)
        clean_env["PYTHONUNBUFFERED"] = "1"
        clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
        clean_env["PYTHONNOUSERSITE"] = "1"
        return clean_env

    def is_isolation_available(self) -> bool:
        """Verify that the child process isolation boundary is functional."""
        if self._isolation_available is not None:
            return self._isolation_available
        try:
            if sys.platform == "win32":
                job = self._create_windows_job_object()
                if not job:
                    self._isolation_available = False
                    return False
                import ctypes

                ctypes.windll.kernel32.CloseHandle(job)

            cmd = [
                self._python_executable,
                "-m",
                "backend.platform.analysis.syntax.worker",
                "--probe",
                str(self._max_memory_mb),
                "5.0",
            ]
            env = self._build_sanitized_environment()
            res = subprocess.run(
                cmd,
                capture_output=True,
                timeout=5.0,
                env=env,
                check=False,
            )
            self._isolation_available = res.returncode == 0 and json.loads(
                res.stdout.decode("utf-8")
            ) == {"sandbox": "ready"}
        except Exception:
            self._isolation_available = False
        return self._isolation_available

    def _create_windows_job_object(self) -> Any:
        """Create a Win32 Job Object with process memory limits and kill-on-close."""
        if sys.platform != "win32":
            return None
        import ctypes
        from ctypes import wintypes

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryLimit", ctypes.c_size_t),
                ("PeakJobMemoryLimit", ctypes.c_size_t),
            ]

        job = ctypes.windll.kernel32.CreateJobObjectW(None, None)
        if not job:
            err = ctypes.GetLastError()
            raise IsolationConfigurationError(
                f"CreateJobObjectW failed with Win32 error {err}"
            )

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        # 0x0100: JOB_OBJECT_LIMIT_PROCESS_MEMORY
        # 0x2000: JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        info.BasicLimitInformation.LimitFlags = 0x0100 | 0x2000
        info.ProcessMemoryLimit = self._max_memory_mb * 1024 * 1024
        success = ctypes.windll.kernel32.SetInformationJobObject(
            job, 9, ctypes.byref(info), ctypes.sizeof(info)
        )
        if not success:
            err = ctypes.GetLastError()
            ctypes.windll.kernel32.CloseHandle(job)
            raise IsolationConfigurationError(
                f"SetInformationJobObject failed with Win32 error {err}"
            )

        return job

    def _assign_windows_job_object(self, job: Any, proc: subprocess.Popen[Any]) -> None:
        """Assign child process to Windows Job Object, validating the return value."""
        if sys.platform != "win32" or job is None:
            return
        import ctypes

        handle = getattr(proc, "_handle", None)
        if handle is None:
            raise IsolationConfigurationError("Child process handle is None on Windows")

        success = ctypes.windll.kernel32.AssignProcessToJobObject(job, int(handle))
        if not success:
            err = ctypes.GetLastError()
            raise IsolationConfigurationError(
                f"AssignProcessToJobObject failed with Win32 error {err}"
            )

    def _communicate_bounded(
        self,
        proc: subprocess.Popen[Any],
        input_data: bytes,
        deadline: float,
        max_stdout_bytes: int,
        max_stderr_bytes: int,
    ) -> tuple[bytes, bytes]:
        """Read stdout and stderr in chunks up to strict bounds with bounded joins."""
        stdout_chunks: list[bytes] = []
        stderr_chunks: list[bytes] = []
        stdout_bytes = 0
        stderr_bytes = 0
        overflow_reason: list[str] = []
        overflow_lock = threading.Lock()

        def write_stdin() -> None:
            if proc.stdin is None:
                return
            try:
                proc.stdin.write(input_data)
                proc.stdin.flush()
            except BrokenPipeError, OSError:
                pass
            finally:
                try:
                    proc.stdin.close()
                except Exception:
                    pass

        def read_stream(
            stream: Any,
            chunks: list[bytes],
            max_bytes: int,
            reason: str,
        ) -> None:
            nonlocal stdout_bytes, stderr_bytes
            try:
                while True:
                    chunk = stream.read(65536)
                    if not chunk:
                        break
                    with overflow_lock:
                        current = stdout_bytes if reason == "stdout" else stderr_bytes
                        if current + len(chunk) > max_bytes:
                            if not overflow_reason:
                                overflow_reason.append(reason)
                            try:
                                proc.kill()
                            except Exception:
                                pass
                            break
                        chunks.append(chunk)
                        if reason == "stdout":
                            stdout_bytes += len(chunk)
                        else:
                            stderr_bytes += len(chunk)
            except Exception:
                pass
            finally:
                try:
                    stream.close()
                except Exception:
                    pass

        t_in = threading.Thread(target=write_stdin, daemon=True)
        t_out = threading.Thread(
            target=read_stream,
            args=(proc.stdout, stdout_chunks, max_stdout_bytes, "stdout"),
            daemon=True,
        )
        t_err = threading.Thread(
            target=read_stream,
            args=(proc.stderr, stderr_chunks, max_stderr_bytes, "stderr"),
            daemon=True,
        )

        t_in.start()
        t_out.start()
        t_err.start()

        timed_out = False
        try:
            proc.wait(timeout=deadline)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                proc.kill()
                proc.wait(timeout=2.0)
            except Exception:
                pass

        t_in.join(timeout=2.0)
        t_out.join(timeout=2.0)
        t_err.join(timeout=2.0)

        if timed_out:
            raise subprocess.TimeoutExpired(cmd=proc.args, timeout=deadline)

        if t_in.is_alive() or t_out.is_alive() or t_err.is_alive():
            try:
                proc.kill()
            except Exception:
                pass
            raise IsolationConfigurationError(
                "Parser IPC threads did not terminate within their bounded "
                "cleanup window"
            )

        with overflow_lock:
            if overflow_reason:
                if overflow_reason[0] == "stdout":
                    raise ResultSizeExceededError(
                        f"Parser IPC output size exceeded allowed ceiling of "
                        f"{max_stdout_bytes} bytes"
                    )
                else:
                    raise StderrOverflowError(
                        f"Parser stderr output size exceeded allowed ceiling of "
                        f"{max_stderr_bytes} bytes"
                    )

        return b"".join(stdout_chunks), b"".join(stderr_chunks)

    def execute_in_process(self, request: ParserRequest) -> ParserResult:
        """Execute parsing in-process (used for benchmarks and testing comparison)."""
        norm_lang = request.language.lower().strip()
        adapter = self._in_process_adapters.get(norm_lang)
        if adapter is None:
            diag = create_parsing_diagnostic(
                analysis_id=request.analysis_id,
                artifact_id=request.artifact_id,
                artifact_path=request.path,
                code="unsupported_parser_language",
                message=f"No parser adapter available for language: {request.language}",
                severity=DiagnosticSeverity.ERROR,
            )
            return ParserResult(
                success=False,
                document=None,
                diagnostics=(diag,),
                error_message=f"Unsupported language: {request.language}",
            )
        return adapter.parse(request)

    def _request_bytes(self, request: ParserRequest) -> bytes:
        max_bytes = min(request.max_file_size_bytes, self._max_file_size_bytes)
        payload = {
            "artifact_id": str(request.artifact_id),
            "path": request.path,
            "language": request.language,
            "content_b64": base64.b64encode(request.content).decode("ascii"),
            "analysis_id": str(request.analysis_id) if request.analysis_id else None,
            "configuration_fingerprint": request.configuration_fingerprint,
            "deadline_seconds": (
                request.deadline_seconds or self._default_timeout_seconds
            ),
            "max_file_size_bytes": max_bytes,
            "max_facts_per_artifact": min(
                request.max_facts_per_artifact, self._max_facts_per_artifact
            ),
            "sandbox_max_memory_mb": self._max_memory_mb,
            "sandbox_cpu_seconds": (
                request.deadline_seconds or self._default_timeout_seconds
            ),
        }
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")

    def _execution_failure(
        self,
        request: ParserRequest,
        exc: BaseException,
        elapsed: float,
    ) -> ParserResult:
        if isinstance(exc, subprocess.TimeoutExpired):
            resolved_analysis_id = request.analysis_id or request.artifact_id
            deadline = request.deadline_seconds or self._default_timeout_seconds
            diagnostic = AnalysisDiagnostic(
                id=uuid5(
                    resolved_analysis_id,
                    f"m2:parser_timeout:{request.path}:{deadline}",
                ),
                analysis_id=resolved_analysis_id,
                code="parser_timeout",
                category=DiagnosticCategory.TIMEOUT,
                severity=DiagnosticSeverity.ERROR,
                scope=DiagnosticScope.FILE,
                message=f"Parser execution exceeded deadline of {deadline} seconds",
                retryability=FailureRetryability.NON_RETRYABLE,
                created_at=datetime.now(UTC),
                stage="syntax_extraction",
                artifact_id=request.artifact_id,
                artifact_path=request.path,
            )
            message = "Parser process timed out"
        elif isinstance(exc, ResultSizeExceededError):
            diagnostic = create_parsing_diagnostic(
                request.analysis_id,
                request.artifact_id,
                request.path,
                "parser_result_size_exceeded",
                str(exc),
                DiagnosticSeverity.ERROR,
            )
            message = "Parser IPC result size ceiling exceeded"
        elif isinstance(exc, StderrOverflowError):
            diagnostic = create_parsing_diagnostic(
                request.analysis_id,
                request.artifact_id,
                request.path,
                "parser_stderr_overflow",
                str(exc),
                DiagnosticSeverity.ERROR,
            )
            message = "Parser stderr size ceiling exceeded"
        else:
            diagnostic = create_parsing_diagnostic(
                request.analysis_id,
                request.artifact_id,
                request.path,
                "parser_process_failed",
                f"Failed to execute parser child process: {type(exc).__name__}",
                DiagnosticSeverity.ERROR,
            )
            message = sanitize_diagnostic_text(str(exc))
        return ParserResult(
            success=False,
            document=None,
            diagnostics=(diagnostic,),
            execution_time_seconds=elapsed,
            error_message=message,
        )

    def _decode_response(
        self,
        request: ParserRequest,
        response_bytes: bytes,
        elapsed: float,
    ) -> ParserResult:
        try:
            data = json.loads(response_bytes.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            diagnostic = create_parsing_diagnostic(
                request.analysis_id,
                request.artifact_id,
                request.path,
                "parser_ipc_error",
                f"Malformed parser child output: {exc}",
                DiagnosticSeverity.ERROR,
            )
            return ParserResult(
                success=False,
                document=None,
                diagnostics=(diagnostic,),
                execution_time_seconds=elapsed,
                error_message=f"IPC error: {exc}",
            )

        document = None
        if data.get("document") is not None:
            document = self._deserialize_document(data["document"])

        diagnostics = []
        for item in data.get("diagnostics", []):
            diagnostics.append(
                AnalysisDiagnostic(
                    id=UUID(item["id"]),
                    analysis_id=request.analysis_id or uuid4(),
                    code=item["code"],
                    category=DiagnosticCategory(item["category"]),
                    severity=DiagnosticSeverity(item["severity"]),
                    scope=DiagnosticScope(item["scope"]),
                    message=item["message"],
                    retryability=FailureRetryability(item["retryability"]),
                    created_at=datetime.now(UTC),
                    stage=item.get("stage", "syntax_extraction"),
                    artifact_id=(
                        UUID(item["artifact_id"]) if item.get("artifact_id") else None
                    ),
                    artifact_path=item.get("artifact_path"),
                    source_line=item.get("source_line"),
                    source_column=item.get("source_column"),
                    details=item.get("details", {}),
                )
            )

        framework_hints: dict[str, dict[str, str]] = {}
        raw_hints = data.get("framework_hints", {})
        if isinstance(raw_hints, dict):
            for fact_key, raw_values in raw_hints.items():
                if isinstance(fact_key, str) and isinstance(raw_values, dict):
                    framework_hints[fact_key] = {
                        str(key): str(value)
                        for key, value in raw_values.items()
                        if isinstance(key, str) and isinstance(value, str)
                    }

        return ParserResult(
            success=data.get("success", True),
            document=document,
            diagnostics=tuple(diagnostics),
            execution_time_seconds=elapsed,
            error_message=(
                sanitize_diagnostic_text(str(data["error_message"]))
                if data.get("error_message") is not None
                else None
            ),
            framework_hints=framework_hints,
        )

    def execute_many(
        self,
        requests: Sequence[ParserRequest],
        *,
        on_complete: Callable[[int], None] | None = None,
        check_cancellation: Callable[[], None] | None = None,
    ) -> tuple[ParserResult, ...]:
        """Parse requests concurrently through reusable isolated child processes.

        Results retain input order regardless of worker completion order. Each child
        is sandboxed before it accepts source bytes and is discarded after a bounded
        number of requests, on timeout, or on any transport failure.
        """
        ordered_requests = tuple(requests)
        if not ordered_requests:
            return ()
        if not self.is_isolation_available():
            return tuple(self.execute(request) for request in ordered_requests)

        worker_count = min(self._worker_count, len(ordered_requests))
        worker_cpu_timeout = max(
            request.deadline_seconds or self._default_timeout_seconds
            for request in ordered_requests
        )
        work: queue.Queue[tuple[int, ParserRequest]] = queue.Queue()
        completions: queue.Queue[int] = queue.Queue()
        for index, request in enumerate(ordered_requests):
            work.put((index, request))
        results: list[ParserResult | None] = [None] * len(ordered_requests)
        stop = threading.Event()
        sessions: list[_PersistentParserSession] = []
        sessions_lock = threading.Lock()

        def run_worker() -> None:
            session: _PersistentParserSession | None = None
            try:
                while not stop.is_set():
                    try:
                        index, request = work.get_nowait()
                    except queue.Empty:
                        return
                    started = time.perf_counter()
                    try:
                        max_bytes = min(
                            request.max_file_size_bytes,
                            self._max_file_size_bytes,
                        )
                        if len(request.content) > max_bytes:
                            diagnostic = create_parsing_diagnostic(
                                request.analysis_id,
                                request.artifact_id,
                                request.path,
                                "file_size_exceeded",
                                (
                                    "File exceeds maximum allowed size of "
                                    f"{max_bytes} bytes"
                                ),
                                DiagnosticSeverity.ERROR,
                            )
                            results[index] = ParserResult(
                                success=False,
                                document=None,
                                diagnostics=(diagnostic,),
                                execution_time_seconds=(time.perf_counter() - started),
                                error_message="File size ceiling exceeded",
                            )
                            completions.put(index)
                            work.task_done()
                            continue
                        if session is None or not session.usable:
                            if session is not None:
                                session.close()
                            session = _PersistentParserSession(
                                python_executable=self._python_executable,
                                environment=self._build_sanitized_environment(),
                                max_memory_mb=self._max_memory_mb,
                                per_request_timeout_seconds=worker_cpu_timeout,
                                max_requests=self._worker_max_requests,
                                max_stdout_bytes=self._max_ipc_result_bytes,
                                max_stderr_bytes=self._max_stderr_bytes,
                            )
                            with sessions_lock:
                                sessions.append(session)
                        response = session.execute(
                            self._request_bytes(request),
                            request.deadline_seconds or self._default_timeout_seconds,
                        )
                        result = self._decode_response(
                            request,
                            response,
                            time.perf_counter() - started,
                        )
                    except BaseException as exc:
                        if session is not None:
                            session.close()
                            session = None
                        result = self._execution_failure(
                            request,
                            exc,
                            time.perf_counter() - started,
                        )
                    results[index] = result
                    completions.put(index)
                    work.task_done()
            finally:
                if session is not None:
                    session.close()

        workers = [
            threading.Thread(
                target=run_worker,
                name=f"parser-pool-{index + 1}",
                daemon=True,
            )
            for index in range(worker_count)
        ]
        for worker in workers:
            worker.start()

        completed = 0
        try:
            while completed < len(ordered_requests):
                if check_cancellation is not None:
                    check_cancellation()
                try:
                    completed_index = completions.get(timeout=0.1)
                except queue.Empty:
                    if not any(worker.is_alive() for worker in workers):
                        break
                    continue
                completed += 1
                if on_complete is not None:
                    on_complete(completed_index)
        except BaseException:
            stop.set()
            with sessions_lock:
                for session in sessions:
                    session.close()
            raise
        finally:
            for worker in workers:
                worker.join(timeout=self._default_timeout_seconds + 3.0)

        if any(result is None for result in results):
            raise IsolationConfigurationError(
                "Parser pool terminated before every request completed"
            )
        return tuple(result for result in results if result is not None)

    def _cleanup_process(
        self,
        proc: subprocess.Popen[Any] | None,
        win_job: Any | None,
    ) -> None:
        """Unified cleanup ensuring child process termination and handle releases."""
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=2.0)
            except Exception:
                pass
            finally:
                for stream in (proc.stdin, proc.stdout, proc.stderr):
                    if stream is not None:
                        try:
                            stream.close()
                        except Exception:
                            pass

        if win_job is not None and sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.kernel32.CloseHandle(win_job)
            except Exception:
                pass

    def execute(self, request: ParserRequest) -> ParserResult:
        """Execute parsing within a dedicated, fail-closed OS child process."""
        start_time = time.perf_counter()

        # Fail closed immediately if process isolation is unavailable
        if not self.is_isolation_available():
            diag = create_parsing_diagnostic(
                analysis_id=request.analysis_id,
                artifact_id=request.artifact_id,
                artifact_path=request.path,
                code="parser_isolation_unavailable",
                message=(
                    "OS child process isolation boundary is unavailable or "
                    "non-functional"
                ),
                severity=DiagnosticSeverity.ERROR,
            )
            return ParserResult(
                success=False,
                document=None,
                diagnostics=(diag,),
                execution_time_seconds=time.perf_counter() - start_time,
                error_message="Parser isolation boundary unavailable",
            )

        # Enforce file size ceiling before invoking child
        max_bytes = min(request.max_file_size_bytes, self._max_file_size_bytes)
        if len(request.content) > max_bytes:
            diag = create_parsing_diagnostic(
                analysis_id=request.analysis_id,
                artifact_id=request.artifact_id,
                artifact_path=request.path,
                code="file_size_exceeded",
                message=f"File exceeds maximum allowed size of {max_bytes} bytes",
                severity=DiagnosticSeverity.ERROR,
            )
            return ParserResult(
                success=False,
                document=None,
                diagnostics=(diag,),
                execution_time_seconds=time.perf_counter() - start_time,
                error_message="File size ceiling exceeded",
            )

        deadline = request.deadline_seconds or self._default_timeout_seconds
        env = self._build_sanitized_environment()

        req_payload = {
            "artifact_id": str(request.artifact_id),
            "path": request.path,
            "language": request.language,
            "content_b64": base64.b64encode(request.content).decode("ascii"),
            "analysis_id": str(request.analysis_id) if request.analysis_id else None,
            "configuration_fingerprint": request.configuration_fingerprint,
            "deadline_seconds": deadline,
            "max_file_size_bytes": max_bytes,
            "max_facts_per_artifact": min(
                request.max_facts_per_artifact, self._max_facts_per_artifact
            ),
            "sandbox_max_memory_mb": self._max_memory_mb,
            "sandbox_cpu_seconds": deadline,
        }
        input_data = json.dumps(req_payload)

        cmd = [self._python_executable, "-m", "backend.platform.analysis.syntax.worker"]

        proc = None
        win_job = None
        try:
            if sys.platform == "win32":
                try:
                    win_job = self._create_windows_job_object()
                except IsolationConfigurationError as job_err:
                    diag = create_parsing_diagnostic(
                        analysis_id=request.analysis_id,
                        artifact_id=request.artifact_id,
                        artifact_path=request.path,
                        code="parser_isolation_failed",
                        message=f"Windows Job Object initialization failed: {job_err}",
                        severity=DiagnosticSeverity.ERROR,
                    )
                    return ParserResult(
                        success=False,
                        document=None,
                        diagnostics=(diag,),
                        execution_time_seconds=time.perf_counter() - start_time,
                        error_message=str(job_err),
                    )

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=False,
                    env=env,
                    close_fds=True,
                )
            except Exception as popen_err:
                diag = create_parsing_diagnostic(
                    analysis_id=request.analysis_id,
                    artifact_id=request.artifact_id,
                    artifact_path=request.path,
                    code="parser_isolation_failed",
                    message=f"Failed to spawn isolated parser process: {popen_err}",
                    severity=DiagnosticSeverity.ERROR,
                )
                return ParserResult(
                    success=False,
                    document=None,
                    diagnostics=(diag,),
                    execution_time_seconds=time.perf_counter() - start_time,
                    error_message=str(popen_err),
                )

            # Assign child to Windows Job Object immediately
            if win_job is not None and sys.platform == "win32":
                try:
                    self._assign_windows_job_object(win_job, proc)
                except IsolationConfigurationError as assign_err:
                    try:
                        proc.kill()
                        proc.wait(timeout=2.0)
                    except Exception:
                        pass
                    diag = create_parsing_diagnostic(
                        analysis_id=request.analysis_id,
                        artifact_id=request.artifact_id,
                        artifact_path=request.path,
                        code="parser_isolation_failed",
                        message=(
                            f"Failed to assign parser process to Job Object: "
                            f"{assign_err}"
                        ),
                        severity=DiagnosticSeverity.ERROR,
                    )
                    return ParserResult(
                        success=False,
                        document=None,
                        diagnostics=(diag,),
                        execution_time_seconds=time.perf_counter() - start_time,
                        error_message=str(assign_err),
                    )

            stdout_bytes, stderr_bytes = self._communicate_bounded(
                proc=proc,
                input_data=input_data.encode("utf-8"),
                deadline=deadline,
                max_stdout_bytes=self._max_ipc_result_bytes,
                max_stderr_bytes=self._max_stderr_bytes,
            )

        except subprocess.TimeoutExpired:
            resolved_analysis_id = request.analysis_id or request.artifact_id
            diag = AnalysisDiagnostic(
                id=uuid5(
                    resolved_analysis_id,
                    f"m2:parser_timeout:{request.path}:{deadline}",
                ),
                analysis_id=resolved_analysis_id,
                code="parser_timeout",
                category=DiagnosticCategory.TIMEOUT,
                severity=DiagnosticSeverity.ERROR,
                scope=DiagnosticScope.FILE,
                message=f"Parser execution exceeded deadline of {deadline} seconds",
                retryability=FailureRetryability.NON_RETRYABLE,
                created_at=datetime.now(UTC),
                stage="syntax_extraction",
                artifact_id=request.artifact_id,
                artifact_path=request.path,
            )
            return ParserResult(
                success=False,
                document=None,
                diagnostics=(diag,),
                execution_time_seconds=time.perf_counter() - start_time,
                error_message="Parser process timed out",
            )
        except ResultSizeExceededError as rse:
            diag = create_parsing_diagnostic(
                analysis_id=request.analysis_id,
                artifact_id=request.artifact_id,
                artifact_path=request.path,
                code="parser_result_size_exceeded",
                message=str(rse),
                severity=DiagnosticSeverity.ERROR,
            )
            return ParserResult(
                success=False,
                document=None,
                diagnostics=(diag,),
                execution_time_seconds=time.perf_counter() - start_time,
                error_message="Parser IPC result size ceiling exceeded",
            )
        except StderrOverflowError as soe:
            diag = create_parsing_diagnostic(
                analysis_id=request.analysis_id,
                artifact_id=request.artifact_id,
                artifact_path=request.path,
                code="parser_stderr_overflow",
                message=str(soe),
                severity=DiagnosticSeverity.ERROR,
            )
            return ParserResult(
                success=False,
                document=None,
                diagnostics=(diag,),
                execution_time_seconds=time.perf_counter() - start_time,
                error_message="Parser stderr size ceiling exceeded",
            )
        except Exception as exc:
            diag = create_parsing_diagnostic(
                analysis_id=request.analysis_id,
                artifact_id=request.artifact_id,
                artifact_path=request.path,
                code="parser_process_failed",
                message=f"Failed to execute parser child process: {exc}",
                severity=DiagnosticSeverity.ERROR,
            )
            return ParserResult(
                success=False,
                document=None,
                diagnostics=(diag,),
                execution_time_seconds=time.perf_counter() - start_time,
                error_message=str(exc),
            )
        finally:
            self._cleanup_process(proc, win_job)

        if proc.returncode != 0:
            stderr_str = stderr_bytes.decode("utf-8", errors="replace").strip()
            diag = create_parsing_diagnostic(
                analysis_id=request.analysis_id,
                artifact_id=request.artifact_id,
                artifact_path=request.path,
                code="parser_crash",
                message=(
                    f"Parser child process terminated abnormally with exit code "
                    f"{proc.returncode}: {stderr_str}"
                ),
                severity=DiagnosticSeverity.ERROR,
            )
            return ParserResult(
                success=False,
                document=None,
                diagnostics=(diag,),
                execution_time_seconds=time.perf_counter() - start_time,
                error_message=f"Child crash (exit code {proc.returncode})",
            )

        stdout_str = stdout_bytes.decode("utf-8", errors="replace")
        try:
            data = json.loads(stdout_str)
        except json.JSONDecodeError as exc:
            diag = create_parsing_diagnostic(
                analysis_id=request.analysis_id,
                artifact_id=request.artifact_id,
                artifact_path=request.path,
                code="parser_ipc_error",
                message=f"Malformed parser child output: {exc}",
                severity=DiagnosticSeverity.ERROR,
            )
            return ParserResult(
                success=False,
                document=None,
                diagnostics=(diag,),
                execution_time_seconds=time.perf_counter() - start_time,
                error_message=f"IPC error: {exc}",
            )

        document = None
        if data.get("document") is not None:
            document = self._deserialize_document(data["document"])

        diagnostics = []
        for d in data.get("diagnostics", []):
            diagnostics.append(
                AnalysisDiagnostic(
                    id=UUID(d["id"]),
                    analysis_id=request.analysis_id or uuid4(),
                    code=d["code"],
                    category=DiagnosticCategory(d["category"]),
                    severity=DiagnosticSeverity(d["severity"]),
                    scope=DiagnosticScope(d["scope"]),
                    message=d["message"],
                    retryability=FailureRetryability(d["retryability"]),
                    created_at=datetime.now(UTC),
                    stage=d.get("stage", "syntax_extraction"),
                    artifact_id=(
                        UUID(d["artifact_id"]) if d.get("artifact_id") else None
                    ),
                    artifact_path=d.get("artifact_path"),
                    source_line=d.get("source_line"),
                    source_column=d.get("source_column"),
                    details=d.get("details", {}),
                )
            )

        framework_hints: dict[str, dict[str, str]] = {}
        raw_hints = data.get("framework_hints", {})
        if isinstance(raw_hints, dict):
            for fact_key, raw_values in raw_hints.items():
                if isinstance(fact_key, str) and isinstance(raw_values, dict):
                    framework_hints[fact_key] = {
                        str(key): str(value)
                        for key, value in raw_values.items()
                        if isinstance(key, str) and isinstance(value, str)
                    }

        return ParserResult(
            success=data.get("success", True),
            document=document,
            diagnostics=tuple(diagnostics),
            execution_time_seconds=time.perf_counter() - start_time,
            error_message=(
                sanitize_diagnostic_text(str(data["error_message"]))
                if data.get("error_message") is not None
                else None
            ),
            framework_hints=framework_hints,
        )

    def _deserialize_document(self, d: dict[str, Any]) -> SyntaxDocument:
        """Reconstruct SyntaxDocument and facts from deserialized dictionary."""
        enc = d["encoding_metadata"]
        encoding_meta = SourceEncodingMetadata(
            detected_encoding=enc["detected_encoding"],
            has_bom=enc["has_bom"],
            line_count=enc["line_count"],
            byte_count=enc["byte_count"],
            is_utf8_clean=enc["is_utf8_clean"],
        )

        def make_range(r: dict[str, Any] | None) -> SourceRange | None:
            if not r:
                return None
            return SourceRange(
                start_byte=r["start_byte"],
                end_byte=r["end_byte"],
                start_line=r["start_line"],
                end_line=r["end_line"],
                start_column=r["start_column"],
                end_column=r["end_column"],
            )

        facts: list[SyntaxFact] = []
        for f in d.get("facts", []):
            if "declaration_range" in f:
                facts.append(
                    DeclarationFact(
                        fact_key=f["fact_key"],
                        kind=DeclarationKind(f["kind"]),
                        name=f["name"],
                        qualified_name=f.get("qualified_name"),
                        container_key=f.get("container_key"),
                        modifiers=tuple(f.get("modifiers", ())),
                        decorators=tuple(f.get("decorators", ())),
                        signature_text=f.get("signature_text"),
                        declaration_range=make_range(f["declaration_range"]),  # type: ignore[arg-type]
                        name_range=make_range(f["name_range"]),  # type: ignore[arg-type]
                    )
                )
            elif "source_module" in f and "imported_name" in f:
                facts.append(
                    ImportFact(
                        fact_key=f["fact_key"],
                        kind=ImportKind(f["kind"]),
                        source_module=f["source_module"],
                        relative_level=f.get("relative_level", 0),
                        imported_name=f.get("imported_name"),
                        local_alias=f.get("local_alias"),
                        is_type_only=f.get("is_type_only", False),
                        is_commonjs=f.get("is_commonjs", False),
                        range=make_range(f["range"]),  # type: ignore[arg-type]
                    )
                )
            elif "exported_name" in f:
                facts.append(
                    ExportFact(
                        fact_key=f["fact_key"],
                        kind=ExportKind(f["kind"]),
                        local_name=f.get("local_name"),
                        exported_name=f["exported_name"],
                        source_module=f.get("source_module"),
                        is_type_only=f.get("is_type_only", False),
                        is_commonjs=f.get("is_commonjs", False),
                        range=make_range(f["range"]),  # type: ignore[arg-type]
                    )
                )
            elif "target_name" in f:
                facts.append(
                    ReferenceFact(
                        fact_key=f["fact_key"],
                        kind=ReferenceKind(f["kind"]),
                        source_declaration_key=f.get("source_declaration_key"),
                        target_name=f["target_name"],
                        range=make_range(f["range"]),  # type: ignore[arg-type]
                    )
                )

        return SyntaxDocument(
            artifact_id=UUID(d["artifact_id"]),
            path=d["path"],
            content_hash=d["content_hash"],
            language=d["language"],
            language_version=d.get("language_version"),
            parser_adapter_id=d["parser_adapter_id"],
            parser_adapter_version=d["parser_adapter_version"],
            grammar_abi_version=d.get("grammar_abi_version"),
            parse_status=ParseStatus(d["parse_status"]),
            encoding_metadata=encoding_meta,
            facts=tuple(facts),
            diagnostic_ids=tuple(d.get("diagnostic_ids", ())),
        )
