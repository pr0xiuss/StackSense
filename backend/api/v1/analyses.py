"""Internal lifecycle REST and SSE API endpoints for Analysis execution."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.platform.analysis.application.dependencies import (
    DelegatedRequestContext,
    get_analysis_lifecycle_service,
    get_analysis_repository,
    get_delegated_context,
    get_event_repository,
    get_job_repository,
    get_queue_publisher,
    get_stage_repository,
    require_delegated_project,
    require_operator_role,
)
from backend.platform.analysis.application.dto import (
    AnalysisDiagnosticListResponse,
    AnalysisListResponse,
    AnalysisResponse,
    CancelAnalysisRequest,
    CreateAnalysisRequest,
)
from backend.platform.analysis.application.events import LifecycleEventEmitter
from backend.platform.analysis.application.lifecycle_service import (
    AnalysisLifecycleService,
)
from backend.platform.analysis.domain.constants import (
    AnalysisStatus,
    DiagnosticSeverity,
    JobStatus,
)
from backend.platform.analysis.infra.queue import (
    AnalysisJobPayload,
    AnalysisQueuePublisher,
)
from backend.platform.analysis.repositories.analysis_repo import AnalysisRepository
from backend.platform.analysis.repositories.event_repo import EventRepository
from backend.platform.analysis.repositories.job_repo import (
    JobRepository,
    StageRepository,
)
from backend.platform.dependency_injection import get_database_session
from backend.platform.errors import AnalysisNotFoundError, AnalysisQueueUnavailableError

router = APIRouter(
    prefix="/analyses",
    tags=["Analysis Lifecycle"],
)


@router.post(
    "",
    response_model=AnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_analysis(
    request: CreateAnalysisRequest,
    context: Annotated[DelegatedRequestContext, Depends(require_operator_role)],
    service: Annotated[
        AnalysisLifecycleService, Depends(get_analysis_lifecycle_service)
    ],
    publisher: Annotated[AnalysisQueuePublisher, Depends(get_queue_publisher)],
    analysis_repo: Annotated[AnalysisRepository, Depends(get_analysis_repository)],
    job_repo: Annotated[JobRepository, Depends(get_job_repository)],
    stage_repo: Annotated[StageRepository, Depends(get_stage_repository)],
    event_repo: Annotated[EventRepository, Depends(get_event_repository)],
    session: Annotated[Session, Depends(get_database_session)],
) -> AnalysisResponse:
    """Initiate a new analysis run, persisting initial state and dispatching task."""
    require_delegated_project(context, request.project_id)
    created = service.create_analysis(request)

    # Commit the dispatch-ready state before publishing.  Publishing first lets a
    # fast worker race the API's PENDING -> QUEUED update, lose its RUNNING claim,
    # acknowledge the delivery and strand the analysis forever in QUEUED.
    # QUEUED jobs without a worker lease are recoverable by the periodic dispatcher.
    if created.active_job and created.active_job.status == JobStatus.PENDING.value:
        analysis = analysis_repo.get_by_id(created.id, created.project_id)
        if analysis:
            now = datetime.now(UTC)
            if analysis.status == AnalysisStatus.CREATED:
                queued_analysis = analysis.transition_to(
                    AnalysisStatus.QUEUED, updated_at=now
                )
                analysis_repo.update(queued_analysis, expected_version=analysis.version)
            active_job = job_repo.get_by_id(created.active_job.id)
            if active_job and active_job.status == JobStatus.PENDING:
                queued_job = active_job.transition_to(JobStatus.QUEUED, updated_at=now)
                job_repo.update(queued_job, expected_version=active_job.version)
                LifecycleEventEmitter(event_repo, created.id).emit_queued(active_job.id)
            session.commit()

            payload = AnalysisJobPayload(
                analysis_id=created.id,
                job_id=created.active_job.id,
                project_id=created.project_id,
                correlation_id=context.correlation_id or str(uuid4()),
            )
            try:
                publisher.publish_job(payload)
            except Exception as exc:
                raise AnalysisQueueUnavailableError(
                    details={"analysis_id": str(created.id)}
                ) from exc

            return service.get_analysis(created.id, created.project_id)

    return created


@router.get(
    "",
    response_model=AnalysisListResponse,
    status_code=status.HTTP_200_OK,
)
def list_analyses(
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    service: Annotated[
        AnalysisLifecycleService, Depends(get_analysis_lifecycle_service)
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    analysis_status: Annotated[AnalysisStatus | None, Query(alias="status")] = None,
    repository_id: Annotated[UUID | None, Query()] = None,
) -> AnalysisListResponse:
    """List analyses belonging to a project with pagination."""
    require_delegated_project(context, project_id)
    return service.list_analyses(
        project_id=project_id,
        limit=limit,
        offset=offset,
        status=analysis_status,
        repository_id=repository_id,
    )


@router.get(
    "/{analysis_id}/diagnostics",
    response_model=AnalysisDiagnosticListResponse,
    status_code=status.HTTP_200_OK,
)
def list_analysis_diagnostics(
    analysis_id: UUID,
    project_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    service: Annotated[
        AnalysisLifecycleService, Depends(get_analysis_lifecycle_service)
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    severity: Annotated[DiagnosticSeverity | None, Query()] = None,
    stage: Annotated[str | None, Query()] = None,
) -> AnalysisDiagnosticListResponse:
    """List paginated diagnostics for an analysis run."""
    require_delegated_project(context, project_id)
    return service.list_diagnostics(
        analysis_id=analysis_id,
        project_id=project_id,
        limit=limit,
        offset=offset,
        severity=severity,
        stage=stage,
    )


@router.get(
    "/{analysis_id}",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
)
def get_analysis(
    analysis_id: UUID,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    service: Annotated[
        AnalysisLifecycleService, Depends(get_analysis_lifecycle_service)
    ],
    analysis_repo: Annotated[AnalysisRepository, Depends(get_analysis_repository)],
    project_id: Annotated[UUID | None, Query()] = None,
) -> AnalysisResponse:
    """Retrieve full lifecycle status and progress for an analysis."""
    effective_project_id = project_id or context.project_id
    if effective_project_id is None:
        raise AnalysisNotFoundError(
            message="Project identifier must be provided to retrieve analysis.",
            details={"analysis_id": str(analysis_id)},
        )
    require_delegated_project(context, effective_project_id)
    return service.get_analysis(analysis_id, effective_project_id)


@router.post(
    "/{analysis_id}/cancel",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
)
def cancel_analysis(
    analysis_id: UUID,
    request: CancelAnalysisRequest,
    context: Annotated[DelegatedRequestContext, Depends(require_operator_role)],
    service: Annotated[
        AnalysisLifecycleService, Depends(get_analysis_lifecycle_service)
    ],
    project_id: Annotated[UUID, Query()],
) -> AnalysisResponse:
    """Cancel an active analysis run (direct if queued, cooperative if running)."""
    require_delegated_project(context, project_id)
    return service.cancel_analysis(
        analysis_id=analysis_id,
        project_id=project_id,
        reason=request.reason,
    )


@router.get(
    "/{analysis_id}/events",
    status_code=status.HTTP_200_OK,
)
async def stream_analysis_events(
    analysis_id: UUID,
    project_id: UUID,
    request: Request,
    context: Annotated[DelegatedRequestContext, Depends(get_delegated_context)],
    event_repo: Annotated[EventRepository, Depends(get_event_repository)],
    analysis_repo: Annotated[AnalysisRepository, Depends(get_analysis_repository)],
    after_sequence: Annotated[int, Query(ge=0)] = 0,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """Stream durable lifecycle events via Server-Sent Events (SSE)."""
    require_delegated_project(context, project_id)
    # Verify analysis existence
    analysis = analysis_repo.get_by_id(analysis_id, project_id)
    if analysis is None:
        raise AnalysisNotFoundError(
            message=f"Analysis '{analysis_id}' not found.",
            details={"analysis_id": str(analysis_id)},
        )

    # Determine sequence offset
    start_seq = after_sequence
    if last_event_id:
        try:
            start_seq = max(start_seq, int(last_event_id))
        except ValueError:
            pass

    async def event_generator() -> AsyncGenerator[str]:
        current_seq = start_seq
        while True:
            # Check client disconnection
            if await request.is_disconnected():
                break

            events = event_repo.list_by_analysis(
                analysis_id,
                after_sequence=current_seq,
                limit=100,
            )

            for ev in events:
                data_str = json.dumps(ev.payload)
                msg = (
                    f"id: {ev.sequence_number}\n"
                    f"event: {ev.event_type.value}\n"
                    f"data: {data_str}\n\n"
                )
                yield msg
                current_seq = ev.sequence_number

            # A terminal analysis can have more than one page of unseen events.
            current_analysis = analysis_repo.get_by_id(analysis_id, project_id)
            if current_analysis and current_analysis.is_terminal:
                if not events:
                    break
                continue

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
