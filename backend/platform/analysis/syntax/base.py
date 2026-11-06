"""Base protocols, request/response models, and encoding normalization for parsers."""

from __future__ import annotations

import io
import re
import tokenize
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID, uuid5

from backend.platform.analysis.domain.constants import (
    DiagnosticCategory,
    DiagnosticScope,
    DiagnosticSeverity,
    FailureRetryability,
)
from backend.platform.analysis.domain.diagnostic import AnalysisDiagnostic
from backend.platform.analysis.syntax.limits import DEFAULT_MAX_FACTS_PER_ARTIFACT
from backend.platform.analysis.syntax.model import (
    SourceEncodingMetadata,
    SyntaxDocument,
)


class SourceEncodingError(Exception):
    """Raised when source bytes cannot be decoded using strict encoding rules."""


@dataclass(frozen=True)
class ParserRequest:
    """Request to parse an individual artifact's content."""

    artifact_id: UUID
    path: str
    content: bytes
    language: str
    analysis_id: UUID | None = None
    configuration_fingerprint: str = ""
    deadline_seconds: float = 30.0
    max_file_size_bytes: int = 5 * 1024 * 1024
    max_facts_per_artifact: int = DEFAULT_MAX_FACTS_PER_ARTIFACT

    def __post_init__(self) -> None:
        if self.deadline_seconds <= 0:
            raise ValueError("deadline_seconds must be positive")
        if self.max_file_size_bytes <= 0:
            raise ValueError("max_file_size_bytes must be positive")
        if self.max_facts_per_artifact <= 0:
            raise ValueError("max_facts_per_artifact must be positive")


@dataclass(frozen=True)
class ParserResult:
    """Outcome of parsing an individual source artifact."""

    success: bool
    document: SyntaxDocument | None
    diagnostics: tuple[AnalysisDiagnostic, ...] = ()
    execution_time_seconds: float = 0.0
    peak_memory_bytes: int = 0
    error_message: str | None = None


@runtime_checkable
class ParserAdapter(Protocol):
    """Protocol for syntax parser adapters."""

    @property
    def adapter_id(self) -> str:
        """Unique identifier for this parser adapter."""
        ...

    @property
    def adapter_version(self) -> str:
        """Version string of the adapter."""
        ...

    @property
    def supported_languages(self) -> tuple[str, ...]:
        """Tuple of normalized language names handled by this adapter."""
        ...

    def parse(self, request: ParserRequest) -> ParserResult:
        """Parse source content and return a structured ParserResult."""
        ...


def normalize_source_encoding(
    content: bytes, language: str
) -> tuple[bytes, str, SourceEncodingMetadata]:
    """Normalize raw artifact bytes into canonical UTF-8 buffer and text.

    Canonical source coordinates guarantee:
    1. BOM is excluded from the canonical UTF-8 buffer.
    2. Python source with PEP 263 encoding comments is strictly decoded and
       re-encoded to UTF-8.
    3. JS/TS/JSX/TSX source is strictly validated as UTF-8.
    4. Newline bytes (both LF and CRLF) are preserved without modification.
    5. Decoding errors fail strictly without lossy replacement.
    """
    has_bom = False
    raw_content = content
    if content.startswith(b"\xef\xbb\xbf"):
        has_bom = True
        raw_content = content[3:]

    norm_lang = language.lower().strip()
    detected_encoding = "utf-8"

    if norm_lang == "python":
        # PEP 263 detection must see the original BOM so a conflicting coding
        # cookie is rejected and UTF-8-SIG is recorded accurately.
        bio = io.BytesIO(content)
        try:
            detected_encoding, _ = tokenize.detect_encoding(bio.readline)
        except Exception as exc:
            raise SourceEncodingError(
                f"Failed to detect Python encoding: {exc}"
            ) from exc

        try:
            text = content.decode(detected_encoding)
        except Exception as exc:
            msg = (
                f"Strict decode failed using detected encoding "
                f"'{detected_encoding}': {exc}"
            )
            raise SourceEncodingError(msg) from exc

        # Re-encode to canonical UTF-8
        canonical_bytes = text.encode("utf-8")
    else:
        # JS, TS, JSX, TSX require strict UTF-8
        try:
            text = raw_content.decode("utf-8")
            canonical_bytes = raw_content
            detected_encoding = "utf-8"
        except UnicodeDecodeError as exc:
            raise SourceEncodingError(
                f"Strict UTF-8 decode failed for {language} artifact: {exc}"
            ) from exc

    # Count lines preserved exactly
    line_count = len(canonical_bytes.splitlines(keepends=True))
    byte_count = len(canonical_bytes)

    metadata = SourceEncodingMetadata(
        detected_encoding=detected_encoding,
        has_bom=has_bom,
        line_count=line_count,
        byte_count=byte_count,
        is_utf8_clean=True,
    )

    return canonical_bytes, text, metadata


_SENSITIVE_URI_PATTERN = re.compile(
    r"([a-zA-Z][a-zA-Z0-9+.-]*://[^:]+:)([^@]+)(@)",
    re.IGNORECASE,
)
_SENSITIVE_KEY_PATTERN = re.compile(
    r"\b(password|passwd|secret|token|api[_-]?key|bearer)[\s:=]+([^\s,;]+)",
    re.IGNORECASE,
)


def sanitize_diagnostic_text(text: str) -> str:
    """Redact passwords, tokens, secrets, and credentials from diagnostic text."""
    sanitized = _SENSITIVE_URI_PATTERN.sub(r"\1***\3", text)
    return _SENSITIVE_KEY_PATTERN.sub(r"\1=***", sanitized)


def _sanitize_diagnostic_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_diagnostic_text(value)
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_diagnostic_value(item) for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return tuple(_sanitize_diagnostic_value(item) for item in value)
    return value


def create_parsing_diagnostic(
    analysis_id: UUID | None,
    artifact_id: UUID,
    artifact_path: str,
    code: str,
    message: str,
    severity: DiagnosticSeverity = DiagnosticSeverity.ERROR,
    source_line: int | None = None,
    source_column: int | None = None,
    details: dict[str, Any] | None = None,
) -> AnalysisDiagnostic:
    """Helper to create an M1-compliant AnalysisDiagnostic for parsing errors."""
    safe_message = sanitize_diagnostic_text(message)
    safe_details: dict[str, Any] = {}
    if details:
        for k, v in details.items():
            safe_details[k] = _sanitize_diagnostic_value(v)

    resolved_analysis_id = analysis_id or artifact_id
    diagnostic_name = "|".join(
        (
            "m2",
            code,
            artifact_path,
            str(source_line or 0),
            str(source_column or 0),
            safe_message,
        )
    )

    return AnalysisDiagnostic(
        id=uuid5(resolved_analysis_id, diagnostic_name),
        analysis_id=resolved_analysis_id,
        code=code,
        category=DiagnosticCategory.PARSING,
        severity=severity,
        scope=DiagnosticScope.FILE,
        message=safe_message,
        retryability=FailureRetryability.NON_RETRYABLE,
        created_at=datetime.now(UTC),
        stage="syntax_extraction",
        artifact_id=artifact_id,
        artifact_path=artifact_path,
        source_line=source_line,
        source_column=source_column,
        details=safe_details,
    )
