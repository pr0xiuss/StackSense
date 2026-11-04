"""FastAPI dependency injection providers for Analysis lifecycle infrastructure."""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.platform.analysis.application.input_factory import (
    AnalysisInputFactory,
)
from backend.platform.analysis.application.lifecycle_service import (
    AnalysisLifecycleService,
)
from backend.platform.analysis.application.orchestrator import (
    AnalysisOrchestrator,
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
from backend.platform.identity.application.dependencies import (
    get_token_service,
)
from backend.platform.identity.application.token import TokenService
from backend.platform.identity.domain.user import User
from backend.platform.identity.infra.user_repo import SqlAlchemyUserRepository
from backend.platform.ingestion.application.storage import (
    StorageService,
)
from backend.platform.ingestion.infra.artifact_repository import (
    SqlAlchemyArtifactRepository,
)
from backend.platform.ingestion.infra.revision_repository import (
    SqlAlchemyRevisionRepository,
)
from backend.platform.ingestion.infra.storage.local_storage import (
    LocalStorageService,
)
from backend.platform.ingestion.repositories.artifact_repo import ArtifactRepository
from backend.platform.ingestion.repositories.revision_repo import RevisionRepository
from backend.platform.projects.infra.repository import (
    SqlAlchemyProjectRepository,
)
from backend.platform.projects.repositories.project_repo import ProjectRepository
from backend.platform.repositories.infra.repository import (
    SqlAlchemyRepositoryRepository,
)
from backend.platform.repositories.repositories.repository_repo import (
    RepositoryRepository,
)

_http_bearer = HTTPBearer(auto_error=False)


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
    session: Session = Depends(get_database_session),
    token_service: TokenService = Depends(get_token_service),
) -> User | None:
    """Resolve current user if valid Bearer token is provided, else None."""
    if credentials is None or not credentials.credentials:
        return None
    try:
        payload = token_service.verify_token(credentials.credentials)
        user_repo = SqlAlchemyUserRepository(session)
        user = user_repo.get_by_id(payload.user_id)
        if user and user.is_active:
            return user
    except Exception:
        pass
    return None


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


def get_artifact_repository(
    session: Session = Depends(get_database_session),
) -> ArtifactRepository:
    """Provide an ArtifactRepository instance."""
    return SqlAlchemyArtifactRepository(session)


def get_storage_service(
    settings: Settings = Depends(get_settings),
) -> StorageService:
    """Provide a StorageService instance."""
    return LocalStorageService(settings.storage_root)


def get_analysis_input_factory(
    session: Session = Depends(get_database_session),
    storage_service: StorageService = Depends(get_storage_service),
) -> AnalysisInputFactory:
    """Provide an AnalysisInputFactory instance."""
    return AnalysisInputFactory(
        revision_repo=SqlAlchemyRevisionRepository(session),
        artifact_repo=SqlAlchemyArtifactRepository(session),
        storage_service=storage_service,
        repository_repo=SqlAlchemyRepositoryRepository(session),
    )


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
        storage_service = LocalStorageService(settings.storage_root)
        resolved_factory = AnalysisInputFactory(
            revision_repo=SqlAlchemyRevisionRepository(session),
            artifact_repo=SqlAlchemyArtifactRepository(session),
            storage_service=storage_service,
            repository_repo=SqlAlchemyRepositoryRepository(session),
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
    )


def get_delegated_context(
    settings: Settings = Depends(get_settings),
    current_user: User | None = Depends(get_current_user_optional),
    x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None,
    x_actor_id: Annotated[str | None, Header(alias="X-Actor-Id")] = None,
    x_actor_role: Annotated[str | None, Header(alias="X-Actor-Role")] = None,
    x_project_id: Annotated[str | None, Header(alias="X-Project-Id")] = None,
    x_correlation_id: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
) -> DelegatedRequestContext:
    """Extract and validate delegated request context from headers or auth."""
    # 1. Check Service Authentication header
    is_service = False
    expected_secret = settings.internal_api_secret_key.get_secret_value()
    if x_service_token and x_service_token == expected_secret:
        is_service = True

    actor_uuid: UUID | None = None
    if x_actor_id:
        try:
            actor_uuid = UUID(x_actor_id)
        except ValueError:
            pass

    project_uuid: UUID | None = None
    if x_project_id:
        try:
            project_uuid = UUID(x_project_id)
        except ValueError:
            pass

    # 2. Determine Role
    role = x_actor_role.upper() if x_actor_role else None
    if is_service:
        return DelegatedRequestContext(
            actor_id=actor_uuid,
            role=role or "ADMIN",
            is_service=True,
            project_id=project_uuid,
            correlation_id=x_correlation_id,
        )

    # 3. Direct User Token fallback
    if current_user:
        return DelegatedRequestContext(
            actor_id=current_user.id,
            role=role or "DEVELOPER",
            is_service=False,
            project_id=project_uuid,
            correlation_id=x_correlation_id,
        )

    # 4. Denied if neither service token nor user token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=(
            "Authentication required: valid service token or user credential "
            "must be provided."
        ),
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_operator_role(
    context: DelegatedRequestContext = Depends(get_delegated_context),
) -> DelegatedRequestContext:
    """Enforce that caller has operator role (OWNER, ADMIN, DEVELOPER) for mutations."""
    if context.role not in ("OWNER", "ADMIN", "DEVELOPER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Role '{context.role}' does not have permission to perform "
                "this operation."
            ),
        )
    return context


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
) -> AnalysisLifecycleService:
    """Provide AnalysisLifecycleService wired with all persistence repositories."""
    analysis_repo = SqlAlchemyAnalysisRepository(session)
    job_repo = SqlAlchemyJobRepository(session)
    stage_repo = SqlAlchemyStageRepository(session)
    event_repo = SqlAlchemyEventRepository(session)
    diagnostic_repo = SqlAlchemyDiagnosticRepository(session)
    revision_repo: RevisionRepository = SqlAlchemyRevisionRepository(session)
    project_repo: ProjectRepository = SqlAlchemyProjectRepository(session)
    repository_repo: RepositoryRepository = SqlAlchemyRepositoryRepository(session)

    return AnalysisLifecycleService(
        analysis_repo=analysis_repo,
        job_repo=job_repo,
        stage_repo=stage_repo,
        event_repo=event_repo,
        diagnostic_repo=diagnostic_repo,
        revision_repo=revision_repo,
        project_repo=project_repo,
        repository_repo=repository_repo,
    )
