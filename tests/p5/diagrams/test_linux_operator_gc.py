"""Second-principal physical GC phase of the real B1 deployment experiment.

Run AFTER worker experiments, as the administrator-approved trusted operator
(NOT root/worker). Exact generation UUIDs come from worker evidence, never
latest/current discovery. This test must not be granted to the ordinary worker.
"""

import hashlib
import json
import os
import re
import subprocess

try:
    import grp
    import pwd
except ImportError:
    grp = None  # type: ignore[assignment]
    pwd = None  # type: ignore[assignment]
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.platform.diagrams.artifacts import STORE_ROOT
from backend.platform.diagrams.persistence import DiagramGenerationModel as Generation

pytestmark = pytest.mark.skipif(
    os.environ.get("M4_LINUX_GC_PROOFS") != "1",
    reason="actual separately authorized operator GC phase required",
)


def test_operator_gc_preserves_accepted_history_and_deletes_only_reserved_orphan():
    assert os.geteuid() not in (0, pwd.getpwnam("stacksense-worker").pw_uid)
    assert grp.getgrnam("stacksense-artifact-gc").gr_gid in {
        *os.getgroups(),
        os.getegid(),
    }
    schema = os.environ["M4_PROOF_SCHEMA"]
    assert re.fullmatch(r"p5_diagram_[0-9a-f]{32}", schema)
    url = make_url(os.environ["P5_TEST_DATABASE_URL"])
    assert (url.database or "").startswith("stacksense_p5_b2_")
    db = create_engine(url).execution_options(schema_translate_map={None: schema})
    accepted = UUID(os.environ["M4_GC_ACCEPTED_GENERATION"])
    orphan = UUID(os.environ["M4_GC_ORPHAN_GENERATION"])
    assert accepted != orphan
    try:
        with Session(db) as session:
            good = session.get(Generation, accepted)
            retired = session.get(Generation, orphan)
            assert good.state == "ACCEPTED" and good.accepted_reference is not None
            assert retired.state == "DELETING" and retired.accepted_reference is None
        root = STORE_ROOT / "sealed"
        assert os.access(root, os.R_OK | os.X_OK)
        good_manifest = (root / str(accepted) / "manifest.json").read_bytes()
        assert (root / str(orphan) / "manifest.json").is_file()
        command = [
            "/usr/bin/sudo",
            "-n",
            "-u",
            "stacksense-artifacts",
            "/opt/stacksense/diagram-artifacts/gc-generation",
        ]
        denied = subprocess.run(
            [*command, str(accepted)], capture_output=True, timeout=10
        )
        assert denied.returncode == 78
        removed = subprocess.run(
            [*command, str(orphan)], capture_output=True, timeout=10
        )
        assert removed.returncode == 0
        assert os.access(root, os.R_OK | os.X_OK)
        assert not (root / str(orphan)).exists()
        assert (root / str(accepted) / "manifest.json").read_bytes() == good_manifest
        with Session(db) as session:
            assert session.get(Generation, accepted).state == "ACCEPTED"
            # Physical GC never owns metadata transitions. The reserved durable
            # tombstone stays DELETING until an M4 metadata owner finalizes it.
            assert session.get(Generation, orphan).state == "DELETING"
        print(
            json.dumps(
                {
                    "proof": "operator-physical-gc",
                    "result": "PASS",
                    "orphan": str(orphan),
                    "accepted": str(accepted),
                    "accepted_manifest_sha256": hashlib.sha256(
                        good_manifest
                    ).hexdigest(),
                }
            )
        )
    finally:
        db.dispose()
