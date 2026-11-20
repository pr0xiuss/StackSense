"""Actual NTFS/sealer + impersonated separate worker identity race harness.

Run ONLY on an authorized Windows proof host, under the non-admin sealer
account. Dedicated worker credentials are test-only inputs, never logged or
passed to Node. Windows impersonation changes the kernel access-check identity
of the hostile thread; it does not emulate ACLs. A two-process deployment test
is additionally required before production support.
"""

import ctypes as c
import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import AttemptIdentity
from backend.platform.diagrams.artifact_contracts import SealRequest
from backend.platform.diagrams.windows_artifacts import ROOT, WindowsPrincipalSealer
from backend.platform.diagrams.windows_native import PTR, U32, NativeWindows

pytestmark = pytest.mark.skipif(
    os.environ.get("M4_WINDOWS_PROOFS") != "1",
    reason="actual separate-identity Windows/NTFS proof host required",
)


@contextmanager
def worker_identity(native):
    token = PTR()
    native.check(
        native.api(
            native.advapi,
            "LogonUserW",
            [c.c_wchar_p, c.c_wchar_p, c.c_wchar_p, U32, U32, PTR],
        )(
            os.environ["M4_WINDOWS_WORKER_ACCOUNT"],
            ".",
            os.environ["M4_WINDOWS_WORKER_TEST_PASSWORD"],
            4,
            0,
            c.byref(token),
        )
    )
    try:
        native.check(native.api(native.advapi, "ImpersonateLoggedOnUser", [PTR])(token))
        try:
            yield
        finally:
            native.check(native.api(native.advapi, "RevertToSelf", [])())
    finally:
        native.close(token)


@pytest.mark.parametrize("ordinal", range(100), ids=lambda n: f"windows-race-{n:03d}")
def test_actual_ntfs_separate_identity_races(ordinal):
    from backend.platform.diagrams.artifact_runtime.windows_seal_generation import (
        configured_metadata,
    )
    from backend.platform.diagrams.persistence import (
        DiagramGenerationModel as Generation,
    )
    from tests.p5.diagrams.conftest import empty_parts
    from tests.p5.diagrams.test_c2_consumers import prepared
    from tests.p5.diagrams.test_database import stage

    native = NativeWindows()
    native.require_unprivileged()
    metadata, config = configured_metadata()
    url = make_url(os.environ["P5_TEST_DATABASE_URL"])
    assert (url.database or "").startswith("stacksense_p5_b2_")
    schema = os.environ["M4_PROOF_SCHEMA"]
    assert re.fullmatch(r"p5_diagram_[0-9a-f]{32}", schema)
    db = create_engine(url).execution_options(schema_translate_map={None: schema})
    p = prepared(generation_id=uuid4(), artifact_id=uuid4())
    ref = p.descriptor.reference.model_copy(
        update={"resource_id": uuid4(), "candidate_id": uuid4()}
    )
    p = p.model_copy(
        update={"descriptor": p.descriptor.model_copy(update={"reference": ref})}
    )
    stage(db, p)
    with Session(db) as session, session.begin():
        row = session.get(Generation, ref.generation_id)
        identity = AttemptIdentity.model_validate_json(json.dumps(row.attempt_snapshot))
        row.manifest = p.descriptor.manifest.model_dump(mode="json")
        row.manifest_sha256 = ref.digests.content
        row.manifest_size = ref.size_bytes
    request = SealRequest(
        protocol=1,
        attempt=identity,
        generation_id=ref.generation_id,
        artifact_id=ref.artifact_id,
        members=p.descriptor.manifest.members,
        manifest_sha256=ref.digests.content,
        manifest_size=ref.size_bytes,
    )
    values = {
        "manifest.json": p.descriptor.manifest.to_bytes(),
        "spec.json": p.spec.to_bytes(),
        "layout.json": p.layout.to_bytes(),
        "members.json": empty_parts()[1].to_bytes(),
        "scene.svg": b"<svg/>",
    }
    staging = ROOT / "staging" / str(ref.generation_id)
    sealed = ROOT / "sealed" / str(ref.generation_id)
    with worker_identity(native):
        staging.mkdir()
        for name, data in values.items():
            (staging / name).write_bytes(data)
        # Provisioned staging inheritance must grant only worker FA and sealer
        # read/traverse. The production sealer never creates these ACLs itself.
        retained = (staging / "spec.json").open("r+b")
    ready, stop = Event(), Event()
    violations = []

    def hostile():
        with worker_identity(native):
            ready.set()
            while not stop.is_set():
                try:
                    if ordinal % 5 == 0:
                        retained.seek(0)
                        retained.write(b"X")
                        retained.flush()
                    elif ordinal % 5 == 1:
                        (staging / "spec.json").write_bytes(b"corruption")
                    elif ordinal % 5 == 2:
                        (staging / "spec.json").rename(staging / "moved-spec")
                    elif ordinal % 5 == 3:
                        os.link(staging / "spec.json", staging / "hardlink-spec")
                    else:
                        (staging / "spec.json").rename(staging / "moved-spec")
                        (staging / "spec.json").symlink_to(r"C:\Windows\win.ini")
                except OSError:
                    pass
                for name in values:
                    try:
                        with (sealed / name).open("wb"):
                            pass
                        violations.append(name)
                    except OSError:
                        pass

    sealer = WindowsPrincipalSealer(
        metadata,
        metadata.limits_for(request),
        sealer_sid=config.sealer_sid,
        worker_sid=config.worker_sid,
        reader_sid=config.reader_sid,
    )
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            attack = pool.submit(hostile)
            assert ready.wait(5)
            try:
                proof = sealer.seal(request)
            except OSError, ValueError:
                proof = None
            finally:
                stop.set()
                attack.result(timeout=5)
        assert not violations
        if proof is None:
            with worker_identity(native):
                for extra in (staging / "hardlink-spec", staging / "moved-spec"):
                    if extra.exists():
                        extra.unlink()
                if (staging / "spec.json").is_symlink():
                    (staging / "spec.json").unlink()
                for name, data in values.items():
                    (staging / name).write_bytes(data)
            proof = sealer.seal(request)
        with worker_identity(native):
            retained.seek(0)
            retained.write(b"stale handle mutation")
            retained.flush()
            for name, data in values.items():
                assert (
                    hashlib.sha256((sealed / name).read_bytes()).digest()
                    == hashlib.sha256(data).digest()
                )
                with pytest.raises(PermissionError):
                    (sealed / name).open("wb")
                with pytest.raises(PermissionError):
                    (sealed / name).unlink()
        print(
            json.dumps(
                {
                    "proof": "windows-identity-race",
                    "ordinal": ordinal,
                    "result": "PASS",
                    "generation": str(ref.generation_id),
                    "physical_object": proof.physical_object_id,
                }
            )
        )
    finally:
        stop.set()
        retained.close()
        metadata.close()
        db.dispose()
