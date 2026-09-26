"""Dependency providers for the Identity application layer."""

from functools import lru_cache

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.platform.dependency_injection import (
    get_application_settings,
    get_database_session,
)
from backend.platform.errors import (
    AuthenticationRequiredError,
    InvalidTokenError,
    UserInactiveError,
)
from backend.platform.identity.application.auth_service import AuthenticationService
from backend.platform.identity.application.current_user import (
    AuthenticatedCurrentUserProvider,
    CurrentUserProvider,
)
from backend.platform.identity.application.password import PasswordHasher
from backend.platform.identity.application.token import TokenService
from backend.platform.identity.domain.user import User
from backend.platform.identity.infra.password_hasher import BcryptPasswordHasher
from backend.platform.identity.infra.token_service import JwtTokenService
from backend.platform.identity.infra.user_repo import SqlAlchemyUserRepository

http_bearer = HTTPBearer(auto_error=False)


@lru_cache
def get_password_hasher() -> PasswordHasher:
    """Provide password hasher configured from application settings."""
    settings = get_application_settings()
    return BcryptPasswordHasher(rounds=settings.bcrypt_rounds)


@lru_cache
def get_token_service() -> TokenService:
    """Provide token service configured from application settings."""
    settings = get_application_settings()
    return JwtTokenService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expiration_minutes=settings.access_token_expire_minutes,
    )


def get_current_user_provider(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    session: Session = Depends(get_database_session),
    token_service: TokenService = Depends(get_token_service),
) -> CurrentUserProvider:
    """Resolve current-user provider from incoming Bearer token."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationRequiredError()

    payload = token_service.verify_token(credentials.credentials)
    user_repo = SqlAlchemyUserRepository(session)
    user = user_repo.get_by_id(payload.user_id)
    if user is None:
        raise InvalidTokenError("User associated with token does not exist.")
    if not user.is_active:
        raise UserInactiveError()

    return AuthenticatedCurrentUserProvider(user)


def get_current_user(
    provider: CurrentUserProvider = Depends(
        get_current_user_provider,
    ),
) -> User:
    """Return the authenticated user for the current request."""
    return provider.get_current_user()


def get_auth_service(
    session: Session = Depends(get_database_session),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
    token_service: TokenService = Depends(get_token_service),
) -> AuthenticationService:
    """Provide AuthenticationService with injected dependencies."""
    user_repo = SqlAlchemyUserRepository(session)
    return AuthenticationService(
        user_repo=user_repo,
        password_hasher=password_hasher,
        token_service=token_service,
    )
