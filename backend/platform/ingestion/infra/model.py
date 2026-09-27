"""SQLAlchemy persistence models for Ingestion, Revision, and Artifact."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.platform.projects.infra.base import Base


class IngestionModel(Base):
    """Persisted Ingestion operation record."""

    __tablename__ = "ingestions"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    source_reference: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "uq_ingestions_active_repo",
            "repository_id",
            unique=True,
            postgresql_where=(status == "processing"),
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_ingestions_status",
        ),
    )


class RevisionModel(Base):
    """Persisted RepositoryRevision record."""

    __tablename__ = "repository_revisions"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ingestion_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("ingestions.id", ondelete="SET NULL"),
        nullable=True,
    )
    revision_identifier: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    source_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    total_files: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    total_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "revision_identifier",
            name="uq_repository_revisions_repo_rev",
        ),
    )


class ArtifactModel(Base):
    """Persisted RepositoryArtifact record."""

    __tablename__ = "repository_artifacts"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("repository_revisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path: Mapped[str] = mapped_column(
        String(4096),
        nullable=False,
    )
    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    support_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(
        String(4096),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "revision_id",
            "path",
            name="uq_repository_artifacts_rev_path",
        ),
    )
