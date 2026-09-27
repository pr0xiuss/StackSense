"""Authentication application service."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from backend.platform.errors import (
    InvalidCredentialsError,
    InvalidTokenError,
    UserAlreadyExistsError,
    UserInactiveError,
)
from backend.platform.identity.application.dto import AuthTokenResponse
from backend.platform.identity.application.password import PasswordHasher
from backend.platform.identity.application.token import TokenService
from backend.platform.identity.domain.credential import UserCredential
from backend.platform.identity.domain.token import TokenPayload
from backend.platform.identity.domain.user import User
from backend.platform.identity.repositories.user_repo import UserRepository


class AuthenticationService:
    """Coordinate user authentication, token issuance, and token verification."""

    # Pre-computed bcrypt hash for constant-time dummy verification on nonexistent
    # users, protecting against timing attacks and account enumeration.
    _DUMMY_BCRYPT_HASH = "$2b$12$7kQeGj9P.3uW/W0oD0k9ve8yqCj0Z7WzB2H5tJ1aL3mN6oP9qRsTu"

    def __init__(
        self,
        user_repo: UserRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
    ) -> None:
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._token_service = token_service

    def register(self, email: str, password: str) -> User:
        """Register a new user with hashed credentials."""
        self._password_hasher.validate(password)
        normalized_email = email.strip().lower()

        existing = self._user_repo.get_by_email(normalized_email)
        if existing is not None:
            raise UserAlreadyExistsError()

        now = datetime.now(UTC)
        user_id = uuid4()
        user = User(
            id=user_id,
            email=normalized_email,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        password_hash = self._password_hasher.hash(password)
        credential = UserCredential(
            user_id=user_id,
            password_hash=password_hash,
            created_at=now,
            updated_at=now,
        )

        try:
            return self._user_repo.save(user, credential)
        except IntegrityError as exc:
            raise UserAlreadyExistsError() from exc

    def authenticate(self, email: str, password: str) -> AuthTokenResponse:
        """Authenticate a user by credentials and return an access token."""
        normalized_email = email.strip().lower() if email else ""

        user = self._user_repo.get_by_email(normalized_email)
        if user is None:
            # Constant-time mitigation against user enumeration
            self._password_hasher.verify(password, self._DUMMY_BCRYPT_HASH)
            raise InvalidCredentialsError()

        if not user.is_active:
            raise UserInactiveError()

        credential = self._user_repo.get_credential_by_user_id(user.id)
        if credential is None:
            raise InvalidCredentialsError()

        if not self._password_hasher.verify(password, credential.password_hash):
            raise InvalidCredentialsError()

        token = self._token_service.create_access_token(user)

        return AuthTokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=self._token_service.expiration_seconds,
        )

    def verify_token(self, token: str) -> TokenPayload:
        """Verify access token signature and claims, returning token payload."""
        return self._token_service.verify_token(token)

    def get_user_from_token(self, token: str) -> User:
        """Verify token and resolve the active User from persistence."""
        payload = self.verify_token(token)
        user = self._user_repo.get_by_id(payload.user_id)
        if user is None:
            raise InvalidTokenError("User associated with token does not exist.")
        if not user.is_active:
            raise UserInactiveError()
        return user
