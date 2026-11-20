"""P5-C3 controlled source adapters for canonical, search, and graph data.

This module provides:
1. CanonicalReadAdapter over public ArchitectureQueryService.
2. SearchReadAdapter over public C1 SearchReadPort.
3. GraphReadAdapter over public P4 GraphGenerationReader and GraphQueryService.

Adheres to §7A.3, §7A.5, §7A.6, and §7A.11 of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError

from backend.platform.analysis.architecture.dto import (
    ArchitectureConflictResponse,
    ArchitectureEntityResponse,
    ArchitectureEvidenceResponse,
    ArchitectureRelationshipResponse,
    ArchitectureUnresolvedResponse,
    ArchitectureVersionResponse,
)
from backend.platform.analysis.architecture.service import ArchitectureQueryService
from backend.platform.errors import ArchitectureResultNotFoundError
from backend.platform.graph.query_contracts import (
    BoundedPathsRequest,
    ContainmentRequest,
    DependenciesRequest,
    DependentsRequest,
    GraphCursorExpiredError,
    GraphCursorInvalidError,
    GraphCursorScopeMismatchError,
    GraphGenerationChangedError,
    GraphNodeNotFoundError,
    GraphPathResult,
    GraphProjectionNotFoundError,
    GraphProjectionNotReadyError,
    GraphQueryError,
    GraphQueryIntegrityError,
    GraphQueryLimitExceededError,
    GraphQueryTimeoutError,
    GraphReadScope,
    GraphSchemaIncompatibleError,
    GraphSubgraph,
    GraphUnavailableError,
    NeighborhoodRequest,
)
from backend.platform.graph.query_repository import GraphGenerationReader
from backend.platform.graph.query_service import GraphQueryService
from backend.platform.knowledge.contracts import (
    SearchBackendUnavailableError,
    SearchCapabilityUnavailableError,
    SearchCapacityExceededError,
    SearchCursorExpiredError,
    SearchCursorInvalidError,
    SearchDeadlineExceededError,
    SearchError,
    SearchGenerationChangedError,
    SearchIntegrityError,
    SearchNotReadyError,
    SearchPage,
    SearchReadPort,
    SearchRequest,
)
from backend.platform.knowledge.projection import filter_safe_metadata
from backend.platform.knowledge.retrieval_contracts import (
    CanonicalFactView,
    CanonicalReadPort,
    ConflictView,
    EvidenceItemView,
    GraphReadPort,
    RelationshipView,
    RetrievalCapacityExceededError,
    RetrievalCursorExpiredError,
    RetrievalCursorInvalidError,
    RetrievalDeadlineExceededError,
    RetrievalError,
    RetrievalGenerationChangedError,
    RetrievalIntegrityFailedError,
    RetrievalInvalidRequestError,
    RetrievalNotFoundError,
    RetrievalScope,
    RetrievalUnavailableError,
    UnresolvedView,
)

T = TypeVar("T")


def canonical_failure(exc: Exception) -> RetrievalError:
    if isinstance(exc, DBAPIError) and getattr(exc.orig, "sqlstate", None) in {
        "57014",
        "55P03",
    }:
        return RetrievalDeadlineExceededError("Canonical database deadline exceeded")
    if isinstance(exc, ValidationError):
        return RetrievalIntegrityFailedError("Invalid canonical result")
    return RetrievalUnavailableError(
        "Canonical service unavailable", cause="canonical_unavailable"
    )


class CanonicalReadAdapter(CanonicalReadPort):
    """Adapter over ArchitectureQueryService implementing CanonicalReadPort."""

    def __init__(self, query_service: ArchitectureQueryService) -> None:
        self._query_service = query_service

    def get_version(self, version_id: UUID, project_id: UUID) -> RetrievalScope:
        try:
            resp: ArchitectureVersionResponse = self._query_service.get_version(
                version_id, project_id
            )
        except ArchitectureResultNotFoundError as exc:
            raise RetrievalNotFoundError(
                f"Architecture version {version_id} not found in project {project_id}",
                cause="canonical_read_failed",
            ) from exc
        except RetrievalError:
            raise
        except Exception as exc:
            raise canonical_failure(exc) from None

        return RetrievalScope(
            project_id=resp.project_id,
            repository_id=resp.repository_id,
            analysis_id=resp.analysis_id,
            snapshot_id=resp.snapshot_id,
            architecture_version_id=resp.id,
            sequence_number=resp.sequence_number,
            canonical_digest=resp.content_digest,
            architecture_schema_version=resp.architecture_schema_version,
            ir_schema_version=resp.ir_schema_version,
            published_at=resp.published_at,
            completeness=resp.completeness,
        )

    def get_entity(
        self, version_id: UUID, entity_id: UUID, project_id: UUID
    ) -> CanonicalFactView | None:
        try:
            resp: ArchitectureEntityResponse = self._query_service.get_entity(
                version_id, entity_id, project_id
            )
            return self._map_entity(resp)
        except ArchitectureResultNotFoundError:
            return None
        except RetrievalError:
            raise
        except Exception as exc:
            raise canonical_failure(exc) from None

    def list_entities(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        kind: str | None = None,
        status: str | None = None,
    ) -> tuple[tuple[CanonicalFactView, ...], int]:
        try:
            col = self._query_service.list_entities(
                version_id,
                project_id,
                limit=limit,
                offset=offset,
                kind=kind,
                status=status,
            )
            if any(
                not isinstance(item, ArchitectureEntityResponse) for item in col.items
            ):
                raise RetrievalIntegrityFailedError("Unexpected canonical record type")
            facts = tuple(
                self._map_entity(cast(ArchitectureEntityResponse, item))
                for item in col.items
            )
            return facts, col.total
        except ArchitectureResultNotFoundError as exc:
            raise RetrievalNotFoundError(
                f"Architecture version {version_id} not found",
                cause="canonical_read_failed",
            ) from exc
        except RetrievalError:
            raise
        except Exception as exc:
            raise canonical_failure(exc) from None

    def list_relationships(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        kind: str | None = None,
        status: str | None = None,
    ) -> tuple[tuple[RelationshipView, ...], int]:
        try:
            col = self._query_service.list_relationships(
                version_id,
                project_id,
                limit=limit,
                offset=offset,
                kind=kind,
                status=status,
            )
            if any(
                not isinstance(item, ArchitectureRelationshipResponse)
                for item in col.items
            ):
                raise RetrievalIntegrityFailedError("Unexpected canonical record type")
            rels = tuple(
                self._map_relationship(cast(ArchitectureRelationshipResponse, item))
                for item in col.items
            )
            return rels, col.total
        except ArchitectureResultNotFoundError as exc:
            raise RetrievalNotFoundError(
                f"Architecture version {version_id} not found",
                cause="canonical_read_failed",
            ) from exc
        except RetrievalError:
            raise
        except Exception as exc:
            raise canonical_failure(exc) from None

    def list_evidence(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        entity_id: UUID | None = None,
    ) -> tuple[tuple[EvidenceItemView, ...], int]:
        try:
            col = self._query_service.list_evidence(
                version_id,
                project_id,
                limit=limit,
                offset=offset,
                entity_id=entity_id,
            )
            if any(
                not isinstance(item, ArchitectureEvidenceResponse) for item in col.items
            ):
                raise RetrievalIntegrityFailedError("Unexpected canonical record type")
            items = tuple(
                self._map_evidence(cast(ArchitectureEvidenceResponse, item))
                for item in col.items
            )
            return items, col.total
        except ArchitectureResultNotFoundError as exc:
            raise RetrievalNotFoundError(
                f"Architecture version {version_id} not found",
                cause="canonical_read_failed",
            ) from exc
        except RetrievalError:
            raise
        except Exception as exc:
            raise canonical_failure(exc) from None

    def list_unresolved(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[tuple[UnresolvedView, ...], int]:
        try:
            col = self._query_service.list_unresolved(
                version_id, project_id, limit=limit, offset=offset
            )
            if any(
                not isinstance(item, ArchitectureUnresolvedResponse)
                for item in col.items
            ):
                raise RetrievalIntegrityFailedError("Unexpected canonical record type")
            items = tuple(
                self._map_unresolved(cast(ArchitectureUnresolvedResponse, item))
                for item in col.items
            )
            return items, col.total
        except ArchitectureResultNotFoundError as exc:
            raise RetrievalNotFoundError(
                f"Architecture version {version_id} not found",
                cause="canonical_read_failed",
            ) from exc
        except RetrievalError:
            raise
        except Exception as exc:
            raise canonical_failure(exc) from None

    def list_conflicts(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[tuple[ConflictView, ...], int]:
        try:
            col = self._query_service.list_conflicts(
                version_id, project_id, limit=limit, offset=offset
            )
            if any(
                not isinstance(item, ArchitectureConflictResponse) for item in col.items
            ):
                raise RetrievalIntegrityFailedError("Unexpected canonical record type")
            items = tuple(
                self._map_conflict(cast(ArchitectureConflictResponse, item))
                for item in col.items
            )
            return items, col.total
        except ArchitectureResultNotFoundError as exc:
            raise RetrievalNotFoundError(
                f"Architecture version {version_id} not found",
                cause="canonical_read_failed",
            ) from exc
        except RetrievalError:
            raise
        except Exception as exc:
            raise canonical_failure(exc) from None

    def _map_entity(self, item: ArchitectureEntityResponse) -> CanonicalFactView:
        return CanonicalFactView(
            record_id=item.id,
            logical_id=item.logical_id,
            kind=item.kind,
            name=item.name,
            namespace=tuple(item.namespace) if item.namespace else None,
            status=item.status,
            metadata=filter_safe_metadata(dict(item.metadata))[0],
            evidence_count=len(item.evidence_ids),
            evidence_references=tuple(item.evidence_ids),
        )

    def _map_relationship(
        self, item: ArchitectureRelationshipResponse
    ) -> RelationshipView:
        return RelationshipView(
            record_id=item.id,
            logical_id=item.logical_id,
            kind=item.kind,
            status=item.status,
            source_logical_id=item.source_logical_id,
            target_logical_id=item.target_logical_id,
            evidence_references=tuple(item.evidence_ids),
        )

    def _map_evidence(self, item: ArchitectureEvidenceResponse) -> EvidenceItemView:
        return EvidenceItemView(
            record_id=item.id,
            logical_id=item.logical_id,
            source_record_type=item.source_record_type,
            path=item.path,
            artifact_id=item.artifact_id,
            range_data=dict(item.source_range) if item.source_range else None,
            polarity=item.polarity,
            strength=item.strength,
            producer_id=item.producer_id,
            producer_version=item.producer_version,
            source_fact_key=item.source_fact_key,
            subject_references=(),
        )

    def _map_unresolved(self, item: ArchitectureUnresolvedResponse) -> UnresolvedView:
        return UnresolvedView(
            record_id=item.id,
            logical_id=item.logical_id,
            reason=item.reason,
            unresolved_type=item.kind,
            source_logical_id=item.source_logical_id,
            target_descriptor=item.target_descriptor,
            status=item.status,
            evidence_references=item.evidence_ids,
            candidate_references=item.candidate_references,
            details=filter_safe_metadata(dict(item.metadata))[0],
        )

    def _map_conflict(self, item: ArchitectureConflictResponse) -> ConflictView:
        return ConflictView(
            record_id=item.id,
            logical_id=item.logical_id,
            conflict_type=item.conflict_type,
            subject_key=item.subject_key,
            details=filter_safe_metadata(dict(item.details))[0],
            evidence_references=tuple(item.evidence_ids),
        )


class SearchReadAdapter:
    """Adapter over C1 SearchReadPort with generation/index binding (§7A.6)."""

    def __init__(
        self,
        search_port: SearchReadPort,
        *,
        bound_generation_id: UUID | None = None,
        bound_index_uuid: str | None = None,
    ) -> None:
        self._search_port = search_port
        self._generation_id = bound_generation_id
        self._index_uuid = bound_index_uuid
        self._scope: Any = None

    @property
    def bound_generation_id(self) -> UUID | None:
        return self._generation_id

    @property
    def bound_index_uuid(self) -> str | None:
        return self._index_uuid

    def search(self, request: SearchRequest, *, actor_id: UUID) -> SearchPage:
        try:
            page = self._search_port.search(request, actor_id=actor_id)
        except SearchCursorExpiredError as exc:
            raise RetrievalCursorExpiredError(
                message=exc.message, safe_details=exc.safe_details, cause=exc.code
            ) from exc
        except SearchCursorInvalidError as exc:
            raise RetrievalCursorInvalidError(
                message=exc.message, safe_details=exc.safe_details, cause=exc.code
            ) from exc
        except SearchGenerationChangedError as exc:
            raise RetrievalGenerationChangedError(
                message=exc.message, safe_details=exc.safe_details, cause=exc.code
            ) from exc
        except SearchCapacityExceededError as exc:
            raise RetrievalCapacityExceededError(
                message=exc.message, safe_details=exc.safe_details, cause=exc.code
            ) from exc
        except SearchDeadlineExceededError as exc:
            raise RetrievalDeadlineExceededError(
                message=exc.message, safe_details=exc.safe_details, cause=exc.code
            ) from exc
        except (
            SearchNotReadyError,
            SearchBackendUnavailableError,
            SearchCapabilityUnavailableError,
        ) as exc:
            raise RetrievalUnavailableError(
                message=exc.message, safe_details=exc.safe_details, cause=exc.code
            ) from exc
        except SearchIntegrityError as exc:
            raise RetrievalIntegrityFailedError(
                message=exc.message, safe_details=exc.safe_details, cause=exc.code
            ) from exc
        except SearchError as exc:
            raise RetrievalError(
                message=exc.message,
                code="retrieval_search_error",
                safe_details=exc.safe_details,
                cause=exc.code,
            ) from exc

        page = SearchPage.model_validate(page)
        if (
            page.scope.project_id != request.project_id
            or page.scope.architecture_version_id != request.architecture_version_id
        ):
            raise RetrievalIntegrityFailedError("Search response scope mismatch")
        if self._scope is not None and page.scope != self._scope:
            raise RetrievalIntegrityFailedError("Search immutable scope changed")
        self._scope = page.scope
        # Bind or verify generation and index UUID consistency
        if self._generation_id is None:
            self._generation_id = page.generation_id
            self._index_uuid = page.index_uuid
        else:
            if (
                page.generation_id != self._generation_id
                or page.index_uuid != self._index_uuid
            ):
                raise RetrievalGenerationChangedError(
                    f"Search generation changed during retrieval: "
                    f"expected {self._generation_id}, got {page.generation_id}"
                )

        return page

    def final_probe(
        self,
        request: SearchRequest,
        *,
        actor_id: UUID,
        remaining_budget: float,
    ) -> None:
        """Execute one public C1 search probe to verify the active search generation.

        Adheres to §7A.6.
        """
        probe_req = SearchRequest(
            project_id=request.project_id,
            architecture_version_id=request.architecture_version_id,
            q=request.q,
            document_kinds=request.document_kinds,
            mode=request.mode,
            entity_kinds=request.entity_kinds,
            statuses=request.statuses,
            limit=request.limit,
            timeout_seconds=min(remaining_budget, request.timeout_seconds),
            cursor=None,
        )
        page = self.search(probe_req, actor_id=actor_id)
        if (
            self._generation_id is not None
            and page.generation_id != self._generation_id
        ) or (self._index_uuid is not None and page.index_uuid != self._index_uuid):
            raise RetrievalGenerationChangedError(
                "Search generation changed during final check validation"
            )


class GraphReadAdapter(GraphReadPort):
    """Adapter over P4 GraphGenerationReader and GraphQueryService (§7A.3, §7A.6)."""

    def __init__(
        self,
        generation_reader: GraphGenerationReader,
        query_service: GraphQueryService,
        *,
        bound_generation_id: UUID | None = None,
    ) -> None:
        self._generation_reader = generation_reader
        self._query_service = query_service
        self._generation_id = bound_generation_id

    @property
    def bound_generation_id(self) -> UUID | None:
        return self._generation_id

    def resolve_active_generation(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        *,
        timeout_seconds: float,
    ) -> GraphReadScope:
        try:
            scope = self._generation_reader.resolve_active_generation(
                project_id, architecture_version_id, timeout_seconds=timeout_seconds
            )
            if self._generation_id is None:
                self._generation_id = scope.generation_id
            elif self._generation_id != scope.generation_id:
                raise RetrievalGenerationChangedError(
                    f"Graph generation changed: expected {self._generation_id}, "
                    f"got {scope.generation_id}"
                )
            return scope
        except (GraphProjectionNotFoundError, GraphProjectionNotReadyError) as exc:
            raise RetrievalUnavailableError(
                "Graph projection not ready or not found", cause="canonical_read_failed"
            ) from exc
        except GraphGenerationChangedError as exc:
            raise RetrievalGenerationChangedError(
                "Graph generation changed during resolution", cause=exc.code
            ) from exc
        except GraphQueryTimeoutError as exc:
            raise RetrievalDeadlineExceededError(
                "Graph generation resolution timed out", cause=exc.code
            ) from exc
        except (GraphQueryIntegrityError, GraphSchemaIncompatibleError) as exc:
            raise RetrievalIntegrityFailedError(
                "Graph generation integrity error", cause=exc.code
            ) from exc
        except GraphUnavailableError as exc:
            raise RetrievalUnavailableError(
                "Graph service unavailable", cause=exc.code
            ) from exc

    def verify_generation_still_active(
        self,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        *,
        timeout_seconds: float,
    ) -> bool:
        return self._execute_graph(
            lambda: self._generation_reader.verify_generation_still_active(
                project_id,
                architecture_version_id,
                generation_id,
                timeout_seconds=timeout_seconds,
            )
        )

    def get_neighborhood(self, request: NeighborhoodRequest) -> GraphSubgraph:
        return self._execute_graph(
            lambda: self._query_service.get_neighborhood(request)
        )

    def get_dependencies(self, request: DependenciesRequest) -> GraphSubgraph:
        return self._execute_graph(
            lambda: self._query_service.get_dependencies(request)
        )

    def get_dependents(self, request: DependentsRequest) -> GraphSubgraph:
        return self._execute_graph(lambda: self._query_service.get_dependents(request))

    def get_containment(self, request: ContainmentRequest) -> GraphSubgraph:
        return self._execute_graph(lambda: self._query_service.get_containment(request))

    def get_bounded_paths(self, request: BoundedPathsRequest) -> GraphPathResult:
        return self._execute_graph(
            lambda: self._query_service.get_bounded_paths(request)
        )

    def _execute_graph(self, fn: Callable[[], T]) -> T:
        try:
            res: T = fn()
            if hasattr(res, "scope") and hasattr(res.scope, "generation_id"):
                gen_id = res.scope.generation_id
                if self._generation_id is None:
                    self._generation_id = gen_id
                elif self._generation_id != gen_id:
                    raise RetrievalGenerationChangedError(
                        f"Graph generation changed during query: "
                        f"expected {self._generation_id}, got {gen_id}"
                    )
            return res
        except (GraphCursorInvalidError, GraphCursorScopeMismatchError) as exc:
            raise RetrievalCursorInvalidError(cause=exc.code) from None
        except GraphCursorExpiredError as exc:
            raise RetrievalCursorExpiredError(cause=exc.code) from None
        except GraphQueryLimitExceededError as exc:
            raise RetrievalInvalidRequestError(cause=exc.code) from None
        except GraphNodeNotFoundError as exc:
            raise RetrievalNotFoundError(
                message=exc.message, safe_details=exc.safe_details, cause=exc.code
            ) from exc
        except GraphGenerationChangedError as exc:
            raise RetrievalGenerationChangedError(
                message=exc.message, safe_details=exc.safe_details, cause=exc.code
            ) from exc
        except GraphQueryTimeoutError as exc:
            raise RetrievalDeadlineExceededError(
                message=exc.message, safe_details=exc.safe_details, cause=exc.code
            ) from exc
        except (
            GraphProjectionNotFoundError,
            GraphProjectionNotReadyError,
            GraphUnavailableError,
        ) as exc:
            raise RetrievalUnavailableError(
                message=exc.message, safe_details=exc.safe_details, cause=exc.code
            ) from exc
        except (GraphQueryIntegrityError, GraphSchemaIncompatibleError) as exc:
            raise RetrievalIntegrityFailedError(
                message=exc.message, safe_details=exc.safe_details, cause=exc.code
            ) from exc
        except GraphQueryError as exc:
            raise RetrievalError(
                message=exc.message,
                code="retrieval_graph_error",
                safe_details=exc.safe_details,
                cause=exc.code,
            ) from exc


__all__ = [
    "CanonicalReadAdapter",
    "GraphReadAdapter",
    "SearchReadAdapter",
]
