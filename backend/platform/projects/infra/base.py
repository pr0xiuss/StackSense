"""SQLAlchemy declarative base for Project infrastructure."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for Project persistence models."""
