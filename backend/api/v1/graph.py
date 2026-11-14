"""P4-D1 Architecture Graph API endpoints."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Any, Final
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from backend.api.error_handlers import GRAPH_ERROR_STATUS_CODES
from backend.platform.analysis.application.dependencies import (
    DelegatedRequestContext,
    get_delegated_context,
    require_delegated_project,
)
from backend.platform.errors import (
    AnalysisAccessDeniedError,
    AnalysisInputError,
)
from backend.platform.graph.api_contracts import (
    GraphApiError,
    GraphErrorResponse,
    ProjectionRebuildAcceptedResponse,
    ProjectionStatusResponse,
)
from backend.platform.graph.api_dependencies import (
    get_correlation_id,
    get_graph_api_service,
)
from backend.platform.graph.api_service import GraphApiService
from backend.platform.graph.dependencies import (
    get_graph_query_health_probe,
    get_graph_query_service,
)
from backend.platform.graph.model import PROJECTION_TYPE
from backend.platform.graph.query_contracts import (
    DEFAULT_QUERY_DEPTH,
    DEFAULT_QUERY_EDGES,
    DEFAULT_QUERY_NODES,
    DEFAULT_QUERY_PAGE_SIZE,
    DEFAULT_QUERY_PATHS,
    DEFAULT_QUERY_TIMEOUT_SECONDS,
    MAX_CURSOR_LENGTH,
    MAX_QUERY_DEPTH,
    MAX_QUERY_EDGES,
    MAX_QUERY_NODES,
    MAX_QUERY_PAGE_SIZE,
    MAX_QUERY_PATHS,
    MAX_QUERY_TIMEOUT_SECONDS,
    BoundedPathsRequest,
    ContainmentDirection,
    ContainmentRequest,
    DependenciesRequest,
    DependentsRequest,
    GraphNode,
    GraphPathResult,
    GraphProjectionNotFoundError,
    GraphQueryError,
    GraphRelationshipKind,
    GraphSubgraph,
    GraphWindowRequest,
    NeighborhoodRequest,
    NodeDetailRequest,
    TraversalDirection,
)
from backend.platform.graph.query_health import (
    GraphQueryHealthProbe,
    GraphQueryHealthResponse,
)
from backend.platform.graph.query_service import GraphQueryService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Architecture Graph"])

GRAPH_ERROR_RESPONSES: Final[dict[int | str, dict[str, Any]]] = {
    401: {
        "model": GraphErrorResponse,
        "description": "Authentication Required or Invalid Token",
    },
    403: {
        "model": GraphErrorResponse,
        "description": "Forbidden / Access Denied",
    },
    404: {
        "model": GraphErrorResponse,
        "description": "Resource Not Found",
    },
    409: {
        "model": GraphErrorResponse,
        "description": "Conflict / Projection Not Ready",
    },
    410: {
        "model": GraphErrorResponse,
        "description": "Cursor Expired",
    },
    422: {
        "model": GraphErrorResponse,
        "description": "Validation Error / Invalid Input",
    },
    500: {
        "model": GraphErrorResponse,
        "description": "Internal Server Error",
    },
    503: {
        "model": GraphErrorResponse,
        "description": "Service Unavailable",
    },
    504: {
        "model": GraphErrorResponse,
        "description": "Gateway Timeout",
    },
}


def _authorize(context: DelegatedRequestContext, project_id: UUID) -> None:
    require_delegated_project(context, project_id)


def _authorize_rebuild(context: DelegatedRequestContext, project_id: UUID) -> None:
    if context.role not in ("OWNER", "ADMIN"):
        raise AnalysisAccessDeniedError(
            f"Role '{context.role}' does not have permission "
            "to perform this operation.",
            details={"role": context.role},
        )
    require_delegated_project(context, project_id)


def _log_graph_operation(
    *,
    operation: str,
    correlation_id: str,
    actor_id: UUID | None,
    actor_role: str,
    project_id: UUID,
    architecture_version_id: UUID,
    status_code: int,
    error_code: str | None = None,
) -> None:
    logger.info(
        "graph_api_operation",
        extra={
            "operation": operation,
            "correlation_id": correlation_id,
            "actor_id": str(actor_id) if actor_id is not None else None,
            "actor_role": actor_role,
            "project_id": str(project_id),
            "architecture_version_id": str(architecture_version_id),
            "status_code": status_code,
            "error_code": error_code,
        },
    )


@contextmanager
def _audit_graph_operation(
    *,
    operation: str,
    correlation_id: str,
    context: DelegatedRequestContext,
    project_id: UUID,
    architecture_version_id: UUID,
    success_status: int = 200,
) -> Iterator[None]:
    try:
        yield
        _log_graph_operation(
            operation=operation,
            correlation_id=correlation_id,
            actor_id=context.actor_id,
            actor_role=context.role,
            project_id=project_id,
            architecture_version_id=architecture_version_id,
            status_code=success_status,
        )
    except GraphApiError as exc:
        status_code = GRAPH_ERROR_STATUS_CODES.get(exc.code, 500)
        _log_graph_operation(
            operation=operation,
            correlation_id=correlation_id,
            actor_id=context.actor_id,
            actor_role=context.role,
            project_id=project_id,
            architecture_version_id=architecture_version_id,
            status_code=status_code,
            error_code=exc.code,
        )
        raise
    except GraphQueryError as exc:
        status_code = GRAPH_ERROR_STATUS_CODES.get(exc.code, 500)
        _log_graph_operation(
            operation=operation,
            correlation_id=correlation_id,
            actor_id=context.actor_id,
            actor_role=context.role,
            project_id=project_id,
            architecture_version_id=architecture_version_id,
            status_code=status_code,
            error_code=exc.code,
        )
        raise
    except AnalysisAccessDeniedError as exc:
        _log_graph_operation(
            operation=operation,
            correlation_id=correlation_id,
            actor_id=context.actor_id,
            actor_role=context.role,
            project_id=project_id,
            architecture_version_id=architecture_version_id,
            status_code=403,
            error_code=exc.code,
        )
        raise
    except AnalysisInputError as exc:
        _log_graph_operation(
            operation=operation,
            correlation_id=correlation_id,
            actor_id=context.actor_id,
            actor_role=context.role,
            project_id=project_id,
            architecture_version_id=architecture_version_id,
            status_code=422,
            error_code=exc.code,
        )
        raise
    except Exception as exc:
        err_code = getattr(exc, "code", "internal_error")
        _log_graph_operation(
            operation=operation,
            correlation_id=correlation_id,
            actor_id=context.actor_id,
            actor_role=context.role,
            project_id=project_id,
            architecture_version_id=architecture_version_id,
            status_code=500,
            error_code=str(err_code),
        )
        raise


@router.get(
    "/architecture-versions/{version_id}/graph/status",
    response_model=ProjectionStatusResponse,
    status_code=status.HTTP_200_OK,
    responses=GRAPH_ERROR_RESPONSES,
)
def get_projection_status(
    version_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
    api_service: Annotated[GraphApiService, Depends(get_graph_api_service)],
) -> ProjectionStatusResponse:
    """Return the exact-scope projection status and active attempt summary."""
    with _audit_graph_operation(
        operation="get_projection_status",
        correlation_id=correlation_id,
        context=context,
        project_id=project_id,
        architecture_version_id=version_id,
        success_status=200,
    ):
        _authorize(context, project_id)
        projection_status = api_service.get_status(
            project_id=project_id,
            architecture_version_id=version_id,
            projection_type=PROJECTION_TYPE,
        )
        if projection_status is None:
            raise GraphProjectionNotFoundError(
                "Graph projection resource not found for the requested version."
            )
        return projection_status


@router.post(
    "/architecture-versions/{version_id}/graph/rebuild",
    response_model=ProjectionRebuildAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {
            "model": ProjectionRebuildAcceptedResponse,
            "description": "Projection rebuild accepted",
        },
        **GRAPH_ERROR_RESPONSES,
    },
)
def request_rebuild(
    version_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
    api_service: Annotated[GraphApiService, Depends(get_graph_api_service)],
) -> ProjectionRebuildAcceptedResponse:
    """Request a durable rebuild of the architecture graph projection."""
    with _audit_graph_operation(
        operation="request_rebuild",
        correlation_id=correlation_id,
        context=context,
        project_id=project_id,
        architecture_version_id=version_id,
        success_status=202,
    ):
        _authorize_rebuild(context, project_id)
        if context.actor_id is None:
            raise AnalysisInputError("Delegated actor ID is required.")

        return api_service.request_rebuild(
            project_id=project_id,
            architecture_version_id=version_id,
            actor_id=context.actor_id,
            actor_role=context.role,
            correlation_id=correlation_id,
            projection_type=PROJECTION_TYPE,
        )


@router.get(
    "/architecture-versions/{version_id}/graph/nodes/{entity_id}",
    response_model=GraphNode,
    status_code=status.HTTP_200_OK,
    responses=GRAPH_ERROR_RESPONSES,
)
def get_node_detail(
    version_id: UUID,
    entity_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
    service: Annotated[GraphQueryService, Depends(get_graph_query_service)],
    timeout_seconds: Annotated[
        float,
        Query(
            gt=0,
            le=MAX_QUERY_TIMEOUT_SECONDS,
            description="Query timeout in seconds",
        ),
    ] = DEFAULT_QUERY_TIMEOUT_SECONDS,
) -> GraphNode:
    """Return entity detail inspector for a single node in the projected graph."""
    with _audit_graph_operation(
        operation="get_node_detail",
        correlation_id=correlation_id,
        context=context,
        project_id=project_id,
        architecture_version_id=version_id,
        success_status=200,
    ):
        _authorize(context, project_id)
        request = NodeDetailRequest(
            project_id=project_id,
            architecture_version_id=version_id,
            entity_id=entity_id,
            timeout_seconds=timeout_seconds,
        )
        return service.get_node_detail(request)


@router.get(
    "/architecture-versions/{version_id}/graph/window",
    response_model=GraphSubgraph,
    status_code=status.HTTP_200_OK,
    responses=GRAPH_ERROR_RESPONSES,
)
def get_graph_window(
    version_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
    service: Annotated[GraphQueryService, Depends(get_graph_query_service)],
    node_limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_NODES,
            description="Maximum number of nodes to return",
        ),
    ] = DEFAULT_QUERY_NODES,
    edge_limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_EDGES,
            description="Maximum number of edges to return",
        ),
    ] = DEFAULT_QUERY_EDGES,
    page_size: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_PAGE_SIZE,
            description="Maximum page size",
        ),
    ] = DEFAULT_QUERY_PAGE_SIZE,
    canonical_kinds: Annotated[
        list[GraphRelationshipKind] | None,
        Query(description="Allowed relationship kinds"),
    ] = None,
    cursor: Annotated[
        str | None,
        Query(
            max_length=MAX_CURSOR_LENGTH,
            description="Opaque pagination cursor",
        ),
    ] = None,
    timeout_seconds: Annotated[
        float,
        Query(
            gt=0,
            le=MAX_QUERY_TIMEOUT_SECONDS,
            description="Query timeout in seconds",
        ),
    ] = DEFAULT_QUERY_TIMEOUT_SECONDS,
) -> GraphSubgraph:
    """Return bounded initial graph window overview for the architecture version."""
    with _audit_graph_operation(
        operation="get_window",
        correlation_id=correlation_id,
        context=context,
        project_id=project_id,
        architecture_version_id=version_id,
        success_status=200,
    ):
        _authorize(context, project_id)
        request = GraphWindowRequest(
            project_id=project_id,
            architecture_version_id=version_id,
            node_limit=node_limit,
            edge_limit=edge_limit,
            page_size=page_size,
            canonical_kinds=(
                tuple(canonical_kinds) if canonical_kinds is not None else None
            ),
            cursor=cursor,
            timeout_seconds=timeout_seconds,
        )
        return service.get_window(request)


@router.get(
    "/architecture-versions/{version_id}/graph/nodes/{entity_id}/neighborhood",
    response_model=GraphSubgraph,
    status_code=status.HTTP_200_OK,
    responses=GRAPH_ERROR_RESPONSES,
)
def get_neighborhood(
    version_id: UUID,
    entity_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
    service: Annotated[GraphQueryService, Depends(get_graph_query_service)],
    direction: Annotated[
        TraversalDirection,
        Query(description="Traversal direction (incoming, outgoing, both)"),
    ] = TraversalDirection.BOTH,
    depth: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_DEPTH,
            description="Traversal depth",
        ),
    ] = DEFAULT_QUERY_DEPTH,
    node_limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_NODES,
            description="Maximum number of nodes to return",
        ),
    ] = DEFAULT_QUERY_NODES,
    edge_limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_EDGES,
            description="Maximum number of edges to return",
        ),
    ] = DEFAULT_QUERY_EDGES,
    relationship_kinds: Annotated[
        list[GraphRelationshipKind] | None,
        Query(description="Allowed relationship kinds"),
    ] = None,
    cursor: Annotated[
        str | None,
        Query(
            max_length=MAX_CURSOR_LENGTH,
            description="Opaque pagination cursor",
        ),
    ] = None,
    timeout_seconds: Annotated[
        float,
        Query(
            gt=0,
            le=MAX_QUERY_TIMEOUT_SECONDS,
            description="Query timeout in seconds",
        ),
    ] = DEFAULT_QUERY_TIMEOUT_SECONDS,
) -> GraphSubgraph:
    """Return structural expansion around an anchor node."""
    with _audit_graph_operation(
        operation="get_neighborhood",
        correlation_id=correlation_id,
        context=context,
        project_id=project_id,
        architecture_version_id=version_id,
        success_status=200,
    ):
        _authorize(context, project_id)
        request = NeighborhoodRequest(
            project_id=project_id,
            architecture_version_id=version_id,
            entity_id=entity_id,
            direction=direction,
            depth=depth,
            node_limit=node_limit,
            edge_limit=edge_limit,
            relationship_kinds=(
                tuple(relationship_kinds) if relationship_kinds is not None else None
            ),
            cursor=cursor,
            timeout_seconds=timeout_seconds,
        )
        return service.get_neighborhood(request)


@router.get(
    "/architecture-versions/{version_id}/graph/nodes/{entity_id}/dependencies",
    response_model=GraphSubgraph,
    status_code=status.HTTP_200_OK,
    responses=GRAPH_ERROR_RESPONSES,
)
def get_dependencies(
    version_id: UUID,
    entity_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
    service: Annotated[GraphQueryService, Depends(get_graph_query_service)],
    depth: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_DEPTH,
            description="Traversal depth",
        ),
    ] = DEFAULT_QUERY_DEPTH,
    node_limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_NODES,
            description="Maximum number of nodes to return",
        ),
    ] = DEFAULT_QUERY_NODES,
    edge_limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_EDGES,
            description="Maximum number of edges to return",
        ),
    ] = DEFAULT_QUERY_EDGES,
    relationship_kinds: Annotated[
        list[GraphRelationshipKind] | None,
        Query(description="Allowed relationship kinds (excluding contains)"),
    ] = None,
    cursor: Annotated[
        str | None,
        Query(
            max_length=MAX_CURSOR_LENGTH,
            description="Opaque pagination cursor",
        ),
    ] = None,
    timeout_seconds: Annotated[
        float,
        Query(
            gt=0,
            le=MAX_QUERY_TIMEOUT_SECONDS,
            description="Query timeout in seconds",
        ),
    ] = DEFAULT_QUERY_TIMEOUT_SECONDS,
) -> GraphSubgraph:
    """Return outgoing dependencies traversal from an anchor node."""
    with _audit_graph_operation(
        operation="get_dependencies",
        correlation_id=correlation_id,
        context=context,
        project_id=project_id,
        architecture_version_id=version_id,
        success_status=200,
    ):
        _authorize(context, project_id)
        request = DependenciesRequest(
            project_id=project_id,
            architecture_version_id=version_id,
            entity_id=entity_id,
            depth=depth,
            node_limit=node_limit,
            edge_limit=edge_limit,
            relationship_kinds=(
                tuple(relationship_kinds) if relationship_kinds is not None else None
            ),
            cursor=cursor,
            timeout_seconds=timeout_seconds,
        )
        return service.get_dependencies(request)


@router.get(
    "/architecture-versions/{version_id}/graph/nodes/{entity_id}/dependents",
    response_model=GraphSubgraph,
    status_code=status.HTTP_200_OK,
    responses=GRAPH_ERROR_RESPONSES,
)
def get_dependents(
    version_id: UUID,
    entity_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
    service: Annotated[GraphQueryService, Depends(get_graph_query_service)],
    depth: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_DEPTH,
            description="Traversal depth",
        ),
    ] = DEFAULT_QUERY_DEPTH,
    node_limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_NODES,
            description="Maximum number of nodes to return",
        ),
    ] = DEFAULT_QUERY_NODES,
    edge_limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_EDGES,
            description="Maximum number of edges to return",
        ),
    ] = DEFAULT_QUERY_EDGES,
    relationship_kinds: Annotated[
        list[GraphRelationshipKind] | None,
        Query(description="Allowed relationship kinds (excluding contains)"),
    ] = None,
    cursor: Annotated[
        str | None,
        Query(
            max_length=MAX_CURSOR_LENGTH,
            description="Opaque pagination cursor",
        ),
    ] = None,
    timeout_seconds: Annotated[
        float,
        Query(
            gt=0,
            le=MAX_QUERY_TIMEOUT_SECONDS,
            description="Query timeout in seconds",
        ),
    ] = DEFAULT_QUERY_TIMEOUT_SECONDS,
) -> GraphSubgraph:
    """Return incoming dependents traversal to an anchor node."""
    with _audit_graph_operation(
        operation="get_dependents",
        correlation_id=correlation_id,
        context=context,
        project_id=project_id,
        architecture_version_id=version_id,
        success_status=200,
    ):
        _authorize(context, project_id)
        request = DependentsRequest(
            project_id=project_id,
            architecture_version_id=version_id,
            entity_id=entity_id,
            depth=depth,
            node_limit=node_limit,
            edge_limit=edge_limit,
            relationship_kinds=(
                tuple(relationship_kinds) if relationship_kinds is not None else None
            ),
            cursor=cursor,
            timeout_seconds=timeout_seconds,
        )
        return service.get_dependents(request)


@router.get(
    "/architecture-versions/{version_id}/graph/nodes/{entity_id}/containment",
    response_model=GraphSubgraph,
    status_code=status.HTTP_200_OK,
    responses=GRAPH_ERROR_RESPONSES,
)
def get_containment(
    version_id: UUID,
    entity_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
    service: Annotated[GraphQueryService, Depends(get_graph_query_service)],
    direction: Annotated[
        ContainmentDirection,
        Query(description="Containment direction (parents, children, both)"),
    ] = ContainmentDirection.CHILDREN,
    depth: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_DEPTH,
            description="Hierarchy traversal depth",
        ),
    ] = DEFAULT_QUERY_DEPTH,
    node_limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_NODES,
            description="Maximum number of nodes to return",
        ),
    ] = DEFAULT_QUERY_NODES,
    edge_limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_EDGES,
            description="Maximum number of edges to return",
        ),
    ] = DEFAULT_QUERY_EDGES,
    cursor: Annotated[
        str | None,
        Query(
            max_length=MAX_CURSOR_LENGTH,
            description="Opaque pagination cursor",
        ),
    ] = None,
    timeout_seconds: Annotated[
        float,
        Query(
            gt=0,
            le=MAX_QUERY_TIMEOUT_SECONDS,
            description="Query timeout in seconds",
        ),
    ] = DEFAULT_QUERY_TIMEOUT_SECONDS,
) -> GraphSubgraph:
    """Return hierarchy navigation for contains relationships."""
    with _audit_graph_operation(
        operation="get_containment",
        correlation_id=correlation_id,
        context=context,
        project_id=project_id,
        architecture_version_id=version_id,
        success_status=200,
    ):
        _authorize(context, project_id)
        request = ContainmentRequest(
            project_id=project_id,
            architecture_version_id=version_id,
            entity_id=entity_id,
            direction=direction,
            depth=depth,
            node_limit=node_limit,
            edge_limit=edge_limit,
            cursor=cursor,
            timeout_seconds=timeout_seconds,
        )
        return service.get_containment(request)


@router.get(
    "/architecture-versions/{version_id}/graph/paths",
    response_model=GraphPathResult,
    status_code=status.HTTP_200_OK,
    responses=GRAPH_ERROR_RESPONSES,
)
def get_bounded_paths(
    version_id: UUID,
    project_id: UUID,
    source_entity_id: Annotated[
        UUID,
        Query(description="Source entity UUID"),
    ],
    target_entity_id: Annotated[
        UUID,
        Query(description="Target entity UUID"),
    ],
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
    service: Annotated[GraphQueryService, Depends(get_graph_query_service)],
    max_depth: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_DEPTH,
            description="Maximum path traversal depth",
        ),
    ] = 3,
    path_limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_QUERY_PATHS,
            description="Maximum number of paths to return",
        ),
    ] = DEFAULT_QUERY_PATHS,
    relationship_kinds: Annotated[
        list[GraphRelationshipKind] | None,
        Query(description="Allowed relationship kinds (excluding contains)"),
    ] = None,
    timeout_seconds: Annotated[
        float,
        Query(
            gt=0,
            le=MAX_QUERY_TIMEOUT_SECONDS,
            description="Query timeout in seconds",
        ),
    ] = DEFAULT_QUERY_TIMEOUT_SECONDS,
) -> GraphPathResult:
    """Return bounded simple paths between source and target entities."""
    with _audit_graph_operation(
        operation="get_bounded_paths",
        correlation_id=correlation_id,
        context=context,
        project_id=project_id,
        architecture_version_id=version_id,
        success_status=200,
    ):
        _authorize(context, project_id)
        request = BoundedPathsRequest(
            project_id=project_id,
            architecture_version_id=version_id,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            max_depth=max_depth,
            path_limit=path_limit,
            relationship_kinds=(
                tuple(relationship_kinds) if relationship_kinds is not None else None
            ),
            timeout_seconds=timeout_seconds,
        )
        return service.get_bounded_paths(request)


@router.get(
    "/health/graph/query",
    response_model=GraphQueryHealthResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "model": GraphQueryHealthResponse,
            "description": "Query engine health check result",
        },
    },
)
def get_query_health(
    probe: Annotated[GraphQueryHealthProbe, Depends(get_graph_query_health_probe)],
) -> GraphQueryHealthResponse:
    """Report independent query engine health without changing core readiness."""
    health = probe.check()
    logger.info(
        "graph_query_health",
        extra={
            "status": health.status.value,
            "code": health.code,
        },
    )
    return health
