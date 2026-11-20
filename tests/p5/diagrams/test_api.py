"""Owned FastAPI boundary, real C2 objects; no claim of physical deployment."""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1 import diagrams as api
from backend.platform.analysis.application.dependencies import (
    DelegatedRequestContext,
    get_delegated_context,
)
from backend.platform.analysis.architecture.dto import ArchitectureVersionResponse
from backend.platform.delivery.contracts import DiagramTemplate
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import DiagramViewResponse
from backend.platform.diagrams.model import digest
from tests.p5.diagrams.test_c2_consumers import prepared


def record_for(value):
    scope = value.spec.scope
    return ArchitectureVersionResponse(
        id=scope.architecture_version_id,
        analysis_id=scope.analysis_id,
        project_id=scope.project_id,
        repository_id=scope.repository_id,
        snapshot_id=scope.snapshot_id,
        sequence_number=scope.sequence_number,
        architecture_schema_version="1.0.0",
        ir_schema_version="1.0.0",
        content_digest=scope.canonical_digest,
        entity_count=0,
        relationship_count=0,
        evidence_count=0,
        unresolved_relationship_count=0,
        conflict_count=0,
        completeness=value.spec.coverage.source_completeness.model_dump(),
        published_at=value.descriptor.reference.scope.published_at,
    )


@pytest.fixture
def boundary():
    value = prepared(DiagramTemplate.OVERVIEW)
    record = record_for(value)
    actor = uuid4()
    context = DelegatedRequestContext(actor, "VIEWER", project_id=record.project_id)
    calls = []

    class Versions:
        def get_version(self, version, project):
            assert version == record.id and project == record.project_id
            return record

    class Service:
        limits = DiagramLimits()

        def prepared(self, *args):
            calls.append(args)
            return value

        def view(self, record, template, gid, body):
            calls.append(body)
            return DiagramViewResponse(
                base_generation_id=gid,
                base_semantic_digest=value.spec.semantic_digest,
                request_digest=digest("ss.diagram.view", body),
                spec=value.spec,
                layout=value.layout,
            )

    service = Service()
    app = FastAPI()
    app.include_router(api.router, prefix="/api/v1")
    app.dependency_overrides[get_delegated_context] = lambda: context
    app.dependency_overrides[
        api.get_diagram_version_reader
    ] = lambda: lambda version, project, deadline: Versions().get_version(
        version, project
    )
    app.dependency_overrides[api.service_factory] = lambda: lambda: service
    app.dependency_overrides[api.get_delivery_coordinator] = lambda: None
    base = f"/api/v1/architecture-versions/{record.id}/diagrams/system_overview"
    exact = base + f"/generations/{value.descriptor.reference.generation_id}"
    with TestClient(app) as client:
        yield client, app, record, value, calls, base, exact


@pytest.mark.parametrize("member", ["spec", "layout"])
def test_exact_json_headers_and_closed_response(boundary, member):
    client, _, record, value, calls, _, exact = boundary
    response = client.get(
        exact + "/" + member, params={"project_id": str(record.project_id)}
    )
    assert response.status_code == 200, response.text
    assert response.content == getattr(value, member).to_bytes()
    assert response.headers["etag"].startswith('"')
    assert response.headers["content-digest"].startswith("sha-256=:")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert len(calls) == 1


def test_cross_project_and_actor_rejected_before_store(boundary):
    client, app, record, _, calls, _, exact = boundary
    response = client.get(exact + "/spec", params={"project_id": str(uuid4())})
    assert response.status_code in (403, 404)
    assert not calls
    app.dependency_overrides[get_delegated_context] = lambda: DelegatedRequestContext(
        None, "VIEWER", project_id=record.project_id
    )
    assert (
        client.get(
            exact + "/spec", params={"project_id": str(record.project_id)}
        ).status_code
        == 401
    )
    assert not calls


@pytest.mark.parametrize(
    "suffix,params,status",
    [
        ("/export", {"format": "png"}, 422),
        ("/members", {"limit": 201}, 422),
        ("/members", {"cursor": "x" * 4097}, 422),
    ],
)
def test_invalid_requests_are_safe_closed_errors(boundary, suffix, params, status):
    client, _, record, _, calls, _, exact = boundary
    response = client.get(
        exact + suffix, params={"project_id": str(record.project_id), **params}
    )
    assert response.status_code == status
    assert set(response.json()["error"]["details"]) == {
        "dimension",
        "actual",
        "limit",
        "request_id",
    }
    assert not calls


def test_range_rejected_without_store_access(boundary):
    client, _, record, _, calls, _, exact = boundary
    response = client.get(
        exact + "/export",
        params={"project_id": str(record.project_id)},
        headers={"Range": "bytes=0-1"},
    )
    assert response.status_code == 416
    assert not calls


def test_svg_export_uses_one_verified_read_and_final_authority_check(boundary):
    from types import SimpleNamespace

    client, app, record, value, _, _, exact = boundary
    reference = value.descriptor.reference
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
    calls = []

    def accepted(*args):
        calls.append("reference")
        return reference

    def read(scope, ref):
        assert (scope, ref) == (reference.scope, reference)
        calls.append("verified")
        return value, svg

    def recheck(scope, ref):
        assert (scope, ref) == (reference.scope, reference)
        calls.append("recheck")

    # No open_exact method: the export must not reopen the already verified SVG.
    service = SimpleNamespace(
        limits=DiagramLimits(),
        exact_reference=accepted,
        reader=SimpleNamespace(
            read_verified=read,
            store=SimpleNamespace(authority=SimpleNamespace(recheck=recheck)),
        ),
    )
    app.dependency_overrides[api.service_factory] = lambda: lambda: service
    response = client.get(
        exact + "/export",
        params={"project_id": str(record.project_id), "format": "svg"},
    )
    assert response.status_code == 200, response.text
    assert response.content == svg
    assert calls == ["reference", "verified", "recheck"]


def test_view_strict_json_and_duplicate_body_keys(boundary):
    client, _, record, _, calls, _, exact = boundary
    body = dict(
        root_ids=[],
        entity_kinds=[],
        statuses=[],
        relationship_kinds=[],
        include_contains=False,
        depth=1,
        direction="outgoing",
        collapsed_group_ids=[],
        selected_entity_ids=[],
    )
    response = client.post(
        exact + "/view", params={"project_id": str(record.project_id)}, json=body
    )
    assert response.status_code == 200, response.text
    for data in ['{"depth":1,"depth":2}', '{"depth":1.5}', "x" * 131073]:
        response = client.post(
            exact + "/view",
            params={"project_id": str(record.project_id)},
            content=data,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422, response.text
    assert len(calls) == 1


def test_disabled_read_configuration_is_honest_collection(boundary):
    client, app, record, _, _, base, _ = boundary

    def unavailable():
        raise ValueError("diagram_store_unavailable")

    app.dependency_overrides[api.service_factory] = lambda: unavailable
    response = client.get(
        base.rsplit("/", 1)[0], params={"project_id": str(record.project_id)}
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) == 4
    for item in response.json()["items"]:
        assert item["availability"] == "UNAVAILABLE"
        assert item["readability"] == "unknown" and item["reference"] is None
        assert not item["capabilities"]["json"]


@pytest.mark.parametrize("code,status", list(api.STATUSES.items()))
def test_closed_error_status_matrix_never_echoes_exception_text(boundary, code, status):
    client, app, record, _, _, _, exact = boundary

    def fail():
        raise ValueError(code)

    app.dependency_overrides[api.service_factory] = lambda: fail
    response = client.get(
        exact + "/spec", params={"project_id": str(record.project_id)}
    )
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.headers["cache-control"] == "private, no-store"


def test_unknown_exception_and_continuation_generation_loss_are_sanitized(boundary):
    client, app, record, _, _, _, exact = boundary

    class Broken:
        def members(self, *args):
            raise ValueError("diagram_generation_unavailable")

    app.dependency_overrides[api.service_factory] = lambda: lambda: Broken()
    response = client.get(
        exact + "/members",
        params={"project_id": str(record.project_id), "cursor": "opaque"},
    )
    assert response.status_code == 410

    def secret_failure():
        raise RuntimeError("private-path-password-sql")

    app.dependency_overrides[api.service_factory] = lambda: secret_failure
    response = client.get(
        exact + "/spec", params={"project_id": str(record.project_id)}
    )
    assert response.status_code == 500
    assert "private-path" not in response.text


@pytest.mark.parametrize("role", ["OWNER", "ADMIN", "DEVELOPER", "VIEWER"])
def test_each_read_role_reauthorizes_before_exact_read(boundary, role):
    client, app, record, _, calls, _, exact = boundary
    app.dependency_overrides[get_delegated_context] = lambda: DelegatedRequestContext(
        uuid4(), role, project_id=record.project_id
    )
    assert (
        client.get(
            exact + "/spec", params={"project_id": str(record.project_id)}
        ).status_code
        == 200
    )
    assert len(calls) == 1


def test_duplicate_project_and_actor_override_query_rejected(boundary):
    client, _, record, _, calls, _, exact = boundary
    assert (
        client.get(
            exact + "/spec",
            params=[
                ("project_id", str(record.project_id)),
                ("project_id", str(record.project_id)),
            ],
        ).status_code
        == 422
    )
    assert (
        client.get(
            exact + "/spec",
            params={"project_id": str(record.project_id), "actor_id": str(uuid4())},
        ).status_code
        == 422
    )
    assert not calls
