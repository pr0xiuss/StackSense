"""Public-page boundary tests; doubles are not PostgreSQL cancellation proof."""

from datetime import UTC, datetime
from time import monotonic
from unittest.mock import Mock
from uuid import UUID

import pytest

from backend.platform.analysis.architecture.dto import (
    ArchitectureCollectionResponse,
    ArchitectureEntityResponse,
    ArchitectureVersionResponse,
)
from backend.platform.analysis.architecture.service import ArchitectureQueryService
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.query import (
    DiagramSourceAdapter,
    SourceBudget,
    SourceEntity,
)
from tests.p5.diagrams.conftest import completeness, scope


def source():
    service = Mock(spec=ArchitectureQueryService)
    s = scope()
    service.get_version.return_value = ArchitectureVersionResponse(
        **s.model_dump(exclude={"architecture_version_id", "canonical_digest"}),
        id=s.architecture_version_id,
        content_digest=s.canonical_digest,
        entity_count=1,
        relationship_count=0,
        evidence_count=0,
        unresolved_relationship_count=0,
        conflict_count=0,
        completeness=completeness().model_dump(),
        published_at=datetime.now(UTC),
    )
    item = ArchitectureEntityResponse(
        id=UUID(int=6),
        logical_id="entity:service",
        kind="service",
        name="Python Service",
        namespace=("backend",),
        status="supported",
        evidence_ids=(),
        source_ir_keys=(),
        metadata={"not_for_diagram": ["mutable"]},
    )
    service.list_entities.return_value = ArchitectureCollectionResponse(
        items=[item],
        total=1,
        limit=200,
        offset=0,
    )
    budget = SourceBudget(DiagramLimits(), monotonic() + 10, lambda: None)
    return service, DiagramSourceAdapter(service), budget


def test_public_paging_preserves_real_ids_and_excludes_metadata():
    service, adapter, budget = source()
    rows = list(adapter.scan("entities", scope(), budget))
    assert isinstance(rows[0], SourceEntity)
    assert rows[0].record.id == UUID(int=6)
    assert rows[0].kind.value == "service"
    assert rows[0].status.value == "supported"
    assert "metadata" not in rows[0].model_dump()
    assert budget.rows == 1 and budget.calls == 3
    service.list_entities.assert_called_once_with(
        scope().architecture_version_id,
        scope().project_id,
        limit=200,
        offset=0,
    )
    assert service.get_version.call_count == 2


def test_scope_and_final_header_mismatch_rejected():
    service, adapter, budget = source()
    initial = service.get_version.return_value
    service.get_version.side_effect = [
        initial,
        initial.model_copy(update={"content_digest": "b" * 64}),
    ]
    with pytest.raises(ValueError, match="scope_mismatch"):
        list(adapter.scan("entities", scope(), budget))


@pytest.mark.parametrize(
    "change",
    [
        {"total": 2},
        {"offset": 1},
        {"limit": 201},
        {"items": []},
        {"total": 25001},
    ],
)
def test_malformed_incomplete_pages_never_silently_pass(change):
    service, adapter, budget = source()
    service.list_entities.return_value = service.list_entities.return_value.model_copy(
        update=change
    )
    with pytest.raises(ValueError, match="integrity"):
        list(adapter.scan("entities", scope(), budget))


def test_source_budget_and_expired_deadline():
    service, adapter, budget = source()
    budget.deadline = monotonic() - 1
    with pytest.raises(TimeoutError):
        list(adapter.scan("entities", scope(), budget))
    service.get_version.assert_not_called()
    _, adapter, budget = source()
    budget.limits = DiagramLimits(max_source_calls=2)
    with pytest.raises(ValueError, match="limit"):
        list(adapter.scan("entities", scope(), budget))


def test_cooperative_stop_propagates_without_lifecycle_write():
    service, adapter, budget = source()

    def stopped():
        raise RuntimeError("test cooperative stop")

    budget.checkpoint = stopped
    with pytest.raises(RuntimeError, match="cooperative"):
        list(adapter.scan("entities", scope(), budget))
    service.get_version.assert_not_called()


def test_third_collection_pass_is_rejected():
    _, adapter, budget = source()
    assert len(list(adapter.scan("entities", scope(), budget))) == 1
    assert len(list(adapter.scan("entities", scope(), budget))) == 1
    with pytest.raises(ValueError, match="limit"):
        list(adapter.scan("entities", scope(), budget))
