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
    )


def test_create_and_verify_token_success(token_service: JwtTokenService) -> None:
    user_id = uuid4()
    now = datetime.now(UTC)
    user = User(
        id=user_id,
        email="tokenuser@stacksense.local",
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


def test_verify_expired_token_raises(token_service: JwtTokenService) -> None:
    # Service with negative expiration to issue an already expired token
    expired_service = JwtTokenService(
        secret_key=TEST_SECRET,
        algorithm="HS256",
        expiration_minutes=-5,
    )
    user = User(id=uuid4(), email="expired@stacksense.local")
    token = expired_service.create_access_token(user)

    with pytest.raises(TokenExpiredError):
        token_service.verify_token(token)


def test_verify_tampered_token_signature_raises(
    token_service: JwtTokenService,
) -> None:
    user = User(id=uuid4(), email="valid@stacksense.local")
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
    user = User(id=uuid4(), email="valid@stacksense.local")
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
    }
    token = jwt.encode(payload, TEST_SECRET.get_secret_value(), algorithm="HS256")

    with pytest.raises(InvalidTokenError, match="not a valid UUID"):
        token_service.verify_token(token)


def test_token_service_expiration_seconds_property(
    token_service: JwtTokenService,
) -> None:
    assert token_service.expiration_seconds == 3600
