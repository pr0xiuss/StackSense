"""Unit tests for P5-C3 controlled source adapters.

Adheres to §7A.3, §7A.5, §7A.6, and §7A.11 of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from backend.platform.analysis.architecture.dto import (
    ArchitectureCollectionResponse,
    ArchitectureConflictResponse,
    ArchitectureEntityResponse,
    ArchitectureEvidenceResponse,
    ArchitectureRelationshipResponse,
    ArchitectureUnresolvedResponse,
    ArchitectureVersionResponse,
)
from backend.platform.errors import ArchitectureResultNotFoundError
from backend.platform.graph.model import ProjectionCounts
from backend.platform.graph.query_contracts import (
    GraphQueryTimeoutError,
    GraphReadScope,
    GraphSubgraph,
)
from backend.platform.knowledge.contracts import (
    SearchBackendUnavailableError,
    SearchCapabilities,
    SearchCursorExpiredError,
    SearchIntegrityError,
    SearchPage,
    SearchRequest,
)
from backend.platform.knowledge.retrieval_adapters import (
    CanonicalReadAdapter,
    GraphReadAdapter,
    SearchReadAdapter,
)
from backend.platform.knowledge.retrieval_contracts import (
    RetrievalCursorExpiredError,
    RetrievalDeadlineExceededError,
    RetrievalGenerationChangedError,
    RetrievalIntegrityFailedError,
    RetrievalNotFoundError,
    RetrievalUnavailableError,
)
from tests.p5.knowledge.conftest import make_test_scope


class FakeArchitectureQueryService:
    def __init__(self, version_id: UUID, project_id: UUID) -> None:
        self.version_id = version_id
        self.project_id = project_id
        self.entities: list[ArchitectureEntityResponse] = []
        self.relationships: list[ArchitectureRelationshipResponse] = []
        self.evidence: list[ArchitectureEvidenceResponse] = []
        self.unresolved: list[ArchitectureUnresolvedResponse] = []
        self.conflicts: list[ArchitectureConflictResponse] = []

    def get_version(
        self, version_id: UUID, project_id: UUID
    ) -> ArchitectureVersionResponse:
        if version_id != self.version_id or project_id != self.project_id:
            raise ArchitectureResultNotFoundError()
        return ArchitectureVersionResponse(
            id=version_id,
            analysis_id=uuid4(),
            project_id=project_id,
            repository_id=uuid4(),
            snapshot_id=uuid4(),
            sequence_number=1,
            architecture_schema_version="1.0.0",
            ir_schema_version="1.0.0",
            content_digest="b" * 64,
            entity_count=len(self.entities),
            relationship_count=len(self.relationships),
            evidence_count=len(self.evidence),
            unresolved_relationship_count=len(self.unresolved),
            conflict_count=len(self.conflicts),
            completeness={},
            published_at=datetime.now(UTC),
        )

    def get_entity(
        self, version_id: UUID, entity_id: UUID, project_id: UUID
    ) -> ArchitectureEntityResponse:
        for e in self.entities:
            if e.id == entity_id:
                return e
        raise ArchitectureResultNotFoundError()

    def list_entities(
        self, version_id: UUID, project_id: UUID, **kwargs
    ) -> ArchitectureCollectionResponse:
        return ArchitectureCollectionResponse(
            items=self.entities, total=len(self.entities), limit=100, offset=0
        )

    def list_relationships(
        self, version_id: UUID, project_id: UUID, **kwargs
    ) -> ArchitectureCollectionResponse:
        return ArchitectureCollectionResponse(
            items=self.relationships, total=len(self.relationships), limit=100, offset=0
        )

    def list_evidence(
        self, version_id: UUID, project_id: UUID, **kwargs
    ) -> ArchitectureCollectionResponse:
        return ArchitectureCollectionResponse(
            items=self.evidence, total=len(self.evidence), limit=100, offset=0
        )

    def list_unresolved(
        self, version_id: UUID, project_id: UUID, **kwargs
    ) -> ArchitectureCollectionResponse:
        return ArchitectureCollectionResponse(
            items=self.unresolved, total=len(self.unresolved), limit=100, offset=0
        )

    def list_conflicts(
        self, version_id: UUID, project_id: UUID, **kwargs
    ) -> ArchitectureCollectionResponse:
        return ArchitectureCollectionResponse(
            items=self.conflicts, total=len(self.conflicts), limit=100, offset=0
        )


def test_canonical_read_adapter_happy_path_and_mapping():
    v_id, p_id = uuid4(), uuid4()
    svc = FakeArchitectureQueryService(v_id, p_id)
    ent_id = uuid4()
    svc.entities.append(
        ArchitectureEntityResponse(
            id=ent_id,
            logical_id="entity://auth",
            kind="service",
            name="AuthService",
            namespace=("core", "auth"),
            status="CONFIRMED",
            evidence_ids=("ev-1",),
            source_ir_keys=(),
            metadata={"framework": "fastapi"},
        )
    )

    adapter = CanonicalReadAdapter(svc)  # type: ignore[arg-type]
    scope = adapter.get_version(v_id, p_id)
    assert scope.architecture_version_id == v_id
    assert scope.canonical_digest == "b" * 64

    # Get entity
    fact = adapter.get_entity(v_id, ent_id, p_id)
    assert fact is not None
    assert fact.record_id == ent_id
    assert fact.logical_id == "entity://auth"
    assert fact.name == "AuthService"
    assert fact.metadata["framework"] == "fastapi"

    # Not found returns None
    assert adapter.get_entity(v_id, uuid4(), p_id) is None


def test_canonical_read_adapter_version_not_found_raises_retrieval_not_found():
    svc = FakeArchitectureQueryService(uuid4(), uuid4())
    adapter = CanonicalReadAdapter(svc)  # type: ignore[arg-type]
    with pytest.raises(RetrievalNotFoundError):
        adapter.get_version(uuid4(), uuid4())


def test_search_read_adapter_enforces_generation_and_index_binding():
    gen_id = uuid4()
    idx_uuid = "idx-v1-uuid"
    scope = make_test_scope()

    class FakeSearchPort:
        def __init__(self):
            self.current_gen = gen_id
            self.current_idx = idx_uuid

        def search(self, request, *, actor_id):
            return SearchPage(
                scope=scope,
                generation_id=self.current_gen,
                index_uuid=self.current_idx,
                items=(),
                total_hits=0,
                has_more=False,
                capabilities=SearchCapabilities(),
            )

    port = FakeSearchPort()
    adapter = SearchReadAdapter(port)
    req = SearchRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        q="test",
    )

    # First read binds generation & index UUID
    _ = adapter.search(req, actor_id=uuid4())
    assert adapter.bound_generation_id == gen_id
    assert adapter.bound_index_uuid == idx_uuid

    # Second read with same generation passes
    adapter.search(req, actor_id=uuid4())

    # Third read when generation drifts raises RetrievalGenerationChangedError (409)
    port.current_gen = uuid4()
    with pytest.raises(RetrievalGenerationChangedError):
        adapter.search(req, actor_id=uuid4())


def test_search_read_adapter_translates_typed_exceptions():
    scope = make_test_scope()

    class ErrorSearchPort:
        def __init__(self, exc):
            self.exc = exc

        def search(self, request, *, actor_id):
            raise self.exc

    req = SearchRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        q="test",
    )

    # 410 cursor expired
    adapter1 = SearchReadAdapter(ErrorSearchPort(SearchCursorExpiredError()))
    with pytest.raises(RetrievalCursorExpiredError):
        adapter1.search(req, actor_id=uuid4())

    # 503 backend unavailable
    adapter2 = SearchReadAdapter(
        ErrorSearchPort(SearchBackendUnavailableError("ES down"))
    )
    with pytest.raises(RetrievalUnavailableError):
        adapter2.search(req, actor_id=uuid4())

    # 500 integrity error
    adapter3 = SearchReadAdapter(ErrorSearchPort(SearchIntegrityError("Corrupt hits")))
    with pytest.raises(RetrievalIntegrityFailedError):
        adapter3.search(req, actor_id=uuid4())


def test_graph_read_adapter_translates_typed_exceptions_and_binds_generation():
    gen_id = uuid4()
    p_id, v_id = uuid4(), uuid4()

    class FakeGraphGenerationReader:
        def __init__(self):
            self.active = True

        def resolve_active_generation(
            self, project_id, architecture_version_id, *, timeout_seconds=None
        ):
            return GraphReadScope(
                project_id=project_id,
                architecture_version_id=architecture_version_id,
                generation_id=gen_id,
                resource_state="COMPLETED",
                graph_schema_version="1.0.0",
                projector_version="1.0.0",
                counts=ProjectionCounts(
                    entities=10,
                    relationships=20,
                    evidence=30,
                    unresolved=0,
                    conflicts=0,
                ),
            )

        def verify_generation_still_active(
            self,
            project_id,
            architecture_version_id,
            generation_id,
            *,
            timeout_seconds=None,
        ):
            return self.active and generation_id == gen_id

    class FakeGraphQueryService:
        def get_dependencies(self, req):
            if req.depth > 3:
                raise GraphQueryTimeoutError("Depth traversal timeout")
            return GraphSubgraph(
                scope=GraphReadScope(
                    project_id=p_id,
                    architecture_version_id=v_id,
                    generation_id=gen_id,
                    resource_state="COMPLETED",
                    graph_schema_version="1.0.0",
                    projector_version="1.0.0",
                    counts=ProjectionCounts(
                        entities=1,
                        relationships=0,
                        evidence=0,
                        unresolved=0,
                        conflicts=0,
                    ),
                ),
                nodes=(),
                edges=(),
                total_manifest_nodes=1,
                total_manifest_edges=0,
                loaded_nodes=0,
                loaded_edges=0,
                truncated=False,
            )

    reader = FakeGraphGenerationReader()
    query_svc = FakeGraphQueryService()
    adapter = GraphReadAdapter(reader, query_svc)  # type: ignore[arg-type]

    # Resolve active generation
    scope = adapter.resolve_active_generation(p_id, v_id, timeout_seconds=2.0)
    assert scope.generation_id == gen_id
    assert adapter.bound_generation_id == gen_id

    # Verify active
    assert (
        adapter.verify_generation_still_active(p_id, v_id, gen_id, timeout_seconds=2.0)
        is True
    )
    reader.active = False
    assert (
        adapter.verify_generation_still_active(p_id, v_id, gen_id, timeout_seconds=2.0)
        is False
    )

    # Timeout translation to RetrievalDeadlineExceededError
    with pytest.raises(RetrievalDeadlineExceededError):
        adapter.get_dependencies(SimpleNamespace(depth=5))  # type: ignore[arg-type]
