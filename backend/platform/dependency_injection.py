"""StackSense dependency injection foundation."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session

from backend.infra.postgres import Database
from backend.platform.config import Settings, get_settings
from backend.platform.database import DatabaseSettings


@lru_cache
def get_application_settings() -> Settings:
    """Provide application settings through the dependency boundary."""
    return get_settings()


@lru_cache
def get_database_settings() -> DatabaseSettings:
    """Provide database settings through the dependency boundary."""
    return DatabaseSettings()


@lru_cache
def get_database() -> Database:
    """Provide the PostgreSQL database infrastructure."""
    return Database(get_database_settings())


def get_database_session() -> Generator[Session]:
    """Provide a PostgreSQL session for one API request."""
    database = get_database()

    session_generator = database.session()
    session = next(session_generator)

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session_generator.close()
