"""User credential domain model."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class UserCredential:
    """Internal credential record for password authentication."""

    user_id: UUID
    password_hash: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
