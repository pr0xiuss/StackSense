"""Search work handler and execution service.

Implements M1-compatible SearchWorkHandler performing candidate index creation,
bulk indexing, sealing, independent verification, and candidate staging
per §7.4 and §13.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform.analysis.architecture.model import ArchitectureDocument
from backend.platform.delivery.contracts import (
    ArtifactReference,
    CandidateSeal,
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
    SearchCapabilities,
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
    ) -> None:
        self._backend = backend
        self._repo = repository
        self._document_loader = document_loader
        self._verifier = verifier or SearchVerifier(backend)
        self._projector = projector or KnowledgeProjector()

    def execute(self, context: WorkExecutionContext) -> PreparedOutput:
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
        short_proj = scope.project_id.hex[:8]
        short_gen = generation_id.hex[:8]
        index_name = f"stacksense-search-{short_proj}-{short_gen}"

        try:
            index_uuid = self._backend.create_index(
                index_name=index_name,
                settings=SEARCH_INDEX_SETTINGS,
                mappings=SEARCH_INDEX_MAPPINGS,
            )
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
            self._backend.delete_index(index_name)
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
            self._backend.delete_index(index_name)
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
            generation_id=generation_id,
            index_name=index_name,
            index_uuid=index_uuid,
            expected_projection=projection,
        )
        if not verification.verified:
            self._backend.delete_index(index_name)
            raise DeliveryExecutionFailure(
                DeliveryFailure(
                    code=f"verification_{verification.failure_code}",
                    retry_class=RetryClass.INTEGRITY,
                    source_capability="search",
                )
            )

        # 7. Create SearchManifest and stage in PostgreSQL
        manifest = SearchManifest(
            c1_version="1.0.0",
            scope=scope,
            profile=profile,
            input_fingerprint=work.input_fingerprint,
            candidate_id=attempt.candidate_id,
            generation_id=generation_id,
            artifact_id=artifact_id,
            index_name=index_name,
            index_uuid=index_uuid,
            settings_hash=compute_settings_hash(SEARCH_INDEX_SETTINGS),
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

    def __init__(self, repository: SqlAlchemySearchRepository) -> None:
        self._repo = repository

    def get_status(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
    ) -> SearchStatus:
        """Project current status, active generation reference, and readiness."""
        resource = self._repo.get_resource(project_id, architecture_version_id)
        dummy_scope = VersionScope(
            project_id=project_id,
            architecture_version_id=architecture_version_id,
            repository_id=project_id,
            snapshot_id=architecture_version_id,
            analysis_id=architecture_version_id,
            sequence_number=1,
            published_at=datetime.now(UTC),
            canonical_digest="0" * 64,
            source_contract_version="1.0.0",
            analyzer_version="1.0.0",
            ir_schema_version="1.0.0",
            architecture_schema_version="1.0.0",
            configuration_fingerprint="0" * 64,
        )

        if resource is None:
            return SearchStatus(
                scope=dummy_scope,
                resource_state="PENDING",
                freshness="UNAVAILABLE",
                is_readable=False,
                unavailable_reason="No search resource exists for the requested scope",
                capabilities=SearchCapabilities(),
            )

        if resource.active_generation_id is None:
            if resource.status == "FAILED":
                return SearchStatus(
                    scope=dummy_scope,
                    resource_state="FAILED",
                    freshness="FAILED",
                    is_readable=False,
                    unavailable_reason="Search candidate generation failed",
                    capabilities=SearchCapabilities(),
                )
            return SearchStatus(
                scope=dummy_scope,
                resource_state=resource.status,
                freshness="BUILDING",
                is_readable=False,
                unavailable_reason="Search generation is building",
                capabilities=SearchCapabilities(),
            )

        gen = self._repo.get_generation(resource.active_generation_id)
        if gen is None:
            return SearchStatus(
                scope=dummy_scope,
                resource_state="FAILED",
                freshness="UNAVAILABLE",
                is_readable=False,
                unavailable_reason="Active generation metadata is missing",
                capabilities=SearchCapabilities(),
            )

        receipt = self._repo.get_publication_receipt(gen.generation_id)
        ref = None
        if receipt is not None:
            ref = ArtifactReference.model_validate_json(
                json.dumps(receipt.artifact_reference)
            )

        active_scope = ref.scope if ref else dummy_scope
        freshness = "CURRENT" if gen.state == "ACTIVE" else "STALE"
        is_current = gen.state == "ACTIVE"

        sealed_dt = gen.sealed_at
        if sealed_dt is not None and sealed_dt.tzinfo is None:
            sealed_dt = sealed_dt.replace(tzinfo=UTC)

        return SearchStatus(
            scope=active_scope,
            resource_state=resource.status,
            freshness=freshness,
            active_reference=ref,
            attempt_state=gen.state,
            is_readable=(
                resource.status == "READY" and gen.state in ("ACTIVE", "HISTORICAL")
            ),
            is_current_version=is_current,
            last_verified_at=sealed_dt,
            capabilities=SearchCapabilities(),
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
    ) -> None:
        self._repo = repository
        self._backend = backend
        self._session = session

    def cleanup_orphans(self, *, older_than_seconds: float = 3600.0) -> int:
        """Safely delete indices for orphan, failed, or cleanup-marked candidates.

        Guarantees:
        - Never deletes ACTIVE or HISTORICAL generations.
        - Never deletes generations with active reader pins.
        - Never deletes currently active generation pointers.
        """
        candidates = self._repo.get_cleanup_candidates(
            older_than_seconds=older_than_seconds
        )
        cleaned_count = 0

        for gen in candidates:
            if gen.state in ("ACTIVE", "HISTORICAL"):
                continue

            res = self._session.scalar(
                select(SearchResourceModel).where(
                    SearchResourceModel.id == gen.resource_id
                )
            )
            if res is not None and res.active_generation_id == gen.generation_id:
                continue

            active_pins = self._repo.get_active_read_pin_count(gen.generation_id)
            if active_pins > 0:
                continue

            self._backend.delete_index(gen.index_name)
            self._session.delete(gen)
            self._session.flush()
            cleaned_count += 1

        return cleaned_count


__all__ = [
    "SearchCleanupService",
    "SearchReader",
    "SearchStatusService",
    "SearchWorkHandler",
]
