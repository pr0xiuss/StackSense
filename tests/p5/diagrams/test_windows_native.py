"""Native Windows tests; skips on Linux never establish Windows support."""

import ctypes
import os
import sys

import pytest

from backend.platform.diagrams.artifact_contracts import SealRequest
from backend.platform.diagrams.windows_artifacts import sealer_sddl
from backend.platform.diagrams.windows_native import (
    FileInformation,
    NativeWindows,
    WindowsJob,
)


def test_shared_seal_wire_is_independent_of_linux_imports():
    if sys.platform != "win32":
        from backend.platform.diagrams.artifacts import SealRequest as LinuxRequest

        assert LinuxRequest is SealRequest
    assert ctypes.sizeof(FileInformation) == 52


@pytest.mark.parametrize(
    "owner,reader",
    [
        ("bad", "S-1-5-21-1"),
        ("S-1-5-18", "S-1-5-21-2"),
        ("S-1-5-21-1", "S-1-5-21-1"),
        ("S-1-5-21-1", "bad)(A;;FA;;;WD)"),
    ],
)
def test_sealer_identity_sddl_rejects_injection_and_collapsed_roles(owner, reader):
    with pytest.raises(ValueError):
        sealer_sddl(owner, reader)


def test_windows_native_never_emulates_on_linux():
    if sys.platform == "win32":
        pytest.skip("non-Windows rejection test")
    with pytest.raises(OSError, match="native Windows"):
        NativeWindows()


@pytest.mark.skipif(
    sys.platform != "win32", reason="actual Windows API execution required"
)
def test_real_windows_job_and_token():
    native = NativeWindows()
    assert native.token_sid().startswith("S-1-5-")
    job = WindowsJob(native, memory=128 * 1024**2, processes=4, cpu=1)
    job.close()
    assert job.handle is None


@pytest.mark.skipif(
    os.environ.get("M4_WINDOWS_PROOFS") != "1",
    reason="provisioned actual Windows LPAC runtime required",
)
def test_real_windows_lpac_elk_and_reproducibility():
    from time import monotonic

    from backend.platform.diagrams.configuration import DiagramLimits
    from backend.platform.diagrams.fonts import DiagramFonts
    from backend.platform.diagrams.layout import (
        LayoutScene,
        RuntimeNode,
        create_layout_profile,
    )
    from backend.platform.diagrams.model import visual_id
    from backend.platform.diagrams.windows_runtime import (
        WindowsElkEngine,
        appcontainer_sid,
        installed,
    )

    native = NativeWindows()
    lock = installed(native, appcontainer_sid(native))
    fonts = DiagramFonts()
    try:
        font_digest = fonts.manifest_digest()
    finally:
        fonts.close()
    profile = create_layout_profile("architecture_compound_v1", lock, font_digest)
    scene = LayoutScene(
        nodes=(
            RuntimeNode(
                id=visual_id("node", "windows"),
                parent_id=None,
                width=240000,
                height=80000,
                ports=(),
            ),
        ),
        edges=(),
        labels=(),
    )

    class Control:
        def checkpoint(self):
            pass

    engine = WindowsElkEngine(DiagramLimits(), font_manifest_digest=font_digest)
    expected = None
    for _ in range(20):
        value = engine.layout("a" * 64, profile, scene, monotonic() + 30, Control())
        raw = value.geometry.to_bytes()
        if expected is not None:
            assert raw == expected
        expected = raw


@pytest.mark.skipif(
    os.environ.get("M4_WINDOWS_PROOFS") != "1",
    reason="actual Windows isolation proof host required",
)
@pytest.mark.parametrize(
    "mode",
    ["denial", "fds", "cancel", "stdout", "stderr", "memory", "cpu", "processes"],
)
def test_real_windows_lpac_denial_exhaustion_cancellation(mode):
    import json
    from time import monotonic

    from backend.platform.diagrams.configuration import DiagramLimits
    from backend.platform.diagrams.windows_runtime import (
        appcontainer_sid,
        communicate,
        installed,
    )

    native = NativeWindows()
    native.require_unprivileged()
    lock = installed(native, appcontainer_sid(native))
    assert "proof_probe.mjs" in {x.path for x in lock.files}
    limits = DiagramLimits(
        max_helper_memory_bytes=128 * 1024**2,
        max_helper_processes=16,
        max_helper_cpu_seconds=20 if mode == "cancel" else 1,
    )
    job = WindowsJob(
        native,
        memory=limits.max_helper_memory_bytes,
        processes=limits.max_helper_processes,
        cpu=limits.max_helper_cpu_seconds,
    )
    started = monotonic()

    class Control:
        def checkpoint(self):
            if mode == "cancel" and monotonic() - started >= 1:
                raise InterruptedError("proof cancellation")

    try:
        try:
            raw = communicate(
                native,
                job,
                json.dumps({"mode": mode}).encode(),
                started + 8,
                Control(),
                limits,
                proof=True,
            )
        except (InterruptedError, TimeoutError) as exc:
            assert mode not in ("denial", "fds")
            assert str(exc) in ("proof cancellation", "diagram_timeout")
        except ValueError as exc:
            assert mode in ("stdout", "stderr") and str(exc) == "diagram_limit_exceeded"
        else:
            if mode == "denial":
                values = json.loads(raw)
                assert values and all(values.values())
            elif mode == "fds":
                values = json.loads(raw)
                # A Windows host without the required native handle bound must
                # FAIL here, not accept the larger default OS handle table.
                assert (
                    values["code"] == "EMFILE"
                    and values["count"] < limits.max_helper_fds
                )
            else:
                # Resource death is not a successful layout response.
                assert not raw
    finally:
        job.close()
    assert job.handle is None
