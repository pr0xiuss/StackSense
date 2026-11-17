"""SQLAlchemy models and table definitions for Phase 5 Module 2 search metadata.

Implements durable PostgreSQL metadata for search resources, candidate generations,
enlisted publication receipts, and point-in-time reader pins per §7.4, §7.10, and §7.12.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.platform.projects.infra.base import Base


class SearchResourceModel(Base):
    """PostgreSQL anchor for a project's architecture version search index."""

    __tablename__ = "search_resources"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    architecture_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    active_generation_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    active_index_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active_index_uuid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "architecture_version_id",
            name="uq_search_resource_scope",
        ),
        Index("ix_search_resource_lookup", "project_id", "architecture_version_id"),
    )


class SearchGenerationModel(Base):
    """Immutable candidate or active index generation record."""

    __tablename__ = "search_generations"

    generation_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(
        ForeignKey("search_resources.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    architecture_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    candidate_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    attempt_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    artifact_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    index_name: Mapped[str] = mapped_column(String(255), nullable=False)
    index_uuid: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    counts_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    key_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    projection_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    sealed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("candidate_id", name="uq_search_generation_candidate"),
        CheckConstraint(
            "state IN ('PREPARING', 'SEALED', 'ACTIVE', 'HISTORICAL', "
            "'FAILED', 'CLEANUP_MARKED')",
            name="ck_search_generation_state",
        ),
        Index("ix_search_generation_scope", "project_id", "architecture_version_id"),
        Index("ix_search_generation_attempt", "attempt_id"),
    )


class SearchPublicationReceiptModel(Base):
    """Enlisted transaction record proving atomic M1 search acceptance."""

    __tablename__ = "search_publication_receipts"

    receipt_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    generation_id: Mapped[UUID] = mapped_column(
        ForeignKey("search_generations.generation_id", ondelete="RESTRICT"),
        nullable=False,
    )
    attempt_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    candidate_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    artifact_reference: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("attempt_id", name="uq_search_receipt_attempt"),
        UniqueConstraint("candidate_id", name="uq_search_receipt_candidate"),
    )


class SearchReadPinModel(Base):
    """Active reader pin preventing cleanup while queries or PITs execute."""

    __tablename__ = "search_read_pins"

    pin_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    generation_id: Mapped[UUID] = mapped_column(
        ForeignKey("search_generations.generation_id", ondelete="CASCADE"),
        nullable=False,
    )
    pit_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pinned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        Index("ix_search_read_pin_expiry", "generation_id", "expires_at"),
    )


SEARCH_TABLES = (
    SearchResourceModel.__table__,
    SearchGenerationModel.__table__,
    SearchPublicationReceiptModel.__table__,
    SearchReadPinModel.__table__,
)

__all__ = [
    "SEARCH_TABLES",
    "SearchGenerationModel",
    "SearchPublicationReceiptModel",
    "SearchReadPinModel",
    "SearchResourceModel",
]
