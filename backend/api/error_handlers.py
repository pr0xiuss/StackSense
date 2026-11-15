"""StackSense API exception handlers."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.platform.errors import ErrorCategory, StackSenseError
from backend.platform.graph.api_contracts import GraphApiError
from backend.platform.graph.query_contracts import GraphQueryError

GRAPH_ERROR_STATUS_CODES: dict[str, int] = {
    "graph_projection_not_found": 404,
    "graph_projection_not_ready": 409,
    "graph_node_not_found": 404,
    "graph_cursor_invalid": 422,
    "graph_cursor_scope_mismatch": 422,
    "graph_cursor_expired": 410,
    "graph_generation_changed": 409,
    "graph_query_limit_exceeded": 422,
    "graph_query_timeout": 504,
    "graph_unavailable": 503,
    "graph_schema_incompatible": 503,
    "graph_query_integrity_error": 500,
    "graph_rebuild_conflict": 409,
    "graph_lifecycle_unavailable": 503,
    "graph_api_internal_error": 500,
}


def register_exception_handlers(application: FastAPI) -> None:
    """Register StackSense application exception handlers."""
    logger = logging.getLogger(__name__)

    @application.exception_handler(StackSenseError)
    async def handle_stacksense_error(
        request: Request,
        exc: StackSenseError,
    ) -> JSONResponse:
        """Translate an application error into the public API contract."""
        logger.error(
            "application_error",
            extra={
                "error_code": exc.code,
                "error_category": exc.category.value,
                "error_scope": exc.scope.value,
            },
        )

        status_codes = {
            "project_access_already_exists": 409,
            "project_access_not_found": 404,
            "repository_not_found": 404,
            "repository_already_exists": 409,
            "invalid_credentials": 401,
            "authentication_required": 401,
            "invalid_token": 401,
            "token_expired": 401,
            "user_inactive": 401,
            "password_policy_violation": 422,
            "user_already_exists": 409,
            "username_already_exists": 409,
            "invalid_refresh_token": 401,
            "refresh_token_expired": 401,
            "refresh_token_revoked": 401,
            "ingestion_not_found": 404,
            "active_ingestion_exists": 409,
            "invalid_ingestion_state": 409,
            "revision_already_exists": 409,
            "source_validation_failed": 422,
            "storage_operation_failed": 500,
            "invalid_source_type": 422,
            "invalid_github_url": 422,
            "invalid_github_ref": 422,
            "github_repository_not_found": 404,
            "github_acquisition_failed": 502,
            "github_rate_limit_exceeded": 429,
            "github_access_denied": 403,
            "github_network_error": 503,
            "github_timeout": 504,
            "unsupported_archive_format": 422,
            "server_path_not_allowed": 403,
            "server_path_not_found": 404,
            "max_file_count_exceeded": 422,
            # Phase 3 Module 1 Analysis Lifecycle Errors
            "analysis_not_found": 404,
            "analysis_already_exists": 409,
            "analysis_state_conflict": 409,
            "analysis_cancel_not_allowed": 409,
            "analysis_cancelled": 409,
            "analysis_input_invalid": 422,
            "analysis_integrity_violation": 500,
            "analysis_timeout": 504,
            "artifact_content_unavailable": 500,
            "unsupported_capability": 422,
            "analysis_configuration_invalid": 422,
            "analysis_access_denied": 403,
            "analysis_queue_unavailable": 503,
            "architecture_result_not_found": 404,
        }

        status_code = status_codes.get(
            exc.code,
            (
                401
                if exc.category is ErrorCategory.AUTHENTICATION
                else (
                    403
                    if exc.category is ErrorCategory.AUTHORIZATION
                    else 422 if exc.category is ErrorCategory.VALIDATION else 500
                )
            ),
        )

        headers: dict[str, str] = {}
        if exc.category is ErrorCategory.AUTHENTICATION:
            headers["WWW-Authenticate"] = "Bearer"

        return JSONResponse(
            status_code=status_code,
            headers=headers if headers else None,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    def _create_graph_error_response(
        event_name: str,
        code: str,
        message: str,
        details: dict[str, Any],
    ) -> JSONResponse:
        logger.error(
            event_name,
            extra={
                "error_code": code,
            },
        )
        status_code = GRAPH_ERROR_STATUS_CODES.get(code, 500)
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "details": details,
                }
            },
        )

    @application.exception_handler(GraphQueryError)
    async def handle_graph_query_error(
        request: Request,
        exc: GraphQueryError,
    ) -> JSONResponse:
        """Translate safe M3 graph query errors into public API contract."""
        return _create_graph_error_response(
            "graph_query_error",
            exc.code,
            exc.message,
            exc.safe_details,
        )

    @application.exception_handler(GraphApiError)
    async def handle_graph_api_error(
        request: Request,
        exc: GraphApiError,
    ) -> JSONResponse:
        """Translate safe M4 graph API errors into public API contract."""
        return _create_graph_error_response(
            "graph_api_error",
            exc.code,
            exc.message,
            exc.safe_details,
        )
