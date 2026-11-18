"""Search work handler and execution service.

Implements M1-compatible SearchWorkHandler performing candidate index creation,
bulk indexing, sealing, independent verification, and candidate staging
per §7.4 and §13.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform.analysis.architecture.model import ArchitectureDocument
from backend.platform.delivery.api_contracts import WorkSummary
from backend.platform.delivery.contracts import (
    ArtifactReference,
    AttemptIdentity,
    AttemptRetirementReader,
    CandidateSeal,
    DeliveryContractError,
    DeliveryExecutionFailure,
    DeliveryFailure,
    OutputDigests,
    PreparedOutput,
    RetryClass,
    VersionScope,
    WorkExecutionContext,
    WorkHandler,
)
from backend.platform.knowledge.contracts import (
    CapabilityState,
    SearchBackendUnavailableError,
    SearchCapabilities,
    SearchDeadlineExceededError,
    SearchError,
    SearchFreshness,
    SearchIntegrityError,
    SearchResourceState,
    SearchStatus,
)
from backend.platform.knowledge.elasticsearch import (
    SEARCH_INDEX_MAPPINGS,
    SEARCH_INDEX_SETTINGS,
    SearchIndexBackend,
    compute_mapping_hash,
    compute_settings_hash,
)
from backend.platform.knowledge.model import SearchManifest
from backend.platform.knowledge.persistence import SearchResourceModel
from backend.platform.knowledge.projection import KnowledgeProjector
from backend.platform.knowledge.reader import SearchReader
from backend.platform.knowledge.repository import SqlAlchemySearchRepository
from backend.platform.knowledge.verification import (
    SEAL_PROTOCOL_VERSION,
    VERIFIER_VERSION,
    SearchVerifier,
)


class SearchWorkHandler(WorkHandler):
    """M1-enlisted worker executing search projection and candidate preparation."""

    def __init__(
        self,
        *,
        backend: SearchIndexBackend,
        repository: SqlAlchemySearchRepository,
        document_loader: Callable[[VersionScope], ArchitectureDocument],
        verifier: SearchVerifier | None = None,
        projector: KnowledgeProjector | None = None,
        index_settings: dict[str, object] | None = None,
    ) -> None:
        self._backend = backend
        self._repo = repository
        self._document_loader = document_loader
        self._verifier = verifier or SearchVerifier(backend)
        self._projector = projector or KnowledgeProjector()
        self._index_settings = (
            index_settings if index_settings is not None else SEARCH_INDEX_SETTINGS
        )

    def execute(self, context: WorkExecutionContext) -> PreparedOutput:
        remaining = (context.deadline - datetime.now(UTC)).total_seconds()
        try:
            with self._backend.operation(monotonic() + remaining):
                return self._execute(context)
        except SearchError as exc:
            transient = isinstance(
                exc, (SearchBackendUnavailableError, SearchDeadlineExceededError)
            )
            raise DeliveryExecutionFailure(
                DeliveryFailure(
                    code=exc.code,
                    retry_class=(
                        RetryClass.TRANSIENT if transient else RetryClass.INTEGRITY
                    ),
                    source_capability="search",
                )
            ) from exc

    def _execute(self, context: WorkExecutionContext) -> PreparedOutput:
        """Execute candidate index construction and audit verification."""
        context.control.checkpoint()
        if context.control.should_stop():
            raise DeliveryExecutionFailure(
                DeliveryFailure(
                    code="cooperative_stop_requested",
                    retry_class=RetryClass.TRANSIENT,
                    source_capability="search",
                )
            )

        attempt = context.attempt
        work = attempt.work
        scope = work.scope
        profile = work.binding.profile

        # 1. Resolve canonical ArchitectureDocument
        try:
            document = self._document_loader(scope)
        except Exception as exc:
            raise DeliveryExecutionFailure(
                DeliveryFailure(
                    code="source_document_unavailable",
                    retry_class=RetryClass.TRANSIENT,
                    source_capability="search",
                )
            ) from exc

        # 2. Pure knowledge projection
        projection = self._projector.project(
            document=document,
            scope=scope,
            profile=profile,
        )

        context.control.checkpoint()

        # 3. Create physical candidate index
        generation_id = uuid4()
        artifact_id = uuid4()
        index_name = f"stacksense-search-{scope.project_id.hex}-{generation_id.hex}"
        self._repo.reserve_candidate(attempt, generation_id, artifact_id, index_name)

        try:
            index_uuid = self._backend.create_index(
                index_name=index_name,
                settings=self._index_settings,
                mappings=SEARCH_INDEX_MAPPINGS,
            )
            self._repo.bind_candidate_index(generation_id, attempt, index_uuid)
        except Exception as exc:
            raise DeliveryExecutionFailure(
                DeliveryFailure(
                    code="index_creation_failed",
                    retry_class=RetryClass.TRANSIENT,
                    source_capability="search",
                )
            ) from exc

        # 4. Bulk index documents
        envelopes = [
            r.to_stored_envelope(generation_id=generation_id, index_uuid=index_uuid)
            for r in projection.records
        ]

        bulk_result = self._backend.bulk_index_records(
            index_name=index_name, records=envelopes
        )
        if bulk_result.failed > 0:
            raise DeliveryExecutionFailure(
                DeliveryFailure(
                    code="bulk_indexing_failed",
                    retry_class=RetryClass.TRANSIENT,
                    source_capability="search",
                )
            )

        # 5. Refresh, drain, and seal candidate
        self._backend.refresh_index(index_name)
        try:
            self._backend.drain_and_seal_index(index_name)
        except Exception as exc:
            raise DeliveryExecutionFailure(
                DeliveryFailure(
                    code="index_sealing_failed",
                    retry_class=RetryClass.TRANSIENT,
                    source_capability="search",
                )
            ) from exc

        context.control.checkpoint()

        # 6. Independent candidate verification
        verification = self._verifier.verify(
            scope=scope,
            profile=profile,
            candidate_id=attempt.candidate_id,
            attempt_id=attempt.attempt_id,
            generation_id=generation_id,
            index_name=index_name,
            index_uuid=index_uuid,
            expected_projection=projection,
            expected_settings=self._index_settings,
        )
        if not verification.verified:
            raise DeliveryExecutionFailure(
                DeliveryFailure(
                    code=f"verification_{verification.failure_code}",
                    retry_class=RetryClass.INTEGRITY,
                    source_capability="search",
                )
            )

        # 7. Create SearchManifest and stage in PostgreSQL
        manifest = SearchManifest(
            attempt=attempt,
            c1_version="1.0.0",
            scope=scope,
            profile=profile,
            input_fingerprint=work.input_fingerprint,
            candidate_id=attempt.candidate_id,
            generation_id=generation_id,
            artifact_id=artifact_id,
            index_name=index_name,
            index_uuid=index_uuid,
            settings_hash=compute_settings_hash(self._index_settings),
            mapping_hash=compute_mapping_hash(SEARCH_INDEX_MAPPINGS),
            counts=projection.counts,
            key_set_digest=verification.actual_key_set_digest,
            payload_digest=verification.actual_payload_digest,
            projection_digest=projection.projection_digest,
            verifier_version=VERIFIER_VERSION,
            seal_protocol_version=SEAL_PROTOCOL_VERSION,
            sealed_at=datetime.now(UTC),
        )

        resource = self._repo.ensure_resource(
            project_id=scope.project_id,
            architecture_version_id=scope.architecture_version_id,
        )

        self._repo.stage_candidate(
            resource_id=resource.id,
            project_id=scope.project_id,
            architecture_version_id=scope.architecture_version_id,
            candidate_id=attempt.candidate_id,
            attempt_id=attempt.attempt_id,
            artifact_id=artifact_id,
            generation_id=generation_id,
            index_name=index_name,
            index_uuid=index_uuid,
            counts=projection.counts,
            manifest=manifest,
        )
        # M1 uses a NEW physical transaction for publication. A flush cannot
        # make the sealed descriptor visible to that transaction.
        self._repo.commit_staging()

        context.control.checkpoint()

        seal = CandidateSeal(
            generation_id=generation_id,
            artifact_id=artifact_id,
            size_bytes=manifest.size_bytes(),
            digests=OutputDigests(content=manifest.content_digest()),
            sealed=True,
        )

        return PreparedOutput(
            attempt=attempt,
            candidate=seal,
        )


class SearchStatusService:
    """Read-only service.

    Projects search resource state, freshness, and capabilities.
    """

    def __init__(
        self,
        repository: SqlAlchemySearchRepository,
        *,
        scope_reader: Callable[[UUID, UUID], VersionScope] | None = None,
        backend: SearchIndexBackend | None = None,
        current_version_reader: Callable[[VersionScope], bool | None] | None = None,
        work_reader: Callable[[VersionScope], WorkSummary | None] | None = None,
    ) -> None:
        self._repo = repository
        self._scope_reader = scope_reader
        self._backend = backend
        self._current_version_reader = current_version_reader
        self._work_reader = work_reader

    def get_status(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
    ) -> SearchStatus:
        try:
            return self._get_status(project_id, architecture_version_id)
        except (DeliveryContractError, ValueError, KeyError, TypeError) as exc:
            raise SearchIntegrityError(
                "Search status metadata integrity failure"
            ) from exc

    def _get_status(
        self, project_id: UUID, architecture_version_id: UUID
    ) -> SearchStatus:
        """Project current status, active generation reference, and readiness."""
        resource = self._repo.get_resource(project_id, architecture_version_id)
        capabilities = SearchCapabilities(
            lexical=(
                CapabilityState.AVAILABLE
                if self._backend is not None
                else CapabilityState.UNAVAILABLE
            )
        )
        if self._scope_reader is None:
            from backend.platform.knowledge.contracts import SearchNotReadyError

            raise SearchNotReadyError("Authoritative version scope unavailable")
        dummy_scope = self._scope_reader(project_id, architecture_version_id)
        if (dummy_scope.project_id, dummy_scope.architecture_version_id) != (
            project_id,
            architecture_version_id,
        ):
            raise SearchIntegrityError("Search status scope mismatch")
        work = self._work_reader(dummy_scope) if self._work_reader else None
        attempt_state = work.state if work else None
        state_map = {
            "PENDING": "PENDING",
            "QUEUED": "PENDING",
            "RUNNING": "RUNNING",
            "RETRYING": "RUNNING",
            "FAILED": "FAILED",
            "CANCELLED": "FAILED",
            "COMPLETED": "COMPLETED",
        }
        current = (
            self._current_version_reader(dummy_scope)
            if self._current_version_reader
            else None
        )

        if resource is None:
            return SearchStatus(
                scope=dummy_scope,
                resource_state=cast(
                    SearchResourceState, state_map.get(attempt_state or "", "PENDING")
                ),
                freshness=(
                    "FAILED"
                    if attempt_state in {"FAILED", "CANCELLED"}
                    else "BUILDING" if work else "UNAVAILABLE"
                ),
                attempt_state=attempt_state,
                is_current_version=current,
                is_readable=False,
                unavailable_reason="No search resource exists for the requested scope",
                capabilities=capabilities,
            )

        if resource.active_generation_id is None:
            public_state = state_map.get(attempt_state or "", resource.status)
            if public_state == "FAILED":
                return SearchStatus(
                    scope=dummy_scope,
                    resource_state="FAILED",
                    freshness="FAILED",
                    attempt_state=attempt_state,
                    is_current_version=current,
                    last_failure_code=work.reason if work else None,
                    is_readable=False,
                    unavailable_reason="Search candidate generation failed",
                    capabilities=capabilities,
                )
            return SearchStatus(
                scope=dummy_scope,
                resource_state=cast(SearchResourceState, public_state),
                freshness="BUILDING",
                is_readable=False,
                attempt_state=attempt_state,
                is_current_version=current,
                unavailable_reason="Search generation is building",
                capabilities=capabilities,
            )

        gen = self._repo.get_generation(resource.active_generation_id)
        if gen is None:
            return SearchStatus(
                scope=dummy_scope,
                resource_state="FAILED",
                freshness="UNAVAILABLE",
                is_readable=False,
                unavailable_reason="Active generation metadata is missing",
                capabilities=capabilities,
            )

        receipt = self._repo.get_publication_receipt(gen.generation_id)
        ref = None
        if receipt is not None:
            ref = ArtifactReference.model_validate_json(
                json.dumps(receipt.artifact_reference)
            )
            if ref.scope != dummy_scope or ref.generation_id != gen.generation_id:
                raise SearchIntegrityError("Search status accepted scope mismatch")

        active_scope = ref.scope if ref else dummy_scope
        # Active within a version is not proof it is the newest repository
        # version. Until a bounded public observation exists, say unknown.
        freshness = (
            "CURRENT" if current is True else "STALE" if current is False else "UNKNOWN"
        )
        is_current = current
        readable = False
        if ref is not None:
            from backend.platform.knowledge.repository import SearchPublicationPort

            manifest = SearchPublicationPort(self._repo._session).require_accepted(ref)
            if self._backend is not None:
                try:
                    physical = self._backend.inspect_index(manifest.index_name)
                    readable = (
                        physical["uuid"] == manifest.index_uuid
                        and physical["sealed"] is True
                    )
                except Exception:
                    readable = False
        if not readable:
            freshness = "UNAVAILABLE"
        elif attempt_state in {"PENDING", "QUEUED", "RUNNING", "RETRYING"}:
            freshness = "BUILDING"

        sealed_dt = gen.sealed_at
        if sealed_dt is not None and sealed_dt.tzinfo is None:
            sealed_dt = sealed_dt.replace(tzinfo=UTC)

        return SearchStatus(
            scope=active_scope,
            resource_state=("STALE" if current is False else "COMPLETED"),
            freshness=cast(SearchFreshness, freshness),
            active_reference=ref,
            attempt_state=attempt_state,
            last_failure_code=(
                work.reason
                if work and attempt_state in {"FAILED", "CANCELLED"}
                else None
            ),
            is_readable=readable,
            is_current_version=is_current,
            last_verified_at=sealed_dt,
            capabilities=capabilities,
        )


class SearchCleanupService:
    """Idempotent background maintenance service.

    Removes orphaned search indices.
    """

    def __init__(
        self,
        repository: SqlAlchemySearchRepository,
        backend: SearchIndexBackend,
        session: Session,
        retirement_reader: AttemptRetirementReader | None = None,
    ) -> None:
        self._repo = repository
        self._backend = backend
        self._session = session
        self._retirement_reader = retirement_reader

    def cleanup_orphans(
        self, *, older_than_seconds: float | None = None, max_items: int | None = None
    ) -> int:
        """Safely delete indices for orphan, failed, or cleanup-marked candidates.

        Guarantees:
        - Never deletes ACTIVE or HISTORICAL generations.
        - Never deletes generations with active reader pins.
        - Never deletes currently active generation pointers.
        """
        if (
            older_than_seconds is None
            or older_than_seconds < 0
            or max_items is None
            or max_items <= 0
            or self._retirement_reader is None
        ):
            return 0  # Destructive maintenance is disabled without approval/port.
        candidates = self._repo.get_cleanup_candidates(
            older_than_seconds=older_than_seconds,
            max_items=max_items,
        )
        cleaned_count = 0

        for gen in candidates:
            from backend.platform.knowledge.repository import SearchPublicationPort

            attempt: AttemptIdentity | None
            if gen.attempt_identity is not None:
                attempt = AttemptIdentity.model_validate_json(
                    json.dumps(gen.attempt_identity)
                )
            elif gen.manifest_bytes is not None:
                attempt = SearchPublicationPort._manifest(gen).attempt
            else:
                continue
            if attempt is None or not gen.index_uuid:
                # Unknown creation outcomes require reconciliation, not adoption.
                continue
            retirement = self._retirement_reader.read_retirement(attempt)
            if (
                retirement is None
                or retirement.outcome == "COMPLETED"
                or retirement.attempt != attempt
            ):
                continue
            # End the read transaction before acquiring producer exclusion.
            generation_id, resource_id = gen.generation_id, gen.resource_id
            self._session.commit()
            self._session.scalar(
                select(SearchResourceModel)
                .where(SearchResourceModel.id == resource_id)
                .with_for_update()
            )
            locked_gen = self._session.scalar(
                select(type(gen))
                .where(type(gen).generation_id == generation_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if locked_gen is None:
                self._session.rollback()
                continue
            gen = locked_gen
            if gen.state in ("ACTIVE", "HISTORICAL"):
                self._session.rollback()
                continue
            if self._repo.get_publication_receipt(gen.generation_id) is not None:
                self._session.rollback()
                continue

            res = self._session.scalar(
                select(SearchResourceModel).where(
                    SearchResourceModel.id == gen.resource_id
                )
            )
            if res is not None and res.active_generation_id == gen.generation_id:
                self._session.rollback()
                continue

            active_pins = self._repo.get_active_read_pin_count(gen.generation_id)
            if active_pins > 0:
                self._session.rollback()
                continue
            index_name, index_uuid = gen.index_name, gen.index_uuid
            gen.state = "CLEANUP_MARKED"
            self._session.commit()  # Publisher now rejects; no locks across I/O.
            try:
                physical = self._backend.inspect_index(index_name)
            except SearchBackendUnavailableError as exc:
                # A prior delete may have succeeded before the tombstone commit.
                # Only an authoritative exact-index 404 is idempotent success;
                # transport/auth failures never authorize deletion or completion.
                if getattr(exc.__cause__, "status_code", None) != 404:
                    raise
                tombstone = self._repo.get_generation(generation_id)
                if tombstone is not None:
                    tombstone.state = "DELETED"
                self._session.commit()
                cleaned_count += 1
                continue
            if physical["uuid"] != index_uuid:
                continue
            if physical["sealed"] is not True:
                self._backend.drain_and_seal_index(index_name)
            self._backend.delete_index(index_name)
            tombstone = self._repo.get_generation(generation_id)
            if tombstone is not None:
                tombstone.state = "DELETED"
            self._session.commit()
            cleaned_count += 1

        return cleaned_count


__all__ = [
    "SearchCleanupService",
    "SearchReader",
    "SearchStatusService",
    "SearchWorkHandler",
]
