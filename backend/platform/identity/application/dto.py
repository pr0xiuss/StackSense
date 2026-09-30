"""Data Transfer Objects for Identity and Authentication."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from backend.platform.identity.domain.constants import USERNAME_PATTERN


class RegisterRequest(BaseModel):
    """Request payload for user registration."""

    model_config = ConfigDict(extra="forbid")

    email: str
    username: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("Email cannot be empty.")
        return cleaned

    @field_validator("username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("Username cannot be empty.")
        if not USERNAME_PATTERN.match(cleaned):
            raise ValueError(
                "Username must be between 3 and 30 characters and contain "
                "only letters, numbers, and underscores."
            )
        return cleaned


class LoginRequest(BaseModel):
    """Request payload for user authentication."""

    model_config = ConfigDict(extra="forbid")

    identifier: str
    password: str

    @field_validator("identifier")
    @classmethod
    def normalize_identifier(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("Identifier cannot be empty.")
        return cleaned


class AuthTokenResponse(BaseModel):
    """Response payload containing issued access and refresh tokens."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int


class RefreshTokenRequest(BaseModel):
    """Request payload to rotate an active refresh token."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str

    @field_validator("refresh_token")
    @classmethod
    def validate_refresh_token(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Refresh token cannot be empty.")
        return cleaned


class RefreshTokenResponse(AuthTokenResponse):
    """Response payload containing rotated token pair."""

    pass


class UserResponse(BaseModel):
    """Public representation of a user identity."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    email: str
    username: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
