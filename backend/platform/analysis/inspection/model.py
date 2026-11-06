"""Canonical F2 repository inspection and inventory models."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum, StrEnum
from typing import Any
from uuid import UUID

from backend.platform.analysis.syntax.model import SourceRange, SyntaxDocument


class ArtifactAnalysisRole(StrEnum):
    """Pipeline analysis role assigned to an artifact."""

    SEMANTIC = "semantic"
    CONFIGURATION = "configuration"
    DOCUMENTATION = "documentation"
    METADATA_ONLY = "metadata_only"
    IGNORED = "ignored"
    UNSUPPORTED = "unsupported"

    @classmethod
    def _missing_(cls, value: object) -> Any:
        if isinstance(value, str) and value.lower() == "failed":
            raise ValueError(
                "Invariant violation: 'failed' is a processing outcome, "
                "never an analysis role."
            )
        return super()._missing_(value)


class ArtifactProcessingOutcome(StrEnum):
    """Processing outcome achieved for an artifact."""

    NOT_PROCESSED = "not_processed"
    ANALYZED = "analyzed"
    ANALYZED_WITH_WARNINGS = "analyzed_with_warnings"
    EXCLUDED = "excluded"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True)
class LanguageDetection:
    """Detected language for an individual artifact or repository component."""

    artifact_id: UUID
    path: str
    language: str
    confidence: str = "confirmed"
    evidence_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeDetection:
    """Detected execution runtime or platform environment."""

    runtime: str
    target: str
    evidence_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class FrameworkDetection:
    """Detected framework or architectural technology."""

    framework: str
    status: str
    version: str | None = None
    evidence_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class DetectionEvidence:
    """Concrete evidence signal supporting or conflicting with a detection."""

    artifact_id: UUID
    path: str
    range: SourceRange | None = None
    signal_code: str = ""
    observed_token: str = ""
    analyzer_id: str = ""
    polarity: str = "supporting"


@dataclass(frozen=True)
class ArtifactInventoryEntry:
    """Classified inventory entry for a single repository artifact."""

    artifact_id: UUID
    revision_id: UUID
    path: str
    content_hash: str
    size_bytes: int
    original_category: str
    original_support_level: str
    detected_language: str | None = None
    is_test: bool = False
    is_generated: bool = False
    is_sensitive: bool = False
    analysis_role: ArtifactAnalysisRole = ArtifactAnalysisRole.UNSUPPORTED
    processing_outcome: ArtifactProcessingOutcome = (
        ArtifactProcessingOutcome.NOT_PROCESSED
    )
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        norm_path = self.path.replace("\\", "/")
        if norm_path.startswith("/") or norm_path.startswith("./"):
            raise ValueError(
                f"Inventory path must be normalized relative POSIX path: {self.path}"
            )
        if not isinstance(self.analysis_role, ArtifactAnalysisRole):
            raise TypeError(f"Invalid analysis role: {self.analysis_role}")
        if not isinstance(self.processing_outcome, ArtifactProcessingOutcome):
            raise TypeError(f"Invalid processing outcome: {self.processing_outcome}")


@dataclass(frozen=True)
class InspectionCoverage:
    """Summary statistics for repository inspection and parsing coverage."""

    total_artifacts: int
    total_bytes: int
    role_counts: dict[str, int]
    outcome_counts: dict[str, int]
    language_counts: dict[str, int]
    processed_artifacts: int
    failed_artifacts: int


def _serialize_json_value(val: Any) -> Any:
    if isinstance(val, UUID):
        return str(val)
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, tuple):
        return [_serialize_json_value(item) for item in val]
    if isinstance(val, list):
        return [_serialize_json_value(item) for item in val]
    if isinstance(val, dict):
        return {k: _serialize_json_value(v) for k, v in sorted(val.items())}
    if hasattr(val, "__dataclass_fields__"):
        return _serialize_json_value(asdict(val))
    return val


@dataclass(frozen=True)
class RepositoryInspectionResult:
    """Canonical root F2 inspection and syntax result produced by Module 2."""

    analysis_id: UUID
    project_id: UUID
    repository_id: UUID
    snapshot_id: UUID
    analyzer_version: str
    configuration_fingerprint: str
    inventory: tuple[ArtifactInventoryEntry, ...]
    syntax_documents: tuple[SyntaxDocument, ...]
    coverage: InspectionCoverage
    f2_version: str = "1.0.0"
    language_detections: tuple[LanguageDetection, ...] = ()
    runtime_detections: tuple[RuntimeDetection, ...] = ()
    framework_detections: tuple[FrameworkDetection, ...] = ()
    diagnostic_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.f2_version != "1.0.0":
            raise ValueError(f"Unsupported F2 contract version: {self.f2_version}")
        # Verify deterministic path ordering
        inv_paths = [entry.path for entry in self.inventory]
        if inv_paths != sorted(inv_paths):
            sorted_inv = tuple(sorted(self.inventory, key=lambda e: e.path))
            object.__setattr__(self, "inventory", sorted_inv)

        doc_paths = [doc.path for doc in self.syntax_documents]
        if doc_paths != sorted(doc_paths):
            sorted_docs = tuple(sorted(self.syntax_documents, key=lambda d: d.path))
            object.__setattr__(self, "syntax_documents", sorted_docs)

        fw_names = [f.framework for f in self.framework_detections]
        if fw_names != sorted(fw_names):
            sorted_fw = tuple(
                sorted(self.framework_detections, key=lambda f: f.framework)
            )
            object.__setattr__(self, "framework_detections", sorted_fw)

        lang_keys = [f"{ld.path}:{ld.language}" for ld in self.language_detections]
        if lang_keys != sorted(lang_keys):
            sorted_langs = tuple(
                sorted(self.language_detections, key=lambda ld: (ld.path, ld.language))
            )
            object.__setattr__(self, "language_detections", sorted_langs)

        rt_keys = [f"{r.runtime}:{r.target}" for r in self.runtime_detections]
        if rt_keys != sorted(rt_keys):
            sorted_rts = tuple(
                sorted(self.runtime_detections, key=lambda r: (r.runtime, r.target))
            )
            object.__setattr__(self, "runtime_detections", sorted_rts)

    def to_dict(self) -> dict[str, Any]:
        """Convert inspection result to a serializable dictionary with sorted keys."""
        return _serialize_json_value(self)  # type: ignore[no-any-return]

    def to_canonical_json(self) -> str:
        """Serialize inspection result to canonical, deterministic UTF-8 JSON."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
