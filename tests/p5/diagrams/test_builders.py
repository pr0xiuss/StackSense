"""Semantic acceptance; no layout, production publication or AI claims."""

import random
from pathlib import Path
from time import monotonic
from uuid import UUID

import pytest

from backend.platform.analysis.architecture.model import (
    ArchitectureEntityKind as K,
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
    ArchitectureRelationshipKind as R,
)
from backend.platform.delivery.contracts import DiagramTemplate as T
from backend.platform.diagrams.builders import BUILDERS, build_from_source
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import (
    DiagramViewRequest,
    EntityRef,
    EvidenceProvenance,
    EvidenceRef,
    Ref,
    RelationshipRef,
)
from backend.platform.diagrams.query import (
    DiagramInput,
    SourceBudget,
    SourceConflict,
    SourceEntity,
    SourceRelationship,
    SourceUnresolved,
)
from backend.platform.diagrams.validation import DiagramValidator
from tests.p5.diagrams.conftest import completeness, scope


def entity(n, kind=K.SERVICE, *, status=Status.SUPPORTED, evidence=()):
    return SourceEntity(
        record=EntityRef(
            record_type="entity", id=UUID(int=n), logical_id=f"entity:{n:05}"
        ),
        kind=kind,
        name=f"{kind.value} {n} α",
        namespace=("actual", "namespace"),
        status=status,
        evidence_ids=evidence,
    )


def relation(n, source, target, kind=R.CALLS, *, status=Status.CONFIRMED, evidence=()):
    return SourceRelationship(
        record=RelationshipRef(
            record_type="relationship",
            id=UUID(int=100000 + n),
            logical_id=f"relationship:{n:05}",
        ),
        kind=kind,
        source_logical_id=source.record.logical_id,
        target_logical_id=target.record.logical_id,
        status=status,
        evidence_ids=evidence,
    )


def data(
    entities=(),
    relationships=(),
    *,
    evidence=(),
    unresolved=(),
    conflicts=(),
    partial=False,
):
    c = completeness().model_copy(
        update={
            "is_partial": partial,
            "architecture_entities": len(entities),
            "architecture_relationships": len(relationships),
            "architecture_unresolved_relationships": len(unresolved),
            "architecture_conflicts": len(conflicts),
        }
    )
    return DiagramInput(
        scope=scope(),
        completeness=c,
        entities=tuple(entities),
        relationships=tuple(relationships),
        evidence=tuple(evidence),
        unresolved=tuple(unresolved),
        conflicts=tuple(conflicts),
        evidence_total=len(evidence),
    )


def request(
    *,
    roots=(),
    selected=(),
    kinds=(),
    relations=(),
    depth=4,
    direction="outgoing",
    contains=False,
):
    return DiagramViewRequest(
        root_ids=tuple(e.record.id for e in roots),
        entity_kinds=tuple(kinds),
        statuses=(),
        relationship_kinds=tuple(relations),
        include_contains=contains,
        depth=depth,
        direction=direction,
        collapsed_group_ids=(),
        selected_entity_ids=tuple(e.record.id for e in selected),
    )


def monorepo():
    kinds = (
        K.APPLICATION,
        K.APPLICATION,
        K.FRONTEND_APPLICATION,
        K.SERVICE,
        K.SERVICE,
        K.CONTROLLER,
        K.CONTROLLER,
        K.MODULE,
        K.COMPONENT,
        K.COMPONENT,
        K.DATABASE,
        K.MESSAGE_BROKER,
        K.WORKER,
        K.QUEUE,
        K.EXTERNAL_API,
        K.LIBRARY,
        K.ENDPOINT,
    )
    entities = [entity(i + 1, kind) for i, kind in enumerate(kinds)]
    (
        a,
        b,
        ui,
        py,
        js,
        pyc,
        jsc,
        module,
        component,
        button,
        db,
        broker,
        worker,
        queue,
        api,
        lib,
        endpoint,
    ) = entities
    triples = [
        (a, py, R.CONTAINS),
        (a, pyc, R.CONTAINS),
        (a, module, R.CONTAINS),
        (b, js, R.CONTAINS),
        (b, jsc, R.CONTAINS),
        (ui, component, R.CONTAINS),
        (ui, button, R.CONTAINS),
        (py, db, R.PERSISTS_TO),
        (js, py, R.CALLS),
        (worker, queue, R.CONSUMES),
        (js, queue, R.PRODUCES),
        (py, api, R.CALLS),
        (module, lib, R.IMPORTS),
        (a, endpoint, R.EXPOSES),
        (a, endpoint, R.CONTAINS),
        (component, endpoint, R.CALLS),
    ]
    return data(entities, [relation(i + 1, *args) for i, args in enumerate(triples)])


def build(value, template=T.OVERVIEW, **kwargs):
    return BUILDERS[template].build(
        value, kwargs.pop("limits", DiagramLimits()), **kwargs
    )


def refs(result):
    return {n.entity.logical_id for n in result.spec.nodes} | {
        ref.logical_id for g in result.catalog.groups for ref in g.members
    }


def member_kinds(result):
    return {m.kind for e in result.spec.edges for m in e.members}


@pytest.mark.parametrize("template", list(T))
def test_four_independent_products_and_permutation_stability(template):
    source = monorepo()
    expected = build(source, template)
    DiagramValidator(DiagramLimits()).semantic(expected.spec, expected.catalog)
    for seed in range(5):
        generator = random.Random(seed)
        changes = {}
        for name in (
            "entities",
            "relationships",
            "evidence",
            "unresolved",
            "conflicts",
        ):
            values = list(getattr(source, name))
            generator.shuffle(values)
            changes[name] = tuple(values)
        result = build(source.model_copy(update=changes), template)
        assert result.spec.to_bytes() == expected.spec.to_bytes()
        assert result.catalog.to_bytes() == expected.catalog.to_bytes()


def test_overview_selects_architectural_boundaries_not_frontend_flood():
    source = monorepo()
    result = build(source)
    selected = {n.entity.id for n in result.spec.nodes}
    assert UUID(int=4) in selected and UUID(int=5) in selected  # Python and JS services
    assert UUID(int=9) in selected  # real cross-boundary UI call, not a filename guess
    assert UUID(int=10) not in selected  # unconnected button
    assert UUID(int=16) not in selected  # library granularity
    assert R.IMPORTS not in member_kinds(result)
    assert R.CONTAINS not in member_kinds(result)
    assert {g.container.id for g in result.spec.groups if g.container} >= {
        UUID(int=1),
        UUID(int=2),
    }


def test_component_preserves_python_js_and_canonical_multiple_parents_and_cycle():
    a, b, child, x, y = (
        entity(1, K.APPLICATION),
        entity(2, K.APPLICATION),
        entity(3, K.SERVICE),
        entity(4, K.MODULE),
        entity(5, K.CONTROLLER),
    )
    source = data(
        (a, b, child, x, y),
        (
            relation(1, a, child, R.CONTAINS),
            relation(2, b, child, R.CONTAINS),
            relation(3, x, y, R.CONTAINS),
            relation(4, y, x, R.CONTAINS),
        ),
    )
    result = build(source, T.COMPONENT)
    assert result.spec.view.multi_parent[0].layout_parent == a.record
    assert result.spec.view.multi_parent[0].parents == (a.record, b.record)
    assert result.spec.view.containment_cycles == ((x.record, y.record),)
    assert {x.record.logical_id, y.record.logical_id} <= refs(result)
    assert {a.kind for a in result.spec.annotations} >= {
        "multiple_parents",
        "containment_cycle",
    }


@pytest.mark.parametrize("kind", [r for r in R if r != R.CONTAINS])
def test_all_twelve_dependency_kinds_preserve_actual_endpoints(kind):
    a, b = entity(1), entity(2)
    rel = relation(1, a, b, kind)
    result = build(data((a, b), (rel,)), T.DEPENDENCY)
    assert member_kinds(result) == {kind}
    member = result.spec.edges[0].members[0]
    assert (member.relationship, member.source, member.target) == (
        rel.record,
        a.record,
        b.record,
    )


def test_incoming_does_not_reverse_edges_or_traverse_contains():
    a, b, c = entity(1), entity(2), entity(3)
    source = data((a, b, c), (relation(1, a, b), relation(2, b, c, R.CONTAINS)))
    result = build(
        source, T.DEPENDENCY, request=request(roots=(b,), direction="incoming")
    )
    assert refs(result) == {a.record.logical_id, b.record.logical_id}
    assert result.spec.edges[0].members[0].source == a.record
    assert R.CONTAINS not in member_kinds(result)


@pytest.mark.parametrize(
    "pairs,expected",
    [
        ([(1, 2), (1, 3), (2, 3)], 0),
        ([(1, 2), (2, 1)], 1),
        ([(1, 1)], 1),
        ([(1, 2), (2, 3), (3, 1)], 1),
    ],
)
def test_sccs_are_iterative_exact_selected_dependency_cycles(pairs, expected):
    nodes = {i: entity(i) for i in (1, 2, 3)}
    source = data(
        nodes.values(),
        [relation(i, nodes[a], nodes[b]) for i, (a, b) in enumerate(pairs)],
    )
    result = build(source, T.DEPENDENCY)
    assert len(result.spec.view.sccs) == expected
    assert all(g.kind == "selected_scc" for g in result.spec.groups)


def test_consumes_and_static_flow_labels_are_not_runtime_claims():
    consumer, channel, producer = entity(1, K.WORKER), entity(2, K.TOPIC), entity(3)
    source = data(
        (consumer, channel, producer),
        (
            relation(1, consumer, channel, R.CONSUMES),
            relation(2, producer, channel, R.PRODUCES),
        ),
    )
    result = build(source, T.DATA_FLOW)
    consumes = next(e for e in result.spec.edges if e.label == "consumes from")
    assert consumes.members[0].source == consumer.record
    assert consumes.members[0].target == channel.record
    assert "not observed traffic" in result.spec.legend[0].label
    assert R.DEPENDS_ON not in member_kinds(result)


@pytest.mark.parametrize("template", list(T))
@pytest.mark.parametrize("partial", [False, True])
def test_honest_empty_views(template, partial):
    result = build(data(partial=partial), template)
    assert not result.spec.nodes and not result.spec.edges
    assert result.spec.coverage.view_state == "empty_view"
    assert result.spec.coverage.source_partial == partial
    if template == T.DATA_FLOW:
        assert result.spec.view.no_flow_reason == (
            "insufficient_evidence" if partial else "no_established_data_flow"
        )


def test_connectivity_is_opt_in_and_dependencies_never_become_flows():
    a, b = entity(1), entity(2, K.DATABASE)
    source = data(
        (a, b), (relation(1, a, b, R.DEPENDS_ON), relation(2, a, b, R.CONNECTS_TO))
    )
    assert not build(source, T.DATA_FLOW).spec.edges
    result = build(source, T.DATA_FLOW, request=request(relations=(R.CONNECTS_TO,)))
    assert result.spec.edges[0].label == "connectivity only"
    assert result.spec.view.connectivity_overlay is True


def test_static_interactions_never_manufacture_containment():
    app, service = entity(1, K.APPLICATION), entity(2)
    result = build(data((app, service), (relation(1, app, service),)), T.DATA_FLOW)
    assert not result.spec.groups
    assert not result.catalog.groups


@pytest.mark.parametrize("template", [T.COMPONENT, T.OVERVIEW])
def test_focused_application_includes_real_referenced_boundary(template):
    app, service, db = entity(1, K.APPLICATION), entity(2), entity(3, K.DATABASE)
    source = data(
        (app, service, db),
        (
            relation(1, app, service, R.CONTAINS),
            relation(2, service, db, R.PERSISTS_TO),
        ),
    )
    result = build(source, template, request=request(roots=(app,)))
    assert db.record.logical_id in refs(result)
    assert R.PERSISTS_TO in member_kinds(result)


def test_contains_overlay_is_not_a_dependency_or_flow():
    a, b = entity(1), entity(2)
    source = data((a, b), (relation(1, a, b, R.CONTAINS),))
    assert not build(source, T.DEPENDENCY).spec.nodes
    result = build(source, T.DEPENDENCY, request=request(contains=True))
    assert member_kinds(result) == {R.CONTAINS}
    assert not result.spec.view.sccs
    with pytest.raises(ValueError, match="input_invalid"):
        build(source, T.DATA_FLOW, request=request(contains=True))


def test_public_source_handoff_scans_each_collection_once_and_checks_final_header():
    value = monorepo()

    class Source:
        def __init__(self):
            self.calls = []
            self.headers = 0

        def header(self, scope, budget):
            budget.check()
            self.headers += 1
            return value.completeness

        def scan(self, collection, scope, budget):
            self.calls.append(collection)
            yield from getattr(value, collection)

    source = Source()
    budget = SourceBudget(DiagramLimits(), monotonic() + 10, lambda: None)
    result = build_from_source(source, value.scope, T.OVERVIEW, budget)
    assert result.spec.to_bytes() == build(value).spec.to_bytes()
    assert source.calls == [
        "entities",
        "relationships",
        "unresolved",
        "conflicts",
        "evidence",
    ]
    assert source.headers == 3


def test_bundles_never_merge_competing_status_or_kind():
    a, b = entity(1), entity(2)
    edges = (
        relation(1, a, b, R.CALLS),
        relation(2, a, b, R.CALLS),
        relation(3, a, b, R.CALLS, status=Status.CONFLICTING),
        relation(4, a, b, R.USES),
    )
    result = build(data((a, b), edges), T.DEPENDENCY)
    assert sorted(len(edge.members) for edge in result.spec.edges) == [1, 1, 2]
    assert {m.relationship.id for e in result.spec.edges for m in e.members} == {
        e.record.id for e in edges
    }


def test_sccs_do_not_claim_cycles_after_edge_budget_cuts_the_cycle():
    a, b = entity(1), entity(2)
    result = build(
        data((a, b), (relation(1, a, b), relation(2, b, a))),
        T.DEPENDENCY,
        limits=DiagramLimits(max_edges=1),
    )
    assert len(result.spec.edges) == 1
    assert not result.spec.view.sccs
    assert result.spec.coverage.selection_bounded


@pytest.mark.parametrize("template", [T.COMPONENT, T.DEPENDENCY])
def test_optional_group_limit_preserves_canonical_nodes_with_explicit_warning(template):
    nodes = tuple(entity(i, K.APPLICATION if i % 2 else K.SERVICE) for i in range(1, 7))
    edges = []
    for i in (0, 2, 4):
        edges.append(
            relation(
                i + 1,
                nodes[i],
                nodes[i + 1],
                R.CONTAINS if template == T.COMPONENT else R.CALLS,
            )
        )
        if template == T.DEPENDENCY:
            edges.append(relation(i + 100, nodes[i + 1], nodes[i], R.CALLS))
    result = build(data(nodes, edges), template, limits=DiagramLimits(max_groups=1))
    assert len(result.spec.nodes) == 6 and len(result.spec.groups) == 1
    assert any(
        a.reason.startswith("presentation grouping budget")
        for a in result.spec.annotations
    )
    assert result.spec.coverage.selection_bounded


def test_fanout_and_byte_bounds_are_fail_closed_or_explicitly_bounded():
    nodes = tuple(entity(i) for i in range(1, 10))
    edges = tuple(relation(i, nodes[0], node) for i, node in enumerate(nodes[1:]))
    result = build(data(nodes, edges), T.DEPENDENCY, limits=DiagramLimits(max_fanout=2))
    assert len(result.spec.edges) == 2
    assert (
        len(
            [
                o
                for o in result.catalog.omitted
                if o.record.record_type == "relationship"
            ]
        )
        == 6
    )
    for limits in (
        DiagramLimits(max_retained_bytes=1),
        DiagramLimits(max_spec_bytes=1),
        DiagramLimits(max_members_bytes=1),
    ):
        with pytest.raises(ValueError, match="limit"):
            build(data(nodes, edges), T.DEPENDENCY, limits=limits)


def test_overview_depth_counts_hidden_intermediate_containment():
    app = entity(1, K.APPLICATION)
    modules = [entity(i, K.MODULE) for i in (2, 3, 4)]
    service = entity(5)
    nodes = (app, *modules, service)
    edges = tuple(
        relation(i, a, b, R.CONTAINS)
        for i, (a, b) in enumerate(zip(nodes, nodes[1:], strict=False))
    )
    result = build(data(nodes, edges), request=request(depth=2))
    assert service.record.id not in {n.entity.id for n in result.spec.nodes}
    assert any(
        o.record.id == service.record.id and o.reason == "depth"
        for o in result.catalog.omitted
    )


def test_optional_connectivity_is_not_claimed_as_established_data_flow():
    a, b = entity(1), entity(2, K.DATABASE)
    result = build(
        data((a, b), (relation(1, a, b, R.CONNECTS_TO),)),
        T.DATA_FLOW,
        request=request(relations=(R.CONNECTS_TO,)),
    )
    assert result.spec.view.no_flow_reason == "no_established_data_flow"


def test_view_set_order_does_not_change_identity_or_digest():
    source = monorepo()
    a = request(kinds=(K.SERVICE, K.DATABASE), relations=(R.CALLS, R.PERSISTS_TO))
    b = a.model_copy(
        update={
            "entity_kinds": tuple(reversed(a.entity_kinds)),
            "relationship_kinds": tuple(reversed(a.relationship_kinds)),
        }
    )
    assert (
        build(source, request=a).spec.to_bytes()
        == build(source, request=b).spec.to_bytes()
    )


def test_ambiguous_overview_ownership_is_not_forced_into_a_group():
    a, b, service = entity(1, K.APPLICATION), entity(2, K.APPLICATION), entity(3)
    result = build(
        data(
            (a, b, service),
            (relation(1, a, service, R.CONTAINS), relation(2, b, service, R.CONTAINS)),
        )
    )
    node = next(n for n in result.spec.nodes if n.entity == service.record)
    assert node.group_id is None
    assert any(
        a.reason == "no unambiguous canonical application owner"
        for a in result.spec.annotations
    )


def test_catalog_members_do_not_hide_visible_depth_omissions():
    app, a, b = entity(1, K.APPLICATION), entity(2), entity(3)
    source = data(
        (app, a, b), (relation(1, app, a, R.CONTAINS), relation(2, a, b, R.CONTAINS))
    )
    result = build(source, T.COMPONENT, request=request(depth=1))
    counts = [c for c in result.spec.coverage.counts if c.collection == "entities"]
    assert sum(c.represented for c in counts) == 2
    assert sum(c.omitted for c in counts) == 1
    assert b.record.logical_id in refs(result)  # reference retained, not visible
    assert b.record.id not in {n.entity.id for n in result.spec.nodes}


def test_public_assembly_retains_only_selected_evidence_and_rejects_header_drift():
    evidence = tuple(
        EvidenceProvenance(
            record=EvidenceRef(
                record_type="evidence",
                id=UUID(int=8000 + i),
                logical_id=f"evidence:{i}",
            ),
            source_record_type="inventory",
            producer_id=None,
            producer_version=None,
            artifact_id=None,
            source_fact_key=None,
            path="canonical/path",
            source_range=None,
            strength=Strength.CONFIGURATION,
            polarity=Polarity.SUPPORTING,
        )
        for i in range(3)
    )
    nodes = tuple(
        entity(i + 1, evidence=(e.record.logical_id,)) for i, e in enumerate(evidence)
    )
    value = data(nodes, evidence=evidence)

    class Source:
        def __init__(self, drift=False):
            self.headers = 0
            self.drift = drift

        def header(self, scope, budget):
            budget.check()
            self.headers += 1
            if self.drift and self.headers > 1:
                return value.completeness.model_copy(update={"failed_artifacts": 1})
            return value.completeness

        def scan(self, collection, scope, budget):
            yield from getattr(value, collection)

    limits = DiagramLimits(max_nodes=1)
    budget = SourceBudget(limits, monotonic() + 10, lambda: None)
    built = build_from_source(Source(), value.scope, T.OVERVIEW, budget)
    assert built.spec.provenance == (evidence[0],)
    count = next(c for c in built.spec.coverage.counts if c.collection == "evidence")
    assert (count.scanned, count.represented, count.omitted) == (3, 1, 2)
    with pytest.raises(ValueError, match="integrity"):
        build_from_source(
            Source(drift=True),
            value.scope,
            T.OVERVIEW,
            SourceBudget(limits, monotonic() + 10, lambda: None),
        )


def test_canonical_validator_rejects_redigested_tampered_node():
    from backend.platform.diagrams.contracts import DiagramSpec
    from backend.platform.diagrams.model import digest

    source = monorepo()
    result = build(source)
    payload = result.spec.model_dump(exclude={"semantic_digest"})
    payload["nodes"][0]["name"] = "fabricated responsibility"
    payload["semantic_digest"] = digest("ss.diagram.semantic", payload)
    changed = DiagramSpec.model_validate(payload)
    with pytest.raises(ValueError, match="canonical node mismatch"):
        DiagramValidator(DiagramLimits()).semantic(
            changed, result.catalog, source=source
        )


def test_uncertainty_and_actual_producer_provenance_preserved():
    p = EvidenceProvenance(
        record=EvidenceRef(
            record_type="evidence", id=UUID(int=9999), logical_id="evidence:actual"
        ),
        source_record_type="detection",
        producer_id="actual.producer",
        producer_version="1.0.0",
        artifact_id=None,
        source_fact_key=None,
        path="actual/path.py",
        source_range={"start_line": 1},
        strength=Strength.DIRECT_SOURCE,
        polarity=Polarity.CONFLICTING,
    )
    e = entity(1, status=Status.INFERRED, evidence=(p.record.logical_id,))
    u = SourceUnresolved(
        record=Ref(
            record_type="unresolved", id=UUID(int=9998), logical_id="unresolved:actual"
        ),
        kind=R.CALLS,
        source_logical_id=e.record.logical_id,
        target_descriptor="dynamic target",
        reason="dynamic_reference",
        status=Status.UNRESOLVED,
        evidence_ids=(p.record.logical_id,),
        candidate_references=(),
    )
    c = SourceConflict(
        record=Ref(
            record_type="conflict", id=UUID(int=9997), logical_id="conflict:actual"
        ),
        conflict_type="competing",
        subject_key=e.record.logical_id,
        evidence_ids=(p.record.logical_id,),
    )
    result = build(
        data((e,), evidence=(p,), unresolved=(u,), conflicts=(c,), partial=True)
    )
    assert result.spec.nodes[0].status == Status.INFERRED
    assert result.spec.provenance == (p,)
    assert {a.kind for a in result.spec.annotations} == {"unresolved", "conflict"}
    assert result.spec.provenance[0].source_fact_key is None
    with pytest.raises(ValueError, match="integrity"):
        build(data((e,)))


def test_scene_budget_discloses_all_omissions_and_required_overflow_fails():
    nodes = tuple(entity(i) for i in range(1, 10))
    source = data(nodes)
    result = build(source, limits=DiagramLimits(max_nodes=3))
    assert len(result.spec.nodes) == 3
    assert len(result.catalog.omitted) == 6
    assert result.spec.coverage.selection_bounded
    assert (
        sum(
            c.omitted for c in result.spec.coverage.counts if c.collection == "entities"
        )
        == 6
    )
    with pytest.raises(ValueError, match="limit"):
        build(
            source,
            limits=DiagramLimits(max_nodes=1, max_selected_ids=3),
            request=request(selected=nodes[:2]),
        )


def test_bad_identity_endpoint_and_cooperative_stop_fail_closed():
    a, b = entity(1), entity(2)
    for source in (data((a, a)), data((a,), (relation(1, a, b),))):
        with pytest.raises(ValueError, match="integrity"):
            build(source)

    def cancelled():
        raise InterruptedError("cancelled")

    with pytest.raises(InterruptedError):
        build(data((a,)), checkpoint=cancelled)


@pytest.mark.parametrize("template", list(T))
def test_frozen_b1_schema_accepts_builder_goldens(template):
    path = (
        Path(__file__).resolve().parents[2]
        / "fixtures/p5/diagrams"
        / f"b2_{template.value}.json"
    )
    result = build(monorepo(), template)
    assert result.spec.to_bytes() == path.read_bytes().replace(b"\r\n", b"\n").rstrip(
        b"\n"
    )
