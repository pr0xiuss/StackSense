"""FastAPI HTTP endpoints for Phase 5 Module 3 Controlled Retrieval.

Implements thin, authorized query, context, and evidence endpoints with
delegated RBAC, structured error responses, and no independent authentication
per §7A.8, §7A.10, and §7A.11 of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import Response

from backend.platform.analysis.application.dependencies import (
    DelegatedRequestContext,
    get_delegated_context,
    require_delegated_project,
)
from backend.platform.errors import StackSenseError
from backend.platform.knowledge.retrieval import KnowledgeQueryService
from backend.platform.knowledge.retrieval_contracts import (
    DEFAULT_RETRIEVAL_LIMIT,
    MAX_RETRIEVAL_LIMIT,
    ContextBundle,
    ContextRequest,
    EvidencePage,
    EvidenceRequest,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    RetrievalCapacityExceededError,
    RetrievalCursorExpiredError,
    RetrievalCursorInvalidError,
    RetrievalDeadlineExceededError,
    RetrievalError,
    RetrievalGenerationChangedError,
    RetrievalIntegrityFailedError,
    RetrievalInvalidRequestError,
    RetrievalNotFoundError,
    RetrievalPrincipal,
    RetrievalUnavailableError,
)
from backend.platform.knowledge.retrieval_dependencies import (
    get_knowledge_query_service,
)

logger = logging.getLogger(__name__)
SAFE_CAUSES = frozenset(
    {
        "search_unavailable",
        "graph_unavailable",
        "canonical_unavailable",
        "search_cursor_expired",
        "search_cursor_invalid",
        "search_generation_changed",
        "search_capacity_exceeded",
        "search_deadline_exceeded",
        "search_not_ready",
        "search_backend_unavailable",
        "search_capability_unavailable",
        "search_integrity_error",
        "graph_generation_changed",
        "graph_query_timeout",
        "graph_query_integrity_error",
        "graph_projection_not_found",
        "graph_projection_not_ready",
        "graph_schema_incompatible",
        "graph_node_not_found",
    }
)


def _error_response(
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
    cause: str | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }
    if cause in SAFE_CAUSES:
        content["error"]["cause"] = cause
    return JSONResponse(status_code=status_code, content=content)


def _handle_retrieval_error(exc: RetrievalError) -> JSONResponse:
    if isinstance(exc, RetrievalNotFoundError):
        return _error_response(exc.code, exc.message, 404, exc.safe_details, exc.cause)
    if isinstance(exc, RetrievalGenerationChangedError):
        return _error_response(exc.code, exc.message, 409, exc.safe_details, exc.cause)
    if isinstance(exc, RetrievalCursorExpiredError):
        return _error_response(exc.code, exc.message, 410, exc.safe_details, exc.cause)
    if isinstance(
        exc,
        (
            RetrievalInvalidRequestError,
            RetrievalCursorInvalidError,
            RetrievalCapacityExceededError,
        ),
    ):
        return _error_response(exc.code, exc.message, 422, exc.safe_details, exc.cause)
    if isinstance(exc, RetrievalUnavailableError):
        return _error_response(exc.code, exc.message, 503, exc.safe_details, exc.cause)
    if isinstance(exc, RetrievalDeadlineExceededError):
        return _error_response(exc.code, exc.message, 504, exc.safe_details, exc.cause)
    if isinstance(exc, RetrievalIntegrityFailedError):
        return _error_response(exc.code, exc.message, 500, exc.safe_details, exc.cause)
    return _error_response(exc.code, exc.message, 400, exc.safe_details, exc.cause)


class RetrievalRoute(APIRoute):
    """Custom APIRoute class ensuring closed error mapping for C3 endpoints."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def bounded_handler(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError:
                logger.info("retrieval_request_validation_failed")
                return _error_response(
                    "retrieval_invalid_request",
                    "Invalid retrieval request parameters",
                    422,
                )
            except ValidationError:
                return _error_response(
                    "retrieval_invalid_request",
                    "Invalid retrieval payload or schema",
                    422,
                )
            except RetrievalError as exc:
                return _handle_retrieval_error(exc)
            except StackSenseError:
                raise
            except HTTPException:
                raise
            except Exception:
                logger.error("unhandled_retrieval_route_exception")
                return _error_response(
                    "retrieval_integrity_failed",
                    "Internal retrieval failure",
                    500,
                )

        return bounded_handler


def authorized_retrieval(
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
) -> DelegatedRequestContext:
    require_delegated_project(context, project_id)
    if context.actor_id is None:
        raise RetrievalInvalidRequestError("A delegated actor is required")
    return context


router = APIRouter(
    tags=["Controlled Retrieval"],
    route_class=RetrievalRoute,
    dependencies=[Depends(authorized_retrieval)],
)


def principal_for(
    context: DelegatedRequestContext, project_id: UUID
) -> RetrievalPrincipal:
    return RetrievalPrincipal(
        actor_id=context.actor_id,
        project_id=project_id,
        role=context.role,
        correlation_id=context.correlation_id,
    )


def route_body(
    body: dict[str, Any], version_id: UUID, project_id: UUID
) -> dict[str, Any]:
    for key, value in (
        ("project_id", project_id),
        ("architecture_version_id", version_id),
    ):
        if key in body and str(body[key]) != str(value):
            raise RetrievalInvalidRequestError("Request scope does not match route")
    return {**body, "project_id": project_id, "architecture_version_id": version_id}


@router.post(
    "/architecture-versions/{version_id}/knowledge/query",
    response_model=KnowledgeQueryResponse,
)
def query_architecture_knowledge(
    version_id: UUID,
    project_id: UUID,
    request: dict[str, Any],
    context: Annotated[DelegatedRequestContext, Depends(authorized_retrieval)],
    query_service: Annotated[
        KnowledgeQueryService, Depends(get_knowledge_query_service)
    ],
) -> Response:
    value = KnowledgeQueryRequest.model_validate(
        route_body(request, version_id, project_id)
    )
    query_service.query(value, principal=principal_for(context, project_id))
    return Response(content=query_service.response_bytes, media_type="application/json")


@router.post(
    "/architecture-versions/{version_id}/knowledge/context",
    response_model=ContextBundle,
)
def assemble_retrieval_context(
    version_id: UUID,
    project_id: UUID,
    body: dict[str, Any],
    context: Annotated[DelegatedRequestContext, Depends(authorized_retrieval)],
    query_service: Annotated[
        KnowledgeQueryService, Depends(get_knowledge_query_service)
    ],
) -> Response:
    value = ContextRequest.model_validate(route_body(body, version_id, project_id))
    query_service.build_context(value, principal=principal_for(context, project_id))
    return Response(content=query_service.response_bytes, media_type="application/json")


@router.get(
    "/architecture-versions/{version_id}/knowledge/evidence",
    response_model=EvidencePage,
)
def get_architecture_evidence_page(
    version_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(authorized_retrieval)],
    query_service: Annotated[
        KnowledgeQueryService, Depends(get_knowledge_query_service)
    ],
    entity_id: Annotated[list[UUID] | None, Query()] = None,
    relationship_id: Annotated[list[UUID] | None, Query()] = None,
    evidence_id: Annotated[list[UUID] | None, Query()] = None,
    limit: Annotated[
        int, Query(ge=1, le=MAX_RETRIEVAL_LIMIT)
    ] = DEFAULT_RETRIEVAL_LIMIT,
    cursor: Annotated[str | None, Query(max_length=4096)] = None,
    offset: Annotated[int | None, Query()] = None,
) -> Response:
    if offset is not None:
        raise RetrievalInvalidRequestError(
            "Use the signed continuation cursor, not offsets"
        )
    value = EvidenceRequest(
        project_id=project_id,
        architecture_version_id=version_id,
        entity_ids=tuple(entity_id or ()),
        relationship_ids=tuple(relationship_id or ()),
        evidence_ids=tuple(evidence_id or ()),
        limit=limit,
        cursor=cursor,
    )
    query_service.read_evidence(value, principal=principal_for(context, project_id))
    return Response(content=query_service.response_bytes, media_type="application/json")


__all__ = ["router"]
