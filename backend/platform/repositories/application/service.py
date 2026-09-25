"""Default implementation of the Repository application service."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from backend.platform.errors import (
    ProjectAccessDeniedError,
    RepositoryAlreadyExistsError,
    RepositoryNotFoundError,
)
from backend.platform.identity.domain.user import User
from backend.platform.projects.application.authorization import (
    ProjectAuthorization,
)
from backend.platform.repositories.application.dto import (
    RegisterRepositoryRequest,
    RepositoryResponse,
    UpdateRepositoryRequest,
)
from backend.platform.repositories.application.repository_service import (
    RepositoryService,
)
from backend.platform.repositories.domain.repository import Repository
from backend.platform.repositories.repositories.repository_repo import (
    RepositoryRepository,
)


class DefaultRepositoryService(RepositoryService):
    """Default application service coordinating Repository operations.

    Enforces Project boundaries, authorization access rules, unique naming
    invariants, and DTO transformations.
    """

    def __init__(
        self,
        repository: RepositoryRepository,
        authorization: ProjectAuthorization | None = None,
    ) -> None:
        self._repository = repository
        self._authorization = authorization

    def register(
        self,
        project_id: UUID,
        request: RegisterRepositoryRequest,
        user: User | None = None,
    ) -> RepositoryResponse:
        """Register a repository under the specified project."""
        if self._authorization is not None:
            if user is None:
                raise ProjectAccessDeniedError()
            self._authorization.require_create_access(project_id, user)

        existing = self._repository.get_by_project_and_name(
            project_id=project_id,
            name=request.name,
        )
        if existing is not None:
            raise RepositoryAlreadyExistsError()

        now = datetime.now(UTC)
        domain_repo = Repository(
            id=uuid4(),
            project_id=project_id,
            name=request.name,
            description=request.description,
            status="registered",
            created_at=now,
            updated_at=now,
        )

        try:
            persisted = self._repository.save(domain_repo)
        except IntegrityError as exc:
            raise RepositoryAlreadyExistsError() from exc

        return RepositoryResponse.model_validate(persisted)

    def get(
        self,
        project_id: UUID,
        repository_id: UUID,
        user: User | None = None,
    ) -> RepositoryResponse:
        """Retrieve a repository by identifier within a project."""
        if self._authorization is not None:
            if user is None:
                raise ProjectAccessDeniedError()
            self._authorization.require_access(project_id, user)

        repo = self._repository.get_by_id(repository_id)
        if repo is None or repo.project_id != project_id:
            raise RepositoryNotFoundError()

        return RepositoryResponse.model_validate(repo)

    def list_by_project(
        self,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        user: User | None = None,
    ) -> list[RepositoryResponse]:
        """List repositories belonging to a project with pagination."""
        if self._authorization is not None:
            if user is None:
                raise ProjectAccessDeniedError()
            self._authorization.require_access(project_id, user)

        repositories = self._repository.list_by_project(
            project_id=project_id,
            limit=limit,
            offset=offset,
        )
        return [RepositoryResponse.model_validate(r) for r in repositories]

    def update(
        self,
        project_id: UUID,
        repository_id: UUID,
        request: UpdateRepositoryRequest,
        user: User | None = None,
    ) -> RepositoryResponse:
        """Update an existing repository."""
        if self._authorization is not None:
            if user is None:
                raise ProjectAccessDeniedError()
            self._authorization.require_update_access(project_id, user)

        existing = self._repository.get_by_id(repository_id)
        if existing is None or existing.project_id != project_id:
            raise RepositoryNotFoundError()

        target_name = request.name if request.name is not None else existing.name
        target_description = (
            request.description
            if request.description is not None
            else existing.description
        )

        if request.name is not None and request.name != existing.name:
            conflict = self._repository.get_by_project_and_name(
                project_id=project_id,
                name=request.name,
            )
            if conflict is not None and conflict.id != repository_id:
                raise RepositoryAlreadyExistsError()

        now = datetime.now(UTC)
        updated_repo = Repository(
            id=existing.id,
            project_id=existing.project_id,
            name=target_name,
            description=target_description,
            status=existing.status,
            created_at=existing.created_at,
            updated_at=now,
        )

        try:
            persisted = self._repository.update(updated_repo)
        except IntegrityError as exc:
            raise RepositoryAlreadyExistsError() from exc

        return RepositoryResponse.model_validate(persisted)

    def delete(
        self,
        project_id: UUID,
        repository_id: UUID,
        user: User | None = None,
    ) -> None:
        """Delete a repository from a project."""
        if self._authorization is not None:
            if user is None:
                raise ProjectAccessDeniedError()
            self._authorization.require_delete_access(project_id, user)

        existing = self._repository.get_by_id(repository_id)
        if existing is None or existing.project_id != project_id:
            raise RepositoryNotFoundError()

        self._repository.delete(repository_id)
