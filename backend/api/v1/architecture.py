"""Published Architecture Model result-query endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from backend.platform.analysis.application.dependencies import (
    DelegatedRequestContext,
    get_architecture_query_service,
    get_delegated_context,
    require_delegated_project,
)
from backend.platform.analysis.architecture.dto import (
    ArchitectureCollectionResponse,
    ArchitectureEntityResponse,
    ArchitectureVersionResponse,
)
from backend.platform.analysis.architecture.service import ArchitectureQueryService

router = APIRouter(tags=["Architecture Model"])


def _authorize(context: DelegatedRequestContext, project_id: UUID) -> None:
    require_delegated_project(context, project_id)


@router.get(
    "/analyses/{analysis_id}/architecture",
    response_model=ArchitectureVersionResponse,
    status_code=status.HTTP_200_OK,
)
def get_analysis_architecture(
    analysis_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    service: Annotated[
        ArchitectureQueryService, Depends(get_architecture_query_service)
    ],
) -> ArchitectureVersionResponse:
    _authorize(context, project_id)
    return service.get_for_analysis(analysis_id, project_id)


@router.get(
    "/architecture-versions/{version_id}",
    response_model=ArchitectureVersionResponse,
)
def get_architecture_version(
    version_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    service: Annotated[
        ArchitectureQueryService, Depends(get_architecture_query_service)
    ],
) -> ArchitectureVersionResponse:
    _authorize(context, project_id)
    return service.get_version(version_id, project_id)


@router.get(
    "/architecture-versions/{version_id}/entities",
    response_model=ArchitectureCollectionResponse,
)
def list_architecture_entities(
    version_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    service: Annotated[
        ArchitectureQueryService, Depends(get_architecture_query_service)
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    kind: str | None = None,
    entity_status: Annotated[str | None, Query(alias="status")] = None,
) -> ArchitectureCollectionResponse:
    _authorize(context, project_id)
    return service.list_entities(
        version_id,
        project_id,
        limit=limit,
        offset=offset,
        kind=kind,
        status=entity_status,
    )


@router.get(
    "/architecture-versions/{version_id}/entities/{entity_id}",
    response_model=ArchitectureEntityResponse,
)
def get_architecture_entity(
    version_id: UUID,
    entity_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    service: Annotated[
        ArchitectureQueryService, Depends(get_architecture_query_service)
    ],
) -> ArchitectureEntityResponse:
    _authorize(context, project_id)
    return service.get_entity(version_id, entity_id, project_id)


@router.get(
    "/architecture-versions/{version_id}/relationships",
    response_model=ArchitectureCollectionResponse,
)
def list_architecture_relationships(
    version_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    service: Annotated[
        ArchitectureQueryService, Depends(get_architecture_query_service)
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    kind: str | None = None,
    relationship_status: Annotated[str | None, Query(alias="status")] = None,
) -> ArchitectureCollectionResponse:
    _authorize(context, project_id)
    return service.list_relationships(
        version_id,
        project_id,
        limit=limit,
        offset=offset,
        kind=kind,
        status=relationship_status,
    )


@router.get(
    "/architecture-versions/{version_id}/evidence",
    response_model=ArchitectureCollectionResponse,
)
def list_architecture_evidence(
    version_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    service: Annotated[
        ArchitectureQueryService, Depends(get_architecture_query_service)
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    entity_id: Annotated[UUID | None, Query()] = None,
) -> ArchitectureCollectionResponse:
    _authorize(context, project_id)
    return service.list_evidence(
        version_id, project_id, limit=limit, offset=offset, entity_id=entity_id
    )


@router.get(
    "/architecture-versions/{version_id}/unresolved",
    response_model=ArchitectureCollectionResponse,
)
def list_architecture_unresolved(
    version_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    service: Annotated[
        ArchitectureQueryService, Depends(get_architecture_query_service)
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ArchitectureCollectionResponse:
    _authorize(context, project_id)
    return service.list_unresolved(version_id, project_id, limit=limit, offset=offset)


@router.get(
    "/architecture-versions/{version_id}/conflicts",
    response_model=ArchitectureCollectionResponse,
)
def list_architecture_conflicts(
    version_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    service: Annotated[
        ArchitectureQueryService, Depends(get_architecture_query_service)
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ArchitectureCollectionResponse:
    _authorize(context, project_id)
    return service.list_conflicts(version_id, project_id, limit=limit, offset=offset)


__all__ = ["router"]
