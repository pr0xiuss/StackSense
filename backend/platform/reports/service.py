"""C4 Architecture Analysis Report service, handler, reader, and cleanup.

This module coordinates C0 worker report generation, immutable storage,
read pin acquisition, and authorized version-scoped metadata and downloads.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, time
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.platform.analysis.architecture.dto import ArchitectureVersionResponse
from backend.platform.delivery.api_contracts import RetryRequest
from backend.platform.delivery.artifacts import VerifiedArtifactHandle
from backend.platform.delivery.contracts import (
    ArtifactReference,
    AttemptIdentity,
    AttemptRetirementReader,
    CandidateSeal,
    DeliveryExecutionFailure,
    DeliveryFailure,
    ExecutionStopped,
    HandlerProfile,
    PreparedOutput,
    ProducerProfile,
    RetryClass,
    VersionScope,
    WorkExecutionContext,
    WorkKind,
    WorkSlot,
)
from backend.platform.delivery.service import DeliveryCoordinator
from backend.platform.reports.api_contracts import (
    ReportCollection,
    ReportGenerationPage,
    ReportGenerationSummary,
    ReportRetryResponse,
    ReportSlotStatus,
    ReportSummary,
)
from backend.platform.reports.artifacts import (
    CandidateReportWriter,
    LocalReportArtifactStore,
    ReportOperatorGC,
)
from backend.platform.reports.configuration import ReportLimits
from backend.platform.reports.contracts import (
    ReportArtifactManifest,
    ReportArtifactMember,
    ReportReadPort,
    ReportSpec,
)
from backend.platform.reports.cursors import (
    ReportCursor,
    ReportCursorKey,
    ReportCursorSigner,
)
from backend.platform.reports.model import c4_canonical_bytes
from backend.platform.reports.pdf import ReportLabPdfRenderer
from backend.platform.reports.persistence import (
    ReportGenerationModel as Generation,
)
from backend.platform.reports.persistence import (
    ReportResourceModel as Resource,
)
from backend.platform.reports.preparation import ReportPreparer
from backend.platform.reports.repository import (
    ReportRepository,
    descriptor,
    metadata_session,
)


def _canonical_scope(record: ArchitectureVersionResponse) -> VersionScope:
    values = record.model_dump()
    values.update(
        architecture_version_id=record.id,
        canonical_digest=record.content_digest,
        source_contract_version="1.0.0",
        analyzer_version=getattr(record, "analyzer_version", "1.0.0"),
        configuration_fingerprint=getattr(
            record, "configuration_fingerprint", "source-config-fingerprint"
        ),
    )
    return VersionScope.model_validate(
        {k: values[k] for k in VersionScope.model_fields if k in values}
    )


class ReportWorkHandler:
    """C0 work handler for the Architecture Analysis Report."""

    def __init__(
        self,
        *,
        binding: HandlerProfile,
        engine_or_session: Engine | Session | Callable[[], Session],
        preparer: ReportPreparer,
        renderer: ReportLabPdfRenderer,
        limits: ReportLimits | None = None,
        writer_factory: (
            Callable[[AttemptIdentity, UUID, UUID, ReportLimits], CandidateReportWriter]
            | None
        ) = None,
    ) -> None:
        binding = HandlerProfile.model_validate(binding)
        if (
            binding.slot.kind != WorkKind.REPORT
            or binding.slot.template != "architecture_analysis"
            or any(
                getattr(binding.profile, name) != "1.0.0"
                for name in (
                    "producer_version",
                    "generator_version",
                    "output_schema_version",
                )
            )
        ):
            raise ValueError("report_contract_unsupported")

        self.binding = binding
        self._engine_or_session = engine_or_session
        self.preparer = preparer
        self.renderer = renderer
        self.limits = limits or ReportLimits()
        self.writer_factory = (
            writer_factory
            if writer_factory is not None
            else lambda att, cid, aid, lim: CandidateReportWriter(
                attempt=att, candidate_id=cid, artifact_id=aid, limits=lim
            )
        )

    @contextmanager
    def _get_session(self) -> Iterator[Session]:
        if isinstance(self._engine_or_session, Session):
            yield self._engine_or_session
        elif isinstance(self._engine_or_session, Engine):
            with Session(self._engine_or_session) as session:
                yield session
        else:
            session = self._engine_or_session()
            try:
                yield session
            finally:
                session.close()

    def execute(self, context: WorkExecutionContext) -> PreparedOutput:
        try:
            context = WorkExecutionContext.model_validate(context)
            work = context.attempt.work
            if (
                work.binding != self.binding
                or work.binding.slot.kind != WorkKind.REPORT
                or work.binding.slot.template != "architecture_analysis"
            ):
                raise ValueError("report_contract_unsupported")

            if (
                context.prerequisites is None
                or len(context.prerequisites.diagrams) != 4
            ):
                raise ValueError("report_prerequisites_missing")

            deadline = min(
                monotonic() + self.limits.total_execution_timeout_seconds,
                monotonic() + (context.deadline - datetime.now(UTC)).total_seconds(),
            )
            if monotonic() >= deadline:
                raise TimeoutError("report_timeout")

            return self._execute(context, deadline)
        except ExecutionStopped, DeliveryExecutionFailure:
            raise
        except Exception as exc:
            code = str(exc)
            if isinstance(exc, TimeoutError) or code == "report_limit_exceeded":
                code, retry = "report_limit_exceeded", RetryClass.CAPACITY
            elif code in (
                "report_store_unavailable",
                "report_source_unavailable",
            ) or isinstance(exc, (OSError, OperationalError)):
                code, retry = "report_store_unavailable", RetryClass.TRANSIENT
            elif "prerequisite" in code.lower() or code in (
                "report_contract_unsupported",
                "report_input_invalid",
                "report_prerequisites_missing",
            ):
                code, retry = "report_prerequisites_missing", RetryClass.PERMANENT
            elif isinstance(exc, ValueError):
                code, retry = "report_integrity_error", RetryClass.INTEGRITY
            else:
                code, retry = "report_internal_error", RetryClass.PERMANENT

            raise DeliveryExecutionFailure(
                DeliveryFailure(
                    code=code,
                    retry_class=retry,
                    source_capability="reports",
                )
            ) from exc

    def _execute(
        self, context: WorkExecutionContext, deadline: float
    ) -> PreparedOutput:
        work = context.attempt.work
        scope = work.scope
        binding = work.binding
        input_fp = work.input_fingerprint
        candidate_id = context.attempt.candidate_id

        # 1. Prepare report spec, snapshot, and prepared diagram placements
        spec, snapshot, prepared_report = self.preparer.prepare(context)
        if monotonic() >= deadline:
            raise TimeoutError("report_timeout")

        # 2. Check replay and allocate candidate in metadata repository
        with self._get_session() as session:
            repo = ReportRepository(session)
            resource = repo.get_or_create_resource(scope, binding, input_fp)
            repo.capture_snapshot(resource.id, snapshot)
            session.commit()

            prior_gen = repo.get_generation(resource.id, candidate_id)
            if prior_gen is not None and prior_gen.state in (
                "SEALED_VERIFIED",
                "ACCEPTED",
            ):
                desc = descriptor(prior_gen, resource)
                candidate_seal = CandidateSeal(
                    generation_id=prior_gen.id,
                    artifact_id=prior_gen.artifact_id,
                    size_bytes=prior_gen.manifest_size or 0,
                    digests=desc.reference.digests,
                    sealed=True,
                )
                return PreparedOutput(
                    attempt=context.attempt,
                    candidate=candidate_seal,
                )

            artifact_id = uuid4()
            repo.allocate_candidate(context.attempt, candidate_id, artifact_id)
            session.commit()

        # 3. Render PDF deterministically
        rendered = self.renderer.render(
            prepared_report, deadline=deadline, control=context.control
        )
        if monotonic() >= deadline:
            raise TimeoutError("report_timeout")

        # 4. Stage artifacts on candidate storage
        writer = self.writer_factory(
            context.attempt, candidate_id, artifact_id, self.limits
        )
        page_placement_digest = hashlib.sha256(
            c4_canonical_bytes(
                [p.model_dump(mode="python") for p in prepared_report.page_placements]
            )
        ).hexdigest()
        manifest, seal, prepared_output = writer.stage_artifacts(
            spec=spec,
            pdf_bytes=rendered.pdf_bytes,
            pdf_sha256=rendered.sha256,
            page_count=rendered.page_count,
            source_snapshot_digest=snapshot.snapshot_digest,
            renderer_profile_digest=rendered.renderer_profile_digest,
            limits_digest=self.limits.limits_digest(),
            page_placement_digest=page_placement_digest,
        )
        if monotonic() >= deadline:
            raise TimeoutError("report_timeout")

        # 5. Record sealed verification in metadata repository
        seal_proof = {
            "verification_version": "1.0.0",
            "manifest_sha256": seal.digests.content,
            "pdf_sha256": rendered.sha256,
            "sealed_at": datetime.now(UTC).isoformat(),
        }
        with self._get_session() as session:
            repo = ReportRepository(session)
            repo.record_sealed(
                generation_id=candidate_id,
                manifest=manifest,
                seal_proof=seal_proof,
                pdf_bytes=rendered.pdf_bytes,
                pdf_sha256=rendered.sha256,
                page_count=rendered.page_count,
            )
            session.commit()

        return prepared_output


class ReportReader(ReportReadPort):
    """Consumer port for reading published report specs and verified handles."""

    def __init__(
        self,
        store: LocalReportArtifactStore,
        limits: ReportLimits | None = None,
    ) -> None:
        self.store = store
        self.limits = limits or ReportLimits()

    def read_exact(
        self, scope: VersionScope, reference: ArtifactReference
    ) -> tuple[ReportSpec, ReportArtifactManifest]:
        handle = self.store.open_exact(scope, reference, member="spec")
        try:
            raw = handle.read(self.limits.max_spec_bytes)
            spec = ReportSpec.from_bytes(raw, max_bytes=self.limits.max_spec_bytes)
            desc = self.store.authority.descriptor(scope, reference)
            return spec, desc.manifest
        finally:
            handle.close()

    def open_exact(
        self,
        scope: VersionScope,
        reference: ArtifactReference,
        member: Literal["spec", "pdf"] = "pdf",
    ) -> VerifiedArtifactHandle:
        return self.store.open_exact(scope, reference, member=member)


class ReportCleanupService:
    """Orphan cleaner coordinating attempt retirement proofs and disk deletion."""

    def __init__(
        self,
        engine: Engine,
        limits: ReportLimits | None = None,
        store_root: Path | None = None,
    ) -> None:
        self.engine = engine
        self.limits = limits or ReportLimits()
        self.gc = ReportOperatorGC(root=store_root)

    def cleanup_unaccepted(
        self,
        candidate_id: UUID,
        actor_id: UUID,
        retirement_reader: AttemptRetirementReader,
        grace_seconds: float = 300.0,
    ) -> bool:
        with metadata_session(self.engine) as session, session.begin():
            repo = ReportRepository(session)
            reserved = repo.reserve_for_deletion(
                candidate_id, actor_id, retirement_reader
            )
            if not reserved:
                return False

        return self.gc.cleanup_unaccepted(candidate_id, grace_seconds=grace_seconds)


class ReportService:
    """Read and retry coordinator for the Architecture Analysis Report API."""

    def __init__(
        self,
        engine: Engine,
        reader: ReportReader,
        limits: ReportLimits,
        cursor_signer: ReportCursorSigner,
        actor_id: UUID | None = None,
    ) -> None:
        self.engine = engine
        self.reader = reader
        self.limits = limits
        self.signer = cursor_signer
        self.actor_id = actor_id

    def summary(
        self,
        record: ArchitectureVersionResponse,
        runtime: DeliveryCoordinator | None,
        role: str,
        generation_id: UUID | None = None,
    ) -> ReportSummary:
        scope = _canonical_scope(record)
        now = datetime.now(UTC)

        default_profile = HandlerProfile(
            slot=WorkSlot(kind=WorkKind.REPORT, template="architecture_analysis"),
            profile=ProducerProfile(
                producer_id="stacksense.reports",
                producer_version="1.0.0",
                generator_version="1.0.0",
                output_schema_version="1.0.0",
                configuration_fingerprint="0" * 64,
            ),
        )

        with metadata_session(self.engine) as session:
            if generation_id is not None:
                gen = session.get(Generation, generation_id)
                if gen is None or gen.state != "ACCEPTED":
                    raise ValueError("report_not_found")
                res = session.get(Resource, gen.resource_id)
                if res is None or res.architecture_version_id != record.id:
                    raise ValueError("report_not_found")

                desc = descriptor(gen, res)
                return ReportSummary(
                    scope=scope,
                    report_id=res.id,
                    report_type="architecture_analysis",
                    profile=desc.reference.binding,
                    input_fingerprint=gen.input_fingerprint,
                    availability="READY",
                    readability="verified",
                    reference=desc.reference,
                    pdf_size_bytes=gen.pdf_size,
                    pdf_sha256=gen.pdf_sha256,
                    page_count=gen.page_count,
                    spec_digest=gen.spec_digest,
                    created_at=gen.created_at,
                    accepted_at=gen.accepted_at,
                    observed_at=now,
                )

            # Active report summary
            stmt = (
                select(Resource)
                .where(Resource.architecture_version_id == record.id)
                .order_by(Resource.created_at.desc())
            )
            res = session.scalars(stmt).first()

            if res is not None and res.accepted_generation_id is not None:
                gen = session.get(Generation, res.accepted_generation_id)
                if gen is not None and gen.state == "ACCEPTED":
                    desc = descriptor(gen, res)
                    return ReportSummary(
                        scope=scope,
                        report_id=res.id,
                        report_type="architecture_analysis",
                        profile=desc.reference.binding,
                        input_fingerprint=gen.input_fingerprint,
                        availability="READY",
                        readability="verified",
                        reference=desc.reference,
                        pdf_size_bytes=gen.pdf_size,
                        pdf_sha256=gen.pdf_sha256,
                        page_count=gen.page_count,
                        spec_digest=gen.spec_digest,
                        created_at=gen.created_at,
                        accepted_at=gen.accepted_at,
                        observed_at=now,
                    )

            # Not ready / in progress / not scheduled
            availability = "NOT_SCHEDULED"
            if runtime is not None:
                try:
                    delivery_sum = runtime.summary(scope, role)
                    report_work = delivery_sum.report
                    if report_work is not None:
                        availability = report_work.state
                    else:
                        availability = "WAITING_FOR_DIAGRAMS"
                except Exception:
                    availability = "UNAVAILABLE"

            res_id = res.id if res is not None else uuid4()
            created_at = res.created_at if res is not None else now
            return ReportSummary(
                scope=scope,
                report_id=res_id,
                report_type="architecture_analysis",
                profile=default_profile,
                input_fingerprint="0" * 64,
                availability=availability,
                readability="unknown",
                reference=None,
                pdf_size_bytes=None,
                pdf_sha256=None,
                page_count=None,
                spec_digest=None,
                created_at=created_at,
                accepted_at=None,
                observed_at=now,
            )

    def collection(
        self,
        record: ArchitectureVersionResponse,
        runtime: DeliveryCoordinator | None,
        role: str,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ReportCollection:
        scope = _canonical_scope(record)
        now = datetime.now(UTC)

        status_str = "NOT_SCHEDULED"
        waiting_on: tuple[str, ...] = ()
        ref: ArtifactReference | None = None

        if runtime is not None:
            try:
                delivery_sum = runtime.summary(scope, role)
                report_work = delivery_sum.report
                if report_work is not None:
                    status_str = report_work.state
                    ref = report_work.reference
                else:
                    status_str = "WAITING_FOR_DIAGRAMS"

                waiting_on = tuple(
                    str(getattr(d.template, "value", d.template))
                    for d in delivery_sum.diagrams
                    if d.template is not None and d.state != "COMPLETED"
                )
            except Exception:
                status_str = "UNAVAILABLE"

        slot_status = ReportSlotStatus(
            status=status_str,
            waiting_on=waiting_on,
            reference=ref,
        )

        items: list[ReportSummary] = []
        with metadata_session(self.engine) as session:
            stmt = (
                select(Resource)
                .where(Resource.architecture_version_id == record.id)
                .order_by(Resource.created_at.desc())
                .limit(limit)
            )
            resources = list(session.scalars(stmt))
            for res in resources:
                if res.accepted_generation_id is not None:
                    gen = session.get(Generation, res.accepted_generation_id)
                    if gen is not None and gen.state == "ACCEPTED":
                        desc = descriptor(gen, res)
                        items.append(
                            ReportSummary(
                                scope=scope,
                                report_id=res.id,
                                report_type="architecture_analysis",
                                profile=desc.reference.binding,
                                input_fingerprint=gen.input_fingerprint,
                                availability="READY",
                                readability="verified",
                                reference=desc.reference,
                                pdf_size_bytes=gen.pdf_size,
                                pdf_sha256=gen.pdf_sha256,
                                page_count=gen.page_count,
                                spec_digest=gen.spec_digest,
                                created_at=gen.created_at,
                                accepted_at=gen.accepted_at,
                                observed_at=now,
                            )
                        )

        return ReportCollection(
            scope=scope,
            automatic=slot_status,
            items=tuple(items),
            next_cursor=None,
        )

    def generations(
        self,
        record: ArchitectureVersionResponse,
        report_id: UUID,
        actor_id: UUID,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ReportGenerationPage:
        scope = _canonical_scope(record)

        if cursor is not None:
            c = self.signer.read(cursor)
            if (
                c.operation != "generations"
                or c.report_id != report_id
                or c.actor_id != actor_id
                or c.version_id != record.id
            ):
                raise ValueError("report_cursor_invalid")

        with metadata_session(self.engine) as session:
            res = session.get(Resource, report_id)
            if res is None or res.architecture_version_id != record.id:
                raise ValueError("report_not_found")

            stmt = (
                select(Generation)
                .where(
                    Generation.resource_id == report_id,
                    Generation.state == "ACCEPTED",
                )
                .order_by(Generation.accepted_at.desc(), Generation.id.desc())
            )
            if cursor is not None:
                c = self.signer.read(cursor)
                if c.after.accepted_at is not None:
                    stmt = stmt.where(
                        (Generation.accepted_at < c.after.accepted_at)
                        | (
                            (Generation.accepted_at == c.after.accepted_at)
                            & (Generation.id < c.after.id)
                        )
                    )

            rows = list(session.scalars(stmt.limit(limit + 1)))

            next_cursor = None
            if len(rows) > limit:
                rows = rows[:limit]
                last = rows[-1]
                next_cursor = self.signer.issue(
                    ReportCursor(
                        kid=self.signer.key_id,
                        operation="generations",
                        actor_id=actor_id,
                        project_id=record.project_id,
                        version_id=record.id,
                        report_id=report_id,
                        after=ReportCursorKey(
                            accepted_at=last.accepted_at,
                            id=last.id,
                        ),
                        issued_at=int(time()),
                        expires_at=int(time()) + self.signer.ttl,
                    )
                )

            items = tuple(
                ReportGenerationSummary(
                    generation_id=row.id,
                    artifact_id=row.artifact_id,
                    accepted_at=row.accepted_at or datetime.now(UTC),
                    page_count=row.page_count or 1,
                    pdf_size_bytes=row.pdf_size or 0,
                    pdf_sha256=row.pdf_sha256 or ("0" * 64),
                    report_spec_digest=row.spec_digest or ("0" * 64),
                    reference=descriptor(row, res).reference,
                )
                for row in rows
            )

            return ReportGenerationPage(
                scope=scope,
                report_id=report_id,
                items=items,
                next_cursor=next_cursor,
            )

    def generation_detail(
        self,
        record: ArchitectureVersionResponse,
        report_id: UUID,
        generation_id: UUID,
    ) -> ReportGenerationSummary:
        with metadata_session(self.engine) as session:
            res = session.get(Resource, report_id)
            if res is None or res.architecture_version_id != record.id:
                raise ValueError("report_not_found")

            gen = session.get(Generation, generation_id)
            if gen is None or gen.resource_id != report_id or gen.state != "ACCEPTED":
                raise ValueError("report_not_found")

            return ReportGenerationSummary(
                generation_id=gen.id,
                artifact_id=gen.artifact_id,
                accepted_at=gen.accepted_at or datetime.now(UTC),
                page_count=gen.page_count or 1,
                pdf_size_bytes=gen.pdf_size or 0,
                pdf_sha256=gen.pdf_sha256 or ("0" * 64),
                report_spec_digest=gen.spec_digest or ("0" * 64),
                reference=descriptor(gen, res).reference,
            )

    def open_pdf(
        self,
        record: ArchitectureVersionResponse,
        report_id: UUID,
        generation_id: UUID | None = None,
    ) -> tuple[
        VerifiedArtifactHandle, ReportArtifactMember, ArchitectureVersionResponse
    ]:
        with metadata_session(self.engine) as session:
            res = session.get(Resource, report_id)
            if res is None or res.architecture_version_id != record.id:
                raise ValueError("report_not_found")

            target_gen_id = (
                generation_id
                if generation_id is not None
                else res.accepted_generation_id
            )
            if target_gen_id is None:
                raise ValueError("report_not_ready")

            gen = session.get(Generation, target_gen_id)
            if gen is None or gen.resource_id != report_id or gen.state != "ACCEPTED":
                raise ValueError("report_not_found")

            desc = descriptor(gen, res)
            ref = desc.reference
            manifest = desc.manifest
            pdf_member = next((m for m in manifest.members if m.member == "pdf"), None)
            if pdf_member is None:
                raise ValueError("report_integrity_error")

        handle = self.reader.open_exact(ref.scope, ref, member="pdf")
        return handle, pdf_member, record

    def retry(
        self,
        record: ArchitectureVersionResponse,
        report_id: UUID,
        idempotency_key: str,
        actor_id: UUID,
        role: str,
        runtime: DeliveryCoordinator | None,
    ) -> ReportRetryResponse:
        scope = _canonical_scope(record)
        if role not in {"OWNER", "ADMIN"}:
            raise ValueError("report_forbidden")

        if runtime is None:
            raise ValueError("report_runtime_unavailable")

        with metadata_session(self.engine) as session:
            res = session.get(Resource, report_id)
            if res is None or res.architecture_version_id != record.id:
                raise ValueError("report_not_found")

        delivery_sum = runtime.summary(scope, role)
        report_work = delivery_sum.report
        if (
            report_work is None
            or report_work.state != "FAILED"
            or report_work.work_id is None
        ):
            raise ValueError("report_conflict")

        retry_req = RetryRequest(
            resource_type=WorkKind.REPORT,
            resource_id=report_work.work_id,
            idempotency_key=idempotency_key,
        )
        retry_accepted = runtime.retry(
            scope, retry_req, actor_id=actor_id, actor_role=role
        )

        return ReportRetryResponse(
            scope=scope,
            report_id=report_id,
            work_id=retry_accepted.work_id,
            operation_id=retry_accepted.operation_id,
            state="PENDING",
        )


__all__ = [
    "ReportCleanupService",
    "ReportReader",
    "ReportService",
    "ReportWorkHandler",
]
