"""FastAPI HTTP endpoints for Phase 5 Module 2 Knowledge and Search.

Implements thin, authorized search and status endpoints with delegated RBAC,
structured error responses, and no independent authentication per §7.4, §7.8, and §7.10.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from backend.platform.analysis.application.dependencies import (
    DelegatedRequestContext,
    get_architecture_query_service,
    get_delegated_context,
    require_delegated_project,
)
from backend.platform.analysis.architecture.service import ArchitectureQueryService
from backend.platform.knowledge.contracts import (
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_SEARCH_TIMEOUT_SECONDS,
    MAX_SEARCH_CURSOR_LENGTH,
    MAX_SEARCH_LIMIT,
    MAX_SEARCH_QUERY_LENGTH,
    MAX_SEARCH_TIMEOUT_SECONDS,
    SearchBackendUnavailableError,
    SearchCapabilityUnavailableError,
    SearchCapacityExceededError,
    SearchCursorExpiredError,
    SearchCursorInvalidError,
    SearchDeadlineExceededError,
    SearchError,
    SearchGenerationChangedError,
    SearchIntegrityError,
    SearchNotReadyError,
    SearchPage,
    SearchRequest,
    SearchStatus,
)
from backend.platform.knowledge.dependencies import (
    get_search_reader,
    get_search_status_service,
)
from backend.platform.knowledge.model import KnowledgeDocumentKind
from backend.platform.knowledge.reader import SearchReader
from backend.platform.knowledge.service import SearchStatusService

router = APIRouter(tags=["Knowledge Search"])


def _error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": {},
            }
        },
    )


def _handle_search_error(exc: SearchError) -> JSONResponse:
    if isinstance(exc, SearchNotReadyError):
        return _error_response(exc.code, exc.message, 404)
    if isinstance(exc, SearchGenerationChangedError):
        return _error_response(exc.code, exc.message, 409)
    if isinstance(exc, SearchCursorExpiredError):
        return _error_response(exc.code, exc.message, 410)
    if isinstance(exc, (SearchCursorInvalidError, SearchCapacityExceededError)):
        return _error_response(exc.code, exc.message, 422)
    if isinstance(exc, SearchDeadlineExceededError):
        return _error_response(exc.code, exc.message, 504)
    if isinstance(exc, SearchBackendUnavailableError):
        return _error_response(exc.code, exc.message, 503)
    if isinstance(exc, SearchCapabilityUnavailableError):
        return _error_response(exc.code, exc.message, 400)
    if isinstance(exc, SearchIntegrityError):
        return _error_response(exc.code, exc.message, 500)
    return _error_response(exc.code, exc.message, 400)


@router.get(
    "/architecture-versions/{version_id}/search",
    response_model=SearchPage,
    status_code=200,
)
@router.get(
    "/projects/{project_id}/architecture/{version_id}/search",
    response_model=SearchPage,
    status_code=200,
    include_in_schema=False,
)
def search_architecture_knowledge(
    version_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    versions: Annotated[
        ArchitectureQueryService, Depends(get_architecture_query_service)
    ],
    reader: Annotated[SearchReader, Depends(get_search_reader)],
    q: Annotated[str, Query(min_length=1, max_length=MAX_SEARCH_QUERY_LENGTH)],
    limit: Annotated[int, Query(ge=1, le=MAX_SEARCH_LIMIT)] = DEFAULT_SEARCH_LIMIT,
    cursor: Annotated[str | None, Query(max_length=MAX_SEARCH_CURSOR_LENGTH)] = None,
    document_kinds: Annotated[list[str] | None, Query()] = None,
    entity_kinds: Annotated[list[str] | None, Query()] = None,
    statuses: Annotated[list[str] | None, Query()] = None,
    timeout_seconds: Annotated[
        float, Query(gt=0, le=MAX_SEARCH_TIMEOUT_SECONDS)
    ] = DEFAULT_SEARCH_TIMEOUT_SECONDS,
) -> SearchPage | JSONResponse:
    """Execute scoped lexical search against an architecture version's search index."""
    require_delegated_project(context, project_id)
    versions.get_version(version_id, project_id)

    parsed_doc_kinds: tuple[KnowledgeDocumentKind, ...] | None = None
    if document_kinds:
        try:
            parsed_doc_kinds = tuple(KnowledgeDocumentKind(k) for k in document_kinds)
        except ValueError:
            return _error_response(
                "invalid_document_kind",
                f"Unknown document kind in {document_kinds}",
                422,
            )

    request = SearchRequest(
        project_id=project_id,
        architecture_version_id=version_id,
        q=q,
        mode="lexical",
        document_kinds=parsed_doc_kinds,
        entity_kinds=tuple(entity_kinds) if entity_kinds else None,
        statuses=tuple(statuses) if statuses else None,
        limit=limit,
        cursor=cursor,
        timeout_seconds=timeout_seconds,
    )

    try:
        return reader.search(request)
    except SearchError as exc:
        return _handle_search_error(exc)


@router.get(
    "/architecture-versions/{version_id}/search/status",
    response_model=SearchStatus,
    status_code=200,
)
@router.get(
    "/projects/{project_id}/architecture/{version_id}/search/status",
    response_model=SearchStatus,
    status_code=200,
    include_in_schema=False,
)
def get_search_status(
    version_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    versions: Annotated[
        ArchitectureQueryService, Depends(get_architecture_query_service)
    ],
    status_service: Annotated[SearchStatusService, Depends(get_search_status_service)],
) -> SearchStatus | JSONResponse:
    """Retrieve search projection freshness, readiness, and capabilities."""
    require_delegated_project(context, project_id)
    versions.get_version(version_id, project_id)

    try:
        return status_service.get_status(project_id, version_id)
    except SearchError as exc:
        return _handle_search_error(exc)
