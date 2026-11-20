"""C0 diagram producer and exact C2 consumer. No lifecycle/recovery ownership."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, ExitStack, contextmanager
from datetime import UTC, datetime
from threading import Lock
from time import monotonic, time
from typing import Literal, get_args
from uuid import UUID

from sqlalchemy.exc import OperationalError

from backend.platform.analysis.architecture.dto import ArchitectureVersionResponse
from backend.platform.delivery.contracts import (
    ArtifactReference,
    AttemptIdentity,
    AttemptRetirementReader,
    DeliveryContractError,
    DeliveryExecutionFailure,
    DeliveryFailure,
    DiagramTemplate,
    ExecutionStopped,
    HandlerProfile,
    PreparedOutput,
    RetryClass,
    VersionScope,
    WorkExecutionContext,
    WorkKind,
)
from backend.platform.delivery.service import DeliveryCoordinator
from backend.platform.diagrams import artifacts
from backend.platform.diagrams.api_contracts import (
    DiagramCapabilities,
    DiagramCollection,
    DiagramSummary,
    GenerationPage,
    GenerationSummary,
    MemberItem,
    MemberPage,
)
from backend.platform.diagrams.artifact_contracts import SealRequest
from backend.platform.diagrams.artifacts import (
    CandidateArtifactWriter,
    GeneratedArtifactStore,
    OperatorArtifactGC,
)
from backend.platform.diagrams.builders import build_from_source
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import (
    CanonicalDiagramScope,
    DiagramArtifactDescriptor,
    DiagramArtifactManifest,
    DiagramSpec,
    DiagramViewRequest,
    DiagramViewResponse,
    ErrorCode,
    LayoutProfile,
    LayoutSpec,
    MemberDescriptor,
    MembershipCatalog,
    PreparedDiagram,
    Ref,
    VerifiedMemberHandle,
)
from backend.platform.diagrams.cursors import CursorKey, CursorSigner, DiagramCursor
from backend.platform.diagrams.export import (
    LayoutEngine,
    member_payloads,
    prepare_layout,
    reuse_geometry,
    svg_bytes,
)
from backend.platform.diagrams.fonts import DiagramFonts
from backend.platform.diagrams.model import canonical_bytes, digest
from backend.platform.diagrams.query import DiagramSourceAdapter, SourceBudget
from backend.platform.diagrams.repository import (
    DiagramQueryRepository,
    DiagramRepository,
    metadata_operation,
    operation_deadline,
)
from backend.platform.diagrams.validation import DiagramValidator

_admission_lock = Lock()
_in_progress: dict[str, int] = {"build": 0, "read": 0}


@contextmanager
def _local_admission(kind: str, limit: int) -> Iterator[None]:
    with _admission_lock:
        if _in_progress[kind] >= limit:
            raise ValueError("diagram_store_unavailable")
        _in_progress[kind] += 1
    try:
        yield
    finally:
        with _admission_lock:
            _in_progress[kind] -= 1


@contextmanager
def _read_errors() -> Iterator[None]:
    try:
        yield
    except TimeoutError as exc:
        raise TimeoutError("diagram_timeout") from exc
    except (OSError, OperationalError) as exc:
        raise ValueError("diagram_store_unavailable") from exc
    except ValueError as exc:
        code = str(exc)
        raise ValueError(
            code if code in get_args(ErrorCode) else "diagram_integrity_error"
        ) from exc
    except Exception as exc:
        raise ValueError("diagram_internal_error") from exc


class _ReadHandle:
    def __init__(
        self, handle: VerifiedMemberHandle, admission: ExitStack, deadline: float
    ) -> None:
        self.handle, self.admission, self.deadline = handle, admission, deadline

    def read(self, size: int) -> bytes:
        try:
            with _read_errors(), metadata_operation(self.deadline):
                return self.handle.read(size)
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        try:
            with _read_errors():
                self.handle.close()
        finally:
            self.admission.close()


class DiagramWorkHandler:
    def __init__(
        self,
        *,
        binding: HandlerProfile,
        repository: DiagramRepository,
        source: Callable[[SourceBudget], AbstractContextManager[DiagramSourceAdapter]],
        layout: LayoutEngine,
        profile: LayoutProfile,
        limits: DiagramLimits,
        writer: CandidateArtifactWriter,
    ) -> None:
        binding = HandlerProfile.model_validate(binding)
        if (
            binding.slot.kind != WorkKind.DIAGRAM
            or not isinstance(binding.slot.template, DiagramTemplate)
            or any(
                getattr(binding.profile, name) != "1.0.0"
                for name in (
                    "producer_version",
                    "generator_version",
                    "output_schema_version",
                )
            )
        ):
            raise ValueError("diagram_contract_unsupported")
        self.binding, self.repository, self.source = binding, repository, source
        self.layout, self.profile, self.limits, self.writer = (
            layout,
            profile,
            limits,
            writer,
        )

    def execute(self, context: WorkExecutionContext) -> PreparedOutput:
        try:
            context = WorkExecutionContext.model_validate(context)
            deadline = monotonic() + min(
                self.limits.build_seconds,
                (context.deadline - datetime.now(UTC)).total_seconds(),
            )
            with (
                metadata_operation(deadline),
                _local_admission("build", self.limits.max_local_builds),
                self.repository.build_admission(
                    context.attempt.work.scope.project_id, self.limits
                ),
            ):
                if (
                    shutil.disk_usage(artifacts.STORE_ROOT / "staging").free
                    < self.limits.min_free_bytes
                ):
                    raise ValueError("diagram_store_unavailable")
                return self._execute(context)
        except ExecutionStopped, DeliveryExecutionFailure:
            raise
        except Exception as exc:
            code = str(exc)
            if isinstance(exc, TimeoutError) or code == "diagram_limit_exceeded":
                code, retry = "diagram_limit_exceeded", RetryClass.CAPACITY
            elif code in (
                "diagram_store_unavailable",
                "diagram_source_unavailable",
            ) or isinstance(exc, (OSError, OperationalError)):
                code, retry = "diagram_store_unavailable", RetryClass.TRANSIENT
            elif code in ("diagram_contract_unsupported", "diagram_input_invalid"):
                retry = RetryClass.PERMANENT
            elif isinstance(exc, ValueError):
                code, retry = "diagram_integrity_error", RetryClass.INTEGRITY
            else:
                code, retry = "diagram_internal_error", RetryClass.PERMANENT
            raise DeliveryExecutionFailure(
                DeliveryFailure(
                    code=code,
                    retry_class=retry,
                    source_capability="diagrams",
                )
            ) from exc

    def _execute(self, context: WorkExecutionContext) -> PreparedOutput:
        a = context.attempt
        if a.work.binding != self.binding or not isinstance(
            self.binding.slot.template, DiagramTemplate
        ):
            raise ValueError("diagram_contract_unsupported")
        deadline = min(
            monotonic() + self.limits.build_seconds,
            monotonic() + (context.deadline - datetime.now(UTC)).total_seconds(),
        )

        def check() -> None:
            context.control.checkpoint()
            if monotonic() >= deadline:
                raise TimeoutError("diagram_timeout")

        check()
        gid, aid = self.repository.reserve(a)
        prior = self.repository.prepared(a, gid)
        if prior is not None:
            # Replay never creates new bytes under an existing sealed identity.
            manifest = self.repository.sealed_manifest(a, gid)
            request = SealRequest(
                protocol=1,
                attempt=a,
                generation_id=gid,
                artifact_id=aid,
                members=manifest.members,
                manifest_sha256=prior.candidate.digests.content,
                manifest_size=prior.candidate.size_bytes,
            )
            self.writer.verify(request, deadline)
            check()
            return prior
        budget = SourceBudget(self.limits, deadline, check)
        with self.source(budget) as source:
            built = build_from_source(
                source,
                CanonicalDiagramScope.from_delivery(a.work.scope),
                self.binding.slot.template,
                budget,
            )
        check()
        fonts = DiagramFonts()
        try:
            layout = prepare_layout(
                built,
                fonts,
                self.layout,
                self.profile,
                self.limits,
                deadline,
                context.control,
            )
        finally:
            fonts.close()
        payloads = member_payloads(built, layout, self.limits, check)
        members = tuple(
            MemberDescriptor.model_validate_json(
                json.dumps(
                    dict(
                        member=name,
                        file_name="scene.svg" if name == "svg" else name + ".json",
                        media_type=(
                            "image/svg+xml" if name == "svg" else "application/json"
                        ),
                        schema_version="1.0.0",
                        size_bytes=len(data),
                        sha256=hashlib.sha256(data).hexdigest(),
                    )
                )
            )
            for name, data in sorted(payloads.items())
        )
        manifest = DiagramArtifactManifest(
            artifact_schema_version="1.0.0",
            scope=a.work.scope,
            binding=a.work.binding,
            input_fingerprint=a.work.input_fingerprint,
            diagram_id=built.spec.diagram_id,
            generation_id=gid,
            artifact_id=aid,
            semantic_digest=built.spec.semantic_digest,
            layout_digest=layout.layout_digest,
            membership_digest=built.spec.membership_digest,
            export_profile="svg_paths_v1",
            members=members,
            verification_version="1.0.0",
        )
        data = manifest.to_bytes()
        if len(data) > self.limits.max_manifest_bytes:
            raise ValueError("diagram_limit_exceeded")
        request = SealRequest(
            protocol=1,
            attempt=a,
            generation_id=gid,
            artifact_id=aid,
            members=manifest.members,
            manifest_size=len(data),
            manifest_sha256=hashlib.sha256(data).hexdigest(),
        )
        self.repository.stage_manifest(a, manifest, self.limits)
        check()
        self.writer.stage(request, data, payloads, deadline, check)
        check()
        proof = self.writer.seal(request, deadline, check)
        check()
        self.writer.verify(request, deadline)
        check()
        return self.repository.mark_sealed(a, gid, proof)


class DiagramReader:
    """M5 gets prepared integers/paths, never a font, SVG parser or lookup client."""

    def __init__(self, store: GeneratedArtifactStore, limits: DiagramLimits) -> None:
        self.store, self.limits = store, limits

    def read_exact(
        self, scope: VersionScope, reference: ArtifactReference
    ) -> PreparedDiagram:
        return self.read_verified(scope, reference)[0]

    def read_verified(
        self, scope: VersionScope, reference: ArtifactReference
    ) -> tuple[PreparedDiagram, bytes]:
        """Return prepared data and its already verified exact SVG in one read.

        The bytes are checked against deterministic rendering and the accepted
        descriptor before returning. Export callers must still recheck authority
        before committing their response, just as other exact-read callers do.
        """
        deadline = operation_deadline(self.limits.read_seconds)
        with (
            _read_errors(),
            metadata_operation(deadline),
            _local_admission("read", self.limits.max_local_reads),
        ):
            return self._read_exact(scope, reference, deadline)

    def _read_exact(
        self,
        scope: VersionScope,
        reference: ArtifactReference,
        deadline: float,
    ) -> tuple[PreparedDiagram, bytes]:
        data: dict[str, bytes] = {}
        for member in ("spec", "layout", "members", "svg"):
            if monotonic() >= deadline:
                raise TimeoutError("diagram_timeout")
            handle = self.store.open_exact(scope, reference, member)
            try:
                chunks: list[bytes] = []
                count = 0
                while True:
                    if monotonic() >= deadline:
                        raise TimeoutError("diagram_timeout")
                    chunk = handle.read(65536)
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > getattr(self.limits, f"max_{member}_bytes"):
                        raise ValueError("diagram_limit_exceeded")
                    chunks.append(chunk)
                data[member] = b"".join(chunks)
            finally:
                handle.close()
        spec = DiagramSpec.from_bytes(
            data["spec"], max_bytes=self.limits.max_spec_bytes
        )
        layout = LayoutSpec.from_bytes(
            data["layout"], max_bytes=self.limits.max_layout_bytes
        )
        catalog = MembershipCatalog.from_bytes(
            data["members"], max_bytes=self.limits.max_members_bytes
        )
        validator = DiagramValidator(self.limits)
        validator.semantic(spec, catalog)
        # svg_bytes below performs the full layout validator before emitting.
        # Do not perform the same expensive immutable-layout validation twice.

        # This deterministic exporter uses prepared paths only, not fonts/ELK.
        def check() -> None:
            if monotonic() >= deadline:
                raise TimeoutError("diagram_timeout")

        if svg_bytes(spec, layout, self.limits, check) != data["svg"]:
            raise ValueError("diagram_integrity_error")
        # The store's authority independently revalidates the committed descriptor.
        authority = self.store.authority
        with authority.pinned(scope, reference) as manifest:
            result = PreparedDiagram(
                spec=spec,
                layout=layout,
                descriptor=DiagramArtifactDescriptor(
                    manifest=manifest, reference=reference
                ),
            )
            authority.recheck(scope, reference)
            check()
            return result, data["svg"]

    def open_exact(
        self,
        scope: VersionScope,
        reference: ArtifactReference,
        member: Literal["spec", "layout", "members", "svg"],
    ) -> VerifiedMemberHandle:
        lease = ExitStack()
        try:
            with (
                _read_errors(),
                metadata_operation(operation_deadline(self.limits.read_seconds)),
            ):
                lease.enter_context(
                    _local_admission("read", self.limits.max_local_reads)
                )
                handle = self.store.open_exact(scope, reference, member)
                return _ReadHandle(
                    handle, lease.pop_all(), monotonic() + self.limits.stream_seconds
                )
        finally:
            lease.close()


class DiagramCleanupService:
    """Trusted operator entry only; no worker schedule, accepted-delete or sweep."""

    def __init__(
        self,
        repository: DiagramRepository,
        retirement: AttemptRetirementReader,
        gc: OperatorArtifactGC,
        limits: DiagramLimits,
    ) -> None:
        self.repository, self.retirement, self.gc, self.limits = (
            repository,
            retirement,
            gc,
            limits,
        )

    def delete_retired(
        self, attempt: AttemptIdentity, generation_id: UUID, actor_id: UUID
    ) -> None:
        deadline = operation_deadline(self.limits.read_seconds)
        with metadata_operation(deadline):
            nonce, deleted = self.repository.reserve_deletion(
                attempt, generation_id, self.retirement, actor_id, self.limits
            )
            if deleted:
                return
            self.gc.delete_reserved(generation_id, deadline)
            self.repository.mark_deleted(generation_id, nonce, actor_id)


def canonical_scope(record: ArchitectureVersionResponse) -> CanonicalDiagramScope:
    values = record.model_dump()
    values.update(
        architecture_version_id=record.id, canonical_digest=record.content_digest
    )
    return CanonicalDiagramScope.model_validate(
        {k: values[k] for k in CanonicalDiagramScope.model_fields}
    )


class DiagramService:
    """Authorized callers supply the exact public header; no lifecycle writes."""

    def __init__(
        self,
        repository: DiagramQueryRepository,
        reader: DiagramReader,
        limits: DiagramLimits,
        signer: CursorSigner,
        source: Callable[[SourceBudget], AbstractContextManager[DiagramSourceAdapter]],
        layout_factory: Callable[[PreparedDiagram], LayoutEngine],
    ) -> None:
        self.repository, self.reader, self.limits, self.signer = (
            repository,
            reader,
            limits,
            signer,
        )
        self.source, self.layout_factory = source, layout_factory

    def exact_reference(
        self,
        record: ArchitectureVersionResponse,
        template: DiagramTemplate,
        generation: UUID,
    ) -> ArtifactReference:
        ref, _, _ = self.repository.accepted(
            record.project_id, record.id, template, generation
        )
        if CanonicalDiagramScope.from_delivery(ref.scope) != canonical_scope(record):
            raise ValueError("diagram_integrity_error")
        return ref

    def prepared(
        self,
        record: ArchitectureVersionResponse,
        template: DiagramTemplate,
        generation: UUID,
    ) -> PreparedDiagram:
        ref = self.exact_reference(record, template, generation)
        return self.reader.read_exact(ref.scope, ref)

    def summary(
        self,
        record: ArchitectureVersionResponse,
        template: DiagramTemplate,
        runtime: DeliveryCoordinator | None,
        role: str,
        generation: UUID | None = None,
    ) -> DiagramSummary:
        scope = canonical_scope(record)
        try:
            known = (
                runtime.scope_for_record(record)
                if runtime is not None and generation is None
                else None
            )
        except DeliveryContractError as exc:
            raise ValueError("diagram_scope_mismatch") from exc
        work = None
        if runtime is not None and known is not None:
            try:
                status = runtime.summary(known, role)
            except DeliveryContractError as exc:
                raise ValueError("diagram_scope_mismatch") from exc
            work = next((w for w in status.diagrams if w.template == template), None)
        ref = (
            self.exact_reference(record, template, generation)
            if generation
            else (work.reference if work else None)
        )
        if work is not None and work.state == "COMPLETED" and ref is None:
            raise ValueError("diagram_integrity_error")
        if work is not None and (
            work.kind != WorkKind.DIAGRAM or (ref is not None and ref.scope != known)
        ):
            raise ValueError("diagram_integrity_error")
        verified_at = None
        if ref is not None:
            actual, _, verified_at = self.repository.accepted(
                record.project_id, record.id, template, ref.generation_id
            )
            if actual != ref or CanonicalDiagramScope.from_delivery(ref.scope) != scope:
                raise ValueError("diagram_integrity_error")
            if generation is None:
                self.repository.require_active(ref)
        available = ref is not None
        ambiguous = (
            not available
            and known is None
            and self.repository.has_accepted(record.project_id, record.id, template)
        )
        state: Literal[
            "NOT_SCHEDULED",
            "WAITING",
            "BUILDING",
            "READY",
            "FAILED",
            "CANCELLED",
            "UNAVAILABLE",
        ] = (
            "READY"
            if available
            else (
                "UNAVAILABLE"
                if runtime is None or ambiguous
                else (
                    "FAILED"
                    if work and work.state == "FAILED"
                    else (
                        "CANCELLED"
                        if work and work.state == "CANCELLED"
                        else (
                            "BUILDING"
                            if work and work.state == "RUNNING"
                            else "WAITING" if work else "NOT_SCHEDULED"
                        )
                    )
                )
            )
        )
        return DiagramSummary(
            template=template,
            canonical_scope=scope,
            delivery_scope=ref.scope if ref else known,
            work=work,
            availability=state,
            readability="unknown",
            verified_at=verified_at,
            reference=ref,
            coverage=None,
            counts=None,
            capabilities=DiagramCapabilities(
                read=available, view=available, json_export=available, svg=available
            ),
            reason=(
                "diagram_runtime_unavailable"
                if (runtime is None or ambiguous) and not available
                else None
            ),
            observed_at=datetime.now(UTC),
        )

    def collection(
        self,
        record: ArchitectureVersionResponse,
        runtime: DeliveryCoordinator | None,
        role: str,
    ) -> DiagramCollection:
        return DiagramCollection(
            canonical_scope=canonical_scope(record),
            items=tuple(
                self.summary(record, t, runtime, role) for t in DiagramTemplate
            ),
        )

    def _cursor(
        self,
        token: str | None,
        *,
        actor: UUID,
        record: ArchitectureVersionResponse,
        template: DiagramTemplate,
        operation: str,
        request_digest: str,
    ) -> DiagramCursor | None:
        if token is None:
            return None
        value = self.signer.read(token)
        if (
            value.actor_id,
            value.project_id,
            value.version_id,
            value.template,
            value.operation,
            value.request_digest,
        ) != (actor, record.project_id, record.id, template, operation, request_digest):
            raise ValueError("diagram_cursor_invalid")
        if value.mode != ("active" if operation == "history" else "exact"):
            raise ValueError("diagram_cursor_invalid")
        return value

    def history(
        self,
        record: ArchitectureVersionResponse,
        template: DiagramTemplate,
        actor: UUID,
        runtime: DeliveryCoordinator | None,
        role: str,
        limit: int,
        token: str | None,
    ) -> GenerationPage:
        deadline = operation_deadline(self.limits.read_seconds)
        with metadata_operation(deadline):
            request_hash = digest("ss.diagram.view", ("history", limit))
            cursor = self._cursor(
                token,
                actor=actor,
                record=record,
                template=template,
                operation="history",
                request_digest=request_hash,
            )
            current = self.summary(record, template, runtime, role).reference
            if current is None:
                raise ValueError(
                    "diagram_runtime_unavailable"
                    if runtime is None
                    else "diagram_not_ready"
                )
            if current.digests.spec is None:
                raise ValueError("diagram_integrity_error")
            if cursor and (
                cursor.resource_id,
                cursor.generation_id,
                cursor.semantic_digest,
            ) != (current.resource_id, current.generation_id, current.digests.spec):
                raise ValueError("diagram_generation_changed")
            high = (
                (cursor.high_water.accepted_at, cursor.high_water.id)
                if cursor and cursor.high_water and cursor.high_water.accepted_at
                else None
            )
            after = (
                (cursor.after.accepted_at, cursor.after.id)
                if cursor and cursor.after.accepted_at
                else None
            )
            rows = self.repository.history(current, limit, high, after)
            items = []
            for gid, accepted in rows[:limit]:
                value = self.prepared(record, template, gid)
                if value.descriptor.reference.resource_id != current.resource_id:
                    raise ValueError("diagram_integrity_error")
                items.append(
                    GenerationSummary(
                        generation_id=gid,
                        reference=value.descriptor.reference,
                        accepted_at=accepted,
                        coverage=value.spec.coverage,
                    )
                )
            next_cursor = None
            if len(rows) > limit:
                now = int(time())
                first, last = rows[0], rows[limit - 1]
                next_cursor = self.signer.issue(
                    DiagramCursor(
                        kid=self.signer.key_id,
                        operation="history",
                        actor_id=actor,
                        project_id=record.project_id,
                        version_id=record.id,
                        template=template,
                        resource_id=current.resource_id,
                        generation_id=current.generation_id,
                        semantic_digest=current.digests.spec,
                        request_digest=request_hash,
                        high_water=(
                            cursor.high_water
                            if cursor
                            else CursorKey(id=first[0], accepted_at=first[1])
                        ),
                        after=CursorKey(id=last[0], accepted_at=last[1]),
                        issued_at=cursor.issued_at if cursor else now,
                        expires_at=(
                            cursor.expires_at if cursor else now + self.signer.ttl
                        ),
                        mode="active",
                    )
                )
            # Both the M4 pointer and public M1 current selection must still match.
            self.repository.require_active(current)
            if self.summary(record, template, runtime, role).reference != current:
                raise ValueError("diagram_generation_changed")
            if monotonic() >= deadline:
                raise TimeoutError("diagram_timeout")
            return GenerationPage(
                scope=canonical_scope(record),
                template=template,
                items=tuple(items),
                next_cursor=next_cursor,
            )

    def members(
        self,
        record: ArchitectureVersionResponse,
        template: DiagramTemplate,
        generation: UUID,
        actor: UUID,
        group_id: str | None,
        entity_id: UUID | None,
        limit: int,
        token: str | None,
    ) -> MemberPage:
        deadline = operation_deadline(self.limits.read_seconds)
        with metadata_operation(deadline):
            if group_id is not None and entity_id is not None:
                raise ValueError("diagram_input_invalid")
            request_hash = digest(
                "ss.diagram.view",
                (
                    "members",
                    str(generation),
                    group_id,
                    str(entity_id) if entity_id else None,
                    limit,
                ),
            )
            cursor = self._cursor(
                token,
                actor=actor,
                record=record,
                template=template,
                operation="members",
                request_digest=request_hash,
            )
            try:
                value = self.prepared(record, template, generation)
            except ValueError as exc:
                if cursor and str(exc) == "diagram_generation_unavailable":
                    raise ValueError("diagram_generation_unavailable") from exc
                raise
            ref, spec = value.descriptor.reference, value.spec
            if cursor and (
                cursor.resource_id,
                cursor.generation_id,
                cursor.semantic_digest,
            ) != (ref.resource_id, generation, spec.semantic_digest):
                raise ValueError("diagram_cursor_invalid")
            handle = self.reader.open_exact(ref.scope, ref, "members")
            try:
                data = bytearray()
                while chunk := handle.read(65536):
                    data.extend(chunk)
                    if len(data) > self.limits.max_members_bytes:
                        raise ValueError("diagram_limit_exceeded")
                catalog = MembershipCatalog.from_bytes(
                    bytes(data), max_bytes=self.limits.max_members_bytes
                )
            finally:
                handle.close()
            chosen: dict[tuple[str, UUID], MemberItem] = {}

            def add(record_ref: Ref, reason: object = None) -> None:
                item = MemberItem.model_validate(dict(record=record_ref, reason=reason))
                chosen[(record_ref.record_type, record_ref.id)] = item

            if group_id is not None:
                group = next(
                    (g for g in catalog.groups if g.group_id == group_id), None
                )
                if group is None:
                    raise ValueError("diagram_not_found")
                for item in group.members:
                    add(item)
            elif entity_id is not None:
                node = next((n for n in spec.nodes if n.entity.id == entity_id), None)
                if node is None:
                    raise ValueError("diagram_not_found")
                for evidence in node.evidence:
                    add(evidence)
            else:
                for node in spec.nodes:
                    add(node.entity)
                for edge in spec.edges:
                    for member in edge.members:
                        add(member.relationship)
                for omitted in catalog.omitted:
                    add(omitted.record, omitted.reason)
            ordered = sorted(
                chosen.values(),
                key=lambda item: (item.record.record_type, item.record.id.bytes),
            )
            if cursor:
                # The signed UUID must identify exactly one last key in immutable bytes.
                positions = [
                    i
                    for i, item in enumerate(ordered)
                    if item.record.id == cursor.after.id
                ]
                if len(positions) != 1:
                    raise ValueError("diagram_cursor_invalid")
                start = positions[0] + 1
            else:
                start = 0
            items = tuple(ordered[start : start + limit])
            next_cursor = None
            if start + limit < len(ordered):
                now = int(time())
                next_cursor = self.signer.issue(
                    DiagramCursor(
                        kid=self.signer.key_id,
                        operation="members",
                        actor_id=actor,
                        project_id=record.project_id,
                        version_id=record.id,
                        template=template,
                        resource_id=ref.resource_id,
                        generation_id=generation,
                        semantic_digest=spec.semantic_digest,
                        request_digest=request_hash,
                        high_water=None,
                        after=CursorKey(accepted_at=None, id=items[-1].record.id),
                        issued_at=cursor.issued_at if cursor else now,
                        expires_at=(
                            cursor.expires_at if cursor else now + self.signer.ttl
                        ),
                        mode="exact",
                    )
                )
            self.reader.store.authority.recheck(ref.scope, ref)
            if monotonic() >= deadline:
                raise TimeoutError("diagram_timeout")
            return MemberPage(
                generation_id=generation,
                semantic_digest=spec.semantic_digest,
                group_id=group_id,
                items=items,
                total=len(ordered),
                next_cursor=next_cursor,
            )

    def view(
        self,
        record: ArchitectureVersionResponse,
        template: DiagramTemplate,
        generation: UUID,
        request: DiagramViewRequest,
    ) -> DiagramViewResponse:
        deadline = operation_deadline(self.limits.view_seconds)

        def check() -> None:
            if monotonic() >= deadline:
                raise TimeoutError("diagram_timeout")

        with (
            metadata_operation(deadline),
            _local_admission("build", self.limits.max_local_builds),
        ):
            base = self.prepared(record, template, generation)
            ref = base.descriptor.reference
            # All request dimensions are bounded before any public source scan.
            if (
                len(request.root_ids) > self.limits.max_focus_roots
                or len(request.selected_entity_ids) > self.limits.max_selected_ids
                or len(request.collapsed_group_ids) > self.limits.max_expanded_groups
                or request.depth > self.limits.max_depth
            ):
                raise ValueError("diagram_limit_exceeded")
            group_ids = {g.id for g in base.spec.groups}
            if not set(request.collapsed_group_ids) <= group_ids:
                raise ValueError("diagram_not_found")
            normalized = request.model_copy(update={"collapsed_group_ids": ()})
            budget = SourceBudget(self.limits, deadline, check)
            with self.source(budget) as source:
                # Explicit unknown root is a not-found, not a syntax error.
                for identity in (*request.root_ids, *request.selected_entity_ids):
                    if not source.contains_entity(base.spec.scope, identity, budget):
                        raise ValueError("diagram_not_found")
                built = build_from_source(
                    source, base.spec.scope, template, budget, normalized
                )
            reused = reuse_geometry(base, built, self.limits)
            if reused is not None:
                layout = reused
            else:
                engine = self.layout_factory(base)
                fonts = DiagramFonts()
                try:

                    class Control:
                        def checkpoint(self) -> None:
                            check()

                        def should_stop(self) -> bool:
                            return monotonic() >= deadline

                    layout = prepare_layout(
                        built,
                        fonts,
                        engine,
                        base.layout.profile,
                        self.limits,
                        deadline,
                        Control(),
                    )
                finally:
                    fonts.close()
            spec = built.spec
            if request.collapsed_group_ids:
                if not set(request.collapsed_group_ids) <= {g.id for g in spec.groups}:
                    raise ValueError("diagram_input_invalid")
                # Presentation collapse retains real topology and accepted geometry.
                payload = spec.model_dump(mode="json", exclude={"semantic_digest"})
                for group in payload["groups"]:
                    group["collapsed_default"] = (
                        group["id"] in request.collapsed_group_ids
                    )
                payload["semantic_digest"] = digest("ss.diagram.semantic", payload)
                spec = DiagramSpec.model_validate_json(canonical_bytes(payload))
                geometry = layout.model_dump(mode="json", exclude={"layout_digest"})
                geometry["semantic_digest"] = spec.semantic_digest
                geometry["layout_digest"] = digest("ss.diagram.layout", geometry)
                layout = LayoutSpec.model_validate_json(canonical_bytes(geometry))
            DiagramValidator(self.limits).semantic(spec, built.catalog)
            DiagramValidator(self.limits).layout(spec, layout)
            self.reader.store.authority.recheck(ref.scope, ref)
            check()
            return DiagramViewResponse(
                base_generation_id=generation,
                base_semantic_digest=base.spec.semantic_digest,
                request_digest=digest("ss.diagram.view", request),
                spec=spec,
                layout=layout,
            )
