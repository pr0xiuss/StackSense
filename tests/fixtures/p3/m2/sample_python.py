"""Sample Python module for M2 parser tests."""

from typing import Any


class UserService:
    """Service handling user accounts."""

    def __init__(self, db_client: Any) -> None:
        self.db = db_client

    async def get_user_by_id(self, user_id: str) -> dict[str, Any]:
        """Fetch user by primary key."""
        result: dict[str, Any] = self.db.find_one({"id": user_id})
        return result


def create_user_service(db: Any) -> UserService:
    """Factory creating UserService instance."""
    return UserService(db)
