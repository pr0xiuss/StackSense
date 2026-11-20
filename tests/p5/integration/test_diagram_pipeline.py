"""Public PG source -> real rootless ELK -> real copy -> actual M1 -> M5.

The explicitly test-only same-UID sealer/rootless runtime do NOT establish
production principal separation/cgroup certification or register a fallback.
"""

# ruff: noqa: F811

import base64
import hashlib
import os
import struct
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import (
    BarrierReceipt,
    DiagramTemplate,
    WorkExecutionContext,
    WorkKind,
)
from backend.platform.delivery.persistence import DeliveryBundleModel
from backend.platform.delivery.publication import PublicationUnitOfWork
from backend.platform.delivery.repository import SqlAlchemyDeliveryRepository
from backend.platform.delivery.source import PublishedVersionReader
from backend.platform.diagrams import artifacts
from backend.platform.diagrams.artifacts import (
    CandidateArtifactWriter,
    LocalGeneratedArtifactStore,
    PrincipalSealer,
)
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.fonts import DiagramFonts
from backend.platform.diagrams.layout import (
    LayoutOutcome,
    LayoutRequest,
    LockedFile,
    create_layout_profile,
    parse_geometry,
)
from backend.platform.diagrams.model import canonical_bytes
from backend.platform.diagrams.persistence import DiagramGenerationModel as Generation
from backend.platform.diagrams.query import canonical_read_source
from backend.platform.diagrams.repository import (
    DatabaseReadAuthority,
    DiagramPublicationPort,
    DiagramRepository,
)
from backend.platform.diagrams.service import DiagramReader, DiagramWorkHandler
from backend.platform.graph.source import SqlAlchemyPublishedArchitectureSource
from tests.p5.diagrams.test_b1_essential_runtime import execute
from tests.p5.diagrams.test_database import diagram_db, publish_canonical  # noqa: F401
from tests.p5.diagrams.test_exports import Control
from tests.p5.diagrams.test_publication import lease_for

pytestmark = pytest.mark.skipif(
    os.environ.get("M4_B1_ESSENTIAL_PROOFS") != "1",
    reason="opt-in actual pinned rootless runtime",
)


class RealRootlessLayout:
    def layout(self, semantic_digest, profile, scene, deadline, control):
        value = LayoutRequest(
            protocol_version=1,
            request_id=uuid4(),
            semantic_digest=semantic_digest,
            profile=profile,
            nodes=scene.nodes,
            edges=scene.edges,
            labels=scene.labels,
        )
        payload = value.to_bytes()
        data, exit_code = execute(
            struct.pack("!I", len(payload)) + payload,
            timeout=min(30, max(0.01, deadline - monotonic())),
            control=control,
        )
        assert exit_code == 0
        return LayoutOutcome(
            parse_geometry(data, value, DiagramLimits()), profile, "none"
        )


@pytest.fixture
def diagram_pipeline(diagram_db, tmp_path, monkeypatch):
    engine, schema, url = diagram_db
    canonical = publish_canonical(engine)
    with Session(engine) as s:
        header = (
            SqlAlchemyPublishedArchitectureSource(s).list_published(limit=1).items[0]
        )
        scope = PublishedVersionReader.scope(header)
    assert scope.architecture_version_id == canonical.architecture_version_id
    for name in ("staging", "sealed", "locks"):
        (tmp_path / name).mkdir(mode=0o700)
    monkeypatch.setattr(artifacts, "STORE_ROOT", tmp_path)

    class Metadata:
        def require_staging(self, request):
            with Session(engine) as s:
                row = s.get(Generation, request.generation_id)
                assert row.state == "STAGING"
                assert row.attempt_snapshot == request.attempt.model_dump(mode="json")
                assert row.manifest_sha256 == request.manifest_sha256

        def require_deleting(self, gid):
            raise PermissionError("no cleanup")

    class ApplicationOnlySealer(PrincipalSealer):
        def __init__(self):
            self.metadata, self.limits = Metadata(), DiagramLimits()

    class ApplicationWriter(CandidateArtifactWriter):
        def seal(self, request, deadline, checkpoint):
            checkpoint()
            return ApplicationOnlySealer().seal(request)

    paths = {
        "node": Path(os.environ["M4_B1_NODE"]),
        "bwrap": Path(os.environ["M4_B1_BWRAP"]),
        "elk_helper": Path("backend/platform/diagrams/layout_runtime/elk_layout.mjs"),
        "elk": Path(
            "backend/platform/diagrams/layout_runtime/node_modules/elkjs/lib/elk.bundled.js"
        ),
    }
    lock = SimpleNamespace(
        files=tuple(
            LockedFile(path=name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            for name, path in sorted(paths.items())
        )
    )
    fonts = DiagramFonts()
    try:
        font_digest = fonts.manifest_digest()
    finally:
        fonts.close()
    repo = DiagramRepository(engine)

    def make_handler(binding):
        template = binding.slot.template
        profile = create_layout_profile(
            {
                DiagramTemplate.OVERVIEW: "architecture_compound_v1",
                DiagramTemplate.COMPONENT: "architecture_compound_v1",
                DiagramTemplate.DEPENDENCY: "dependency_layered_v1",
                DiagramTemplate.DATA_FLOW: "static_flow_v1",
            }[template],
            lock,
            font_digest,
        )
        return DiagramWorkHandler(
            binding=binding,
            repository=repo,
            source=lambda budget: canonical_read_source(
                url, budget, read_schema=schema
            ),
            layout=RealRootlessLayout(),
            profile=profile,
            limits=DiagramLimits(),
            writer=ApplicationWriter(),
        )

    return scope, repo, make_handler


def test_real_four_diagram_handler_publication_and_report_barrier(
    diagram_db, diagram_pipeline
):
    engine, _, _ = diagram_db
    scope, repo, make_handler = diagram_pipeline
    refs = []
    for template in DiagramTemplate:
        lease, _ = lease_for(engine, template, scope)
        handler = make_handler(lease.identity.work.binding)
        context = WorkExecutionContext(
            attempt=lease.identity, deadline=lease.deadline, control=Control()
        )
        output = handler.execute(context)
        assert handler.execute(context) == output  # Exact physical same-attempt replay.
        with PublicationUnitOfWork(
            engine, timeout_seconds=5, lock_timeout_ms=1000
        ) as uow:

            def dependencies(session, receipt, lease=lease):
                def validate(item):
                    uow.enlist(DiagramPublicationPort).validate_ready(
                        item.accepted.reference, uow.context(item.prepared.attempt)
                    )

                SqlAlchemyDeliveryRepository(session).coordinate_dependencies(
                    lease.identity.work.bundle_id, validate, tentative=receipt
                )

            receipt = uow.complete(
                lease, output, DiagramPublicationPort, stage_dependencies=dependencies
            )
            uow.commit()
        refs.append(receipt.accepted.reference)
    with Session(engine) as s:
        bundle = s.get(DeliveryBundleModel, lease.identity.work.bundle_id)
        barrier = BarrierReceipt.model_validate_json(canonical_bytes(bundle.barrier))
    assert {r.accepted.reference for r in barrier.diagrams} == set(refs)
    reader = DiagramReader(
        LocalGeneratedArtifactStore(
            DatabaseReadAuthority(engine, DiagramLimits(), actor_id=None),
            DiagramLimits(),
        ),
        DiagramLimits(),
    )
    # A report consumer fixture uses exactly the M1-accepted four references.
    prepared = [
        reader.read_exact(scope, r.accepted.reference) for r in barrier.diagrams
    ]
    assert {p.spec.template for p in prepared} == set(DiagramTemplate)
    assert all(
        p.spec.scope.architecture_version_id == scope.architecture_version_id
        for p in prepared
    )
    assert any(p.layout.labels and p.layout.glyphs for p in prepared)
    # B4 actual HTTP -> M4 accepted reader -> PG/files, all four exact products.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.api.v1 import diagrams as api
    from backend.platform.analysis.application.dependencies import (
        DelegatedRequestContext,
        get_architecture_query_service,
        get_delegated_context,
    )
    from backend.platform.diagrams.contracts import PreparedDiagram
    from backend.platform.diagrams.cursors import CursorSigner
    from backend.platform.diagrams.repository import DiagramQueryRepository
    from backend.platform.diagrams.service import DiagramService

    actor = uuid4()
    limits = DiagramLimits()
    api_reader = DiagramReader(
        LocalGeneratedArtifactStore(
            DatabaseReadAuthority(engine, limits, actor_id=actor, purpose="api"), limits
        ),
        limits,
    )
    service = DiagramService(
        DiagramQueryRepository(engine),
        api_reader,
        limits,
        CursorSigner("b4-test", "isolated-test-secret-not-production"),
        handler.source,
        lambda base: RealRootlessLayout(),
    )
    with Session(engine) as session:
        record = get_architecture_query_service(session=session).get_version(
            scope.architecture_version_id, scope.project_id
        )
    app = FastAPI()
    app.include_router(api.router, prefix="/api/v1")
    app.dependency_overrides[get_delegated_context] = lambda: DelegatedRequestContext(
        actor, "VIEWER", project_id=scope.project_id
    )
    app.dependency_overrides[api.get_diagram_version_reader] = (
        lambda: lambda version, project, deadline: record
    )
    app.dependency_overrides[api.service_factory] = lambda: lambda: service
    with TestClient(app) as client:
        for value in prepared:
            ref = value.descriptor.reference
            url = (
                f"/api/v1/architecture-versions/{scope.architecture_version_id}"
                f"/diagrams/{value.spec.template.value}/generations/{ref.generation_id}"
            )
            for member in ("spec", "layout"):
                response = client.get(
                    url + "/" + member, params={"project_id": str(scope.project_id)}
                )
                assert response.status_code == 200, response.text
                assert response.content == getattr(value, member).to_bytes()
            for format in ("json", "svg"):
                response = client.get(
                    url + "/export",
                    params={"project_id": str(scope.project_id), "format": format},
                )
                assert response.status_code == 200, response.text
                expected = (
                    "sha-256=:"
                    + base64.b64encode(
                        hashlib.sha256(response.content).digest()
                    ).decode()
                    + ":"
                )
                assert response.headers["content-digest"] == expected
                if format == "json":
                    assert (
                        PreparedDiagram.model_validate_json(response.content) == value
                    )
                else:
                    assert (
                        b"<svg" in response.content
                        and b"<script" not in response.content
                    )
            response = client.get(
                url + "/members",
                params={"project_id": str(scope.project_id), "limit": 1},
            )
            assert response.status_code == 200, response.text
            if response.json()["next_cursor"]:
                second = client.get(
                    url + "/members",
                    params={
                        "project_id": str(scope.project_id),
                        "limit": 1,
                        "cursor": response.json()["next_cursor"],
                    },
                )
                assert second.status_code == 200 and second.json()[
                    "generation_id"
                ] == str(ref.generation_id)


def test_b4_real_query_members_transient_layout_and_no_publication(
    diagram_db, diagram_pipeline
):
    """Real public PG/canonical + accepted store + isolated helper; no fake IO."""
    from backend.platform.analysis.application.dependencies import (
        get_architecture_query_service,
    )
    from backend.platform.delivery.api_contracts import DeliverySummary, WorkSummary
    from backend.platform.diagrams.contracts import DiagramViewRequest
    from backend.platform.diagrams.cursors import CursorSigner
    from backend.platform.diagrams.repository import DiagramQueryRepository
    from backend.platform.diagrams.service import DiagramService

    engine, schema, url = diagram_db
    scope, _, make_handler = diagram_pipeline
    lease, _ = lease_for(engine, DiagramTemplate.OVERVIEW, scope)
    handler = make_handler(lease.identity.work.binding)
    output = handler.execute(
        WorkExecutionContext(
            attempt=lease.identity, deadline=lease.deadline, control=Control()
        )
    )
    with PublicationUnitOfWork(engine, timeout_seconds=5, lock_timeout_ms=1000) as uow:
        receipt = uow.complete(lease, output, DiagramPublicationPort)
        uow.commit()
    ref = receipt.accepted.reference
    limits = DiagramLimits()
    authority = DatabaseReadAuthority(engine, limits, actor_id=uuid4(), purpose="view")
    reader = DiagramReader(LocalGeneratedArtifactStore(authority, limits), limits)
    service = DiagramService(
        DiagramQueryRepository(engine),
        reader,
        limits,
        CursorSigner("b4-test", "isolated-test-secret-not-production"),
        handler.source,
        lambda base: RealRootlessLayout(),
    )
    with Session(engine) as session:
        record = get_architecture_query_service(session=session).get_version(
            scope.architecture_version_id, scope.project_id
        )
    base = service.prepared(record, DiagramTemplate.OVERVIEW, ref.generation_id)
    assert base.spec.nodes
    actor = uuid4()
    first = service.members(
        record, DiagramTemplate.OVERVIEW, ref.generation_id, actor, None, None, 1, None
    )
    assert len(first.items) == 1 and first.next_cursor
    second = service.members(
        record,
        DiagramTemplate.OVERVIEW,
        ref.generation_id,
        actor,
        None,
        None,
        1,
        first.next_cursor,
    )
    assert first.items != second.items
    with pytest.raises(ValueError, match="diagram_cursor_invalid"):
        service.members(
            record,
            DiagramTemplate.OVERVIEW,
            ref.generation_id,
            uuid4(),
            None,
            None,
            1,
            first.next_cursor,
        )
    request = DiagramViewRequest(
        root_ids=(base.spec.nodes[0].entity.id,),
        entity_kinds=(),
        statuses=(),
        relationship_kinds=(),
        include_contains=False,
        depth=1,
        direction="outgoing",
        collapsed_group_ids=(),
        selected_entity_ids=(),
    )
    reply = service.view(record, DiagramTemplate.OVERVIEW, ref.generation_id, request)
    assert reply.base_semantic_digest == base.spec.semantic_digest
    assert reply.spec.view.root_ids[0].id == base.spec.nodes[0].entity.id
    assert reply.layout.nodes
    # Transient views do not create resources, generations or M1 work.
    from sqlalchemy import func, select

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Generation)) == 1

    class Runtime:
        def scope_for_record(self, record):
            return scope

        def summary(self, known, role):
            return DeliverySummary(
                scope=scope,
                eligibility="ELIGIBLE",
                diagrams=(
                    WorkSummary(
                        kind=WorkKind.DIAGRAM,
                        template=DiagramTemplate.OVERVIEW,
                        state="COMPLETED",
                        reference=ref,
                    ),
                ),
            )

    history = service.history(
        record, DiagramTemplate.OVERVIEW, actor, Runtime(), "VIEWER", 50, None
    )
    assert history.items[0].reference == ref and history.next_cursor is None
    # Same exact generation remains readable with dispatch/runtime absent.
    assert (
        service.summary(
            record, DiagramTemplate.OVERVIEW, None, "VIEWER", ref.generation_id
        ).availability
        == "READY"
    )
    assert service.prepared(record, DiagramTemplate.OVERVIEW, ref.generation_id) == base
