"""Data Transfer Objects for the Repository application layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RegisterRepositoryRequest(BaseModel):
    """Input contract for registering a new repository within a project."""

    name: str = Field(
        min_length=1,
        max_length=255,
        description="Repository name, unique within the owning project.",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional human-readable description.",
    )


class UpdateRepositoryRequest(BaseModel):
    """Input contract for updating repository metadata."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="New repository name.",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="New repository description.",
    )


class RepositoryResponse(BaseModel):
    """Output contract for Repository application and API operations."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime
