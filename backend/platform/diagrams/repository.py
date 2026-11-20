"""M4 metadata only. Independent staging, guarded acceptance and exact read pins."""

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
from uuid import UUID, uuid4

from sqlalchemy import event, func, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import (
    AcceptedOutput,
    ArtifactReference,
    AttemptIdentity,
    AttemptRetirementReader,
    CandidateSeal,
    DeliveryExecutionFailure,
    DeliveryFailure,
    DiagramTemplate,
    OutputDigests,
    PreparedOutput,
    RetryClass,
    VersionScope,
)
from backend.platform.delivery.publication import (
    GuardedEnlistedSession,
    PublicationContext,
    ReadyValidation,
)
from backend.platform.diagrams.artifact_contracts import SealProof
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import (
    DiagramArtifactDescriptor,
    DiagramArtifactManifest,
)
from backend.platform.diagrams.model import canonical_bytes
from backend.platform.diagrams.persistence import (
    DiagramGenerationModel as Generation,
)
from backend.platform.diagrams.persistence import DiagramReadPinModel as Pin
from backend.platform.diagrams.persistence import DiagramResourceModel as Resource
from backend.platform.diagrams.persistence import diagram_resource_id

_deadline: ContextVar[float | None] = ContextVar(
    "diagram_metadata_deadline", default=None
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
def metadata_session(engine: Engine, seconds: int = 5) -> Iterator[Session]:
    deadline = min(_deadline.get() or float("inf"), monotonic() + seconds)
    if deadline <= monotonic() or (
        _deadline.get() is not None and deadline - monotonic() < 1
    ):
        raise TimeoutError("diagram_timeout")
    done, expired = Event(), Event()
    connections: list[Any] = []
    failures: list[Exception] = []
    # Hold our own checkout until cancellation is stopped/joined. A Session
    # commit must not return a connection that the watchdog could later cancel.
    owned = engine.connect()
    session = Session(owned)

    @event.listens_for(session, "after_begin")
    def begun(session: Session, transaction: Any, connection: Any) -> None:
        raw = connection.connection.driver_connection
        connections.append(raw)
        ms = max(1, int((deadline - monotonic()) * 1000))
        connection.exec_driver_sql(f"SET LOCAL statement_timeout={ms}")
        connection.exec_driver_sql(f"SET LOCAL lock_timeout={min(ms,1000)}")

    def cancel() -> None:
        if done.wait(max(0, deadline - monotonic())):
            return
        expired.set()
        for connection in connections:
            try:
                connection.cancel_safe(timeout=1)
            except Exception as exc:
                failures.append(exc)

    watchdog = Thread(target=cancel, daemon=True)
    watchdog.start()
    try:
        yield session
    except Exception as exc:
        if (
            expired.is_set()
            or getattr(getattr(exc, "orig", None), "sqlstate", None) == "57014"
        ):
            raise TimeoutError("diagram_timeout") from exc
        raise
    finally:
        done.set()
        watchdog.join(timeout=2)
        session.close()
        owned.close()
        if watchdog.is_alive() or failures:
            raise RuntimeError("diagram_metadata_cancellation_failed")
    if expired.is_set() or monotonic() >= deadline:
        raise TimeoutError("diagram_timeout")


def binding_digest(attempt: AttemptIdentity) -> str:
    return hashlib.sha256(canonical_bytes(attempt.work.binding)).hexdigest()


@contextmanager
def _publication_errors() -> Iterator[None]:
    from sqlalchemy.exc import OperationalError

    try:
        yield
    except TimeoutError as exc:
        raise DeliveryExecutionFailure(
            DeliveryFailure(
                code="diagram_timeout",
                retry_class=RetryClass.TRANSIENT,
                source_capability="diagrams",
            )
        ) from exc
    except OperationalError as exc:
        raise DeliveryExecutionFailure(
            DeliveryFailure(
                code="diagram_store_unavailable",
                retry_class=RetryClass.TRANSIENT,
                source_capability="diagrams",
            )
        ) from exc
    except ValueError as exc:
        raise DeliveryExecutionFailure(
            DeliveryFailure(
                code="diagram_integrity_error",
                retry_class=RetryClass.INTEGRITY,
                source_capability="diagrams",
            )
        ) from exc


def descriptor(row: Generation, resource: Resource) -> DiagramArtifactDescriptor:
    """Revalidate complete immutable snapshots, not just a stored digest label."""
    if row.manifest is None or row.seal_proof is None:
        raise ValueError("diagram_generation_unavailable")
    m = DiagramArtifactManifest.model_validate_json(json.dumps(row.manifest))
    a = AttemptIdentity.model_validate_json(json.dumps(row.attempt_snapshot))
    w = a.work
    proof = SealProof.model_validate_json(json.dumps(row.seal_proof))
    content = m.to_bytes()
    if (
        row.resource_id != resource.id
        or resource.id != diagram_resource_id(w.scope, w.binding, w.input_fingerprint)
        or resource.scope != w.scope.model_dump(mode="json")
        or resource.binding != w.binding.model_dump(mode="json")
        or resource.canonical_digest != w.scope.canonical_digest
        or resource.input_fingerprint != w.input_fingerprint
        or row.input_fingerprint != w.input_fingerprint
        or row.binding_fingerprint != binding_digest(a)
        or resource.binding_fingerprint != binding_digest(a)
        or row.project_id != w.scope.project_id
        or resource.project_id != w.scope.project_id
        or row.architecture_version_id != w.scope.architecture_version_id
        or resource.architecture_version_id != w.scope.architecture_version_id
        or row.template != resource.template
        or row.template != w.binding.slot.template
        or (
            row.work_id,
            row.attempt_id,
            row.candidate_id,
            row.attempt_ordinal,
            row.fence,
            row.dispatch_epoch,
        )
        != (
            w.work_id,
            a.attempt_id,
            a.candidate_id,
            a.ordinal,
            a.fence,
            a.dispatch_epoch,
        )
        or m.generation_id != row.id
        or m.artifact_id != row.artifact_id
        or m.scope != w.scope
        or m.binding != w.binding
        or m.input_fingerprint != w.input_fingerprint
        or row.manifest_size != len(content)
        or row.manifest_sha256 != hashlib.sha256(content).hexdigest()
        or (row.spec_digest, row.layout_digest, row.membership_digest)
        != (m.semantic_digest, m.layout_digest, m.membership_digest)
        or row.total_member_bytes != sum(member.size_bytes for member in m.members)
        or proof.manifest_sha256 != row.manifest_sha256
        or proof.member_set_digest
        != hashlib.sha256(canonical_bytes(m.members)).hexdigest()
        or row.sealed_at != proof.sealed_at
    ):
        raise ValueError("diagram_integrity_error")
    ref = ArtifactReference(
        scope=w.scope,
        binding=w.binding,
        input_fingerprint=w.input_fingerprint,
        resource_id=resource.id,
        candidate_id=a.candidate_id,
        generation_id=row.id,
        artifact_id=row.artifact_id,
        size_bytes=len(content),
        digests=OutputDigests(
            content=hashlib.sha256(content).hexdigest(),
            spec=m.semantic_digest,
            layout=m.layout_digest,
        ),
        sealed=True,
    )
    return DiagramArtifactDescriptor(manifest=m, reference=ref)


class DiagramRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def build_admission(
        self, project_id: UUID, limits: DiagramLimits
    ) -> Iterator[None]:
        """One project build across processes; no transaction held during compute."""
        key = int.from_bytes(
            hashlib.sha256(b"ss.diagram.admission:" + project_id.bytes).digest()[:8],
            signed=True,
        )
        with self.engine.connect() as connection:
            acquired = False
            try:
                connection.exec_driver_sql("SET LOCAL statement_timeout=1000")
                acquired = bool(
                    connection.scalar(
                        text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
                    )
                )
                connection.commit()
                if not acquired:
                    raise ValueError("diagram_store_unavailable")
                with metadata_session(self.engine) as session:
                    orphan_bytes = session.scalar(
                        select(
                            func.coalesce(func.sum(Generation.total_member_bytes), 0)
                        ).where(
                            Generation.state.in_(
                                ("STAGING", "SEALED_VERIFIED", "DELETING")
                            )
                        )
                    )
                    if (orphan_bytes or 0) >= limits.max_orphan_bytes:
                        raise ValueError("diagram_store_unavailable")
                yield
            finally:
                if acquired:
                    try:
                        connection.exec_driver_sql("SET LOCAL statement_timeout=1000")
                        if (
                            connection.scalar(
                                text("SELECT pg_advisory_unlock(:key)"), {"key": key}
                            )
                            is not True
                        ):
                            raise RuntimeError("diagram_admission_release_failed")
                        connection.commit()
                    except Exception:
                        connection.invalidate()  # Never pool a leaked session lock.
                        raise

    def reserve(self, attempt: AttemptIdentity) -> tuple[UUID, UUID]:
        """Commit private identity before filesystem work or M1 publication."""
        attempt = AttemptIdentity.model_validate(attempt)
        work = attempt.work
        if not isinstance(work.binding.slot.template, DiagramTemplate):
            raise ValueError("diagram_contract_unsupported")
        rid = diagram_resource_id(work.scope, work.binding, work.input_fingerprint)
        with metadata_session(self.engine) as session, session.begin():
            session.execute(
                insert(Resource)
                .values(
                    id=rid,
                    project_id=work.scope.project_id,
                    architecture_version_id=work.scope.architecture_version_id,
                    template=work.binding.slot.template.value,
                    canonical_digest=work.scope.canonical_digest,
                    input_fingerprint=work.input_fingerprint,
                    binding_fingerprint=binding_digest(attempt),
                    scope=work.scope.model_dump(mode="json"),
                    binding=work.binding.model_dump(mode="json"),
                )
                .on_conflict_do_nothing(index_elements=[Resource.id])
            )
            resource = session.scalar(
                select(Resource).where(Resource.id == rid).with_for_update()
            )
            if resource is None:
                raise ValueError("diagram_integrity_error")
            old = session.scalar(
                select(Generation)
                .where(Generation.attempt_id == attempt.attempt_id)
                .with_for_update()
            )
            if old is not None:
                if old.attempt_snapshot != attempt.model_dump(mode="json"):
                    raise ValueError("diagram_integrity_error")
                if old.state in ("DELETING", "DELETED"):
                    raise ValueError("diagram_generation_unavailable")
                return old.id, old.artifact_id
            generation_id, artifact_id = uuid4(), uuid4()
            session.add(
                Generation(
                    id=generation_id,
                    artifact_id=artifact_id,
                    resource_id=rid,
                    project_id=work.scope.project_id,
                    architecture_version_id=work.scope.architecture_version_id,
                    template=work.binding.slot.template.value,
                    work_id=work.work_id,
                    attempt_id=attempt.attempt_id,
                    candidate_id=attempt.candidate_id,
                    attempt_ordinal=attempt.ordinal,
                    fence=attempt.fence,
                    dispatch_epoch=attempt.dispatch_epoch,
                    attempt_snapshot=attempt.model_dump(mode="json"),
                    input_fingerprint=work.input_fingerprint,
                    binding_fingerprint=binding_digest(attempt),
                    state="STAGING",
                )
            )
            return generation_id, artifact_id

    def stage_manifest(
        self,
        attempt: AttemptIdentity,
        manifest: DiagramArtifactManifest,
        limits: DiagramLimits | None = None,
    ) -> None:
        data = manifest.to_bytes()
        limits = limits or DiagramLimits()
        with metadata_session(self.engine) as session, session.begin():
            # Serialize only this short M4 admission update, never external IO.
            session.execute(text("SELECT pg_advisory_xact_lock(817420310043)"))
            row = self._staging(session, attempt, manifest.generation_id)
            private_bytes = (
                session.scalar(
                    select(
                        func.coalesce(func.sum(Generation.total_member_bytes), 0)
                    ).where(
                        Generation.id != row.id,
                        Generation.state.in_(
                            ("STAGING", "SEALED_VERIFIED", "DELETING")
                        ),
                    )
                )
                or 0
            )
            if (
                private_bytes + sum(m.size_bytes for m in manifest.members)
                > limits.max_orphan_bytes
            ):
                raise ValueError("diagram_store_unavailable")
            if (
                row.artifact_id != manifest.artifact_id
                or manifest.scope != attempt.work.scope
                or manifest.binding != attempt.work.binding
                or manifest.input_fingerprint != attempt.work.input_fingerprint
            ):
                raise ValueError("diagram_integrity_error")
            snapshot = manifest.model_dump(mode="json")
            if row.manifest is not None and row.manifest != snapshot:
                raise ValueError("diagram_integrity_error")
            row.manifest = snapshot
            row.manifest_sha256 = hashlib.sha256(data).hexdigest()
            row.manifest_size = len(data)
            row.spec_digest, row.layout_digest = (
                manifest.semantic_digest,
                manifest.layout_digest,
            )
            row.membership_digest = manifest.membership_digest
            row.total_member_bytes = sum(m.size_bytes for m in manifest.members)

    @staticmethod
    def _staging(session: Session, attempt: AttemptIdentity, gid: UUID) -> Generation:
        rid = diagram_resource_id(
            attempt.work.scope, attempt.work.binding, attempt.work.input_fingerprint
        )
        session.scalar(select(Resource).where(Resource.id == rid).with_for_update())
        row = session.scalar(
            select(Generation).where(Generation.id == gid).with_for_update()
        )
        if (
            row is None
            or row.resource_id != rid
            or row.state != "STAGING"
            or row.attempt_snapshot != attempt.model_dump(mode="json")
        ):
            raise ValueError("diagram_integrity_error")
        return row

    def mark_sealed(
        self, attempt: AttemptIdentity, gid: UUID, proof: SealProof
    ) -> PreparedOutput:
        with metadata_session(self.engine) as session, session.begin():
            row = self._staging(session, attempt, gid)
            row.seal_proof = proof.model_dump(mode="json")
            row.sealed_at = proof.sealed_at
            resource = session.get(Resource, row.resource_id)
            if resource is None:
                raise ValueError("diagram_integrity_error")
            result = descriptor(row, resource)
            row.state = "SEALED_VERIFIED"
            return PreparedOutput(
                attempt=attempt,
                candidate=CandidateSeal(
                    generation_id=gid,
                    artifact_id=row.artifact_id,
                    size_bytes=result.reference.size_bytes,
                    digests=result.reference.digests,
                    sealed=True,
                ),
            )

    def prepared(self, attempt: AttemptIdentity, gid: UUID) -> PreparedOutput | None:
        with metadata_session(self.engine) as session:
            row = session.get(Generation, gid)
            if row is None or row.attempt_snapshot != attempt.model_dump(mode="json"):
                raise ValueError("diagram_integrity_error")
            if row.state == "STAGING":
                return None
            if row.state not in ("SEALED_VERIFIED", "ACCEPTED"):
                raise ValueError("diagram_generation_unavailable")
            resource = session.get(Resource, row.resource_id)
            if resource is None:
                raise ValueError("diagram_integrity_error")
            ref = descriptor(row, resource).reference
            return PreparedOutput(
                attempt=attempt,
                candidate=CandidateSeal(
                    generation_id=gid,
                    artifact_id=ref.artifact_id,
                    size_bytes=ref.size_bytes,
                    digests=ref.digests,
                    sealed=True,
                ),
            )

    def sealed_manifest(
        self, attempt: AttemptIdentity, gid: UUID
    ) -> DiagramArtifactManifest:
        with metadata_session(self.engine) as session:
            row = session.get(Generation, gid)
            if (
                row is None
                or row.state not in ("SEALED_VERIFIED", "ACCEPTED")
                or row.attempt_snapshot != attempt.model_dump(mode="json")
            ):
                raise ValueError("diagram_generation_unavailable")
            resource = session.get(Resource, row.resource_id)
            if resource is None:
                raise ValueError("diagram_integrity_error")
            return descriptor(row, resource).manifest

    def reserve_deletion(
        self,
        attempt: AttemptIdentity,
        gid: UUID,
        reader: AttemptRetirementReader,
        actor_id: UUID,
        limits: DiagramLimits,
    ) -> tuple[UUID, bool]:
        """Trusted operator only; public retirement is observed before M4 locks."""
        retirement = reader.read_retirement(attempt)
        now = datetime.now(UTC)
        if (
            retirement is None
            or retirement.attempt != attempt
            or retirement.publication is not None
            or now - retirement.ended_at
            < timedelta(seconds=limits.orphan_grace_seconds)
        ):
            raise ValueError("diagram_generation_unavailable")
        rid = diagram_resource_id(
            attempt.work.scope, attempt.work.binding, attempt.work.input_fingerprint
        )
        with metadata_session(self.engine) as session, session.begin():
            resource = session.scalar(
                select(Resource).where(Resource.id == rid).with_for_update()
            )
            row = session.scalar(
                select(Generation).where(Generation.id == gid).with_for_update()
            )
            if (
                resource is None
                or row is None
                or row.resource_id != rid
                or row.attempt_snapshot != attempt.model_dump(mode="json")
                or row.state
                not in ("STAGING", "SEALED_VERIFIED", "DELETING", "DELETED")
                or row.accepted_reference is not None
                or row.acceptance_context is not None
                or resource.accepted_generation_id == gid
                or now - row.created_at < timedelta(seconds=limits.orphan_grace_seconds)
                or session.scalar(
                    select(Pin.id).where(Pin.generation_id == gid).limit(1)
                )
            ):
                raise ValueError("diagram_generation_unavailable")
            if row.state in ("DELETING", "DELETED"):
                if (
                    row.deletion_nonce is None
                    or row.deletion_actor != actor_id
                    or row.retirement_snapshot != retirement.model_dump(mode="json")
                ):
                    raise ValueError("diagram_integrity_error")
                return row.deletion_nonce, row.state == "DELETED"
            nonce = uuid4()
            row.state, row.deletion_nonce, row.deletion_actor = (
                "DELETING",
                nonce,
                actor_id,
            )
            row.retirement_snapshot = retirement.model_dump(mode="json")
            row.deleting_at = now
            return nonce, False

    def mark_deleted(self, gid: UUID, nonce: UUID, actor_id: UUID) -> None:
        """Called only after the protected operator GC confirms exact unlink."""
        with metadata_session(self.engine) as session, session.begin():
            rid = session.scalar(
                select(Generation.resource_id).where(Generation.id == gid)
            )
            session.scalar(select(Resource).where(Resource.id == rid).with_for_update())
            row = session.scalar(
                select(Generation).where(Generation.id == gid).with_for_update()
            )
            if (
                row is None
                or row.state not in ("DELETING", "DELETED")
                or row.deletion_nonce != nonce
                or row.deletion_actor != actor_id
            ):
                raise ValueError("diagram_integrity_error")
            if row.state == "DELETED":
                return
            row.state, row.deleted_at = "DELETED", datetime.now(UTC)


class DiagramQueryRepository(DiagramRepository):
    """Read only M4 metadata. Current selection is supplied by public M1 summary."""

    def has_accepted(
        self, project_id: UUID, version_id: UUID, template: DiagramTemplate
    ) -> bool:
        with metadata_session(self.engine) as session, session.begin():
            return (
                session.scalar(
                    select(Generation.id)
                    .where(
                        Generation.project_id == project_id,
                        Generation.architecture_version_id == version_id,
                        Generation.template == template.value,
                        Generation.state == "ACCEPTED",
                    )
                    .limit(1)
                )
                is not None
            )

    def accepted(
        self, project_id: UUID, version_id: UUID, template: DiagramTemplate, gid: UUID
    ) -> tuple[ArtifactReference, datetime, datetime | None]:
        with metadata_session(self.engine) as session, session.begin():
            row = session.scalar(
                select(Generation).where(
                    Generation.id == gid,
                    Generation.project_id == project_id,
                    Generation.architecture_version_id == version_id,
                    Generation.template == template.value,
                    Generation.state == "ACCEPTED",
                )
            )
            if row is None:
                raise ValueError("diagram_generation_unavailable")
            resource = session.get(Resource, row.resource_id)
            if resource is None:
                raise ValueError("diagram_integrity_error")
            reference = descriptor(row, resource).reference
            if (
                row.accepted_reference != reference.model_dump(mode="json")
                or row.accepted_at is None
            ):
                raise ValueError("diagram_integrity_error")
            return reference, row.accepted_at, row.sealed_at

    def require_active(self, reference: ArtifactReference) -> None:
        with metadata_session(self.engine) as session, session.begin():
            resource = session.get(Resource, reference.resource_id)
            if (
                resource is None
                or resource.accepted_generation_id != reference.generation_id
            ):
                raise ValueError("diagram_generation_changed")

    def history(
        self,
        reference: ArtifactReference,
        limit: int,
        high: tuple[datetime, UUID] | None,
        after: tuple[datetime, UUID] | None,
    ) -> tuple[tuple[UUID, datetime], ...]:
        with metadata_session(self.engine) as session, session.begin():
            query = select(Generation.id, Generation.accepted_at).where(
                Generation.resource_id == reference.resource_id,
                Generation.project_id == reference.scope.project_id,
                Generation.architecture_version_id
                == reference.scope.architecture_version_id,
                Generation.state == "ACCEPTED",
            )
            key = tuple_(Generation.accepted_at, Generation.id)
            if high is not None:
                query = query.where(key <= high)
            if after is not None:
                query = query.where(key < after)
            rows = session.execute(
                query.order_by(
                    Generation.accepted_at.desc(), Generation.id.desc()
                ).limit(limit + 1)
            ).all()
            return tuple((row[0], row[1]) for row in rows)


class DiagramPublicationPort:
    """M1 owns this Session and transaction. No external calls or lifecycle methods."""

    def __init__(self, session: GuardedEnlistedSession) -> None:
        if not isinstance(session, GuardedEnlistedSession):
            raise ValueError("guarded M1 publication session required")
        self.session = session

    def _rows(self, rid: UUID, gid: UUID) -> tuple[Resource, Generation]:
        resource = self.session.scalar(
            select(Resource).where(Resource.id == rid).with_for_update()
        )
        row = self.session.scalar(
            select(Generation).where(Generation.id == gid).with_for_update()
        )
        if resource is None or row is None or row.resource_id != resource.id:
            raise ValueError("diagram_generation_unavailable")
        return resource, row

    def publish_prepared(
        self, prepared: PreparedOutput, context: PublicationContext
    ) -> AcceptedOutput:
        with _publication_errors():
            return self._publish_prepared(prepared, context)

    def _publish_prepared(
        self, prepared: PreparedOutput, context: PublicationContext
    ) -> AcceptedOutput:
        context.require_prepared(prepared)
        if datetime.now(UTC) >= context.deadline:
            raise TimeoutError("diagram_timeout")
        a = prepared.attempt
        rid = diagram_resource_id(
            a.work.scope, a.work.binding, a.work.input_fingerprint
        )
        resource, row = self._rows(rid, prepared.candidate.generation_id)
        if row.attempt_snapshot != a.model_dump(mode="json") or row.state not in (
            "SEALED_VERIFIED",
            "ACCEPTED",
        ):
            raise ValueError("diagram_integrity_error")
        ref = descriptor(row, resource).reference
        result = AcceptedOutput(reference=ref)
        result.require_candidate(prepared)
        if row.state == "ACCEPTED":
            self.validate_ready(ref, context)
            return result
        row.state = "ACCEPTED"
        row.accepted_at = datetime.now(UTC)
        row.accepted_reference = ref.model_dump(mode="json")
        row.acceptance_context = dict(
            transaction_id=str(context.transaction_id),
            attempt_id=str(a.attempt_id),
            reference=row.accepted_reference,
        )
        resource.accepted_generation_id = row.id
        self.session.flush()
        return result

    def validate_ready(
        self, reference: ArtifactReference, context: PublicationContext
    ) -> ReadyValidation:
        with _publication_errors():
            return self._validate_ready(reference, context)

    def _validate_ready(
        self, reference: ArtifactReference, context: PublicationContext
    ) -> ReadyValidation:
        context.require_reference(reference)
        resource, row = self._rows(reference.resource_id, reference.generation_id)
        ref = descriptor(row, resource).reference
        if (
            row.state != "ACCEPTED"
            or ref != reference
            or row.attempt_snapshot != context.attempt.model_dump(mode="json")
            or row.accepted_reference != ref.model_dump(mode="json")
            or not row.acceptance_context
            or row.acceptance_context.get("attempt_id")
            != str(context.attempt.attempt_id)
            or row.acceptance_context.get("reference") != row.accepted_reference
        ):
            raise ValueError("diagram_integrity_error")
        return ReadyValidation(reference=ref)


class DatabaseReadAuthority:
    """Historical exact reads do not require an active original lease/pointer."""

    def __init__(
        self,
        engine: Engine,
        limits: DiagramLimits,
        *,
        actor_id: UUID | None,
        purpose: str = "report",
    ) -> None:
        if purpose not in ("report", "api", "view") or (
            actor_id is None and purpose != "report"
        ):
            raise ValueError("diagram_scope_mismatch")
        self.engine, self.limits, self.actor_id, self.purpose = (
            engine,
            limits,
            actor_id,
            purpose,
        )

    @staticmethod
    def _exact(
        session: Session, scope: VersionScope, reference: ArtifactReference
    ) -> DiagramArtifactManifest:
        ref = ArtifactReference.model_validate(reference)
        if VersionScope.model_validate(scope) != ref.scope:
            raise ValueError("diagram_scope_mismatch")
        resource = session.scalar(
            select(Resource).where(Resource.id == ref.resource_id).with_for_update()
        )
        row = session.scalar(
            select(Generation)
            .where(Generation.id == ref.generation_id)
            .with_for_update()
        )
        if resource is None or row is None or row.state != "ACCEPTED":
            raise ValueError("diagram_generation_unavailable")
        actual = descriptor(row, resource)
        if (
            actual.reference != ref
            or row.accepted_reference != ref.model_dump(mode="json")
            or not row.acceptance_context
            or row.acceptance_context.get("reference") != row.accepted_reference
            or row.acceptance_context.get("attempt_id") != str(row.attempt_id)
        ):
            raise ValueError("diagram_integrity_error")
        return actual.manifest

    def recheck(self, scope: VersionScope, reference: ArtifactReference) -> None:
        with metadata_session(self.engine) as session, session.begin():
            self._exact(session, scope, reference)

    @contextmanager
    def pinned(
        self, scope: VersionScope, reference: ArtifactReference
    ) -> Iterator[DiagramArtifactManifest]:
        now, pid = datetime.now(UTC), uuid4()
        with metadata_session(self.engine) as session, session.begin():
            manifest = self._exact(session, scope, reference)
            pins = session.scalars(
                select(Pin.id)
                .where(Pin.generation_id == reference.generation_id)
                .limit(self.limits.max_pins_per_generation)
            ).all()
            if len(pins) >= self.limits.max_pins_per_generation:
                raise ValueError("diagram_store_unavailable")
            session.add(
                Pin(
                    id=pid,
                    generation_id=reference.generation_id,
                    actor_id=self.actor_id,
                    purpose=self.purpose,
                    created_at=now,
                    expires_at=now + timedelta(seconds=self.limits.pin_seconds),
                    token_hash=hashlib.sha256(uuid4().bytes).hexdigest(),
                )
            )
        try:
            yield manifest
        finally:
            # A cancelled/expired read still closes its pin. This separate,
            # bounded cleanup cannot extend the failed read or return content.
            token = _deadline.set(None)
            try:
                with (
                    metadata_session(self.engine, seconds=1) as session,
                    session.begin(),
                ):
                    row = session.get(Pin, pid)
                    if row is not None:
                        session.delete(row)
            finally:
                _deadline.reset(token)
