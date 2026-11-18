"""Dependency injection factories and registration helpers for P5-M2 search services."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.platform.analysis.application.dependencies import (
    get_architecture_query_service,
)
from backend.platform.analysis.architecture.model import ArchitectureDocument
from backend.platform.analysis.architecture.service import ArchitectureQueryService
from backend.platform.delivery.contracts import (
    HandlerProfile,
    PreparedOutput,
    VersionScope,
    WorkExecutionContext,
    WorkKind,
)
from backend.platform.delivery.dependencies import get_delivery_reader
from backend.platform.delivery.publication import (
    GuardedEnlistedSession,
    ProducerPublicationFactory,
    ProducerPublicationPort,
)
from backend.platform.delivery.registry import HandlerRegistration
from backend.platform.delivery.source import PublishedVersionReader
from backend.platform.dependency_injection import get_database_session
from backend.platform.knowledge.contracts import SearchBackendUnavailableError
from backend.platform.knowledge.elasticsearch import SearchIndexBackend
from backend.platform.knowledge.reader import SearchReader
from backend.platform.knowledge.rebuild import SearchRebuildService
from backend.platform.knowledge.repository import (
    SearchPublicationPort,
    SqlAlchemySearchRepository,
)
from backend.platform.knowledge.service import (
    SearchCleanupService,
    SearchStatusService,
    SearchWorkHandler,
)

_DEFAULT_SEARCH_BACKEND: SearchIndexBackend | None = None


def get_search_backend() -> SearchIndexBackend:
    """Resolve SearchIndexBackend instance."""
    global _DEFAULT_SEARCH_BACKEND
    if _DEFAULT_SEARCH_BACKEND is None:
        from backend.platform.config import get_settings
        from backend.platform.knowledge.configuration import configured_backend

        config = get_settings().search_deployment_json
        if config is None:
            raise SearchBackendUnavailableError(
                "Search deployment has not been configured"
            )
        return configured_backend(config.get_secret_value())
    return _DEFAULT_SEARCH_BACKEND


def set_search_backend(backend: SearchIndexBackend | None) -> None:
    """Override SearchIndexBackend instance for testing or runtime binding."""
    global _DEFAULT_SEARCH_BACKEND
    _DEFAULT_SEARCH_BACKEND = backend


def get_search_repository(
    session: Annotated[Session, Depends(get_database_session)],
) -> SqlAlchemySearchRepository:
    """FastAPI dependency for SqlAlchemySearchRepository."""
    return SqlAlchemySearchRepository(session)


def get_search_reader(
    backend: Annotated[SearchIndexBackend, Depends(get_search_backend)],
    repository: Annotated[SqlAlchemySearchRepository, Depends(get_search_repository)],
) -> SearchReader:
    """FastAPI dependency for SearchReader."""
    from backend.platform.config import get_settings

    secret = getattr(get_settings(), "search_cursor_secret", None)
    if secret is None:
        raise SearchBackendUnavailableError("Search cursor signing is not configured")
    from backend.platform.knowledge.configuration import parse_deployment

    raw = get_settings().search_deployment_json
    if raw is None:
        raise SearchBackendUnavailableError("Search deployment has not been configured")
    deployment = parse_deployment(raw.get_secret_value())
    return SearchReader(
        backend=backend,
        repository=repository,
        cursor_secret=secret.get_secret_value(),
        cursor_ttl_seconds=deployment.pit_seconds,
    )


def get_search_status_service(
    repository: Annotated[SqlAlchemySearchRepository, Depends(get_search_repository)],
    versions: Annotated[
        ArchitectureQueryService, Depends(get_architecture_query_service)
    ],
    source: Annotated[PublishedVersionReader, Depends(get_delivery_reader)],
) -> SearchStatusService:
    """FastAPI dependency for SearchStatusService."""
    from backend.platform.config import get_settings
    from backend.platform.delivery_composition import get_output_delivery_coordinator
    from backend.platform.knowledge.configuration import parse_deployment

    runtime = get_output_delivery_coordinator()
    raw = get_settings().search_deployment_json
    deployment = parse_deployment(raw.get_secret_value()) if raw else None

    def current_version(scope: VersionScope) -> bool | None:
        if deployment is None:
            return None
        cursor = None
        seen = False
        for _ in range(deployment.status_max_pages):
            page = source.list_published(
                limit=deployment.status_page_size, cursor=cursor
            )
            for header in page.items:
                if (
                    header.project_id == scope.project_id
                    and header.repository_id == scope.repository_id
                ):
                    if header.sequence_number > scope.sequence_number:
                        return False
                    seen |= (
                        header.architecture_version_id == scope.architecture_version_id
                    )
                elif seen and (header.project_id, header.repository_id) > (
                    scope.project_id,
                    scope.repository_id,
                ):
                    return True
            if page.next_cursor is None:
                return True if seen else None
            cursor = page.next_cursor
        return None  # A bounded incomplete observation is never CURRENT.

    try:
        backend = get_search_backend()
    except SearchBackendUnavailableError:
        backend = None
    return SearchStatusService(
        repository=repository,
        backend=backend,
        scope_reader=lambda p, v: source.inspect_requested(
            versions.get_version(v, p)
        ).scope,
        current_version_reader=current_version,
        work_reader=(
            (lambda scope: runtime.summary(scope, "VIEWER").search) if runtime else None
        ),
    )


def get_search_cleanup_service(
    backend: Annotated[SearchIndexBackend, Depends(get_search_backend)],
    repository: Annotated[SqlAlchemySearchRepository, Depends(get_search_repository)],
    session: Annotated[Session, Depends(get_database_session)],
) -> SearchCleanupService:
    """FastAPI dependency for SearchCleanupService."""
    from backend.platform.config import get_settings
    from backend.platform.delivery.dependencies import build_attempt_retirement_reader
    from backend.platform.delivery.service import RuntimeBudgets
    from backend.platform.dependency_injection import get_database_engine

    raw = get_settings().delivery_runtime_json
    retirement = (
        build_attempt_retirement_reader(
            get_database_engine(), RuntimeBudgets.model_validate_json(raw)
        )
        if raw
        else None
    )
    return SearchCleanupService(
        repository=repository,
        backend=backend,
        session=session,
        retirement_reader=retirement,
    )


def create_search_publication_factory(
    backend: SearchIndexBackend | None = None,
) -> ProducerPublicationFactory:
    """Create a publication factory accepting GuardedEnlistedSession from M1."""

    def _factory(session: GuardedEnlistedSession) -> ProducerPublicationPort:
        return SearchPublicationPort(
            session, backend=backend if backend is not None else get_search_backend()
        )

    return _factory


def get_search_rebuild_service(
    repository: Annotated[SqlAlchemySearchRepository, Depends(get_search_repository)],
) -> SearchRebuildService:
    from backend.platform.config import get_settings
    from backend.platform.delivery.reprojection import (
        SearchReprojectionPolicy,
        SearchReprojectionService,
    )
    from backend.platform.delivery_composition import get_output_delivery_coordinator

    runtime = get_output_delivery_coordinator()
    if runtime is None:
        raise SearchBackendUnavailableError("Delivery runtime is unavailable")
    raw = get_settings().delivery_search_reprojection_json
    policy = SearchReprojectionPolicy.model_validate_json(raw) if raw else None
    return SearchRebuildService(repository, SearchReprojectionService(runtime, policy))


def create_search_handler_registration(
    *,
    binding: HandlerProfile,
    backend: SearchIndexBackend,
    session: Session,
    document_loader: Callable[[VersionScope], ArchitectureDocument],
) -> HandlerRegistration:
    """Build M1 HandlerRegistration binding SearchWorkHandler and publication port."""
    repo = SqlAlchemySearchRepository(session)
    handler = SearchWorkHandler(
        backend=backend,
        repository=repo,
        document_loader=document_loader,
    )
    publication_factory = create_search_publication_factory(backend)
    return HandlerRegistration(
        binding=binding,
        handler=handler,
        publication_factory=publication_factory,
    )


def configured_search_registrations() -> tuple[HandlerRegistration, ...]:
    """Composition-only extension; each acquired execution gets a NEW Session."""
    from backend.platform.config import get_settings
    from backend.platform.dependency_injection import get_database_engine
    from backend.platform.graph.source import SqlAlchemyPublishedArchitectureSource
    from backend.platform.knowledge.configuration import parse_deployment

    settings = get_settings()
    if settings.search_deployment_json is None:
        return ()
    deployment = parse_deployment(settings.search_deployment_json.get_secret_value())
    binding = deployment.binding
    if (
        binding.slot.kind != WorkKind.SEARCH
        or binding.slot.template is not None
        or binding.profile.producer_version != "1.0.0"
        or binding.profile.generator_version != "1.0.0"
        or binding.profile.output_schema_version != "1.0.0"
    ):
        return ()

    # No network access while announcing fleet capability. Actual physical work
    # resolves clients inside execute; M1 still checks pinned policy/fleet.
    class RegisteredSearchHandler:
        def execute(self, context: WorkExecutionContext) -> PreparedOutput:
            if context.attempt.work.binding != binding:
                raise SearchBackendUnavailableError("Pinned search profile mismatch")
            with Session(get_database_engine(), autoflush=False) as session:

                def load(scope: VersionScope) -> ArchitectureDocument:
                    document = SqlAlchemyPublishedArchitectureSource(
                        session
                    ).load_exact(scope.architecture_version_id, scope.project_id)
                    if document is None:
                        raise SearchBackendUnavailableError(
                            "Exact architecture unavailable"
                        )
                    return document

                return SearchWorkHandler(
                    backend=get_search_backend(),
                    repository=SqlAlchemySearchRepository(session),
                    document_loader=load,
                    index_settings=deployment.index_settings,
                ).execute(context)

    return (
        HandlerRegistration(
            binding=binding,
            handler=RegisteredSearchHandler(),
            publication_factory=create_search_publication_factory(),
        ),
    )


__all__ = [
    "create_search_handler_registration",
    "create_search_publication_factory",
    "get_search_backend",
    "get_search_cleanup_service",
    "get_search_reader",
    "get_search_repository",
    "get_search_status_service",
    "set_search_backend",
]
