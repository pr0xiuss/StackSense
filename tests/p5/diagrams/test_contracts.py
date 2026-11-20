"""C2 strictness and reproducible byte rules, not physical-store proof."""

import hashlib

import pytest
from pydantic import ValidationError

from backend.platform.delivery.contracts import DiagramTemplate
from backend.platform.diagrams.contracts import (
    Box,
    DiagramSpec,
    EvidenceProvenance,
    EvidenceRef,
    MemberDescriptor,
    PathCommand,
    Polarity,
    Strength,
)
from backend.platform.diagrams.model import (
    canonical_bytes,
    digest,
    load_json,
    template_rules,
    visual_id,
)
from tests.p5.diagrams.conftest import empty_parts


def test_canonical_utf8_and_controls():
    assert canonical_bytes({"é": "e\u0301\r\n\t", "a": '\\"'}) == (
        '{"a":"\\\\\\"","é":"e\u0301\\u000d\\u000a\\u0009"}'.encode()
    )
    assert canonical_bytes("é") != canonical_bytes("e\u0301")
    assert canonical_bytes("\ufeff") == '"\ufeff"'.encode()


@pytest.mark.parametrize(
    "value", [1.2, float("nan"), float("inf"), {1: "bad"}, 2**53, "\ud800"]
)
def test_invalid_canonical_values(value):
    with pytest.raises((ValueError, UnicodeError)):
        canonical_bytes(value)


@pytest.mark.parametrize(
    "data",
    [
        b'{"x":1,"x":2}',
        b"NaN",
        b"1.0",
        b"1e0",
        b"\xef\xbb\xbf{}",
        b'"\\ud800"',
        b'{"x":Infinity}',
    ],
)
def test_bad_wire_values(data):
    with pytest.raises((ValueError, UnicodeError)):
        load_json(data, max_bytes=100)


def test_wire_byte_cap():
    with pytest.raises(ValueError):
        load_json(b'"1234"', max_bytes=3)


@pytest.mark.parametrize("data", [b"-0", b"9007199254740992"])
def test_noncanonical_integer_ingress(data):
    with pytest.raises(ValueError):
        load_json(data, max_bytes=100)


def test_domain_hash_is_exact_and_separated():
    payload = {"a": 1}
    expected = hashlib.sha256(b'["ss.diagram.node","1.0.0",{"a":1}]').hexdigest()
    assert digest("ss.diagram.node", payload) == expected
    assert visual_id("node", payload) == "dn:" + expected
    assert digest("ss.diagram.edge", payload) != expected
    with pytest.raises(ValueError):
        digest("ss.unknown", payload)


@pytest.mark.parametrize("template", tuple(DiagramTemplate))
def test_four_closed_views_roundtrip(template):
    spec, _, layout = empty_parts(template)
    assert DiagramSpec.from_bytes(spec.to_bytes(), max_bytes=65536) == spec
    assert layout.semantic_digest == spec.semantic_digest
    with pytest.raises(ValidationError):
        spec.template = DiagramTemplate.OVERVIEW


def test_digest_corruption_and_unknown_fields():
    spec, _, _ = empty_parts()
    payload = spec.model_dump(mode="json")
    payload["semantic_digest"] = "0" * 64
    with pytest.raises(ValidationError, match="digest mismatch"):
        DiagramSpec.model_validate_json(canonical_bytes(payload))
    payload = spec.model_dump(mode="json")
    payload["version"] = "1.0.0"
    with pytest.raises(ValidationError):
        DiagramSpec.model_validate_json(canonical_bytes(payload))


def test_uppercase_uuid_rejected_at_wire():
    spec, _, _ = empty_parts()
    data = spec.model_dump(mode="json")
    data["scope"]["project_id"] = "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"
    with pytest.raises(ValidationError, match="noncanonical"):
        DiagramSpec.model_validate_json(canonical_bytes(data))


@pytest.mark.parametrize("bad", [True, 1.0, "1", -1, 10**9 + 1])
def test_geometry_strict_integer_bounds(bad):
    with pytest.raises(ValidationError):
        Box(x=0, y=0, width=bad, height=0)


def test_deeply_frozen_range_and_optional_provenance():
    from uuid import UUID

    original = {"start_line": 1}
    evidence = EvidenceProvenance(
        record=EvidenceRef(record_type="evidence", id=UUID(int=1), logical_id="ev:1"),
        source_record_type="inventory",
        producer_id=None,
        producer_version=None,
        artifact_id=None,
        source_fact_key=None,
        path="src/a.py",
        source_range=original,
        strength=Strength.CONFIGURATION,
        polarity=Polarity.SUPPORTING,
    )
    original["start_line"] = 20
    assert evidence.source_range["start_line"] == 1
    with pytest.raises(TypeError):
        evidence.source_range["start_line"] = 2
    assert (
        EvidenceProvenance.from_bytes(evidence.to_bytes(), max_bytes=4096) == evidence
    )


def test_untrusted_model_copy_is_revalidated_on_serialize():
    spec, _, _ = empty_parts()
    corrupt = spec.model_copy(update={"semantic_digest": "0" * 64})
    with pytest.raises(ValidationError):
        corrupt.to_bytes()


def test_member_names_and_command_arity():
    with pytest.raises(ValidationError):
        MemberDescriptor(
            member="svg",
            file_name="spec.json",
            media_type="image/svg+xml",
            schema_version="1.0.0",
            size_bytes=0,
            sha256="a" * 64,
        )
    with pytest.raises(ValidationError):
        PathCommand(command="C", operands=(1, 2))


def test_four_rules_keep_static_semantics_and_conditional_promotions():
    from backend.platform.analysis.architecture.model import (
        ArchitectureEntityKind as Kind,
    )
    from backend.platform.analysis.architecture.model import (
        ArchitectureRelationshipKind as Rel,
    )

    dep = template_rules(DiagramTemplate.DEPENDENCY)
    assert len(dep.default_relationships) == 12
    assert Rel.CONTAINS not in dep.default_relationships
    flow = template_rules(DiagramTemplate.DATA_FLOW)
    assert Rel.CONSUMES in flow.default_relationships
    assert Rel.CONNECTS_TO not in flow.default_relationships
    assert Rel.CONNECTS_TO in flow.optional_relationships
    overview = template_rules(DiagramTemplate.OVERVIEW)
    assert Kind.COMPONENT not in overview.default_kinds
    assert Kind.COMPONENT in overview.conditional_kinds
    assert Kind.SERVICE in overview.default_kinds


def test_runtime_changes_do_not_redefine_semantic_profile():
    from backend.platform.diagrams.configuration import DiagramLimits

    rules = template_rules(DiagramTemplate.OVERVIEW)
    baseline = DiagramLimits()
    slower = DiagramLimits(helper_wall_seconds=60)
    assert rules.fingerprint(baseline.semantic_selection_policy()) == rules.fingerprint(
        slower.semantic_selection_policy()
    )
    smaller = DiagramLimits(max_nodes=150)
    assert rules.fingerprint(baseline.semantic_selection_policy()) != rules.fingerprint(
        smaller.semantic_selection_policy()
    )


def test_set_order_is_canonical_but_glyph_and_route_order_is_meaningful():
    from backend.platform.diagrams.model import normalize_sets

    first = {
        "nodes": [{"id": "dn:b"}, {"id": "dn:a"}],
        "routes": [{"edge_id": "de:b", "sections": [{"start": 1}, {"end": 2}]}],
        "labels": [
            {
                "id": "dl:a",
                "glyphs": [
                    {"glyph_id": "gl:b", "origin": 1},
                    {"glyph_id": "gl:a", "origin": 2},
                ],
            }
        ],
    }
    second = {**first, "nodes": list(reversed(first["nodes"]))}
    assert canonical_bytes(normalize_sets(first)) == canonical_bytes(
        normalize_sets(second)
    )
    assert normalize_sets(first)["labels"][0]["glyphs"] == first["labels"][0]["glyphs"]
    assert (
        normalize_sets(first)["routes"][0]["sections"] == first["routes"][0]["sections"]
    )
