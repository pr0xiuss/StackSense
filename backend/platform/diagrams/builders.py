"""Four deterministic canonical-only semantic builders. No layout or lifecycle.

The read helper uses only the public paged source adapter. Pure builders work
on immutable request-local inputs; all grouping is presentation, never identity
resolution, transitive architecture inference or a replacement canonical model.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from time import monotonic
from types import MappingProxyType
from typing import ClassVar, Literal, cast
from uuid import UUID

from backend.platform.analysis.architecture.model import (
    ArchitectureEntityKind as Kind,
)
from backend.platform.analysis.architecture.model import (
    ArchitectureRelationshipKind as Rel,
)
from backend.platform.delivery.contracts import DiagramTemplate as Template
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import (
    Annotation,
    CanonicalDiagramScope,
    ComponentView,
    Count,
    Coverage,
    DataFlowView,
    DependencyView,
    DiagramEdge,
    DiagramGroup,
    DiagramNode,
    DiagramSpec,
    DiagramViewRequest,
    EntityRef,
    EvidenceProvenance,
    EvidenceRef,
    GroupMembership,
    LegendItem,
    MembershipCatalog,
    MultipleParents,
    OmissionReason,
    OmittedRecord,
    OverviewView,
    Ref,
    RelationshipMember,
    SemanticProfile,
    ViewDefinition,
)
from backend.platform.diagrams.model import (
    digest,
    normalize_sets,
    template_rules,
    visual_id,
)
from backend.platform.diagrams.query import (
    DiagramInput,
    DiagramSourceAdapter,
    SourceBudget,
    SourceConflict,
    SourceEntity,
    SourceRecord,
    SourceRelationship,
    SourceUnresolved,
)
from backend.platform.diagrams.validation import DiagramValidator

APPS = frozenset((Kind.APPLICATION, Kind.FRONTEND_APPLICATION))
PERSISTENCE = frozenset((Kind.DATABASE, Kind.MESSAGE_BROKER, Kind.QUEUE, Kind.TOPIC))
EXTERNAL = frozenset((Kind.EXTERNAL_SERVICE, Kind.EXTERNAL_API))
DETAIL = frozenset((Kind.MODULE, Kind.LIBRARY, Kind.CONFIGURATION_COMPONENT))
LABELS = {kind: kind.value.replace("_", " ") for kind in Rel} | {
    Rel.CONSUMES: "consumes from",
    Rel.CALLS: "static invocation",
    Rel.ROUTES_TO: "static routing",
    Rel.CONNECTS_TO: "connectivity only",
    Rel.PERSISTS_TO: "persistence association",
}


def _check() -> None:
    """Pure in-memory calls may omit cooperative execution control."""


def _cap(actual: int, maximum: int) -> None:
    if actual > maximum:
        raise ValueError("diagram_limit_exceeded")


def _key(entity: SourceEntity) -> tuple[int, bytes]:
    priority = {
        Kind.APPLICATION: 0,
        Kind.FRONTEND_APPLICATION: 1,
        Kind.SERVICE: 2,
        Kind.WORKER: 3,
    }
    return (
        priority.get(
            entity.kind,
            4 if entity.kind in PERSISTENCE else 5 if entity.kind in EXTERNAL else 6,
        ),
        entity.record.logical_id.encode("utf-8"),
    )


def _scc(
    vertices: Iterable[str],
    edges: Iterable[tuple[str, str]],
    check: Callable[[], None],
) -> tuple[tuple[str, ...], ...]:
    """Iterative Kosaraju; no recursion limit or repository-global cycle claim."""
    forward: dict[str, list[str]] = {key: [] for key in vertices}
    reverse: dict[str, list[str]] = {key: [] for key in forward}
    for a, b in edges:
        if a in forward and b in forward:
            forward[a].append(b)
            reverse[b].append(a)
    for table in (forward, reverse):
        for values in table.values():
            values.sort(key=lambda value: value.encode("utf-8"))
    seen, order = set(), []
    for root in sorted(forward):
        if root in seen:
            continue
        seen.add(root)
        stack: list[tuple[str, Iterator[str]]] = [(root, iter(forward[root]))]
        while stack:
            check()
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                stack.pop()
                order.append(node)
                continue
            if child not in seen:
                seen.add(child)
                stack.append((child, iter(forward[child])))
    seen.clear()
    result = []
    for root in reversed(order):
        if root in seen:
            continue
        pending, component = [root], []
        seen.add(root)
        while pending:
            check()
            node = pending.pop()
            component.append(node)
            for child in reverse[node]:
                if child not in seen:
                    seen.add(child)
                    pending.append(child)
        result.append(tuple(sorted(component)))
    return tuple(sorted(result))


@dataclass(frozen=True, slots=True)
class BuiltDiagram:
    spec: DiagramSpec
    catalog: MembershipCatalog


class _Build:
    def __init__(
        self,
        data: DiagramInput,
        template: Template,
        limits: DiagramLimits,
        request: DiagramViewRequest | None,
        check: Callable[[], None],
    ) -> None:
        self.check, self.limits, self.template = check, limits, template
        self.data = DiagramInput.model_validate(data)
        self.request = (
            DiagramViewRequest.model_validate(request)
            if request
            else DiagramViewRequest(
                root_ids=(),
                entity_kinds=(),
                statuses=(),
                relationship_kinds=(),
                include_contains=False,
                depth=limits.max_depth,
                direction="outgoing",
                collapsed_group_ids=(),
                selected_entity_ids=(),
            )
        )
        r = self.request
        # Collapse is a later derived-layout operation, never silently ignored.
        if r.collapsed_group_ids:
            raise ValueError("diagram_input_invalid")
        if self.template != Template.DEPENDENCY and r.direction != "outgoing":
            raise ValueError("diagram_input_invalid")
        if self.template == Template.DATA_FLOW and r.include_contains:
            raise ValueError("diagram_input_invalid")
        if Rel.CONTAINS in r.relationship_kinds and not r.include_contains:
            raise ValueError("diagram_input_invalid")
        _cap(len(r.root_ids), limits.max_focus_roots)
        _cap(len(r.selected_entity_ids), limits.max_selected_ids)
        _cap(r.depth, limits.max_depth)
        self.entities = {e.record.logical_id: e for e in data.entities}
        self.by_id = {e.record.id: e.record.logical_id for e in data.entities}
        if len(self.entities) != len(data.entities) or len(self.by_id) != len(
            data.entities
        ):
            raise ValueError("diagram_integrity_error")
        self.relations = {e.record.logical_id: e for e in data.relationships}
        if len(self.relations) != len(data.relationships) or len(
            {e.record.id for e in data.relationships}
        ) != len(data.relationships):
            raise ValueError("diagram_integrity_error")
        self.required: set[str] = set()
        for identity in (*r.root_ids, *r.selected_entity_ids):
            if identity not in self.by_id:
                raise ValueError("diagram_input_invalid")
            self.required.add(self.by_id[identity])
        if len(set(r.root_ids)) != len(r.root_ids) or len(
            set(r.selected_entity_ids)
        ) != len(r.selected_entity_ids):
            raise ValueError("diagram_input_invalid")
        self.parents: dict[str, set[str]] = defaultdict(set)
        self.children: dict[str, set[str]] = defaultdict(set)
        self.contains = []
        for edge in data.relationships:
            check()
            if (
                edge.source_logical_id not in self.entities
                or edge.target_logical_id not in self.entities
            ):
                raise ValueError("diagram_integrity_error")
            if edge.kind == Rel.CONTAINS:
                a, b = edge.source_logical_id, edge.target_logical_id
                self.parents[b].add(a)
                self.children[a].add(b)
                self.contains.append((a, b))
        components = _scc(self.entities, self.contains, check)
        contains_pairs = set(self.contains)
        self.cycles = tuple(
            c for c in components if len(c) > 1 or (c[0], c[0]) in contains_pairs
        )
        self.cyclic = {key for cycle in self.cycles for key in cycle}
        self.owners = self._owners(components)
        rules = template_rules(template)
        allowed = set(rules.default_relationships)
        if r.relationship_kinds:
            if not set(r.relationship_kinds) <= allowed | set(
                rules.optional_relationships
            ) | {Rel.CONTAINS}:
                raise ValueError("diagram_input_invalid")
            allowed &= set(r.relationship_kinds)
            allowed |= set(r.relationship_kinds) & set(rules.optional_relationships)
        if r.include_contains:
            allowed.add(Rel.CONTAINS)
        else:
            allowed.discard(Rel.CONTAINS)
        self.allowed = allowed
        self.eligible = self._eligible()
        if not self.required <= self.eligible:
            raise ValueError("diagram_input_invalid")
        self.omitted: dict[tuple[str, UUID], OmittedRecord] = {}
        self.selected = self._select()
        self.profile = SemanticProfile(
            template_version="1.0.0",
            builder_version="1.0.0",
            selection_version="1.0.0",
            identity_version="1.0.0",
            fingerprint=rules.fingerprint(limits.semantic_selection_policy()),
        )
        seed = dict(
            root_ids=self.refs(self.by_id[x] for x in r.root_ids),
            entity_kinds=r.entity_kinds,
            statuses=r.statuses,
            relationship_kinds=r.relationship_kinds,
            include_contains=r.include_contains,
            depth=r.depth,
            selected_entity_ids=self.refs(self.by_id[x] for x in r.selected_entity_ids),
        )
        if template == Template.OVERVIEW:
            seed.update(
                layers=(
                    "applications",
                    "interfaces",
                    "processing",
                    "persistence",
                    "external",
                ),
                boundary_ids=(),
            )
        elif template == Template.COMPONENT:
            seed.update(multi_parent=(), containment_cycles=())
        elif template == Template.DEPENDENCY:
            seed.update(direction=r.direction, sccs=(), scc_scope="selected_view")
        else:
            seed.update(
                semantics="static_interactions",
                connectivity_overlay=Rel.CONNECTS_TO in allowed,
                no_flow_reason=None,
            )
        self.seed = seed
        self.diagram_id = visual_id(
            "id", (data.scope, template, self.profile.fingerprint, normalize_sets(seed))
        )

    def refs(self, keys: Iterable[str]) -> tuple[EntityRef, ...]:
        return tuple(
            sorted((self.entities[k].record for k in keys), key=lambda x: str(x.id))
        )

    def _owners(self, components: tuple[tuple[str, ...], ...]) -> dict[str, str | None]:
        """Containment condensation; at most two owners suffice to flag ambiguity."""
        index = {key: i for i, part in enumerate(components) for key in part}
        incoming: dict[int, set[int]] = {i: set() for i in range(len(components))}
        outgoing: dict[int, set[int]] = {i: set() for i in incoming}
        for a, b in self.contains:
            if index[a] != index[b]:
                incoming[index[b]].add(index[a])
                outgoing[index[a]].add(index[b])
        degree = {i: len(values) for i, values in incoming.items()}
        queue = deque(sorted(i for i in degree if not degree[i]))
        owners: dict[int, set[str]] = {i: set() for i in incoming}
        uncertain: set[int] = set()
        result: dict[str, str | None] = {}
        while queue:
            self.check()
            i = queue.popleft()
            own = {key for key in components[i] if self.entities[key].kind in APPS}
            if own:
                owners[i] = own
                uncertain.discard(i)
            if any(key in self.cyclic for key in components[i]):
                uncertain.add(i)
            known = owners[i]
            owner = (
                next(iter(known)) if len(known) == 1 and i not in uncertain else None
            )
            for key in components[i]:
                result[key] = owner
            for child in sorted(outgoing[i]):
                if i in uncertain:
                    uncertain.add(child)
                owners[child] = set(sorted(owners[child] | known)[:2])
                degree[child] -= 1
                if degree[child] == 0:
                    queue.append(child)
        return result

    def _eligible(self) -> set[str]:
        rules = template_rules(self.template)
        core = {k for k, e in self.entities.items() if e.kind in rules.default_kinds}
        interactions = [
            e
            for e in self.data.relationships
            if e.kind in self.allowed and e.kind != Rel.CONTAINS
        ]
        if self.template == Template.OVERVIEW:
            for edge in interactions:
                a, b = edge.source_logical_id, edge.target_logical_id
                for key in (a, b):
                    boundary = (
                        edge.kind in (Rel.EXPOSES, Rel.ROUTES_TO)
                        or self.owners[key] is None
                        or (
                            self.owners[a] is not None
                            and self.owners[b] is not None
                            and self.owners[a] != self.owners[b]
                        )
                    )
                    if boundary and self.entities[key].kind in rules.conditional_kinds:
                        core.add(key)
            # Explicit application focus may show canonical internals, without
            # asserting that every frontend component is an overview boundary.
            focused = {self.by_id[x] for x in self.request.root_ids}
            core |= {
                k
                for k, owner in self.owners.items()
                if owner in focused and self.entities[k].kind in rules.conditional_kinds
            }
        elif self.template == Template.COMPONENT:
            internal = set(core)
            for edge in interactions:
                for a, b in (
                    (edge.source_logical_id, edge.target_logical_id),
                    (edge.target_logical_id, edge.source_logical_id),
                ):
                    if (
                        a in internal
                        and self.entities[b].kind in rules.conditional_kinds
                    ):
                        core.add(b)
        elif self.template == Template.DEPENDENCY:
            participants = {
                k
                for e in interactions
                for k in (e.source_logical_id, e.target_logical_id)
            }
            core &= participants
            if self.request.include_contains:
                core |= {k for a, b in self.contains for k in (a, b)}
            if not self.required and not self.request.entity_kinds:
                core = {k for k in core if self.entities[k].kind not in DETAIL}
            core |= self.required
        else:
            core &= {
                k
                for e in interactions
                for k in (e.source_logical_id, e.target_logical_id)
            }
            core |= self.required
        if self.request.entity_kinds:
            core = {
                k for k in core if self.entities[k].kind in self.request.entity_kinds
            }
        if self.request.statuses:
            core = {k for k in core if self.entities[k].status in self.request.statuses}
        return core

    def omit(self, ref: Ref, reason: OmissionReason) -> None:
        self.omitted[(ref.record_type, ref.id)] = OmittedRecord(
            record=ref, reason=reason
        )
        _cap(len(self.omitted), self.limits.max_retained_records)

    def _select(self) -> set[str]:
        r = self.request
        adjacency: dict[str, set[str]] = defaultdict(set)
        if self.template == Template.DEPENDENCY:
            for edge in self.data.relationships:
                if edge.kind not in self.allowed or edge.kind == Rel.CONTAINS:
                    continue
                a, b = edge.source_logical_id, edge.target_logical_id
                if r.direction in ("outgoing", "both"):
                    adjacency[a].add(b)
                if r.direction in ("incoming", "both"):
                    adjacency[b].add(a)
        else:
            adjacency.update(
                {key: set(values) for key, values in self.children.items()}
            )
            if self.template == Template.DATA_FLOW:
                for edge in self.data.relationships:
                    if edge.kind in self.allowed and edge.kind != Rel.CONTAINS:
                        adjacency[edge.source_logical_id].add(edge.target_logical_id)
                        adjacency[edge.target_logical_id].add(edge.source_logical_id)
        seeds = self.required or (
            set(self.eligible)
            if self.template == Template.DEPENDENCY
            else {key for key in self.entities if not self.parents[key]}
        )
        if not self.required:
            seeds |= self.cyclic & self.eligible
        queue = deque(
            (key, 0) for key in sorted(seeds, key=lambda k: _key(self.entities[k]))
        )
        selected: set[str] = set()
        seen: set[str] = set()
        _cap(len(self.required), self.limits.max_nodes)
        while queue:
            self.check()
            key, depth = queue.popleft()
            if key in seen:
                continue
            seen.add(key)
            if key in self.eligible:
                if len(selected) >= self.limits.max_nodes:
                    self.omit(self.entities[key].record, "scene_budget")
                    continue
                selected.add(key)
            children = sorted(
                adjacency[key]
                & (
                    self.eligible
                    if self.template == Template.DEPENDENCY
                    else self.entities.keys()
                ),
                key=lambda k: self.entities[k].record.logical_id.encode(),
            )
            if depth < r.depth:
                queue.extend(
                    (child, depth + 1) for child in children[: self.limits.max_fanout]
                )
        if not self.required <= selected:
            raise ValueError("diagram_limit_exceeded")
        if self.required and self.template in (Template.COMPONENT, Template.OVERVIEW):
            # Real referenced boundary stubs are not containment descendants.
            # Add only direct connections from the chosen canonical slice.
            linked = set()
            for edge in self.data.relationships:
                if edge.kind not in self.allowed or edge.kind == Rel.CONTAINS:
                    continue
                for a, b in (
                    (edge.source_logical_id, edge.target_logical_id),
                    (edge.target_logical_id, edge.source_logical_id),
                ):
                    if a in selected and b in self.eligible:
                        if (
                            self.template == Template.OVERVIEW
                            or self.entities[b].kind
                            in template_rules(self.template).conditional_kinds
                            or self.owners[a] != self.owners[b]
                        ):
                            linked.add(b)
            for key in sorted(linked - selected, key=lambda k: _key(self.entities[k])):
                if len(selected) < self.limits.max_nodes:
                    selected.add(key)
        # Disconnected eligible records are roots only in default views. Cyclic
        # dependency components may have canonical parents outside this view.
        for key, entity in self.entities.items():
            if key not in selected:
                self.omit(
                    entity.record,
                    (
                        (
                            "filter"
                            if self.request.entity_kinds or self.request.statuses
                            else "granularity"
                        )
                        if key not in self.eligible
                        else (
                            "scene_budget"
                            if len(selected) >= self.limits.max_nodes
                            else "depth"
                        )
                    ),
                )
        return selected

    def finish(self) -> BuiltDiagram:
        self.check()
        groups, memberships, node_groups, mapped, cycles = self._groups()
        wanted: set[str] = set()
        annotations: list[Annotation] = []

        def evidence(keys: Iterable[str]) -> tuple[EvidenceRef, ...]:
            refs = []
            for key in sorted(set(keys)):
                if key not in evidence_by_key:
                    raise ValueError("diagram_integrity_error")
                wanted.add(key)
                refs.append(evidence_by_key[key].record)
            return tuple(refs)

        evidence_by_key = {p.record.logical_id: p for p in self.data.evidence}
        if len(evidence_by_key) != len(self.data.evidence) or len(
            {p.record.id for p in self.data.evidence}
        ) != len(self.data.evidence):
            raise ValueError("diagram_integrity_error")
        nodes = []
        for key in sorted(self.selected):
            self.check()
            entity = self.entities[key]
            if key in self.selected:
                nodes.append(
                    DiagramNode(
                        id=mapped[key],
                        entity=entity.record,
                        kind=entity.kind,
                        name=entity.name,
                        namespace=entity.namespace,
                        status=entity.status,
                        evidence=evidence(entity.evidence_ids),
                        group_id=node_groups.get(key),
                        category=_category(entity.kind),
                    )
                )
        edges: list[DiagramEdge] = []
        represented: set[str] = set()
        for a, b, relations in self.relationship_groups(mapped):
            self.check()
            members = tuple(
                RelationshipMember(
                    relationship=e.record,
                    kind=e.kind,
                    source=self.entities[e.source_logical_id].record,
                    target=self.entities[e.target_logical_id].record,
                    status=e.status,
                    evidence=evidence(e.evidence_ids),
                )
                for e in relations
            )
            edges.append(
                DiagramEdge(
                    id=visual_id(
                        "edge",
                        (self.diagram_id, tuple(m.relationship for m in members), a, b),
                    ),
                    source_visual_id=a,
                    target_visual_id=b,
                    members=members,
                    label=LABELS[relations[0].kind],
                    bundle=len(members) > 1,
                )
            )
            represented.update(e.record.logical_id for e in relations)
        for cycle in self.cycles:
            annotations.append(
                Annotation(
                    kind="containment_cycle",
                    subject_ids=tuple(
                        sorted({mapped[k] for k in cycle if k in mapped})
                    ),
                    records=self.refs(cycle),
                    evidence=(),
                    reason="canonical containment cycle",
                    count=len(cycle),
                )
            )
        multi = []
        groups_by_id = {group.id: group for group in groups}
        for child in sorted(self.selected):
            parents = self.parents[child]
            if len(parents) > 1:
                layout_group = groups_by_id.get(node_groups.get(child, ""))
                if (
                    layout_group is not None
                    and layout_group.container == self.entities[child].record
                ):
                    layout_group = groups_by_id.get(layout_group.parent_group_id or "")
                chosen = (
                    layout_group.container.logical_id
                    if layout_group is not None
                    and layout_group.container is not None
                    and layout_group.container.logical_id in parents
                    and child not in self.cyclic
                    else None
                )
                multi.append(
                    MultipleParents(
                        child=self.entities[child].record,
                        parents=self.refs(parents),
                        layout_parent=self.entities[chosen].record if chosen else None,
                    )
                )
                annotations.append(
                    Annotation(
                        kind="multiple_parents",
                        subject_ids=(mapped[child],),
                        records=self.refs(parents),
                        evidence=(),
                        reason="layout parent does not resolve canonical ownership",
                        count=len(parents),
                    )
                )
        uncertainty: dict[tuple[str, str], list[SourceUnresolved | SourceConflict]] = (
            defaultdict(list)
        )
        for item in self.data.unresolved:
            uncertainty[("unresolved", item.reason)].append(item)
        for conflict in self.data.conflicts:
            uncertainty[("conflict", conflict.conflict_type)].append(conflict)
        for (kind, reason), items in sorted(uncertainty.items()):
            self.check()
            annotations.append(
                Annotation(
                    kind=cast(Literal["unresolved", "conflict"], kind),
                    subject_ids=(),
                    records=tuple(
                        sorted((item.record for item in items), key=lambda x: str(x.id))
                    ),
                    evidence=evidence(k for item in items for k in item.evidence_ids),
                    reason=reason,
                    count=len(items),
                )
            )
        if self.template == Template.OVERVIEW:
            ambiguous = [
                k for k in self.selected if self.owners[k] is None and self.parents[k]
            ]
            if ambiguous:
                annotations.append(
                    Annotation(
                        kind="label_limitation",
                        subject_ids=tuple(sorted({mapped[k] for k in ambiguous})),
                        records=self.refs(ambiguous),
                        evidence=(),
                        reason="no unambiguous canonical application owner",
                        count=len(ambiguous),
                    )
                )
        if self.group_omissions:
            annotations.append(
                Annotation(
                    kind="label_limitation",
                    subject_ids=(),
                    records=tuple(
                        sorted(set(self.group_omissions), key=lambda ref: str(ref.id))
                    ),
                    evidence=(),
                    reason="presentation grouping budget; canonical nodes retained",
                    count=self.group_omission_count,
                )
            )
        _cap(len(annotations), 10000)
        view_data = dict(self.seed, template=self.template)
        if self.template == Template.OVERVIEW:
            view_data["boundary_ids"] = self.refs(
                k
                for k in self.selected
                if self.entities[k].kind
                in template_rules(self.template).conditional_kinds
            )
            view: ViewDefinition = OverviewView.model_validate(view_data)
        elif self.template == Template.COMPONENT:
            view_data.update(
                multi_parent=tuple(multi),
                containment_cycles=tuple(self.refs(c) for c in self.cycles),
            )
            view = ComponentView.model_validate(view_data)
        elif self.template == Template.DEPENDENCY:
            view_data["sccs"] = tuple(self.refs(c) for c in cycles)
            view = DependencyView.model_validate(view_data)
        else:
            view_data["no_flow_reason"] = (
                None
                if any(
                    m.kind != Rel.CONNECTS_TO for edge in edges for m in edge.members
                )
                else (
                    "insufficient_evidence"
                    if self.data.completeness.is_partial
                    else "no_established_data_flow"
                )
            )
            view = DataFlowView.model_validate(view_data)
        catalog = MembershipCatalog(
            membership_schema_version="1.0.0",
            diagram_id=self.diagram_id,
            groups=tuple(memberships),
            omitted=tuple(
                sorted(
                    self.omitted.values(),
                    key=lambda o: (o.record.record_type, str(o.record.id)),
                )
            ),
        )
        # Catalog references preserve hidden facts; they must not inflate the
        # visible representation counts or conceal depth/scene omissions.
        counts = self._counts(self.selected, represented, wanted, len(groups))
        reason_set: set[OmissionReason] = {o.reason for o in catalog.omitted}
        if self.group_omissions:
            reason_set.add("scene_budget")
        reasons = tuple(sorted(reason_set))
        bounded = any(
            reason in reasons for reason in ("scene_budget", "depth", "collapsed")
        )
        partial = self.data.completeness.is_partial
        coverage = Coverage(
            view_state=(
                "empty_view"
                if not nodes and not groups
                else (
                    "partial_view"
                    if partial
                    else "bounded_view" if bounded else "complete_view"
                )
            ),
            source_partial=partial,
            selection_bounded=bounded,
            scan_exhausted=True,
            source_completeness=self.data.completeness,
            counts=counts,
            reasons=reasons,
        )
        payload = dict(
            diagram_schema_version="1.0.0",
            scope=self.data.scope,
            template=self.template,
            profile=self.profile,
            diagram_id=self.diagram_id,
            view=view,
            nodes=tuple(nodes),
            edges=tuple(edges),
            groups=tuple(groups),
            annotations=tuple(annotations),
            provenance=tuple(evidence_by_key[k] for k in sorted(wanted)),
            membership_digest=hashlib.sha256(catalog.to_bytes()).hexdigest(),
            coverage=coverage,
            legend=(
                LegendItem(
                    key="static",
                    label="Static interaction view—not observed traffic",
                    meaning=(
                        "Arrows preserve canonical source-to-target directions; "
                        "inference and conflicts are not runtime observations."
                    ),
                ),
            ),
        )
        payload["semantic_digest"] = digest("ss.diagram.semantic", payload)
        spec = DiagramSpec.model_validate(payload)
        self.check()
        DiagramValidator(self.limits).semantic(spec, catalog, source=self.data)
        self.check()
        return BuiltDiagram(spec, catalog)

    def _groups(
        self,
    ) -> tuple[
        list[DiagramGroup],
        list[GroupMembership],
        dict[str, str],
        dict[str, str],
        tuple[tuple[str, ...], ...],
    ]:
        selected = self.selected
        mapped = {
            key: visual_id("node", (self.diagram_id, self.entities[key].record))
            for key in selected
        }
        groups: list[DiagramGroup] = []
        memberships: list[GroupMembership] = []
        node_groups: dict[str, str] = {}
        cycles: tuple[tuple[str, ...], ...] = ()
        candidates: list[tuple[str, str | None, tuple[str, ...]]] = []
        self.group_omissions: list[EntityRef] = []
        self.group_omission_count = 0
        candidate_members = 0
        if self.template == Template.DEPENDENCY:
            pairs = [
                (e.source_logical_id, e.target_logical_id)
                for _, _, edges in self.relationship_groups(mapped)
                for e in edges
                if e.kind != Rel.CONTAINS
            ]
            loops = set(pairs)
            cycles = tuple(
                c
                for c in _scc(selected, pairs, self.check)
                if len(c) > 1 or (c[0], c[0]) in loops
            )
            candidates = [("selected_scc", None, c) for c in cycles]
        elif self.template in (
            Template.COMPONENT,
            Template.OVERVIEW,
            Template.DATA_FLOW,
        ):
            for key in sorted(selected, key=lambda key: _key(self.entities[key])):
                if key in self.cyclic:
                    continue
                if (
                    self.template != Template.COMPONENT
                    and self.entities[key].kind not in APPS
                ):
                    continue
                if not self.children[key]:
                    continue
                if len(candidates) >= self.limits.max_groups:
                    self.group_omissions.append(self.entities[key].record)
                    self.group_omission_count += 1
                    continue
                members = {key}
                queue = deque([key])
                while queue:
                    self.check()
                    parent = queue.popleft()
                    for child in sorted(self.children[parent]):
                        if child in members or child in self.cyclic:
                            continue
                        actual_parents = self.parents[child]
                        chosen = min(actual_parents) if actual_parents else None
                        if self.template == Template.OVERVIEW:
                            chosen = parent if self.owners[child] == key else None
                        if chosen == parent:
                            members.add(child)
                            queue.append(child)
                if len(members & selected) > 1:
                    member_keys = tuple(sorted(members & self.eligible))
                    if (
                        candidate_members + len(member_keys)
                        > self.limits.max_group_members
                    ):
                        self.group_omissions.append(self.entities[key].record)
                        self.group_omission_count += 1
                        continue
                    candidate_members += len(member_keys)
                    candidates.append(
                        (
                            "canonical_container",
                            key,
                            member_keys,
                        )
                    )
        group_for: dict[str, str] = {}
        for kind, container, member_keys in candidates:
            self.check()
            if (
                len(groups) >= self.limits.max_groups
                or sum(len(g.members) for g in memberships) + len(member_keys)
                > self.limits.max_group_members
            ):
                self.group_omissions.extend(
                    self.refs((container,) if container else member_keys)
                )
                self.group_omission_count += 1
                continue
            refs = self.refs(member_keys)
            ref = self.entities[container].record if container else None
            rule = (
                "canonical_contains_v1" if container else "selected_dependency_scc_v1"
            )
            identity = visual_id("group", (self.diagram_id, kind, rule, ref, refs))
            groups.append(
                DiagramGroup(
                    id=identity,
                    kind=cast(Literal["canonical_container", "selected_scc"], kind),
                    label=(
                        self.entities[container].name
                        if container
                        else "Cycle in selected view"
                    ),
                    container=ref,
                    parent_group_id=None,
                    visible_member_ids=(),
                    membership_count=len(refs),
                    collapsed_default=False,
                    rule=rule,
                )
            )
            memberships.append(GroupMembership(group_id=identity, members=refs))
            if container:
                group_for[container] = identity
            else:
                for key in member_keys:
                    node_groups[key] = identity
        if self.template != Template.DEPENDENCY:
            for key in selected:
                current = key
                visited = {key}
                while self.parents[current] and current not in self.cyclic:
                    parent = min(self.parents[current])
                    if parent in visited:
                        break
                    visited.add(parent)
                    if parent in group_for:
                        if (
                            self.template != Template.OVERVIEW
                            or self.owners[key] == parent
                        ):
                            node_groups[key] = group_for[parent]
                            break
                    current = parent
            for membership in memberships:
                # Hidden canonical members can map to a real container only;
                # represented edges retain the underlying actual endpoints.
                for ref in membership.members:
                    if ref.logical_id not in mapped:
                        mapped[ref.logical_id] = membership.group_id
        group_parents = {key: node_groups.get(key) for key in group_for}
        node_groups.update(group_for)
        for i, group in enumerate(groups):
            container = group.container.logical_id if group.container else None
            parent_group = group_parents.get(container) if container else None
            visible = {
                mapped[k] for k, owner in node_groups.items() if owner == group.id
            }
            visible.update(
                g.id
                for g in groups
                if g.container is not None
                and group_parents.get(g.container.logical_id) == group.id
            )
            groups[i] = group.model_copy(
                update={
                    "parent_group_id": parent_group,
                    "visible_member_ids": tuple(sorted(visible - {group.id})),
                }
            )
        return groups, memberships, node_groups, mapped, cycles

    def relationship_groups(
        self, mapped: Mapping[str, str]
    ) -> list[tuple[str, str, tuple[SourceRelationship, ...]]]:
        """Select whole homogeneous bundles in canonical kind/endpoint order."""
        bundles: dict[tuple[str, str, str, str], list[SourceRelationship]] = (
            defaultdict(list)
        )
        ordered = sorted(
            self.data.relationships,
            key=lambda e: (
                e.kind,
                e.source_logical_id.encode(),
                e.target_logical_id.encode(),
                e.record.logical_id.encode(),
            ),
        )
        for edge in ordered:
            self.check()
            a, b = mapped.get(edge.source_logical_id), mapped.get(
                edge.target_logical_id
            )
            if edge.kind not in self.allowed:
                self.omit(
                    edge.record,
                    "filter" if self.request.relationship_kinds else "granularity",
                )
            elif a is None or b is None:
                self.omit(
                    edge.record,
                    (
                        "scene_budget"
                        if len(self.selected) >= self.limits.max_nodes
                        else "filter"
                    ),
                )
            elif a == b and edge.source_logical_id != edge.target_logical_id:
                self.omit(edge.record, "collapsed")
            else:
                bundles[(a, b, edge.kind, edge.status)].append(edge)
        groups: list[tuple[str, str, tuple[SourceRelationship, ...]]] = []
        retained = 0
        neighbors: dict[str, set[str]] = defaultdict(set)
        for (a, b, _, _), relations in sorted(
            bundles.items(),
            key=lambda item: (
                item[1][0].kind,
                item[1][0].source_logical_id.encode(),
                item[1][0].target_logical_id.encode(),
                item[0][3],
            ),
        ):
            self.check()
            if (
                len(groups) >= self.limits.max_edges
                or retained + len(relations) > self.limits.max_relationship_members
                or (
                    b not in neighbors[a]
                    and len(neighbors[a]) >= self.limits.max_fanout
                )
            ):
                for edge in relations:
                    self.omit(edge.record, "scene_budget")
                continue
            groups.append(
                (a, b, tuple(sorted(relations, key=lambda e: str(e.record.id))))
            )
            retained += len(relations)
            neighbors[a].add(b)
        return groups

    def _counts(
        self,
        entities: set[str],
        relationships: set[str],
        evidence: set[str],
        group_count: int,
    ) -> tuple[Count, ...]:
        rows = []
        for collection, records, represented in (
            ("entities", self.data.entities, entities),
            ("relationships", self.data.relationships, relationships),
        ):
            kinds = sorted({r.kind.value for r in records})
            for kind in kinds:
                subset = [r for r in records if r.kind.value == kind]
                present = sum(r.record.logical_id in represented for r in subset)
                eligible = (
                    sum(r.record.logical_id in self.eligible for r in subset)
                    if collection == "entities"
                    else sum(r.kind in self.allowed for r in subset)
                )
                eligible = max(eligible, present)
                rows.append(
                    Count(
                        collection=cast(
                            Literal["entities", "relationships"], collection
                        ),
                        kind=kind,
                        scanned=len(subset),
                        eligible=eligible,
                        represented=present,
                        excluded=len(subset) - eligible,
                        omitted=eligible - present,
                    )
                )
        for name, total, represented_count in (
            ("evidence", self.data.evidence_total, len(evidence)),
            ("unresolved", len(self.data.unresolved), len(self.data.unresolved)),
            ("conflicts", len(self.data.conflicts), len(self.data.conflicts)),
            ("groups", group_count + self.group_omission_count, group_count),
        ):
            rows.append(
                Count(
                    collection=cast(
                        Literal["evidence", "unresolved", "conflicts", "groups"], name
                    ),
                    kind=None,
                    scanned=total,
                    eligible=total,
                    represented=represented_count,
                    excluded=0,
                    omitted=total - represented_count,
                )
            )
        return tuple(rows)


def _category(
    kind: Kind,
) -> Literal[
    "application",
    "interface",
    "processing",
    "persistence",
    "external",
    "implementation",
    "unknown",
]:
    if kind in APPS:
        return "application"
    if kind == Kind.ENDPOINT:
        return "interface"
    if kind in PERSISTENCE:
        return "persistence"
    if kind in EXTERNAL:
        return "external"
    if kind in (
        Kind.SERVICE,
        Kind.WORKER,
        Kind.CONTROLLER,
        Kind.COMPONENT,
        Kind.DATA_REPOSITORY,
    ):
        return "processing"
    return "unknown" if kind == Kind.UNKNOWN else "implementation"


class DiagramBuilder:
    template: ClassVar[Template]

    def build(
        self,
        data: DiagramInput,
        limits: DiagramLimits,
        request: DiagramViewRequest | None = None,
        *,
        checkpoint: Callable[[], None] = _check,
    ) -> BuiltDiagram:
        deadline = monotonic() + limits.build_seconds

        def bounded() -> None:
            checkpoint()
            if monotonic() >= deadline:
                raise TimeoutError("diagram_timeout")

        validate_input(data, limits, bounded)
        return _Build(data, self.template, limits, request, bounded).finish()


class SystemOverviewBuilder(DiagramBuilder):
    template = Template.OVERVIEW


class ComponentArchitectureBuilder(DiagramBuilder):
    template = Template.COMPONENT


class DependencyMapBuilder(DiagramBuilder):
    template = Template.DEPENDENCY


class DataFlowBuilder(DiagramBuilder):
    template = Template.DATA_FLOW


BUILDERS: Mapping[Template, DiagramBuilder] = MappingProxyType(
    {
        Template.OVERVIEW: SystemOverviewBuilder(),
        Template.COMPONENT: ComponentArchitectureBuilder(),
        Template.DEPENDENCY: DependencyMapBuilder(),
        Template.DATA_FLOW: DataFlowBuilder(),
    }
)


def validate_input(
    data: DiagramInput, limits: DiagramLimits, check: Callable[[], None]
) -> None:
    DiagramInput.model_validate(data)
    total_bytes = 0
    rows: tuple[SourceRecord, ...] = (
        *data.entities,
        *data.relationships,
        *data.unresolved,
        *data.conflicts,
        *data.evidence,
    )
    _cap(len(rows), limits.max_retained_records)
    ids: set[tuple[str, UUID]] = set()
    logical_ids: set[tuple[str, str]] = set()
    for row in rows:
        check()
        if isinstance(
            row, (SourceEntity, SourceRelationship, SourceUnresolved, SourceConflict)
        ):
            if len(set(row.evidence_ids)) != len(row.evidence_ids):
                raise ValueError("diagram_integrity_error")
        if isinstance(row, SourceUnresolved) and row.record.record_type != "unresolved":
            raise ValueError("diagram_integrity_error")
        if isinstance(row, SourceConflict) and row.record.record_type != "conflict":
            raise ValueError("diagram_integrity_error")
        identity = (row.record.record_type, row.record.id)
        logical = (row.record.record_type, row.record.logical_id)
        if identity in ids or logical in logical_ids:
            raise ValueError("diagram_integrity_error")
        ids.add(identity)
        logical_ids.add(logical)
        total_bytes += len(row.to_bytes())
        _cap(total_bytes, limits.max_retained_bytes)
        _cap(len(row.record.logical_id.encode()), limits.max_logical_id_bytes)
        if isinstance(row, SourceEntity):
            _cap(len(row.name.encode()), limits.max_name_bytes)
            for part in row.namespace:
                _cap(len(part.encode()), limits.max_namespace_component_bytes)
        if isinstance(row, EvidenceProvenance) and row.source_fact_key is not None:
            _cap(len(row.source_fact_key.encode()), limits.max_source_fact_key_bytes)
    if data.evidence_total < len(data.evidence):
        raise ValueError("diagram_integrity_error")
    for actual, expected in (
        (len(data.entities), data.completeness.architecture_entities),
        (len(data.relationships), data.completeness.architecture_relationships),
        (len(data.unresolved), data.completeness.architecture_unresolved_relationships),
        (len(data.conflicts), data.completeness.architecture_conflicts),
    ):
        if actual != expected:
            raise ValueError("diagram_integrity_error")


def build_from_source(
    source: DiagramSourceAdapter,
    scope: CanonicalDiagramScope,
    template: Template,
    budget: SourceBudget,
    request: DiagramViewRequest | None = None,
) -> BuiltDiagram:
    """Bounded public paging → pure builder; no work/attempt/recovery ownership.

    Compact canonical records are read once. Only referenced evidence is retained;
    the complete evidence scan and final header still establish source coverage.
    """
    budget.deadline = min(budget.deadline, monotonic() + budget.limits.build_seconds)
    completeness = source.header(scope, budget)
    values: dict[str, list[SourceRecord]] = {}
    count, size = 0, 0
    for collection in ("entities", "relationships", "unresolved", "conflicts"):
        records: list[SourceRecord] = []
        for row in source.scan(collection, scope, budget):
            count += 1
            size += len(row.to_bytes())
            _cap(count, budget.limits.max_retained_records)
            _cap(size, budget.limits.max_retained_bytes)
            records.append(row)
        values[collection] = records
    data = DiagramInput(
        scope=scope,
        completeness=completeness,
        entities=tuple(cast(list[SourceEntity], values["entities"])),
        relationships=tuple(cast(list[SourceRelationship], values["relationships"])),
        unresolved=tuple(cast(list[SourceUnresolved], values["unresolved"])),
        conflicts=tuple(cast(list[SourceConflict], values["conflicts"])),
        evidence=(),
        evidence_total=0,
    )
    plan = _Build(data, template, budget.limits, request, budget.check)
    # Select first; do not retain evidence for every repository relationship.
    # Both phases use the same pure selection/bundle rules, including caps.
    _, _, _, mapped, _ = plan._groups()
    keys = {
        k
        for e in data.entities
        if e.record.logical_id in plan.selected
        for k in e.evidence_ids
    }
    keys.update(
        k
        for _, _, group in plan.relationship_groups(mapped)
        for e in group
        for k in e.evidence_ids
    )
    for unresolved in data.unresolved:
        keys.update(unresolved.evidence_ids)
    for conflict in data.conflicts:
        keys.update(conflict.evidence_ids)
    evidence = []
    total = 0
    for row in source.scan("evidence", scope, budget):
        total += 1
        if not isinstance(row, EvidenceProvenance):
            raise ValueError("diagram_integrity_error")
        if row.record.logical_id in keys:
            count += 1
            size += len(row.to_bytes())
            _cap(count, budget.limits.max_retained_records)
            _cap(size, budget.limits.max_retained_bytes)
            evidence.append(row)
    if source.header(scope, budget) != completeness:
        raise ValueError("diagram_integrity_error")
    final = data.model_copy(
        update={"evidence": tuple(evidence), "evidence_total": total}
    )
    result = BUILDERS[template].build(
        final, budget.limits, request, checkpoint=budget.check
    )
    if source.header(scope, budget) != completeness:
        raise ValueError("diagram_integrity_error")
    budget.check()
    return result
