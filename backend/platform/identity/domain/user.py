"""Identity domain primitives."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class User:
    """Represent an authenticated StackSense user."""

    id: UUID
