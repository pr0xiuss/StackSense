"""Project-scoped access roles."""

from enum import StrEnum


class ProjectRole(StrEnum):
    """Roles that define access within a Project."""

    OWNER = "owner"
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"
