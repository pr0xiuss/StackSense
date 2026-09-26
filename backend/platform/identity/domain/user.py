"""Identity domain primitives."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class User:
    """Represent an authenticated StackSense user."""

    id: UUID
    email: str
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.email or not self.email.strip():
            raise ValueError("User email cannot be empty.")
