"""FastAPI HTTP endpoints for Phase 5 Module 3 Controlled Retrieval.

Implements thin, authorized query, context, and evidence endpoints with
delegated RBAC, structured error responses, and no independent authentication
per §7A.8, §7A.10, and §7A.11 of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import Response

from backend.platform.analysis.application.dependencies import (
    DelegatedRequestContext,
    get_delegated_context,
    require_delegated_project,
)
from backend.platform.errors import StackSenseError
from backend.platform.knowledge.context import ContextBuilder
from backend.platform.knowledge.evidence import EvidencePlanner
from backend.platform.knowledge.retrieval import KnowledgeQueryService
from backend.platform.knowledge.retrieval_configuration import RetrievalPolicy
from backend.platform.knowledge.retrieval_contracts import (
    DEFAULT_RETRIEVAL_LIMIT,
    MAX_RETRIEVAL_LIMIT,
    CanonicalFactView,
    CanonicalReadPort,
    ContextBundle,
    ContextRequest,
    Coverage,
    EvidencePage,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    RelationshipView,
    ResolvedSubject,
    RetrievalCapacityExceededError,
    RetrievalCursorExpiredError,
    RetrievalCursorInvalidError,
    RetrievalDeadlineExceededError,
    RetrievalError,
    RetrievalGenerationChangedError,
    RetrievalIntegrityFailedError,
    RetrievalInvalidRequestError,
    RetrievalNotFoundError,
    RetrievalOperation,
    RetrievalPlan,
    RetrievalPrincipal,
    RetrievalUnavailableError,
    SelectionRationale,
    SelectionRationaleCode,
)
from backend.platform.knowledge.retrieval_dependencies import (
    get_canonical_read_port,
    get_evidence_planner,
    get_knowledge_query_service,
    get_retrieval_policy,
)

logger = logging.getLogger(__name__)


def _error_response(
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
    cause: str | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }
    if cause:
        content["error"]["cause"] = cause
    return JSONResponse(status_code=status_code, content=content)


def _handle_retrieval_error(exc: RetrievalError) -> JSONResponse:
    if isinstance(exc, RetrievalNotFoundError):
        return _error_response(exc.code, exc.message, 404, exc.safe_details, exc.cause)
    if isinstance(exc, RetrievalGenerationChangedError):
        return _error_response(exc.code, exc.message, 409, exc.safe_details, exc.cause)
    if isinstance(exc, RetrievalCursorExpiredError):
        return _error_response(exc.code, exc.message, 410, exc.safe_details, exc.cause)
    if isinstance(
        exc,
        (
            RetrievalInvalidRequestError,
            RetrievalCursorInvalidError,
            RetrievalCapacityExceededError,
        ),
    ):
        return _error_response(exc.code, exc.message, 422, exc.safe_details, exc.cause)
    if isinstance(exc, RetrievalUnavailableError):
        return _error_response(exc.code, exc.message, 503, exc.safe_details, exc.cause)
    if isinstance(exc, RetrievalDeadlineExceededError):
        return _error_response(exc.code, exc.message, 504, exc.safe_details, exc.cause)
    if isinstance(exc, RetrievalIntegrityFailedError):
        return _error_response(exc.code, exc.message, 500, exc.safe_details, exc.cause)
    return _error_response(exc.code, exc.message, 400, exc.safe_details, exc.cause)


class RetrievalRoute(APIRoute):
    """Custom APIRoute class ensuring closed error mapping for C3 endpoints."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def bounded_handler(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError as exc:
                logger.error("RequestValidationError: %s", exc.errors())
                return _error_response(
                    "retrieval_invalid_request",
                    "Invalid retrieval request parameters",
                    422,
                )
            except ValidationError:
                return _error_response(
                    "retrieval_invalid_request",
                    "Invalid retrieval payload or schema",
                    422,
                )
            except RetrievalError as exc:
                return _handle_retrieval_error(exc)
            except StackSenseError:
                raise
            except HTTPException:
                raise
            except Exception as exc:
                logger.exception("unhandled_retrieval_route_exception: %s", exc)
                return _error_response(
                    "retrieval_integrity_failed",
                    "Internal retrieval failure",
                    500,
                )

        return bounded_handler


router = APIRouter(tags=["Controlled Retrieval"], route_class=RetrievalRoute)


@router.post(
    "/architecture-versions/{version_id}/knowledge/query",
    response_model=KnowledgeQueryResponse,
    status_code=200,
)
def query_architecture_knowledge(
    version_id: UUID,
    project_id: UUID,
    request: KnowledgeQueryRequest,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    query_service: Annotated[
        KnowledgeQueryService, Depends(get_knowledge_query_service)
    ],
    canonical_port: Annotated[CanonicalReadPort, Depends(get_canonical_read_port)],
) -> KnowledgeQueryResponse:
    """Execute a controlled retrieval operation for architecture subjects."""
    require_delegated_project(context, project_id)
    if context.actor_id is None:
        raise RetrievalInvalidRequestError(
            "Non-null actor is required for retrieval",
            safe_details={"project_id": str(project_id)},
        )

    if (
        request.project_id != project_id
        or request.architecture_version_id != version_id
    ):
        raise RetrievalInvalidRequestError(
            "Request scope does not match route parameters",
            safe_details={
                "expected_scope": f"{project_id}/{version_id}",
                "actual_scope": (
                    f"{request.project_id}/{request.architecture_version_id}"
                ),
            },
        )

    # Verify version existence and ownership
    canonical_port.get_version(version_id, project_id)

    principal = RetrievalPrincipal(
        actor_id=context.actor_id,
        project_id=project_id,
        role=context.role,
        correlation_id=context.correlation_id,
    )
    return query_service.query(request, principal=principal)


@router.post(
    "/architecture-versions/{version_id}/knowledge/context",
    response_model=ContextBundle,
    status_code=200,
)
def assemble_retrieval_context(
    version_id: UUID,
    project_id: UUID,
    body: ContextRequest,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    query_service: Annotated[
        KnowledgeQueryService, Depends(get_knowledge_query_service)
    ],
    canonical_port: Annotated[CanonicalReadPort, Depends(get_canonical_read_port)],
    evidence_planner: Annotated[EvidencePlanner, Depends(get_evidence_planner)],
    policy: Annotated[RetrievalPolicy, Depends(get_retrieval_policy)],
) -> ContextBundle:
    """Assemble an immutable ContextBundle for specified subjects and operations."""
    require_delegated_project(context, project_id)
    if context.actor_id is None:
        raise RetrievalInvalidRequestError(
            "Non-null actor is required for context assembly",
            safe_details={"project_id": str(project_id)},
        )

    if body.project_id != project_id or body.architecture_version_id != version_id:
        raise RetrievalInvalidRequestError(
            "ContextRequest scope does not match route parameters",
            safe_details={
                "expected_scope": f"{project_id}/{version_id}",
                "actual_scope": f"{body.project_id}/{body.architecture_version_id}",
            },
        )

    scope = canonical_port.get_version(version_id, project_id)
    principal = RetrievalPrincipal(
        actor_id=context.actor_id,
        project_id=project_id,
        role=context.role,
        correlation_id=context.correlation_id,
    )

    all_resolved_subjects: list[ResolvedSubject] = []
    all_facts: list[CanonicalFactView] = []
    all_relationships: list[RelationshipView] = []
    all_rationales: list[SelectionRationale] = []

    # 1. Resolve each subject and query operations
    for subj_sel in body.subjects:
        lookup_req = KnowledgeQueryRequest(
            project_id=project_id,
            architecture_version_id=version_id,
            operation=RetrievalOperation.LOOKUP,
            subject=subj_sel,
            limit=policy.canonical_page_size,
        )
        lookup_resp = query_service.query(lookup_req, principal=principal)
        if lookup_resp.resolved_subject:
            all_resolved_subjects.append(lookup_resp.resolved_subject)
        all_facts.extend(lookup_resp.facts)
        for f in lookup_resp.facts:
            all_rationales.append(
                SelectionRationale(
                    code=SelectionRationaleCode.EXPLICIT_IDENTITY,
                    target_logical_id=f.logical_id,
                    target_kind=f.kind,
                    originating_operation=RetrievalOperation.LOOKUP,
                )
            )

        if (
            RetrievalOperation.RELATIONSHIPS in body.operations
            and lookup_resp.resolved_subject
            and lookup_resp.resolved_subject.selected_logical_id
        ):
            rel_req = KnowledgeQueryRequest(
                project_id=project_id,
                architecture_version_id=version_id,
                operation=RetrievalOperation.RELATIONSHIPS,
                subject=subj_sel,
                limit=policy.canonical_page_size,
            )
            rel_resp = query_service.query(rel_req, principal=principal)
            all_relationships.extend(rel_resp.relationships)
            for r in rel_resp.relationships:
                all_rationales.append(
                    SelectionRationale(
                        code=SelectionRationaleCode.DIRECT_RELATIONSHIP,
                        target_logical_id=r.logical_id,
                        target_kind=r.kind,
                        originating_operation=RetrievalOperation.RELATIONSHIPS,
                    )
                )

    # 2. Plan and resolve evidence, conflicts, and unresolved items
    evidence_res = evidence_planner.plan_evidence(
        version_id=version_id,
        project_id=project_id,
        facts=all_facts,
        relationships=all_relationships,
        include_evidence=body.include_evidence,
        include_conflicts=body.include_conflicts,
        include_unresolved=body.include_unresolved,
    )

    for ev in evidence_res.evidence:
        code = (
            SelectionRationaleCode.CONFLICTING_EVIDENCE
            if ev.polarity == "conflicting"
            else SelectionRationaleCode.SUPPORTING_EVIDENCE
        )
        all_rationales.append(
            SelectionRationale(
                code=code,
                target_logical_id=ev.logical_id,
                target_kind="evidence",
            )
        )

    # 3. Build RetrievalPlan
    request_fingerprint = hashlib.sha256(
        body.model_dump_json().encode("utf-8")
    ).hexdigest()
    plan = RetrievalPlan(
        strategy_version="1.0.0",
        request_fingerprint=request_fingerprint,
        operations=body.operations,
        subjects=body.subjects,
        required_sources=body.required_sources,
        optional_sources=body.optional_sources,
        policy_fingerprint=policy.compute_fingerprint(),
        budget_snapshot={"page_size": policy.canonical_page_size},
    )

    # 4. Assemble ContextBundle
    builder = ContextBuilder(scope=scope, plan=plan, policy=policy)
    return builder.build_bundle(
        source_observations=(),
        resolved_subjects=all_resolved_subjects,
        facts=all_facts,
        relationships=all_relationships,
        evidence=evidence_res.evidence,
        unresolved=evidence_res.unresolved,
        conflicts=evidence_res.conflicts,
        rationales=all_rationales,
        omissions=evidence_res.omissions,
    )


@router.get(
    "/architecture-versions/{version_id}/knowledge/evidence",
    response_model=EvidencePage,
    status_code=200,
)
def get_architecture_evidence_page(
    version_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    canonical_port: Annotated[CanonicalReadPort, Depends(get_canonical_read_port)],
    entity_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[
        int, Query(ge=1, le=MAX_RETRIEVAL_LIMIT)
    ] = DEFAULT_RETRIEVAL_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EvidencePage:
    """Retrieve bounded paginated evidence records for an architecture version."""
    require_delegated_project(context, project_id)
    if context.actor_id is None:
        raise RetrievalInvalidRequestError(
            "Non-null actor is required to read evidence",
            safe_details={"project_id": str(project_id)},
        )

    scope = canonical_port.get_version(version_id, project_id)
    items, total = canonical_port.list_evidence(
        version_id=version_id,
        project_id=project_id,
        limit=limit,
        offset=offset,
        entity_id=entity_id,
    )
    has_more = (offset + len(items)) < total
    coverage = Coverage(
        considered_count=total,
        selected_count=len(items),
        scanned_count=min(total, offset + len(items)),
        count_known=True,
        exhausted=not has_more,
    )

    return EvidencePage(
        scope=scope,
        items=items,
        total_items=total,
        has_more=has_more,
        coverage=coverage,
    )


__all__ = ["router"]
