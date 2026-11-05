"""Isolated child worker entry point for parsing untrusted source."""

from __future__ import annotations

import base64
import json
import sys
from uuid import UUID

from backend.platform.analysis.syntax.base import (
    ParserAdapter,
    ParserRequest,
    ParserResult,
)
from backend.platform.analysis.syntax.javascript import TreeSitterJsTsAdapter
from backend.platform.analysis.syntax.python import PythonAstAdapter


def main() -> None:
    """Read a single ParserRequest from stdin, parse, and write result to stdout."""
    try:
        raw_input = sys.stdin.read()
        if not raw_input:
            sys.exit(1)
        req_dict = json.loads(raw_input)

        content = base64.b64decode(req_dict["content_b64"])
        artifact_id = UUID(req_dict["artifact_id"])
        analysis_id = (
            UUID(req_dict["analysis_id"]) if req_dict.get("analysis_id") else None
        )

        req = ParserRequest(
            artifact_id=artifact_id,
            path=req_dict["path"],
            content=content,
            language=req_dict["language"],
            analysis_id=analysis_id,
            configuration_fingerprint=req_dict.get("configuration_fingerprint", ""),
            deadline_seconds=float(req_dict.get("deadline_seconds", 30.0)),
            max_file_size_bytes=int(
                req_dict.get("max_file_size_bytes", 5 * 1024 * 1024)
            ),
        )

        norm_lang = req.language.lower().strip()
        adapter: ParserAdapter
        if norm_lang == "python":
            adapter = PythonAstAdapter()
        elif norm_lang in ("javascript", "typescript", "jsx", "tsx"):
            adapter = TreeSitterJsTsAdapter()
        else:
            sys.stdout.write(
                json.dumps(
                    {
                        "success": False,
                        "error_message": f"Unsupported parser language: {req.language}",
                        "document": None,
                        "diagnostics": [],
                        "execution_time_seconds": 0.0,
                    }
                )
            )
            return

        result: ParserResult = adapter.parse(req)

        # Serialize document and diagnostics
        doc_dict = None
        if result.document is not None:
            from backend.platform.analysis.inspection.model import _serialize_json_value

            doc_dict = _serialize_json_value(result.document)

        diag_dicts = []
        for d in result.diagnostics:
            diag_dicts.append(
                {
                    "id": str(d.id),
                    "code": d.code,
                    "category": d.category.value,
                    "severity": d.severity.value,
                    "scope": d.scope.value,
                    "message": d.message,
                    "retryability": d.retryability.value,
                    "stage": d.stage,
                    "artifact_id": str(d.artifact_id) if d.artifact_id else None,
                    "artifact_path": d.artifact_path,
                    "source_line": d.source_line,
                    "source_column": d.source_column,
                    "details": d.details,
                }
            )

        output = {
            "success": result.success,
            "document": doc_dict,
            "diagnostics": diag_dicts,
            "execution_time_seconds": result.execution_time_seconds,
            "error_message": result.error_message,
        }
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
