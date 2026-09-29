"""Refresh token repository persistence contract."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.platform.identity.domain.refresh_token import RefreshToken


class RefreshTokenRepository(ABC):
    """Persistence contract for RefreshToken entities and rotation metadata."""

    @abstractmethod
    def save(self, refresh_token: RefreshToken) -> RefreshToken:
        """Persist a newly issued refresh token."""
        ...

    @abstractmethod
    def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        """Retrieve a refresh token by its deterministic cryptographic hash."""
        ...

    @abstractmethod
    def revoke(self, token_id: UUID, replaced_by_token_id: UUID | None = None) -> None:
        """Mark a token as revoked, optionally linking the replacement token ID."""
        ...

    @abstractmethod
    def revoke_all_for_user(self, user_id: UUID) -> None:
        """Revoke all active refresh tokens for a user (e.g., on password change)."""
        ...

    @abstractmethod
    def get_active_for_user(self, user_id: UUID) -> list[RefreshToken]:
        """Retrieve all active (non-expired, non-revoked) tokens for a user."""
        ...
