"""PostgreSQL database infrastructure."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.platform.database import DatabaseSettings


class Database:
    """Manage the application's PostgreSQL database connection."""

    def __init__(self, settings: DatabaseSettings) -> None:
        self._engine = create_engine(
            settings.database_url.get_secret_value().replace(
                "postgresql://",
                "postgresql+psycopg://",
                1,
            ),
            pool_pre_ping=True,
        )

        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
        )

    def session(self) -> Generator[Session]:
        """Provide a database session for one unit of work."""
        session = self._session_factory()

        try:
            yield session
        finally:
            session.close()

    def dispose(self) -> None:
        """Dispose of the database connection pool."""
        self._engine.dispose()
