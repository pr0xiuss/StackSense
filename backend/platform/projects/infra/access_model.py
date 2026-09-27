"""SQLAlchemy model for project access."""

from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.platform.projects.domain.project_role import ProjectRole
from backend.platform.projects.infra.base import Base


class ProjectAccessModel(Base):
    """Persisted project access record."""

    __tablename__ = "project_access"

    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )

    role: Mapped[ProjectRole] = mapped_column(
        Enum(
            ProjectRole,
            name="project_role",
        ),
        nullable=False,
    )
