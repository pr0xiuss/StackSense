"""Test fixtures and helpers for P5 M5 Architecture Analysis Report."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from backend.platform.delivery.contracts import (
    AcceptedOutput,
    ArtifactReference,
    AttemptIdentity,
    BarrierReceipt,
    CandidateSeal,
    DiagramTemplate,
    HandlerProfile,
    OutputDigests,
    PreparedOutput,
    ProducerProfile,
    PublicationReceipt,
    VersionScope,
    WorkExecutionContext,
    WorkIdentity,
    WorkKind,
    WorkSlot,
    execution_control,
)
from backend.platform.diagrams.contracts import (
    DiagramArtifactDescriptor,
    DiagramArtifactManifest,
    MemberDescriptor,
    PreparedDiagram,
)
from tests.p5.diagrams.conftest import empty_parts


def sample_scope() -> VersionScope:
    return VersionScope(
        project_id=UUID("00000000-0000-0000-0000-000000000001"),
        repository_id=UUID("00000000-0000-0000-0000-000000000002"),
        analysis_id=UUID("00000000-0000-0000-0000-000000000003"),
        snapshot_id=UUID("00000000-0000-0000-0000-000000000004"),
        architecture_version_id=UUID("00000000-0000-0000-0000-000000000005"),
        sequence_number=1,
        published_at=datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC),
        canonical_digest="a" * 64,
        source_contract_version="1.0.0",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        configuration_fingerprint="source-config-fingerprint",
    )


def sample_handler_profile(
    kind: WorkKind = WorkKind.REPORT,
    template: DiagramTemplate | str | None = "architecture_analysis",
) -> HandlerProfile:
    return HandlerProfile(
        slot=WorkSlot(kind=kind, template=template),  # type: ignore[arg-type]
        profile=ProducerProfile(
            producer_id=(
                "stacksense.reports"
                if kind == WorkKind.REPORT
                else "stacksense.diagrams"
            ),
            producer_version="1.0.0",
            generator_version="1.0.0",
            output_schema_version="1.0.0",
            configuration_fingerprint="c" * 64,
        ),
    )


def sample_prepared_diagram(
    template: DiagramTemplate,
    scope: VersionScope | None = None,
    bundle_id: UUID | None = None,
    *,
    detailed: bool = False,
) -> tuple[PreparedDiagram, PublicationReceipt]:
    scope = scope or sample_scope()
    bundle_id = bundle_id or UUID("00000000-0000-0000-0000-000000000099")
    spec, catalog, layout = empty_parts(template)
    if detailed:
        from time import monotonic

        from backend.platform.diagrams.configuration import DiagramLimits
        from backend.platform.diagrams.export import prepare_layout
        from backend.platform.diagrams.fonts import DiagramFonts
        from tests.p5.diagrams.test_builders import build, monorepo
        from tests.p5.diagrams.test_exports import Control, UnitLayout

        built = build(monorepo(), template)
        fonts = DiagramFonts()
        try:
            layout = prepare_layout(
                built,
                fonts,
                UnitLayout(),
                layout.profile,
                DiagramLimits(),
                monotonic() + 30,
                Control(),
            )
        finally:
            fonts.close()
        spec, catalog = built.spec, built.catalog

    binding = sample_handler_profile(WorkKind.DIAGRAM, template)
    work = WorkIdentity(
        scope=scope,
        bundle_id=bundle_id,
        work_id=uuid4(),
        run_number=1,
        binding=binding,
        bundle_fingerprint="f" * 64,
        input_fingerprint="d" * 64,
    )
    attempt = AttemptIdentity(
        work=work,
        attempt_id=uuid4(),
        ordinal=1,
        fence=1,
        dispatch_epoch=uuid4(),
        candidate_id=uuid4(),
    )
    gen_id = uuid4()
    art_id = uuid4()

    data = {
        "spec": spec.to_bytes(),
        "layout": layout.to_bytes(),
        "members": catalog.to_bytes(),
        "svg": b"<svg/>",
    }
    members = tuple(
        MemberDescriptor(
            member=name,  # type: ignore[arg-type]
            file_name=name + ".json" if name != "svg" else "scene.svg",
            media_type="application/json" if name != "svg" else "image/svg+xml",
            schema_version="1.0.0",
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )
        for name, content in sorted(data.items())
    )
    manifest = DiagramArtifactManifest(
        artifact_schema_version="1.0.0",
        scope=scope,
        binding=binding,
        input_fingerprint=work.input_fingerprint,
        diagram_id=spec.diagram_id,
        generation_id=gen_id,
        artifact_id=art_id,
        semantic_digest=spec.semantic_digest,
        layout_digest=layout.layout_digest,
        membership_digest=spec.membership_digest,
        export_profile="svg_paths_v1",
        members=members,
        verification_version="1.0.0",
    )
    digests = OutputDigests(
        content=hashlib.sha256(manifest.to_bytes()).hexdigest(),
        spec=spec.semantic_digest,
        layout=layout.layout_digest,
    )
    reference = ArtifactReference(
        scope=scope,
        binding=binding,
        input_fingerprint=work.input_fingerprint,
        resource_id=uuid4(),
        candidate_id=attempt.candidate_id,
        generation_id=gen_id,
        artifact_id=art_id,
        size_bytes=len(manifest.to_bytes()),
        sealed=True,
        digests=digests,
    )
    descriptor = DiagramArtifactDescriptor(
        reference=reference,
        manifest=manifest,
    )
    prepared_diag = PreparedDiagram(
        spec=spec,
        layout=layout,
        descriptor=descriptor,
    )
    prep_out = PreparedOutput(
        attempt=attempt,
        candidate=CandidateSeal(
            generation_id=gen_id,
            artifact_id=art_id,
            size_bytes=len(manifest.to_bytes()),
            digests=digests,
            sealed=True,
        ),
    )
    receipt = PublicationReceipt(
        receipt_id=uuid4(),
        prepared=prep_out,
        accepted=AcceptedOutput(reference=reference),
    )
    return prepared_diag, receipt


def sample_barrier_receipt(
    scope: VersionScope | None = None,
    *,
    detailed: bool = False,
) -> tuple[BarrierReceipt, dict[DiagramTemplate, PreparedDiagram]]:
    scope = scope or sample_scope()
    bundle_id = uuid4()
    receipts: list[PublicationReceipt] = []
    diagrams: dict[DiagramTemplate, PreparedDiagram] = {}

    for tpl in (
        DiagramTemplate.OVERVIEW,
        DiagramTemplate.COMPONENT,
        DiagramTemplate.DEPENDENCY,
        DiagramTemplate.DATA_FLOW,
    ):
        p_diag, p_receipt = sample_prepared_diagram(
            tpl, scope, bundle_id, detailed=detailed
        )
        receipts.append(p_receipt)
        diagrams[tpl] = p_diag

    report_profile = ProducerProfile(
        producer_id="stacksense.reports",
        producer_version="1.0.0",
        generator_version="1.0.0",
        output_schema_version="1.0.0",
        configuration_fingerprint="c" * 64,
    )
    barrier = BarrierReceipt(
        scope=scope,
        report_profile=report_profile,
        diagrams=tuple(receipts),
    )
    return barrier, diagrams


def sample_work_context(
    scope: VersionScope | None = None,
    *,
    detailed: bool = False,
) -> tuple[WorkExecutionContext, dict[DiagramTemplate, PreparedDiagram]]:
    scope = scope or sample_scope()
    barrier, diagrams = sample_barrier_receipt(scope, detailed=detailed)
    binding = sample_handler_profile(WorkKind.REPORT, "architecture_analysis")
    bundle_id = barrier.diagrams[0].prepared.attempt.work.bundle_id
    bundle_fingerprint = barrier.diagrams[0].prepared.attempt.work.bundle_fingerprint

    work = WorkIdentity(
        scope=scope,
        bundle_id=bundle_id,
        work_id=uuid4(),
        run_number=1,
        binding=binding,
        bundle_fingerprint=bundle_fingerprint,
        input_fingerprint=barrier.input_fingerprint(),
    )
    attempt = AttemptIdentity(
        work=work,
        attempt_id=uuid4(),
        ordinal=1,
        fence=1,
        dispatch_epoch=uuid4(),
        candidate_id=uuid4(),
    )
    ctrl = execution_control(lambda: None)
    context = WorkExecutionContext(
        attempt=attempt,
        deadline=datetime.now(UTC) + timedelta(hours=1),
        control=ctrl,
        prerequisites=barrier,
    )
    return context, diagrams


class FakeDiagramReader:
    def __init__(self, diagrams: dict[DiagramTemplate, PreparedDiagram]) -> None:
        self.diagrams = diagrams

    def read_exact(
        self, scope: VersionScope, reference: ArtifactReference
    ) -> PreparedDiagram:
        tpl = reference.binding.slot.template
        if tpl in self.diagrams:
            return self.diagrams[tpl]  # type: ignore[index]
        raise ValueError("diagram_not_found")


class FakeArchitectureQueryService:
    def __init__(self) -> None:
        pass

    def get_version(self, version_id: UUID, project_id: UUID) -> Any:
        class FakeVersion:
            id = version_id
            state = "published"
            analysis_id = sample_scope().analysis_id

        return FakeVersion()

    def list_entities(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> Any:
        class Entity:
            def __init__(self, i: int) -> None:
                self.id = uuid4()
                self.logical_id = f"entity_{i}"
                self.kind = "service" if i % 2 == 0 else "endpoint"
                self.status = "confirmed"

        class Collection:
            items = [Entity(i) for i in range(offset, min(10, offset + limit))]
            total = 10

        return Collection()

    def list_relationships(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> Any:
        class Rel:
            def __init__(self, i: int) -> None:
                self.id = uuid4()
                self.logical_id = f"rel_{i}"
                self.kind = "calls"

        class Collection:
            items = [Rel(i) for i in range(offset, min(5, offset + limit))]
            total = 5

        return Collection()

    def list_evidence(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> Any:
        class Collection:
            items = [object() for _ in range(offset, min(12, offset + limit))]
            total = 12

        return Collection()

    def list_unresolved(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> Any:
        class Collection:
            items = [object() for _ in range(offset, min(1, offset + limit))]
            total = 1

        return Collection()

    def list_conflicts(
        self, version_id: UUID, project_id: UUID, *, limit: int, offset: int
    ) -> Any:
        class Collection:
            items = []
            total = 0

        return Collection()


class FakeAnalysisLifecycleService:
    def __init__(self) -> None:
        pass

    def get_analysis(self, analysis_id: UUID, project_id: UUID) -> Any:
        class FakeAnalysis:
            id = analysis_id
            status = "completed"
            coverage = None

        return FakeAnalysis()

    def list_diagnostics(
        self, analysis_id: UUID, project_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> Any:
        class Diag:
            def __init__(self, i: int) -> None:
                self.id = uuid4()
                self.code = f"WARN_{i}"
                self.category = "security"
                self.severity = "warning" if i % 2 == 0 else "info"
                self.scope = "file"
                self.stage = "analysis"
                self.message = f"Sample warning diagnostic #{i}"
                self.artifact_path = f"src/module_{i}.py"
                self.source_line = 42
                self.source_column = 1
                self.created_at = datetime(2026, 11, 20, 12, 5, 0, tzinfo=UTC)
                self.retryability = "non_retryable"
                self.withheld_reason = None

        class ListRes:
            items = [Diag(i) for i in range(6)]
            total = 6

        return ListRes()
