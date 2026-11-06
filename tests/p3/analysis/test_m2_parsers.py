"""Tests for parser adapters, canonical ranges, and isolated executor."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any
from uuid import uuid4

import pytest

from backend.platform.analysis.domain.constants import (
    DiagnosticCategory,
    DiagnosticSeverity,
)
from backend.platform.analysis.syntax.base import (
    ParserRequest,
    normalize_source_encoding,
)
from backend.platform.analysis.syntax.executor import ParserExecutor
from backend.platform.analysis.syntax.javascript import TreeSitterJsTsAdapter
from backend.platform.analysis.syntax.model import (
    DeclarationKind,
    ParseStatus,
    ReferenceFact,
    ReferenceKind,
)
from backend.platform.analysis.syntax.python import PythonAstAdapter
from backend.platform.analysis.syntax.sandbox import (
    ParserSandboxError,
    _apply_resource_limits,
)


def test_python_adapter_valid_source_and_canonical_ranges() -> None:
    """Verify PythonAstAdapter extracts declarations and maps canonical UTF-8 ranges."""
    source = (
        b"import os\n"
        b"\n"
        b"@decorator\n"
        b"async def process_item(item_id: str) -> bool:\n"
        b"    return bool(item_id)\n"
        b"\n"
        b"class Worker:\n"
        b"    pass\n"
    )

    adapter = PythonAstAdapter()
    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/worker.py",
        content=source,
        language="python",
    )
    res = adapter.parse(req)

    assert res.success is True
    assert res.document is not None
    doc = res.document
    assert doc.parse_status == ParseStatus.PARSED
    assert doc.language == "python"
    assert doc.parser_adapter_id == "python-ast"
    assert doc.encoding_metadata.is_utf8_clean is True

    # Check extracted facts
    decl_names = [f.name for f in doc.facts if hasattr(f, "name")]
    assert "process_item" in decl_names
    assert "Worker" in decl_names

    fn_fact = next(f for f in doc.facts if getattr(f, "name", "") == "process_item")
    assert fn_fact.declaration_range.start_line == 3  # @decorator start
    assert fn_fact.declaration_range.end_line == 5
    assert fn_fact.declaration_range.start_byte < fn_fact.declaration_range.end_byte
    # Slicing the canonical bytes with the range should match the function definition
    slice_bytes = source[
        fn_fact.declaration_range.start_byte : fn_fact.declaration_range.end_byte
    ]
    assert b"def process_item" in slice_bytes


def test_python_adapter_utf8_bom_and_crlf_preservation() -> None:
    """Verify UTF-8 BOM is excluded from coordinates while CRLF is preserved."""
    # Source with BOM and CRLF
    bom = b"\xef\xbb\xbf"
    code = b"def sample():\r\n    return 42\r\n"
    content = bom + code

    adapter = PythonAstAdapter()
    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/bom_test.py",
        content=content,
        language="python",
    )
    res = adapter.parse(req)

    assert res.success is True
    assert res.document is not None
    doc = res.document
    assert doc.encoding_metadata.has_bom is True
    assert doc.encoding_metadata.detected_encoding.lower() == "utf-8-sig"

    fn_fact = next(f for f in doc.facts if getattr(f, "name", "") == "sample")
    # Coordinates must index into canonical bytes without the 3-byte BOM
    assert fn_fact.declaration_range.start_byte == 0
    canonical_bytes, _, _ = normalize_source_encoding(content, "python")
    extracted = canonical_bytes[
        fn_fact.declaration_range.start_byte : fn_fact.declaration_range.end_byte
    ]
    assert extracted.startswith(b"def sample():\r\n")


def test_python_bom_conflicting_encoding_cookie_fails_strictly() -> None:
    """A UTF-8 BOM cannot be combined with a conflicting PEP 263 cookie."""
    content = b"\xef\xbb\xbf# coding: latin-1\nvalue = 1\n"
    result = PythonAstAdapter().parse(
        ParserRequest(
            artifact_id=uuid4(),
            path="src/conflicting_encoding.py",
            content=content,
            language="python",
        )
    )

    assert result.success is False
    assert result.document is None
    assert result.diagnostics[0].code == "source_decode_error"


def test_python_adapter_pep263_latin1_encoding() -> None:
    """Verify PEP 263 non-UTF-8 Python is decoded strictly and normalized to UTF-8."""
    # Latin-1 encoded Python with accents
    latin1_content = (
        "# -*- coding: iso-8859-1 -*-\ndef résumé():\n    return 'success'\n"
    ).encode("iso-8859-1")

    adapter = PythonAstAdapter()
    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/legacy.py",
        content=latin1_content,
        language="python",
    )
    res = adapter.parse(req)

    assert res.success is True
    assert res.document is not None
    doc = res.document
    assert doc.encoding_metadata.detected_encoding.lower() in ("iso-8859-1", "latin-1")

    fn_fact = next(f for f in doc.facts if getattr(f, "name", "") == "résumé")
    assert fn_fact.name == "résumé"


def test_python_adapter_syntax_error_handling() -> None:
    """Verify malformed Python produces diagnostic without crashing."""
    broken_source = b"def broken_function(\n    return 1\n"
    adapter = PythonAstAdapter()
    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/broken.py",
        content=broken_source,
        language="python",
    )
    res = adapter.parse(req)

    assert res.success is True
    assert res.document is not None
    assert res.document.parse_status == ParseStatus.FAILED
    assert len(res.diagnostics) == 1
    diag = res.diagnostics[0]
    assert diag.code == "syntax_error"
    assert diag.category == DiagnosticCategory.PARSING
    assert diag.source_line is not None
    assert "text" not in diag.details


def test_python_decorator_facts_never_retain_literal_arguments() -> None:
    """Decorator evidence keeps the structural name without secret arguments."""
    source = b'@auth.require(token="literal-secret")\ndef handler():\n    pass\n'
    result = PythonAstAdapter().parse(
        ParserRequest(
            artifact_id=uuid4(),
            path="src/handler.py",
            content=source,
            language="python",
        )
    )

    assert result.document is not None
    declaration = next(
        fact for fact in result.document.facts if getattr(fact, "name", "") == "handler"
    )
    assert declaration.decorators == ("auth.require",)
    assert "literal-secret" not in str(declaration)


def test_python_adapter_file_size_ceiling() -> None:
    """Verify files exceeding max size limit are rejected with diagnostic."""
    large_content = b"# comment\n" * 1000
    adapter = PythonAstAdapter()
    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/large.py",
        content=large_content,
        language="python",
        max_file_size_bytes=500,  # lower ceiling for test
    )
    res = adapter.parse(req)

    assert res.success is False
    assert res.document is None
    assert len(res.diagnostics) == 1
    assert res.diagnostics[0].code == "file_size_exceeded"


def test_treesitter_js_adapter_valid_source_and_ranges() -> None:
    """Verify TreeSitterJsTsAdapter parses JavaScript and JSX."""
    js_source = (
        b'import express from "express";\n'
        b"\n"
        b"class Server {\n"
        b"  start() {\n"
        b"    return true;\n"
        b"  }\n"
        b"}\n"
        b"\n"
        b"function createApp() {\n"
        b"  return new Server();\n"
        b"}\n"
    )

    adapter = TreeSitterJsTsAdapter()
    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/server.js",
        content=js_source,
        language="javascript",
    )
    res = adapter.parse(req)

    assert res.success is True
    assert res.document is not None
    doc = res.document
    assert doc.parse_status == ParseStatus.PARSED
    assert doc.language == "javascript"
    assert doc.parser_adapter_id == "tree-sitter-javascript-typescript"

    decl_names = [f.name for f in doc.facts if hasattr(f, "name")]
    assert "Server" in decl_names
    assert "createApp" in decl_names


def test_treesitter_ts_adapter_interfaces_and_types() -> None:
    """Verify TreeSitterJsTsAdapter parses TypeScript interfaces and type aliases."""
    ts_source = (
        b"export interface UserDto {\n"
        b"  id: string;\n"
        b"  email: string;\n"
        b"}\n"
        b"\n"
        b"export type Role = 'admin' | 'user';\n"
    )

    adapter = TreeSitterJsTsAdapter()
    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/types.ts",
        content=ts_source,
        language="typescript",
    )
    res = adapter.parse(req)

    assert res.success is True
    assert res.document is not None
    doc = res.document
    assert doc.parse_status == ParseStatus.PARSED

    facts_by_name = {getattr(f, "name", None): f for f in doc.facts}
    assert "UserDto" in facts_by_name
    assert facts_by_name["UserDto"].kind == DeclarationKind.INTERFACE
    assert "Role" in facts_by_name
    assert facts_by_name["Role"].kind == DeclarationKind.TYPE_ALIAS


def test_treesitter_tsx_react_composition() -> None:
    """Verify TSX parsing detects React component composition references."""
    tsx_source = (
        b"import React from 'react';\n"
        b"export const App = () => {\n"
        b"  return <Header title='Hello' />;\n"
        b"};\n"
    )

    adapter = TreeSitterJsTsAdapter()
    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/App.tsx",
        content=tsx_source,
        language="tsx",
    )
    res = adapter.parse(req)

    assert res.success is True
    assert res.document is not None
    doc = res.document

    # Verify Header is recognized as React composition reference
    react_refs = [
        f
        for f in doc.facts
        if isinstance(f, ReferenceFact) and f.kind == ReferenceKind.REACT_COMPOSITION
    ]
    assert any(ref.target_name == "Header" for ref in react_refs)


def test_treesitter_recoverable_syntax_error() -> None:
    """Verify malformed JS parses with PARSED_WITH_ERRORS and diagnostic."""
    broken_js = b"function incomplete( { return 1; }"
    adapter = TreeSitterJsTsAdapter()
    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/broken.js",
        content=broken_js,
        language="javascript",
    )
    res = adapter.parse(req)

    assert res.success is True
    assert res.document is not None
    assert res.document.parse_status == ParseStatus.PARSED_WITH_ERRORS
    assert len(res.diagnostics) >= 1
    assert res.diagnostics[0].severity == DiagnosticSeverity.WARNING


def test_treesitter_strict_utf8_decode_failure() -> None:
    """Verify non-UTF-8 bytes in JS fail with source_decode_error diagnostic."""
    bad_bytes = b"const x = '\xff\xfe\x00';"
    adapter = TreeSitterJsTsAdapter()
    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/bad_enc.js",
        content=bad_bytes,
        language="javascript",
    )
    res = adapter.parse(req)

    assert res.success is False
    assert res.document is None
    assert len(res.diagnostics) == 1
    assert res.diagnostics[0].code == "source_decode_error"


def test_parser_executor_os_process_isolation() -> None:
    """Verify ParserExecutor runs parsing inside an isolated child process."""
    executor = ParserExecutor()
    assert executor.is_isolation_available() is True

    py_source = b"def compute(a, b):\n    return a + b\n"
    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/math.py",
        content=py_source,
        language="python",
    )
    res = executor.execute(req)

    assert res.success is True
    assert res.document is not None
    assert res.document.path == "src/math.py"
    assert res.document.parse_status == ParseStatus.PARSED
    assert any(getattr(f, "name", None) == "compute" for f in res.document.facts)


def test_parser_executor_environment_sanitization() -> None:
    """Verify sensitive environment variables are stripped from child process."""
    os.environ["SECRET_API_TOKEN_FOR_TEST"] = "super-secret"
    os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/db"

    executor = ParserExecutor()
    clean_env = executor._build_sanitized_environment()

    assert "SECRET_API_TOKEN_FOR_TEST" not in clean_env
    assert "DATABASE_URL" not in clean_env
    assert "PYTHONPATH" in clean_env


def test_parser_executor_timeout_enforcement() -> None:
    """Verify ParserExecutor kills child process and returns timeout diagnostic."""
    executor = ParserExecutor()
    # A request with virtually zero deadline to force timeout
    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/timeout_test.py",
        content=b"x = 1\n",
        language="python",
        deadline_seconds=0.0001,
    )
    res = executor.execute(req)

    assert res.success is False
    assert len(res.diagnostics) == 1
    assert res.diagnostics[0].code == "parser_timeout"
    assert res.diagnostics[0].category == DiagnosticCategory.TIMEOUT


def test_parser_executor_fail_closed_when_isolation_unavailable() -> None:
    """Verify ParserExecutor fails closed if isolation cannot be verified."""
    executor = ParserExecutor(python_executable="non_existent_python_binary_xyz")
    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/app.py",
        content=b"x = 1\n",
        language="python",
    )
    res = executor.execute(req)

    assert res.success is False
    assert len(res.diagnostics) == 1
    assert res.diagnostics[0].code == "parser_isolation_unavailable"


def test_parser_executor_bounded_ipc_result_size() -> None:
    """Verify ParserExecutor rejects child outputs that exceed max IPC result bytes."""
    executor = ParserExecutor(max_ipc_result_bytes=10)
    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/app.py",
        content=b"x = 1\n",
        language="python",
    )
    res = executor.execute(req)

    assert res.success is False
    assert len(res.diagnostics) == 1
    assert res.diagnostics[0].code == "parser_result_size_exceeded"


def test_parser_executor_memory_limit_configuration() -> None:
    """Verify ParserExecutor configures OS memory limit and Job Object."""
    executor = ParserExecutor(max_memory_mb=256)
    assert executor._max_memory_mb == 256

    if sys.platform == "win32":
        job = executor._create_windows_job_object()
        assert job is not None
        import ctypes

        ctypes.windll.kernel32.CloseHandle(job)


def test_grammar_abi_version_is_non_null() -> None:
    """Verify that both Python and JS/TS adapters emit non-null grammar ABI versions."""
    py_adapter = PythonAstAdapter()
    py_req = ParserRequest(
        artifact_id=uuid4(),
        path="src/sample.py",
        content=b"x = 1\n",
        language="python",
    )
    py_res = py_adapter.parse(py_req)
    assert py_res.document is not None
    assert py_res.document.grammar_abi_version is not None
    assert py_res.document.grammar_abi_version > 0

    js_adapter = TreeSitterJsTsAdapter()
    js_req = ParserRequest(
        artifact_id=uuid4(),
        path="src/sample.js",
        content=b"const x = 1;\n",
        language="javascript",
    )
    js_res = js_adapter.parse(js_req)
    assert js_res.document is not None
    assert js_res.document.grammar_abi_version is not None
    assert js_res.document.grammar_abi_version > 0


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows Job Object tests require Windows",
)
def test_windows_job_object_create_failure_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify ParserExecutor fails closed if CreateJobObjectW fails."""
    import ctypes

    def mock_create(*args: Any, **kwargs: Any) -> int:
        return 0

    monkeypatch.setattr(ctypes.windll.kernel32, "CreateJobObjectW", mock_create)
    executor = ParserExecutor()
    assert executor.is_isolation_available() is False

    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/app.py",
        content=b"x = 1\n",
        language="python",
    )
    res = executor.execute(req)
    assert res.success is False
    assert len(res.diagnostics) == 1
    assert res.diagnostics[0].code in (
        "parser_isolation_unavailable",
        "parser_isolation_failed",
    )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows Job Object tests require Windows",
)
def test_windows_job_object_set_information_failure_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify ParserExecutor fails closed if SetInformationJobObject fails."""
    import ctypes

    def mock_set_info(*args: Any, **kwargs: Any) -> int:
        return 0

    monkeypatch.setattr(
        ctypes.windll.kernel32, "SetInformationJobObject", mock_set_info
    )
    executor = ParserExecutor()
    assert executor.is_isolation_available() is False

    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/app.py",
        content=b"x = 1\n",
        language="python",
    )
    res = executor.execute(req)
    assert res.success is False
    assert len(res.diagnostics) == 1
    assert res.diagnostics[0].code in (
        "parser_isolation_unavailable",
        "parser_isolation_failed",
    )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows Job Object tests require Windows",
)
def test_windows_job_object_assign_failure_kills_child_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify ParserExecutor kills child if AssignProcessToJobObject fails."""
    import ctypes

    def mock_assign(*args: Any, **kwargs: Any) -> int:
        return 0

    monkeypatch.setattr(ctypes.windll.kernel32, "AssignProcessToJobObject", mock_assign)
    executor = ParserExecutor()
    req = ParserRequest(
        artifact_id=uuid4(),
        path="src/app.py",
        content=b"x = 1\n",
        language="python",
    )
    res = executor.execute(req)
    assert res.success is False
    assert len(res.diagnostics) == 1
    assert res.diagnostics[0].code == "parser_isolation_failed"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX resource limit tests require POSIX",
)
def test_posix_resource_limit_failure_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the child sandbox fails closed if a resource limit cannot apply."""
    import resource

    def mock_setrlimit(*args: Any, **kwargs: Any) -> None:
        raise OSError(1, "Operation not permitted")

    monkeypatch.setattr(resource, "setrlimit", mock_setrlimit)
    with pytest.raises(ParserSandboxError, match="Unable to apply RLIMIT_AS"):
        _apply_resource_limits(max_memory_mb=512, cpu_seconds=30.0)


def test_bounded_ipc_input_write_cannot_bypass_deadline() -> None:
    """A child that never reads stdin cannot deadlock the pytest process."""
    executor = ParserExecutor()
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    with pytest.raises(subprocess.TimeoutExpired):
        executor._communicate_bounded(
            proc=proc,
            input_data=b"A" * (2 * 1024 * 1024),
            deadline=0.1,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
        )
    assert proc.poll() is not None


def test_truly_bounded_stdout_streaming_kills_child_early() -> None:
    """Verify bounded communicate terminates child before buffering excess stdout."""
    executor = ParserExecutor(max_ipc_result_bytes=50)
    cmd = "import sys; " "sys.stdout.write('A' * 5000); " "sys.stdout.flush()"
    proc = subprocess.Popen(
        [sys.executable, "-c", cmd],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    with pytest.raises(Exception) as exc_info:
        executor._communicate_bounded(
            proc=proc,
            input_data=b"",
            deadline=5.0,
            max_stdout_bytes=50,
            max_stderr_bytes=1024,
        )
    assert "ResultSizeExceededError" in exc_info.type.__name__
    assert proc.poll() is not None


def test_truly_bounded_stderr_streaming_kills_child_early() -> None:
    """Verify bounded communicate terminates child before buffering excess stderr."""
    executor = ParserExecutor(max_stderr_bytes=50)
    cmd = "import sys; " "sys.stderr.write('E' * 5000); " "sys.stderr.flush()"
    proc = subprocess.Popen(
        [sys.executable, "-c", cmd],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    with pytest.raises(Exception) as exc_info:
        executor._communicate_bounded(
            proc=proc,
            input_data=b"",
            deadline=5.0,
            max_stdout_bytes=1024,
            max_stderr_bytes=50,
        )
    assert "StderrOverflowError" in exc_info.type.__name__
    assert proc.poll() is not None


def test_child_cleanup_on_timeout_and_exceptions() -> None:
    """Verify _cleanup_process reliably kills processes and releases handles."""
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    executor = ParserExecutor()
    executor._cleanup_process(proc, win_job=None)
    assert proc.poll() is not None


def test_parser_executor_from_settings() -> None:
    """Verify ParserExecutor.from_settings() wires platform settings correctly."""
    from backend.platform.config import Settings

    custom_settings = Settings(
        parser_per_file_timeout_seconds=45.0,
        parser_max_file_size_bytes=2 * 1024 * 1024,
        parser_max_memory_mb=256,
        parser_max_stderr_bytes=512 * 1024,
        parser_max_facts_per_artifact=12_345,
    )
    executor = ParserExecutor.from_settings(settings=custom_settings)
    assert executor._default_timeout_seconds == 45.0
    assert executor._max_file_size_bytes == 2 * 1024 * 1024
    assert executor._max_memory_mb == 256
    assert executor._max_stderr_bytes == 512 * 1024
    assert executor._max_facts_per_artifact == 12_345

    # Default fallback to get_settings()
    default_executor = ParserExecutor.from_settings()
    assert default_executor._default_timeout_seconds == 30.0
    assert default_executor._max_file_size_bytes == 5 * 1024 * 1024
    assert default_executor._max_memory_mb == 512
    assert default_executor._max_stderr_bytes == 1024 * 1024
    assert default_executor._max_facts_per_artifact == 25_000


def test_diagnostic_credential_and_secret_redaction() -> None:
    """Verify create_parsing_diagnostic redacts secrets, tokens, and URIs."""
    from backend.platform.analysis.syntax.base import create_parsing_diagnostic

    raw_msg = (
        "Failed connecting to postgresql://admin:super_secret_pw@db.prod:5432/core "
        "with Bearer eyJhbGciOiJIUzI1NiJ9.secret_token and password=hidden_pwd"
    )
    diag = create_parsing_diagnostic(
        analysis_id=uuid4(),
        artifact_id=uuid4(),
        artifact_path="src/main.py",
        code="auth_error",
        message=raw_msg,
        details={
            "raw_exception": "api_key=sk-1234567890abcdef",
            "nested": {"password": "password=still-hidden"},
            "safe_metric": 42,
        },
    )

    assert "super_secret_pw" not in diag.message
    assert "secret_token" not in diag.message
    assert "hidden_pwd" not in diag.message
    assert "***" in diag.message
    assert "sk-1234567890abcdef" not in str(diag.details)
    assert "still-hidden" not in str(diag.details)
    assert diag.details["safe_metric"] == 42


def test_parser_executor_environment_sanitization_flags() -> None:
    """Verify execution environment sets protective Python runtime flags."""
    executor = ParserExecutor()
    env = executor._build_sanitized_environment()

    assert env["PYTHONUNBUFFERED"] == "1"
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert env["PYTHONNOUSERSITE"] == "1"
    assert "PYTHONPATH" in env
    assert not any("SECRET" in k for k in env)
