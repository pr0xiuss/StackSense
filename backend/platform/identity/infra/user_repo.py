"""SQLAlchemy implementation of the UserRepository contract."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.platform.identity.domain.credential import UserCredential
from backend.platform.identity.domain.user import User
from backend.platform.identity.infra.user_model import (
    UserCredentialModel,
    UserModel,
)
from backend.platform.identity.repositories.user_repo import UserRepository


class SqlAlchemyUserRepository(UserRepository):
    """PostgreSQL-backed implementation of UserRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: UUID) -> User | None:
        statement = select(UserModel).where(UserModel.id == user_id)
        model = self._session.scalar(statement)
        if model is None:
            return None
        return self._to_domain(model)

    def get_by_email(self, email: str) -> User | None:
        normalized_email = email.strip().lower()
        statement = select(UserModel).where(
            func.lower(UserModel.email) == normalized_email,
        )
        model = self._session.scalar(statement)
        if model is None:
            return None
        return self._to_domain(model)

    def get_credential_by_user_id(self, user_id: UUID) -> UserCredential | None:
        statement = select(UserCredentialModel).where(
            UserCredentialModel.user_id == user_id,
        )
        model = self._session.scalar(statement)
        if model is None:
            return None
        return UserCredential(
            user_id=model.user_id,
            password_hash=model.password_hash,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def save(
        self,
        user: User,
        credential: UserCredential | None = None,
    ) -> User:
        user_model = UserModel(
            id=user.id,
            email=user.email.strip().lower(),
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        self._session.add(user_model)
        self._session.flush()

        if credential is not None:
            credential_model = UserCredentialModel(
                user_id=credential.user_id,
                password_hash=credential.password_hash,
                created_at=credential.created_at or user.created_at,
                updated_at=credential.updated_at or user.updated_at,
            )
            self._session.add(credential_model)
            self._session.flush()

        return user

    def update(self, user: User) -> User:
        statement = select(UserModel).where(UserModel.id == user.id)
        model = self._session.scalar(statement)
        if model is None:
            raise ValueError(f"User {user.id} not found for update.")

        model.email = user.email.strip().lower()
        model.is_active = user.is_active
        if user.updated_at is not None:
            model.updated_at = user.updated_at

        self._session.flush()
        return user

    def _to_domain(self, model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
