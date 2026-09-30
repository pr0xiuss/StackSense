"""Repository domain model."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Repository:
    """Domain entity representing a registered repository.

    A repository represents the logical source repository registered within a
    Project. It belongs to exactly one Project and maintains a stable identity
    across analyses and snapshot ingestions.
    """

    id: UUID
    project_id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime
