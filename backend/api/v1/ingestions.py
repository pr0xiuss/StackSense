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

from backend.platform.errors import UnsupportedArchiveFormatError
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
from backend.platform.ingestion.domain.constants import SourceType

router = APIRouter(
    prefix="/projects/{project_id}/repositories/{repository_id}",
    tags=["Ingestion"],
)

SUPPORTED_ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".tar", ".zip")


def _get_upload_suffix(filename: str | None) -> str:
    """Validate upload filename and return canonical archive suffix.

    Extension Handling Behavior (IR-M4-013, IR-M4-014):
    - Supported extensions: '.zip', '.tar', '.tar.gz', '.tgz' (case-insensitive).
    - Evaluation order: Compound extensions ('.tar.gz') are checked prior to
      single-part extensions ('.tar') to prevent misclassifying tar.gz archives.
      '.tgz' is recognized as a direct alias for tar.gz archives.
    - Suffix preservation: The detected suffix is preserved when creating the
      temporary staging file, allowing ArchiveExtractor to route to the appropriate
      zipfile or tarfile decompression engine.
    """
    if not filename:
        raise UnsupportedArchiveFormatError(
            "Uploaded file must have a filename with a supported archive extension."
        )
    fn_lower = filename.lower()
    for ext in SUPPORTED_ARCHIVE_SUFFIXES:
        if fn_lower.endswith(ext):
            return ext
    raise UnsupportedArchiveFormatError(
        f"Unsupported archive format for file '{filename}'. "
        "Supported formats: .zip, .tar, .tar.gz, .tgz."
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
    """Trigger ingestion for a repository using a source reference.

    Supports three source acquisition modes (IR-M4-015):
    1. 'github': Public GitHub repository URL ('https://github.com/owner/repo')
       with optional 'ref' branch/tag/commit reference.
    2. 'archive': Server-staged archive file (.zip, .tar, .tar.gz, .tgz).
    3. 'server_path': Host server filesystem path (directory or staged archive)
       strictly verified against configured allowed_source_roots.
    """
    # Ensure request repository_id matches the route parameter
    if request.repository_id != repository_id:
        data = request.model_dump()
        data["repository_id"] = repository_id
        request = TriggerIngestionRequest(**data)

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
        File(description="Repository source archive (.zip, .tar, .tar.gz, .tgz)"),
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
    common ingestion pipeline, and guarantees cleanup of the uploaded artifact.

    Extension Handling (IR-M4-013, IR-M4-014):
    - Validates uploaded filename against SUPPORTED_ARCHIVE_SUFFIXES
      (.zip, .tar, .tar.gz, .tgz).
    - Preserves file extension on temporary staging file for downstream engine routing.
    - Rejects unsupported file formats with UnsupportedArchiveFormatError (HTTP 422).

    Ingestion Mode Note (IR-M4-015):
    - This multipart endpoint processes client-uploaded file archives only.
    - For server filesystem paths (pre-staged directories or archives residing in
      allowed server roots), use POST /ingestions with source_type="server_path".
    """
    suffix = _get_upload_suffix(file.filename)
    temp_fd, temp_file_path = tempfile.mkstemp(
        prefix="stacksense_upload_",
        suffix=suffix,
    )
    os.close(temp_fd)
    destination = Path(temp_file_path)

    try:
        with open(destination, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        request = TriggerIngestionRequest(
            repository_id=repository_id,
            source_type=SourceType.ARCHIVE,
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
