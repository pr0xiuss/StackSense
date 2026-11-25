"""Test C5 transport contract fixtures parity and schema validity.

Verifies that `tests/fixtures/p5/transport/c5-contracts.json` accurately reflects
the public C0-C4 models, C5 21-route manifest, enums, transport limits, and error
codes without mutating any producer source code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "fixtures"
    / "p5"
    / "transport"
    / "c5-contracts.json"
)


@pytest.fixture(scope="module")
def contracts_fixture() -> dict[str, Any]:
    assert FIXTURES_PATH.exists(), f"Missing fixture file at {FIXTURES_PATH}"
    with FIXTURES_PATH.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    assert isinstance(data, dict)
    return data


def test_manifest_metadata(contracts_fixture: dict[str, Any]) -> None:
    assert contracts_fixture.get("c5_version") == "1.0.0"
    assert contracts_fixture.get("manifest_name") == "P5_C5_TRANSPORT_MANIFEST"


def test_routes_manifest_count_and_uniqueness(
    contracts_fixture: dict[str, Any],
) -> None:
    routes = contracts_fixture.get("routes", [])
    assert len(routes) == 21, f"Expected exactly 21 routes, got {len(routes)}"

    names = set()
    paths_and_methods = set()
    for route in routes:
        name = route.get("name")
        method = route.get("method")
        path = route.get("express_path")

        assert name, "Route name must be non-empty"
        assert method in ("GET", "POST"), f"Invalid method {method}"
        assert path and path.startswith(
            "/architecture-versions/:versionId/"
        ), f"Invalid path prefix {path}"

        assert name not in names, f"Duplicate route name: {name}"
        names.add(name)

        key = (method, path)
        assert key not in paths_and_methods, f"Duplicate method/path: {key}"
        paths_and_methods.add(key)


def test_schemas_presence(contracts_fixture: dict[str, Any]) -> None:
    schemas = contracts_fixture.get("schemas", {})
    expected_models = [
        "DeliverySummary",
        "RetryAccepted",
        "RetryRequest",
        "SearchStatus",
        "SearchPage",
        "SearchRebuildRequest",
        "SearchReprojectionAccepted",
        "KnowledgeQueryRequest",
        "KnowledgeQueryResponse",
        "ContextRequest",
        "ContextBundle",
        "EvidencePage",
        "DiagramCollection",
        "DiagramSummary",
        "GenerationPage",
        "DiagramSpec",
        "LayoutSpec",
        "DiagramViewRequest",
        "DiagramViewResponse",
        "MemberPage",
        "PreparedDiagram",
        "ReportCollection",
        "ReportSummary",
        "ReportGenerationPage",
        "ReportGenerationSummary",
    ]
    for model_name in expected_models:
        assert model_name in schemas, f"Missing schema for {model_name}"
        schema = schemas[model_name]
        assert "properties" in schema or "$defs" in schema or "type" in schema


def test_enums_presence_and_values(contracts_fixture: dict[str, Any]) -> None:
    enums = contracts_fixture.get("enums", {})
    assert "DiagramTemplate" in enums
    assert set(enums["DiagramTemplate"]) == {
        "system_overview",
        "component_architecture",
        "dependency_map",
        "data_flow",
    }

    assert "RetrievalOperation" in enums
    assert "lookup" in enums["RetrievalOperation"]
    assert "relationships" in enums["RetrievalOperation"]
    assert "evidence" in enums["RetrievalOperation"]

    assert "DeliveryEligibility" in enums
    assert "ELIGIBLE" in enums["DeliveryEligibility"]

    assert "ReportStatus" in enums
    assert set(enums["ReportStatus"]) == {"WAITING", "BUILDING", "READY", "FAILED"}


def test_transport_limits_match_policy(contracts_fixture: dict[str, Any]) -> None:
    limits = contracts_fixture.get("transport_limits", {})
    assert limits.get("max_query_bytes") == 32768
    assert limits.get("max_json_body_bytes") == 131072
    assert limits.get("max_metadata_response_bytes") == 4194304
    assert limits.get("max_pdf_bytes") == 67108864
    assert limits.get("read_timeout_seconds") == 30
    assert limits.get("context_timeout_seconds") == 120
    assert limits.get("max_active_artifact_relays") == 2


def test_error_codes(contracts_fixture: dict[str, Any]) -> None:
    errors = contracts_fixture.get("error_codes", {})
    transport_errors = errors.get("transport", [])
    assert "intelligence_upstream_invalid" in transport_errors
    assert "intelligence_transport_limit" in transport_errors
    assert "intelligence_transport_busy" in transport_errors
    assert "intelligence_upstream_unavailable" in transport_errors
    assert "intelligence_upstream_timeout" in transport_errors
