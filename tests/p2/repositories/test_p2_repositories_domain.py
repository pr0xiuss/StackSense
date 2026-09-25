"""Unit tests for Repository domain entity."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.platform.repositories.domain.repository import Repository


def test_repository_domain_creation() -> None:
    repo_id = uuid4()
    project_id = uuid4()
    now = datetime.now(UTC)

    repository = Repository(
        id=repo_id,
        project_id=project_id,
        name="payment-service",
        description="Core payment processing service",
        status="registered",
        created_at=now,
        updated_at=now,
    )

    assert repository.id == repo_id
    assert repository.project_id == project_id
    assert repository.name == "payment-service"
    assert repository.description == "Core payment processing service"
    assert repository.status == "registered"
    assert repository.created_at == now
    assert repository.updated_at == now


def test_repository_domain_immutability() -> None:
    repo_id = uuid4()
    project_id = uuid4()
    now = datetime.now(UTC)

    repository = Repository(
        id=repo_id,
        project_id=project_id,
        name="auth-service",
        description=None,
        status="registered",
        created_at=now,
        updated_at=now,
    )

    with pytest.raises(FrozenInstanceError):
        repository.name = "new-name"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        repository.status = "active"  # type: ignore[misc]


def test_repository_domain_slots() -> None:
    repository = Repository(
        id=uuid4(),
        project_id=uuid4(),
        name="analytics",
        description=None,
        status="registered",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with pytest.raises(AttributeError):
        repository.arbitrary_field = "unexpected"  # type: ignore[attr-defined]
