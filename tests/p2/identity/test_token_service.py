"""Unit tests for JwtTokenService."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from pydantic import SecretStr

from backend.platform.errors import InvalidTokenError, TokenExpiredError
from backend.platform.identity.domain.user import User
from backend.platform.identity.infra.token_service import JwtTokenService

TEST_SECRET = SecretStr(
    "stacksense-test-secret-key-that-is-at-least-32-bytes-long-for-hmac-sha256"
)


@pytest.fixture
def token_service() -> JwtTokenService:
    return JwtTokenService(
        secret_key=TEST_SECRET,
        algorithm="HS256",
        expiration_minutes=60,
        refresh_token_expire_days=30,
    )


def test_create_and_verify_token_success(token_service: JwtTokenService) -> None:
    user_id = uuid4()
    now = datetime.now(UTC)
    user = User(
        id=user_id,
        email="tokenuser@stacksense.local",
        username="tokenuser",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    token = token_service.create_access_token(user)
    assert isinstance(token, str)

    payload = token_service.verify_token(token)
    assert payload.user_id == user_id
    assert payload.email == "tokenuser@stacksense.local"
    assert payload.token_id is not None
    assert payload.issued_at <= datetime.now(UTC)
    assert payload.expires_at > payload.issued_at
    assert payload.token_type == "access"


def test_verify_expired_token_raises(token_service: JwtTokenService) -> None:
    # Service with negative expiration to issue an already expired token
    expired_service = JwtTokenService(
        secret_key=TEST_SECRET,
        algorithm="HS256",
        expiration_minutes=-5,
    )
    user = User(id=uuid4(), email="expired@stacksense.local", username="expired_user")
    token = expired_service.create_access_token(user)

    with pytest.raises(TokenExpiredError):
        token_service.verify_token(token)


def test_verify_tampered_token_signature_raises(
    token_service: JwtTokenService,
) -> None:
    user = User(id=uuid4(), email="valid@stacksense.local", username="valid_user")
    token = token_service.create_access_token(user)

    # Tamper with the signature portion (last part of JWT)
    parts = token.split(".")
    tampered_sig = "X" + parts[2][1:] if parts[2][0] != "X" else "Y" + parts[2][1:]
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"

    with pytest.raises(InvalidTokenError):
        token_service.verify_token(tampered_token)


def test_verify_token_signed_with_different_secret_raises(
    token_service: JwtTokenService,
) -> None:
    other_service = JwtTokenService(
        secret_key=SecretStr(
            "completely-different-secret-key-that-is-at-least-32-bytes-long"
        ),
        algorithm="HS256",
        expiration_minutes=60,
    )
    user = User(id=uuid4(), email="valid@stacksense.local", username="valid_user")
    token = other_service.create_access_token(user)

    with pytest.raises(InvalidTokenError):
        token_service.verify_token(token)


def test_verify_token_with_malformed_string_raises(
    token_service: JwtTokenService,
) -> None:
    with pytest.raises(InvalidTokenError):
        token_service.verify_token("not.a.valid.jwt")


def test_verify_token_with_invalid_uuid_subject_raises(
    token_service: JwtTokenService,
) -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": "not-a-valid-uuid",
        "email": "badsub@stacksense.local",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=60)).timestamp()),
        "jti": str(uuid4()),
        "token_type": "access",
    }
    token = jwt.encode(payload, TEST_SECRET.get_secret_value(), algorithm="HS256")

    with pytest.raises(InvalidTokenError, match="not a valid UUID"):
        token_service.verify_token(token)


def test_token_service_refresh_token_generation_and_hashing(
    token_service: JwtTokenService,
) -> None:
    user = User(
        id=uuid4(), email="refresh_user@stacksense.local", username="refresh_user"
    )
    raw_token, token_hash, expires_at = token_service.create_refresh_token(user)

    assert isinstance(raw_token, str)
    assert len(raw_token) > 20
    assert token_hash == token_service.hash_refresh_token(raw_token)
    assert expires_at > datetime.now(UTC)
    assert token_service.refresh_expiration_seconds == 30 * 86400

    # Keyed HMAC-SHA256 must be distinct from unkeyed SHA-256
    legacy_hash = token_service.legacy_hash_refresh_token(raw_token)
    assert token_hash != legacy_hash

    # A different secret key must yield a different HMAC hash for the same token
    alt_service = JwtTokenService(
        secret_key=SecretStr("an-alternative-secret-key-at-least-32-bytes"),
        algorithm="HS256",
    )
    assert alt_service.hash_refresh_token(raw_token) != token_hash
    # But legacy unkeyed hash is identical across services
    assert alt_service.legacy_hash_refresh_token(raw_token) == legacy_hash
