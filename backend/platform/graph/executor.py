"""P4-W1 projection execution coordinator, short PG units of work, and cleanup."""

from __future__ import annotations

import logging
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform.config import Settings
from backend.platform.dependency_injection import get_database_engine
from backend.platform.graph.lifecycle import GraphProjectionLifecycle
from backend.platform.graph.model import (
    ACTIVE_ATTEMPT_STATES,
    ActivationDisposition,
    ProjectionLease,
)
from backend.platform.graph.persistence import (
    GraphProjectionAttemptModel,
    GraphProjectionResourceModel,
    SqlAlchemyGraphProjectionRepository,
)
from backend.platform.graph.projection import (
    ProjectionCapacityExceededError,
    ProjectionContractError,
    ProjectionError,
    build_projection_plan,
)
from backend.platform.graph.projection_store import (
    ProjectionStore,
    ProjectionStoreUnavailableError,
    StaleFenceError,
)
from backend.platform.graph.queue import ProjectionWorkPayload
from backend.platform.graph.source import SqlAlchemyPublishedArchitectureSource
from backend.platform.graph.verification import (
    GRAPH_INTERNAL_ERROR,
    GRAPH_WRITE_UNAVAILABLE,
    PROJECTION_SOURCE_MISSING,
    GraphVerifier,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProjectionExecutionResult:
    """Deterministic result summary from a projection execution attempt."""

    status: str  # "completed", "failed", "fenced", "skipped"
    generation_id: UUID | None = None
    disposition: ActivationDisposition | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    transient: bool = False
    reason: str | None = None
    execution_duration_seconds: float = 0.0
    transform_duration_seconds: float = 0.0
    write_duration_seconds: float = 0.0
    verify_duration_seconds: float = 0.0
    nodes_written: int = 0
    relationships_written: int = 0


@dataclass(frozen=True, slots=True)
class CleanupResult:
    """Safe summary from an identifier-only bounded cleanup evaluation."""

    eligible: bool
    generation_id: UUID
    reason: str | None = None
    deleted_count: int = 0


class ProjectionExecutor:
    """P4-W1 projection executor coordinating transformation, Neo4j, and M1."""

    def __init__(
        self,
        *,
        settings: Settings,
        store: ProjectionStore,
        verifier: GraphVerifier,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._verifier = verifier
        self._session_factory = session_factory or (
            lambda: Session(get_database_engine())
        )

    def execute(
        self,
        payload: ProjectionWorkPayload,
        *,
        worker_id: str | None = None,
    ) -> ProjectionExecutionResult:
        """Execute one projection attempt using short PG transactions."""
        start_time = time.monotonic()
        actual_worker_id = worker_id or socket.gethostname()
        lease_duration = timedelta(seconds=self._settings.graph_lease_duration_seconds)

        # ------------------------------------------------------------------
        # Unit of Work 1: Acquire lease and load source document
        # ------------------------------------------------------------------
        with self._session_factory() as session:
            repo = SqlAlchemyGraphProjectionRepository(session)
            lifecycle = GraphProjectionLifecycle(repo)
            source = SqlAlchemyPublishedArchitectureSource(session)

            lease = lifecycle.acquire(
                payload,
                worker_id=actual_worker_id,
                lease_duration=lease_duration,
            )
            if lease is None:
                logger.info(
                    "Projection claim %s skipped: lease not acquired",
                    payload.attempt_id,
                )
                return ProjectionExecutionResult(
                    status="skipped",
                    reason="lease_unavailable",
                    generation_id=payload.generation_id,
                    execution_duration_seconds=time.monotonic() - start_time,
                )

            resource = repo.get_resource(payload.projection_id)
            attempt = repo.get_attempt(payload.attempt_id)
            if resource is None or attempt is None:
                raise RuntimeError("Projection resource or attempt not found")

            doc = source.load_exact(payload.architecture_version_id, payload.project_id)
            session.commit()

        # Check source document existence
        if doc is None:
            return self._record_pre_verification_failure(
                lease=lease,
                failure_code=PROJECTION_SOURCE_MISSING,
                failure_message=(
                    f"Architecture version '{payload.architecture_version_id}' "
                    "document was not found."
                ),
                transient=False,
                start_time=start_time,
            )

        # Validate source content digest
        if doc.content_digest != resource.source_content_digest:
            return self._record_pre_verification_failure(
                lease=lease,
                failure_code="projection_source_mismatch",
                failure_message=(
                    "Source content digest does not match resource expected digest."
                ),
                transient=False,
                start_time=start_time,
            )

        # ------------------------------------------------------------------
        # Transform: Build immutable projection plan in-memory
        # ------------------------------------------------------------------
        t_trans_start = time.monotonic()
        try:
            plan = build_projection_plan(
                doc,
                generation_id=payload.generation_id,
                expected_counts=attempt.expected_counts,
                max_projected_properties_bytes=(
                    self._settings.graph_projection_max_projected_properties_bytes
                ),
                max_meta_key_bytes=self._settings.graph_projection_max_meta_key_bytes,
                max_meta_string_bytes=(
                    self._settings.graph_projection_max_meta_string_bytes
                ),
                max_meta_list_items=(
                    self._settings.graph_projection_max_meta_list_items
                ),
                max_meta_record_bytes=(
                    self._settings.graph_projection_max_meta_record_bytes
                ),
            )
        except ProjectionCapacityExceededError as exc:
            return self._record_pre_verification_failure(
                lease=lease,
                failure_code="projection_capacity_exceeded",
                failure_message=str(exc),
                transient=False,
                start_time=start_time,
            )
        except ProjectionContractError as exc:
            return self._record_pre_verification_failure(
                lease=lease,
                failure_code=exc.code or "projection_contract_mismatch",
                failure_message=str(exc),
                transient=False,
                start_time=start_time,
            )
        except ProjectionError as exc:
            return self._record_pre_verification_failure(
                lease=lease,
                failure_code=exc.code or "projection_contract_mismatch",
                failure_message=str(exc),
                transient=False,
                start_time=start_time,
            )
        except Exception:
            return self._record_pre_verification_failure(
                lease=lease,
                failure_code=GRAPH_INTERNAL_ERROR,
                failure_message="Failed to build projection plan.",
                transient=False,
                start_time=start_time,
            )
        t_trans = time.monotonic() - t_trans_start

        # ------------------------------------------------------------------
        # Neo4j Operations: Bounded writes with periodic lease checkpoints
        # ------------------------------------------------------------------
        t_write_start = time.monotonic()
        last_heartbeat = time.monotonic()
        heartbeat_interval = self._settings.graph_heartbeat_interval_seconds

        try:
            # 1. Claim candidate manifest
            self._store.claim_candidate(
                project_id=payload.project_id,
                architecture_version_id=payload.architecture_version_id,
                generation_id=payload.generation_id,
                resource_id=payload.projection_id,
                attempt_id=payload.attempt_id,
                lease_token=lease.token,
                source_content_digest=plan.source_content_digest,
                expected_counts=plan.expected_counts,
                expected_key_set_digest=plan.key_set_digest,
                expected_endpoint_digest=plan.endpoint_digest,
                expected_payload_digest=plan.payload_digest,
                expected_evidence_summary_digest=plan.evidence_summary_digest,
                expected_unresolved_summary_digest=plan.unresolved_summary_digest,
                expected_conflict_summary_digest=plan.conflict_summary_digest,
            )

            # 2. Reset any candidate elements from previous attempts of same generation
            self._store.reset_candidate(
                project_id=payload.project_id,
                architecture_version_id=payload.architecture_version_id,
                generation_id=payload.generation_id,
                lease_token=lease.token,
                page_size=self._settings.graph_projection_cleanup_page_size,
            )

            # 3. Write nodes in bounded pages
            node_batch_size = self._settings.graph_projection_node_batch_size
            for i in range(0, len(plan.nodes), node_batch_size):
                batch = plan.nodes[i : i + node_batch_size]
                self._store.write_nodes(
                    project_id=payload.project_id,
                    architecture_version_id=payload.architecture_version_id,
                    generation_id=payload.generation_id,
                    lease_token=lease.token,
                    nodes=batch,
                    batch_size=node_batch_size,
                )
                if time.monotonic() - last_heartbeat >= heartbeat_interval:
                    lease = self._refresh_lease(lease)
                    last_heartbeat = time.monotonic()

            # 4. Write relationships in bounded pages
            rel_batch_size = self._settings.graph_projection_relationship_batch_size
            for i in range(0, len(plan.relationships), rel_batch_size):
                rel_batch = plan.relationships[i : i + rel_batch_size]
                self._store.write_relationships(
                    project_id=payload.project_id,
                    architecture_version_id=payload.architecture_version_id,
                    generation_id=payload.generation_id,
                    lease_token=lease.token,
                    relationships=rel_batch,
                    batch_size=rel_batch_size,
                )
                if time.monotonic() - last_heartbeat >= heartbeat_interval:
                    lease = self._refresh_lease(lease)
                    last_heartbeat = time.monotonic()

        except StaleFenceError as exc:
            logger.exception("Write StaleFenceError: %s", exc)
            return ProjectionExecutionResult(
                status="fenced",
                reason="stale_fence",
                generation_id=payload.generation_id,
                execution_duration_seconds=time.monotonic() - start_time,
            )
        except ProjectionStoreUnavailableError:
            return self._record_pre_verification_failure(
                lease=lease,
                failure_code=GRAPH_WRITE_UNAVAILABLE,
                failure_message="Neo4j write failed or unavailable.",
                transient=True,
                start_time=start_time,
            )
        except Exception:
            return self._record_pre_verification_failure(
                lease=lease,
                failure_code=GRAPH_INTERNAL_ERROR,
                failure_message="Unexpected error during Neo4j projection write.",
                transient=False,
                start_time=start_time,
            )

        t_write = time.monotonic() - t_write_start

        # ------------------------------------------------------------------
        # Independent Read-Back Verification in Fresh Read Session
        # ------------------------------------------------------------------
        t_verify_start = time.monotonic()
        try:
            verification_result = self._verifier.verify_candidate(
                plan=plan,
                lease_token=lease.token,
                resource_id=payload.projection_id,
                attempt_id=payload.attempt_id,
                projection_contract_version=payload.contract_version,
            )
        except StaleFenceError:
            return ProjectionExecutionResult(
                status="fenced",
                reason="stale_fence",
                generation_id=payload.generation_id,
                execution_duration_seconds=time.monotonic() - start_time,
            )
        except ProjectionStoreUnavailableError:
            return self._record_pre_verification_failure(
                lease=lease,
                failure_code=GRAPH_WRITE_UNAVAILABLE,
                failure_message="Neo4j unavailable during read-back verification.",
                transient=True,
                start_time=start_time,
            )
        except Exception as exc:
            logger.exception("Unexpected verification error: %s", exc)
            return self._record_pre_verification_failure(
                lease=lease,
                failure_code=GRAPH_INTERNAL_ERROR,
                failure_message="Unexpected error during read-back verification.",
                transient=False,
                start_time=start_time,
            )
        t_verify = time.monotonic() - t_verify_start

        receipt = verification_result.to_receipt(
            resource_id=payload.projection_id,
            attempt_id=payload.attempt_id,
            generation_id=payload.generation_id,
            project_id=payload.project_id,
            architecture_version_id=payload.architecture_version_id,
            lease_owner=lease.worker_id,
            lease_token=lease.token,
            contract_version=payload.contract_version,
            source_content_digest=plan.source_content_digest,
        )

        # ------------------------------------------------------------------
        # Unit of Work 2: Complete verification through M1 activate(receipt)
        # ------------------------------------------------------------------
        with self._session_factory() as session:
            repo = SqlAlchemyGraphProjectionRepository(session)
            lifecycle = GraphProjectionLifecycle(repo)
            activation = lifecycle.activate(receipt)
            session.commit()

        status = (
            "completed"
            if activation.disposition
            in (
                ActivationDisposition.ACTIVATED,
                ActivationDisposition.ALREADY_ACTIVATED,
            )
            else "failed"
        )
        return ProjectionExecutionResult(
            status=status,
            generation_id=payload.generation_id,
            disposition=activation.disposition,
            failure_code=activation.attempt.failure_code,
            failure_message=activation.attempt.failure_message,
            transient=False,
            execution_duration_seconds=time.monotonic() - start_time,
            transform_duration_seconds=t_trans,
            write_duration_seconds=t_write,
            verify_duration_seconds=t_verify,
            nodes_written=len(plan.nodes),
            relationships_written=len(plan.relationships),
        )

    def cleanup_generation(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        force: bool = False,
    ) -> CleanupResult:
        """Perform identifier-only bounded cleanup if generation is eligible."""
        now = datetime.now(UTC)

        with self._session_factory() as session:
            attempt_row = session.scalars(
                select(GraphProjectionAttemptModel).where(
                    GraphProjectionAttemptModel.generation_id == generation_id
                )
            ).first()

            if attempt_row is None:
                return CleanupResult(
                    eligible=False,
                    generation_id=generation_id,
                    reason="attempt_not_found",
                )

            resource_row = session.scalars(
                select(GraphProjectionResourceModel).where(
                    GraphProjectionResourceModel.id == attempt_row.resource_id
                )
            ).first()

            if resource_row is None:
                return CleanupResult(
                    eligible=False,
                    generation_id=generation_id,
                    reason="resource_not_found",
                )

            # Assert scope match
            if (
                resource_row.project_id != project_id
                or resource_row.architecture_version_id != architecture_version_id
            ):
                return CleanupResult(
                    eligible=False,
                    generation_id=generation_id,
                    reason="scope_mismatch",
                )

            # Never delete active generation
            if resource_row.active_generation_id == generation_id:
                return CleanupResult(
                    eligible=False,
                    generation_id=generation_id,
                    reason="active_generation",
                )

            # Never delete generation with active attempt
            if attempt_row.state in ACTIVE_ATTEMPT_STATES:
                return CleanupResult(
                    eligible=False,
                    generation_id=generation_id,
                    reason="attempt_active",
                )

            # Verify grace period unless forced
            if not force:
                grace_seconds = self._settings.graph_projection_cleanup_grace_seconds
                updated_at = attempt_row.updated_at
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=UTC)
                age = (now - updated_at).total_seconds()
                if age < grace_seconds:
                    return CleanupResult(
                        eligible=False,
                        generation_id=generation_id,
                        reason="grace_period_not_elapsed",
                    )

        # Eligible! Delete generation elements in bounded pages
        page_size = self._settings.graph_projection_cleanup_page_size
        deleted_count = self._store.delete_generation(
            project_id=project_id,
            architecture_version_id=architecture_version_id,
            generation_id=generation_id,
            batch_size=page_size,
        )
        return CleanupResult(
            eligible=True,
            generation_id=generation_id,
            deleted_count=deleted_count,
        )

    def _refresh_lease(self, lease: ProjectionLease) -> ProjectionLease:
        """Checkpoint worker lease in a short PG transaction."""
        lease_duration = timedelta(seconds=self._settings.graph_lease_duration_seconds)
        with self._session_factory() as session:
            repo = SqlAlchemyGraphProjectionRepository(session)
            lifecycle = GraphProjectionLifecycle(repo)
            updated = lifecycle.heartbeat(
                lease,
                lease_duration=lease_duration,
            )
            session.commit()
        if updated is None:
            raise StaleFenceError("Lease heartbeat lost or expired during projection")
        return updated

    def _record_pre_verification_failure(
        self,
        *,
        lease: ProjectionLease,
        failure_code: str,
        failure_message: str,
        transient: bool,
        start_time: float,
    ) -> ProjectionExecutionResult:
        """Record pre-verification failure using M1 record_failure."""
        clean_code = failure_code[:100]
        clean_msg = failure_message[:500]

        try:
            with self._session_factory() as session:
                repo = SqlAlchemyGraphProjectionRepository(session)
                lifecycle = GraphProjectionLifecycle(repo)
                lifecycle.record_failure(
                    lease,
                    failure_code=clean_code,
                    failure_message=clean_msg,
                    transient=transient,
                )
                session.commit()
        except Exception:
            logger.exception("Failed to record pre-verification failure in PostgreSQL")

        return ProjectionExecutionResult(
            status="failed",
            generation_id=lease.generation_id,
            failure_code=clean_code,
            failure_message=clean_msg,
            transient=transient,
            execution_duration_seconds=time.monotonic() - start_time,
        )


__all__ = [
    "CleanupResult",
    "ProjectionExecutionResult",
    "ProjectionExecutor",
]
