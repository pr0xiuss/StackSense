"""Isolated child worker entry point for parsing untrusted source."""

from __future__ import annotations

import base64
import codecs
import json
import struct
import sys
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from backend.platform.analysis.inspection.model import _serialize_json_value
from backend.platform.analysis.syntax.base import (
    ParserAdapter,
    ParserRequest,
    ParserResult,
)
from backend.platform.analysis.syntax.javascript import TreeSitterJsTsAdapter
from backend.platform.analysis.syntax.python import PythonAstAdapter
from backend.platform.analysis.syntax.sandbox import (
    apply_parser_sandbox,
    verify_parser_sandbox,
)


def _preload_source_codecs() -> None:
    """Load supported source codecs before filesystem access is denied."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "iso-8859-1", "cp1252"):
        codecs.lookup(encoding)


_FRAME_HEADER = struct.Struct(">Q")
_MAX_REQUEST_FRAME_BYTES = 16 * 1024 * 1024


def _build_adapters() -> dict[str, ParserAdapter]:
    python_adapter = PythonAstAdapter()
    javascript_adapter = TreeSitterJsTsAdapter()
    return {
        "python": python_adapter,
        "javascript": javascript_adapter,
        "typescript": javascript_adapter,
        "jsx": javascript_adapter,
        "tsx": javascript_adapter,
    }


def _serialize_result(result: ParserResult) -> dict[str, Any]:
    doc_dict = (
        _serialize_json_value(result.document) if result.document is not None else None
    )
    diag_dicts = [
        {
            "id": str(diagnostic.id),
            "code": diagnostic.code,
            "category": diagnostic.category.value,
            "severity": diagnostic.severity.value,
            "scope": diagnostic.scope.value,
            "message": diagnostic.message,
            "retryability": diagnostic.retryability.value,
            "stage": diagnostic.stage,
            "artifact_id": (
                str(diagnostic.artifact_id) if diagnostic.artifact_id else None
            ),
            "artifact_path": diagnostic.artifact_path,
            "source_line": diagnostic.source_line,
            "source_column": diagnostic.source_column,
            "details": diagnostic.details,
        }
        for diagnostic in result.diagnostics
    ]
    return {
        "success": result.success,
        "document": doc_dict,
        "diagnostics": diag_dicts,
        "execution_time_seconds": result.execution_time_seconds,
        "error_message": result.error_message,
        "framework_hints": result.framework_hints,
    }


def _handle_request(
    req_dict: Mapping[str, Any], adapters: Mapping[str, ParserAdapter]
) -> dict[str, Any]:
    try:
        content = base64.b64decode(req_dict["content_b64"], validate=True)
        artifact_id = UUID(str(req_dict["artifact_id"]))
        analysis_id = (
            UUID(str(req_dict["analysis_id"])) if req_dict.get("analysis_id") else None
        )
        request = ParserRequest(
            artifact_id=artifact_id,
            path=str(req_dict["path"]),
            content=content,
            language=str(req_dict["language"]),
            analysis_id=analysis_id,
            configuration_fingerprint=str(
                req_dict.get("configuration_fingerprint", "")
            ),
            deadline_seconds=float(req_dict.get("deadline_seconds", 30.0)),
            max_file_size_bytes=int(
                req_dict.get("max_file_size_bytes", 5 * 1024 * 1024)
            ),
            max_facts_per_artifact=int(req_dict.get("max_facts_per_artifact", 25_000)),
        )
        adapter = adapters.get(request.language.lower().strip())
        if adapter is None:
            return {
                "success": False,
                "error_message": (f"Unsupported parser language: {request.language}"),
                "document": None,
                "diagnostics": [],
                "execution_time_seconds": 0.0,
                "framework_hints": {},
            }
        return _serialize_result(adapter.parse(request))
    except Exception as exc:
        return {
            "success": False,
            "error_message": f"Parser worker request failed: {type(exc).__name__}",
            "document": None,
            "diagnostics": [],
            "execution_time_seconds": 0.0,
            "framework_hints": {},
        }


def _read_exact(stream: Any, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise EOFError("Parser request frame ended unexpectedly")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _serve_pool(max_memory_mb: int, cpu_seconds: float, max_requests: int) -> None:
    if max_requests <= 0:
        raise ValueError("Parser pool max_requests must be positive")
    _preload_source_codecs()
    adapters = _build_adapters()
    apply_parser_sandbox(max_memory_mb=max_memory_mb, cpu_seconds=cpu_seconds)
    verify_parser_sandbox()

    source = sys.stdin.buffer
    destination = sys.stdout.buffer
    for _ in range(max_requests):
        header = source.read(_FRAME_HEADER.size)
        if not header:
            break
        if len(header) != _FRAME_HEADER.size:
            raise EOFError("Parser request frame header was incomplete")
        frame_size = _FRAME_HEADER.unpack(header)[0]
        if frame_size == 0:
            break
        if frame_size > _MAX_REQUEST_FRAME_BYTES:
            raise ValueError("Parser request frame exceeded the transport limit")
        request_data = json.loads(_read_exact(source, frame_size).decode("utf-8"))
        result_data = _handle_request(request_data, adapters)
        encoded = json.dumps(result_data, separators=(",", ":")).encode("utf-8")
        destination.write(_FRAME_HEADER.pack(len(encoded)))
        destination.write(encoded)
        destination.flush()


def main() -> None:
    """Read a single ParserRequest from stdin, parse, and write result to stdout."""
    try:
        if len(sys.argv) == 4 and sys.argv[1] == "--probe":
            _preload_source_codecs()
            apply_parser_sandbox(
                max_memory_mb=int(sys.argv[2]), cpu_seconds=float(sys.argv[3])
            )
            verify_parser_sandbox()
            sys.stdout.write(json.dumps({"sandbox": "ready"}))
            return

        if len(sys.argv) == 5 and sys.argv[1] == "--serve":
            _serve_pool(
                max_memory_mb=int(sys.argv[2]),
                cpu_seconds=float(sys.argv[3]),
                max_requests=int(sys.argv[4]),
            )
            return

        raw_input = sys.stdin.read()
        if not raw_input:
            sys.exit(1)
        req_dict = json.loads(raw_input)

        _preload_source_codecs()
        apply_parser_sandbox(
            max_memory_mb=int(req_dict["sandbox_max_memory_mb"]),
            cpu_seconds=float(req_dict["sandbox_cpu_seconds"]),
        )

        output = _handle_request(req_dict, _build_adapters())
        sys.stdout.write(json.dumps(output))

    except Exception as exc:
        sys.stderr.write(f"Worker exception: {exc}\n")
        sys.stdout.write(
            json.dumps(
                {
                    "success": False,
                    "error_message": str(exc),
                    "document": None,
                    "diagnostics": [],
                    "execution_time_seconds": 0.0,
                }
            )
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
