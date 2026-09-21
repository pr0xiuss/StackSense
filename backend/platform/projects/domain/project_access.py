"""Project access domain model."""

from dataclasses import dataclass
from uuid import UUID

from backend.platform.projects.domain.project_role import ProjectRole


@dataclass(frozen=True)
class ProjectAccess:
    """Represent a user's access to a Project."""

    project_id: UUID
    user_id: UUID
    role: ProjectRole

    def can_read(self) -> bool:
        """Return whether this access allows project reads."""
        return True

    def can_create(self) -> bool:
        """Return whether this access allows project-level creation actions."""
        return self.role in {
            ProjectRole.OWNER,
            ProjectRole.ADMIN,
            ProjectRole.DEVELOPER,
        }

    def can_update(self) -> bool:
        """Return whether this access allows project updates."""
        return self.role in {
            ProjectRole.OWNER,
            ProjectRole.ADMIN,
            ProjectRole.DEVELOPER,
        }

    def can_delete(self) -> bool:
        """Return whether this access allows project deletion."""
        return self.role in {
            ProjectRole.OWNER,
            ProjectRole.ADMIN,
        }
