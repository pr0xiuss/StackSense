"""Framework-enrichment contracts and deterministic orchestration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from backend.platform.analysis.syntax.model import (
    FrameworkFact,
    SyntaxDocument,
    sort_facts,
)

if TYPE_CHECKING:
    from backend.platform.analysis.inspection.model import FrameworkDetection


class FrameworkEnricher(Protocol):
    """Enrich parser-neutral documents without reading or reparsing source."""

    @property
    def supported_frameworks(self) -> frozenset[str]: ...

    def enrich(
        self,
        document: SyntaxDocument,
        frameworks: frozenset[str],
        framework_hints: Mapping[str, Mapping[str, str]] | None = None,
    ) -> tuple[FrameworkFact, ...]: ...


class FrameworkEnrichmentService:
    """Apply framework enrichers once to confirmed framework documents."""

    def __init__(self, enrichers: Iterable[FrameworkEnricher] | None = None) -> None:
        if enrichers is None:
            from backend.platform.analysis.frameworks.javascript import (
                JavaScriptFrameworkEnricher,
            )
            from backend.platform.analysis.frameworks.python import (
                PythonFrameworkEnricher,
            )

            enrichers = (PythonFrameworkEnricher(), JavaScriptFrameworkEnricher())
        self._enrichers = tuple(
            sorted(enrichers, key=lambda item: sorted(item.supported_frameworks))
        )

    def enrich(
        self,
        documents: Iterable[SyntaxDocument],
        detections: Iterable[FrameworkDetection],
        analysis_id: UUID,
        framework_hints: Mapping[UUID, Mapping[str, Mapping[str, str]]] | None = None,
    ) -> tuple[SyntaxDocument, ...]:
        """Return documents with framework facts appended deterministically.

        ``analysis_id`` is intentionally accepted at the orchestration boundary so a
        future diagnostic collector can attribute degradable enricher failures. The
        current built-in enrichers are total functions over immutable facts.
        """
        del analysis_id
        hints_by_artifact = framework_hints or {}
        confirmed = frozenset(
            item.framework for item in detections if item.status == "confirmed"
        )
        enriched: list[SyntaxDocument] = []
        for document in sorted(documents, key=lambda item: item.path):
            additions: list[FrameworkFact] = []
            for enricher in self._enrichers:
                active = confirmed & enricher.supported_frameworks
                if active:
                    additions.extend(
                        enricher.enrich(
                            document,
                            active,
                            hints_by_artifact.get(document.artifact_id, {}),
                        )
                    )
            enriched.append(
                replace(document, facts=sort_facts((*document.facts, *additions)))
                if additions
                else document
            )
        return tuple(enriched)
