"""FastAPI dependency injection providers for Analysis lifecycle infrastructure."""

import secrets
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from backend.platform.analysis.application.input_factory import (
    AnalysisInputFactory,
    PlatformAnalysisInputFactory,
)
from backend.platform.analysis.application.lifecycle_service import (
    AnalysisLifecycleService,
)
from backend.platform.analysis.application.orchestrator import (
    AnalysisOrchestrator,
)
from backend.platform.analysis.application.platform_gateway import (
    HttpPlatformRepositoryGateway,
    PlatformRepositoryGateway,
)
from backend.platform.analysis.application.recovery import (
    JobRecoveryService,
)
from backend.platform.analysis.application.registry import (
    StageHandlerRegistry,
)
from backend.platform.analysis.infra.analysis_repository import (
    SqlAlchemyAnalysisRepository,
)
from backend.platform.analysis.infra.diagnostic_repository import (
    SqlAlchemyDiagnosticRepository,
)
from backend.platform.analysis.infra.event_repository import (
    SqlAlchemyEventRepository,
)
from backend.platform.analysis.infra.job_repository import (
    SqlAlchemyJobRepository,
    SqlAlchemyStageRepository,
)
from backend.platform.analysis.infra.queue import (
    AnalysisQueuePublisher,
    CeleryAnalysisQueuePublisher,
)
from backend.platform.analysis.repositories.analysis_repo import AnalysisRepository
from backend.platform.analysis.repositories.diagnostic_repo import (
    DiagnosticRepository,
)
from backend.platform.analysis.repositories.event_repo import EventRepository
from backend.platform.analysis.repositories.job_repo import (
    JobRepository,
    StageRepository,
)
from backend.platform.config import Settings, get_settings
from backend.platform.dependency_injection import get_database_session
from backend.platform.errors import (
    AnalysisAccessDeniedError,
    AnalysisInputError,
    AuthenticationRequiredError,
    InvalidTokenError,
)


@dataclass(frozen=True, slots=True)
class DelegatedRequestContext:
    """Delegated actor context from Express or direct service-to-service call."""

    actor_id: UUID | None
    role: str
    is_service: bool = False
    project_id: UUID | None = None
    correlation_id: str | None = None


# Shared publisher instance
_default_queue_publisher: AnalysisQueuePublisher | None = None


def get_queue_publisher(
    settings: Settings = Depends(get_settings),
) -> AnalysisQueuePublisher:
    """Provide the active queue publisher instance."""
    global _default_queue_publisher
    if _default_queue_publisher is None:
        _default_queue_publisher = CeleryAnalysisQueuePublisher(
            queue_name=settings.analysis_queue_name
        )
    return _default_queue_publisher


def set_queue_publisher(publisher: AnalysisQueuePublisher | None) -> None:
    """Override queue publisher (for test isolation)."""
    global _default_queue_publisher
    _default_queue_publisher = publisher


def get_stage_handler_registry() -> StageHandlerRegistry:
    """Provide the active stage handler registry."""
    from backend.worker.tasks import get_worker_registry

    return get_worker_registry()


def get_platform_repository_gateway(
    settings: Settings = Depends(get_settings),
) -> PlatformRepositoryGateway:
    """Provide the authorized Express platform source adapter."""
    return HttpPlatformRepositoryGateway(
        settings.platform_api_base_url,
        settings.platform_api_secret_key.get_secret_value(),
        settings.platform_api_timeout_seconds,
    )


def get_analysis_input_factory(
    gateway: PlatformRepositoryGateway = Depends(get_platform_repository_gateway),
) -> AnalysisInputFactory:
    """Build immutable input through Express APIs, never MongoDB access."""
    return PlatformAnalysisInputFactory(gateway)


def get_analysis_orchestrator(
    session: Session = Depends(get_database_session),
    input_factory: AnalysisInputFactory | None = Depends(get_analysis_input_factory),
    registry: StageHandlerRegistry | None = Depends(get_stage_handler_registry),
    settings: Settings = Depends(get_settings),
) -> AnalysisOrchestrator:
    """Provide an AnalysisOrchestrator instance."""
    resolved_factory: AnalysisInputFactory
    if isinstance(input_factory, AnalysisInputFactory):
        resolved_factory = input_factory
    else:
        resolved_factory = PlatformAnalysisInputFactory(
            get_platform_repository_gateway(settings)
        )

    resolved_registry: StageHandlerRegistry
    if isinstance(registry, StageHandlerRegistry):
        resolved_registry = registry
    else:
        from backend.worker.tasks import get_worker_registry

        resolved_registry = get_worker_registry()

    return AnalysisOrchestrator(
        analysis_repo=SqlAlchemyAnalysisRepository(session),
        job_repo=SqlAlchemyJobRepository(session),
        stage_repo=SqlAlchemyStageRepository(session),
        event_repo=SqlAlchemyEventRepository(session),
        diagnostic_repo=SqlAlchemyDiagnosticRepository(session),
        input_factory=resolved_factory,
        registry=resolved_registry,
        max_duration_seconds=settings.analysis_max_duration_seconds,
        stage_timeout_seconds=settings.analysis_stage_timeout_seconds,
        max_diagnostics=settings.analysis_max_diagnostics_per_analysis,
        checkpoint=session.commit,
    )


def get_job_recovery_service(
    session: Session = Depends(get_database_session),
    queue_publisher: AnalysisQueuePublisher = Depends(get_queue_publisher),
) -> JobRecoveryService:
    """Provide a JobRecoveryService instance."""
    return JobRecoveryService(
        analysis_repo=SqlAlchemyAnalysisRepository(session),
        job_repo=SqlAlchemyJobRepository(session),
        event_repo=SqlAlchemyEventRepository(session),
        diagnostic_repo=SqlAlchemyDiagnosticRepository(session),
        queue_publisher=queue_publisher,
        checkpoint=session.commit,
    )


def get_delegated_context(
    settings: Settings = Depends(get_settings),
    x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None,
    x_actor_id: Annotated[str | None, Header(alias="X-Actor-Id")] = None,
    x_actor_role: Annotated[str | None, Header(alias="X-Actor-Role")] = None,
    x_project_id: Annotated[str | None, Header(alias="X-Project-Id")] = None,
    x_correlation_id: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
) -> DelegatedRequestContext:
    """Validate the trusted Express-to-Python delegated request boundary."""
    if not x_service_token:
        raise AuthenticationRequiredError(
            "A service credential is required for the internal analysis API."
        )
    expected_secret = settings.internal_api_secret_key.get_secret_value()
    if not secrets.compare_digest(x_service_token, expected_secret):
        raise InvalidTokenError("Internal service credential is invalid.")
    if not x_actor_id or not x_actor_role or not x_project_id:
        raise AnalysisInputError(
            "Delegated actor, role, and project headers are required.",
            details={
                "required_headers": ["X-Actor-Id", "X-Actor-Role", "X-Project-Id"]
            },
        )
    try:
        actor_uuid = UUID(x_actor_id)
        project_uuid = UUID(x_project_id)
    except ValueError as exc:
        raise AnalysisInputError(
            "Delegated actor and project headers must be valid UUIDs."
        ) from exc
    role = x_actor_role.upper()
    if role not in {"OWNER", "ADMIN", "DEVELOPER", "VIEWER"}:
        raise AnalysisAccessDeniedError(
            "Delegated project role is not recognized.", details={"role": x_actor_role}
        )
    return DelegatedRequestContext(
        actor_id=actor_uuid,
        role=role,
        is_service=True,
        project_id=project_uuid,
        correlation_id=x_correlation_id,
    )


def require_operator_role(
    context: DelegatedRequestContext = Depends(get_delegated_context),
) -> DelegatedRequestContext:
    """Enforce that caller has operator role (OWNER, ADMIN, DEVELOPER) for mutations."""
    if context.role not in ("OWNER", "ADMIN", "DEVELOPER"):
        raise AnalysisAccessDeniedError(
            f"Role '{context.role}' does not have permission to perform "
            "this operation.",
            details={"role": context.role},
        )
    return context


def require_delegated_project(
    context: DelegatedRequestContext,
    requested_project_id: UUID,
) -> UUID:
    """Require a request project to match the trusted delegated project scope."""
    if context.project_id != requested_project_id:
        raise AnalysisAccessDeniedError(
            "Requested project does not match delegated project scope.",
            details={"project_id": str(requested_project_id)},
        )
    return requested_project_id


def get_analysis_repository(
    session: Session = Depends(get_database_session),
) -> AnalysisRepository:
    """Provide an AnalysisRepository instance bound to the request database session."""
    return SqlAlchemyAnalysisRepository(session)


def get_job_repository(
    session: Session = Depends(get_database_session),
) -> JobRepository:
    """Provide a JobRepository instance bound to the request database session."""
    return SqlAlchemyJobRepository(session)


def get_stage_repository(
    session: Session = Depends(get_database_session),
) -> StageRepository:
    """Provide a StageRepository instance bound to the request database session."""
    return SqlAlchemyStageRepository(session)


def get_event_repository(
    session: Session = Depends(get_database_session),
) -> EventRepository:
    """Provide an EventRepository instance bound to the request database session."""
    return SqlAlchemyEventRepository(session)


def get_diagnostic_repository(
    session: Session = Depends(get_database_session),
) -> DiagnosticRepository:
    """Provide a DiagnosticRepository instance bound to the request database session."""
    return SqlAlchemyDiagnosticRepository(session)


def get_analysis_lifecycle_service(
    session: Session = Depends(get_database_session),
    source_gateway: PlatformRepositoryGateway = Depends(
        get_platform_repository_gateway
    ),
) -> AnalysisLifecycleService:
    """Provide AnalysisLifecycleService wired with all persistence repositories."""
    analysis_repo = SqlAlchemyAnalysisRepository(session)
    job_repo = SqlAlchemyJobRepository(session)
    stage_repo = SqlAlchemyStageRepository(session)
    event_repo = SqlAlchemyEventRepository(session)
    diagnostic_repo = SqlAlchemyDiagnosticRepository(session)
    return AnalysisLifecycleService(
        analysis_repo=analysis_repo,
        job_repo=job_repo,
        stage_repo=stage_repo,
        event_repo=event_repo,
        diagnostic_repo=diagnostic_repo,
        revision_repo=None,
        project_repo=None,
        repository_repo=None,
        source_gateway=source_gateway,
    )
