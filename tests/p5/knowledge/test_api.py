"""Tests for Knowledge Search FastAPI endpoints and HTTP status translations."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.error_handlers import register_exception_handlers
from backend.api.v1.knowledge import router
from backend.platform.analysis.application.dependencies import (
    DelegatedRequestContext,
    get_architecture_query_service,
    get_delegated_context,
)
from backend.platform.knowledge.contracts import (
    SearchBackendUnavailableError,
    SearchCapabilities,
    SearchCursorExpiredError,
    SearchCursorInvalidError,
    SearchDeadlineExceededError,
    SearchGenerationChangedError,
    SearchNotReadyError,
    SearchPage,
    SearchStatus,
)
from backend.platform.knowledge.dependencies import (
    get_search_reader,
    get_search_status_service,
)
from tests.p5.knowledge.conftest import make_test_scope


@pytest.fixture
def knowledge_api():
    scope = make_test_scope()
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    class MockReader:
        error = None

        def search(self, request):
            if self.error:
                raise self.error
            return SearchPage(
                c1_version="1.0.0",
                scope=scope,
                generation_id=uuid4(),
                items=(),
                total_hits=0,
                has_more=False,
                capabilities=SearchCapabilities(),
            )

    class MockStatusService:
        error = None

        def get_status(self, project_id, version_id):
            if self.error:
                raise self.error
            return SearchStatus(
                scope=scope,
                resource_state="READY",
                freshness="CURRENT",
                is_readable=True,
                is_current_version=True,
                capabilities=SearchCapabilities(),
            )

    reader = MockReader()
    status_service = MockStatusService()

    app.dependency_overrides[get_search_reader] = lambda: reader
    app.dependency_overrides[get_search_status_service] = lambda: status_service
    app.dependency_overrides[get_architecture_query_service] = lambda: SimpleNamespace(
        get_version=lambda v, p: scope
    )
    app.dependency_overrides[get_delegated_context] = lambda: DelegatedRequestContext(
        actor_id=uuid4(), role="OWNER", project_id=scope.project_id
    )

    client = TestClient(app)
    yield client, app, reader, status_service, scope


def search_path(scope, query: str = "test") -> str:
    return (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}"
        f"/search?project_id={scope.project_id}&q={query}"
    )


def status_path(scope) -> str:
    return (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}"
        f"/search/status?project_id={scope.project_id}"
    )


@pytest.mark.parametrize("role", ["OWNER", "ADMIN", "DEVELOPER", "VIEWER"])
def test_all_delegated_roles_can_search_and_read_status(knowledge_api, role):
    client, app, _, _, scope = knowledge_api
    app.dependency_overrides[get_delegated_context] = lambda: DelegatedRequestContext(
        actor_id=uuid4(), role=role, project_id=scope.project_id
    )

    # 1. Search endpoint
    search_res = client.get(search_path(scope))
    assert search_res.status_code == 200
    assert search_res.json()["c1_version"] == "1.0.0"

    # 2. Status endpoint
    status_res = client.get(status_path(scope))
    assert status_res.status_code == 200
    assert status_res.json()["resource_state"] == "READY"
    assert status_res.json()["freshness"] == "CURRENT"


def test_project_scope_mismatch_forbidden(knowledge_api):
    client, app, _, _, scope = knowledge_api
    # Context with a different project_id
    app.dependency_overrides[get_delegated_context] = lambda: DelegatedRequestContext(
        actor_id=uuid4(), role="OWNER", project_id=uuid4()
    )

    response = client.get(search_path(scope))
    assert response.status_code == 403


def test_invalid_document_kind_rejected(knowledge_api):
    client, _, _, _, scope = knowledge_api
    url = f"{search_path(scope)}&document_kinds=invalid_kind"
    response = client.get(url)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_document_kind"


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (SearchNotReadyError(), 404, "search_not_ready"),
        (SearchGenerationChangedError(), 409, "search_generation_changed"),
        (SearchCursorExpiredError(), 410, "search_cursor_expired"),
        (SearchCursorInvalidError(), 422, "search_cursor_invalid"),
        (SearchBackendUnavailableError(), 503, "search_backend_unavailable"),
        (SearchDeadlineExceededError(), 504, "search_deadline_exceeded"),
    ],
)
def test_search_error_translations(
    knowledge_api, error, expected_status, expected_code
):
    client, _, reader, _, scope = knowledge_api
    reader.error = error

    response = client.get(search_path(scope))
    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code
