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

from sqlalchemy import literal, select, text, tuple_
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.platform.analysis.architecture.dto import ArchitectureVersionResponse
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
    RetryClass,
    VersionScope,
    WorkExecutionContext,
    WorkKind,
)
from backend.platform.delivery.service import DeliveryCoordinator
from backend.platform.reports.api_contracts import (
    ReportCollection,
    ReportGenerationPage,
    ReportGenerationSummary,
    ReportSlotStatus,
    ReportSummary,
)
from backend.platform.reports.artifacts import (
    CandidateReportWriter,
    LocalReportArtifactStore,
    ReportOperatorGC,
    generation_lock,
)
from backend.platform.reports.configuration import ReportLimits
from backend.platform.reports.contracts import (
    DiagramsSection,
    PreparedReport,
    ReportArtifactManifest,
    ReportArtifactMember,
    ReportInputSnapshot,
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
from backend.platform.reports.render_runtime import IsolatedReportRenderRuntime
from backend.platform.reports.repository import (
    ReportRepository,
    descriptor,
    metadata_session,
)


class ReportWorkHandler:
    """C0 work handler for the Architecture Analysis Report."""

    def __init__(
        self,
        *,
        binding: HandlerProfile,
        engine_or_session: Engine | Session | Callable[[], Session],
        preparer: ReportPreparer,
        renderer: ReportLabPdfRenderer | IsolatedReportRenderRuntime,
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

        # Capture once. Retries never query upstream after a snapshot has committed.
        import json

        with self._get_session() as session:
            repo = ReportRepository(session)
            resource = repo.get_or_create_resource(scope, binding, input_fp)
            resource_id = resource.id
            captured = resource.captured_snapshot
            session.commit()
        if captured is None:
            _, proposed, _ = self.preparer.prepare(context)
            with self._get_session() as session:
                repo = ReportRepository(session)
                winner = repo.capture_snapshot(resource_id, proposed)
                captured = winner.captured_snapshot
                session.commit()
        snapshot = ReportInputSnapshot.model_validate_json(json.dumps(captured))
        spec = snapshot.report_spec
        diagram_section = spec.sections[2]
        if not isinstance(diagram_section, DiagramsSection):
            raise ValueError("report_integrity_error")
        prepared_report = PreparedReport(
            spec=spec,
            font_assets=snapshot.font_assets,
            page_placements=diagram_section.placements,
            renderer_profile_digest=self.preparer.profile.profile_digest(),
            limits_digest=self.limits.limits_digest(),
        )
        from backend.platform.reports.validation import ReportValidator

        ReportValidator(self.limits).validate(spec)
        if monotonic() >= deadline:
            raise TimeoutError("report_timeout")

        # 2. Check replay and allocate candidate in metadata repository
        with self._get_session() as session:
            repo = ReportRepository(session)
            resource = repo.get_or_create_resource(scope, binding, input_fp)
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

            allocated = repo.allocate_candidate(context.attempt, candidate_id, uuid4())
            artifact_id = allocated.artifact_id
            session.commit()

        # 3. Render PDF deterministically
        # Output admission only; M1 retains all scheduling/attempt ownership.
        with self._get_session() as admission:
            if admission.get_bind().dialect.name == "postgresql":
                key = int.from_bytes(
                    hashlib.sha256(
                        b"ss.report.render\0" + scope.project_id.bytes
                    ).digest()[:8],
                    "big",
                    signed=True,
                )
                admission.execute(text("SET LOCAL statement_timeout=1000"))
                if not admission.scalar(
                    text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key}
                ):
                    raise ValueError("report_limit_exceeded")
            rendered = self.renderer.render(
                prepared_report, deadline=deadline, control=context.control
            )
        if monotonic() >= deadline:
            raise TimeoutError("report_timeout")

        # 4. Stage artifacts on candidate storage
        writer = self.writer_factory(
            context.attempt, candidate_id, artifact_id, self.limits
        )

        def require_staging(attempt: AttemptIdentity) -> None:
            context.control.checkpoint()
            with self._get_session() as session:
                row = session.get(Generation, candidate_id)
                if (
                    row is None
                    or row.state != "STAGING"
                    or row.attempt_snapshot != attempt.model_dump(mode="json")
                    or row.artifact_id != artifact_id
                ):
                    raise ValueError("report_integrity_error")

        writer.require_staging = require_staging
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
            source_snapshot_digest=spec.metadata.source_snapshot_digest,
            renderer_profile_digest=rendered.renderer_profile_digest,
            limits_digest=self.limits.limits_digest(),
            page_placement_digest=page_placement_digest,
            asset_hashes=tuple(
                (name, digest) for name, digest, _ in snapshot.font_assets
            ),
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
            if (
                desc.reference != reference
                or spec.metadata.scope != scope
                or spec.metadata.profile != reference.binding
                or spec.metadata.report_id != reference.resource_id
                or spec.report_spec_digest != desc.manifest.report_spec_digest
                or spec.metadata.source_snapshot_digest
                != desc.manifest.source_snapshot_digest
                or tuple(d.receipt.receipt_id for d in spec.diagram_inputs)
                != desc.manifest.diagram_receipt_ids
                or tuple(
                    d.receipt.accepted.reference.digests.content
                    for d in spec.diagram_inputs
                )
                != desc.manifest.diagram_member_digests
            ):
                raise ValueError("report_integrity_error")
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

        def require_deleting(candidate_id: UUID) -> None:
            with metadata_session(self.engine) as session:
                row = session.get(Generation, candidate_id)
                if (
                    row is None
                    or row.state != "DELETING"
                    or row.accepted_reference is not None
                ):
                    raise PermissionError("report deletion not reserved")

        self.gc = ReportOperatorGC(root=store_root, require_deleting=require_deleting)

    def cleanup_unaccepted(
        self,
        candidate_id: UUID,
        actor_id: UUID,
        retirement_reader: AttemptRetirementReader,
        grace_seconds: float | None = None,
    ) -> bool:
        grace = (
            grace_seconds
            if grace_seconds is not None
            else self.limits.orphan_grace_seconds
        )
        if (
            grace is None
            or grace
            < self.limits.pin_ttl_seconds + self.limits.watchdog_kill_grace_seconds
        ):
            raise ValueError(
                "report cleanup grace requires measured safe configuration"
            )
        with generation_lock(self.gc.root, candidate_id):
            with metadata_session(self.engine) as session, session.begin():
                repo = ReportRepository(session)
                reserved = repo.reserve_for_deletion(
                    candidate_id, actor_id, retirement_reader
                )
                if not reserved:
                    return False
            done = self.gc.cleanup_unaccepted(candidate_id, grace_seconds=grace)
            if done:
                with metadata_session(self.engine) as session, session.begin():
                    row = session.get(Generation, candidate_id, with_for_update=True)
                    if row is None or row.state != "DELETING":
                        raise ValueError("report_integrity_error")
                    row.state, row.deleted_at = "DELETED", datetime.now(UTC)
            return done


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

    def _scope(
        self,
        record: ArchitectureVersionResponse,
        runtime: DeliveryCoordinator | None = None,
    ) -> VersionScope:
        import json

        with metadata_session(self.engine) as session:
            row = session.scalar(
                select(Resource)
                .where(
                    Resource.architecture_version_id == record.id,
                    Resource.project_id == record.project_id,
                )
                .order_by(Resource.id)
                .limit(1)
            )
            scope = (
                VersionScope.model_validate_json(json.dumps(row.scope)) if row else None
            )
        if scope is None and runtime is not None:
            scope = runtime.scope_for_record(record)
        if scope is None:
            raise ValueError("report_source_unavailable")
        if (
            scope.project_id,
            scope.architecture_version_id,
            scope.canonical_digest,
        ) != (record.project_id, record.id, record.content_digest):
            raise ValueError("report_integrity_error")
        return scope

    def summary(
        self,
        record: ArchitectureVersionResponse,
        runtime: DeliveryCoordinator | None,
        role: str,
        report_id: UUID,
        generation_id: UUID | None = None,
    ) -> ReportSummary:
        import json

        with metadata_session(self.engine) as session:
            resource = session.get(Resource, report_id)
            if (
                resource is None
                or resource.architecture_version_id != record.id
                or resource.project_id != record.project_id
            ):
                raise ValueError("report_not_found")
            scope = VersionScope.model_validate_json(json.dumps(resource.scope))
            target = generation_id or resource.accepted_generation_id
            generation = session.get(Generation, target) if target else None
            if generation_id is not None and (
                generation is None
                or generation.resource_id != report_id
                or generation.state != "ACCEPTED"
            ):
                raise ValueError("report_not_found")
            ref = (
                descriptor(generation, resource).reference
                if generation is not None and generation.state == "ACCEPTED"
                else None
            )
            return ReportSummary(
                scope=scope,
                report_id=resource.id,
                report_type="architecture_analysis",
                profile=HandlerProfile.model_validate_json(
                    json.dumps(resource.binding)
                ),
                input_fingerprint=resource.input_fingerprint,
                availability="READY" if ref else "BUILDING",
                readability="metadata_only" if ref else "unknown",
                reference=ref,
                pdf_size_bytes=generation.pdf_size if ref and generation else None,
                pdf_sha256=generation.pdf_sha256 if ref and generation else None,
                page_count=generation.page_count if ref and generation else None,
                spec_digest=generation.spec_digest if ref and generation else None,
                created_at=resource.created_at,
                accepted_at=generation.accepted_at if ref and generation else None,
                observed_at=datetime.now(UTC),
            )

    def collection(
        self,
        record: ArchitectureVersionResponse,
        runtime: DeliveryCoordinator | None,
        role: str,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ReportCollection:
        scope = self._scope(record, runtime)
        now = datetime.now(UTC)

        status_str = "NOT_SCHEDULED"
        waiting_on: tuple[str, ...] = ()
        ref: ArtifactReference | None = None
        report_work = None

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
            work=report_work,
        )

        items: list[ReportSummary] = []
        actor = self.actor_id
        if actor is None:
            raise ValueError("report_authentication_required")
        continuation = self.signer.read(cursor) if cursor else None
        if continuation is not None and (
            continuation.operation != "collection"
            or continuation.actor_id != actor
            or continuation.project_id != record.project_id
            or continuation.version_id != record.id
            or continuation.page_size != limit
            or continuation.high_water is None
            or continuation.profile != "all_profiles"
        ):
            raise ValueError("report_cursor_invalid")
        with metadata_session(self.engine) as session:
            stmt = (
                select(Resource)
                .where(
                    Resource.architecture_version_id == record.id,
                    Resource.project_id == record.project_id,
                    Resource.accepted_generation_id.is_not(None),
                )
                .order_by(Resource.created_at.desc(), Resource.id.desc())
            )
            if continuation is not None:
                upper = continuation.high_water
                assert upper is not None
                stmt = stmt.where(
                    tuple_(Resource.created_at, Resource.id)
                    <= tuple_(literal(upper.accepted_at), literal(upper.id)),
                    tuple_(Resource.created_at, Resource.id)
                    < tuple_(
                        literal(continuation.after.accepted_at),
                        literal(continuation.after.id),
                    ),
                )
            resources = list(session.scalars(stmt.limit(limit + 1)))
            more = len(resources) > limit
            resources = resources[:limit]
            high_water = (
                continuation.high_water
                if continuation
                else (
                    ReportCursorKey(
                        accepted_at=resources[0].created_at, id=resources[0].id
                    )
                    if resources
                    else None
                )
            )
            next_cursor = None
            if more and high_water is not None:
                issued = continuation.issued_at if continuation else int(time())
                next_cursor = self.signer.issue(
                    ReportCursor(
                        kid=self.signer.key_id,
                        operation="collection",
                        actor_id=actor,
                        project_id=record.project_id,
                        version_id=record.id,
                        after=ReportCursorKey(
                            accepted_at=resources[-1].created_at, id=resources[-1].id
                        ),
                        high_water=high_water,
                        page_size=limit,
                        profile="all_profiles",
                        issued_at=issued,
                        expires_at=(
                            continuation.expires_at
                            if continuation
                            else issued + self.signer.ttl
                        ),
                    )
                )
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
                                readability="metadata_only",
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
            next_cursor=next_cursor,
        )

    def generations(
        self,
        record: ArchitectureVersionResponse,
        report_id: UUID,
        actor_id: UUID,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ReportGenerationPage:
        scope = self._scope(record)

        if cursor is not None:
            c = self.signer.read(cursor)
            if (
                c.operation != "generations"
                or c.report_id != report_id
                or c.actor_id != actor_id
                or c.version_id != record.id
                or c.project_id != record.project_id
                or c.page_size != limit
                or c.high_water is None
            ):
                raise ValueError("report_cursor_invalid")

        with metadata_session(self.engine) as session:
            res = session.get(Resource, report_id)
            if res is None or res.architecture_version_id != record.id:
                raise ValueError("report_not_found")
            if cursor is not None and c.profile != res.binding_fingerprint:
                raise ValueError("report_cursor_invalid")

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
                assert c.high_water is not None
                stmt = stmt.where(
                    tuple_(Generation.accepted_at, Generation.id)
                    <= tuple_(
                        literal(c.high_water.accepted_at), literal(c.high_water.id)
                    )
                )
                if c.after.accepted_at is not None:
                    stmt = stmt.where(
                        (Generation.accepted_at < c.after.accepted_at)
                        | (
                            (Generation.accepted_at == c.after.accepted_at)
                            & (Generation.id < c.after.id)
                        )
                    )

            rows = list(session.scalars(stmt.limit(limit + 1)))
            high_water = (
                c.high_water
                if cursor is not None
                else (
                    ReportCursorKey(accepted_at=rows[0].accepted_at, id=rows[0].id)
                    if rows
                    else None
                )
            )

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
                        high_water=high_water,
                        profile=res.binding_fingerprint,
                        page_size=limit,
                        issued_at=c.issued_at if cursor is not None else int(time()),
                        expires_at=(
                            c.expires_at
                            if cursor is not None
                            else int(time()) + self.signer.ttl
                        ),
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
        generation_id: UUID,
    ) -> tuple[
        VerifiedArtifactHandle, ReportArtifactMember, ArchitectureVersionResponse
    ]:
        with metadata_session(self.engine) as session:
            res = session.get(Resource, report_id)
            if res is None or res.architecture_version_id != record.id:
                raise ValueError("report_not_found")

            target_gen_id = generation_id
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


__all__ = [
    "ReportCleanupService",
    "ReportReader",
    "ReportService",
    "ReportWorkHandler",
]
