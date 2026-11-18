"""P5 delivery read/retry boundary; delegated RBAC remains authoritative."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from backend.platform.analysis.application.dependencies import (
    DelegatedRequestContext,
    get_architecture_query_service,
    get_delegated_context,
    require_delegated_project,
)
from backend.platform.analysis.architecture.service import ArchitectureQueryService
from backend.platform.delivery.api_contracts import (
    DeliveryApiError,
    DeliveryErrorResponse,
    DeliverySummary,
    RetryAccepted,
    RetryRequest,
)
from backend.platform.delivery.contracts import DeliveryContractError
from backend.platform.delivery.dependencies import (
    build_delivery_coordinator,
    get_delivery_reader,
)
from backend.platform.delivery.model import Eligibility
from backend.platform.delivery.service import DeliveryCoordinator
from backend.platform.delivery.source import PublishedVersionReader
from backend.platform.delivery_composition import get_output_handler_registry
from backend.platform.errors import AnalysisAccessDeniedError

router = APIRouter(tags=["Delivery"])
ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    code: {"model": DeliveryErrorResponse} for code in (401, 403, 404, 409, 503)
}


def get_delivery_coordinator() -> DeliveryCoordinator | None:
    from backend.platform.config import get_settings
    from backend.platform.dependency_injection import get_database_engine
    from backend.worker.celery_app import celery_app

    try:
        return build_delivery_coordinator(
            get_database_engine(),
            get_settings(),
            celery_app,
            registry=get_output_handler_registry(),
        )
    except ValueError, SQLAlchemyError:
        logging.getLogger(__name__).warning(
            "delivery_runtime_configuration_unavailable"
        )
        return None


@contextmanager
def _errors() -> Iterator[None]:
    try:
        yield
    except SQLAlchemyError as exc:
        raise DeliveryApiError("delivery_persistence_unavailable", 503) from exc
    except (DeliveryContractError, ValidationError) as exc:
        raise DeliveryApiError("delivery_prerequisite_conflict") from exc


def _error_response(exc: DeliveryApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={
            "error": {
                "code": exc.code,
                "message": "Delivery operation could not be completed.",
                "details": {},
            }
        },
    )


@router.get(
    "/architecture-versions/{version_id}/delivery",
    response_model=DeliverySummary,
    responses=ERROR_RESPONSES,
)
def delivery_status(
    version_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    versions: Annotated[
        ArchitectureQueryService, Depends(get_architecture_query_service)
    ],
    reader: Annotated[PublishedVersionReader, Depends(get_delivery_reader)],
    runtime: Annotated[DeliveryCoordinator | None, Depends(get_delivery_coordinator)],
) -> DeliverySummary | JSONResponse:
    require_delegated_project(context, project_id)
    try:
        with _errors():
            record = versions.get_version(version_id, project_id)
            known = runtime.scope_for_record(record) if runtime is not None else None
            if known is not None and runtime is not None:
                return runtime.summary(known, context.role)
            inspection = reader.inspect_requested(record)
            if runtime is None:
                return DeliverySummary(
                    scope=inspection.scope,
                    eligibility="NOT_SCHEDULED",
                    capabilities=("runtime_unavailable",),
                )
            return runtime.summary(inspection.scope, context.role)
    except DeliveryApiError as exc:
        return _error_response(exc)


@router.post(
    "/architecture-versions/{version_id}/delivery/retry",
    response_model=RetryAccepted,
    status_code=202,
    responses=ERROR_RESPONSES,
)
def retry_delivery(
    version_id: UUID,
    project_id: UUID,
    body: RetryRequest,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    versions: Annotated[
        ArchitectureQueryService, Depends(get_architecture_query_service)
    ],
    reader: Annotated[PublishedVersionReader, Depends(get_delivery_reader)],
    runtime: Annotated[DeliveryCoordinator | None, Depends(get_delivery_coordinator)],
) -> RetryAccepted | JSONResponse:
    require_delegated_project(context, project_id)
    if context.actor_id is None or context.role not in {"OWNER", "ADMIN"}:
        raise AnalysisAccessDeniedError("Delivery retry requires OWNER or ADMIN.")
    try:
        with _errors():
            inspection = reader.inspect_requested(
                versions.get_version(version_id, project_id)
            )
            if inspection.eligibility != Eligibility.ELIGIBLE:
                raise DeliveryApiError("delivery_prerequisite_conflict")
            if runtime is None:
                raise DeliveryApiError("delivery_runtime_unavailable", 503)
            return runtime.retry(inspection.scope, body, context.actor_id, context.role)
    except DeliveryApiError as exc:
        return _error_response(exc)
