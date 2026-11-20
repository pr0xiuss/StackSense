"""Adversarial regressions for the independent M3 review findings."""

from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from pydantic import SecretStr, ValidationError

from backend.platform.graph.model import ProjectionCounts
from backend.platform.graph.query_contracts import (
    GraphNode,
    GraphReadScope,
    GraphSubgraph,
)
from backend.platform.knowledge.context import ContextBuilder
from backend.platform.knowledge.contracts import SearchHit, SearchPage
from backend.platform.knowledge.model import KnowledgeDocumentKind
from backend.platform.knowledge.retrieval import KnowledgeQueryService, decode_c3_cursor
from backend.platform.knowledge.retrieval_configuration import RetrievalPolicy
from backend.platform.knowledge.retrieval_contracts import (
    CanonicalFactView,
    ContextBundle,
    KnowledgeQueryRequest,
    RetrievalCapacityExceededError,
    RetrievalCursorInvalidError,
    RetrievalGenerationChangedError,
    RetrievalIntegrityFailedError,
    RetrievalOperation,
    RetrievalOutcome,
    RetrievalUnavailableError,
    SubjectSelector,
)
from backend.platform.knowledge.retrieval_dependencies import (
    get_retrieval_cursor_secret,
    get_retrieval_policy,
)
from tests.p5.knowledge.conftest import make_test_scope
from tests.p5.knowledge.test_context import _make_plan
from tests.p5.knowledge.test_retrieval import MockCanonicalPort, _setup_test_environment
from tests.p5.knowledge.test_retrieval_api import retrieval_fixture as retrieval_fixture


@pytest.fixture
def case():
    _, _, scope, principal, policy, secret = _setup_test_environment()
    canonical = MockCanonicalPort(scope)
    canonical.entities = [
        CanonicalFactView(
            record_id=uuid4(),
            logical_id=f"entity://{i}",
            kind="service",
            name=f"Service{i}",
            status="confirmed",
        )
        for i in range(3)
    ]
    return canonical, scope, principal, policy, secret


def service(case, **kwargs):
    canonical, _, _, policy, secret = case
    return KnowledgeQueryService(
        canonical,
        policy=kwargs.pop("policy", policy),
        cursor_secret_key=secret,
        **kwargs,
    )


def query(case, **kwargs):
    _, scope, _, _, _ = case
    return KnowledgeQueryRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        operation=RetrievalOperation.LOOKUP,
        **kwargs,
    )


class Search:
    def __init__(self, case, drift=False, foreign=False):
        canonical, scope, *_ = case
        self.scope = make_test_scope(
            **{
                k: getattr(scope, k)
                for k in (
                    "project_id",
                    "architecture_version_id",
                    "repository_id",
                    "analysis_id",
                    "snapshot_id",
                    "canonical_digest",
                )
            }
        )
        if foreign:
            self.scope = self.scope.model_copy(update={"repository_id": uuid4()})
        self.fact = canonical.entities[0]
        self.generation = uuid4()
        self.calls = []
        self.drift = drift

    def search(self, request, *, actor_id):
        self.calls.append(request)
        hit = SearchHit(
            knowledge_key="a" * 64,
            document_kind=KnowledgeDocumentKind.ENTITY,
            canonical_reference=self.fact.logical_id,
            title=self.fact.name,
            score=1.0,
            scope=self.scope,
        )
        return SearchPage(
            scope=self.scope,
            generation_id=(
                uuid4() if self.drift and len(self.calls) > 1 else self.generation
            ),
            index_uuid="exact-index",
            items=(hit,),
            total_hits=1,
            has_more=False,
        )


def test_canonical_only_never_opens_optional_services(case):
    factory = Mock(side_effect=AssertionError("Optional service opened"))
    result = service(case, search_factory=factory, graph_factory=factory).query(
        query(
            case,
            subject=SubjectSelector.from_record_id(
                "entity", case[0].entities[0].record_id
            ),
        ),
        principal=case[2],
    )
    assert result.outcome == RetrievalOutcome.COMPLETE
    assert all(o.freshness.value == "UNKNOWN" for o in result.source_observations)
    factory.assert_not_called()


def test_text_search_does_not_fallback_to_unfiltered_canonical(case):
    with pytest.raises(RetrievalUnavailableError):
        service(case).query(query(case, q="missing"), principal=case[2])


def test_search_rehydrates_and_preserves_probe_parameters(case):
    search = Search(case)
    result = service(case, search_port=search).query(
        query(case, q="Service", limit=2, document_kinds=("entity",)), principal=case[2]
    )
    assert result.facts == (case[0].entities[0],)
    assert len(search.calls) == 2
    assert search.calls[0].q == search.calls[1].q
    assert search.calls[0].limit == search.calls[1].limit == 2
    assert search.calls[0].document_kinds == search.calls[1].document_kinds
    assert (
        "lexical"
        in next(
            o for o in result.source_observations if o.source_kind.value == "search"
        ).capabilities
    )


@pytest.mark.parametrize(
    "foreign,drift,error",
    [
        (True, False, RetrievalIntegrityFailedError),
        (False, True, RetrievalGenerationChangedError),
    ],
)
def test_search_scope_and_final_pointer_fail_closed(case, foreign, drift, error):
    with pytest.raises(error):
        service(case, search_port=Search(case, foreign=foreign, drift=drift)).query(
            query(case, q="Service"), principal=case[2]
        )


def test_source_call_budget_is_aggregate(case):
    with pytest.raises(RetrievalCapacityExceededError):
        service(case, policy=RetrievalPolicy(max_source_calls=1)).query(
            query(
                case,
                subject=SubjectSelector.from_record_id(
                    "entity", case[0].entities[0].record_id
                ),
            ),
            principal=case[2],
        )


def test_bundle_nested_values_are_frozen_and_digest_checked(case):
    _, scope, _, policy, _ = case
    fact = (
        case[0]
        .entities[0]
        .model_copy(update={"metadata": {"framework": {"name": "fastapi"}}})
    )
    bundle = ContextBuilder(
        scope=scope, plan=_make_plan(policy), policy=policy
    ).build_bundle(facts=[fact])
    with pytest.raises(TypeError):
        bundle.facts[0].metadata["framework"]["name"] = "changed"
    with pytest.raises(TypeError):
        bundle.plan.budget_snapshot["limit"] = 123
    payload = bundle.model_dump(mode="json")
    payload["facts"][0]["name"] = "tampered"
    with pytest.raises(ValidationError, match="digest mismatch"):
        ContextBundle.model_validate(payload)


def test_nested_non_json_mutable_metadata_is_rejected():
    with pytest.raises(ValidationError, match="immutable JSON"):
        CanonicalFactView(
            record_id=uuid4(),
            logical_id="entity://unsafe",
            kind="service",
            name="Unsafe",
            status="confirmed",
            metadata={"opaque": {1, 2}},
        )


def test_duplicate_identity_conflict_is_not_first_wins(case):
    _, scope, _, policy, _ = case
    first = case[0].entities[0]
    with pytest.raises(RetrievalIntegrityFailedError):
        ContextBuilder(
            scope=scope, plan=_make_plan(policy), policy=policy
        ).build_bundle(facts=[first, first.model_copy(update={"name": "different"})])


def test_duplicate_record_uuid_cannot_have_two_logical_ids(case):
    _, scope, _, policy, _ = case
    first = case[0].entities[0]
    with pytest.raises(RetrievalIntegrityFailedError):
        ContextBuilder(
            scope=scope, plan=_make_plan(policy), policy=policy
        ).build_bundle(
            facts=[first, first.model_copy(update={"logical_id": "entity://other"})]
        )


def test_candidate_limit_applies_during_scan(case):
    case[0].entities = [
        e.model_copy(update={"name": "Duplicate"}) for e in case[0].entities
    ]
    with pytest.raises(RetrievalCapacityExceededError, match="Candidate budget"):
        service(case, policy=RetrievalPolicy(max_retained_candidates=1)).query(
            query(
                case,
                subject=SubjectSelector(selector_type="entity_name", name="Duplicate"),
            ),
            principal=case[2],
        )


def test_api_does_not_log_invalid_input_or_raw_cause(retrieval_fixture, caplog):
    client, _, port, scope, *_ = retrieval_fixture
    url = (
        f"/api/v1/architecture-versions/{scope.architecture_version_id}"
        f"/knowledge/query?project_id={scope.project_id}"
    )
    secret = "SECRET-invalid-input-must-not-be-logged"
    response = client.post(url, json={"operation": secret})
    assert response.status_code == 422
    assert secret not in response.text and secret not in caplog.text
    port.error = RetrievalUnavailableError(cause=secret)
    response = client.post(url, json={"operation": "lookup"})
    assert response.status_code == 503
    assert secret not in response.text and secret not in caplog.text


def test_final_wire_size_is_exact(case):
    _, scope, _, policy, _ = case
    bundle = ContextBuilder(
        scope=scope, plan=_make_plan(policy), policy=policy
    ).build_bundle(facts=case[0].entities)
    assert bundle.limits_and_usage.total_output_bytes == len(
        bundle.model_dump_json().encode()
    )
    # A smaller operating limit is itself in the payload; leave headroom for
    # its shorter integer representation, then cross the final-wire boundary.
    small = policy.model_copy(
        update={"max_output_bytes": len(bundle.model_dump_json().encode()) - 32}
    )
    with pytest.raises(RetrievalCapacityExceededError):
        ContextBuilder(scope=scope, plan=_make_plan(small), policy=small).build_bundle(
            facts=case[0].entities
        )


def test_cursor_does_not_renew_and_rejects_malformed_before_reads(case):
    port, scope, principal, policy, secret = case
    req = KnowledgeQueryRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        operation=RetrievalOperation.EVIDENCE,
        limit=1,
    )
    from backend.platform.knowledge.retrieval_contracts import EvidenceItemView

    port.evidence = [
        EvidenceItemView(
            record_id=uuid4(),
            logical_id=f"ev-{i}",
            source_record_type="declaration",
            path="src/app.py",
            polarity="supporting",
            strength="direct_source",
        )
        for i in range(3)
    ]
    with patch("backend.platform.knowledge.retrieval.time.time", return_value=1000):
        first = service(case).query(req, principal=principal)
    continued = req.model_copy(update={"cursor": first.next_cursor})
    with patch("backend.platform.knowledge.retrieval.time.time", return_value=1100):
        second = service(case).query(continued, principal=principal)
        data = decode_c3_cursor(
            second.next_cursor,
            secret_key=secret,
            principal=principal,
            scope=scope,
            request=req,
            policy=policy,
        )
    assert data["iat"] == 1000 and data["exp"] == 1300
    port.get_version = Mock(side_effect=AssertionError("Read before validation"))
    with pytest.raises(RetrievalCursorInvalidError):
        service(case).query(
            req.model_copy(update={"cursor": "malformed"}), principal=principal
        )
    port.get_version.assert_not_called()


def test_required_graph_is_not_ignored(retrieval_fixture):
    client, _, _, scope, fact, *_ = retrieval_fixture
    response = client.post(
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/context?project_id={scope.project_id}",
        json={
            "subjects": [
                {"selector_type": "record_id", "record_id": str(fact.record_id)}
            ],
            "operations": ["dependencies"],
            "required_sources": ["canonical", "graph"],
            "optional_sources": [],
        },
    )
    assert response.status_code == 503


def test_evidence_scan_incomplete_is_not_complete(retrieval_fixture):
    client, app, port, scope, fact, *_ = retrieval_fixture
    from backend.platform.knowledge.retrieval_dependencies import get_retrieval_policy

    app.dependency_overrides[get_retrieval_policy] = lambda: RetrievalPolicy(
        canonical_max_rows_per_collection=1
    )
    port.evidence.reverse()
    response = client.post(
        f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge/context?project_id={scope.project_id}",
        json={
            "subjects": [
                {"selector_type": "record_id", "record_id": str(fact.record_id)}
            ],
            "operations": ["lookup"],
        },
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == "partial"
    assert "evidence_scan_incomplete" in response.json()["coverage"]["omission_reasons"]
    assert response.json()["coverage"]["exhausted"] is False


def test_unconfigured_policy_and_secret_fail_closed():
    settings = SimpleNamespace(
        retrieval_policy_json=None,
        retrieval_cursor_secret=None,
        jwt_secret_key=SecretStr("known-dev-key"),
    )
    with patch(
        "backend.platform.knowledge.retrieval_dependencies.get_settings",
        return_value=settings,
    ):
        with pytest.raises(RetrievalUnavailableError):
            get_retrieval_policy()
        with pytest.raises(RetrievalUnavailableError):
            get_retrieval_cursor_secret()


def test_graph_projection_cannot_invent_canonical_fact(case):
    port, scope, principal, *_ = case

    class Graph:
        def get_dependencies(self, request):
            read = GraphReadScope(
                project_id=scope.project_id,
                architecture_version_id=scope.architecture_version_id,
                generation_id=uuid4(),
                resource_state="COMPLETED",
                graph_schema_version="1.0.0",
                projector_version="1.0.0",
                counts=ProjectionCounts(1, 0, 0, 0, 0),
            )
            node = GraphNode(
                architecture_entity_id=uuid4(),
                logical_id="entity://fabricated",
                canonical_kind="service",
                name="Fabricated",
                namespace="root",
                fact_status="confirmed",
                semantic_signature="a" * 64,
                evidence_logical_ids=(),
                metadata={},
            )
            return GraphSubgraph(
                scope=read,
                nodes=(node,),
                edges=(),
                total_manifest_nodes=1,
                total_manifest_edges=0,
                loaded_nodes=1,
                loaded_edges=0,
                truncated=False,
            )

    with pytest.raises(RetrievalIntegrityFailedError):
        service(case, graph_port=Graph()).query(
            query(
                case,
                subject=SubjectSelector.from_record_id(
                    "entity", port.entities[0].record_id
                ),
            ).model_copy(update={"operation": RetrievalOperation.DEPENDENCIES}),
            principal=principal,
        )
