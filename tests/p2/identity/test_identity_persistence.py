"""Integration tests for Identity persistence (SqlAlchemyUserRepository)."""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.platform.dependency_injection import get_database
from backend.platform.errors import (
    UserAlreadyExistsError,
    UsernameAlreadyExistsError,
)
from backend.platform.identity.domain.credential import UserCredential
from backend.platform.identity.domain.user import User
from backend.platform.identity.infra.user_model import (
    UserCredentialModel,
    UserModel,
)
from backend.platform.identity.infra.user_repo import SqlAlchemyUserRepository
from backend.platform.projects.domain.project_role import ProjectRole
from backend.platform.projects.infra.access_model import ProjectAccessModel
from backend.platform.projects.infra.model import ProjectModel


@pytest.fixture
def session() -> Generator[Session]:
    """Provide a database session that rolls back or cleans up after each test."""
    database = get_database()
    gen = database.session()
    sess = next(gen)
    try:
        yield sess
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        gen.close()


def test_save_and_get_by_id(session: Session) -> None:
    repo = SqlAlchemyUserRepository(session)
    user_id = uuid4()
    tag = uuid4().hex[:8]
    email = f"alice-{tag}@stacksense.local"
    username = f"alice_{tag}"
    now = datetime.now(UTC)
    user = User(
        id=user_id,
        email=email,
        username=username,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    saved = repo.save(user)
    assert saved.id == user_id

    fetched = repo.get_by_id(user_id)
    assert fetched is not None
    assert fetched.id == user_id
    assert fetched.email == email
    assert fetched.username == username
    assert fetched.is_active is True


def test_save_with_credential_and_get_credential(session: Session) -> None:
    repo = SqlAlchemyUserRepository(session)
    user_id = uuid4()
    tag = uuid4().hex[:8]
    email = f"bob-{tag}@stacksense.local"
    username = f"bob_{tag}"
    now = datetime.now(UTC)
    user = User(
        id=user_id,
        email=email,
        username=username,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    cred = UserCredential(
        user_id=user_id,
        password_hash="$2b$12$somehashedpasswordstring1234567890",
        created_at=now,
        updated_at=now,
    )

    repo.save(user, credential=cred)

    fetched_cred = repo.get_credential_by_user_id(user_id)
    assert fetched_cred is not None
    assert fetched_cred.user_id == user_id
    assert fetched_cred.password_hash == "$2b$12$somehashedpasswordstring1234567890"


def test_get_by_email_case_insensitive(session: Session) -> None:
    repo = SqlAlchemyUserRepository(session)
    user_id = uuid4()
    tag = uuid4().hex[:8]
    email = f"charlie-{tag}@stacksense.local"
    username = f"charlie_{tag}"
    now = datetime.now(UTC)
    user = User(
        id=user_id,
        email=email,
        username=username,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    repo.save(user)

    fetched = repo.get_by_email(f"CHARLIE-{tag.upper()}@STACKSENSE.LOCAL")
    assert fetched is not None
    assert fetched.id == user_id

    fetched_spaces = repo.get_by_email(f"   {email}   ")
    assert fetched_spaces is not None
    assert fetched_spaces.id == user_id


def test_get_by_email_not_found(session: Session) -> None:
    repo = SqlAlchemyUserRepository(session)
    assert repo.get_by_email(f"nonexistent-{uuid4().hex[:8]}@stacksense.local") is None


def test_get_by_username_case_insensitive(session: Session) -> None:
    repo = SqlAlchemyUserRepository(session)
    user_id = uuid4()
    tag = uuid4().hex[:8]
    email = f"user-{tag}@stacksense.local"
    username = f"dave_{tag}"
    now = datetime.now(UTC)
    user = User(
        id=user_id,
        email=email,
        username=username,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    repo.save(user)

    fetched = repo.get_by_username(f"DAVE_{tag.upper()}")
    assert fetched is not None
    assert fetched.id == user_id

    fetched_spaces = repo.get_by_username(f"   {username}   ")
    assert fetched_spaces is not None
    assert fetched_spaces.id == user_id


def test_get_by_username_not_found(session: Session) -> None:
    repo = SqlAlchemyUserRepository(session)
    assert repo.get_by_username(f"nonexistent_{uuid4().hex[:6]}") is None


def test_get_by_id_not_found(session: Session) -> None:
    repo = SqlAlchemyUserRepository(session)
    assert repo.get_by_id(uuid4()) is None


def test_update_user(session: Session) -> None:
    repo = SqlAlchemyUserRepository(session)
    user_id = uuid4()
    tag = uuid4().hex[:8]
    email = f"dan-{tag}@stacksense.local"
    username = f"dan_{tag}"
    now = datetime.now(UTC)
    user = User(
        id=user_id,
        email=email,
        username=username,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    repo.save(user)

    updated_time = datetime.now(UTC)
    updated_email = f"dan_updated-{tag}@stacksense.local"
    updated_username = f"dan_updated_{tag}"
    updated_user = User(
        id=user_id,
        email=updated_email,
        username=updated_username,
        is_active=False,
        created_at=now,
        updated_at=updated_time,
    )
    repo.update(updated_user)

    fetched = repo.get_by_id(user_id)
    assert fetched is not None
    assert fetched.email == updated_email
    assert fetched.username == updated_username
    assert fetched.is_active is False


def test_update_nonexistent_user_raises(session: Session) -> None:
    repo = SqlAlchemyUserRepository(session)
    user = User(
        id=uuid4(),
        email=f"ghost-{uuid4().hex[:8]}@stacksense.local",
        username=f"ghost_{uuid4().hex[:6]}",
    )
    with pytest.raises(ValueError, match="not found for update"):
        repo.update(user)


def test_duplicate_email_raises_user_already_exists_error(session: Session) -> None:
    repo = SqlAlchemyUserRepository(session)
    now = datetime.now(UTC)
    tag = uuid4().hex[:8]
    email = f"unique-{tag}@stacksense.local"
    user1 = User(
        id=uuid4(),
        email=email,
        username=f"user1_{tag}",
        created_at=now,
        updated_at=now,
    )
    user2 = User(
        id=uuid4(),
        email=email.upper(),
        username=f"user2_{tag}",
        created_at=now,
        updated_at=now,
    )

    repo.save(user1)

    with pytest.raises(UserAlreadyExistsError):
        repo.save(user2)
    session.rollback()


def test_duplicate_username_raises_username_already_exists_error(
    session: Session,
) -> None:
    repo = SqlAlchemyUserRepository(session)
    now = datetime.now(UTC)
    tag = uuid4().hex[:8]
    username = f"unique_{tag}"
    user1 = User(
        id=uuid4(),
        email=f"user1-{tag}@stacksense.local",
        username=username,
        created_at=now,
        updated_at=now,
    )
    user2 = User(
        id=uuid4(),
        email=f"user2-{tag}@stacksense.local",
        username=username.upper(),
        created_at=now,
        updated_at=now,
    )

    repo.save(user1)

    with pytest.raises(UsernameAlreadyExistsError):
        repo.save(user2)
    session.rollback()


def test_database_level_case_insensitive_email_unique_index(session: Session) -> None:
    now = datetime.now(UTC)
    tag = uuid4().hex[:8]
    m1 = UserModel(
        id=uuid4(),
        email=f"CaseTest-{tag}@stacksense.local",
        username=f"user_m1_{tag}",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(m1)
    session.flush()

    m2 = UserModel(
        id=uuid4(),
        email=f"casetest-{tag}@stacksense.local",
        username=f"user_m2_{tag}",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(m2)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_database_level_case_insensitive_username_unique_index(
    session: Session,
) -> None:
    now = datetime.now(UTC)
    tag = uuid4().hex[:8]
    m1 = UserModel(
        id=uuid4(),
        email=f"user1-{tag}@stacksense.local",
        username=f"UniqueUser_{tag}",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(m1)
    session.flush()

    m2 = UserModel(
        id=uuid4(),
        email=f"user2-{tag}@stacksense.local",
        username=f"uniqueuser_{tag}",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(m2)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_cascade_delete_credential(session: Session) -> None:
    repo = SqlAlchemyUserRepository(session)
    user_id = uuid4()
    tag = uuid4().hex[:8]
    now = datetime.now(UTC)
    user = User(
        id=user_id,
        email=f"cascade_test-{tag}@stacksense.local",
        username=f"cascade_{tag}",
        created_at=now,
        updated_at=now,
    )
    cred = UserCredential(
        user_id=user_id,
        password_hash="test_hash",
        created_at=now,
        updated_at=now,
    )
    repo.save(user, credential=cred)

    # Directly delete user model
    user_model = session.scalar(select(UserModel).where(UserModel.id == user_id))
    assert user_model is not None
    session.delete(user_model)
    session.flush()

    # Credential must be gone due to CASCADE
    cred_model = session.scalar(
        select(UserCredentialModel).where(UserCredentialModel.user_id == user_id)
    )
    assert cred_model is None


def test_project_access_foreign_key_on_delete_restrict(session: Session) -> None:
    repo = SqlAlchemyUserRepository(session)
    user_id = uuid4()
    tag = uuid4().hex[:8]
    project_id = uuid4()
    now = datetime.now(UTC)

    # 1. Create User
    user = User(
        id=user_id,
        email=f"project_owner-{tag}@stacksense.local",
        username=f"proj_owner_{tag}",
        created_at=now,
        updated_at=now,
    )
    repo.save(user)

    # 2. Create Project
    project = ProjectModel(
        id=project_id,
        name=f"FK-Test-{tag[:6]}",
        created_at=now,
        updated_at=now,
    )
    session.add(project)
    session.flush()

    # 3. Create ProjectAccess
    access = ProjectAccessModel(
        project_id=project_id,
        user_id=user_id,
        role=ProjectRole.OWNER,
    )
    session.add(access)
    session.flush()

    # 4. Attempt to delete user — must fail with IntegrityError
    # because of ON DELETE RESTRICT constraint on project_access.user_id.
    user_model = session.scalar(select(UserModel).where(UserModel.id == user_id))
    assert user_model is not None
    session.delete(user_model)

    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
