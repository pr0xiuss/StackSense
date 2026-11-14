"""P4-D1 graph API application service and status read adapter."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.platform.graph.api_contracts import (
    GraphApiError,
    GraphApiInternalError,
    GraphLifecycleUnavailableError,
    GraphRebuildConflictError,
    ProjectionAttemptSummary,
    ProjectionRebuildAcceptedResponse,
    ProjectionStatusResponse,
)
from backend.platform.graph.lifecycle import GraphProjectionLifecycle
from backend.platform.graph.model import (
    ACTIVE_ATTEMPT_STATES,
    PROJECTION_TYPE,
    ProjectionCounts,
)
from backend.platform.graph.persistence import (
    GraphProjectionAttemptModel,
    GraphProjectionResourceModel,
)
from backend.platform.graph.query_contracts import GraphProjectionNotFoundError
from backend.platform.graph.repository import GraphLifecycleStateError


class GraphProjectionStatusReader(Protocol):
    """Read-only port for exact-scope projection status queries."""

    def get_status(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        projection_type: str = PROJECTION_TYPE,
    ) -> ProjectionStatusResponse | None:
        """Return the coherent status snapshot or None if out of scope."""
        ...


class SqlAlchemyGraphProjectionStatusReader:
    """PostgreSQL implementation of the single-statement status reader.

    Reads the exact scoped GraphProjectionResourceModel left-joining its
    active QUEUED, RUNNING, or RETRYING attempt in one statement snapshot.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_status(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        projection_type: str = PROJECTION_TYPE,
    ) -> ProjectionStatusResponse | None:
        active_states = tuple(state.value for state in ACTIVE_ATTEMPT_STATES)
        statement = (
            select(GraphProjectionResourceModel, GraphProjectionAttemptModel)
            .outerjoin(
                GraphProjectionAttemptModel,
                (
                    GraphProjectionAttemptModel.resource_id
                    == GraphProjectionResourceModel.id
                )
                & (GraphProjectionAttemptModel.state.in_(active_states)),
            )
            .where(
                GraphProjectionResourceModel.project_id == project_id,
                GraphProjectionResourceModel.architecture_version_id
                == architecture_version_id,
                GraphProjectionResourceModel.projection_type == projection_type,
            )
        )

        row = self._session.execute(statement).first()
        if row is None:
            return None

        resource, attempt = row

        counts: ProjectionCounts | None = None
        if resource.active_entity_count is not None:
            counts = ProjectionCounts(
                entities=resource.active_entity_count,
                relationships=resource.active_relationship_count or 0,
                evidence=resource.active_evidence_count or 0,
                unresolved=resource.active_unresolved_count or 0,
                conflicts=resource.active_conflict_count or 0,
            )

        active_attempt: ProjectionAttemptSummary | None = None
        last_attempt_at: datetime | None = None
        if attempt is not None:
            last_attempt_at = attempt.created_at
            active_attempt = ProjectionAttemptSummary(
                attempt_id=attempt.id,
                attempt_number=attempt.attempt_number,
                status=attempt.state,
                created_at=attempt.created_at,
                updated_at=attempt.updated_at,
                completed_at=attempt.completed_at,
            )

        return ProjectionStatusResponse(
            resource_id=resource.id,
            project_id=resource.project_id,
            architecture_version_id=resource.architecture_version_id,
            projection_type=resource.projection_type,
            status=resource.state,
            active_generation_id=resource.active_generation_id,
            schema_version=resource.active_graph_schema_version,
            projector_version=resource.active_projector_version,
            counts=counts,
            last_failure_code=resource.last_failure_code,
            created_at=resource.created_at,
            updated_at=resource.updated_at,
            last_attempt_at=last_attempt_at,
            active_attempt=active_attempt,
        )


class GraphApiService:
    """Thin facade composing graph status queries and rebuild transactions."""

    def __init__(
        self,
        status_reader: GraphProjectionStatusReader,
        lifecycle: GraphProjectionLifecycle | None = None,
        commit_fn: Callable[[], None] | None = None,
        rollback_fn: Callable[[], None] | None = None,
    ) -> None:
        self._status_reader = status_reader
        self._lifecycle = lifecycle
        self._commit_fn = commit_fn
        self._rollback_fn = rollback_fn

    def get_status(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        projection_type: str = PROJECTION_TYPE,
    ) -> ProjectionStatusResponse | None:
        """Retrieve projection status for the exact scoped architecture version."""
        return self._status_reader.get_status(
            project_id=project_id,
            architecture_version_id=architecture_version_id,
            projection_type=projection_type,
        )

    def request_rebuild(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        actor_id: UUID,
        actor_role: str,
        correlation_id: str,
        projection_type: str = PROJECTION_TYPE,
    ) -> ProjectionRebuildAcceptedResponse:
        """Request a durable rebuild attempt in the current request transaction."""
        if self._lifecycle is None:
            raise GraphLifecycleUnavailableError(
                "Graph lifecycle service is not configured."
            )

        status = self._status_reader.get_status(
            project_id=project_id,
            architecture_version_id=architecture_version_id,
            projection_type=projection_type,
        )
        if status is None:
            raise GraphProjectionNotFoundError(
                "Graph projection resource not found for the requested version."
            )

        try:
            attempt, _ = self._lifecycle.request_rebuild(
                status.resource_id,
                actor_id=actor_id,
                actor_role=actor_role,
                correlation_id=correlation_id,
            )
            post_status = self._status_reader.get_status(
                project_id=project_id,
                architecture_version_id=architecture_version_id,
                projection_type=projection_type,
            )
            if self._commit_fn is not None:
                self._commit_fn()
        except GraphLifecycleStateError as exc:
            if self._rollback_fn is not None:
                self._rollback_fn()
            raise GraphRebuildConflictError(
                "Graph projection rebuild conflict"
            ) from exc
        except SQLAlchemyError as exc:
            if self._rollback_fn is not None:
                self._rollback_fn()
            raise GraphLifecycleUnavailableError(
                "Graph lifecycle database operation failed."
            ) from exc
        except GraphApiError:
            if self._rollback_fn is not None:
                self._rollback_fn()
            raise
        except Exception as exc:
            if self._rollback_fn is not None:
                self._rollback_fn()
            raise GraphApiInternalError("Internal graph API error") from exc

        if post_status is not None and post_status.active_attempt is not None:
            return ProjectionRebuildAcceptedResponse(
                resource_id=post_status.resource_id,
                architecture_version_id=post_status.architecture_version_id,
                status=post_status.status,
                attempt_id=post_status.active_attempt.attempt_id,
                attempt_number=post_status.active_attempt.attempt_number,
                attempt_status=post_status.active_attempt.status,
                accepted_at=post_status.active_attempt.created_at,
            )

        attempt_status_val = (
            attempt.state.value
            if hasattr(attempt.state, "value")
            else str(attempt.state)
        )
        return ProjectionRebuildAcceptedResponse(
            resource_id=status.resource_id,
            architecture_version_id=architecture_version_id,
            status=post_status.status if post_status else status.status,
            attempt_id=attempt.id,
            attempt_number=attempt.attempt_number,
            attempt_status=attempt_status_val,
            accepted_at=attempt.created_at,
        )
