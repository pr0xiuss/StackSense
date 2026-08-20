"""Integration tests for StackSense dependency injection."""

from sqlalchemy import text

from backend.platform.dependency_injection import get_database_session


def test_database_session_dependency_connects_to_postgres() -> None:
    """Database session dependency provides a working PostgreSQL session."""
    session_generator = get_database_session()
    session = next(session_generator)

    try:
        result = session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
    finally:
        session.close()
        session_generator.close()
