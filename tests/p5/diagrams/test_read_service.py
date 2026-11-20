"""Service keysets/pointer races with public contract doubles, not DB proofs."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from backend.platform.delivery.api_contracts import DeliverySummary, WorkSummary
from backend.platform.delivery.contracts import DiagramTemplate, WorkKind
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.cursors import CursorSigner
from backend.platform.diagrams.service import DiagramService
from tests.p5.diagrams.test_api import record_for
from tests.p5.diagrams.test_c2_consumers import prepared


@pytest.fixture
def history_service():
    first = prepared(
        DiagramTemplate.OVERVIEW, generation_id=UUID(int=100), artifact_id=UUID(int=101)
    )
    second = prepared(
        DiagramTemplate.OVERVIEW, generation_id=UUID(int=200), artifact_id=UUID(int=201)
    )
    values = {v.descriptor.reference.generation_id: v for v in (first, second)}
    now = datetime.now(UTC)
    rows = (
        (first.descriptor.reference.generation_id, now),
        (second.descriptor.reference.generation_id, now - timedelta(seconds=1)),
    )

    class Repository:
        active = first.descriptor.reference
        change_after_read = False

        def accepted(self, project, version, template, gid):
            ref = values[gid].descriptor.reference
            assert (
                ref.scope.project_id == project
                and ref.scope.architecture_version_id == version
                and ref.binding.slot.template == template
            )
            return ref, next(t for k, t in rows if k == gid), now

        def has_accepted(self, *args):
            return True

        def require_active(self, ref):
            if ref != self.active:
                raise ValueError("diagram_generation_changed")

        def history(self, ref, limit, high, after):
            return tuple(
                (g, t)
                for g, t in rows
                if (high is None or (t, g) <= high)
                and (after is None or (t, g) < after)
            )[: limit + 1]

    repo = Repository()

    class Reader:
        def read_exact(self, scope, ref):
            if repo.change_after_read:
                repo.active = second.descriptor.reference
            return values[ref.generation_id]

    class Runtime:
        def scope_for_record(self, record):
            return first.descriptor.reference.scope

        def summary(self, scope, role):
            return DeliverySummary(
                scope=scope,
                eligibility="ELIGIBLE",
                diagrams=(
                    WorkSummary(
                        kind=WorkKind.DIAGRAM,
                        template=DiagramTemplate.OVERVIEW,
                        state="COMPLETED",
                        reference=repo.active,
                    ),
                ),
            )

    service = DiagramService(
        repo,
        Reader(),
        DiagramLimits(),
        CursorSigner("test-key", "test-only-secret-not-a-default" * 2),
        None,
        None,
    )
    return service, repo, Runtime(), record_for(first), uuid4()


def test_history_keyset_highwater_and_absolute_expiry(history_service):
    service, repo, runtime, record, actor = history_service
    first = service.history(
        record, DiagramTemplate.OVERVIEW, actor, runtime, "VIEWER", 1, None
    )
    assert first.next_cursor
    cursor = service.signer.read(first.next_cursor)
    assert cursor.mode == "active" and cursor.high_water.accepted_at
    second = service.history(
        record, DiagramTemplate.OVERVIEW, actor, runtime, "VIEWER", 1, first.next_cursor
    )
    assert second.items[0].generation_id != first.items[0].generation_id
    assert second.next_cursor is None
    assert service.signer.read(first.next_cursor).expires_at == cursor.expires_at


def test_history_rejects_actor_request_and_generation_drift(history_service):
    service, repo, runtime, record, actor = history_service
    token = service.history(
        record, DiagramTemplate.OVERVIEW, actor, runtime, "VIEWER", 1, None
    ).next_cursor
    for other, limit in [(uuid4(), 1), (actor, 2)]:
        with pytest.raises(ValueError, match="diagram_cursor_invalid"):
            service.history(
                record, DiagramTemplate.OVERVIEW, other, runtime, "VIEWER", limit, token
            )
    repo.active = prepared(
        DiagramTemplate.OVERVIEW, generation_id=UUID(int=200), artifact_id=UUID(int=201)
    ).descriptor.reference
    with pytest.raises(ValueError, match="diagram_generation_changed"):
        service.history(
            record, DiagramTemplate.OVERVIEW, actor, runtime, "VIEWER", 1, token
        )


def test_history_final_pointer_check_happens_after_read_mapping(history_service):
    service, repo, runtime, record, actor = history_service
    repo.change_after_read = True
    with pytest.raises(ValueError, match="diagram_generation_changed"):
        service.history(
            record, DiagramTemplate.OVERVIEW, actor, runtime, "VIEWER", 1, None
        )


def test_exact_history_survives_dispatch_unavailability_and_no_false_not_scheduled(
    history_service,
):
    service, repo, _, record, _ = history_service
    result = service.summary(
        record, DiagramTemplate.OVERVIEW, None, "VIEWER", repo.active.generation_id
    )
    assert result.availability == "READY" and result.readability == "unknown"

    class UnknownRuntime:
        def scope_for_record(self, record):
            return None

    result = service.summary(
        record, DiagramTemplate.OVERVIEW, UnknownRuntime(), "VIEWER"
    )
    assert result.availability == "UNAVAILABLE" and result.reference is None


def test_public_delivery_scope_ambiguity_is_a_typed_conflict(history_service):
    from backend.platform.delivery.contracts import DeliveryContractError

    service, _, _, record, _ = history_service

    class Ambiguous:
        def scope_for_record(self, record):
            raise DeliveryContractError("private policy diagnostic")

    with pytest.raises(ValueError, match="diagram_scope_mismatch"):
        service.summary(record, DiagramTemplate.OVERVIEW, Ambiguous(), "VIEWER")
