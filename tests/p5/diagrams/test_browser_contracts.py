"""Cross-language fixture/schema parity, not actual browser acceptance."""

import base64
import gzip
import json
from pathlib import Path

import pytest

from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import PreparedDiagram
from backend.platform.diagrams.validation import DiagramValidator

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/p5/diagrams"
ROOT = Path(__file__).resolve().parents[3]


def test_frontend_schema_is_exact_current_c2_materialization():
    schema = json.loads((FIXTURES / "c2-schema.json").read_text())
    assert schema == PreparedDiagram.model_json_schema()
    assert schema == json.loads(
        (ROOT / "frontend/src/contracts/diagramSchema.json").read_text()
    )


def test_optimized_json_escaping_is_exact_for_controls_unicode_and_literal_slashes():
    from backend.platform.diagrams.model import canonical_bytes

    samples = [
        "".join(chr(i) for i in range(128)),
        'quoted " text \\ literal \\n\nα😀',
        "plain:field-identifier",
    ]
    for text in samples:
        expected = (
            '"'
            + "".join(
                (
                    '\\"'
                    if c == '"'
                    else (
                        "\\\\"
                        if c == "\\"
                        else f"\\u{ord(c):04x}" if ord(c) < 32 else c
                    )
                )
                for c in text
            )
            + '"'
        )
        assert canonical_bytes(text) == expected.encode("utf-8")


def test_prepared_serialization_still_revalidates_unsafe_nested_model_copy():
    from tests.p5.diagrams.test_c2_consumers import prepared

    value = prepared()
    invalid_layout = value.layout.model_copy(update={"layout_digest": "0" * 64})
    invalid = value.model_copy(update={"layout": invalid_layout})
    with pytest.raises(ValueError):
        invalid.to_bytes()


def test_canonical_encoder_matches_reference_on_nested_unicode_and_controls():
    import random

    from backend.platform.diagrams.model import canonical_bytes

    def reference(value):
        if value is None:
            return b"null"
        if type(value) is bool:
            return b"true" if value else b"false"
        if type(value) is int:
            return str(value).encode()
        if isinstance(value, str):
            return (
                '"'
                + "".join(
                    (
                        '\\"'
                        if c == '"'
                        else (
                            "\\\\"
                            if c == "\\"
                            else f"\\u{ord(c):04x}" if ord(c) < 32 else c
                        )
                    )
                    for c in value
                )
                + '"'
            ).encode("utf-8")
        if isinstance(value, list):
            return b"[" + b",".join(reference(v) for v in value) + b"]"
        return (
            b"{"
            + b",".join(
                reference(k) + b":" + reference(value[k])
                for k in sorted(value, key=lambda k: k.encode("utf-8"))
            )
            + b"}"
        )

    rng = random.Random(4519)
    chars = [
        "a",
        "β",
        "😀",
        "\ue000",
        "\U00010000",
        "\x00",
        "\b",
        "\t",
        "\n",
        "\r",
        "\f",
        '"',
        "\\",
        "/",
    ]

    def value(depth):
        choice = rng.randrange(6 if depth else 4)
        if choice == 0:
            return None
        if choice == 1:
            return rng.choice([False, True])
        if choice == 2:
            return rng.choice([0, -1, 2**53 - 1, -(2**53 - 1)])
        if choice == 3:
            return "".join(rng.choices(chars, k=rng.randrange(20)))
        if choice == 4:
            return [value(depth - 1) for _ in range(rng.randrange(5))]
        return {
            "".join(rng.choices(chars, k=4)): value(depth - 1)
            for _ in range(rng.randrange(5))
        }

    for _ in range(1000):
        record = value(4)
        assert canonical_bytes(record) == reference(record)


@pytest.mark.parametrize(
    "name",
    [
        "system_overview",
        "component_architecture",
        "dependency_map",
        "data_flow",
        "stress150",
        "stress500",
    ],
)
def test_real_elk_browser_fixture_prepared_and_geometry_validation(name):
    raw = gzip.decompress(
        base64.b64decode(
            (FIXTURES / f"b4_{name}.json.gz.b64").read_text(), validate=False
        )
    )
    value = PreparedDiagram.from_bytes(raw, max_bytes=128 * 1024 * 1024)
    DiagramValidator(DiagramLimits()).layout(value.spec, value.layout)
    if name.startswith("stress"):
        assert len(value.spec.nodes) == int(name[6:])
    else:
        assert value.spec.template.value == name
    assert value.to_bytes() == raw
