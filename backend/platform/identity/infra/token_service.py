"""JWT token infrastructure implementation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from pydantic import SecretStr

from backend.platform.errors import InvalidTokenError, TokenExpiredError
from backend.platform.identity.application.token import TokenService
from backend.platform.identity.domain.token import TokenPayload
from backend.platform.identity.domain.user import User


class JwtTokenService(TokenService):
    """PyJWT implementation of TokenService."""

    def __init__(
        self,
        secret_key: str | SecretStr,
        algorithm: str = "HS256",
        expiration_minutes: int = 60,
    ) -> None:
        self._secret_key = (
            secret_key.get_secret_value()
            if isinstance(secret_key, SecretStr)
            else secret_key
        )
        self._algorithm = algorithm
        self._expiration_minutes = expiration_minutes

    @property
    def expiration_seconds(self) -> int:
        """Return token lifetime in seconds."""
        return self._expiration_minutes * 60

    def create_access_token(self, user: User) -> str:
        """Issue a signed JWT access token for a user."""
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=self._expiration_minutes)
        token_id = str(uuid4())

        payload = {
            "sub": str(user.id),
            "email": user.email,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": token_id,
        }

        return jwt.encode(
            payload,
            self._secret_key,
            algorithm=self._algorithm,
        )

    def verify_token(self, token: str) -> TokenPayload:
        """Decode and validate a JWT access token."""
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                options={"require": ["sub", "email", "iat", "exp", "jti"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredError() from exc
        except jwt.PyJWTError as exc:
            raise InvalidTokenError() from exc

        try:
            user_id = UUID(payload["sub"])
        except (ValueError, TypeError) as exc:
            raise InvalidTokenError("Token subject is not a valid UUID.") from exc

        issued_at = datetime.fromtimestamp(payload["iat"], tz=UTC)
        expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC)

        return TokenPayload(
            user_id=user_id,
            email=payload["email"],
            token_id=payload["jti"],
            issued_at=issued_at,
            expires_at=expires_at,
        )
