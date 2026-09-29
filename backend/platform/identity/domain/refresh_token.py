"""Refresh token domain primitives."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RefreshToken:
    """Represent an issued refresh token with rotation and revocation metadata."""

    id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime
    replaced_by_token_id: UUID | None = None

    @property
    def is_active(self) -> bool:
        """Return True if token is not revoked and has not expired."""
        now = datetime.now(UTC)
        return self.revoked_at is None and self.expires_at > now

    @property
    def is_expired(self) -> bool:
        """Return True if token expiry is in the past."""
        return self.expires_at <= datetime.now(UTC)

    @property
    def is_revoked(self) -> bool:
        """Return True if token has been revoked."""
        return self.revoked_at is not None
