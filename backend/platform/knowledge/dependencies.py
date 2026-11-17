"""Dependency injection factories and registration helpers for P5-M2 search services."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.platform.analysis.architecture.model import ArchitectureDocument
from backend.platform.delivery.contracts import HandlerProfile, VersionScope
from backend.platform.delivery.publication import (
    GuardedEnlistedSession,
    ProducerPublicationFactory,
    ProducerPublicationPort,
)
from backend.platform.delivery.registry import HandlerRegistration
from backend.platform.dependency_injection import get_database_session
from backend.platform.knowledge.elasticsearch import (
    InMemorySearchBackend,
    SearchIndexBackend,
)
from backend.platform.knowledge.reader import SearchReader
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
        _DEFAULT_SEARCH_BACKEND = InMemorySearchBackend()
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
    return SearchReader(backend=backend, repository=repository)


def get_search_status_service(
    repository: Annotated[SqlAlchemySearchRepository, Depends(get_search_repository)],
) -> SearchStatusService:
    """FastAPI dependency for SearchStatusService."""
    return SearchStatusService(repository=repository)


def get_search_cleanup_service(
    backend: Annotated[SearchIndexBackend, Depends(get_search_backend)],
    repository: Annotated[SqlAlchemySearchRepository, Depends(get_search_repository)],
    session: Annotated[Session, Depends(get_database_session)],
) -> SearchCleanupService:
    """FastAPI dependency for SearchCleanupService."""
    return SearchCleanupService(repository=repository, backend=backend, session=session)


def create_search_publication_factory() -> ProducerPublicationFactory:
    """Create a publication factory accepting GuardedEnlistedSession from M1."""

    def _factory(session: GuardedEnlistedSession) -> ProducerPublicationPort:
        return SearchPublicationPort(session)

    return _factory


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
    publication_factory = create_search_publication_factory()
    return HandlerRegistration(
        binding=binding,
        handler=handler,
        publication_factory=publication_factory,
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
