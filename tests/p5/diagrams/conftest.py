"""Public C2 fixtures; no physical seal or accepted publication is implied."""

import hashlib
from uuid import UUID

import pytest

from backend.platform.delivery.contracts import DiagramTemplate
from backend.platform.diagrams.contracts import (
    CanonicalDiagramScope,
    CompletenessSnapshot,
    Coverage,
    DiagramSpec,
    LayoutProfile,
    LayoutSpec,
    MembershipCatalog,
    SemanticProfile,
)
from backend.platform.diagrams.model import canonical_bytes, digest, visual_id


def scope() -> CanonicalDiagramScope:
    return CanonicalDiagramScope(
        project_id=UUID(int=1),
        repository_id=UUID(int=2),
        analysis_id=UUID(int=3),
        snapshot_id=UUID(int=4),
        architecture_version_id=UUID(int=5),
        sequence_number=1,
        canonical_digest="a" * 64,
        architecture_schema_version="1.0.0",
        ir_schema_version="1.0.0",
    )


def completeness() -> CompletenessSnapshot:
    return CompletenessSnapshot.model_validate(
        {
            k: False if k == "is_partial" else 0
            for k in CompletenessSnapshot.model_fields
        }
    )


def empty_parts(
    template: DiagramTemplate = DiagramTemplate.DATA_FLOW,
) -> tuple[DiagramSpec, MembershipCatalog, LayoutSpec]:
    common = dict(
        root_ids=(),
        entity_kinds=(),
        statuses=(),
        relationship_kinds=(),
        include_contains=False,
        depth=4,
        selected_entity_ids=(),
    )
    views = {
        DiagramTemplate.OVERVIEW: dict(layers=(), boundary_ids=()),
        DiagramTemplate.COMPONENT: dict(multi_parent=(), containment_cycles=()),
        DiagramTemplate.DEPENDENCY: dict(
            direction="outgoing", sccs=(), scc_scope="selected_view"
        ),
        DiagramTemplate.DATA_FLOW: dict(
            semantics="static_interactions",
            connectivity_overlay=False,
            no_flow_reason="no_established_data_flow",
        ),
    }
    # Wire parsing also verifies the discriminator/enum JSON boundary.
    profile = SemanticProfile(
        template_version="1.0.0",
        builder_version="1.0.0",
        selection_version="1.0.0",
        identity_version="1.0.0",
        fingerprint="b" * 64,
    )
    diagram_id = visual_id("id", (scope(), template, profile.fingerprint, common))
    catalog = MembershipCatalog(
        membership_schema_version="1.0.0", diagram_id=diagram_id, groups=(), omitted=()
    )
    payload = dict(
        diagram_schema_version="1.0.0",
        scope=scope(),
        template=template,
        profile=profile,
        diagram_id=diagram_id,
        view=dict(template=template, **common, **views[template]),
        nodes=(),
        edges=(),
        groups=(),
        annotations=(),
        provenance=(),
        membership_digest=hashlib.sha256(canonical_bytes(catalog)).hexdigest(),
        coverage=Coverage(
            view_state="empty_view",
            source_partial=False,
            selection_bounded=False,
            scan_exhausted=True,
            source_completeness=completeness(),
            counts=(),
            reasons=(),
        ),
        legend=(),
    )
    payload["semantic_digest"] = digest("ss.diagram.semantic", payload)
    spec = DiagramSpec.model_validate_json(canonical_bytes(payload))
    layout_payload = dict(
        layout_schema_version="1.0.0",
        diagram_id=diagram_id,
        semantic_digest=spec.semantic_digest,
        profile=LayoutProfile(
            id="architecture_compound_v1",
            version="1.0.0",
            engine="elkjs",
            engine_version="0.12.1",
            runtime_version="24.22.3",
            font_profile="dejavu_paths_2_37_v1",
            fingerprint="c" * 64,
        ),
        unit="milli_css_px",
        nodes=(),
        groups=(),
        ports=(),
        labels=(),
        routes=(),
        glyphs=(),
        font_notice="Fixture, not installed font proof",
        bounds=dict(x=0, y=0, width=0, height=0),
        fallback="none",
        limitations=(),
    )
    layout_payload["layout_digest"] = digest("ss.diagram.layout", layout_payload)
    layout = LayoutSpec.model_validate_json(canonical_bytes(layout_payload))
    return spec, catalog, layout


@pytest.fixture
def empty_scene() -> tuple[DiagramSpec, MembershipCatalog, LayoutSpec]:
    return empty_parts()
