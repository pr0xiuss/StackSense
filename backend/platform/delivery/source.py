"""Read-only P5 adapter over exported P4 source and public analysis DTOs.

No repository/private table imports, latest-version substitution, upstream
recomputation, cache of documents, or mutation of analysis/graph lifecycle.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, cast
from uuid import UUID

from backend.platform.analysis.application.dto import AnalysisResponse
from backend.platform.analysis.architecture.dto import ArchitectureVersionResponse
from backend.platform.analysis.architecture.model import ArchitectureDocument
from backend.platform.analysis.domain.constants import AnalysisStatus
from backend.platform.delivery.contracts import DeliveryContractError, VersionScope
from backend.platform.delivery.model import Eligibility
from backend.platform.graph.model import SOURCE_CONTRACT_VERSION, ProjectionCounts
from backend.platform.graph.source import (
    PublishedArchitectureCursor,
    PublishedArchitectureHeader,
    PublishedArchitecturePage,
    PublishedArchitectureSource,
)


@dataclass(frozen=True, slots=True)
class EligibilityInspection:
    scope: VersionScope
    eligibility: Eligibility


class PublishedVersionReader:
    def __init__(
        self,
        source: PublishedArchitectureSource,
        read_analysis: Callable[[UUID, UUID], AnalysisResponse],
    ) -> None:
        self._source = source
        self._read_analysis = read_analysis

    @staticmethod
    def scope(header: PublishedArchitectureHeader) -> VersionScope:
        if header.contract_version != SOURCE_CONTRACT_VERSION:
            raise DeliveryContractError("unsupported published source contract")
        return VersionScope(
            project_id=header.project_id,
            repository_id=header.repository_id,
            analysis_id=header.analysis_id,
            snapshot_id=header.snapshot_id,
            architecture_version_id=header.architecture_version_id,
            sequence_number=header.sequence_number,
            published_at=header.published_at,
            canonical_digest=header.content_digest,
            source_contract_version=cast(Literal["1.0.0"], header.contract_version),
            analyzer_version=header.analyzer_version,
            ir_schema_version=header.ir_schema_version,
            architecture_schema_version=header.architecture_schema_version,
            configuration_fingerprint=header.configuration_fingerprint,
        )

    def list_published(
        self, *, limit: int, cursor: PublishedArchitectureCursor | None = None
    ) -> PublishedArchitecturePage:
        page = self.list_for_discovery(limit=limit, cursor=cursor)
        for header in page.items:
            self.scope(header)
        return page

    def list_for_discovery(
        self, *, limit: int, cursor: PublishedArchitectureCursor | None = None
    ) -> PublishedArchitecturePage:
        """Ordered identity-safe page; coordinator durably quarantines bad metadata.

        Unlike the strict public list, this does not declare every header valid.
        Unsafe identity/order cannot be advanced past and fails closed.
        """
        if type(limit) is not int or not 1 <= limit <= 500:
            raise DeliveryContractError("source page limit must be 1..500")
        page = self._source.list_published(limit=limit, after=cursor)
        if len(page.items) > limit or (page.next_cursor is not None and not page.items):
            raise DeliveryContractError("invalid published source page")
        previous = self._cursor_key(cursor) if cursor else None
        for header in page.items:
            if (
                not all(
                    isinstance(value, UUID)
                    for value in (
                        header.project_id,
                        header.repository_id,
                        header.analysis_id,
                        header.snapshot_id,
                        header.architecture_version_id,
                    )
                )
                or type(header.sequence_number) is not int
                or header.sequence_number <= 0
            ):
                raise DeliveryContractError("unsafe published source cursor identity")
            key = (
                header.project_id,
                header.repository_id,
                header.sequence_number,
                header.architecture_version_id,
            )
            if previous is not None and key <= previous:
                raise DeliveryContractError("published source order/cursor mismatch")
            previous = key
        if (
            page.next_cursor is not None
            and self._cursor_key(page.next_cursor) != previous
        ):
            raise DeliveryContractError("published source continuation mismatch")
        # None is end-of-pass, not a permanent high-water mark. B2 persists a
        # fenced checkpoint and starts the next bounded sweep at None.
        return page

    @staticmethod
    def _cursor_key(
        cursor: PublishedArchitectureCursor,
    ) -> tuple[UUID, UUID, int, UUID]:
        return (
            cursor.project_id,
            cursor.repository_id,
            cursor.sequence_number,
            cursor.architecture_version_id,
        )

    def inspect_eligibility(
        self, header: PublishedArchitectureHeader
    ) -> EligibilityInspection:
        scope = self.scope(header)
        analysis = self._read_analysis(scope.analysis_id, scope.project_id)
        if (
            analysis.id,
            analysis.project_id,
            analysis.repository_id,
            analysis.snapshot_id,
        ) != (
            scope.analysis_id,
            scope.project_id,
            scope.repository_id,
            scope.snapshot_id,
        ):
            raise DeliveryContractError("published source analysis scope mismatch")
        try:
            status = AnalysisStatus(analysis.status)
        except ValueError as exc:
            raise DeliveryContractError("unsupported analysis status") from exc
        if status in {AnalysisStatus.COMPLETED, AnalysisStatus.COMPLETED_WITH_WARNINGS}:
            # Validate one exact immutable document outside publication locks.
            self.load_exact(header)
            eligibility = Eligibility.ELIGIBLE
        elif status in {AnalysisStatus.FAILED, AnalysisStatus.CANCELLED}:
            eligibility = Eligibility.INELIGIBLE
        else:
            eligibility = Eligibility.WAITING
        return EligibilityInspection(scope, eligibility)

    def load_exact(self, header: PublishedArchitectureHeader) -> ArchitectureDocument:
        scope = self.scope(header)
        document = self._source.load_exact(
            scope.architecture_version_id, scope.project_id
        )
        if document is None:
            raise DeliveryContractError("exact published document unavailable")
        if (
            document.architecture_version_id != scope.architecture_version_id
            or document.project_id != scope.project_id
            or document.repository_id != scope.repository_id
            or document.analysis_id != scope.analysis_id
            or document.snapshot_id != scope.snapshot_id
            or document.configuration_fingerprint != scope.configuration_fingerprint
            or document.analyzer_version != scope.analyzer_version
            or document.ir_schema_version != scope.ir_schema_version
            or document.architecture_schema_version != scope.architecture_schema_version
            or document.content_digest != scope.canonical_digest
            or (
                len(document.entities),
                len(document.relationships),
                len(document.evidence),
                len(document.unresolved_relationships),
                len(document.conflicts),
            )
            != (
                header.counts.entities,
                header.counts.relationships,
                header.counts.evidence,
                header.counts.unresolved,
                header.counts.conflicts,
            )
        ):
            raise DeliveryContractError(
                "exact published document identity/digest/count mismatch"
            )
        return document

    def inspect_requested(
        self, record: ArchitectureVersionResponse
    ) -> EligibilityInspection:
        """Compose only exported exact-version read contracts, never a latest alias."""
        document = self._source.load_exact(record.id, record.project_id)
        if document is None:
            raise DeliveryContractError("exact published document unavailable")
        header = PublishedArchitectureHeader(
            contract_version=SOURCE_CONTRACT_VERSION,
            architecture_version_id=record.id,
            analysis_id=record.analysis_id,
            project_id=record.project_id,
            repository_id=record.repository_id,
            snapshot_id=record.snapshot_id,
            sequence_number=record.sequence_number,
            published_at=record.published_at,
            configuration_fingerprint=document.configuration_fingerprint,
            analyzer_version=document.analyzer_version,
            ir_schema_version=record.ir_schema_version,
            architecture_schema_version=record.architecture_schema_version,
            content_digest=record.content_digest,
            counts=ProjectionCounts(
                entities=record.entity_count,
                relationships=record.relationship_count,
                evidence=record.evidence_count,
                unresolved=record.unresolved_relationship_count,
                conflicts=record.conflict_count,
            ),
        )
        return self.inspect_eligibility(header)
