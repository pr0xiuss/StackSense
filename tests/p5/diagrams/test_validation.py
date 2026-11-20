import pytest
from pydantic import ValidationError

from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import DiagramSpec, LayoutSpec
from backend.platform.diagrams.model import canonical_bytes, digest
from backend.platform.diagrams.validation import DiagramValidator
from tests.p5.diagrams.conftest import empty_parts


def test_empty_data_flow_is_honest_valid_product():
    spec, catalog, layout = empty_parts()
    validator = DiagramValidator(DiagramLimits())
    validator.semantic(spec, catalog)
    validator.layout(spec, layout)
    assert spec.view.no_flow_reason == "no_established_data_flow"


def test_foreign_catalog_rejected():
    spec, catalog, _ = empty_parts()
    with pytest.raises(ValueError, match="membership"):
        DiagramValidator(DiagramLimits()).semantic(
            spec, catalog.model_copy(update={"diagram_id": "diagram://" + "d" * 64})
        )


def test_layout_digest_cannot_attest_invalid_geometry():
    spec, _, layout = empty_parts()
    payload = layout.model_dump(mode="json", exclude={"layout_digest"})
    payload["bounds"]["width"] = 10
    payload["layout_digest"] = digest("ss.diagram.layout", payload)
    changed = LayoutSpec.model_validate_json(canonical_bytes(payload))
    with pytest.raises(ValueError, match="zero bounds"):
        DiagramValidator(DiagramLimits()).layout(spec, changed)


def test_semantic_model_rejects_mixed_template():
    spec, _, _ = empty_parts()
    payload = spec.model_dump(mode="json")
    payload["template"] = "dependency_map"
    with pytest.raises(ValidationError):
        DiagramSpec.model_validate_json(canonical_bytes(payload))


def test_real_static_edge_direction_cannot_be_reversed():
    from uuid import UUID

    from backend.platform.analysis.architecture.model import (
        ArchitectureEntityKind as Kind,
    )
    from backend.platform.analysis.architecture.model import (
        ArchitectureFactStatus as Status,
    )
    from backend.platform.analysis.architecture.model import (
        ArchitectureRelationshipKind as Rel,
    )
    from backend.platform.diagrams.contracts import (
        DiagramEdge,
        DiagramNode,
        EntityRef,
        RelationshipMember,
        RelationshipRef,
    )
    from backend.platform.diagrams.model import visual_id

    spec, catalog, _ = empty_parts()
    nodes = tuple(
        DiagramNode(
            id=visual_id("node", (spec.diagram_id, ref)),
            entity=ref,
            kind=kind,
            name=name,
            namespace=(),
            status=Status.SUPPORTED,
            evidence=(),
            group_id=None,
            category=category,
        )
        for ref, kind, name, category in (
            (
                EntityRef(
                    record_type="entity", id=UUID(int=101), logical_id="worker:a"
                ),
                Kind.WORKER,
                "Consumer",
                "processing",
            ),
            (
                EntityRef(record_type="entity", id=UUID(int=102), logical_id="queue:b"),
                Kind.QUEUE,
                "Channel",
                "persistence",
            ),
        )
    )
    ref = RelationshipRef(
        record_type="relationship", id=UUID(int=103), logical_id="rel:consumes"
    )
    edge = DiagramEdge(
        id=visual_id("edge", (spec.diagram_id, (ref,), nodes[0].id, nodes[1].id)),
        source_visual_id=nodes[0].id,
        target_visual_id=nodes[1].id,
        members=(
            RelationshipMember(
                relationship=ref,
                kind=Rel.CONSUMES,
                source=nodes[0].entity,
                target=nodes[1].entity,
                status=Status.SUPPORTED,
                evidence=(),
            ),
        ),
        label="consumes from",
        bundle=False,
    )
    payload = spec.model_dump(mode="json", exclude={"semantic_digest"})
    payload.update(
        nodes=[n.model_dump(mode="json") for n in nodes],
        edges=[edge.model_dump(mode="json")],
    )
    payload["coverage"]["view_state"] = "complete_view"
    payload["semantic_digest"] = digest("ss.diagram.semantic", payload)
    spec = DiagramSpec.model_validate_json(canonical_bytes(payload))
    validator = DiagramValidator(DiagramLimits())
    validator.semantic(spec, catalog)
    payload = spec.model_dump(mode="json", exclude={"semantic_digest"})
    payload["edges"][0]["source_visual_id"] = nodes[1].id
    payload["edges"][0]["target_visual_id"] = nodes[0].id
    payload["edges"][0]["id"] = visual_id(
        "edge", (spec.diagram_id, (ref,), nodes[1].id, nodes[0].id)
    )
    payload["semantic_digest"] = digest("ss.diagram.semantic", payload)
    changed = DiagramSpec.model_validate_json(canonical_bytes(payload))
    with pytest.raises(ValueError, match="direction mismatch"):
        validator.semantic(changed, catalog)
