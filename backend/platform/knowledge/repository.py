"""Search metadata repository and enlisted publication port.

Implements PostgreSQL state management for search resources, candidate generations,
and atomic acceptance on M1's publication unit-of-work per §7.4, §7.10, and §12.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import (
    AcceptedOutput,
    ArtifactReference,
    DeliveryContractError,
    DeliveryExecutionFailure,
    DeliveryFailure,
    PreparedOutput,
    RetryClass,
)
from backend.platform.delivery.publication import (
    GuardedEnlistedSession,
    ProducerPublicationPort,
    PublicationContext,
    ReadyValidation,
)
from backend.platform.knowledge.model import (
    KnowledgeCounts,
    SearchManifest,
)
from backend.platform.knowledge.persistence import (
    SearchGenerationModel,
    SearchPublicationReceiptModel,
    SearchReadPinModel,
    SearchResourceModel,
)


class SqlAlchemySearchRepository:
    """PostgreSQL operations for search resources and candidate generations."""

    def __init__(self, session: Session | GuardedEnlistedSession) -> None:
        self._session = session

    def ensure_resource(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
    ) -> SearchResourceModel:
        """Find or create search resource anchor for project architecture version."""
        stmt = (
            select(SearchResourceModel)
            .where(
                SearchResourceModel.project_id == project_id,
                SearchResourceModel.architecture_version_id == architecture_version_id,
            )
            .with_for_update()
        )
        res = self._session.scalar(stmt)
        now = datetime.now(UTC)
        if res is None:
            res = SearchResourceModel(
                id=uuid4(),
                project_id=project_id,
                architecture_version_id=architecture_version_id,
                status="PENDING",
                created_at=now,
                updated_at=now,
            )
            self._session.add(res)
            self._session.flush()
        return res

    def stage_candidate(
        self,
        *,
        resource_id: UUID,
        project_id: UUID,
        architecture_version_id: UUID,
        candidate_id: UUID,
        attempt_id: UUID,
        artifact_id: UUID,
        generation_id: UUID,
        index_name: str,
        index_uuid: str,
        counts: KnowledgeCounts,
        manifest: SearchManifest,
    ) -> SearchGenerationModel:
        """Stage candidate index generation in SEALED state before publication."""
        now = datetime.now(UTC)
        gen = SearchGenerationModel(
            generation_id=generation_id,
            resource_id=resource_id,
            project_id=project_id,
            architecture_version_id=architecture_version_id,
            candidate_id=candidate_id,
            attempt_id=attempt_id,
            artifact_id=artifact_id,
            index_name=index_name,
            index_uuid=index_uuid,
            state="SEALED",
            counts_json=counts.model_dump(mode="json"),
            key_set_digest=manifest.key_set_digest,
            payload_digest=manifest.payload_digest,
            projection_digest=manifest.projection_digest,
            manifest_digest=manifest.content_digest(),
            manifest_bytes=manifest.to_canonical_bytes(),
            sealed_at=now,
            created_at=now,
        )
        self._session.add(gen)
        self._session.flush()
        return gen

    def get_generation(self, generation_id: UUID) -> SearchGenerationModel | None:
        """Fetch generation by generation UUID."""
        return self._session.scalar(
            select(SearchGenerationModel).where(
                SearchGenerationModel.generation_id == generation_id
            )
        )

    def get_active_generation(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
    ) -> SearchGenerationModel | None:
        """Resolve current accepted active generation for an architecture version."""
        resource = self._session.scalar(
            select(SearchResourceModel).where(
                SearchResourceModel.project_id == project_id,
                SearchResourceModel.architecture_version_id == architecture_version_id,
            )
        )
        if resource is None or resource.active_generation_id is None:
            return None
        return self.get_generation(resource.active_generation_id)

    def mark_cleanup(self, generation_id: UUID) -> None:
        """Mark unreferenced generation for background cleanup."""
        gen = self.get_generation(generation_id)
        if gen is None:
            return
        # Ensure generation is not currently active
        res = self._session.scalar(
            select(SearchResourceModel).where(SearchResourceModel.id == gen.resource_id)
        )
        if res and res.active_generation_id == generation_id:
            raise DeliveryContractError("cannot cleanup active search generation")
        gen.state = "CLEANUP_MARKED"
        self._session.flush()

    def get_resource(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
    ) -> SearchResourceModel | None:
        """Fetch search resource anchor for project and architecture version."""
        return self._session.scalar(
            select(SearchResourceModel).where(
                SearchResourceModel.project_id == project_id,
                SearchResourceModel.architecture_version_id == architecture_version_id,
            )
        )

    def get_publication_receipt(
        self,
        generation_id: UUID,
    ) -> SearchPublicationReceiptModel | None:
        """Fetch publication receipt for a given generation."""
        return self._session.scalar(
            select(SearchPublicationReceiptModel).where(
                SearchPublicationReceiptModel.generation_id == generation_id
            )
        )

    def acquire_read_pin(
        self,
        *,
        generation_id: UUID,
        pit_id: str | None = None,
        ttl_seconds: float = 300.0,
    ) -> SearchReadPinModel:
        """Acquire reader pin protecting generation from background cleanup."""
        now = datetime.now(UTC)
        pin = SearchReadPinModel(
            pin_id=uuid4(),
            generation_id=generation_id,
            pit_id=pit_id,
            pinned_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        self._session.add(pin)
        self._session.flush()
        return pin

    def release_read_pin(self, pin_id: UUID) -> None:
        """Release a reader pin by its pin_id."""
        self._session.execute(
            delete(SearchReadPinModel).where(SearchReadPinModel.pin_id == pin_id)
        )
        self._session.flush()

    def get_active_read_pin_count(self, generation_id: UUID) -> int:
        """Count non-expired reader pins for a generation."""
        now = datetime.now(UTC)
        count = self._session.scalar(
            select(func.count(SearchReadPinModel.pin_id)).where(
                SearchReadPinModel.generation_id == generation_id,
                SearchReadPinModel.expires_at > now,
            )
        )
        return int(count or 0)

    def get_cleanup_candidates(
        self,
        *,
        older_than_seconds: float = 3600.0,
    ) -> list[SearchGenerationModel]:
        """Query generations eligible for orphan cleanup."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=older_than_seconds)
        stmt = select(SearchGenerationModel).where(
            or_(
                SearchGenerationModel.state == "CLEANUP_MARKED",
                SearchGenerationModel.state == "FAILED",
                and_(
                    SearchGenerationModel.state == "PREPARING",
                    SearchGenerationModel.created_at < cutoff,
                ),
            )
        )
        return list(self._session.scalars(stmt).all())


class SearchPublicationPort(ProducerPublicationPort):
    """Enlisted producer port accepting candidates into PostgreSQL within M1's UoW."""

    def __init__(self, session: GuardedEnlistedSession | Session) -> None:
        self._session = session
        self._repo = SqlAlchemySearchRepository(session)

    def publish_prepared(
        self, prepared: PreparedOutput, context: PublicationContext
    ) -> AcceptedOutput:
        """Enlist candidate activation atomically within M1's live-fence publication."""
        context.require_prepared(prepared)

        now = datetime.now(UTC)
        if now > context.deadline:
            raise DeliveryExecutionFailure(
                DeliveryFailure(
                    code="publication_deadline_exceeded",
                    retry_class=RetryClass.TRANSIENT,
                    source_capability="search",
                )
            )

        attempt = context.attempt
        work = attempt.work

        gen = self._session.scalar(
            select(SearchGenerationModel)
            .where(
                SearchGenerationModel.generation_id == prepared.candidate.generation_id,
                SearchGenerationModel.candidate_id == attempt.candidate_id,
            )
            .with_for_update()
        )
        if gen is None:
            raise DeliveryExecutionFailure(
                DeliveryFailure(
                    code="candidate_not_found",
                    retry_class=RetryClass.INTEGRITY,
                    source_capability="search",
                )
            )
        if gen.state == "CLEANUP_MARKED":
            raise DeliveryExecutionFailure(
                DeliveryFailure(
                    code="candidate_cleanup_marked",
                    retry_class=RetryClass.INTEGRITY,
                    source_capability="search",
                )
            )
        if gen.state != "SEALED":
            raise DeliveryExecutionFailure(
                DeliveryFailure(
                    code="candidate_not_sealed",
                    retry_class=RetryClass.INTEGRITY,
                    source_capability="search",
                )
            )

        resource = self._repo.ensure_resource(
            project_id=work.scope.project_id,
            architecture_version_id=work.scope.architecture_version_id,
        )

        # Transition prior active generation to HISTORICAL
        if (
            resource.active_generation_id is not None
            and resource.active_generation_id != gen.generation_id
        ):
            self._session.execute(
                update(SearchGenerationModel)
                .where(
                    SearchGenerationModel.generation_id == resource.active_generation_id
                )
                .values(state="HISTORICAL")
            )

        # Activate candidate generation
        gen.state = "ACTIVE"
        gen.activated_at = now
        resource.active_generation_id = gen.generation_id
        resource.active_index_name = gen.index_name
        resource.active_index_uuid = gen.index_uuid
        resource.status = "READY"
        resource.updated_at = now

        ref = ArtifactReference(
            scope=work.scope,
            binding=work.binding,
            input_fingerprint=work.input_fingerprint,
            resource_id=resource.id,
            candidate_id=attempt.candidate_id,
            generation_id=gen.generation_id,
            artifact_id=prepared.candidate.artifact_id,
            size_bytes=prepared.candidate.size_bytes,
            digests=prepared.candidate.digests,
            sealed=True,
        )

        receipt = SearchPublicationReceiptModel(
            receipt_id=uuid4(),
            generation_id=gen.generation_id,
            attempt_id=attempt.attempt_id,
            candidate_id=attempt.candidate_id,
            accepted_at=now,
            artifact_reference=ref.model_dump(mode="json"),
        )
        self._session.add(receipt)
        self._session.flush()

        return AcceptedOutput(reference=ref)

    def validate_ready(
        self, reference: ArtifactReference, context: PublicationContext
    ) -> ReadyValidation:
        """Validate locally that artifact reference was accepted and exists."""
        stmt = select(SearchPublicationReceiptModel).where(
            SearchPublicationReceiptModel.candidate_id == reference.candidate_id
        )
        receipt = self._session.scalar(stmt)
        if receipt is None:
            raise DeliveryContractError(
                f"Search candidate reference {reference.candidate_id} not accepted"
            )
        return ReadyValidation(reference=reference)


__all__ = [
    "SearchPublicationPort",
    "SqlAlchemySearchRepository",
]
