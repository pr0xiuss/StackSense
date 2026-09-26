"""SQLAlchemy persistence models for Identity and Credentials."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.platform.projects.infra.base import Base


class UserModel(Base):
    """Persisted User entity."""

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email_lower", func.lower(text("email")), unique=True),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    credential: Mapped[UserCredentialModel | None] = relationship(
        "UserCredentialModel",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class UserCredentialModel(Base):
    """Persisted user credential record."""

    __tablename__ = "user_credentials"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    user: Mapped[UserModel] = relationship(
        UserModel,
        back_populates="credential",
    )
