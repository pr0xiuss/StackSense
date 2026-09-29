"""SQLAlchemy implementation of the RefreshTokenRepository contract."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.platform.identity.domain.refresh_token import RefreshToken
from backend.platform.identity.infra.refresh_token_model import RefreshTokenModel
from backend.platform.identity.repositories.refresh_token_repo import (
    RefreshTokenRepository,
)


class SqlAlchemyRefreshTokenRepository(RefreshTokenRepository):
    """PostgreSQL-backed implementation of RefreshTokenRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, refresh_token: RefreshToken) -> RefreshToken:
        model = RefreshTokenModel(
            id=refresh_token.id,
            user_id=refresh_token.user_id,
            token_hash=refresh_token.token_hash,
            expires_at=refresh_token.expires_at,
            revoked_at=refresh_token.revoked_at,
            replaced_by_token_id=refresh_token.replaced_by_token_id,
            created_at=refresh_token.created_at,
        )
        self._session.add(model)
        self._session.flush()
        return refresh_token

    def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        statement = select(RefreshTokenModel).where(
            RefreshTokenModel.token_hash == token_hash
        )
        model = self._session.scalar(statement)
        if model is None:
            return None
        return self._to_domain(model)

    def revoke(self, token_id: UUID, replaced_by_token_id: UUID | None = None) -> None:
        now = datetime.now(UTC)
        statement = (
            update(RefreshTokenModel)
            .where(RefreshTokenModel.id == token_id)
            .values(revoked_at=now, replaced_by_token_id=replaced_by_token_id)
        )
        self._session.execute(statement)
        self._session.flush()

    def revoke_all_for_user(self, user_id: UUID) -> None:
        now = datetime.now(UTC)
        statement = (
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        self._session.execute(statement)
        self._session.flush()

    def get_active_for_user(self, user_id: UUID) -> list[RefreshToken]:
        now = datetime.now(UTC)
        statement = (
            select(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked_at.is_(None),
                RefreshTokenModel.expires_at > now,
            )
            .order_by(RefreshTokenModel.created_at.desc())
        )
        models = self._session.scalars(statement).all()
        return [self._to_domain(m) for m in models]

    def _to_domain(self, model: RefreshTokenModel) -> RefreshToken:
        return RefreshToken(
            id=model.id,
            user_id=model.user_id,
            token_hash=model.token_hash,
            expires_at=model.expires_at,
            revoked_at=model.revoked_at,
            replaced_by_token_id=model.replaced_by_token_id,
            created_at=model.created_at,
        )
