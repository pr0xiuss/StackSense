"""Exact-version diagram reads. M6 owns the Express/browser transport later."""

from __future__ import annotations

import asyncio
import base64
import hashlib
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

from backend.api.v1.delivery import get_delivery_coordinator
from backend.platform.analysis.application.dependencies import (
    DelegatedRequestContext,
    get_delegated_context,
    require_delegated_project,
)
from backend.platform.analysis.architecture.dto import ArchitectureVersionResponse
from backend.platform.delivery.contracts import DiagramTemplate
from backend.platform.delivery.service import DeliveryCoordinator
from backend.platform.diagrams.api_contracts import (
    DiagramCapabilities,
    DiagramCollection,
    DiagramSummary,
    GenerationPage,
    MemberPage,
)
from backend.platform.diagrams.contracts import (
    DiagramSpec,
    DiagramViewRequest,
    DiagramViewResponse,
    ErrorResponse,
    LayoutSpec,
    PreparedDiagram,
)
from backend.platform.diagrams.dependencies import (
    get_diagram_limits,
    get_diagram_service,
    get_diagram_version_reader,
)
from backend.platform.diagrams.model import canonical_bytes, load_json
from backend.platform.diagrams.repository import metadata_operation
from backend.platform.diagrams.service import DiagramService, canonical_scope
from backend.platform.errors import StackSenseError

STATUSES = {
    "diagram_authentication_required": 401,
    "diagram_forbidden": 403,
    "diagram_not_found": 404,
    "diagram_not_ready": 409,
    "diagram_scope_mismatch": 409,
    "diagram_generation_changed": 409,
    "diagram_cursor_invalid": 422,
    "diagram_cursor_expired": 410,
    "diagram_generation_unavailable": 503,
    "diagram_input_invalid": 422,
    "diagram_contract_unsupported": 422,
    "diagram_limit_exceeded": 422,
    "diagram_range_unsupported": 416,
    "diagram_runtime_unavailable": 503,
    "diagram_store_unavailable": 503,
    "diagram_source_unavailable": 503,
    "diagram_timeout": 504,
    "diagram_integrity_error": 500,
    "diagram_internal_error": 500,
}


def error(code: str, *, continuation: bool = False) -> JSONResponse:
    status = STATUSES.get(code, 500)
    if code not in STATUSES:
        code = "diagram_internal_error"
    if code == "diagram_generation_unavailable" and continuation:
        status = 410
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": code.replace("_", " ").capitalize() + ".",
                "details": {
                    "dimension": None,
                    "actual": None,
                    "limit": None,
                    "request_id": None,
                },
            }
        },
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


class DiagramRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handle(request: Request) -> Response:
            try:
                limits = get_diagram_limits()
                request.state.diagram_deadline = monotonic() + (
                    limits.build_seconds
                    if request.url.path.endswith("/local-preview")
                    else (
                        limits.view_seconds
                        if request.method == "POST"
                        else limits.read_seconds
                    )
                )
                keys = list(request.query_params.keys())
                if any(len(request.query_params.getlist(k)) != 1 for k in keys):
                    return error("diagram_input_invalid")
                if not set(keys) <= {
                    "project_id",
                    "generation_id",
                    "limit",
                    "cursor",
                    "group_id",
                    "entity_id",
                    "format",
                }:
                    return error("diagram_input_invalid")
                if request.method == "POST":
                    if (
                        request.headers.get("content-type", "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                        != "application/json"
                    ):
                        return error("diagram_input_invalid")
                    data = bytearray()
                    async with asyncio.timeout(
                        max(0, request.state.diagram_deadline - monotonic())
                    ):
                        async for chunk in request.stream():
                            data.extend(chunk)
                            if len(data) > limits.max_api_body_bytes:
                                return error("diagram_limit_exceeded")
                    # Reject duplicate keys/floats before parsed-object ingress.
                    try:
                        load_json(bytes(data), max_bytes=131072)
                    except ValueError:
                        return error("diagram_input_invalid")
                    request._body = bytes(data)
                with metadata_operation(request.state.diagram_deadline):
                    async with asyncio.timeout(
                        max(0, request.state.diagram_deadline - monotonic())
                    ):
                        response = await original(request)
                if monotonic() >= request.state.diagram_deadline:
                    return error("diagram_timeout")
                return response
            except RequestValidationError:
                return error("diagram_input_invalid")
            except ValidationError:
                return error("diagram_integrity_error")
            except TimeoutError:
                return error("diagram_timeout")
            except StackSenseError as exc:
                code = exc.code.lower()
                mapped = (
                    "diagram_authentication_required"
                    if any(x in code for x in ("token", "authentication"))
                    else (
                        "diagram_forbidden"
                        if any(x in code for x in ("denied", "forbidden"))
                        else (
                            "diagram_not_found"
                            if "not_found" in code
                            else "diagram_internal_error"
                        )
                    )
                )
                return error(mapped)
            except ValueError as exc:
                return error(
                    str(exc), continuation=bool(request.query_params.get("cursor"))
                )
            except SQLAlchemyError, OSError:
                return error("diagram_store_unavailable")
            except Exception:
                return error("diagram_internal_error")

        return handle


router = APIRouter(
    tags=["Diagrams"],
    route_class=DiagramRoute,
    responses={
        status: {"model": ErrorResponse}
        for status in (401, 403, 404, 409, 410, 416, 422, 500, 503, 504)
    },
)


@dataclass(frozen=True)
class Access:
    record: ArchitectureVersionResponse
    actor: UUID
    role: str


def authorize(
    version_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    versions: Annotated[
        Callable[[UUID, UUID, float], ArchitectureVersionResponse],
        Depends(get_diagram_version_reader),
    ],
    request: Request,
) -> Access:
    require_delegated_project(context, project_id)
    if context.actor_id is None:
        raise ValueError("diagram_authentication_required")
    if context.role not in {"OWNER", "ADMIN", "DEVELOPER", "VIEWER"}:
        raise ValueError("diagram_forbidden")
    return Access(
        versions(version_id, project_id, request.state.diagram_deadline),
        context.actor_id,
        context.role,
    )


def service_factory(
    access: Annotated[Access, Depends(authorize)],
) -> Callable[[], DiagramService]:
    # Returning a factory ensures authorization/header validation precedes store access.
    instance: DiagramService | None = None

    def get() -> DiagramService:
        nonlocal instance
        if instance is None:
            instance = get_diagram_service(access.actor)
        return instance

    return get


A = Annotated[Access, Depends(authorize)]
F = Annotated[Callable[[], DiagramService], Depends(service_factory)]
R = Annotated[DeliveryCoordinator | None, Depends(get_delivery_coordinator)]
PREFIX = "/architecture-versions/{version_id}/diagrams"
EXACT = PREFIX + "/{template}/generations/{generation}"


def summary(
    access: Access,
    template: DiagramTemplate,
    factory: Callable[[], DiagramService],
    runtime: DeliveryCoordinator | None,
    generation: UUID | None = None,
) -> DiagramSummary:
    try:
        service = factory()
    except ValueError:
        if generation is not None:
            raise
        return DiagramSummary(
            template=template,
            canonical_scope=canonical_scope(access.record),
            delivery_scope=None,
            work=None,
            availability="UNAVAILABLE",
            readability="unknown",
            verified_at=None,
            reference=None,
            coverage=None,
            counts=None,
            capabilities=DiagramCapabilities(
                read=False, view=False, json_export=False, svg=False
            ),
            reason="diagram_store_unavailable",
            observed_at=datetime.now(UTC),
        )
    with metadata_operation(monotonic() + service.limits.read_seconds):
        return service.summary(
            access.record, template, runtime, access.role, generation
        )


@router.get(PREFIX, response_model=DiagramCollection)
def collection(access: A, factory: F, runtime: R) -> DiagramCollection:
    return DiagramCollection(
        canonical_scope=canonical_scope(access.record),
        items=tuple(summary(access, t, factory, runtime) for t in DiagramTemplate),
    )


@router.get(PREFIX + "/{template}", response_model=DiagramSummary)
def template_status(
    template: DiagramTemplate,
    access: A,
    factory: F,
    runtime: R,
    generation_id: UUID | None = None,
) -> DiagramSummary:
    return summary(access, template, factory, runtime, generation_id)


@router.get(PREFIX + "/{template}/local-preview")
def local_preview(template: DiagramTemplate, access: A) -> dict[str, Any]:
    """Opt-in local-only rendering; never a published or sealed generation."""
    from backend.platform.config import get_settings

    if (
        not get_settings().stacksense_local_diagrams
        or get_settings().app_env != "development"
    ):
        raise ValueError("diagram_not_found")
    from backend.platform.dependency_injection import get_database_settings
    from backend.platform.diagrams.local_layout import render_local_diagram

    spec, layout, data = render_local_diagram(
        access.record, template, get_database_settings().database_url.get_secret_value()
    )
    return {
        "mode": "local_unpublished",
        "spec": spec.model_dump(mode="json"),
        "layout": layout.model_dump(mode="json"),
        "svg_base64": base64.b64encode(data).decode(),
    }


@router.get(PREFIX + "/{template}/generations", response_model=GenerationPage)
def generations(
    template: DiagramTemplate,
    access: A,
    factory: F,
    runtime: R,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: Annotated[str | None, Query(max_length=4096)] = None,
) -> GenerationPage:
    return factory().history(
        access.record, template, access.actor, runtime, access.role, limit, cursor
    )


def prepared(
    access: Access, template: DiagramTemplate, generation: UUID, service: DiagramService
) -> PreparedDiagram:
    return service.prepared(access.record, template, generation)


def byte_response(data: bytes, media: str, name: str | None = None) -> Response:
    headers = {
        "Content-Digest": "sha-256=:"
        + base64.b64encode(hashlib.sha256(data).digest()).decode()
        + ":",
        "ETag": '"' + hashlib.sha256(data).hexdigest() + '"',
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    }
    if name:
        headers["Content-Disposition"] = 'attachment; filename="' + name + '"'
    return Response(data, media_type=media, headers=headers)


@router.get(EXACT + "/spec", response_model=DiagramSpec)
def spec(
    template: DiagramTemplate, generation: UUID, access: A, factory: F, request: Request
) -> Response:
    if request.headers.get("range") is not None:
        raise ValueError("diagram_range_unsupported")
    value = prepared(access, template, generation, factory())
    return byte_response(value.spec.to_bytes(), "application/json")


@router.get(EXACT + "/layout", response_model=LayoutSpec)
def layout(
    template: DiagramTemplate, generation: UUID, access: A, factory: F, request: Request
) -> Response:
    if request.headers.get("range") is not None:
        raise ValueError("diagram_range_unsupported")
    value = prepared(access, template, generation, factory())
    return byte_response(value.layout.to_bytes(), "application/json")


async def view_body(request: Request) -> DiagramViewRequest:
    try:
        return DiagramViewRequest.from_bytes(await request.body(), max_bytes=131072)
    except ValueError as exc:
        raise ValueError("diagram_input_invalid") from exc


def view_body_schema() -> dict[str, Any]:
    schema = DiagramViewRequest.model_json_schema()
    definitions = schema.pop("$defs", {})

    def inline(value: Any) -> Any:
        if isinstance(value, dict):
            if "$ref" in value:
                return inline(definitions[value["$ref"].split("/")[-1]])
            return {k: inline(v) for k, v in value.items()}
        if isinstance(value, list):
            return [inline(v) for v in value]
        return value

    result = inline(schema)
    assert isinstance(result, dict)
    return result


@router.post(
    EXACT + "/view",
    response_model=DiagramViewResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": view_body_schema()}},
        }
    },
)
def view(
    template: DiagramTemplate,
    generation: UUID,
    body: Annotated[DiagramViewRequest, Depends(view_body)],
    access: A,
    factory: F,
) -> DiagramViewResponse:
    service = factory()
    if len(body.to_bytes()) > service.limits.max_api_body_bytes:
        raise ValueError("diagram_limit_exceeded")
    return service.view(access.record, template, generation, body)


@router.get(EXACT + "/members", response_model=MemberPage)
def members(
    template: DiagramTemplate,
    generation: UUID,
    access: A,
    factory: F,
    group_id: Annotated[str | None, Query(max_length=67)] = None,
    entity_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: Annotated[str | None, Query(max_length=4096)] = None,
) -> MemberPage:
    return factory().members(
        access.record,
        template,
        generation,
        access.actor,
        group_id,
        entity_id,
        limit,
        cursor,
    )


@router.get(
    EXACT + "/export",
    response_model=PreparedDiagram,
    responses={
        200: {
            "content": {
                "image/svg+xml": {"schema": {"type": "string", "format": "binary"}}
            }
        }
    },
)
def export(
    template: DiagramTemplate,
    generation: UUID,
    request: Request,
    access: A,
    factory: F,
    format: Literal["json", "svg"] = "json",
) -> Response:
    if request.headers.get("range") is not None:
        raise ValueError("diagram_range_unsupported")
    service = factory()
    with metadata_operation(monotonic() + service.limits.read_seconds):
        if format == "json":
            value = prepared(access, template, generation, service)
            data = canonical_bytes(value)
            media = "application/json"
        else:
            ref = service.exact_reference(access.record, template, generation)
            value, data = service.reader.read_verified(ref.scope, ref)
            media = "image/svg+xml"
        service.reader.store.authority.recheck(
            value.descriptor.reference.scope, value.descriptor.reference
        )
        return byte_response(
            data, media, f"diagram-{template.value}-{generation}.{format}"
        )
