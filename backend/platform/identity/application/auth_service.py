"""Authentication application service."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from backend.platform.errors import (
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    InvalidTokenError,
    RefreshTokenExpiredError,
    RefreshTokenRevokedError,
    UserAlreadyExistsError,
    UserInactiveError,
    UsernameAlreadyExistsError,
)
from backend.platform.identity.application.dto import AuthTokenResponse
from backend.platform.identity.application.password import PasswordHasher
from backend.platform.identity.application.token import TokenService
from backend.platform.identity.domain.credential import UserCredential
from backend.platform.identity.domain.refresh_token import RefreshToken
from backend.platform.identity.domain.token import TokenPayload
from backend.platform.identity.domain.user import User
from backend.platform.identity.repositories.refresh_token_repo import (
    RefreshTokenRepository,
)
from backend.platform.identity.repositories.user_repo import UserRepository


class AuthenticationService:
    """Coordinate authentication, token issuance, refresh rotation, and verification."""

    # Pre-computed bcrypt hash for constant-time dummy verification on nonexistent
    # users, protecting against timing attacks and account enumeration.
    _DUMMY_BCRYPT_HASH = "$2b$12$7kQeGj9P.3uW/W0oD0k9ve8yqCj0Z7WzB2H5tJ1aL3mN6oP9qRsTu"

    def __init__(
        self,
        user_repo: UserRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
        refresh_token_repo: RefreshTokenRepository,
    ) -> None:
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._token_service = token_service
        self._refresh_token_repo = refresh_token_repo

    def register(self, email: str, username: str, password: str) -> User:
        """Register a new user with email, unique username, and hashed credentials."""
        self._password_hasher.validate(password)
        normalized_email = email.strip().lower()
        normalized_username = username.strip().lower()

        # Application-level pre-checks for clear domain errors
        if self._user_repo.get_by_email(normalized_email) is not None:
            raise UserAlreadyExistsError()

        if self._user_repo.get_by_username(normalized_username) is not None:
            raise UsernameAlreadyExistsError()

        now = datetime.now(UTC)
        user_id = uuid4()
        user = User(
            id=user_id,
            email=normalized_email,
            username=normalized_username,
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
            err_msg = str(exc).lower()
            if "ix_users_username_lower" in err_msg or "users.username" in err_msg:
                raise UsernameAlreadyExistsError() from exc
            if "ix_users_email_lower" in err_msg or "users.email" in err_msg:
                raise UserAlreadyExistsError() from exc
            raise

    def authenticate(self, identifier: str, password: str) -> AuthTokenResponse:
        """Authenticate user by email/username and return access/refresh token pair."""
        normalized_identifier = identifier.strip().lower() if identifier else ""

        # Try lookup by email first, then by username
        user = self._user_repo.get_by_email(normalized_identifier)
        if user is None:
            user = self._user_repo.get_by_username(normalized_identifier)

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

        access_token = self._token_service.create_access_token(user)
        raw_refresh, token_hash, expires_at = self._token_service.create_refresh_token(
            user
        )

        now = datetime.now(UTC)
        refresh_record = RefreshToken(
            id=uuid4(),
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked_at=None,
            created_at=now,
            replaced_by_token_id=None,
        )
        self._refresh_token_repo.save(refresh_record)

        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",
            expires_in=self._token_service.expiration_seconds,
            refresh_expires_in=self._token_service.refresh_expiration_seconds,
        )

    def refresh_access_token(self, refresh_token: str) -> AuthTokenResponse:
        """Rotate active refresh token and issue a fresh access/refresh token pair."""
        token_hash = self._token_service.hash_refresh_token(refresh_token)
        record = self._refresh_token_repo.get_by_token_hash(token_hash)
        if record is None:
            # Backward-compatible lookup for legacy unkeyed SHA-256 tokens
            legacy_hash = self._token_service.legacy_hash_refresh_token(refresh_token)
            record = self._refresh_token_repo.get_by_token_hash(legacy_hash)

        if record is None:
            raise InvalidRefreshTokenError()

        if record.is_revoked:
            raise RefreshTokenRevokedError()

        if record.is_expired:
            raise RefreshTokenExpiredError()

        user = self._user_repo.get_by_id(record.user_id)
        if user is None:
            raise InvalidTokenError("User associated with token does not exist.")
        if not user.is_active:
            raise UserInactiveError()

        # Issue new refresh token
        new_raw_refresh, new_token_hash, new_expires_at = (
            self._token_service.create_refresh_token(user)
        )
        now = datetime.now(UTC)
        new_token_id = uuid4()
        new_record = RefreshToken(
            id=new_token_id,
            user_id=user.id,
            token_hash=new_token_hash,
            expires_at=new_expires_at,
            revoked_at=None,
            created_at=now,
            replaced_by_token_id=None,
        )
        self._refresh_token_repo.save(new_record)

        # Revoke old refresh token with audit trail link
        self._refresh_token_repo.revoke(record.id, replaced_by_token_id=new_token_id)

        new_access_token = self._token_service.create_access_token(user)

        return AuthTokenResponse(
            access_token=new_access_token,
            refresh_token=new_raw_refresh,
            token_type="bearer",
            expires_in=self._token_service.expiration_seconds,
            refresh_expires_in=self._token_service.refresh_expiration_seconds,
        )

    def revoke_refresh_token(self, refresh_token: str) -> None:
        """Revoke a refresh token upon logout."""
        token_hash = self._token_service.hash_refresh_token(refresh_token)
        record = self._refresh_token_repo.get_by_token_hash(token_hash)
        if record is None:
            legacy_hash = self._token_service.legacy_hash_refresh_token(refresh_token)
            record = self._refresh_token_repo.get_by_token_hash(legacy_hash)
        if record is not None and not record.is_revoked:
            self._refresh_token_repo.revoke(record.id)

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
