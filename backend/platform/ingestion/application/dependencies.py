"""Dependency providers for the Ingestion application layer."""

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.platform.config import get_settings
from backend.platform.dependency_injection import get_database_session
from backend.platform.ingestion.application.classifier import (
    ArtifactClassifier,
)
from backend.platform.ingestion.application.service import (
    DefaultIngestionService,
    IngestionService,
)
from backend.platform.ingestion.application.validator import SourceValidator
from backend.platform.ingestion.infra.acquisition.directory_handler import (
    LocalDirectoryAcquisitionHandler,
)
from backend.platform.ingestion.infra.acquisition.zip_handler import (
    ZipArchiveAcquisitionHandler,
)
from backend.platform.ingestion.infra.artifact_repository import (
    SqlAlchemyArtifactRepository,
)
from backend.platform.ingestion.infra.ingestion_repository import (
    SqlAlchemyIngestionRepository,
)
from backend.platform.ingestion.infra.revision_repository import (
    SqlAlchemyRevisionRepository,
)
from backend.platform.ingestion.infra.storage.local_storage import (
    LocalStorageService,
)
from backend.platform.projects.application.authorization import (
    ProjectAuthorization,
)
from backend.platform.projects.application.dependencies import (
    get_project_authorization,
)
from backend.platform.repositories.infra.repository import (
    SqlAlchemyRepositoryRepository,
)


def get_ingestion_service(
    session: Session = Depends(get_database_session),
    authorization: ProjectAuthorization = Depends(get_project_authorization),
) -> Generator[IngestionService]:
    """Provide the Ingestion application service for an API request."""
    settings = get_settings()

    repository_repo = SqlAlchemyRepositoryRepository(session)
    ingestion_repo = SqlAlchemyIngestionRepository(session)
    revision_repo = SqlAlchemyRevisionRepository(session)
    artifact_repo = SqlAlchemyArtifactRepository(session)
    storage_service = LocalStorageService(settings.storage_root)

    acquisition_handlers = [
        ZipArchiveAcquisitionHandler(),
        LocalDirectoryAcquisitionHandler(),
    ]
    validator = SourceValidator()
    classifier = ArtifactClassifier()

    yield DefaultIngestionService(
        project_authorization=authorization,
        repository_repo=repository_repo,
        ingestion_repo=ingestion_repo,
        revision_repo=revision_repo,
        artifact_repo=artifact_repo,
        storage_service=storage_service,
        acquisition_handlers=acquisition_handlers,
        validator=validator,
        classifier=classifier,
    )
