"""Exact M5/M6/C0-shaped consumer values, not accepted artifact fixtures."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from backend.platform.delivery.contracts import (
    ArtifactReference,
    HandlerProfile,
    OutputDigests,
    ProducerProfile,
    VersionScope,
    WorkKind,
    WorkSlot,
)
from backend.platform.diagrams.contracts import (
    DiagramArtifactDescriptor,
    DiagramArtifactManifest,
    DiagramViewResponse,
    MemberDescriptor,
    PreparedDiagram,
)
from tests.p5.diagrams.conftest import empty_parts


def prepared(template=None, *, generation_id=None, artifact_id=None):
    spec, catalog, layout = empty_parts() if template is None else empty_parts(template)
    scope = VersionScope(
        **spec.scope.model_dump(),
        published_at=datetime(2026, 11, 19, tzinfo=UTC),
        source_contract_version="1.0.0",
        analyzer_version="1.0.0",
        configuration_fingerprint="source-opaque-fingerprint",
    )
    binding = HandlerProfile(
        slot=WorkSlot(kind=WorkKind.DIAGRAM, template=spec.template),
        profile=ProducerProfile(
            producer_id="stacksense.diagrams",
            producer_version="1.0.0",
            generator_version="1.0.0",
            output_schema_version="1.0.0",
            configuration_fingerprint="d" * 64,
        ),
    )
    data = {
        "spec": spec.to_bytes(),
        "layout": layout.to_bytes(),
        "members": catalog.to_bytes(),
        "svg": b"<svg/>",
    }
    members = tuple(
        MemberDescriptor(
            member=name,
            file_name="scene.svg" if name == "svg" else name + ".json",
            media_type="image/svg+xml" if name == "svg" else "application/json",
            schema_version="1.0.0",
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )
        for name, content in sorted(data.items())
    )
    manifest = DiagramArtifactManifest(
        artifact_schema_version="1.0.0",
        scope=scope,
        binding=binding,
        input_fingerprint="e" * 64,
        diagram_id=spec.diagram_id,
        generation_id=generation_id or UUID(int=10),
        artifact_id=artifact_id or UUID(int=11),
        semantic_digest=spec.semantic_digest,
        layout_digest=layout.layout_digest,
        membership_digest=spec.membership_digest,
        export_profile="svg_paths_v1",
        members=members,
        verification_version="1.0.0",
    )
    reference = ArtifactReference(
        scope=scope,
        binding=binding,
        input_fingerprint=manifest.input_fingerprint,
        resource_id=UUID(int=12),
        candidate_id=UUID(int=13),
        generation_id=manifest.generation_id,
        artifact_id=manifest.artifact_id,
        size_bytes=len(manifest.to_bytes()),
        sealed=True,
        digests=OutputDigests(
            content=hashlib.sha256(manifest.to_bytes()).hexdigest(),
            spec=spec.semantic_digest,
            layout=layout.layout_digest,
        ),
    )
    return PreparedDiagram(
        spec=spec,
        layout=layout,
        descriptor=DiagramArtifactDescriptor(manifest=manifest, reference=reference),
    )


def test_prepared_m5_consumer_roundtrip_requires_no_runtime_or_store():
    value = prepared()
    assert PreparedDiagram.from_bytes(value.to_bytes(), max_bytes=65536) == value
    assert not hasattr(value, "session")


@pytest.mark.parametrize(
    "field,value",
    [
        ("generation_id", UUID(int=99)),
        ("artifact_id", UUID(int=99)),
        ("input_fingerprint", "0" * 64),
        ("size_bytes", 0),
    ],
)
def test_altered_reference_rejected(field, value):
    p = prepared()
    altered = p.descriptor.reference.model_copy(update={field: value})
    with pytest.raises(ValidationError):
        DiagramArtifactDescriptor(manifest=p.descriptor.manifest, reference=altered)


def test_m6_derived_response_does_not_claim_accepted_output():
    p = prepared()
    response = DiagramViewResponse(
        base_generation_id=p.descriptor.reference.generation_id,
        base_semantic_digest=p.spec.semantic_digest,
        request_digest="f" * 64,
        spec=p.spec,
        layout=p.layout,
    )
    assert "reference" not in response.model_dump()


def test_prepared_fixture_and_schema_match_implementation():
    root = Path(__file__).resolve().parents[2] / "fixtures" / "p5" / "diagrams"
    value = PreparedDiagram.from_bytes(
        (root / "m5_prepared.json").read_bytes(), max_bytes=65536
    )
    assert value == prepared()
    assert (
        json.loads((root / "c2-schema.json").read_text())
        == PreparedDiagram.model_json_schema()
    )


def test_partial_conflict_and_m6_fixtures_preserve_uncertainty():
    from backend.platform.diagrams.contracts import DiagramSpec

    root = Path(__file__).resolve().parents[2] / "fixtures" / "p5" / "diagrams"
    partial = DiagramSpec.from_bytes(
        (root / "partial_conflicting.json").read_bytes(), max_bytes=65536
    )
    assert (
        partial.coverage.source_partial
        and partial.coverage.source_completeness.is_partial
    )
    assert partial.annotations[0].kind == "conflict"
    assert partial.annotations[0].records[0].record_type == "conflict"
    assert partial.view.no_flow_reason == "insufficient_evidence"
    response = DiagramViewResponse.from_bytes(
        (root / "m6_view_response.json").read_bytes(), max_bytes=65536
    )
    assert response.base_generation_id == prepared().descriptor.reference.generation_id
    assert "reference" not in response.model_dump()
