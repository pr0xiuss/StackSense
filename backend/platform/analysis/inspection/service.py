"""Stateless M2 inventory, detection, and generic syntax extraction service."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING
from uuid import UUID

from backend.platform.analysis.domain.constants import DiagnosticSeverity
from backend.platform.analysis.domain.diagnostic import AnalysisDiagnostic
from backend.platform.analysis.domain.input import AnalysisInput
from backend.platform.analysis.frameworks import FrameworkEnrichmentService
from backend.platform.analysis.inspection.detection import DetectionService
from backend.platform.analysis.inspection.inventory import InventoryBuilder
from backend.platform.analysis.inspection.model import (
    ArtifactAnalysisRole,
    ArtifactInventoryEntry,
    ArtifactProcessingOutcome,
    FrameworkDetection,
    InspectionCoverage,
    LanguageDetection,
    RepositoryInspectionResult,
    RuntimeDetection,
)
from backend.platform.analysis.syntax.base import (
    ParserRequest,
    create_parsing_diagnostic,
)
from backend.platform.analysis.syntax.executor import ParserExecutor
from backend.platform.analysis.syntax.limits import (
    DEFAULT_MAX_FACTS_PER_ANALYSIS,
    DEFAULT_MAX_FACTS_PER_ARTIFACT,
    DEFAULT_MAX_SERIALIZED_F2_BYTES,
)
from backend.platform.analysis.syntax.model import ParseStatus, SyntaxDocument

if TYPE_CHECKING:
    from backend.platform.config import Settings


_SHA256_HEX_RE = re.compile(r"[0-9a-fA-F]{64}")


@dataclass(frozen=True)
class RepositoryInspectionExecution:
    """M2 execution value plus shared diagnostics recorded by orchestration later."""

    result: RepositoryInspectionResult
    diagnostics: tuple[AnalysisDiagnostic, ...]


@dataclass(frozen=True)
class InspectionPreparation:
    """Immutable output of inventory and preliminary detection stages."""

    inventory: tuple[ArtifactInventoryEntry, ...]
    languages: tuple[LanguageDetection, ...]
    runtimes: tuple[RuntimeDetection, ...]
    framework_candidates: tuple[FrameworkDetection, ...]
    diagnostics: tuple[AnalysisDiagnostic, ...] = ()
    manifest_documents: tuple[SyntaxDocument, ...] = ()


class RepositoryInspectionService:
    """Build a deterministic pre-enrichment F2 result without M1 lifecycle work."""

    def __init__(
        self,
        parser_executor: ParserExecutor | None = None,
        framework_enrichment: FrameworkEnrichmentService | None = None,
        *,
        max_facts_per_artifact: int = DEFAULT_MAX_FACTS_PER_ARTIFACT,
        max_facts_per_analysis: int = DEFAULT_MAX_FACTS_PER_ANALYSIS,
        max_serialized_f2_bytes: int = DEFAULT_MAX_SERIALIZED_F2_BYTES,
    ) -> None:
        if (
            min(
                max_facts_per_artifact,
                max_facts_per_analysis,
                max_serialized_f2_bytes,
            )
            <= 0
        ):
            raise ValueError("M2 extraction limits must be positive")
        self._parser = parser_executor or ParserExecutor(
            max_facts_per_artifact=max_facts_per_artifact,
            max_ipc_result_bytes=max_serialized_f2_bytes,
        )
        self._max_facts_per_artifact = max_facts_per_artifact
        self._max_facts_per_analysis = max_facts_per_analysis
        self._max_serialized_f2_bytes = max_serialized_f2_bytes
        self._detection = DetectionService()
        self._framework_enrichment = (
            framework_enrichment or FrameworkEnrichmentService()
        )

    @classmethod
    def from_settings(
        cls, settings: Settings | None = None
    ) -> RepositoryInspectionService:
        if settings is None:
            from backend.platform.config import get_settings

            settings = get_settings()
        return cls(
            ParserExecutor.from_settings(
                settings,
                max_ipc_result_bytes=settings.parser_max_serialized_f2_bytes,
            ),
            max_facts_per_artifact=settings.parser_max_facts_per_artifact,
            max_facts_per_analysis=settings.parser_max_facts_per_analysis,
            max_serialized_f2_bytes=settings.parser_max_serialized_f2_bytes,
        )

    def inspect(
        self,
        analysis_input: AnalysisInput,
        *,
        configuration_fingerprint: str,
        preparation: InspectionPreparation | None = None,
        report_progress: Callable[[int, int, str | None], None] | None = None,
        check_cancellation: Callable[[], None] | None = None,
    ) -> RepositoryInspectionExecution:
        """Inspect artifacts once, enrich generic facts, and return canonical F2."""
        prepared = preparation or self.prepare(analysis_input)
        inventory = prepared.inventory
        languages = prepared.languages
        runtimes = prepared.runtimes
        candidates = prepared.framework_candidates

        entries = {entry.artifact_id: entry for entry in inventory}
        documents: list[SyntaxDocument] = list(prepared.manifest_documents)
        framework_hints: dict[UUID, Mapping[str, Mapping[str, str]]] = {}
        diagnostics = list(prepared.diagnostics)
        total_facts = sum(len(document.facts) for document in documents)
        for manifest_document in prepared.manifest_documents:
            entry = entries[manifest_document.artifact_id]
            entries[manifest_document.artifact_id] = replace(
                entry,
                processing_outcome=ArtifactProcessingOutcome.ANALYZED,
            )
        for diagnostic in prepared.diagnostics:
            if diagnostic.artifact_id in entries and diagnostic.code.startswith(
                "manifest_"
            ):
                entry = entries[diagnostic.artifact_id]
                entries[diagnostic.artifact_id] = replace(
                    entry,
                    processing_outcome=ArtifactProcessingOutcome.FAILED,
                    reason_codes=(*entry.reason_codes, diagnostic.code),
                )
        semantic_artifacts = tuple(
            artifact
            for artifact in analysis_input.artifact_catalog.artifacts
            if entries[artifact.id].analysis_role == ArtifactAnalysisRole.SEMANTIC
        )
        total_semantic = len(semantic_artifacts)
        processed_semantic = 0

        for artifact in analysis_input.artifact_catalog.artifacts:
            entry = entries[artifact.id]
            if entry.analysis_role != ArtifactAnalysisRole.SEMANTIC:
                continue
            if check_cancellation is not None:
                check_cancellation()
            try:
                content = analysis_input.content_reader.read_bytes(
                    artifact,
                    max_bytes=min(
                        analysis_input.effective_configuration.max_file_size_bytes,
                        5 * 1024 * 1024,
                    ),
                )
                if len(content) != artifact.size_bytes:
                    raise ValueError(
                        "artifact content size did not match immutable metadata"
                    )
                if _SHA256_HEX_RE.fullmatch(artifact.content_hash):
                    actual_hash = hashlib.sha256(content).hexdigest()
                    if actual_hash.lower() != artifact.content_hash.lower():
                        raise ValueError(
                            "artifact content hash did not match immutable metadata"
                        )
            except Exception as exc:
                diagnostic = create_parsing_diagnostic(
                    analysis_input.analysis_id,
                    artifact.id,
                    entry.path,
                    "artifact_read_failed",
                    f"Artifact content could not be read ({type(exc).__name__})",
                    DiagnosticSeverity.ERROR,
                )
                diagnostics.append(diagnostic)
                entries[artifact.id] = replace(
                    entry,
                    processing_outcome=ArtifactProcessingOutcome.FAILED,
                    reason_codes=(*entry.reason_codes, "artifact_read_failed"),
                )
                processed_semantic += 1
                if report_progress is not None:
                    report_progress(
                        processed_semantic,
                        total_semantic,
                        f"Inspection failed for {entry.path}",
                    )
                continue

            try:
                parse_result = self._parser.execute(
                    ParserRequest(
                        artifact_id=artifact.id,
                        path=entry.path,
                        content=content,
                        language=entry.detected_language or "",
                        analysis_id=analysis_input.analysis_id,
                        configuration_fingerprint=configuration_fingerprint,
                        max_file_size_bytes=min(
                            analysis_input.effective_configuration.max_file_size_bytes,
                            5 * 1024 * 1024,
                        ),
                        max_facts_per_artifact=self._max_facts_per_artifact,
                    )
                )
            except Exception as exc:
                diagnostic = create_parsing_diagnostic(
                    analysis_input.analysis_id,
                    artifact.id,
                    entry.path,
                    "parser_process_failed",
                    f"Parser execution failed ({type(exc).__name__})",
                    DiagnosticSeverity.ERROR,
                )
                diagnostics.append(diagnostic)
                entries[artifact.id] = replace(
                    entry,
                    processing_outcome=ArtifactProcessingOutcome.FAILED,
                    reason_codes=(*entry.reason_codes, "syntax_extraction_failed"),
                )
                processed_semantic += 1
                if report_progress is not None:
                    report_progress(
                        processed_semantic,
                        total_semantic,
                        f"Inspection failed for {entry.path}",
                    )
                continue

            diagnostics.extend(parse_result.diagnostics)
            document = parse_result.document
            if (
                not parse_result.success
                or document is None
                or document.parse_status == ParseStatus.FAILED
            ):
                reason = (
                    "resource_limit_exceeded"
                    if any(
                        d.code == "resource_limit_exceeded"
                        for d in parse_result.diagnostics
                    )
                    else "syntax_extraction_failed"
                )
                entries[artifact.id] = replace(
                    entry,
                    processing_outcome=ArtifactProcessingOutcome.FAILED,
                    reason_codes=(*entry.reason_codes, reason),
                )
                if document is not None:
                    documents.append(document)
                processed_semantic += 1
                if report_progress is not None:
                    report_progress(
                        processed_semantic,
                        total_semantic,
                        f"Inspected {entry.path}",
                    )
                continue

            total_facts += len(document.facts)
            if total_facts > self._max_facts_per_analysis:
                diagnostic = create_parsing_diagnostic(
                    analysis_input.analysis_id,
                    artifact.id,
                    entry.path,
                    "resource_limit_exceeded",
                    (
                        "Analysis exceeded the approved aggregate limit of "
                        f"{self._max_facts_per_analysis} facts"
                    ),
                    DiagnosticSeverity.ERROR,
                    details={
                        "limit": self._max_facts_per_analysis,
                        "scope": "analysis_facts",
                    },
                )
                diagnostics.append(diagnostic)
                return self._failed_atomic_result(
                    analysis_input,
                    entries,
                    languages,
                    runtimes,
                    candidates,
                    diagnostics,
                    configuration_fingerprint,
                    "analysis_fact_limit_exceeded",
                )

            documents.append(document)
            framework_hints[artifact.id] = parse_result.framework_hints
            entries[artifact.id] = replace(
                entry,
                processing_outcome=(
                    ArtifactProcessingOutcome.ANALYZED_WITH_WARNINGS
                    if document.parse_status == ParseStatus.PARSED_WITH_ERRORS
                    or parse_result.diagnostics
                    else ArtifactProcessingOutcome.ANALYZED
                ),
            )
            processed_semantic += 1
            if report_progress is not None:
                report_progress(
                    processed_semantic,
                    total_semantic,
                    f"Inspected {entry.path}",
                )

        ordered_entries = tuple(sorted(entries.values(), key=lambda item: item.path))
        ordered_documents = tuple(sorted(documents, key=lambda item: item.path))
        frameworks = self._detection.finalize_framework_detections(
            candidates, ordered_documents
        )
        if check_cancellation is not None:
            check_cancellation()
        if report_progress is not None:
            report_progress(
                total_semantic,
                total_semantic,
                "Enriching confirmed framework evidence",
            )
        try:
            ordered_documents = self._framework_enrichment.enrich(
                ordered_documents,
                frameworks,
                analysis_input.analysis_id,
                framework_hints,
            )
        except Exception as exc:
            # Enrichment is degradable: generic facts remain complete and usable.
            diagnostic = create_parsing_diagnostic(
                analysis_input.analysis_id,
                next(
                    (document.artifact_id for document in ordered_documents),
                    analysis_input.analysis_id,
                ),
                "<repository>",
                "framework_enrichment_failed",
                f"Framework enrichment failed ({type(exc).__name__})",
                DiagnosticSeverity.WARNING,
            )
            diagnostics.append(diagnostic)
            entries = {
                artifact_id: (
                    replace(
                        entry,
                        processing_outcome=ArtifactProcessingOutcome.ANALYZED_WITH_WARNINGS,
                        reason_codes=(
                            *entry.reason_codes,
                            "framework_enrichment_failed",
                        ),
                    )
                    if entry.processing_outcome == ArtifactProcessingOutcome.ANALYZED
                    else entry
                )
                for artifact_id, entry in entries.items()
            }
            ordered_entries = tuple(
                sorted(entries.values(), key=lambda item: item.path)
            )

        enriched_fact_count = sum(len(document.facts) for document in ordered_documents)
        if (
            any(
                len(document.facts) > self._max_facts_per_artifact
                for document in ordered_documents
            )
            or enriched_fact_count > self._max_facts_per_analysis
        ):
            diagnostic = create_parsing_diagnostic(
                analysis_input.analysis_id,
                next(
                    (document.artifact_id for document in ordered_documents),
                    analysis_input.analysis_id,
                ),
                "<repository>",
                "resource_limit_exceeded",
                "Framework enrichment exceeded an approved F2 fact limit",
                DiagnosticSeverity.ERROR,
                details={"scope": "enriched_facts"},
            )
            diagnostics.append(diagnostic)
            return self._failed_atomic_result(
                analysis_input,
                entries,
                languages,
                runtimes,
                frameworks,
                diagnostics,
                configuration_fingerprint,
                "framework_fact_limit_exceeded",
            )
        inspection_result = self._build_result(
            analysis_input,
            ordered_entries,
            ordered_documents,
            languages,
            runtimes,
            frameworks,
            diagnostics,
            configuration_fingerprint,
        )
        if (
            len(inspection_result.to_canonical_json().encode("utf-8"))
            > self._max_serialized_f2_bytes
        ):
            diagnostic = create_parsing_diagnostic(
                analysis_input.analysis_id,
                next(
                    (
                        entry.artifact_id
                        for entry in ordered_entries
                        if entry.analysis_role == ArtifactAnalysisRole.SEMANTIC
                    ),
                    analysis_input.analysis_id,
                ),
                "<repository>",
                "resource_limit_exceeded",
                (
                    "F2 result exceeded the approved serialized limit of "
                    f"{self._max_serialized_f2_bytes} bytes"
                ),
                DiagnosticSeverity.ERROR,
                details={
                    "limit": self._max_serialized_f2_bytes,
                    "scope": "serialized_f2",
                },
            )
            diagnostics.append(diagnostic)
            return self._failed_atomic_result(
                analysis_input,
                entries,
                languages,
                runtimes,
                candidates,
                diagnostics,
                configuration_fingerprint,
                "serialized_f2_limit_exceeded",
            )
        return RepositoryInspectionExecution(inspection_result, tuple(diagnostics))

    def prepare(self, analysis_input: AnalysisInput) -> InspectionPreparation:
        """Build deterministic inventory and preliminary detection once."""
        inventory, _ = InventoryBuilder(
            analysis_input.effective_configuration
        ).build_inventory(analysis_input.artifact_catalog.artifacts)
        languages = self._detection.detect_languages(inventory)
        runtimes = self._detection.detect_runtimes(inventory)
        manifest_documents: list[SyntaxDocument] = []
        candidates, _, diagnostics = self._detection.detect_framework_candidates(
            analysis_input.artifact_catalog.artifacts,
            inventory,
            analysis_input.content_reader,
            analysis_input.analysis_id,
            manifest_documents=manifest_documents,
        )
        return InspectionPreparation(
            inventory=inventory,
            languages=languages,
            runtimes=runtimes,
            framework_candidates=candidates,
            diagnostics=diagnostics,
            manifest_documents=tuple(
                sorted(manifest_documents, key=lambda document: document.path)
            ),
        )

    def _failed_atomic_result(
        self,
        analysis_input: AnalysisInput,
        entries: dict[UUID, ArtifactInventoryEntry],
        languages: tuple[LanguageDetection, ...],
        runtimes: tuple[RuntimeDetection, ...],
        frameworks: tuple[FrameworkDetection, ...],
        diagnostics: list[AnalysisDiagnostic],
        configuration_fingerprint: str,
        reason: str,
    ) -> RepositoryInspectionExecution:
        failed_entries = tuple(
            sorted(
                (
                    (
                        replace(
                            entry,
                            processing_outcome=ArtifactProcessingOutcome.FAILED,
                            reason_codes=(*entry.reason_codes, reason),
                        )
                        if entry.analysis_role == ArtifactAnalysisRole.SEMANTIC
                        else entry
                    )
                    for entry in entries.values()
                ),
                key=lambda item: item.path,
            )
        )
        result = self._build_result(
            analysis_input,
            failed_entries,
            (),
            languages,
            runtimes,
            frameworks,
            diagnostics,
            configuration_fingerprint,
        )
        return RepositoryInspectionExecution(result, tuple(diagnostics))

    @staticmethod
    def _coverage(entries: tuple[ArtifactInventoryEntry, ...]) -> InspectionCoverage:
        roles = Counter(entry.analysis_role.value for entry in entries)
        outcomes = Counter(entry.processing_outcome.value for entry in entries)
        languages = Counter(entry.detected_language or "unknown" for entry in entries)
        return InspectionCoverage(
            total_artifacts=len(entries),
            total_bytes=sum(entry.size_bytes for entry in entries),
            role_counts=dict(roles),
            outcome_counts=dict(outcomes),
            language_counts=dict(languages),
            processed_artifacts=sum(
                entry.processing_outcome
                in (
                    ArtifactProcessingOutcome.ANALYZED,
                    ArtifactProcessingOutcome.ANALYZED_WITH_WARNINGS,
                )
                for entry in entries
            ),
            failed_artifacts=sum(
                entry.processing_outcome == ArtifactProcessingOutcome.FAILED
                for entry in entries
            ),
        )

    @classmethod
    def _build_result(
        cls,
        analysis_input: AnalysisInput,
        entries: tuple[ArtifactInventoryEntry, ...],
        documents: tuple[SyntaxDocument, ...],
        languages: tuple[LanguageDetection, ...],
        runtimes: tuple[RuntimeDetection, ...],
        frameworks: tuple[FrameworkDetection, ...],
        diagnostics: list[AnalysisDiagnostic],
        configuration_fingerprint: str,
    ) -> RepositoryInspectionResult:
        return RepositoryInspectionResult(
            analysis_id=analysis_input.analysis_id,
            project_id=analysis_input.project_id,
            repository_id=analysis_input.repository_id,
            snapshot_id=analysis_input.snapshot_id,
            analyzer_version=analysis_input.analyzer_version,
            configuration_fingerprint=configuration_fingerprint,
            inventory=entries,
            syntax_documents=documents,
            language_detections=languages,
            runtime_detections=runtimes,
            framework_detections=frameworks,
            coverage=cls._coverage(entries),
            diagnostic_ids=tuple(str(item.id) for item in diagnostics),
        )
