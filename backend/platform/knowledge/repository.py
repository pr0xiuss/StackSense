"""Search metadata repository and enlisted publication port.

Implements PostgreSQL state management for search resources, candidate generations,
and atomic acceptance on M1's publication unit-of-work per §7.4, §7.10, and §12.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import (
    AcceptedOutput,
    ArtifactReference,
    AttemptIdentity,
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
from backend.platform.knowledge.elasticsearch import SearchIndexBackend
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

    def commit_staging(self) -> None:
        """Only a dedicated producer staging Session may make this commit."""
        if not isinstance(self._session, Session):
            raise DeliveryContractError("cannot commit enlisted publication session")
        self._session.commit()

    def read_deadline(self, deadline: float) -> None:
        """Bound PostgreSQL work by the remaining whole-operation deadline."""
        from backend.platform.knowledge.contracts import SearchDeadlineExceededError

        remaining = deadline - monotonic()
        if remaining <= 0:
            raise SearchDeadlineExceededError()
        if (
            isinstance(self._session, Session)
            and self._session.get_bind().dialect.name == "postgresql"
        ):
            milliseconds = str(max(1, int(remaining * 1000)))
            for name in ("statement_timeout", "lock_timeout"):
                self._session.execute(select(func.set_config(name, milliseconds, True)))

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
        existing = self.get_generation(generation_id)
        if existing is not None:
            if (
                existing.state != "PREPARING"
                or existing.attempt_id != attempt_id
                or existing.candidate_id != candidate_id
                or existing.index_uuid != index_uuid
            ):
                raise DeliveryContractError("candidate reservation ownership lost")
            existing.state = "SEALED"
            existing.counts_json = counts.model_dump(mode="json")
            existing.key_set_digest = manifest.key_set_digest
            existing.payload_digest = manifest.payload_digest
            existing.projection_digest = manifest.projection_digest
            existing.manifest_digest = manifest.content_digest()
            existing.manifest_bytes = manifest.to_canonical_bytes()
            existing.sealed_at = now
            self._session.flush()
            return existing
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

    def reserve_candidate(
        self,
        attempt: AttemptIdentity,
        generation_id: UUID,
        artifact_id: UUID,
        index_name: str,
    ) -> None:
        """Durable orphan identity BEFORE external creation; no accepted output."""
        scope = attempt.work.scope
        resource = self.ensure_resource(
            project_id=scope.project_id,
            architecture_version_id=scope.architecture_version_id,
        )
        now = datetime.now(UTC)
        self._session.add(
            SearchGenerationModel(
                generation_id=generation_id,
                resource_id=resource.id,
                project_id=scope.project_id,
                architecture_version_id=scope.architecture_version_id,
                candidate_id=attempt.candidate_id,
                attempt_id=attempt.attempt_id,
                attempt_identity=attempt.model_dump(mode="json"),
                artifact_id=artifact_id,
                index_name=index_name,
                index_uuid="",
                state="PREPARING",
                counts_json={},
                key_set_digest="",
                payload_digest="",
                projection_digest="",
                manifest_digest="",
                manifest_bytes=None,
                created_at=now,
            )
        )
        self.commit_staging()

    def bind_candidate_index(
        self, generation_id: UUID, attempt: AttemptIdentity, index_uuid: str
    ) -> None:
        row = self._session.scalar(
            select(SearchGenerationModel)
            .where(SearchGenerationModel.generation_id == generation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            row is None
            or row.state != "PREPARING"
            or row.attempt_id != attempt.attempt_id
        ):
            raise DeliveryContractError("candidate reservation retired")
        row.index_uuid = index_uuid
        self.commit_staging()

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
        resource = self.get_resource(project_id, architecture_version_id)
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
        if (
            gen.state in {"ACTIVE", "HISTORICAL"}
            or self.get_publication_receipt(generation_id) is not None
            or (res and res.active_generation_id == generation_id)
        ):
            raise DeliveryContractError("cannot cleanup accepted search generation")
        gen.state = "CLEANUP_MARKED"
        self._session.flush()

    def get_resource(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
    ) -> SearchResourceModel | None:
        """Fetch search resource anchor for project and architecture version."""
        return self._session.scalar(
            select(SearchResourceModel)
            .where(
                SearchResourceModel.project_id == project_id,
                SearchResourceModel.architecture_version_id == architecture_version_id,
            )
            .execution_options(populate_existing=True)
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

    def require_read_pin(
        self, pin_id: UUID, generation_id: UUID, pit_id: str
    ) -> SearchReadPinModel:
        from backend.platform.knowledge.contracts import SearchCursorExpiredError

        pin = self._session.scalar(
            select(SearchReadPinModel)
            .where(SearchReadPinModel.pin_id == pin_id)
            .execution_options(populate_existing=True)
        )
        if pin is None or pin.generation_id != generation_id or pin.pit_id != pit_id:
            raise SearchCursorExpiredError("Search read session is unavailable")
        expiry = pin.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        if expiry <= datetime.now(UTC):
            raise SearchCursorExpiredError()
        return pin

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
        older_than_seconds: float,
        max_items: int,
    ) -> list[SearchGenerationModel]:
        """Query generations eligible for orphan cleanup."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=older_than_seconds)
        stmt = (
            select(SearchGenerationModel)
            .where(
                SearchGenerationModel.state.in_(
                    ("CLEANUP_MARKED", "FAILED", "PREPARING", "SEALED")
                ),
                SearchGenerationModel.created_at < cutoff,
                ~select(SearchPublicationReceiptModel.receipt_id)
                .where(
                    SearchPublicationReceiptModel.generation_id
                    == SearchGenerationModel.generation_id
                )
                .exists(),
            )
            .order_by(
                SearchGenerationModel.created_at, SearchGenerationModel.generation_id
            )
            .limit(max_items)
        )
        return list(self._session.scalars(stmt).all())


class SearchPublicationPort(ProducerPublicationPort):
    """Enlisted producer port accepting candidates into PostgreSQL within M1's UoW."""

    def __init__(
        self,
        session: GuardedEnlistedSession | Session,
        backend: SearchIndexBackend | None = None,
    ) -> None:
        self._session = session
        self._repo = SqlAlchemySearchRepository(session)
        self._backend = backend

    def _physical(self, manifest: SearchManifest, context: PublicationContext) -> None:
        if self._backend is None:
            raise DeliveryContractError("physical search readiness adapter required")
        remaining = (context.deadline - datetime.now(UTC)).total_seconds()
        with self._backend.operation(monotonic() + remaining):
            physical = self._backend.inspect_index(manifest.index_name)
            if (
                physical["uuid"] != manifest.index_uuid
                or physical["sealed"] is not True
                or physical["mapping_hash"] != manifest.mapping_hash
                or physical["settings_hash"] != manifest.settings_hash
            ):
                raise DeliveryContractError("physical search readiness mismatch")

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

        # Lock order is resource -> generation everywhere, including cleanup.
        resource = self._repo.ensure_resource(
            project_id=work.scope.project_id,
            architecture_version_id=work.scope.architecture_version_id,
        )

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
        manifest = self._manifest(gen)
        if (
            manifest.attempt != attempt
            or gen.attempt_id != attempt.attempt_id
            or gen.resource_id != resource.id
            or manifest.scope != work.scope
            or manifest.profile != work.binding.profile
            or manifest.input_fingerprint != work.input_fingerprint
            or manifest.candidate_id != attempt.candidate_id
            or gen.project_id != work.scope.project_id
            or gen.architecture_version_id != work.scope.architecture_version_id
            or manifest.artifact_id != prepared.candidate.artifact_id
            or manifest.content_digest() != prepared.candidate.digests.content
            or manifest.size_bytes() != prepared.candidate.size_bytes
        ):
            raise DeliveryContractError("search publication descriptor mismatch")
        prior = self._repo.get_publication_receipt(gen.generation_id)
        if prior is not None:
            self._physical(manifest, context)
            accepted = AcceptedOutput(
                reference=ArtifactReference.model_validate_json(
                    json.dumps(prior.artifact_reference)
                )
            )
            accepted.require_candidate(prepared)
            return accepted
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

        self._physical(manifest, context)

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
        resource.status = "COMPLETED"
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
        reference = ArtifactReference.model_validate(reference)
        context.require_reference(reference)
        manifest = self.require_accepted(reference)
        self._physical(manifest, context)
        return ReadyValidation(reference=reference)

    @staticmethod
    def _manifest(gen: SearchGenerationModel) -> SearchManifest:
        if not gen.manifest_bytes:
            raise DeliveryContractError("search manifest unavailable")
        manifest = SearchManifest.model_validate_json(gen.manifest_bytes)
        if (
            manifest.content_digest() != gen.manifest_digest
            or manifest.verifier_version != "1.0.0"
            or manifest.seal_protocol_version != "1.0.0"
            or manifest.generation_id != gen.generation_id
            or manifest.candidate_id != gen.candidate_id
            or manifest.artifact_id != gen.artifact_id
            or manifest.index_name != gen.index_name
            or manifest.index_uuid != gen.index_uuid
            or manifest.counts.model_dump(mode="json") != gen.counts_json
            or manifest.key_set_digest != gen.key_set_digest
            or manifest.payload_digest != gen.payload_digest
            or manifest.projection_digest != gen.projection_digest
        ):
            raise DeliveryContractError("search manifest integrity mismatch")
        return manifest

    def require_accepted(self, reference: ArtifactReference) -> SearchManifest:
        reference = ArtifactReference.model_validate(reference)
        gen = self._repo.get_generation(reference.generation_id)
        receipt = self._repo.get_publication_receipt(reference.generation_id)
        if gen is None or gen.state not in {"ACTIVE", "HISTORICAL"} or receipt is None:
            raise DeliveryContractError("search generation not accepted")
        stored = ArtifactReference.model_validate_json(
            json.dumps(receipt.artifact_reference)
        )
        manifest = self._manifest(gen)
        if (
            stored != reference
            or manifest.attempt is None
            or receipt.attempt_id != manifest.attempt.attempt_id
            or gen.attempt_id != manifest.attempt.attempt_id
            or receipt.candidate_id != manifest.candidate_id
            or manifest.scope != reference.scope
            or manifest.profile != reference.binding.profile
            or manifest.attempt.work.scope != reference.scope
            or manifest.attempt.work.binding != reference.binding
            or manifest.input_fingerprint != reference.input_fingerprint
            or manifest.content_digest() != reference.digests.content
            or manifest.size_bytes() != reference.size_bytes
            or manifest.artifact_id != reference.artifact_id
            or manifest.candidate_id != reference.candidate_id
            or gen.resource_id != reference.resource_id
        ):
            raise DeliveryContractError("search accepted reference mismatch")
        return manifest


__all__ = [
    "SearchPublicationPort",
    "SqlAlchemySearchRepository",
]
