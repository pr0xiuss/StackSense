"""Phase 3 Module 3 Batch 3 end-to-end integration and handoff verification tests.

Tests worker registry stage ordering, attempt-scoped F2/F3 handoff, boundary checks,
cancellation checkpoints, error diagnostics, and M4 consumer projection stubs.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from backend.platform.analysis.application.execution import (
    ExecutionContext,
)
from backend.platform.analysis.application.handoff import (
    AnalysisAttemptStore,
    F3ResultReader,
)
from backend.platform.analysis.application.registry import StageHandlerRegistry
from backend.platform.analysis.domain.analysis import AnalysisConfiguration
from backend.platform.analysis.domain.constants import (
    AnalysisStageName,
    DiagnosticCategory,
    DiagnosticSeverity,
    StageStatus,
)
from backend.platform.analysis.domain.diagnostic import AnalysisDiagnostic
from backend.platform.analysis.domain.event import AnalysisEventType
from backend.platform.analysis.domain.input import (
    AnalysisArtifact,
    AnalysisInput,
    ArtifactCatalog,
    ArtifactContentReader,
)
from backend.platform.analysis.inspection.handlers import M2ExecutionCoordinator
from backend.platform.analysis.inspection.model import RepositoryInspectionResult
from backend.platform.analysis.ir.handlers import (
    IRConstructionStageHandler,
    register_ir_stage_handler,
)
from backend.platform.analysis.ir.model import (
    IRCapacityLimitError,
    IRConstructionError,
    IRDocument,
    IREntityKind,
)
from backend.platform.analysis.ir.service import IRConstructionService
from backend.platform.analysis.syntax.model import (
    DeclarationKind,
    ParseStatus,
)
from backend.platform.config import Settings
from backend.platform.errors import AnalysisCancelledError
from backend.platform.ingestion.domain.constants import (
    ArtifactCategory,
    SupportLevel,
)
from backend.worker.tasks import (
    build_ir_construction_service,
    get_attempt_store,
    get_worker_registry,
    set_worker_registry,
)
from tests.p3.analysis.m3_test_helper import (
    create_mock_declaration_fact,
    create_mock_inspection_result,
    create_mock_inventory_entry,
    create_mock_syntax_document,
)


class _DummyContentReader(ArtifactContentReader):
    """Stub content reader for integration testing."""

    def read_bytes(
        self, artifact: AnalysisArtifact, max_bytes: int | None = None
    ) -> bytes:
        return b""

    def open_stream(self, artifact: AnalysisArtifact):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def exists(self, artifact: AnalysisArtifact) -> bool:
        return True


class _MockExecutionContext(ExecutionContext):
    """Execution context mock tracking progress, diagnostics, and events."""

    def __init__(
        self,
        analysis_input: AnalysisInput,
        job_id: UUID | None = None,
        stage_name: str = AnalysisStageName.IR_CONSTRUCTION.value,
    ) -> None:
        self._input = analysis_input
        self._job_id = job_id or uuid4()
        self._stage_id = uuid4()
        self._stage_name = stage_name
        self.progress: list[tuple[int, int, str | None]] = []
        self.diagnostics: list[AnalysisDiagnostic] = []
        self.events: list[tuple[AnalysisEventType, dict[str, Any] | None]] = []
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
        return self._stage_id

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
        self.events.append((event_type, payload))


def _create_test_context(
    analysis_id: UUID | None = None,
    project_id: UUID | None = None,
    snapshot_id: UUID | None = None,
    job_id: UUID | None = None,
) -> _MockExecutionContext:
    aid = analysis_id or uuid4()
    pid = project_id or uuid4()
    sid = snapshot_id or uuid4()
    artifact = AnalysisArtifact(
        id=uuid4(),
        revision_id=sid,
        path="src/main.py",
        size_bytes=128,
        content_hash="sha256:abc",
        category=ArtifactCategory.SOURCE_CODE,
        support_level=SupportLevel.FULL,
    )
    analysis_input = AnalysisInput(
        analysis_id=aid,
        project_id=pid,
        repository_id=uuid4(),
        snapshot_id=sid,
        revision_identifier="main",
        source_hash="sha256:rep",
        total_files=1,
        total_bytes=128,
        effective_configuration=AnalysisConfiguration(),
        artifact_catalog=ArtifactCatalog((artifact,)),
        content_reader=_DummyContentReader(),
    )
    return _MockExecutionContext(analysis_input=analysis_input, job_id=job_id)


class TestWorkerRegistryWiring:
    """Tests production worker registry registration and stage sequence."""

    def test_worker_registry_stage_ordering(self) -> None:
        """Verify that IR_CONSTRUCTION is registered in canonical order after M2."""
        set_worker_registry(None)
        registry = get_worker_registry()
        stages = registry.registered_stages()

        assert AnalysisStageName.INVENTORY.value in stages
        assert AnalysisStageName.LANGUAGE_DETECTION.value in stages
        assert AnalysisStageName.FRAMEWORK_DETECTION.value in stages
        assert AnalysisStageName.SYNTAX_EXTRACTION.value in stages
        assert AnalysisStageName.IR_CONSTRUCTION.value in stages

        idx_syntax = stages.index(AnalysisStageName.SYNTAX_EXTRACTION.value)
        idx_ir = stages.index(AnalysisStageName.IR_CONSTRUCTION.value)
        assert idx_ir > idx_syntax

    def test_ir_stage_handler_mandatory_attribute(self) -> None:
        """Verify IR handler has is_mandatory=True and correct stage name."""
        set_worker_registry(None)
        registry = get_worker_registry()
        handler = registry.get(AnalysisStageName.IR_CONSTRUCTION.value)
        assert handler is not None
        assert handler.stage_name == "ir_construction"
        assert handler.is_mandatory is True

    def test_get_attempt_store_singleton_lifecycle(self) -> None:
        """Verify get_attempt_store returns AnalysisAttemptStore instance."""
        set_worker_registry(None)
        store = get_attempt_store()
        assert isinstance(store, AnalysisAttemptStore)
        set_worker_registry(None)

    def test_register_ir_stage_handler_helper(self) -> None:
        """Verify register_ir_stage_handler registers handler into registry."""
        custom_registry = StageHandlerRegistry()
        store = AnalysisAttemptStore()
        handler = register_ir_stage_handler(
            custom_registry,
            f2_reader=store,
            f3_writer=store,
        )
        assert isinstance(handler, IRConstructionStageHandler)
        assert custom_registry.has_handler("ir_construction")
        assert custom_registry.get("ir_construction") is handler


class TestIRStageExecution:
    """Tests end-to-end execution of IRConstructionStageHandler."""

    def test_successful_ir_stage_execution(self) -> None:
        """Verify normal execution publishes F3 document and emits events."""
        ctx = _create_test_context()
        artifact_id = ctx.input.artifact_catalog.artifacts[0].id

        decl = create_mock_declaration_fact(
            fact_key="decl::1",
            name="process_data",
            kind=DeclarationKind.FUNCTION,
        )
        sdoc = create_mock_syntax_document(
            path="src/main.py",
            artifact_id=artifact_id,
            language="python",
            parse_status=ParseStatus.PARSED,
            declarations=(decl,),
        )
        inv = create_mock_inventory_entry(
            path="src/main.py",
            artifact_id=artifact_id,
            revision_id=ctx.input.snapshot_id,
        )
        f2_result = create_mock_inspection_result(
            analysis_id=ctx.analysis_id,
            project_id=ctx.project_id,
            repository_id=ctx.input.repository_id,
            snapshot_id=ctx.input.snapshot_id,
            inventory=(inv,),
            syntax_documents=(sdoc,),
        )

        store = AnalysisAttemptStore()
        store.set_f2_result(ctx.analysis_id, ctx.job_id, f2_result)

        handler = IRConstructionStageHandler(f2_reader=store, f3_writer=store)
        result = handler.execute(ctx)

        assert result.status == StageStatus.COMPLETED
        assert result.stage_name == "ir_construction"
        assert result.processed_items > 0
        assert result.total_items == result.processed_items

        assert result.output_summary is not None
        assert result.output_summary["ir_schema_version"] == "1.0.0"
        assert result.output_summary["total_entities"] == result.processed_items
        assert result.output_summary["is_partial"] is False

        assert store.has_f3_result(ctx.analysis_id, ctx.job_id)
        f3_doc = store.read_f3_result(ctx.analysis_id, ctx.job_id)
        assert isinstance(f3_doc, IRDocument)
        assert f3_doc.ir_schema_version == "1.0.0"
        assert len(f3_doc.entities) == result.processed_items

        # Verify progress reports
        assert len(ctx.progress) >= 2
        assert ctx.progress[0][0] == 0  # Initial progress
        assert ctx.progress[-1][0] == result.processed_items  # Final progress

        # M1 orchestration owns the single public stage-completed event.
        assert ctx.events == []

    def test_missing_f2_result_fails_gracefully(self) -> None:
        """Verify LookupError during F2 read generates diagnostic and FAILED status."""
        ctx = _create_test_context()
        store = AnalysisAttemptStore()
        handler = IRConstructionStageHandler(f2_reader=store, f3_writer=store)

        result = handler.execute(ctx)

        assert result.status == StageStatus.FAILED
        assert result.error_code == "F2_UNAVAILABLE"
        assert len(ctx.diagnostics) == 1
        diag = ctx.diagnostics[0]
        assert diag.code == "F2_HANDOFF_UNAVAILABLE"
        assert diag.severity == DiagnosticSeverity.ERROR
        assert diag.category == DiagnosticCategory.ORCHESTRATION

    def test_analysis_id_mismatch_fails_safely(self) -> None:
        """Verify F2 analysis_id mismatch generates diagnostic and FAILED status."""
        ctx = _create_test_context()
        different_aid = uuid4()
        f2_result = create_mock_inspection_result(
            analysis_id=different_aid,
            snapshot_id=ctx.input.snapshot_id,
        )

        class _MismatchedReader:
            def read_f2_result(
                self,
                analysis_id: UUID,
                job_id: UUID,
                analysis_input: AnalysisInput | None = None,
            ) -> RepositoryInspectionResult:
                return f2_result

        store = AnalysisAttemptStore()
        handler = IRConstructionStageHandler(
            f2_reader=_MismatchedReader(),
            f3_writer=store,
        )

        result = handler.execute(ctx)

        assert result.status == StageStatus.FAILED
        assert result.error_code == "F2_IDENTITY_MISMATCH"
        assert any(d.code == "F2_IDENTITY_MISMATCH" for d in ctx.diagnostics)

    def test_snapshot_id_mismatch_fails_safely(self) -> None:
        """Verify F2 snapshot_id mismatch generates diagnostic and FAILED status."""
        ctx = _create_test_context()
        different_sid = uuid4()
        f2_result = create_mock_inspection_result(
            analysis_id=ctx.analysis_id,
            snapshot_id=different_sid,
        )

        store = AnalysisAttemptStore()
        store.set_f2_result(ctx.analysis_id, ctx.job_id, f2_result)
        handler = IRConstructionStageHandler(f2_reader=store, f3_writer=store)

        result = handler.execute(ctx)

        assert result.status == StageStatus.FAILED
        assert result.error_code == "F2_SNAPSHOT_MISMATCH"
        assert any(d.code == "F2_SNAPSHOT_MISMATCH" for d in ctx.diagnostics)

    def test_cancellation_checkpoint_triggers_cancellation_error(self) -> None:
        """Verify cooperative cancellation check raises AnalysisCancelledError."""
        ctx = _create_test_context()
        ctx.cancelled = True
        store = AnalysisAttemptStore()
        handler = IRConstructionStageHandler(f2_reader=store, f3_writer=store)

        with pytest.raises(AnalysisCancelledError):
            handler.execute(ctx)

    def test_capacity_limit_exceeded_handling(self) -> None:
        """Verify IRCapacityLimitError produces RESOURCE_LIMIT diagnostic."""
        ctx = _create_test_context()
        f2_result = create_mock_inspection_result(
            analysis_id=ctx.analysis_id,
            project_id=ctx.project_id,
            repository_id=ctx.input.repository_id,
            snapshot_id=ctx.input.snapshot_id,
        )
        store = AnalysisAttemptStore()
        store.set_f2_result(ctx.analysis_id, ctx.job_id, f2_result)

        class _CapExceededService(IRConstructionService):
            def construct(
                self,
                inspection_result: RepositoryInspectionResult,
                expected_schema_version: str = "1.0.0",
                validate: bool = True,
            ) -> IRDocument:
                raise IRCapacityLimitError("Entity limit 150000 exceeded")

        handler = IRConstructionStageHandler(
            f2_reader=store,
            f3_writer=store,
            service=_CapExceededService(),
        )
        result = handler.execute(ctx)

        assert result.status == StageStatus.FAILED
        assert result.error_code == "IR_CAPACITY_EXCEEDED"
        diag = ctx.diagnostics[0]
        assert diag.category == DiagnosticCategory.RESOURCE
        assert diag.code == "IR_CAPACITY_LIMIT_EXCEEDED"

    def test_general_construction_error_handling(self) -> None:
        """Verify IRConstructionError produces ANALYSIS error diagnostic."""
        ctx = _create_test_context()
        f2_result = create_mock_inspection_result(
            analysis_id=ctx.analysis_id,
            project_id=ctx.project_id,
            repository_id=ctx.input.repository_id,
            snapshot_id=ctx.input.snapshot_id,
        )
        store = AnalysisAttemptStore()
        store.set_f2_result(ctx.analysis_id, ctx.job_id, f2_result)

        class _FailingService(IRConstructionService):
            def construct(
                self,
                inspection_result: RepositoryInspectionResult,
                expected_schema_version: str = "1.0.0",
                validate: bool = True,
            ) -> IRDocument:
                raise IRConstructionError("Syntax fact tree corrupted")

        handler = IRConstructionStageHandler(
            f2_reader=store,
            f3_writer=store,
            service=_FailingService(),
        )
        result = handler.execute(ctx)

        assert result.status == StageStatus.FAILED
        assert result.error_code == "IR_CONSTRUCTION_FAILED"
        diag = ctx.diagnostics[0]
        assert diag.category == DiagnosticCategory.ANALYSIS
        assert diag.code == "IR_CONSTRUCTION_ERROR"


class TestAttemptStoreLifecycleAndReplay:
    """Tests attempt isolation, replay idempotency, and resource release."""

    def test_replay_idempotency(self) -> None:
        """Verify handler re-execution with same attempt succeeds idempotently."""
        ctx = _create_test_context()
        artifact_id = ctx.input.artifact_catalog.artifacts[0].id
        decl = create_mock_declaration_fact(name="run")
        sdoc = create_mock_syntax_document(
            path="src/main.py",
            artifact_id=artifact_id,
            declarations=(decl,),
        )
        inv = create_mock_inventory_entry(
            path="src/main.py",
            artifact_id=artifact_id,
            revision_id=ctx.input.snapshot_id,
        )
        f2_result = create_mock_inspection_result(
            analysis_id=ctx.analysis_id,
            project_id=ctx.project_id,
            repository_id=ctx.input.repository_id,
            snapshot_id=ctx.input.snapshot_id,
            inventory=(inv,),
            syntax_documents=(sdoc,),
        )

        store = AnalysisAttemptStore()
        store.set_f2_result(ctx.analysis_id, ctx.job_id, f2_result)
        handler = IRConstructionStageHandler(f2_reader=store, f3_writer=store)

        res1 = handler.execute(ctx)
        doc1 = store.read_f3_result(ctx.analysis_id, ctx.job_id)

        res2 = handler.execute(ctx)
        doc2 = store.read_f3_result(ctx.analysis_id, ctx.job_id)

        assert res1.status == StageStatus.COMPLETED
        assert res2.status == StageStatus.COMPLETED
        assert doc1.ir_schema_version == doc2.ir_schema_version
        assert len(doc1.entities) == len(doc2.entities)

    def test_attempt_isolation(self) -> None:
        """Verify distinct attempts do not leak F2 or F3 stage results."""
        store = AnalysisAttemptStore()
        a1, j1 = uuid4(), uuid4()
        a2, j2 = uuid4(), uuid4()

        f2_1 = create_mock_inspection_result(analysis_id=a1)
        store.set_f2_result(a1, j1, f2_1)

        assert store.read_f2_result(a1, j1) == f2_1
        with pytest.raises(LookupError):
            store.read_f2_result(a2, j2)

        assert not store.has_f3_result(a1, j1)
        assert not store.has_f3_result(a2, j2)

    def test_attempt_release_clears_memory(self) -> None:
        """Verify release() clears attempt F2 and F3 records deterministically."""
        store = AnalysisAttemptStore()
        a, j = uuid4(), uuid4()
        s = uuid4()

        f2 = create_mock_inspection_result(analysis_id=a, snapshot_id=s)
        service = IRConstructionService()
        f3 = service.construct(f2)

        store.set_f2_result(a, j, f2)
        store.write_f3_result(a, j, f3)

        assert store.has_f3_result(a, j)
        store.release(a, j)

        assert not store.has_f3_result(a, j)
        with pytest.raises(LookupError):
            store.read_f2_result(a, j)
        with pytest.raises(LookupError):
            store.read_f3_result(a, j)

    def test_attempt_store_rejects_non_equivalent_f3_replacement(self) -> None:
        store = AnalysisAttemptStore()
        analysis_id, job_id = uuid4(), uuid4()
        original = IRConstructionService().construct(
            create_mock_inspection_result(analysis_id=analysis_id)
        )
        conflicting = replace(original, project_id=uuid4())

        store.write_f3_result(analysis_id, job_id, original)
        with pytest.raises(ValueError, match="immutable F3"):
            store.write_f3_result(analysis_id, job_id, conflicting)

    def test_m1_store_recovers_lost_f2_and_f3_with_same_input(self) -> None:
        """M1-owned recovery rebuilds non-persisted handoffs without M3 ownership."""
        ctx = _create_test_context()
        f2 = create_mock_inspection_result(
            analysis_id=ctx.analysis_id,
            project_id=ctx.project_id,
            repository_id=ctx.input.repository_id,
            snapshot_id=ctx.input.snapshot_id,
            analyzer_version=ctx.input.analyzer_version,
        )

        class _MissingHandoff:
            def require_result(self, analysis_id: UUID, job_id: UUID) -> None:
                raise LookupError("lost")

        class _RecoveryCoordinator:
            handoff = _MissingHandoff()

            def __init__(self) -> None:
                self.rebuilds = 0
                self.releases = 0

            def signature(self, analysis_input: AnalysisInput) -> SimpleNamespace:
                return SimpleNamespace(
                    configuration_fingerprint=f2.configuration_fingerprint
                )

            def rebuild_lost_result(
                self,
                analysis_input: AnalysisInput,
                *,
                job_id: UUID,
                expected_signature: object,
            ) -> SimpleNamespace:
                self.rebuilds += 1
                return SimpleNamespace(result=f2)

            def release_attempt(self, analysis_id: UUID, job_id: UUID) -> None:
                self.releases += 1

        recovery = _RecoveryCoordinator()
        store = AnalysisAttemptStore(
            m2_coordinator=cast(M2ExecutionCoordinator, recovery),
            ir_service=IRConstructionService(),
        )

        recovered = store.read_f3_result(
            ctx.analysis_id,
            ctx.job_id,
            ctx.input,
        )
        assert recovered.analysis_id == ctx.analysis_id
        assert recovery.rebuilds == 1
        assert store.read_f3_result(ctx.analysis_id, ctx.job_id) is recovered

        store.release(ctx.analysis_id, ctx.job_id)
        assert recovery.releases == 1

    def test_configured_ir_capacity_limits_are_wired(self) -> None:
        settings = Settings(ir_max_entities=1)
        service = build_ir_construction_service(settings)

        with pytest.raises(IRCapacityLimitError, match="Entity count"):
            service.construct(create_mock_inspection_result())


class TestM4ConsumerStub:
    """Simulates Phase 3 Module 4 architecture projection consumption."""

    def test_m4_consumer_traversal_of_f3_document(self) -> None:
        """Verify M4 reader can traverse entities, relationships, and evidence."""
        ctx = _create_test_context()
        artifact_id = ctx.input.artifact_catalog.artifacts[0].id
        decl = create_mock_declaration_fact(
            name="UserModel",
            kind=DeclarationKind.CLASS,
        )
        sdoc = create_mock_syntax_document(
            path="src/models.py",
            artifact_id=artifact_id,
            declarations=(decl,),
        )
        inv = create_mock_inventory_entry(
            path="src/models.py",
            artifact_id=artifact_id,
            revision_id=ctx.input.snapshot_id,
        )
        f2 = create_mock_inspection_result(
            analysis_id=ctx.analysis_id,
            project_id=ctx.project_id,
            repository_id=ctx.input.repository_id,
            snapshot_id=ctx.input.snapshot_id,
            inventory=(inv,),
            syntax_documents=(sdoc,),
        )

        store = AnalysisAttemptStore()
        store.set_f2_result(ctx.analysis_id, ctx.job_id, f2)
        handler = IRConstructionStageHandler(f2_reader=store, f3_writer=store)
        handler.execute(ctx)

        # M4 Consumer Stub
        class ArchitectureModelStub:
            def __init__(self, reader: F3ResultReader) -> None:
                self.reader = reader

            def build_components(
                self, analysis_id: UUID, job_id: UUID
            ) -> list[dict[str, Any]]:
                ir_doc = self.reader.read_f3_result(analysis_id, job_id)
                assert ir_doc.ir_schema_version == "1.0.0"

                components = []
                for entity in ir_doc.entities:
                    if entity.kind == IREntityKind.SYMBOL:
                        components.append(
                            {
                                "name": entity.name,
                                "qualified_name": entity.qualified_name,
                                "module_key": entity.module_key,
                                "key": entity.ir_key,
                            }
                        )
                return components

        builder = ArchitectureModelStub(store)
        components = builder.build_components(ctx.analysis_id, ctx.job_id)

        assert len(components) == 1
        assert components[0]["name"] == "UserModel"
        assert components[0]["qualified_name"] == "src/models.py::UserModel"
        assert components[0]["module_key"] == "module::src/models.py"
        assert components[0]["key"].startswith("symbol::src/models.py::UserModel::")
