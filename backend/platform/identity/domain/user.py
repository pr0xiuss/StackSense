"""Identity domain primitives."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from backend.platform.identity.domain.constants import USERNAME_PATTERN


@dataclass(frozen=True)
class User:
    """Represent an authenticated StackSense user."""

    id: UUID
    email: str
    username: str
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.email or not self.email.strip():
            raise ValueError("User email cannot be empty.")

        normalized_email = self.email.strip().lower()
        object.__setattr__(self, "email", normalized_email)

        if not self.username or not self.username.strip():
            raise ValueError("User username cannot be empty.")

        normalized_username = self.username.strip().lower()
        if not USERNAME_PATTERN.match(normalized_username):
            raise ValueError(
                "Username must be between 3 and 30 characters and contain "
                "only letters, numbers, and underscores."
            )
        object.__setattr__(self, "username", normalized_username)
