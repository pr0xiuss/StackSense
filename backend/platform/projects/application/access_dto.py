"""Project access application DTOs."""

from uuid import UUID

from pydantic import BaseModel

from backend.platform.projects.domain.project_role import ProjectRole


class GrantProjectAccessRequest(BaseModel):
    """Request to grant a user access to a project."""

    user_id: UUID
    role: ProjectRole


class UpdateProjectAccessRequest(BaseModel):
    """Request to change a project member's role."""

    role: ProjectRole


class ProjectAccessResponse(BaseModel):
    """Public representation of project access."""

    project_id: UUID
    user_id: UUID
    role: ProjectRole

    model_config = {
        "from_attributes": True,
    }
