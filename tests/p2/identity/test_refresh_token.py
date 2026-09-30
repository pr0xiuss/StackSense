"""Tests for refresh token domain, persistence, rotation, and lifecycle."""

import secrets
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.platform.dependency_injection import get_database
from backend.platform.errors import (
    InvalidRefreshTokenError,
    RefreshTokenExpiredError,
    RefreshTokenRevokedError,
    UserInactiveError,
)
from backend.platform.identity.application.auth_service import AuthenticationService
from backend.platform.identity.domain.refresh_token import RefreshToken
from backend.platform.identity.domain.user import User
from backend.platform.identity.infra.password_hasher import BcryptPasswordHasher
from backend.platform.identity.infra.refresh_token_repo import (
    SqlAlchemyRefreshTokenRepository,
)
from backend.platform.identity.infra.token_service import JwtTokenService
from backend.platform.identity.infra.user_repo import SqlAlchemyUserRepository


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
def auth_components(session: Session) -> dict[str, Any]:
    user_repo = SqlAlchemyUserRepository(session)
    refresh_token_repo = SqlAlchemyRefreshTokenRepository(session)
    password_hasher = BcryptPasswordHasher(rounds=4)
    token_service = JwtTokenService(
        secret_key="test-secret-key-at-least-32-bytes-long",
        algorithm="HS256",
        expiration_minutes=15,
        refresh_token_expire_days=7,
    )
    auth_service = AuthenticationService(
        user_repo=user_repo,
        password_hasher=password_hasher,
        token_service=token_service,
        refresh_token_repo=refresh_token_repo,
    )
    return {
        "user_repo": user_repo,
        "refresh_token_repo": refresh_token_repo,
        "token_service": token_service,
        "auth_service": auth_service,
    }


def test_refresh_token_domain_invariants() -> None:
    """Verify RefreshToken active, expired, and revoked state logic."""
    now = datetime.now(UTC)
    future = now + timedelta(days=1)
    past = now - timedelta(days=1)

    active_token = RefreshToken(
        id=uuid4(),
        user_id=uuid4(),
        token_hash="hash1",
        expires_at=future,
        revoked_at=None,
        created_at=now,
    )
    assert active_token.is_active is True
    assert active_token.is_expired is False
    assert active_token.is_revoked is False

    expired_token = RefreshToken(
        id=uuid4(),
        user_id=uuid4(),
        token_hash="hash2",
        expires_at=past,
        revoked_at=None,
        created_at=now - timedelta(days=2),
    )
    assert expired_token.is_active is False
    assert expired_token.is_expired is True
    assert expired_token.is_revoked is False

    revoked_token = RefreshToken(
        id=uuid4(),
        user_id=uuid4(),
        token_hash="hash3",
        expires_at=future,
        revoked_at=now,
        created_at=now,
    )
    assert revoked_token.is_active is False
    assert revoked_token.is_expired is False
    assert revoked_token.is_revoked is True


def test_refresh_token_persistence_lifecycle(
    auth_components: dict[str, Any],
) -> None:
    """Verify repository save, lookup by hash, revoke, and get_active."""
    repo = auth_components["refresh_token_repo"]
    user_repo = auth_components["user_repo"]
    tag = uuid4().hex[:8]
    user_id = uuid4()
    now = datetime.now(UTC)
    user = User(
        id=user_id,
        email=f"repo_lc_{tag}@stacksense.local",
        username=f"repo_lc_{tag}",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user_repo.save(user)

    token_id = uuid4()
    token_hash = f"sample_sha256_hash_{tag}"

    token = RefreshToken(
        id=token_id,
        user_id=user_id,
        token_hash=token_hash,
        expires_at=now + timedelta(days=5),
        revoked_at=None,
        created_at=now,
    )
    saved = repo.save(token)
    assert saved.id == token_id

    # Lookup by hash
    fetched = repo.get_by_token_hash(token_hash)
    assert fetched is not None
    assert fetched.id == token_id
    assert fetched.user_id == user_id
    assert fetched.is_active is True

    # Lookup non-existent
    assert repo.get_by_token_hash("non_existent_hash") is None

    # Revoke with replacement token
    new_token_id = uuid4()
    new_token = RefreshToken(
        id=new_token_id,
        user_id=user_id,
        token_hash=f"replacement_hash_{tag}",
        expires_at=now + timedelta(days=5),
        revoked_at=None,
        created_at=now,
    )
    repo.save(new_token)
    repo.revoke(token_id, replaced_by_token_id=new_token_id)
    revoked = repo.get_by_token_hash(token_hash)
    assert revoked is not None
    assert revoked.is_revoked is True
    assert revoked.replaced_by_token_id == new_token_id


def test_login_issues_access_and_refresh_tokens(
    auth_components: dict[str, Any],
) -> None:
    """Authenticate returns both valid access and refresh tokens."""
    auth_service = auth_components["auth_service"]
    tag = uuid4().hex[:8]
    username = f"user_{tag}"
    email = f"user_{tag}@stacksense.local"
    user = auth_service.register(
        email=email,
        username=username,
        password="ValidPassword123!",
    )
    assert user.username == username

    # Login with username
    auth_resp = auth_service.authenticate(username, "ValidPassword123!")
    assert auth_resp.access_token is not None
    assert auth_resp.refresh_token is not None
    assert auth_resp.expires_in == 15 * 60
    assert auth_resp.refresh_expires_in == 7 * 86400

    # Login with email
    auth_resp_email = auth_service.authenticate(email, "ValidPassword123!")
    assert auth_resp_email.access_token is not None
    assert auth_resp_email.refresh_token is not None


def test_refresh_token_rotation_flow(
    auth_components: dict[str, Any],
) -> None:
    """Refreshing an active token rotates it: old is revoked, new is issued."""
    auth_service = auth_components["auth_service"]
    token_service = auth_components["token_service"]
    repo = auth_components["refresh_token_repo"]
    tag = uuid4().hex[:8]
    username = f"rot_{tag}"
    email = f"rot_{tag}@stacksense.local"

    auth_service.register(
        email=email,
        username=username,
        password="ValidPassword123!",
    )
    login_resp = auth_service.authenticate(username, "ValidPassword123!")
    original_refresh = login_resp.refresh_token

    # Perform rotation
    rotated_resp = auth_service.refresh_access_token(original_refresh)
    assert rotated_resp.access_token is not None
    assert rotated_resp.refresh_token != original_refresh

    # Verify new access token is valid
    payload = token_service.verify_token(rotated_resp.access_token)
    assert payload.email == email

    # Old refresh token is now revoked
    old_hash = token_service.hash_refresh_token(original_refresh)
    old_record = repo.get_by_token_hash(old_hash)
    assert old_record is not None
    assert old_record.is_revoked is True
    assert old_record.replaced_by_token_id is not None

    # Attempting to use the old refresh token raises RefreshTokenRevokedError
    with pytest.raises(RefreshTokenRevokedError):
        auth_service.refresh_access_token(original_refresh)

    # New refresh token works for subsequent rotation
    second_rotated = auth_service.refresh_access_token(rotated_resp.refresh_token)
    assert second_rotated.refresh_token != rotated_resp.refresh_token


def test_refresh_with_expired_token_raises(
    auth_components: dict[str, Any],
) -> None:
    """Expired refresh token raises RefreshTokenExpiredError."""
    auth_service = auth_components["auth_service"]
    token_service = auth_components["token_service"]
    repo = auth_components["refresh_token_repo"]
    tag = uuid4().hex[:8]

    user = auth_service.register(
        email=f"exp_{tag}@stacksense.local",
        username=f"exp_{tag}",
        password="ValidPassword123!",
    )
    raw_token, token_hash, _ = token_service.create_refresh_token(user)

    # Manually save as expired in the past
    past_expiry = datetime.now(UTC) - timedelta(hours=1)
    expired_record = RefreshToken(
        id=uuid4(),
        user_id=user.id,
        token_hash=token_hash,
        expires_at=past_expiry,
        revoked_at=None,
        created_at=datetime.now(UTC) - timedelta(days=8),
    )
    repo.save(expired_record)

    with pytest.raises(RefreshTokenExpiredError):
        auth_service.refresh_access_token(raw_token)


def test_refresh_with_invalid_token_raises(
    auth_components: dict[str, Any],
) -> None:
    """Unknown or tampered refresh token raises InvalidRefreshTokenError."""
    auth_service = auth_components["auth_service"]
    with pytest.raises(InvalidRefreshTokenError):
        auth_service.refresh_access_token("completely_fabricated_token_value")


def test_logout_revokes_refresh_token(
    auth_components: dict[str, Any],
) -> None:
    """Logging out revokes the refresh token so subsequent refresh fails."""
    auth_service = auth_components["auth_service"]
    tag = uuid4().hex[:8]
    username = f"logout_{tag}"

    auth_service.register(
        email=f"logout_{tag}@stacksense.local",
        username=username,
        password="ValidPassword123!",
    )
    login_resp = auth_service.authenticate(username, "ValidPassword123!")

    # Revoke via logout
    auth_service.revoke_refresh_token(login_resp.refresh_token)

    # Refresh must now fail with RefreshTokenRevokedError
    with pytest.raises(RefreshTokenRevokedError):
        auth_service.refresh_access_token(login_resp.refresh_token)


def test_inactive_user_cannot_refresh(
    auth_components: dict[str, Any],
) -> None:
    """Deactivated user account cannot refresh tokens."""
    auth_service = auth_components["auth_service"]
    user_repo = auth_components["user_repo"]
    tag = uuid4().hex[:8]
    username = f"deact_{tag}"

    user = auth_service.register(
        email=f"deact_{tag}@stacksense.local",
        username=username,
        password="ValidPassword123!",
    )
    login_resp = auth_service.authenticate(username, "ValidPassword123!")

    # Deactivate user
    user_repo.update(
        User(
            id=user.id,
            email=user.email,
            username=user.username,
            is_active=False,
            created_at=user.created_at,
            updated_at=datetime.now(UTC),
        )
    )

    with pytest.raises(UserInactiveError):
        auth_service.refresh_access_token(login_resp.refresh_token)


def test_concurrent_sessions_multiple_refresh_tokens(
    auth_components: dict[str, Any],
) -> None:
    """Multiple concurrent logins generate independent active refresh tokens."""
    auth_service = auth_components["auth_service"]
    repo = auth_components["refresh_token_repo"]
    tag = uuid4().hex[:8]
    username = f"multi_{tag}"

    user = auth_service.register(
        email=f"multi_{tag}@stacksense.local",
        username=username,
        password="ValidPassword123!",
    )

    login_1 = auth_service.authenticate(username, "ValidPassword123!")
    login_2 = auth_service.authenticate(username, "ValidPassword123!")

    assert login_1.refresh_token != login_2.refresh_token

    active_tokens = repo.get_active_for_user(user.id)
    assert len(active_tokens) == 2

    # Rotate session 1
    rotated_1 = auth_service.refresh_access_token(login_1.refresh_token)
    assert rotated_1.refresh_token != login_1.refresh_token

    # Session 2 still works independently
    rotated_2 = auth_service.refresh_access_token(login_2.refresh_token)
    assert rotated_2.refresh_token != login_2.refresh_token


def test_refresh_token_legacy_sha256_backward_compatibility(
    auth_components: dict[str, Any],
) -> None:
    """Legacy tokens hashed with plain SHA-256 can be refreshed to HMAC-SHA256."""
    auth_service = auth_components["auth_service"]
    token_service = auth_components["token_service"]
    repo = auth_components["refresh_token_repo"]
    tag = uuid4().hex[:8]
    username = f"leg_{tag}"
    email = f"leg_{tag}@stacksense.local"

    user = auth_service.register(
        email=email,
        username=username,
        password="ValidPassword123!",
    )
    raw_legacy_token = secrets.token_urlsafe(32)
    legacy_hash = token_service.legacy_hash_refresh_token(raw_legacy_token)
    legacy_record = RefreshToken(
        id=uuid4(),
        user_id=user.id,
        token_hash=legacy_hash,
        expires_at=datetime.now(UTC) + timedelta(days=7),
        revoked_at=None,
        created_at=datetime.now(UTC),
    )
    repo.save(legacy_record)

    # Refresh the legacy token
    rotated_resp = auth_service.refresh_access_token(raw_legacy_token)
    assert rotated_resp.access_token is not None
    assert rotated_resp.refresh_token is not None
    assert rotated_resp.refresh_token != raw_legacy_token

    # Verify old legacy token was revoked
    old_record = repo.get_by_token_hash(legacy_hash)
    assert old_record is not None
    assert old_record.is_revoked is True

    # Verify the new token is stored using HMAC-SHA256
    new_hmac_hash = token_service.hash_refresh_token(rotated_resp.refresh_token)
    new_record = repo.get_by_token_hash(new_hmac_hash)
    assert new_record is not None
    assert new_record.is_active is True


def test_revoke_legacy_sha256_refresh_token(
    auth_components: dict[str, Any],
) -> None:
    """Legacy tokens hashed with plain SHA-256 can be revoked on logout."""
    auth_service = auth_components["auth_service"]
    token_service = auth_components["token_service"]
    repo = auth_components["refresh_token_repo"]
    tag = uuid4().hex[:8]
    username = f"revleg_{tag}"
    email = f"revleg_{tag}@stacksense.local"

    user = auth_service.register(
        email=email,
        username=username,
        password="ValidPassword123!",
    )
    raw_legacy_token = secrets.token_urlsafe(32)
    legacy_hash = token_service.legacy_hash_refresh_token(raw_legacy_token)
    legacy_record = RefreshToken(
        id=uuid4(),
        user_id=user.id,
        token_hash=legacy_hash,
        expires_at=datetime.now(UTC) + timedelta(days=7),
        revoked_at=None,
        created_at=datetime.now(UTC),
    )
    repo.save(legacy_record)

    # Revoke legacy token
    auth_service.revoke_refresh_token(raw_legacy_token)
    revoked_record = repo.get_by_token_hash(legacy_hash)
    assert revoked_record is not None
    assert revoked_record.is_revoked is True
