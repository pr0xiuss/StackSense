"""Token domain primitives."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class TokenPayload:
    """Represent validated authentication token claims."""

    user_id: UUID
    email: str
    token_id: str
    issued_at: datetime
    expires_at: datetime
