"""HTTP contract, delegated authorization and safe local error translation."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from backend.api.error_handlers import register_exception_handlers
from backend.api.v1.delivery import (
    get_delivery_coordinator,
    router,
)
from backend.platform.analysis.application.dependencies import (
    DelegatedRequestContext,
    get_architecture_query_service,
    get_delegated_context,
)
from backend.platform.delivery.api_contracts import (
    DeliveryApiError,
    DeliverySummary,
    RetryAccepted,
)
from backend.platform.delivery.dependencies import get_delivery_reader
from backend.platform.delivery.model import Eligibility
from tests.p5.delivery.test_contracts import scope


@pytest.fixture
def api():
    selected = scope()
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    class Runtime:
        error = None
        calls = 0

        def scope_for_record(self, record):
            return None

        def summary(self, received, role):
            assert received == selected
            if self.error:
                raise self.error
            return DeliverySummary(scope=received, eligibility="NOT_SCHEDULED")

        def retry(self, received, request, actor, role):
            self.calls += 1
            if self.error:
                raise self.error
            return RetryAccepted(
                scope=received,
                operation_id=uuid4(),
                work_id=uuid4(),
                retry_of_work_id=request.resource_id,
            )

    runtime = Runtime()
    app.dependency_overrides[get_delivery_coordinator] = lambda: runtime
    app.dependency_overrides[get_architecture_query_service] = lambda: SimpleNamespace(
        get_version=lambda version, project: selected
    )
    app.dependency_overrides[get_delivery_reader] = lambda: SimpleNamespace(
        inspect_requested=lambda version: SimpleNamespace(
            scope=selected, eligibility=Eligibility.ELIGIBLE
        )
    )
    app.dependency_overrides[get_delegated_context] = lambda: DelegatedRequestContext(
        actor_id=uuid4(), role="OWNER", project_id=selected.project_id
    )
    return app, TestClient(app), runtime, selected


def path(selected):
    return (
        f"/api/v1/architecture-versions/{selected.architecture_version_id}"
        f"/delivery?project_id={selected.project_id}"
    )


def retry_path(selected):
    return path(selected).replace("/delivery?", "/delivery/retry?")


def body():
    return {
        "resource_type": "diagram",
        "resource_id": str(uuid4()),
        "idempotency_key": "retry:key",
    }


@pytest.mark.parametrize("role", ["OWNER", "ADMIN", "DEVELOPER", "VIEWER"])
def test_all_delegated_roles_can_read_status(api, role):
    app, client, _, selected = api
    app.dependency_overrides[get_delegated_context] = lambda: DelegatedRequestContext(
        actor_id=uuid4(), role=role, project_id=selected.project_id
    )
    response = client.get(path(selected))
    assert response.status_code == 200
    assert response.json()["scope"]["architecture_version_id"] == str(
        selected.architecture_version_id
    )


@pytest.mark.parametrize("role", ["DEVELOPER", "VIEWER"])
def test_unauthorized_retry_never_calls_service(api, role):
    app, client, runtime, selected = api
    app.dependency_overrides[get_delegated_context] = lambda: DelegatedRequestContext(
        actor_id=uuid4(), role=role, project_id=selected.project_id
    )
    assert client.post(retry_path(selected), json=body()).status_code == 403
    assert runtime.calls == 0


def test_project_scope_mismatch_denied(api):
    app, client, runtime, selected = api
    app.dependency_overrides[get_delegated_context] = lambda: DelegatedRequestContext(
        actor_id=uuid4(), role="OWNER", project_id=uuid4()
    )
    assert client.get(path(selected)).status_code == 403
    assert client.post(retry_path(selected), json=body()).status_code == 403
    assert runtime.calls == 0


def test_real_service_auth_requires_token_and_trusted_actor(api):
    app, client, _, selected = api
    app.dependency_overrides.pop(get_delegated_context)
    assert client.get(path(selected)).status_code == 401
    assert (
        client.get(
            path(selected), headers={"X-Service-Token": "not-the-secret"}
        ).status_code
        == 401
    )


@pytest.mark.parametrize(
    "change",
    [
        {"extra": True},
        {"resource_type": "arbitrary"},
        {"resource_id": "bad"},
        {"idempotency_key": "x" * 129},
        {"idempotency_key": ""},
    ],
)
def test_strict_retry_request_validation(api, change):
    _, client, runtime, selected = api
    assert (
        client.post(retry_path(selected), json={**body(), **change}).status_code == 422
    )
    assert runtime.calls == 0


@pytest.mark.parametrize("status", [404, 409, 503])
def test_safe_error_status_and_shape(api, status):
    _, client, runtime, selected = api
    runtime.error = DeliveryApiError("delivery_fixture_failure", status)
    response = client.post(retry_path(selected), json=body())
    assert response.status_code == status
    assert response.json()["error"]["code"] == "delivery_fixture_failure"
    assert response.json()["error"]["details"] == {}


def test_persistence_error_does_not_expose_credentials(api):
    _, client, runtime, selected = api
    runtime.error = OperationalError("sensitive SQL", {}, Exception("secret password"))
    response = client.get(path(selected))
    assert response.status_code == 503
    assert "secret" not in response.text and "sensitive" not in response.text


def test_async_retry_acceptance_and_unconfigured_status(api):
    app, client, _, selected = api
    assert client.post(retry_path(selected), json=body()).status_code == 202
    app.dependency_overrides[get_delivery_coordinator] = lambda: None
    response = client.get(path(selected))
    assert response.status_code == 200
    assert response.json()["eligibility"] == "NOT_SCHEDULED"
    assert client.post(retry_path(selected), json=body()).status_code == 503


def test_accepted_scope_polling_avoids_reloading_canonical_payload(api):
    app, client, runtime, selected = api
    runtime.scope_for_record = lambda record: selected

    def forbidden():
        raise AssertionError("accepted scope must not reload canonical source")

    app.dependency_overrides[get_delivery_reader] = lambda: SimpleNamespace(
        inspect_requested=lambda record: forbidden()
    )
    assert client.get(path(selected)).status_code == 200


def test_corrupt_persisted_c0_value_maps_to_safe_conflict(api):
    from pydantic import ValidationError

    from backend.platform.delivery.contracts import ArtifactReference

    _, client, runtime, selected = api
    try:
        ArtifactReference.model_validate({"contract_version": "unsupported"})
    except ValidationError as exc:
        runtime.error = exc
    response = client.get(path(selected))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "delivery_prerequisite_conflict"
    assert "validation" not in response.text.lower()


def test_error_dtos_are_present_in_openapi(api):
    app, _, _, _ = api
    endpoints = app.openapi()["paths"]
    for operation in (
        endpoints["/api/v1/architecture-versions/{version_id}/delivery"]["get"],
        endpoints["/api/v1/architecture-versions/{version_id}/delivery/retry"]["post"],
    ):
        assert {"401", "403", "404", "409", "422", "503"} <= set(operation["responses"])
