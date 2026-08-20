"""PostgreSQL integration tests."""

from sqlalchemy import text

from backend.platform.dependency_injection import get_database


def test_database_connection() -> None:
    """Verify StackSense can execute a query against PostgreSQL."""
    database = get_database()
    session = next(database.session())

    try:
        result = session.execute(text("SELECT 1")).scalar_one()
    finally:
        session.close()
        database.dispose()

    assert result == 1
