"""Unit-only preflight/policy tests; never runtime or physical proof claims."""

import os
import sys

import pytest

from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.linux_runtime import policy, protected_regular


def test_cgroup_policy_keeps_zero_swap_and_one_cpu():
    limits = DiagramLimits()
    assert policy(limits) == {
        "memory.max": str(768 * 1024**2),
        "memory.swap.max": "0",
        "pids.max": "64",
        "cpu.max": "100000 100000",
    }


def test_installation_rejects_worker_owned_or_symlinked_runtime(tmp_path):
    if sys.platform != "linux" or not hasattr(os, "geteuid"):
        pytest.skip(
            "Linux rootless deployment preflight checks require Linux and geteuid"
        )
    regular = tmp_path / "entry"
    regular.write_bytes(b"not a root-installed executable")
    if os.geteuid() != 0:
        with pytest.raises(ValueError):
            protected_regular(regular)
    link = tmp_path / "alias"
    link.symlink_to(regular)
    with pytest.raises(ValueError):
        protected_regular(link, uid=os.geteuid())
