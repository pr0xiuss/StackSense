"""Exact-version architecture report reads and downloads.

M6 owns the Express/browser gateway relay later. This router provides
strictly authorized internal FastAPI endpoints for report summaries,
exact generation history, bounded PDF streaming, and retry triggering.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Callable, Coroutine, Iterator
from dataclasses import dataclass
from time import monotonic
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.routing import APIRoute
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

from backend.api.v1.delivery import get_delivery_coordinator
from backend.platform.analysis.application.dependencies import (
    DelegatedRequestContext,
    get_architecture_query_service,
    get_delegated_context,
    require_delegated_project,
)
from backend.platform.analysis.architecture.dto import ArchitectureVersionResponse
from backend.platform.analysis.architecture.service import ArchitectureQueryService
from backend.platform.delivery.service import DeliveryCoordinator
from backend.platform.errors import StackSenseError
from backend.platform.reports.api_contracts import (
    ErrorResponse,
    ReportCollection,
    ReportGenerationPage,
    ReportGenerationSummary,
    ReportSummary,
)
from backend.platform.reports.dependencies import (
    get_report_limits,
    get_report_service,
)
from backend.platform.reports.repository import metadata_operation
from backend.platform.reports.service import ReportService

STATUSES: dict[str, int] = {
    "report_authentication_required": 401,
    "report_forbidden": 403,
    "report_not_found": 404,
    "report_not_ready": 409,
    "report_scope_mismatch": 409,
    "report_selection_drift": 409,
    "report_conflict": 409,
    "report_generation_changed": 409,
    "report_cursor_expired": 410,
    "report_range_unsupported": 416,
    "report_cursor_invalid": 400,
    "report_input_invalid": 422,
    "report_contract_unsupported": 409,
    "report_limit_exceeded": 413,
    "report_store_unavailable": 503,
    "report_source_unavailable": 503,
    "report_runtime_unavailable": 503,
    "report_integrity_error": 503,
    "report_timeout": 504,
    "report_internal_error": 500,
}


def error(code: str, details: dict[str, Any] | None = None) -> JSONResponse:
    status = STATUSES.get(code, 500)
    if code not in STATUSES:
        code = "report_internal_error"
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": code.replace("_", " ").capitalize() + ".",
                "details": details
                or {
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


class ReportRoute(APIRoute):
    """Enforces query validation, deadlines, and error envelope mapping."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handle(request: Request) -> Response:
            try:
                limits = get_report_limits()
                request.state.report_deadline = (
                    monotonic() + limits.read_timeout_seconds
                )
                keys = list(request.query_params.keys())
                if any(len(request.query_params.getlist(k)) != 1 for k in keys):
                    return error("report_input_invalid")
                if not set(keys) <= {
                    "project_id",
                    "generation_id",
                    "limit",
                    "cursor",
                }:
                    return error("report_input_invalid")

                with metadata_operation(request.state.report_deadline):
                    async with asyncio.timeout(
                        max(0, request.state.report_deadline - monotonic())
                    ):
                        response = await original(request)

                if monotonic() >= request.state.report_deadline:
                    return error("report_timeout")
                return response
            except RequestValidationError:
                return error("report_input_invalid")
            except ValidationError:
                return error("report_integrity_error")
            except TimeoutError:
                return error("report_timeout")
            except StackSenseError as exc:
                code = exc.code.lower()
                mapped = (
                    "report_authentication_required"
                    if any(x in code for x in ("token", "authentication"))
                    else (
                        "report_forbidden"
                        if any(x in code for x in ("denied", "forbidden"))
                        else (
                            "report_not_found"
                            if "not_found" in code
                            else "report_internal_error"
                        )
                    )
                )
                return error(mapped)
            except ValueError as exc:
                return error(str(exc))
            except SQLAlchemyError, OSError:
                return error("report_store_unavailable")
            except Exception:
                return error("report_internal_error")

        return handle


router = APIRouter(
    tags=["Reports"],
    route_class=ReportRoute,
    responses={
        status: {"model": ErrorResponse}
        for status in (400, 401, 403, 404, 409, 410, 413, 416, 422, 500, 503, 504)
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
        ArchitectureQueryService, Depends(get_architecture_query_service)
    ],
) -> Access:
    require_delegated_project(context, project_id)
    if context.actor_id is None:
        raise ValueError("report_authentication_required")
    if context.role not in {"OWNER", "ADMIN", "DEVELOPER", "VIEWER"}:
        raise ValueError("report_forbidden")
    record = versions.get_version(version_id, project_id)
    return Access(record=record, actor=context.actor_id, role=context.role)


def get_report_service_dependency(
    access: Annotated[Access, Depends(authorize)],
) -> ReportService:
    return get_report_service(actor_id=access.actor)


A = Annotated[Access, Depends(authorize)]
S = Annotated[ReportService, Depends(get_report_service_dependency)]
R = Annotated[DeliveryCoordinator | None, Depends(get_delivery_coordinator)]

PREFIX = "/architecture-versions/{version_id}/reports"
EXACT = PREFIX + "/{report_id}/generations/{generation_id}"


@router.get(PREFIX, response_model=ReportCollection)
def get_reports(
    access: A,
    service: S,
    runtime: R,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(max_length=4096)] = None,
) -> ReportCollection:
    """Return report collection with automatic slot status and persisted resources."""
    return service.collection(
        record=access.record,
        runtime=runtime,
        role=access.role,
        limit=limit,
        cursor=cursor,
    )


@router.get(PREFIX + "/{report_id}", response_model=ReportSummary)
def get_report_summary(
    report_id: UUID,
    access: A,
    service: S,
    runtime: R,
    generation_id: UUID | None = None,
) -> ReportSummary:
    """Return active or exact historical report summary."""
    return service.summary(
        record=access.record,
        report_id=report_id,
        runtime=runtime,
        role=access.role,
        generation_id=generation_id,
    )


@router.get(PREFIX + "/{report_id}/generations", response_model=ReportGenerationPage)
def get_report_generations(
    report_id: UUID,
    access: A,
    service: S,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(max_length=4096)] = None,
) -> ReportGenerationPage:
    """Return paginated history of accepted report generations."""
    return service.generations(
        record=access.record,
        report_id=report_id,
        actor_id=access.actor,
        limit=limit,
        cursor=cursor,
    )


@router.get(EXACT, response_model=ReportGenerationSummary)
def get_report_generation(
    report_id: UUID,
    generation_id: UUID,
    access: A,
    service: S,
) -> ReportGenerationSummary:
    """Return exact historical report generation metadata."""
    return service.generation_detail(
        record=access.record,
        report_id=report_id,
        generation_id=generation_id,
    )


def _download_stream(
    handle: Any,
    pdf_member: Any,
    record: ArchitectureVersionResponse,
    generation_id: UUID,
) -> StreamingResponse:
    def stream_bytes() -> Iterator[bytes]:
        try:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            handle.close()

    raw_sha = bytes.fromhex(pdf_member.sha256)
    b64_digest = base64.b64encode(raw_sha).decode("ascii")
    filename = f"report-architecture-v{record.sequence_number}-{generation_id}.pdf"

    headers = {
        "Content-Type": "application/pdf",
        "Content-Length": str(pdf_member.size_bytes),
        "Content-Digest": f"sha-256=:{b64_digest}:",
        "ETag": f'"{pdf_member.sha256}"',
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return StreamingResponse(
        stream_bytes(),
        media_type="application/pdf",
        headers=headers,
    )


@router.get(
    EXACT + "/download",
    responses={
        200: {
            "content": {
                "application/pdf": {"schema": {"type": "string", "format": "binary"}}
            }
        }
    },
)
def download_report_generation(
    report_id: UUID,
    generation_id: UUID,
    access: A,
    service: S,
    request: Request,
) -> Response:
    """Download verified exact historical generation PDF stream."""
    if request.headers.get("range") is not None:
        raise ValueError("report_range_unsupported")

    handle, pdf_member, record = service.open_pdf(
        record=access.record,
        report_id=report_id,
        generation_id=generation_id,
    )
    return _download_stream(handle, pdf_member, record, generation_id)


__all__ = ["router"]
