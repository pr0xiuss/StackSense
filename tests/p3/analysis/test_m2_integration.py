"""Batch 4 M1 adapter, F2 handoff, recovery, and production-wiring tests."""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID, uuid4

import pytest

from backend.platform.analysis.application.execution import ExecutionContext
from backend.platform.analysis.application.registry import StageHandlerRegistry
from backend.platform.analysis.domain.analysis import AnalysisConfiguration
from backend.platform.analysis.domain.constants import AnalysisStageName
from backend.platform.analysis.domain.diagnostic import AnalysisDiagnostic
from backend.platform.analysis.domain.event import AnalysisEventType
from backend.platform.analysis.domain.input import (
    AnalysisArtifact,
    AnalysisInput,
    ArtifactCatalog,
    ArtifactContentReader,
)
from backend.platform.analysis.frameworks.base import FrameworkEnrichmentService
from backend.platform.analysis.inspection.handlers import (
    M2ExecutionCoordinator,
    create_m2_stage_handlers,
)
from backend.platform.analysis.inspection.model import RepositoryInspectionResult
from backend.platform.analysis.inspection.service import RepositoryInspectionService
from backend.platform.analysis.syntax.base import ParserRequest, ParserResult
from backend.platform.analysis.syntax.javascript import TreeSitterJsTsAdapter
from backend.platform.analysis.syntax.model import FrameworkFact, ManifestFact
from backend.platform.analysis.syntax.python import PythonAstAdapter
from backend.platform.ingestion.domain.constants import ArtifactCategory, SupportLevel
from backend.worker.tasks import get_worker_registry, set_worker_registry


class _MemoryReader(ArtifactContentReader):
    def __init__(self, values: dict[UUID, bytes]) -> None:
        self.values = values

    def read_bytes(
        self, artifact: AnalysisArtifact, max_bytes: int | None = None
    ) -> bytes:
        value = self.values[artifact.id]
        if max_bytes is not None and len(value) > max_bytes:
            raise ValueError("bounded read exceeded")
        return value

    def open_stream(self, artifact: AnalysisArtifact):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def exists(self, artifact: AnalysisArtifact) -> bool:
        return artifact.id in self.values


@dataclass
class _InProcessExecutor:
    calls: int = 0

    def execute(self, request: ParserRequest) -> ParserResult:
        self.calls += 1
        if request.language == "python":
            return PythonAstAdapter().parse(request)
        return TreeSitterJsTsAdapter().parse(request)


class _FailingEnrichment(FrameworkEnrichmentService):
    def enrich(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        raise RuntimeError("intentional test failure")


class _Context(ExecutionContext):
    def __init__(self, analysis_input: AnalysisInput) -> None:
        self._input = analysis_input
        self._job_id = uuid4()
        self._stage_name = AnalysisStageName.INVENTORY.value
        self.progress: list[tuple[int, int, str | None]] = []
        self.diagnostics: list[AnalysisDiagnostic] = []
        self.events: list[AnalysisEventType] = []
        self.cancelled = False

    @property
    def analysis_id(self) -> UUID:
        return self._input.analysis_id

    @property
    def project_id(self) -> UUID:
        return self._input.project_id

    @property
    def job_id(self) -> UUID:
        return self._job_id

    @property
    def stage_id(self) -> UUID:
        return uuid4()

    @property
    def stage_name(self) -> str:
        return self._stage_name

    @property
    def input(self) -> AnalysisInput:
        return self._input

    def is_cancellation_requested(self) -> bool:
        return self.cancelled

    def report_progress(
        self, processed_items: int, total_items: int, message: str | None = None
    ) -> None:
        self.progress.append((processed_items, total_items, message))

    def record_diagnostic(self, diagnostic: AnalysisDiagnostic) -> None:
        self.diagnostics.append(diagnostic)

    def record_event(
        self,
        event_type: AnalysisEventType,
        payload: dict[str, Any] | None = None,
    ) -> None:
        del payload
        self.events.append(event_type)


def _input() -> AnalysisInput:
    sources = (
        (
            "requirements.txt",
            b"fastapi==0.100\n",
            ArtifactCategory.CONFIGURATION,
            SupportLevel.PARTIAL,
        ),
        (
            "frontend/package.json",
            b'{"devDependencies":{"typescript":"^5.0.0"}}',
            ArtifactCategory.CONFIGURATION,
            SupportLevel.PARTIAL,
        ),
        (
            "app/api.py",
            (
                b"from fastapi import FastAPI\n"
                b"@app.get('/secret')\n"
                b"def home():\n    pass\n"
            ),
            ArtifactCategory.SOURCE_CODE,
            SupportLevel.FULL,
        ),
    )
    artifacts: list[AnalysisArtifact] = []
    content: dict[UUID, bytes] = {}
    revision_id = uuid4()
    for path, value, category, support in sources:
        artifact = AnalysisArtifact(
            id=uuid4(),
            revision_id=revision_id,
            path=path,
            size_bytes=len(value),
            content_hash=f"sha256:{path}",
            category=category,
            support_level=support,
        )
        artifacts.append(artifact)
        content[artifact.id] = value
    return AnalysisInput(
        analysis_id=uuid4(),
        project_id=uuid4(),
        repository_id=uuid4(),
        snapshot_id=revision_id,
        revision_identifier="main",
        source_hash="sha256:repository",
        total_files=len(artifacts),
        total_bytes=sum(item.size_bytes for item in artifacts),
        effective_configuration=AnalysisConfiguration(),
        artifact_catalog=ArtifactCatalog(tuple(artifacts)),
        content_reader=_MemoryReader(content),
    )


def _coordinator(executor: _InProcessExecutor | None = None) -> M2ExecutionCoordinator:
    return M2ExecutionCoordinator(
        RepositoryInspectionService(parser_executor=executor or _InProcessExecutor())  # type: ignore[arg-type]
    )


def _m3_consumer_stub(result: RepositoryInspectionResult) -> tuple[str, ...]:
    """Exercise only the frozen parser-neutral value supplied by orchestration."""
    assert result.f2_version == "1.0.0"
    return tuple(document.path for document in result.syntax_documents)


def test_ordered_handlers_produce_attempt_scoped_immutable_f2_once() -> None:
    analysis_input = _input()
    executor = _InProcessExecutor()
    coordinator = _coordinator(executor)
    context = _Context(analysis_input)

    for handler in create_m2_stage_handlers(coordinator):
        context._stage_name = handler.stage_name
        result = handler.execute(context)
        assert result.stage_name == handler.stage_name

    f2 = coordinator.handoff.require_result(context.analysis_id, context.job_id)
    assert executor.calls == 1
    assert f2.framework_detections[0].framework == "fastapi"
    assert any(
        isinstance(fact, FrameworkFact)
        for document in f2.syntax_documents
        for fact in document.facts
    )
    route = next(
        fact
        for document in f2.syntax_documents
        for fact in document.facts
        if isinstance(fact, FrameworkFact) and fact.fact_type == "route"
    )
    assert route.name == "/secret"
    assert route.details == {
        "method": "GET",
        "path": "/secret",
        "reference_kind": "decorator",
    }
    assert context.events == []
    assert context.progress
    assert _m3_consumer_stub(f2) == (
        "app/api.py",
        "frontend/package.json",
        "requirements.txt",
    )
    assert any(
        isinstance(fact, ManifestFact) and fact.name == "fastapi"
        for document in f2.syntax_documents
        for fact in document.facts
    )
    assert any(
        isinstance(fact, ManifestFact)
        and fact.name == "typescript"
        and fact.scope == "devDependencies"
        and fact.is_dev
        for document in f2.syntax_documents
        for fact in document.facts
    )


def test_inspection_rejects_content_that_breaks_immutable_hash() -> None:
    content = b"def ok():\n    return 1\n"
    other = b"def no():\n    return 2\n"
    assert len(content) == len(other)
    revision_id = uuid4()
    artifact = AnalysisArtifact(
        id=uuid4(),
        revision_id=revision_id,
        path="app.py",
        size_bytes=len(content),
        content_hash=hashlib.sha256(other).hexdigest(),
        category=ArtifactCategory.SOURCE_CODE,
        support_level=SupportLevel.FULL,
    )
    analysis_input = AnalysisInput(
        analysis_id=uuid4(),
        project_id=uuid4(),
        repository_id=uuid4(),
        snapshot_id=revision_id,
        revision_identifier="main",
        source_hash="sha256:repository",
        total_files=1,
        total_bytes=len(content),
        effective_configuration=AnalysisConfiguration(),
        artifact_catalog=ArtifactCatalog((artifact,)),
        content_reader=_MemoryReader({artifact.id: content}),
    )
    executor = _InProcessExecutor()

    execution = RepositoryInspectionService(parser_executor=executor).inspect(  # type: ignore[arg-type]
        analysis_input,
        configuration_fingerprint="f" * 64,
    )

    assert executor.calls == 0
    assert execution.result.inventory[0].processing_outcome.value == "failed"
    assert any(
        diagnostic.code == "artifact_read_failed"
        for diagnostic in execution.diagnostics
    )


def test_recovery_rebuild_is_byte_equivalent_and_has_no_lifecycle_side_effects() -> (
    None
):
    analysis_input = _input()
    coordinator = _coordinator()
    context = _Context(analysis_input)
    for handler in create_m2_stage_handlers(coordinator):
        context._stage_name = handler.stage_name
        handler.execute(context)
    original = coordinator.handoff.require_result(context.analysis_id, context.job_id)
    signature = coordinator.signature(analysis_input)
    progress_before = tuple(context.progress)
    diagnostics_before = tuple(context.diagnostics)
    coordinator.handoff.drop_result(context.analysis_id, context.job_id)

    rebuilt = coordinator.rebuild_lost_result(
        analysis_input,
        job_id=context.job_id,
        expected_signature=signature,
    )

    assert rebuilt.result.to_canonical_json() == original.to_canonical_json()
    assert tuple(context.progress) == progress_before
    assert tuple(context.diagnostics) == diagnostics_before
    assert context.events == []

    changed = replace(
        analysis_input,
        effective_configuration=replace(
            analysis_input.effective_configuration,
            exclude_paths=("app/**",),
        ),
    )
    with pytest.raises(ValueError, match="signature mismatch"):
        coordinator.rebuild_lost_result(
            changed,
            job_id=context.job_id,
            expected_signature=signature,
        )
    with pytest.raises(ValueError, match="signature mismatch"):
        coordinator.rebuild_lost_result(
            replace(analysis_input, revision_identifier="different"),
            job_id=context.job_id,
            expected_signature=signature,
        )


def test_concurrent_recovery_rebuilds_are_canonical() -> None:
    analysis_input = _input()
    coordinator = _coordinator()
    signature = coordinator.signature(analysis_input)
    job_id = uuid4()

    def rebuild() -> str:
        return coordinator.rebuild_lost_result(
            analysis_input,
            job_id=job_id,
            expected_signature=signature,
        ).result.to_canonical_json()

    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs = tuple(pool.map(lambda _: rebuild(), range(8)))

    assert len(set(outputs)) == 1


def test_diagnostic_result_is_byte_stable_and_attempt_can_be_released() -> None:
    analysis_input = _input()
    source = next(
        artifact
        for artifact in analysis_input.artifact_catalog.artifacts
        if artifact.path.endswith(".py")
    )
    reader = analysis_input.content_reader
    assert isinstance(reader, _MemoryReader)
    malformed = b"def broken(:\n"
    reader.values[source.id] = malformed + b" " * (source.size_bytes - len(malformed))
    coordinator = _coordinator()
    signature = coordinator.signature(analysis_input)
    job_id = uuid4()

    first = coordinator.rebuild_lost_result(
        analysis_input,
        job_id=job_id,
        expected_signature=signature,
    ).result.to_canonical_json()
    second = coordinator.rebuild_lost_result(
        analysis_input,
        job_id=job_id,
        expected_signature=signature,
    ).result.to_canonical_json()

    assert first == second
    coordinator.release_attempt(analysis_input.analysis_id, job_id)
    with pytest.raises(LookupError, match="unavailable"):
        coordinator.handoff.require_result(analysis_input.analysis_id, job_id)


def test_enrichment_failure_preserves_generic_facts_and_becomes_warning() -> None:
    analysis_input = _input()
    executor = _InProcessExecutor()
    service = RepositoryInspectionService(
        parser_executor=executor,  # type: ignore[arg-type]
        framework_enrichment=_FailingEnrichment(),
    )
    execution = service.inspect(
        analysis_input,
        configuration_fingerprint="test",
    )

    assert executor.calls == 1
    assert execution.result.syntax_documents[0].facts
    assert not any(
        isinstance(fact, FrameworkFact)
        for fact in execution.result.syntax_documents[0].facts
    )
    assert any(
        diagnostic.code == "framework_enrichment_failed"
        for diagnostic in execution.diagnostics
    )


def test_cancellation_checkpoint_runs_before_artifact_parsing() -> None:
    coordinator = _coordinator()
    context = _Context(_input())
    handlers = create_m2_stage_handlers(coordinator)
    for handler in handlers[:3]:
        context._stage_name = handler.stage_name
        handler.execute(context)
    context.cancelled = True

    with pytest.raises(Exception, match="cancellation checkpoint"):
        handlers[3].execute(context)


def test_production_registry_contains_only_real_m2_handlers_from_this_module() -> None:
    set_worker_registry(None)
    try:
        registry = get_worker_registry()
        assert registry.registered_stages() == (
            AnalysisStageName.INPUT_VALIDATION.value,
            AnalysisStageName.INVENTORY.value,
            AnalysisStageName.LANGUAGE_DETECTION.value,
            AnalysisStageName.FRAMEWORK_DETECTION.value,
            AnalysisStageName.SYNTAX_EXTRACTION.value,
            AnalysisStageName.IR_CONSTRUCTION.value,
        )
    finally:
        set_worker_registry(StageHandlerRegistry())
