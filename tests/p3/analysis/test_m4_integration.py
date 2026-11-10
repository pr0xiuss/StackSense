"""M4 Batch 4 handoff and production-composition integration tests."""

from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.platform.analysis.application.handoff import AnalysisAttemptStore
from backend.platform.analysis.architecture.builder import ArchitectureBuilder
from backend.platform.analysis.architecture.handlers import (
    ArchitectureBuildStageHandler,
    IdentityResolutionStageHandler,
)
from backend.platform.analysis.architecture.identity import IdentityResolutionService
from backend.platform.analysis.architecture.model import (
    ArchitectureEntityKind,
    ArchitectureRelationshipKind,
)
from backend.platform.analysis.architecture.validator import (
    ArchitectureCapacityConfig,
    ArchitectureValidator,
)
from backend.platform.analysis.domain.analysis import AnalysisConfiguration
from backend.platform.analysis.domain.constants import AnalysisStageName
from backend.platform.analysis.domain.input import (
    AnalysisArtifact,
    AnalysisInput,
    ArtifactCatalog,
)
from backend.platform.analysis.inspection.service import RepositoryInspectionService
from backend.platform.analysis.ir.service import IRConstructionService
from backend.platform.config import Settings
from backend.platform.ingestion.domain.constants import ArtifactCategory, SupportLevel
from backend.platform.projects.infra.base import Base
from backend.worker.tasks import build_worker_registry
from tests.p3.analysis.test_m2_integration import (
    _InProcessExecutor,
    _input,
    _MemoryReader,
)
from tests.p3.analysis.test_m4_builder import _document, _evidence


def _multi_application_input() -> AnalysisInput:
    sources = (
        (
            "backend/django/requirements.txt",
            b"Django==5.0\n",
            ArtifactCategory.CONFIGURATION,
            SupportLevel.PARTIAL,
        ),
        (
            "backend/django/manage.py",
            b"import django\n\ndef main():\n    django.setup()\n",
            ArtifactCategory.SOURCE_CODE,
            SupportLevel.FULL,
        ),
        (
            "backend/express/package.json",
            (
                b'{"dependencies":{"express":"^5.0.0",'
                b'"@elastic/elasticsearch":"^9.0.0"}}'
            ),
            ArtifactCategory.CONFIGURATION,
            SupportLevel.PARTIAL,
        ),
        (
            "backend/express/src/app.js",
            (
                b'import express from "express";\n'
                b'import { Client } from "@elastic/elasticsearch";\n'
                b'import docsRoutes from "./routes/docs.routes.js";\n'
                b'import searchRoutes from "./routes/search.routes.js";\n'
                b"const app = express();\n"
                b"const search = new Client();\n"
                b'app.get("/documents", listDocuments);\n'
                b'app.use("/api/documents", docsRoutes);\n'
                b'app.use("/api/search", searchRoutes);\n'
            ),
            ArtifactCategory.SOURCE_CODE,
            SupportLevel.FULL,
        ),
        (
            "backend/express/src/routes/docs.routes.js",
            (
                b'import express from "express";\n'
                b"const router = express.Router();\n"
                b'router.get("/", listDocuments);\n'
                b"export default router;\n"
            ),
            ArtifactCategory.SOURCE_CODE,
            SupportLevel.FULL,
        ),
        (
            "backend/express/src/routes/search.routes.js",
            (
                b'import express from "express";\n'
                b"const router = express.Router();\n"
                b'router.get("/", searchDocuments);\n'
                b"export default router;\n"
            ),
            ArtifactCategory.SOURCE_CODE,
            SupportLevel.FULL,
        ),
        (
            "frontend/package.json",
            b'{"dependencies":{"react":"^19.0.0"}}',
            ArtifactCategory.CONFIGURATION,
            SupportLevel.PARTIAL,
        ),
        (
            "frontend/src/App.jsx",
            (
                b'import React from "react";\n'
                b'import Dashboard from "./Dashboard";\n'
                b'import authFetch from "./authFetch";\n'
                b'import Missing from "./Missing.jsx";\n'
                b"export default function App() {\n"
                b"  authFetch();\n"
                b"  return <Dashboard />;\n"
                b"}\n"
            ),
            ArtifactCategory.SOURCE_CODE,
            SupportLevel.FULL,
        ),
        (
            "frontend/src/authFetch.js",
            b"export default function authFetch() { return fetch('/api'); }\n",
            ArtifactCategory.SOURCE_CODE,
            SupportLevel.FULL,
        ),
        (
            "frontend/src/Dashboard.jsx",
            (
                b'import React from "react";\n'
                b"export default function Dashboard() { return <main />; }\n"
            ),
            ArtifactCategory.SOURCE_CODE,
            SupportLevel.FULL,
        ),
    )
    revision_id = uuid4()
    artifacts: list[AnalysisArtifact] = []
    content = {}
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
        revision_identifier="multi-app",
        source_hash="sha256:multi-app",
        total_files=len(artifacts),
        total_bytes=sum(item.size_bytes for item in artifacts),
        effective_configuration=AnalysisConfiguration(),
        artifact_catalog=ArtifactCatalog(tuple(artifacts)),
        content_reader=_MemoryReader(content),
    )


def test_attempt_store_preserves_immutable_resolved_handoff() -> None:
    source = _document(entities=(), evidence=(_evidence("framework"),))
    store = AnalysisAttemptStore(identity_service=IdentityResolutionService())
    resolved = IdentityResolutionService().resolve(source)

    store.write_resolved_architecture_result(
        source.analysis_id, source.analysis_id, resolved
    )
    assert (
        store.read_resolved_architecture_result(
            source.analysis_id, source.analysis_id, analysis_input=None
        )
        == resolved
    )
    store.release(source.analysis_id, source.analysis_id)


def test_session_bound_worker_registry_registers_real_m4_handlers() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        registry, _ = build_worker_registry(session, Settings())

        identity = registry.get(AnalysisStageName.IDENTITY_RESOLUTION.value)
        build = registry.get(AnalysisStageName.ARCHITECTURE_BUILD.value)
        assert isinstance(identity, IdentityResolutionStageHandler)
        assert isinstance(build, ArchitectureBuildStageHandler)
        assert build.requires_published_architecture is True
    engine.dispose()


def test_real_fastapi_route_promotes_to_architecture_endpoint() -> None:
    analysis_input = _input()
    inspected = RepositoryInspectionService(  # type: ignore[arg-type]
        parser_executor=_InProcessExecutor()
    ).inspect(
        analysis_input,
        configuration_fingerprint="f" * 64,
    )
    ir_document = IRConstructionService().construct(inspected.result)

    architecture = (
        ArchitectureBuilder(ArchitectureValidator(ArchitectureCapacityConfig()))
        .build(ir_document, uuid4())
        .document
    )

    endpoint = next(
        entity
        for entity in architecture.entities
        if entity.kind is ArchitectureEntityKind.ENDPOINT
    )
    assert endpoint.name == "GET /secret"
    assert endpoint.metadata["method"] == "GET"
    assert endpoint.metadata["path"] == "/secret"


def test_multi_application_pipeline_preserves_architecture_structure() -> None:
    analysis_input = _multi_application_input()
    inspected = RepositoryInspectionService(  # type: ignore[arg-type]
        parser_executor=_InProcessExecutor()
    ).inspect(
        analysis_input,
        configuration_fingerprint="f" * 64,
    )
    ir_document = IRConstructionService().construct(inspected.result)

    architecture = (
        ArchitectureBuilder(ArchitectureValidator(ArchitectureCapacityConfig()))
        .build(ir_document, uuid4())
        .document
    )

    applications = {
        entity.name: entity
        for entity in architecture.entities
        if entity.kind
        in {
            ArchitectureEntityKind.APPLICATION,
            ArchitectureEntityKind.FRONTEND_APPLICATION,
        }
    }
    assert applications.keys() >= {
        "django application",
        "express application",
        "react application",
    }
    assert any(
        entity.kind is ArchitectureEntityKind.MODULE and entity.name == "app.js"
        for entity in architecture.entities
    )
    assert any(
        entity.kind is ArchitectureEntityKind.COMPONENT and entity.name == "App"
        for entity in architecture.entities
    )
    assert any(
        entity.kind is ArchitectureEntityKind.ENDPOINT
        and entity.metadata.get("path") == "/documents"
        for entity in architecture.entities
    )
    assert {
        entity.metadata.get("path")
        for entity in architecture.entities
        if entity.kind is ArchitectureEntityKind.ENDPOINT
    } >= {"/api/documents/", "/api/search/"}
    assert any(
        entity.kind is ArchitectureEntityKind.DATABASE
        and entity.name == "Elasticsearch"
        for entity in architecture.entities
    )
    assert architecture.relationships
    assert {relationship.kind for relationship in architecture.relationships} >= {
        ArchitectureRelationshipKind.CALLS,
        ArchitectureRelationshipKind.CONTAINS,
        ArchitectureRelationshipKind.EXPOSES,
        ArchitectureRelationshipKind.IMPORTS,
    }
    assert {
        unresolved.target_descriptor
        for unresolved in architecture.unresolved_relationships
    } == {"./Missing.jsx"}
    assert architecture.conflicts == ()
    assert len(architecture.evidence) > len(applications)
    assert architecture.completeness.source_entities > len(applications)
    assert architecture.completeness.architecture_entities > len(applications)
