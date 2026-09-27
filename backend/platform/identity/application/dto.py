"""Data Transfer Objects for Identity and Authentication."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class RegisterRequest(BaseModel):
    """Request payload for user registration."""

    model_config = ConfigDict(extra="forbid")

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("Email cannot be empty.")
        return cleaned


class LoginRequest(BaseModel):
    """Request payload for user authentication."""

    model_config = ConfigDict(extra="forbid")

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("Email cannot be empty.")
        return cleaned


class AuthTokenResponse(BaseModel):
    """Response payload containing issued access token."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """Public representation of a user identity."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    email: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
