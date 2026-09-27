"""Bcrypt password hashing infrastructure."""

from __future__ import annotations

import bcrypt

from backend.platform.errors import PasswordPolicyError
from backend.platform.identity.application.password import PasswordHasher

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


class BcryptPasswordHasher(PasswordHasher):
    """Bcrypt implementation of PasswordHasher."""

    def __init__(self, rounds: int = 12) -> None:
        self._rounds = rounds

    def hash(self, password: str) -> str:
        """Hash a plaintext password with bcrypt after validating policy."""
        self.validate(password)
        pw_bytes = password.encode("utf-8")[:72]
        salt = bcrypt.gensalt(rounds=self._rounds)
        return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")

    def verify(self, password: str, password_hash: str) -> bool:
        """Verify a plaintext password against a stored bcrypt hash."""
        if not password or not password_hash:
            return False
        try:
            pw_bytes = password.encode("utf-8")[:72]
            hash_bytes = password_hash.encode("utf-8")
            return bcrypt.checkpw(pw_bytes, hash_bytes)
        except Exception:
            return False

    def validate(self, password: str) -> None:
        """Validate password against length policy requirements."""
        if (
            not password
            or len(password) < MIN_PASSWORD_LENGTH
            or len(password) > MAX_PASSWORD_LENGTH
        ):
            raise PasswordPolicyError(
                f"Password must be between {MIN_PASSWORD_LENGTH} and "
                f"{MAX_PASSWORD_LENGTH} characters long."
            )
