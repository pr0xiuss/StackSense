"""Unit tests for BcryptPasswordHasher."""

import pytest

from backend.platform.errors import PasswordPolicyError
from backend.platform.identity.infra.password_hasher import BcryptPasswordHasher


@pytest.fixture
def hasher() -> BcryptPasswordHasher:
    # Use rounds=4 for fast test execution
    return BcryptPasswordHasher(rounds=4)


def test_hash_creates_valid_bcrypt_format(hasher: BcryptPasswordHasher) -> None:
    hashed = hasher.hash("securePassword123")
    assert hashed.startswith("$2b$")
    assert len(hashed) == 60


def test_verify_correct_password(hasher: BcryptPasswordHasher) -> None:
    password = "correct_horse_battery"
    hashed = hasher.hash(password)

    assert hasher.verify(password, hashed) is True


def test_verify_wrong_password(hasher: BcryptPasswordHasher) -> None:
    hashed = hasher.hash("validPassword123")
    assert hasher.verify("wrongPassword123", hashed) is False


def test_verify_empty_or_none_returns_false(hasher: BcryptPasswordHasher) -> None:
    hashed = hasher.hash("validPassword123")
    assert hasher.verify("", hashed) is False
    assert hasher.verify("validPassword123", "") is False


def test_verify_malformed_hash_returns_false_safely(
    hasher: BcryptPasswordHasher,
) -> None:
    assert hasher.verify("validPassword123", "not_a_valid_hash") is False
    assert (
        hasher.verify("validPassword123", "$2b$04$invalidhashthatisnotvalid") is False
    )


def test_password_policy_minimum_length(hasher: BcryptPasswordHasher) -> None:
    # 7 characters — too short
    with pytest.raises(PasswordPolicyError, match="between 8 and 128"):
        hasher.hash("1234567")

    # 8 characters — boundary pass
    hashed = hasher.hash("12345678")
    assert hasher.verify("12345678", hashed) is True


def test_password_policy_maximum_length(hasher: BcryptPasswordHasher) -> None:
    # 128 characters — boundary pass
    password_128 = "a" * 128
    hashed = hasher.hash(password_128)
    assert hasher.verify(password_128, hashed) is True

    # 129 characters — too long
    with pytest.raises(PasswordPolicyError, match="between 8 and 128"):
        hasher.hash("a" * 129)


def test_password_policy_empty_string(hasher: BcryptPasswordHasher) -> None:
    with pytest.raises(PasswordPolicyError, match="between 8 and 128"):
        hasher.hash("")


def test_hasher_rounds_configuration() -> None:
    hasher_4 = BcryptPasswordHasher(rounds=4)
    hashed_4 = hasher_4.hash("testPassword123")
    assert hashed_4.startswith("$2b$04$")

    hasher_5 = BcryptPasswordHasher(rounds=5)
    hashed_5 = hasher_5.hash("testPassword123")
    assert hashed_5.startswith("$2b$05$")
