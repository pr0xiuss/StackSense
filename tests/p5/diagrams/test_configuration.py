import pytest
from pydantic import ValidationError

from backend.platform.diagrams.configuration import DiagramLimits


def test_approved_defaults_are_not_runtime_enablement():
    limits = DiagramLimits()
    assert (
        limits.max_nodes,
        limits.max_edges,
        limits.max_groups,
        limits.max_depth,
    ) == (500, 2000, 128, 4)
    assert limits.max_helper_memory_bytes == 768 * 1024**2
    assert limits.max_input_bytes == 128 * 1024**2
    assert limits.max_project_builds == 1


@pytest.mark.parametrize(
    "name,value",
    [
        ("max_nodes", 1001),
        ("max_helper_memory_bytes", 1024**3 + 1),
        ("max_project_builds", 2),
        ("orphan_grace_seconds", 3599),
        ("max_source_rows", True),
        ("page_size", 201),
        ("source_page_size", 0),
        ("min_free_bytes", 512 * 1024**2 - 1),
        ("extra_limit", 1),
    ],
)
def test_out_of_policy_fails_closed(name, value):
    with pytest.raises(ValidationError):
        DiagramLimits.model_validate({name: value})


def test_read_pin_outlives_stream():
    with pytest.raises(ValidationError):
        DiagramLimits(pin_seconds=60, stream_seconds=60)
