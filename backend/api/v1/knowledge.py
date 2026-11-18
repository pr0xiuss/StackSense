"""FastAPI HTTP endpoints for Phase 5 Module 2 Knowledge and Search.

Implements thin, authorized search and status endpoints with delegated RBAC,
structured error responses, and no independent authentication per §7.4, §7.8, and §7.10.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.requests import Request
from starlette.responses import Response

from backend.platform.analysis.application.dependencies import (
    DelegatedRequestContext,
    get_architecture_query_service,
    get_delegated_context,
    require_delegated_project,
)
from backend.platform.analysis.architecture.service import ArchitectureQueryService
from backend.platform.delivery.api_contracts import DeliveryApiError
from backend.platform.delivery.dependencies import get_delivery_reader
from backend.platform.delivery.reprojection import (
    AuthorizedReprojectionPrincipal,
    ReprojectionKey,
    SearchReprojectionAccepted,
)
from backend.platform.delivery.source import PublishedVersionReader
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
    get_search_rebuild_service,
    get_search_status_service,
)
from backend.platform.knowledge.model import KnowledgeDocumentKind
from backend.platform.knowledge.reader import SearchReader
from backend.platform.knowledge.rebuild import SearchRebuildService
from backend.platform.knowledge.service import SearchStatusService


class SearchRoute(APIRoute):
    """Map M2 dependency failures as well as endpoint failures safely."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def bounded_handler(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError:
                return _error_response(
                    "search_invalid_request", "Invalid search request", 422
                )
            except SearchError as exc:
                return _handle_search_error(exc)
            except DeliveryApiError as exc:
                return _error_response(
                    exc.code, "Search rebuild could not be accepted", exc.status
                )
            except ValidationError:
                return _error_response(
                    "search_invalid_request",
                    "Invalid search request or accepted metadata",
                    422,
                )

        return bounded_handler


router = APIRouter(tags=["Knowledge Search"], route_class=SearchRoute)


class SearchRebuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    idempotency_key: ReprojectionKey


@router.post(
    "/architecture-versions/{version_id}/search/rebuild",
    response_model=SearchReprojectionAccepted,
    status_code=202,
)
def rebuild_search(
    version_id: UUID,
    project_id: UUID,
    body: SearchRebuildRequest,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    versions: Annotated[
        ArchitectureQueryService, Depends(get_architecture_query_service)
    ],
    source: Annotated[PublishedVersionReader, Depends(get_delivery_reader)],
    service: Annotated[SearchRebuildService, Depends(get_search_rebuild_service)],
) -> SearchReprojectionAccepted:
    require_delegated_project(context, project_id)
    if context.actor_id is None:
        raise DeliveryApiError("delivery_reprojection_forbidden", 403)
    scope = source.inspect_requested(versions.get_version(version_id, project_id)).scope
    return service.request(
        scope,
        body.idempotency_key,
        AuthorizedReprojectionPrincipal(
            actor_id=context.actor_id, project_id=project_id, role=context.role
        ),
    )


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
        return _error_response(exc.code, exc.message, 409)
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
        return _error_response(exc.code, exc.message, 422)
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
    q: Annotated[
        str, Query(min_length=1, max_length=MAX_SEARCH_QUERY_LENGTH, pattern=r"\S")
    ],
    mode: Annotated[str, Query()] = "lexical",
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
    if mode not in {"lexical", "semantic", "hybrid"}:
        return _error_response("search_invalid_mode", "Unknown search mode", 422)
    if mode != "lexical":
        return _handle_search_error(SearchCapabilityUnavailableError())

    parsed_doc_kinds: tuple[KnowledgeDocumentKind, ...] | None = None
    if document_kinds:
        try:
            parsed_doc_kinds = tuple(KnowledgeDocumentKind(k) for k in document_kinds)
        except ValueError:
            return _error_response(
                "invalid_document_kind",
                "Unknown search document kind",
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
        return reader.search(request, actor_id=context.actor_id)
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
