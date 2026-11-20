"""Cross-record C2 integrity checks, never canonical inference or repair."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import (
    Box,
    DiagramSpec,
    EntityRef,
    LayoutSpec,
    MembershipCatalog,
)
from backend.platform.diagrams.model import canonical_bytes, visual_id

if TYPE_CHECKING:
    from backend.platform.diagrams.query import DiagramInput, SourceRecord


class DiagramValidator:
    def __init__(self, limits: DiagramLimits) -> None:
        self.limits = limits

    def semantic(
        self,
        spec: DiagramSpec,
        catalog: MembershipCatalog,
        *,
        source: DiagramInput | None = None,
    ) -> None:
        spec = DiagramSpec.model_validate(spec)
        catalog = MembershipCatalog.model_validate(catalog)
        if (
            catalog.diagram_id != spec.diagram_id
            or hashlib.sha256(canonical_bytes(catalog)).hexdigest()
            != spec.membership_digest
        ):
            raise ValueError("diagram membership binding mismatch")
        nodes = {n.id: n for n in spec.nodes}
        groups = {g.id: g for g in spec.groups}
        edges = {e.id: e for e in spec.edges}
        all_ids = (
            tuple(n.id for n in spec.nodes)
            + tuple(g.id for g in spec.groups)
            + tuple(e.id for e in spec.edges)
        )
        if len(set(all_ids)) != len(all_ids):
            raise ValueError("duplicate visual identity")
        self._cap(len(nodes), self.limits.max_nodes)
        self._cap(len(edges), self.limits.max_edges)
        self._cap(len(groups), self.limits.max_groups)
        self._cap(len(canonical_bytes(spec)), self.limits.max_spec_bytes)
        self._cap(len(canonical_bytes(catalog)), self.limits.max_members_bytes)
        self._cap(
            sum(len(e.members) for e in spec.edges),
            self.limits.max_relationship_members,
        )
        self._cap(
            sum(len(g.members) for g in catalog.groups), self.limits.max_group_members
        )
        visual = nodes.keys() | groups.keys()
        if spec.coverage.view_state == "empty_view" and (nodes or groups or edges):
            raise ValueError("empty coverage contains a nonempty scene")
        if len({n.entity.id for n in spec.nodes}) != len(nodes):
            raise ValueError("duplicate canonical entity representation")
        members = {g.group_id: g.members for g in catalog.groups}
        if len(members) != len(catalog.groups) or set(members) != set(groups):
            raise ValueError("catalog group set mismatch")
        represented_relationships: set[str] = set()
        provenance = {p.record.logical_id: p.record for p in spec.provenance}
        if len(provenance) != len(spec.provenance):
            raise ValueError("duplicate evidence provenance")
        for group in spec.groups:
            if len({r.id for r in members[group.id]}) != len(members[group.id]):
                raise ValueError("duplicate canonical group membership")
            expected_group_id = visual_id(
                "group",
                (
                    spec.diagram_id,
                    group.kind,
                    group.rule,
                    group.container,
                    tuple(
                        sorted(
                            members[group.id], key=lambda r: str(r.id).encode("utf-8")
                        )
                    ),
                ),
            )
            if group.id != expected_group_id:
                raise ValueError("group identity mismatch")
            if len(set(group.visible_member_ids)) != len(group.visible_member_ids):
                raise ValueError("duplicate group member")
            if (
                not set(group.visible_member_ids) <= visual
                or group.id in group.visible_member_ids
            ):
                raise ValueError("invalid visible membership")
            if group.membership_count != len(members[group.id]):
                raise ValueError("group membership count mismatch")
            if group.container is not None and group.container not in members[group.id]:
                raise ValueError("container absent from group membership")
            for child in group.visible_member_ids:
                if child in nodes and nodes[child].group_id != group.id:
                    raise ValueError("visible node parent mismatch")
                if child in groups and groups[child].parent_group_id != group.id:
                    raise ValueError("visible group parent mismatch")
            chain = {group.id}
            parent = group.parent_group_id
            while parent is not None:
                if parent not in groups or parent in chain:
                    raise ValueError("invalid/cyclic layout parent")
                chain.add(parent)
                parent = groups[parent].parent_group_id
        for node in spec.nodes:
            if node.id != visual_id("node", (spec.diagram_id, node.entity)):
                raise ValueError("node identity mismatch")
            if node.group_id is not None and node.group_id not in groups:
                raise ValueError("missing node group")
            if node.group_id is not None and (
                node.entity not in members[node.group_id]
                or node.id not in groups[node.group_id].visible_member_ids
            ):
                raise ValueError("node group membership mismatch")
            for ref in node.evidence:
                if provenance.get(ref.logical_id) != ref:
                    raise ValueError("missing/foreign node evidence")
        for edge in spec.edges:
            expected_edge_id = visual_id(
                "edge",
                (
                    spec.diagram_id,
                    tuple(
                        sorted(
                            (m.relationship for m in edge.members),
                            key=lambda r: str(r.id).encode("utf-8"),
                        )
                    ),
                    edge.source_visual_id,
                    edge.target_visual_id,
                ),
            )
            if edge.id != expected_edge_id:
                raise ValueError("edge identity mismatch")
            if (
                edge.source_visual_id not in visual
                or edge.target_visual_id not in visual
            ):
                raise ValueError("missing edge visual endpoint")
            for member in edge.members:
                if member.relationship.logical_id in represented_relationships:
                    raise ValueError("duplicate represented relationship")
                represented_relationships.add(member.relationship.logical_id)
                for endpoint, entity_ref in (
                    (edge.source_visual_id, member.source),
                    (edge.target_visual_id, member.target),
                ):
                    allowed = (
                        (nodes[endpoint].entity,)
                        if endpoint in nodes
                        else members[endpoint]
                    )
                    if entity_ref not in allowed:
                        raise ValueError("edge endpoint/direction mismatch")
                for ref in member.evidence:
                    if provenance.get(ref.logical_id) != ref:
                        raise ValueError("missing/foreign relationship evidence")
        for annotation in spec.annotations:
            if not set(annotation.subject_ids) <= visual:
                raise ValueError("missing annotation subject")
            for ref in annotation.evidence:
                if provenance.get(ref.logical_id) != ref:
                    raise ValueError("missing/foreign annotation evidence")
        if source is not None:
            self._canonical(spec, catalog, source)

    @staticmethod
    def _canonical(
        spec: DiagramSpec, catalog: MembershipCatalog, source: DiagramInput
    ) -> None:
        """Verify exact public records, not just syntactically valid UUIDs."""
        if source.scope != spec.scope:
            raise ValueError("diagram_scope_mismatch")
        entities = {row.record.logical_id: row for row in source.entities}
        relationships = {row.record.logical_id: row for row in source.relationships}
        evidence = {row.record.logical_id: row for row in source.evidence}

        def entity(ref: EntityRef) -> None:
            row = entities.get(ref.logical_id)
            if row is None or row.record != ref:
                raise ValueError("foreign canonical entity")

        for node in spec.nodes:
            original = entities.get(node.entity.logical_id)
            if original is None or (
                original.record != node.entity
                or original.kind != node.kind
                or original.status != node.status
                or original.name != node.name
                or original.namespace != node.namespace
                or set(original.evidence_ids) != {r.logical_id for r in node.evidence}
            ):
                raise ValueError("canonical node mismatch")
        for group in spec.groups:
            if group.container is not None:
                entity(group.container)
        for group_membership in catalog.groups:
            for ref in group_membership.members:
                entity(ref)
        for edge in spec.edges:
            for member in edge.members:
                original_edge = relationships.get(member.relationship.logical_id)
                if original_edge is None or (
                    original_edge.record != member.relationship
                    or original_edge.kind != member.kind
                    or original_edge.status != member.status
                    or original_edge.source_logical_id != member.source.logical_id
                    or original_edge.target_logical_id != member.target.logical_id
                    or set(original_edge.evidence_ids)
                    != {r.logical_id for r in member.evidence}
                ):
                    raise ValueError("canonical relationship mismatch")
                entity(member.source)
                entity(member.target)
        for provenance in spec.provenance:
            if evidence.get(provenance.record.logical_id) != provenance:
                raise ValueError("canonical evidence mismatch")
        records: tuple[SourceRecord, ...] = (
            *source.entities,
            *source.relationships,
            *source.evidence,
            *source.unresolved,
            *source.conflicts,
        )
        allowed_refs = {
            (r.record.record_type, r.record.id): r.record.logical_id for r in records
        }
        for annotation_ref in (r for a in spec.annotations for r in a.records):
            if (
                allowed_refs.get((annotation_ref.record_type, annotation_ref.id))
                != annotation_ref.logical_id
            ):
                raise ValueError("foreign annotation record")
        for omitted in catalog.omitted:
            omitted_ref = omitted.record
            if (
                allowed_refs.get((omitted_ref.record_type, omitted_ref.id))
                != omitted_ref.logical_id
            ):
                raise ValueError("foreign omission record")

    def layout(self, spec: DiagramSpec, layout: LayoutSpec) -> None:
        spec = DiagramSpec.model_validate(spec)
        layout = LayoutSpec.model_validate(layout)
        if (layout.diagram_id, layout.semantic_digest) != (
            spec.diagram_id,
            spec.semantic_digest,
        ):
            raise ValueError("layout source mismatch")
        for actual, expected in (
            (tuple(n.id for n in layout.nodes), {n.id for n in spec.nodes}),
            (tuple(g.id for g in layout.groups), {g.id for g in spec.groups}),
            (tuple(e.edge_id for e in layout.routes), {e.id for e in spec.edges}),
        ):
            if len(set(actual)) != len(actual) or set(actual) != expected:
                raise ValueError("layout ID set mismatch")
        self._cap(len(canonical_bytes(layout)), self.limits.max_layout_bytes)
        self._cap(
            sum(len(r.sections) for r in layout.routes), self.limits.max_route_sections
        )
        self._cap(len(layout.glyphs), self.limits.max_glyphs)
        self._cap(
            sum(len(label.glyphs) for label in layout.labels),
            self.limits.max_glyph_placements,
        )
        self._cap(
            sum(len(g.commands) for g in layout.glyphs), self.limits.max_path_commands
        )
        glyphs = {g.id for g in layout.glyphs}
        if len(glyphs) != len(layout.glyphs):
            raise ValueError("duplicate glyph")
        for label in layout.labels:
            if any(p.glyph_id not in glyphs for p in label.glyphs):
                raise ValueError("missing label glyph")
        if len({label.id for label in layout.labels}) != len(layout.labels):
            raise ValueError("duplicate layout label")
        boxes = {item.id: item.box for item in (*layout.nodes, *layout.groups)}
        edge_ids = {edge.id for edge in spec.edges}

        def inside(x: int, y: int, box: Box = layout.bounds) -> bool:
            return box.x <= x <= box.x + box.width and box.y <= y <= box.y + box.height

        for label in layout.labels:
            b = label.box
            if (
                label.owner_id not in boxes.keys() | edge_ids
                or not inside(b.x, b.y)
                or not inside(b.x + b.width, b.y + b.height)
            ):
                raise ValueError("invalid label owner/bounds")
        if len({port.id for port in layout.ports}) != len(layout.ports):
            raise ValueError("duplicate layout port")
        for port in layout.ports:
            if port.owner_id not in boxes or not inside(
                port.point.x, port.point.y, boxes[port.owner_id]
            ):
                raise ValueError("invalid port owner/bounds")
        edges = {edge.id: edge for edge in spec.edges}
        for route in layout.routes:
            edge = edges[route.edge_id]
            if not inside(
                route.sections[0].start.x,
                route.sections[0].start.y,
                boxes[edge.source_visual_id],
            ) or not inside(
                route.sections[-1].end.x,
                route.sections[-1].end.y,
                boxes[edge.target_visual_id],
            ):
                raise ValueError("invalid static edge direction/endpoints")
            if any(
                a.end != b.start
                for a, b in zip(route.sections, route.sections[1:], strict=False)
            ):
                raise ValueError("discontinuous route")
            if any(
                not inside(p.x, p.y)
                for section in route.sections
                for p in (section.start, *section.bends, section.end)
            ):
                raise ValueError("route outside layout bounds")
        for item in (*layout.nodes, *layout.groups):
            b, outer = item.box, layout.bounds
            if (
                b.width <= 0
                or b.height <= 0
                or not (
                    outer.x <= b.x
                    and outer.y <= b.y
                    and b.x + b.width <= outer.x + outer.width
                    and b.y + b.height <= outer.y + outer.height
                )
            ):
                raise ValueError("invalid layout bounds")
        if (
            not spec.nodes
            and not spec.groups
            and layout.bounds.model_dump() != dict(x=0, y=0, width=0, height=0)
        ):
            raise ValueError("empty scene must have zero bounds")

    @staticmethod
    def _cap(actual: int, limit: int) -> None:
        if actual > limit:
            raise ValueError("diagram_limit_exceeded")
