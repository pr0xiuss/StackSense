"""Ingestion application service orchestrating acquisition and storage."""

import hashlib
import shutil
import tempfile
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from backend.platform.errors import (
    ActiveIngestionExistsError,
    IngestionNotFoundError,
    RepositoryNotFoundError,
    SourceValidationError,
    StackSenseError,
)
from backend.platform.identity.domain.user import User
from backend.platform.ingestion.application.acquisition import (
    AcquisitionHandler,
)
from backend.platform.ingestion.application.classifier import (
    ArtifactClassifier,
)
from backend.platform.ingestion.application.dto import (
    ArtifactResponse,
    IngestionResponse,
    RevisionResponse,
    TriggerIngestionRequest,
)
from backend.platform.ingestion.application.storage import StorageService
from backend.platform.ingestion.application.validator import SourceValidator
from backend.platform.ingestion.domain.artifact import RepositoryArtifact
from backend.platform.ingestion.domain.constants import IngestionStatus
from backend.platform.ingestion.domain.ingestion import Ingestion
from backend.platform.ingestion.domain.revision import RepositoryRevision
from backend.platform.ingestion.repositories.artifact_repo import (
    ArtifactRepository,
)
from backend.platform.ingestion.repositories.ingestion_repo import (
    IngestionRepository,
)
from backend.platform.ingestion.repositories.revision_repo import (
    RevisionRepository,
)
from backend.platform.projects.application.authorization import (
    ProjectAuthorization,
)
from backend.platform.repositories.repositories.repository_repo import (
    RepositoryRepository,
)


class IngestionService(ABC):
    """Abstract application service for repository ingestion workflows."""

    @abstractmethod
    def trigger_ingestion(
        self,
        request: TriggerIngestionRequest,
        user: User,
    ) -> IngestionResponse:
        """Trigger repository ingestion process."""
        raise NotImplementedError

    @abstractmethod
    def get_ingestion(
        self,
        project_id: UUID,
        repository_id: UUID,
        ingestion_id: UUID,
        user: User,
    ) -> IngestionResponse:
        """Retrieve an ingestion job by ID."""
        raise NotImplementedError

    @abstractmethod
    def list_ingestions(
        self,
        project_id: UUID,
        repository_id: UUID,
        user: User,
        *,
        limit: int,
        offset: int,
    ) -> list[IngestionResponse]:
        """List ingestion jobs for a repository."""
        raise NotImplementedError

    @abstractmethod
    def get_revision(
        self,
        project_id: UUID,
        repository_id: UUID,
        revision_id: UUID,
        user: User,
    ) -> RevisionResponse:
        """Retrieve a specific repository revision."""
        raise NotImplementedError

    @abstractmethod
    def list_revisions(
        self,
        project_id: UUID,
        repository_id: UUID,
        user: User,
        *,
        limit: int,
        offset: int,
    ) -> list[RevisionResponse]:
        """List revisions belonging to a repository."""
        raise NotImplementedError

    @abstractmethod
    def list_artifacts(
        self,
        project_id: UUID,
        repository_id: UUID,
        revision_id: UUID,
        user: User,
        *,
        limit: int,
        offset: int,
    ) -> list[ArtifactResponse]:
        """List artifacts belonging to a revision with deterministic pagination."""
        raise NotImplementedError


class DefaultIngestionService(IngestionService):
    """Production implementation of IngestionService."""

    def __init__(
        self,
        project_authorization: ProjectAuthorization,
        repository_repo: RepositoryRepository,
        ingestion_repo: IngestionRepository,
        revision_repo: RevisionRepository,
        artifact_repo: ArtifactRepository,
        storage_service: StorageService,
        acquisition_handlers: list[AcquisitionHandler],
        validator: SourceValidator,
        classifier: ArtifactClassifier,
    ) -> None:
        self._project_authorization = project_authorization
        self._repository_repo = repository_repo
        self._ingestion_repo = ingestion_repo
        self._revision_repo = revision_repo
        self._artifact_repo = artifact_repo
        self._storage_service = storage_service
        self._acquisition_handlers = acquisition_handlers
        self._validator = validator
        self._classifier = classifier

    def trigger_ingestion(
        self,
        request: TriggerIngestionRequest,
        user: User,
    ) -> IngestionResponse:
        repository = self._repository_repo.get_by_id(request.repository_id)
        if repository is None:
            raise RepositoryNotFoundError()

        # Enforce server-side project authorization boundary
        self._project_authorization.require_create_access(
            repository.project_id,
            user,
        )

        # Check active ingestion concurrency guard
        recent_ingestions = self._ingestion_repo.list_by_repository(
            repository.id,
            limit=10,
            offset=0,
        )
        if any(ing.status == IngestionStatus.PROCESSING for ing in recent_ingestions):
            raise ActiveIngestionExistsError()

        now = datetime.now(UTC)
        ingestion = Ingestion(
            id=uuid4(),
            project_id=repository.project_id,
            repository_id=repository.id,
            source_type=request.source_type,
            source_reference=request.source_reference,
            status=IngestionStatus.PENDING,
            error_code=None,
            error_message=None,
            started_at=None,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        try:
            ingestion = self._ingestion_repo.save(ingestion)

            # Transition to PROCESSING
            started_now = datetime.now(UTC)
            ingestion = Ingestion(
                id=ingestion.id,
                project_id=ingestion.project_id,
                repository_id=ingestion.repository_id,
                source_type=ingestion.source_type,
                source_reference=ingestion.source_reference,
                status=IngestionStatus.PROCESSING,
                error_code=None,
                error_message=None,
                started_at=started_now,
                completed_at=None,
                created_at=ingestion.created_at,
                updated_at=started_now,
            )
            ingestion = self._ingestion_repo.update(ingestion)
        except IntegrityError as exc:
            if "uq_ingestions_active_repo" in str(exc).lower():
                raise ActiveIngestionExistsError() from exc
            raise

        temp_dir = tempfile.mkdtemp(prefix=f"stacksense_ingest_{ingestion.id}_")
        temp_path = Path(temp_dir)

        try:
            handler = next(
                (
                    h
                    for h in self._acquisition_handlers
                    if h.can_handle(request.source_type)
                ),
                None,
            )
            if handler is None:
                raise SourceValidationError(
                    f"Unsupported repository source type: {request.source_type}"
                )

            acquisition_result = handler.acquire(
                request.source_reference,
                request.revision_identifier,
                temp_path,
            )

            validated_source = self._validator.validate(acquisition_result.root_path)

            artifacts: list[RepositoryArtifact] = []
            rev_id = uuid4()
            art_now = datetime.now(UTC)

            for item in validated_source.files:
                # Streaming SHA-256 to avoid full-file memory load (Section 7.17)
                hasher = hashlib.sha256()
                with open(item.absolute_path, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        hasher.update(chunk)
                content_hash = hasher.hexdigest()

                category, support_level = self._classifier.classify(
                    item.relative_path,
                    item.size_bytes,
                )

                storage_key = f"content/{content_hash[:2]}/{content_hash}"
                if not self._storage_service.exists(storage_key):
                    with open(item.absolute_path, "rb") as f:
                        self._storage_service.put(storage_key, f)

                artifact = RepositoryArtifact(
                    id=uuid4(),
                    project_id=repository.project_id,
                    repository_id=repository.id,
                    revision_id=rev_id,
                    path=item.relative_path,
                    size_bytes=item.size_bytes,
                    content_hash=content_hash,
                    category=category,
                    support_level=support_level,
                    storage_key=storage_key,
                    created_at=art_now,
                )
                artifacts.append(artifact)

            # Create and persist Revision
            revision = RepositoryRevision(
                id=rev_id,
                project_id=repository.project_id,
                repository_id=repository.id,
                ingestion_id=ingestion.id,
                revision_identifier=acquisition_result.revision_identifier,
                source_hash=acquisition_result.source_hash,
                total_files=validated_source.total_files,
                total_bytes=validated_source.total_bytes,
                created_at=art_now,
            )
            self._revision_repo.save(revision)

            # Persist artifact batch
            self._artifact_repo.save_batch(artifacts)

            # Transition to COMPLETED
            completed_now = datetime.now(UTC)
            ingestion = Ingestion(
                id=ingestion.id,
                project_id=ingestion.project_id,
                repository_id=ingestion.repository_id,
                source_type=ingestion.source_type,
                source_reference=ingestion.source_reference,
                status=IngestionStatus.COMPLETED,
                error_code=None,
                error_message=None,
                started_at=ingestion.started_at,
                completed_at=completed_now,
                created_at=ingestion.created_at,
                updated_at=completed_now,
            )
            ingestion = self._ingestion_repo.update(ingestion)
            return self._to_ingestion_dto(ingestion)

        except Exception as exc:
            failed_now = datetime.now(UTC)
            code = exc.code if isinstance(exc, StackSenseError) else "ingestion_failed"
            message = exc.message if isinstance(exc, StackSenseError) else str(exc)

            failed_ingestion = Ingestion(
                id=ingestion.id,
                project_id=ingestion.project_id,
                repository_id=ingestion.repository_id,
                source_type=ingestion.source_type,
                source_reference=ingestion.source_reference,
                status=IngestionStatus.FAILED,
                error_code=code,
                error_message=message,
                started_at=ingestion.started_at,
                completed_at=failed_now,
                created_at=ingestion.created_at,
                updated_at=failed_now,
            )
            self._ingestion_repo.update(failed_ingestion)
            raise

        finally:
            shutil.rmtree(temp_path, ignore_errors=True)

    def get_ingestion(
        self,
        project_id: UUID,
        repository_id: UUID,
        ingestion_id: UUID,
        user: User,
    ) -> IngestionResponse:
        self._project_authorization.require_access(project_id, user)
        self._ensure_repo_belongs_to_project(repository_id, project_id)

        ingestion = self._ingestion_repo.get_by_id(ingestion_id)
        if (
            ingestion is None
            or ingestion.repository_id != repository_id
            or ingestion.project_id != project_id
        ):
            raise IngestionNotFoundError()

        return self._to_ingestion_dto(ingestion)

    def list_ingestions(
        self,
        project_id: UUID,
        repository_id: UUID,
        user: User,
        *,
        limit: int,
        offset: int,
    ) -> list[IngestionResponse]:
        self._project_authorization.require_access(project_id, user)
        self._ensure_repo_belongs_to_project(repository_id, project_id)

        ingestions = self._ingestion_repo.list_by_repository(
            repository_id,
            limit=limit,
            offset=offset,
        )
        return [self._to_ingestion_dto(ing) for ing in ingestions]

    def get_revision(
        self,
        project_id: UUID,
        repository_id: UUID,
        revision_id: UUID,
        user: User,
    ) -> RevisionResponse:
        self._project_authorization.require_access(project_id, user)
        self._ensure_repo_belongs_to_project(repository_id, project_id)

        revision = self._revision_repo.get_by_id(revision_id)
        if (
            revision is None
            or revision.repository_id != repository_id
            or revision.project_id != project_id
        ):
            raise IngestionNotFoundError("Repository revision not found.")

        return self._to_revision_dto(revision)

    def list_revisions(
        self,
        project_id: UUID,
        repository_id: UUID,
        user: User,
        *,
        limit: int,
        offset: int,
    ) -> list[RevisionResponse]:
        self._project_authorization.require_access(project_id, user)
        self._ensure_repo_belongs_to_project(repository_id, project_id)

        revisions = self._revision_repo.list_by_repository(
            repository_id,
            limit=limit,
            offset=offset,
        )
        return [self._to_revision_dto(rev) for rev in revisions]

    def list_artifacts(
        self,
        project_id: UUID,
        repository_id: UUID,
        revision_id: UUID,
        user: User,
        *,
        limit: int,
        offset: int,
    ) -> list[ArtifactResponse]:
        self._project_authorization.require_access(project_id, user)
        self._ensure_repo_belongs_to_project(repository_id, project_id)

        # Verify revision belongs to this repository
        revision = self._revision_repo.get_by_id(revision_id)
        if (
            revision is None
            or revision.repository_id != repository_id
            or revision.project_id != project_id
        ):
            raise IngestionNotFoundError("Repository revision not found.")

        artifacts = self._artifact_repo.list_by_revision(
            revision_id,
            limit=limit,
            offset=offset,
        )
        return [self._to_artifact_dto(art) for art in artifacts]

    def _ensure_repo_belongs_to_project(
        self,
        repository_id: UUID,
        project_id: UUID,
    ) -> None:
        repo = self._repository_repo.get_by_id(repository_id)
        if repo is None or repo.project_id != project_id:
            raise RepositoryNotFoundError()

    @staticmethod
    def _to_ingestion_dto(ingestion: Ingestion) -> IngestionResponse:
        return IngestionResponse(
            id=ingestion.id,
            project_id=ingestion.project_id,
            repository_id=ingestion.repository_id,
            source_type=ingestion.source_type,
            source_reference=ingestion.source_reference,
            status=ingestion.status.value,
            error_code=ingestion.error_code,
            error_message=ingestion.error_message,
            started_at=ingestion.started_at,
            completed_at=ingestion.completed_at,
            created_at=ingestion.created_at,
            updated_at=ingestion.updated_at,
        )

    @staticmethod
    def _to_revision_dto(revision: RepositoryRevision) -> RevisionResponse:
        return RevisionResponse(
            id=revision.id,
            project_id=revision.project_id,
            repository_id=revision.repository_id,
            ingestion_id=revision.ingestion_id,
            revision_identifier=revision.revision_identifier,
            source_hash=revision.source_hash,
            total_files=revision.total_files,
            total_bytes=revision.total_bytes,
            created_at=revision.created_at,
        )

    @staticmethod
    def _to_artifact_dto(artifact: RepositoryArtifact) -> ArtifactResponse:
        return ArtifactResponse(
            id=artifact.id,
            project_id=artifact.project_id,
            repository_id=artifact.repository_id,
            revision_id=artifact.revision_id,
            path=artifact.path,
            size_bytes=artifact.size_bytes,
            content_hash=artifact.content_hash,
            category=artifact.category.value,
            support_level=artifact.support_level.value,
            storage_key=artifact.storage_key,
            created_at=artifact.created_at,
        )
