"""Token service contract."""

from abc import ABC, abstractmethod
from datetime import datetime

from backend.platform.identity.domain.token import TokenPayload
from backend.platform.identity.domain.user import User


class TokenService(ABC):
    """Contract for issuing and verifying authentication tokens."""

    @property
    @abstractmethod
    def expiration_seconds(self) -> int:
        """Return access token lifetime in seconds."""
        ...

    @property
    @abstractmethod
    def refresh_expiration_seconds(self) -> int:
        """Return refresh token lifetime in seconds."""
        ...

    @abstractmethod
    def create_access_token(self, user: User) -> str:
        """Issue a signed access token for the given user."""
        ...

    @abstractmethod
    def verify_token(self, token: str) -> TokenPayload:
        """Decode, authenticate, and validate an access token, returning its payload."""
        ...

    @abstractmethod
    def create_refresh_token(self, user: User) -> tuple[str, str, datetime]:
        """Generate a refresh token: (raw_token, token_hash, expires_at)."""
        ...

    @abstractmethod
    def hash_refresh_token(self, raw_token: str) -> str:
        """Compute the deterministic cryptographic hash of a raw refresh token."""
        ...

    @abstractmethod
    def legacy_hash_refresh_token(self, raw_token: str) -> str:
        """Compute unkeyed SHA-256 hash for backward compatibility."""
        ...
