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
from backend.platform.analysis.architecture.model import ArchitectureEntityKind
from backend.platform.analysis.architecture.validator import (
    ArchitectureCapacityConfig,
    ArchitectureValidator,
)
from backend.platform.analysis.domain.constants import AnalysisStageName
from backend.platform.analysis.inspection.service import RepositoryInspectionService
from backend.platform.analysis.ir.service import IRConstructionService
from backend.platform.config import Settings
from backend.platform.projects.infra.base import Base
from backend.worker.tasks import build_worker_registry
from tests.p3.analysis.test_m2_integration import _InProcessExecutor, _input
from tests.p3.analysis.test_m4_builder import _document, _evidence


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
