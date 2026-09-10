from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Project:
    """
    Domain entity representing a StackSense project.

    A project is the primary ownership and access boundary
    for repositories and future project-scoped resources.
    """

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
