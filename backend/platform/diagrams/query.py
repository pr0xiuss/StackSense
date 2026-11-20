"""Bounded immutable projection of public canonical pages, no private SQL.

The caller owns a read-only/cancellable session and execution control. This
adapter has no dependency on graph/search availability or M1 persistence.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from math import ceil
from threading import Event, Lock, Thread
from time import monotonic
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from backend.platform.analysis.application.dependencies import (
    get_architecture_query_service,
)
from backend.platform.analysis.architecture.dto import (
    ArchitectureCollectionResponse,
    ArchitectureConflictResponse,
    ArchitectureEntityResponse,
    ArchitectureEvidenceResponse,
    ArchitectureRelationshipResponse,
    ArchitectureUnresolvedResponse,
    ArchitectureVersionResponse,
)
from backend.platform.analysis.architecture.model import (
    ArchitectureEntityKind as Kind,
)
from backend.platform.analysis.architecture.model import (
    ArchitectureEvidencePolarity as Polarity,
)
from backend.platform.analysis.architecture.model import (
    ArchitectureEvidenceStrength as Strength,
)
from backend.platform.analysis.architecture.model import (
    ArchitectureFactStatus as Status,
)
from backend.platform.analysis.architecture.model import (
    ArchitectureRelationshipKind as Rel,
)
from backend.platform.analysis.architecture.service import ArchitectureQueryService
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import (
    T1024,
    CanonicalDiagramScope,
    ClosedRecord,
    CompletenessSnapshot,
    EntityRef,
    EvidenceProvenance,
    EvidenceRef,
    LogicalId,
    Ref,
    RelationshipRef,
    Short,
    Text,
)
from backend.platform.diagrams.model import canonical_bytes

Collection = Literal["entities", "relationships", "evidence", "unresolved", "conflicts"]


@contextmanager
def canonical_read_source(
    database_url: str, budget: SourceBudget, *, read_schema: str | None = None
) -> Iterator[DiagramSourceAdapter]:
    """Own every connection and cancel database work, not just the Python wait.

    No shared/global engine, borrowed producer Session or private upstream SQL.
    PostgreSQL read-only mode is a server-enforced connection default. Each
    statement receives the smaller remaining operation/statement/lock budget.
    """
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("diagram_source_unavailable")
    budget.check()
    if budget.deadline - monotonic() < 1:
        raise TimeoutError("diagram_timeout")
    remaining = max(1, ceil(budget.deadline - monotonic()))
    engine = create_engine(
        url.set(drivername="postgresql+psycopg"),
        poolclass=NullPool,
        connect_args={
            "connect_timeout": min(remaining, budget.limits.statement_seconds),
            "application_name": "stacksense.diagram.read."
            + str(UUID(int=int(monotonic() * 1000000))),
            "options": (
                "-c default_transaction_read_only=on "
                "-c statement_timeout="
                f"{min(remaining, budget.limits.statement_seconds)*1000} "
                f"-c lock_timeout={min(remaining, budget.limits.lock_seconds)*1000}"
            ),
        },
    )
    if read_schema is not None:
        import re

        if re.fullmatch(r"p5_diagram_[0-9a-f]{32}", read_schema) is None:
            engine.dispose()
            raise ValueError("diagram_source_unavailable")
        engine = engine.execution_options(schema_translate_map={None: read_schema})
    connections: list[Any] = []
    lock, done, expired = Lock(), Event(), Event()
    cancel_failures: list[Exception] = []

    @event.listens_for(engine, "connect")
    def connected(connection: Any, record: Any) -> None:
        if not callable(getattr(connection, "cancel_safe", None)):
            raise ValueError("diagram_source_unavailable")
        with lock:
            if expired.is_set():
                raise TimeoutError("diagram_timeout")
            connections.append(connection)

    @event.listens_for(engine, "before_cursor_execute")
    def bounded_statement(
        conn: Any,
        cursor: Any,
        statement: Any,
        parameters: Any,
        context: Any,
        executemany: Any,
    ) -> None:
        budget.check()
        millis = max(1, int((budget.deadline - monotonic()) * 1000))
        cursor.execute(
            "SET LOCAL statement_timeout = "
            f"{min(millis, budget.limits.statement_seconds * 1000)}"
        )
        cursor.execute(
            f"SET LOCAL lock_timeout = {min(millis, budget.limits.lock_seconds * 1000)}"
        )

    def watchdog() -> None:
        if done.wait(max(0, budget.deadline - monotonic())):
            return
        expired.set()
        with lock:
            active = tuple(connections)
        for connection in active:
            try:
                connection.cancel_safe(timeout=1)
            except Exception as exc:
                cancel_failures.append(exc)

    thread = Thread(target=watchdog, name="diagram-read-deadline")
    session = Session(engine)
    thread.start()
    try:
        try:
            yield DiagramSourceAdapter(get_architecture_query_service(session=session))
            budget.check()
        except Exception as exc:
            if expired.is_set() or monotonic() >= budget.deadline:
                raise TimeoutError("diagram_timeout") from exc
            raise
    finally:
        done.set()
        thread.join(timeout=2)
        try:
            session.close()
        finally:
            engine.dispose()
        if thread.is_alive() or cancel_failures:
            raise RuntimeError("diagram_source_cancellation_failed")


@dataclass(slots=True)
class SourceBudget:
    limits: DiagramLimits
    deadline: float
    checkpoint: Callable[[], None]
    rows: int = 0
    calls: int = 0
    bytes: int = 0
    passes: dict[tuple[UUID, str], int] = field(default_factory=dict)

    def check(self) -> None:
        self.checkpoint()
        if monotonic() >= self.deadline:
            raise TimeoutError("diagram_timeout")

    def call(self) -> None:
        self.check()
        self.calls += 1
        if self.calls > self.limits.max_source_calls:
            raise ValueError("diagram_limit_exceeded")

    def record(self, size: int) -> None:
        self.check()
        self.rows += 1
        self.bytes += size
        if (
            self.rows > self.limits.max_source_rows
            or self.bytes > self.limits.max_input_bytes
        ):
            raise ValueError("diagram_limit_exceeded")

    def begin_scan(self, version_id: UUID, collection: str) -> None:
        key = (version_id, collection)
        count = self.passes.get(key, 0) + 1
        if count > 2:
            raise ValueError("diagram_limit_exceeded")
        self.passes[key] = count


class SourceEntity(ClosedRecord):
    record: EntityRef
    kind: Kind
    name: Text
    namespace: Annotated[tuple[T1024, ...], Field(max_length=64)]
    status: Status
    evidence_ids: tuple[LogicalId, ...]


class SourceRelationship(ClosedRecord):
    record: RelationshipRef
    kind: Rel
    source_logical_id: LogicalId
    target_logical_id: LogicalId
    status: Status
    evidence_ids: tuple[LogicalId, ...]


class SourceUnresolved(ClosedRecord):
    record: Ref
    kind: Rel
    source_logical_id: LogicalId
    target_descriptor: Text
    reason: Short
    status: Status
    evidence_ids: tuple[LogicalId, ...]
    candidate_references: tuple[LogicalId, ...]


class SourceConflict(ClosedRecord):
    record: Ref
    conflict_type: Short
    subject_key: LogicalId
    evidence_ids: tuple[LogicalId, ...]


SourceRecord = (
    SourceEntity
    | SourceRelationship
    | EvidenceProvenance
    | SourceUnresolved
    | SourceConflict
)


class DiagramInput(ClosedRecord):
    """Request-local canonical projection, never a cache or persisted model.

    Evidence may be restricted to the exact references requested by a builder;
    evidence_total records the exhausted canonical scan, not a guessed count.
    Builders reject every missing evidence reference they actually emit.
    """

    scope: CanonicalDiagramScope
    completeness: CompletenessSnapshot
    entities: tuple[SourceEntity, ...]
    relationships: tuple[SourceRelationship, ...]
    evidence: tuple[EvidenceProvenance, ...]
    unresolved: tuple[SourceUnresolved, ...]
    conflicts: tuple[SourceConflict, ...]
    evidence_total: Annotated[int, Field(strict=True, ge=0, le=75000)]


class DiagramSourceAdapter:
    def __init__(self, service: ArchitectureQueryService) -> None:
        self._service = service

    def version(
        self, version_id: UUID, project_id: UUID, budget: SourceBudget
    ) -> ArchitectureVersionResponse:
        """Public header through this adapter's owned cancellable read session."""
        budget.call()
        record = self._service.get_version(version_id, project_id)
        budget.check()
        return record

    def contains_entity(
        self, scope: CanonicalDiagramScope, identity: UUID, budget: SourceBudget
    ) -> bool:
        from backend.platform.errors import ArchitectureResultNotFoundError

        budget.call()
        try:
            value = self._service.get_entity(
                scope.architecture_version_id, identity, scope.project_id
            )
        except ArchitectureResultNotFoundError:
            return False
        budget.check()
        budget.bytes += len(canonical_bytes(value))
        budget.rows += 1
        if (
            budget.bytes > budget.limits.max_input_bytes
            or budget.rows > budget.limits.max_source_rows
        ):
            raise ValueError("diagram_limit_exceeded")
        return value.id == identity

    def header(
        self, scope: CanonicalDiagramScope, budget: SourceBudget
    ) -> CompletenessSnapshot:
        budget.call()
        version = self._service.get_version(
            scope.architecture_version_id, scope.project_id
        )
        budget.check()
        values = {
            k: getattr(version, k)
            for k in (
                "project_id",
                "repository_id",
                "analysis_id",
                "snapshot_id",
                "sequence_number",
                "architecture_schema_version",
                "ir_schema_version",
            )
        }
        values.update(
            architecture_version_id=version.id, canonical_digest=version.content_digest
        )
        if CanonicalDiagramScope.model_validate(values) != scope:
            raise ValueError("diagram_scope_mismatch")
        maxima = (25000, 50000, 75000, 10000, 5000)
        counts = (
            version.entity_count,
            version.relationship_count,
            version.evidence_count,
            version.unresolved_relationship_count,
            version.conflict_count,
        )
        if any(
            type(v) is not int or v < 0 or v > cap
            for v, cap in zip(counts, maxima, strict=True)
        ):
            raise ValueError("diagram_limit_exceeded")
        return CompletenessSnapshot.model_validate(version.completeness)

    def scan(
        self,
        collection: Collection,
        scope: CanonicalDiagramScope,
        budget: SourceBudget,
    ) -> Iterator[SourceRecord]:
        """Stream one collection; exhausting it verifies its final version header.

        Consumers closing early have not established scan completeness. Budget
        and page total checks never substitute for complete source traversal.
        """
        budget.begin_scan(scope.architecture_version_id, collection)
        self.header(scope, budget)
        methods: dict[Collection, Callable[..., ArchitectureCollectionResponse]] = {
            "entities": self._service.list_entities,
            "relationships": self._service.list_relationships,
            "evidence": self._service.list_evidence,
            "unresolved": self._service.list_unresolved,
            "conflicts": self._service.list_conflicts,
        }
        expected = {
            "entities": ArchitectureEntityResponse,
            "relationships": ArchitectureRelationshipResponse,
            "evidence": ArchitectureEvidenceResponse,
            "unresolved": ArchitectureUnresolvedResponse,
            "conflicts": ArchitectureConflictResponse,
        }
        caps = dict(
            entities=25000,
            relationships=50000,
            evidence=75000,
            unresolved=10000,
            conflicts=5000,
        )
        if collection not in methods:
            raise ValueError("diagram_input_invalid")
        offset, total = 0, None
        seen_ids: set[object] = set()
        seen_logical: set[str] = set()
        retained_identity_bytes = 0
        while True:
            budget.call()
            page: ArchitectureCollectionResponse = methods[collection](
                scope.architecture_version_id,
                scope.project_id,
                limit=budget.limits.source_page_size,
                offset=offset,
            )
            budget.check()
            if (
                type(page.total) is not int
                or not 0 <= page.total <= caps[collection]
                or page.offset != offset
                or page.limit != budget.limits.source_page_size
                or (total is not None and total != page.total)
                or len(page.items) != min(page.limit, page.total - offset)
            ):
                raise ValueError("diagram_integrity_error")
            total = page.total
            for item in page.items:
                if not isinstance(item, expected[collection]):
                    raise ValueError("diagram_integrity_error")
                budget.record(len(item.model_dump_json().encode("utf-8")))
                if item.id in seen_ids or item.logical_id in seen_logical:
                    raise ValueError("diagram_integrity_error")
                seen_ids.add(item.id)
                seen_logical.add(item.logical_id)
                retained_identity_bytes += 16 + len(item.logical_id.encode("utf-8"))
                if (
                    len(seen_ids) > budget.limits.max_retained_records
                    or retained_identity_bytes > budget.limits.max_retained_bytes
                ):
                    raise ValueError("diagram_limit_exceeded")
                yield _project(item)
            offset += len(page.items)
            if offset == total:
                break
        self.header(scope, budget)


def _project(item: object) -> SourceRecord:
    if isinstance(item, ArchitectureEntityResponse):
        return SourceEntity(
            record=EntityRef(
                record_type="entity", id=item.id, logical_id=item.logical_id
            ),
            kind=Kind(item.kind),
            name=item.name,
            namespace=item.namespace,
            status=Status(item.status),
            evidence_ids=item.evidence_ids,
        )
    if isinstance(item, ArchitectureRelationshipResponse):
        return SourceRelationship(
            record=RelationshipRef(
                record_type="relationship", id=item.id, logical_id=item.logical_id
            ),
            kind=Rel(item.kind),
            source_logical_id=item.source_logical_id,
            target_logical_id=item.target_logical_id,
            status=Status(item.status),
            evidence_ids=item.evidence_ids,
        )
    if isinstance(item, ArchitectureEvidenceResponse):
        return EvidenceProvenance(
            record=EvidenceRef(
                record_type="evidence", id=item.id, logical_id=item.logical_id
            ),
            source_record_type=item.source_record_type,
            producer_id=item.producer_id,
            producer_version=item.producer_version,
            artifact_id=item.artifact_id,
            source_fact_key=item.source_fact_key,
            path=item.path,
            source_range=item.source_range,
            strength=Strength(item.strength),
            polarity=Polarity(item.polarity),
        )
    if isinstance(item, ArchitectureUnresolvedResponse):
        return SourceUnresolved(
            record=Ref(
                record_type="unresolved", id=item.id, logical_id=item.logical_id
            ),
            kind=Rel(item.kind),
            source_logical_id=item.source_logical_id,
            target_descriptor=item.target_descriptor,
            reason=item.reason,
            status=Status(item.status),
            evidence_ids=item.evidence_ids,
            candidate_references=item.candidate_references,
        )
    if isinstance(item, ArchitectureConflictResponse):
        return SourceConflict(
            record=Ref(record_type="conflict", id=item.id, logical_id=item.logical_id),
            conflict_type=item.conflict_type,
            subject_key=item.subject_key,
            evidence_ids=item.evidence_ids,
        )
    raise ValueError("diagram_integrity_error")
