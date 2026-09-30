"""Tests for AuthenticationService application service."""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy.orm import Session

from backend.platform.dependency_injection import get_database
from backend.platform.errors import (
    InvalidCredentialsError,
    InvalidTokenError,
    UserInactiveError,
)
from backend.platform.identity.application.auth_service import AuthenticationService
from backend.platform.identity.domain.credential import UserCredential
from backend.platform.identity.domain.user import User
from backend.platform.identity.infra.password_hasher import BcryptPasswordHasher
from backend.platform.identity.infra.refresh_token_repo import (
    SqlAlchemyRefreshTokenRepository,
)
from backend.platform.identity.infra.token_service import JwtTokenService
from backend.platform.identity.infra.user_repo import SqlAlchemyUserRepository

TEST_SECRET = SecretStr("stacksense-auth-service-test-secret-at-least-32-bytes-long")


@pytest.fixture
def session() -> Generator[Session]:
    database = get_database()
    gen = database.session()
    sess = next(gen)
    try:
        yield sess
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        gen.close()


@pytest.fixture
def auth_service(session: Session) -> AuthenticationService:
    repo = SqlAlchemyUserRepository(session)
    refresh_repo = SqlAlchemyRefreshTokenRepository(session)
    hasher = BcryptPasswordHasher(rounds=4)
    token_svc = JwtTokenService(
        secret_key=TEST_SECRET,
        algorithm="HS256",
        expiration_minutes=60,
    )
    return AuthenticationService(
        user_repo=repo,
        password_hasher=hasher,
        token_service=token_svc,
        refresh_token_repo=refresh_repo,
    )


def test_authenticate_success(
    session: Session, auth_service: AuthenticationService
) -> None:
    repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher(rounds=4)
    user_id = uuid4()
    tag = uuid4().hex[:8]
    email = f"auth-user-{tag}@stacksense.local"
    username = f"auth_user_{tag}"
    password = "CorrectPassword123"
    now = datetime.now(UTC)

    user = User(
        id=user_id,
        email=email,
        username=username,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    cred = UserCredential(
        user_id=user_id,
        password_hash=hasher.hash(password),
        created_at=now,
        updated_at=now,
    )
    repo.save(user, credential=cred)

    response = auth_service.authenticate(email, password)

    assert response.access_token is not None
    assert response.refresh_token is not None
    assert response.token_type == "bearer"
    assert response.expires_in == 3600

    # Verify payload matches user
    payload = auth_service.verify_token(response.access_token)
    assert payload.user_id == user_id
    assert payload.email == email

    # Also authenticate using username
    resp_by_username = auth_service.authenticate(username, password)
    assert resp_by_username.access_token is not None


def test_authenticate_email_case_and_whitespace_insensitivity(
    session: Session, auth_service: AuthenticationService
) -> None:
    repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher(rounds=4)
    user_id = uuid4()
    tag = uuid4().hex[:8]
    email = f"caseuser-{tag}@stacksense.local"
    username = f"case_user_{tag}"
    password = "CorrectPassword123"
    now = datetime.now(UTC)

    user = User(
        id=user_id,
        email=email,
        username=username,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    cred = UserCredential(
        user_id=user_id,
        password_hash=hasher.hash(password),
        created_at=now,
        updated_at=now,
    )
    repo.save(user, credential=cred)

    # Login with uppercase email and surrounding whitespace
    login_email = f"   CASEUSER-{tag.upper()}@STACKSENSE.LOCAL   "
    response = auth_service.authenticate(login_email, password)

    assert response.access_token is not None
    payload = auth_service.verify_token(response.access_token)
    assert payload.user_id == user_id


def test_authenticate_wrong_password_raises(
    session: Session, auth_service: AuthenticationService
) -> None:
    repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher(rounds=4)
    user_id = uuid4()
    tag = uuid4().hex[:8]
    email = f"wrongpw-{tag}@stacksense.local"
    username = f"wrongpw_{tag}"
    now = datetime.now(UTC)

    user = User(
        id=user_id,
        email=email,
        username=username,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    cred = UserCredential(
        user_id=user_id,
        password_hash=hasher.hash("RightPassword123"),
        created_at=now,
        updated_at=now,
    )
    repo.save(user, credential=cred)

    with pytest.raises(InvalidCredentialsError):
        auth_service.authenticate(email, "WrongPassword999")


def test_authenticate_nonexistent_email_raises(
    auth_service: AuthenticationService,
) -> None:
    with pytest.raises(InvalidCredentialsError):
        auth_service.authenticate(
            f"nobody-{uuid4().hex[:8]}@stacksense.local", "SomePassword123"
        )


def test_authenticate_inactive_user_raises(
    session: Session, auth_service: AuthenticationService
) -> None:
    repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher(rounds=4)
    user_id = uuid4()
    tag = uuid4().hex[:8]
    email = f"inactive-{tag}@stacksense.local"
    username = f"inactive_{tag}"
    password = "CorrectPassword123"
    now = datetime.now(UTC)

    user = User(
        id=user_id,
        email=email,
        username=username,
        is_active=False,
        created_at=now,
        updated_at=now,
    )
    cred = UserCredential(
        user_id=user_id,
        password_hash=hasher.hash(password),
        created_at=now,
        updated_at=now,
    )
    repo.save(user, credential=cred)

    with pytest.raises(UserInactiveError):
        auth_service.authenticate(email, password)


def test_authenticate_missing_credential_raises(
    session: Session, auth_service: AuthenticationService
) -> None:
    repo = SqlAlchemyUserRepository(session)
    user_id = uuid4()
    tag = uuid4().hex[:8]
    email = f"nocred-{tag}@stacksense.local"
    username = f"nocred_{tag}"
    now = datetime.now(UTC)

    user = User(
        id=user_id,
        email=email,
        username=username,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    # Save user without credential
    repo.save(user)

    with pytest.raises(InvalidCredentialsError):
        auth_service.authenticate(email, "SomePassword123")


def test_get_user_from_token_success(
    session: Session, auth_service: AuthenticationService
) -> None:
    repo = SqlAlchemyUserRepository(session)
    user_id = uuid4()
    tag = uuid4().hex[:8]
    email = f"tokenresolve-{tag}@stacksense.local"
    username = f"tokenres_{tag}"
    now = datetime.now(UTC)

    user = User(
        id=user_id,
        email=email,
        username=username,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    repo.save(user)

    token_svc = JwtTokenService(
        secret_key=TEST_SECRET,
        algorithm="HS256",
        expiration_minutes=60,
    )
    token = token_svc.create_access_token(user)

    resolved_user = auth_service.get_user_from_token(token)
    assert resolved_user.id == user_id
    assert resolved_user.email == email
    assert resolved_user.username == username


def test_get_user_from_token_user_not_in_db_raises(
    auth_service: AuthenticationService,
) -> None:
    # Issue a valid token for a user ID that does not exist in DB
    ghost_user = User(id=uuid4(), email="ghost@stacksense.local", username="ghost_user")
    token_svc = JwtTokenService(
        secret_key=TEST_SECRET,
        algorithm="HS256",
        expiration_minutes=60,
    )
    token = token_svc.create_access_token(ghost_user)

    with pytest.raises(InvalidTokenError, match="does not exist"):
        auth_service.get_user_from_token(token)


def test_get_user_from_token_inactive_user_raises(
    session: Session, auth_service: AuthenticationService
) -> None:
    repo = SqlAlchemyUserRepository(session)
    user_id = uuid4()
    tag = uuid4().hex[:8]
    email = f"deactivated-{tag}@stacksense.local"
    username = f"deact_{tag}"
    now = datetime.now(UTC)

    user = User(
        id=user_id,
        email=email,
        username=username,
        is_active=False,
        created_at=now,
        updated_at=now,
    )
    repo.save(user)

    token_svc = JwtTokenService(
        secret_key=TEST_SECRET,
        algorithm="HS256",
        expiration_minutes=60,
    )
    token = token_svc.create_access_token(user)

    with pytest.raises(UserInactiveError):
        auth_service.get_user_from_token(token)
