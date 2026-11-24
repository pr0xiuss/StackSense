"""M5 repository: staging metadata, guarded publication, read pins and history.

Only metadata transactions are performed here; physical artifact I/O is segregated.
Publication operates strictly within M1's GuardedEnlistedSession.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from time import monotonic
from typing import Any
from uuid import UUID, uuid4, uuid5

from sqlalchemy import delete, event, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import (
    AcceptedOutput,
    ArtifactReference,
    AttemptIdentity,
    AttemptRetirementReader,
    HandlerProfile,
    OutputDigests,
    PreparedOutput,
    VersionScope,
)
from backend.platform.delivery.publication import (
    GuardedEnlistedSession,
    ProducerPublicationPort,
    PublicationContext,
    ReadyValidation,
)
from backend.platform.reports.configuration import ReportLimits
from backend.platform.reports.contracts import (
    ReportArtifactDescriptor,
    ReportArtifactManifest,
    ReportInputSnapshot,
)
from backend.platform.reports.model import (
    c4_binding_digest,
    c4_report_resource_id,
)
from backend.platform.reports.persistence import (
    ReportGenerationModel as Generation,
)
from backend.platform.reports.persistence import ReportReadPinModel as Pin
from backend.platform.reports.persistence import (
    ReportResourceModel as Resource,
)

_deadline: ContextVar[float | None] = ContextVar(
    "report_metadata_deadline", default=None
)


def operation_deadline(seconds: int) -> float:
    return min(_deadline.get() or float("inf"), monotonic() + seconds)


@contextmanager
def metadata_operation(deadline: float) -> Iterator[None]:
    """Propagate one operation budget through private, independently owned sessions."""
    previous = _deadline.get()
    token = _deadline.set(min(previous, deadline) if previous is not None else deadline)
    try:
        yield
    finally:
        _deadline.reset(token)


@contextmanager
def metadata_session(
    engine: Engine, seconds: int = 5, *, read_only: bool = False
) -> Iterator[Session]:
    deadline = min(_deadline.get() or float("inf"), monotonic() + seconds)
    if deadline <= monotonic() or (
        _deadline.get() is not None and deadline - monotonic() < 1
    ):
        raise TimeoutError("report_timeout")
    done, expired = Event(), Event()

    owned = engine.connect()
    if read_only:
        owned = owned.execution_options(
            isolation_level="REPEATABLE READ", postgresql_readonly=True
        )
    session = Session(owned)

    def cancel() -> None:
        if done.wait(max(0, deadline - monotonic())):
            return
        expired.set()
        try:
            driver = owned.connection.driver_connection
            if driver is not None:
                driver.cancel_safe(timeout=1)
        except Exception:
            pass

    watcher = Thread(target=cancel, daemon=True)
    if engine.dialect.name == "postgresql":

        @event.listens_for(session, "after_begin")
        def bounded_transaction(s: Any, transaction: Any, connection: Any) -> None:
            remaining = max(1, min(5000, int((deadline - monotonic()) * 1000)))
            connection.exec_driver_sql(f"SET LOCAL statement_timeout={remaining}")
            connection.exec_driver_sql("SET LOCAL lock_timeout=1000")

    watcher.start()
    try:
        yield session
    finally:
        done.set()
        watcher.join(timeout=1.0)
        session.close()
        owned.close()
        if expired.is_set():
            raise TimeoutError("report_timeout")


def descriptor(row: Generation, resource: Resource) -> ReportArtifactDescriptor:
    manifest_raw = row.manifest
    if isinstance(manifest_raw, (str, bytes)):
        manifest = ReportArtifactManifest.model_validate_json(manifest_raw)
    elif isinstance(manifest_raw, dict):
        manifest = ReportArtifactManifest.model_validate_json(json.dumps(manifest_raw))
    else:
        manifest = ReportArtifactManifest.model_validate(manifest_raw)

    scope_raw = resource.scope
    if isinstance(scope_raw, (str, bytes)):
        scope = VersionScope.model_validate_json(scope_raw)
    elif isinstance(scope_raw, dict):
        scope = VersionScope.model_validate_json(json.dumps(scope_raw))
    else:
        scope = VersionScope.model_validate(scope_raw)

    binding_raw = resource.binding
    if isinstance(binding_raw, (str, bytes)):
        binding = HandlerProfile.model_validate_json(binding_raw)
    elif isinstance(binding_raw, dict):
        binding = HandlerProfile.model_validate_json(json.dumps(binding_raw))
    else:
        binding = HandlerProfile.model_validate(binding_raw)

    gen_id = row.id if isinstance(row.id, UUID) else UUID(str(row.id))
    art_id = (
        row.artifact_id
        if isinstance(row.artifact_id, UUID)
        else UUID(str(row.artifact_id))
    )
    cand_id = (
        row.candidate_id
        if isinstance(row.candidate_id, UUID)
        else UUID(str(row.candidate_id))
    )
    res_id = (
        row.resource_id
        if isinstance(row.resource_id, UUID)
        else UUID(str(row.resource_id))
    )

    reference = ArtifactReference(
        scope=scope,
        binding=binding,
        generation_id=gen_id,
        artifact_id=art_id,
        candidate_id=cand_id,
        resource_id=res_id,
        input_fingerprint=row.input_fingerprint,
        sealed=True,
        digests=OutputDigests(
            content=row.manifest_sha256 or "",
            spec=row.spec_digest or "",
            layout=None,
        ),
        size_bytes=row.manifest_size or 0,
    )
    if (
        resource.project_id != scope.project_id
        or resource.architecture_version_id != scope.architecture_version_id
        or row.project_id != scope.project_id
        or row.architecture_version_id != scope.architecture_version_id
        or row.resource_id != resource.id
        or manifest.page_count != row.page_count
    ):
        raise ValueError("report_integrity_error")
    pdf = next(m for m in manifest.members if m.member == "pdf")
    if (pdf.sha256, pdf.size_bytes) != (row.pdf_sha256, row.pdf_size):
        raise ValueError("report_integrity_error")
    return ReportArtifactDescriptor(manifest=manifest, reference=reference)


class ReportRepository:
    """Manages report persistence, candidate allocations, and read pins."""

    def __init__(self, session: Session, limits: ReportLimits | None = None) -> None:
        self.session = session
        self.limits = limits or ReportLimits()

    def get_or_create_resource(
        self, scope: VersionScope, binding: HandlerProfile, input_fingerprint: str
    ) -> Resource:
        rid = c4_report_resource_id(scope, binding, input_fingerprint)
        resource = self.session.get(Resource, rid)
        if resource is None:
            resource = Resource(
                id=rid,
                project_id=scope.project_id,
                architecture_version_id=scope.architecture_version_id,
                report_type="architecture_analysis",
                input_fingerprint=input_fingerprint,
                binding_fingerprint=c4_binding_digest(binding),
                scope=scope.model_dump(mode="json"),
                binding=binding.model_dump(mode="json"),
                captured_snapshot=None,
                source_snapshot_digest=None,
                captured_at=None,
                accepted_generation_id=None,
            )
            try:
                with self.session.begin_nested():
                    self.session.add(resource)
                    self.session.flush()
            except IntegrityError:
                existing = self.session.get(Resource, rid)
                if existing is None:
                    raise
                resource = existing
        if resource.scope != scope.model_dump(
            mode="json"
        ) or resource.binding != binding.model_dump(mode="json"):
            raise ValueError("report_integrity_error")
        return resource

    def capture_snapshot(
        self,
        resource_id: UUID,
        snapshot: ReportInputSnapshot,
    ) -> Resource:
        """Capture report input snapshot insert-once using compare-and-set."""
        resource = self.session.get(Resource, resource_id, with_for_update=True)
        if resource is None:
            raise ValueError("report_resource_not_found")

        if resource.captured_snapshot is not None:
            # Already captured
            return resource

        snapshot_dict = json.loads(snapshot.model_dump_json())
        resource.captured_snapshot = snapshot_dict
        resource.source_snapshot_digest = snapshot.snapshot_digest
        resource.captured_at = snapshot.captured_at
        self.session.flush()
        return resource

    def allocate_candidate(
        self,
        attempt: AttemptIdentity,
        candidate_id: UUID,
        artifact_id: UUID,
    ) -> Generation:
        """Allocate a new report generation row in STAGING state."""
        scope = attempt.work.scope
        binding = attempt.work.binding
        input_fp = attempt.work.input_fingerprint

        resource = self.get_or_create_resource(scope, binding, input_fp)

        prior = self.get_generation(resource.id, candidate_id)
        if prior is not None:
            if prior.attempt_snapshot != attempt.model_dump(mode="json"):
                raise ValueError("report_integrity_error")
            return prior

        gen = Generation(
            id=candidate_id,
            resource_id=resource.id,
            project_id=scope.project_id,
            architecture_version_id=scope.architecture_version_id,
            report_type="architecture_analysis",
            work_id=attempt.work.work_id,
            attempt_id=attempt.attempt_id,
            candidate_id=candidate_id,
            artifact_id=artifact_id,
            attempt_ordinal=attempt.ordinal,
            fence=attempt.fence,
            dispatch_epoch=attempt.dispatch_epoch,
            attempt_snapshot=attempt.model_dump(mode="json"),
            input_fingerprint=input_fp,
            binding_fingerprint=c4_binding_digest(binding),
            state="STAGING",
        )
        self.session.add(gen)
        self.session.flush()
        return gen

    def record_sealed(
        self,
        generation_id: UUID,
        manifest: ReportArtifactManifest,
        seal_proof: dict[str, Any],
        pdf_bytes: bytes,
        pdf_sha256: str,
        page_count: int,
    ) -> Generation:
        """Transition generation from STAGING to SEALED_VERIFIED."""
        gen = self.session.get(Generation, generation_id, with_for_update=True)
        if gen is None:
            raise ValueError("report_generation_not_found")
        if gen.state != "STAGING":
            raise ValueError(f"invalid report state transition from {gen.state}")

        manifest_dict = manifest.model_dump(mode="json")
        manifest_bytes = manifest.to_bytes()
        manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        attempt = AttemptIdentity.model_validate_json(json.dumps(gen.attempt_snapshot))
        for field, expected in {
            "scope": attempt.work.scope,
            "binding": attempt.work.binding,
            "input_fingerprint": attempt.work.input_fingerprint,
            "work_id": attempt.work.work_id,
            "attempt_id": attempt.attempt_id,
            "candidate_id": attempt.candidate_id,
            "generation_id": gen.id,
            "artifact_id": gen.artifact_id,
            "fence_token": attempt.fence,
            "epoch": attempt.dispatch_epoch,
            "run_id": uuid5(attempt.attempt_id, f"run:{attempt.work.run_number}"),
        }.items():
            if getattr(manifest, field) != expected:
                raise ValueError("report_integrity_error")
        if (
            seal_proof.get("manifest_sha256") != manifest_sha256
            or seal_proof.get("pdf_sha256") != pdf_sha256
            or seal_proof.get("verification_version") != "1.0.0"
        ):
            raise ValueError("report_integrity_error")
        if (
            hashlib.sha256(pdf_bytes).hexdigest() != pdf_sha256
            or page_count != manifest.page_count
        ):
            raise ValueError("report_integrity_error")
        expected_pdf = next(m for m in manifest.members if m.member == "pdf")
        if expected_pdf.sha256 != pdf_sha256 or expected_pdf.size_bytes != len(
            pdf_bytes
        ):
            raise ValueError("report_integrity_error")

        gen.manifest = manifest_dict
        gen.manifest_sha256 = manifest_sha256
        gen.spec_digest = manifest.report_spec_digest
        gen.render_fingerprint = manifest.render_fingerprint
        gen.manifest_size = len(manifest_bytes)
        gen.pdf_size = len(pdf_bytes)
        gen.pdf_sha256 = pdf_sha256
        gen.page_count = page_count
        gen.seal_proof = seal_proof
        gen.sealed_at = datetime.now(UTC)
        gen.state = "SEALED_VERIFIED"
        self.session.flush()
        return gen

    def get_generation(
        self, resource_id: UUID, generation_id: UUID
    ) -> Generation | None:
        stmt = select(Generation).where(
            Generation.resource_id == resource_id,
            Generation.id == generation_id,
        )
        return self.session.scalar(stmt)

    def list_accepted_generations(
        self, resource_id: UUID, limit: int = 20, cursor: str | None = None
    ) -> tuple[list[Generation], str | None]:
        stmt = (
            select(Generation)
            .where(
                Generation.resource_id == resource_id,
                Generation.state == "ACCEPTED",
            )
            .order_by(Generation.accepted_at.desc(), Generation.id.desc())
            .limit(limit + 1)
        )
        rows = list(self.session.scalars(stmt))
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            acc_at = (
                last.accepted_at.isoformat() if last.accepted_at is not None else ""
            )
            next_cursor = f"{acc_at}_{last.id}"
        return rows, next_cursor

    def acquire_pin(
        self,
        generation_id: UUID,
        actor_id: UUID | None,
        purpose: str = "download",
        ttl_seconds: int = 300,
    ) -> Pin:
        """Acquire an expiring read pin on an ACCEPTED generation."""
        gen = self.session.get(Generation, generation_id)
        if gen is None or gen.state != "ACCEPTED":
            raise ValueError("pin_requires_accepted_generation")

        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=min(ttl_seconds, 600))
        token = hashlib.sha256(uuid4().bytes).hexdigest()

        pin = Pin(
            id=uuid4(),
            generation_id=generation_id,
            actor_id=actor_id,
            purpose=purpose,
            created_at=now,
            expires_at=expires_at,
            token_hash=token,
        )
        self.session.add(pin)
        self.session.flush()
        return pin

    def release_pin(self, pin_id: UUID) -> None:
        pin = self.session.get(Pin, pin_id)
        if pin is not None:
            self.session.delete(pin)
            self.session.flush()

    def reserve_for_deletion(
        self,
        generation_id: UUID,
        actor_id: UUID,
        retirement_reader: AttemptRetirementReader,
    ) -> bool:
        """Reserve a retired unaccepted generation for operator deletion."""
        gen = self.session.get(Generation, generation_id, with_for_update=True)
        if gen is None or gen.state in ("ACCEPTED", "DELETED"):
            return False
        if gen.state == "DELETING":
            return gen.deletion_actor == actor_id

        # Verify retirement using reader
        attempt_data = gen.attempt_snapshot
        if isinstance(attempt_data, dict):
            attempt = AttemptIdentity.model_validate_json(json.dumps(attempt_data))
        elif isinstance(attempt_data, (str, bytes)):
            attempt = AttemptIdentity.model_validate_json(attempt_data)
        else:
            attempt = AttemptIdentity.model_validate(attempt_data)

        retirement = retirement_reader.read_retirement(attempt)
        if (
            retirement is None
            or retirement.attempt != attempt
            or retirement.publication is not None
        ):
            return False

        # Verify no active pins
        pin_stmt = select(func.count(Pin.id)).where(
            Pin.generation_id == generation_id, Pin.expires_at > datetime.now(UTC)
        )
        pin_count = self.session.scalar(pin_stmt) or 0
        if pin_count > 0:
            return False

        gen.state = "DELETING"
        gen.deletion_nonce = uuid4()
        gen.deletion_actor = actor_id
        gen.retirement_snapshot = retirement.model_dump(mode="json")
        gen.deleting_at = datetime.now(UTC)
        self.session.flush()
        return True


class ReportPublicationPort(ProducerPublicationPort):
    """Enlisted M1 publication port executing within GuardedEnlistedSession."""

    def __init__(self, session: GuardedEnlistedSession) -> None:
        self.session = session

    def validate_ready(
        self, reference: ArtifactReference, context: PublicationContext
    ) -> ReadyValidation:
        """Validate exact report metadata locally on the enlisted transaction."""
        context.require_reference(reference)
        rid = reference.resource_id
        gen_id = reference.generation_id
        stmt = select(Generation).where(
            Generation.id == gen_id, Generation.resource_id == rid
        )
        row = self.session.scalar(stmt)
        if row is None or row.state not in ("SEALED_VERIFIED", "ACCEPTED"):
            raise ValueError("report_not_ready")

        if (
            row.manifest_sha256 != reference.digests.content
            or row.spec_digest != reference.digests.spec
            or row.manifest_size != reference.size_bytes
        ):
            raise ValueError("report_digest_mismatch")

        resource = self.session.scalar(select(Resource).where(Resource.id == rid))
        if resource is None or descriptor(row, resource).reference != reference:
            raise ValueError("report_integrity_error")
        if row.attempt_snapshot != context.attempt.model_dump(mode="json"):
            raise ValueError("report_integrity_error")

        return ReadyValidation(reference=reference)

    def publish_prepared(
        self, prepared: PreparedOutput, context: PublicationContext
    ) -> AcceptedOutput:
        """Atomically transition sealed candidate to ACCEPTED state."""
        context.require_prepared(prepared)
        a = prepared.attempt
        rid = c4_report_resource_id(
            a.work.scope, a.work.binding, a.work.input_fingerprint
        )

        res_stmt = select(Resource).where(Resource.id == rid).with_for_update()
        resource = self.session.scalar(res_stmt)
        if resource is None:
            raise ValueError("report_resource_not_found")

        gen_stmt = (
            select(Generation)
            .where(
                Generation.id == prepared.candidate.generation_id,
                Generation.resource_id == rid,
            )
            .with_for_update()
        )
        row = self.session.scalar(gen_stmt)
        if row is None:
            raise ValueError("report_generation_not_found")

        attempt_data = row.attempt_snapshot
        if isinstance(attempt_data, dict):
            attempt_recorded = AttemptIdentity.model_validate_json(
                json.dumps(attempt_data)
            )
        elif isinstance(attempt_data, (str, bytes)):
            attempt_recorded = AttemptIdentity.model_validate_json(attempt_data)
        else:
            attempt_recorded = AttemptIdentity.model_validate(attempt_data)

        if attempt_recorded != a or row.state not in (
            "SEALED_VERIFIED",
            "ACCEPTED",
        ):
            raise ValueError("report_integrity_error")

        ref = descriptor(row, resource).reference
        result = AcceptedOutput(reference=ref)
        result.require_candidate(prepared)

        if row.state == "ACCEPTED":
            self.validate_ready(ref, context)
            return result

        row.state = "ACCEPTED"
        row.accepted_at = datetime.now(UTC)
        row.accepted_reference = ref.model_dump(mode="json")
        row.acceptance_context = {
            "transaction_id": str(context.transaction_id),
            "attempt_id": str(a.attempt_id),
            "reference": ref.model_dump(mode="json"),
        }
        resource.accepted_generation_id = row.id
        self.session.flush()
        return result


class ReportDatabaseReadAuthority:
    """Database-backed read authority for verifying and pinning report artifacts."""

    def __init__(
        self,
        engine: Engine,
        limits: ReportLimits,
        *,
        actor_id: UUID | None = None,
        purpose: str = "export",
    ) -> None:
        self.engine = engine
        self.limits = limits
        self.actor_id = actor_id
        self.purpose = purpose

    def _exact(
        self, session: Session, scope: VersionScope, reference: ArtifactReference
    ) -> ReportArtifactManifest:
        ref = ArtifactReference.model_validate(reference)
        if VersionScope.model_validate(scope) != ref.scope:
            raise ValueError("report_scope_mismatch")
        resource = session.scalar(
            select(Resource).where(Resource.id == ref.resource_id)
        )
        row = session.scalar(
            select(Generation).where(Generation.id == ref.generation_id)
        )
        if resource is None or row is None or row.state != "ACCEPTED":
            raise ValueError("report_generation_unavailable")
        actual = descriptor(row, resource)
        if (
            actual.reference != ref
            or row.resource_id != resource.id
            or not row.accepted_reference
            or ArtifactReference.model_validate_json(json.dumps(row.accepted_reference))
            != ref
        ):
            raise ValueError("report_integrity_error")
        return actual.manifest

    def descriptor(
        self, scope: VersionScope, reference: ArtifactReference
    ) -> ReportArtifactDescriptor:
        with metadata_session(self.engine) as session:
            self._exact(session, scope, reference)
            ref = ArtifactReference.model_validate(reference)
            resource = session.scalar(
                select(Resource).where(Resource.id == ref.resource_id)
            )
            row = session.scalar(
                select(Generation).where(Generation.id == ref.generation_id)
            )
            if resource is None or row is None or row.state != "ACCEPTED":
                raise ValueError("report_generation_unavailable")
            return descriptor(row, resource)

    def recheck(self, scope: VersionScope, reference: ArtifactReference) -> None:
        with metadata_session(self.engine) as session:
            self._exact(session, scope, reference)

    @contextmanager
    def pinned(
        self, scope: VersionScope, reference: ArtifactReference
    ) -> Iterator[ReportArtifactManifest]:
        now, pid = datetime.now(UTC), uuid4()
        with metadata_session(self.engine) as session, session.begin():
            session.scalar(
                select(Resource)
                .where(Resource.id == reference.resource_id)
                .with_for_update()
            )
            session.scalar(
                select(Generation)
                .where(Generation.id == reference.generation_id)
                .with_for_update()
            )
            manifest = self._exact(session, scope, reference)
            session.execute(
                delete(Pin).where(
                    Pin.generation_id == reference.generation_id, Pin.expires_at <= now
                )
            )
            pins = session.scalars(
                select(Pin.id)
                .where(
                    Pin.generation_id == reference.generation_id, Pin.expires_at > now
                )
                .limit(self.limits.max_pins_per_generation)
            ).all()
            if len(pins) >= self.limits.max_pins_per_generation:
                raise ValueError("report_store_unavailable")
            pin = Pin(
                id=pid,
                generation_id=reference.generation_id,
                actor_id=self.actor_id,
                purpose=self.purpose,
                created_at=now,
                expires_at=now + timedelta(seconds=self.limits.pin_ttl_seconds),
                token_hash=hashlib.sha256(uuid4().bytes).hexdigest(),
            )
            session.add(pin)

        try:
            yield manifest
        finally:
            with metadata_session(self.engine) as session, session.begin():
                pin_row = session.get(Pin, pid)
                if pin_row is not None:
                    session.delete(pin_row)


__all__ = [
    "ReportDatabaseReadAuthority",
    "ReportPublicationPort",
    "ReportRepository",
    "descriptor",
    "metadata_operation",
    "metadata_session",
    "operation_deadline",
]
