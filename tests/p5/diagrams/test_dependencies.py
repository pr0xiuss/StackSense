"""Registry and deployment gates, not certification by configuration flag."""

from types import SimpleNamespace

import pytest

from backend.platform import config
from backend.platform.diagrams import dependencies
from backend.platform.diagrams.configuration import DiagramRuntimeConfig


@pytest.mark.parametrize(
    "enabled,approved,raw",
    [
        (False, False, None),
        (True, False, None),
        (False, True, None),
        (True, True, None),
    ],
)
def test_incomplete_configuration_does_not_register_any_diagram(
    monkeypatch, enabled, approved, raw
):
    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: SimpleNamespace(
            diagram_enabled=enabled,
            diagram_operational_approval=approved,
            diagram_deployment_json=raw,
        ),
    )

    def forbidden():
        pytest.fail("disabled registration performed infrastructure I/O")

    monkeypatch.setattr(dependencies, "verify_installation", forbidden)
    assert dependencies.configured_diagram_registrations() == ()


def test_no_secret_default_or_implicit_runtime_profile():
    with pytest.raises(ValueError):
        DiagramRuntimeConfig.model_validate_json("{}")


def test_proof_fault_configuration_cannot_enable_production(monkeypatch):
    from pathlib import Path

    original = Path.exists
    monkeypatch.setattr(
        Path, "exists", lambda self: self.name == "proof-enabled" or original(self)
    )
    with pytest.raises(ValueError, match="diagram_store_unavailable"):
        dependencies._storage_preflight()
