"""Token service contract."""

from abc import ABC, abstractmethod

from backend.platform.identity.domain.token import TokenPayload
from backend.platform.identity.domain.user import User


class TokenService(ABC):
    """Contract for issuing and verifying authentication tokens."""

    @property
    @abstractmethod
    def expiration_seconds(self) -> int:
        """Return token lifetime in seconds."""
        ...

    @abstractmethod
    def create_access_token(self, user: User) -> str:
        """Issue a signed access token for the given user."""
        ...

    @abstractmethod
    def verify_token(self, token: str) -> TokenPayload:
        """Decode, authenticate, and validate an access token, returning its payload."""
        ...
