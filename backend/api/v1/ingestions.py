"""Ingestion and repository revision API endpoints."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)

from backend.platform.identity.application.dependencies import (
    get_current_user,
)
from backend.platform.identity.domain.user import User
from backend.platform.ingestion.application.dependencies import (
    get_ingestion_service,
)
from backend.platform.ingestion.application.dto import (
    ArtifactResponse,
    IngestionResponse,
    RevisionResponse,
    TriggerIngestionRequest,
)
from backend.platform.ingestion.application.service import IngestionService

router = APIRouter(
    prefix="/projects/{project_id}/repositories/{repository_id}",
    tags=["Ingestion"],
)


@router.post(
    "/ingestions",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
)
def trigger_ingestion(
    project_id: UUID,
    repository_id: UUID,
    request: TriggerIngestionRequest,
    current_user: User = Depends(get_current_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> IngestionResponse:
    """Trigger ingestion for a repository using a local staged source reference."""
    # Ensure request repository_id matches the route parameter
    if request.repository_id != repository_id:
        request = TriggerIngestionRequest(
            repository_id=repository_id,
            source_type=request.source_type,
            source_reference=request.source_reference,
            revision_identifier=request.revision_identifier,
        )

    return service.trigger_ingestion(request, user=current_user)


@router.post(
    "/ingestions/upload",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_and_ingest(
    project_id: UUID,
    repository_id: UUID,
    file: Annotated[
        UploadFile,
        File(description="Repository source zip archive"),
    ],
    revision_identifier: Annotated[
        str | None,
        Form(description="Optional revision identifier (tag, branch, commit)"),
    ] = None,
    current_user: User = Depends(get_current_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> IngestionResponse:
    """Upload a source archive and trigger repository ingestion.

    Streams the uploaded payload to a temporary file on disk, executes the
    ingestion pipeline, and guarantees cleanup of the uploaded artifact.
    """
    temp_fd, temp_file_path = tempfile.mkstemp(
        prefix="stacksense_upload_",
        suffix=".zip",
    )
    os.close(temp_fd)
    destination = Path(temp_file_path)

    try:
        with open(destination, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        request = TriggerIngestionRequest(
            repository_id=repository_id,
            source_type="archive",
            source_reference=str(destination),
            revision_identifier=revision_identifier,
        )

        return service.trigger_ingestion(request, user=current_user)

    finally:
        if destination.exists():
            destination.unlink(missing_ok=True)


@router.get(
    "/ingestions/{ingestion_id}",
    response_model=IngestionResponse,
)
def get_ingestion(
    project_id: UUID,
    repository_id: UUID,
    ingestion_id: UUID,
    current_user: User = Depends(get_current_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> IngestionResponse:
    """Retrieve an ingestion job status by ID."""
    return service.get_ingestion(
        project_id=project_id,
        repository_id=repository_id,
        ingestion_id=ingestion_id,
        user=current_user,
    )


@router.get(
    "/ingestions",
    response_model=list[IngestionResponse],
)
def list_ingestions(
    project_id: UUID,
    repository_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> list[IngestionResponse]:
    """List ingestion jobs for a repository with pagination."""
    return service.list_ingestions(
        project_id=project_id,
        repository_id=repository_id,
        user=current_user,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/revisions",
    response_model=list[RevisionResponse],
)
def list_revisions(
    project_id: UUID,
    repository_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> list[RevisionResponse]:
    """List captured source revisions for a repository."""
    return service.list_revisions(
        project_id=project_id,
        repository_id=repository_id,
        user=current_user,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/revisions/{revision_id}",
    response_model=RevisionResponse,
)
def get_revision(
    project_id: UUID,
    repository_id: UUID,
    revision_id: UUID,
    current_user: User = Depends(get_current_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> RevisionResponse:
    """Retrieve a specific repository revision."""
    return service.get_revision(
        project_id=project_id,
        repository_id=repository_id,
        revision_id=revision_id,
        user=current_user,
    )


@router.get(
    "/revisions/{revision_id}/artifacts",
    response_model=list[ArtifactResponse],
)
def list_artifacts(
    project_id: UUID,
    repository_id: UUID,
    revision_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> list[ArtifactResponse]:
    """List artifacts belonging to a revision with pagination."""
    return service.list_artifacts(
        project_id=project_id,
        repository_id=repository_id,
        revision_id=revision_id,
        user=current_user,
        limit=limit,
        offset=offset,
    )
