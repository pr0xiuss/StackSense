"""Unit tests for Identity domain models (User and UserCredential)."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.platform.identity.domain.credential import UserCredential
from backend.platform.identity.domain.user import User


def test_user_domain_creation_with_defaults() -> None:
    user_id = uuid4()
    user = User(id=user_id, email="alice@stacksense.local")

    assert user.id == user_id
    assert user.email == "alice@stacksense.local"
    assert user.is_active is True
    assert user.created_at is None
    assert user.updated_at is None


def test_user_domain_empty_or_whitespace_email_raises() -> None:
    user_id = uuid4()
    with pytest.raises(ValueError, match="User email cannot be empty."):
        User(id=user_id, email="")

    with pytest.raises(ValueError, match="User email cannot be empty."):
        User(id=user_id, email="   ")


def test_user_domain_creation_with_all_fields() -> None:
    user_id = uuid4()
    now = datetime.now(UTC)
    user = User(
        id=user_id,
        email="developer@stacksense.local",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    assert user.id == user_id
    assert user.email == "developer@stacksense.local"
    assert user.is_active is True
    assert user.created_at == now
    assert user.updated_at == now


def test_user_domain_immutability() -> None:
    user = User(id=uuid4(), email="test@stacksense.local")

    with pytest.raises(FrozenInstanceError):
        user.email = "changed@stacksense.local"  # type: ignore[misc]


def test_user_credential_domain_creation() -> None:
    user_id = uuid4()
    now = datetime.now(UTC)
    credential = UserCredential(
        user_id=user_id,
        password_hash="$2b$12$eX4mpL3h4shV4lu3f0rt3st1ng0nly",
        created_at=now,
        updated_at=now,
    )

    assert credential.user_id == user_id
    assert credential.password_hash == "$2b$12$eX4mpL3h4shV4lu3f0rt3st1ng0nly"
    assert credential.created_at == now
    assert credential.updated_at == now


def test_user_credential_domain_immutability() -> None:
    credential = UserCredential(
        user_id=uuid4(),
        password_hash="hashed_pw",
    )

    with pytest.raises(FrozenInstanceError):
        credential.password_hash = "new_hash"  # type: ignore[misc]
