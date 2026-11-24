"""Actual fixed-identity seal entry, PostgreSQL staging and 100 hostile races.

Opt-in only on the provisioned B1 store and precreated isolated schema. Test
artifacts/metadata are retained for independent examination, never recursively
deleted. Run with -s --junitxml=... to retain individual race outcomes.
"""

import hashlib
import json
import os
import pwd
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import AttemptIdentity, DiagramTemplate
from backend.platform.diagrams.artifacts import STORE_ROOT, SealProof, SealRequest
from backend.platform.diagrams.persistence import DiagramGenerationModel as Generation
from tests.p5.diagrams.conftest import empty_parts
from tests.p5.diagrams.test_c2_consumers import prepared
from tests.p5.diagrams.test_database import stage

pytestmark = pytest.mark.skipif(
    os.environ.get("M4_LINUX_PROOFS") != "1",
    reason="real separate-principal Linux proof",
)
SEAL = "/opt/stacksense/diagram-artifacts/seal-generation"
GC = "/opt/stacksense/diagram-artifacts/gc-generation"


def test_actual_sealer_database_grants_are_read_only_and_m4_only():
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    url = make_url(os.environ["M4_SEAL_TEST_DATABASE_URL"])
    assert (url.database or "").startswith("stacksense_p5_b2_")
    schema = os.environ["M4_PROOF_SCHEMA"]
    assert re.fullmatch(r"p5_diagram_[0-9a-f]{32}", schema)
    db = create_engine(url, connect_args={"connect_timeout": 2})
    try:
        with db.connect() as connection:
            assert connection.scalar(text("SHOW default_transaction_read_only")) == "on"
            connection.execute(
                text(f'SELECT id FROM "{schema}".diagram_generation LIMIT 1')
            )
        for statement in (
            f'UPDATE "{schema}".diagram_generation SET state=state',
            f'SELECT id FROM "{schema}".delivery_work LIMIT 1',
            f'CREATE TABLE "{schema}".unauthorized_sealer_table (id integer)',
        ):
            with pytest.raises(DBAPIError) as error, db.connect() as connection:
                connection.execute(text("SET TRANSACTION READ WRITE"))
                connection.execute(text(statement))
            assert error.value.orig.sqlstate == "42501"
    finally:
        db.dispose()


@pytest.fixture(scope="module")
def physical_db():
    assert os.geteuid() == pwd.getpwnam("stacksense-worker").pw_uid != 0
    assert os.geteuid() != pwd.getpwnam("stacksense-artifacts").pw_uid
    value = os.environ["P5_TEST_DATABASE_URL"]
    url = make_url(value)
    assert (url.database or "").startswith("stacksense_p5_b2_")
    schema = os.environ["M4_PROOF_SCHEMA"]
    assert re.fullmatch(r"p5_diagram_[0-9a-f]{32}", schema)
    engine = create_engine(url).execution_options(schema_translate_map={None: schema})
    try:
        with Session(engine) as session:
            session.execute(select(Generation.id).limit(1))
        yield engine
    finally:
        engine.dispose()


def invoke(request):
    result = subprocess.run(
        ["/usr/bin/sudo", "-n", "-u", "stacksense-artifacts", SEAL],
        input=request.to_bytes(),
        capture_output=True,
        timeout=30,
        check=False,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TZ": "UTC"},
    )
    if result.returncode:
        assert not result.stdout
        return None
    return SealProof.from_bytes(result.stdout, max_bytes=8192)


def staged(engine, lease=None, generation_id=None, *, application_only=False):
    p = prepared(
        template=lease.identity.work.binding.slot.template if lease else None,
        generation_id=generation_id or uuid4(),
        artifact_id=uuid4(),
    )
    if lease is not None:
        manifest = p.descriptor.manifest.model_copy(
            update={
                "scope": lease.identity.work.scope,
                "binding": lease.identity.work.binding,
                "input_fingerprint": lease.identity.work.input_fingerprint,
            }
        )
        p = p.model_copy(
            update={
                "descriptor": p.descriptor.model_copy(update={"manifest": manifest})
            }
        )
    ref = p.descriptor.reference.model_copy(
        update={"resource_id": uuid4(), "candidate_id": uuid4()}
    )
    if lease is not None:
        ref = ref.model_copy(
            update={
                "scope": lease.identity.work.scope,
                "binding": lease.identity.work.binding,
                "input_fingerprint": lease.identity.work.input_fingerprint,
                "candidate_id": lease.identity.candidate_id,
                "size_bytes": len(manifest.to_bytes()),
                "digests": ref.digests.model_copy(
                    update={"content": hashlib.sha256(manifest.to_bytes()).hexdigest()}
                ),
            }
        )
    p = p.model_copy(
        update={"descriptor": p.descriptor.model_copy(update={"reference": ref})}
    )
    _, generation = stage(engine, p, owner=lease.identity if lease else None)
    with Session(engine) as session, session.begin():
        row = session.get(Generation, generation)
        owner = AttemptIdentity.model_validate_json(json.dumps(row.attempt_snapshot))
        row.manifest = p.descriptor.manifest.model_dump(mode="json")
        row.manifest_size = ref.size_bytes
        row.manifest_sha256 = ref.digests.content
    folder = STORE_ROOT / "staging" / str(generation)
    folder.mkdir(mode=0o700)
    values = {
        "spec.json": p.spec.to_bytes(),
        "layout.json": p.layout.to_bytes(),
        "members.json": empty_parts(p.spec.template)[1].to_bytes(),
        "scene.svg": b"<svg/>",
        "manifest.json": p.descriptor.manifest.to_bytes(),
    }
    for name, data in values.items():
        path = folder / name
        with path.open("xb") as stream:
            stream.write(data)
        path.chmod(0o600)
        if not application_only:
            subprocess.run(
                ["/usr/bin/setfacl", "-m", "u:stacksense-artifacts:r--", str(path)],
                check=True,
            )
    if not application_only:
        subprocess.run(
            ["/usr/bin/setfacl", "-m", "u:stacksense-artifacts:r-x", str(folder)],
            check=True,
        )
    request = SealRequest(
        protocol=1,
        attempt=owner,
        generation_id=generation,
        artifact_id=ref.artifact_id,
        members=p.descriptor.manifest.members,
        manifest_sha256=ref.digests.content,
        manifest_size=ref.size_bytes,
    )
    return p, request, folder, values


@pytest.mark.parametrize("ordinal", range(100), ids=lambda n: f"race-{n:03d}")
def test_separate_principal_adversarial_race(physical_db, ordinal):
    p, request, folder, values = staged(physical_db)
    original = folder / "spec.json"
    retained = original.open("r+b")
    sealed = STORE_ROOT / "sealed" / str(request.generation_id)
    ready, stop = Event(), Event()
    violations = []
    mode = ordinal % 5

    def attack():
        ready.set()
        while not stop.is_set():
            try:
                if mode == 0:
                    retained.seek(0)
                    retained.write(b"X")
                    retained.flush()
                elif mode == 1:
                    os.link(original, folder / "hostile-link")
                elif mode == 2:
                    original.rename(folder / "moved-spec")
                    original.symlink_to("/etc/shadow")
                elif mode == 3:
                    original.chmod(0o000)
                else:
                    with original.open("wb") as stream:
                        stream.write(b"bad")
            except OSError:
                pass
            for name in values:
                target = sealed / name
                for operation in (
                    lambda t=target: t.open("wb").close(),
                    lambda t=target: t.chmod(0o600),
                    lambda t=target: t.unlink(),
                ):
                    try:
                        operation()
                        violations.append(name)
                    except OSError:
                        pass

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(attack)
            assert ready.wait(2)
            result = invoke(request)
            stop.set()
            writer.result(timeout=2)
        assert not violations
        # A racing staging mutation must either reject or seal the exact bytes.
        # Restore only worker-owned staging and retry a rejected copy.
        if result is None:
            for name, data in values.items():
                path = folder / name
                if path.is_symlink():
                    path.unlink()
                if path.exists():
                    path.chmod(0o600)
                path.write_bytes(data)
                subprocess.run(
                    ["/usr/bin/setfacl", "-m", "u:stacksense-artifacts:r--", str(path)],
                    check=True,
                )
            for extra in (folder / "hostile-link", folder / "moved-spec"):
                if extra.exists():
                    extra.unlink()
            result = invoke(request)
        assert result is not None
        for name, data in values.items():
            assert (
                hashlib.sha256((sealed / name).read_bytes()).digest()
                == hashlib.sha256(data).digest()
            )
            with pytest.raises(PermissionError):
                (sealed / name).open("wb")
            with pytest.raises(PermissionError):
                (sealed / name).chmod(0o600)
            with pytest.raises(PermissionError):
                (sealed / name).unlink()
        retained.seek(0)
        retained.write(b"stale mutation")
        retained.flush()
        assert (sealed / "spec.json").read_bytes() == values["spec.json"]
        denied = subprocess.run(
            [
                "/usr/bin/sudo",
                "-n",
                "-u",
                "stacksense-artifacts",
                GC,
                str(request.generation_id),
            ],
            capture_output=True,
            timeout=5,
        )
        assert denied.returncode != 0
        with Session(physical_db) as session:
            row = session.get(Generation, request.generation_id)
            assert row.state == "STAGING" and row.accepted_reference is None
        print(
            json.dumps(
                {
                    "proof": "sealing-race",
                    "ordinal": ordinal,
                    "attack": mode,
                    "generation": str(request.generation_id),
                    "result": "PASS",
                    "worker_uid": os.geteuid(),
                    "seal": result.model_dump(mode="json"),
                }
            )
        )
    finally:
        stop.set()
        retained.close()


def test_physical_seal_m1_commit_rollback_read_and_gc_exclusion(physical_db):
    """REAL M1 UoW with a test-only M4 participant, not B3 registration.

    The participant is deliberately local to this experiment; physical bytes
    come from the fixed OS sealer above, not a mocked store or seal label.
    """
    from contextlib import contextmanager
    from datetime import timedelta

    from sqlalchemy.exc import DBAPIError

    from backend.platform.delivery.contracts import (
        AcceptedOutput,
        CandidateSeal,
        PreparedOutput,
    )
    from backend.platform.delivery.model import Eligibility
    from backend.platform.delivery.ownership import SqlAlchemyAttemptRetirementReader
    from backend.platform.delivery.persistence import DeliveryWorkModel as Work
    from backend.platform.delivery.publication import (
        PublicationUnitOfWork,
        ReadyValidation,
    )
    from backend.platform.delivery.repository import SqlAlchemyDeliveryRepository
    from backend.platform.diagrams.artifacts import LocalGeneratedArtifactStore
    from backend.platform.diagrams.configuration import DiagramLimits
    from backend.platform.diagrams.persistence import DiagramReadPinModel as Pin
    from backend.platform.diagrams.persistence import DiagramResourceModel as Resource
    from tests.p5.delivery.test_rollout import budgets
    from tests.p5.diagrams.test_database import verified_metadata
    from tests.p5.integration.test_delivery_postgres import policy

    initial = prepared(DiagramTemplate.OVERVIEW)
    binding = initial.descriptor.reference.binding
    selected = policy()
    selected = selected.model_copy(
        update={
            "profiles": tuple(
                binding if x.slot == binding.slot else x for x in selected.profiles
            )
        }
    )
    scope = initial.descriptor.reference.scope
    with Session(physical_db) as session, session.begin():
        repo = SqlAlchemyDeliveryRepository(session)
        bundle = repo.ensure_bundle(
            scope,
            selected,
            Eligibility.ELIGIBLE,
            revisit_seconds=1,
            runtime_profile=budgets().model_dump(mode="json"),
        )
        work = session.scalar(
            select(Work.id).where(
                Work.bundle_id == bundle,
                Work.kind == "diagram",
                Work.template == "system_overview",
            )
        )
        reservation = repo.reserve(
            work,
            scope.project_id,
            reservation_seconds=2,
            correlation_id="m4:b1:physical-proof",
        )
        assert reservation is not None
    with Session(physical_db) as session, session.begin():
        lease = SqlAlchemyDeliveryRepository(session).claim(
            reservation[0],
            binding,
            "m4-b1-proof",
            max_executions=3,
            lease_seconds=120,
            execution_seconds=180,
        )
    assert lease is not None
    p, request, _, values = staged(physical_db, lease)
    proof = invoke(request)
    assert proof is not None
    forged = request.model_copy(
        update={
            "attempt": request.attempt.model_copy(
                update={"fence": request.attempt.fence + 1}
            )
        }
    )
    assert invoke(forged) is None
    verified_metadata(
        physical_db,
        request.generation_id,
        value=p,
        actual_proof=proof.model_dump(mode="json"),
    )
    reference = p.descriptor.reference
    candidate = PreparedOutput(
        attempt=lease.identity,
        candidate=CandidateSeal(
            generation_id=reference.generation_id,
            artifact_id=reference.artifact_id,
            digests=reference.digests,
            size_bytes=reference.size_bytes,
            sealed=True,
        ),
    )

    class Participant:
        def __init__(self, session):
            self.session = session

        def publish_prepared(self, value, context):
            context.require_prepared(value)
            row = self.session.scalar(
                select(Generation)
                .where(Generation.id == reference.generation_id)
                .with_for_update()
            )
            assert row.state == "SEALED_VERIFIED"
            assert row.attempt_snapshot == lease.identity.model_dump(mode="json")
            assert row.seal_proof == proof.model_dump(mode="json")
            self.session.execute(
                update(Generation)
                .where(Generation.id == row.id)
                .values(
                    state="ACCEPTED",
                    accepted_reference=reference.model_dump(mode="json"),
                    acceptance_context={
                        "transaction_id": str(context.transaction_id),
                        "attempt_id": str(lease.identity.attempt_id),
                        "reference": reference.model_dump(mode="json"),
                    },
                    accepted_at=datetime.now(UTC),
                )
            )
            self.session.execute(
                update(Resource)
                .where(Resource.id == reference.resource_id)
                .values(accepted_generation_id=reference.generation_id)
            )
            return AcceptedOutput(reference=reference)

        def validate_ready(self, ref, context):
            context.require_reference(ref)
            row = self.session.scalar(
                select(Generation).where(Generation.id == ref.generation_id)
            )
            assert row.accepted_reference == ref.model_dump(mode="json")
            return ReadyValidation(reference=ref)

    class Authority:
        @contextmanager
        def pinned(self, scope, ref):
            self.recheck(scope, ref)
            identity = uuid4()
            now = datetime.now(UTC)
            with Session(physical_db) as session, session.begin():
                session.add(
                    Pin(
                        id=identity,
                        generation_id=ref.generation_id,
                        actor_id=uuid4(),
                        purpose="api",
                        created_at=now,
                        expires_at=now + timedelta(seconds=120),
                        token_hash="a" * 64,
                    )
                )
            try:
                yield p.descriptor.manifest
            finally:
                from sqlalchemy import delete

                with Session(physical_db) as session, session.begin():
                    session.execute(delete(Pin).where(Pin.id == identity))

        def recheck(self, scope, ref):
            with Session(physical_db) as session:
                row = session.get(Generation, ref.generation_id)
                if row.state != "ACCEPTED" or row.accepted_reference != ref.model_dump(
                    mode="json"
                ):
                    raise PermissionError("not committed/accepted")

    store = LocalGeneratedArtifactStore(Authority(), DiagramLimits())
    for commit in (False, True):
        with PublicationUnitOfWork(
            physical_db, timeout_seconds=5, lock_timeout_ms=1000
        ) as uow:
            uow.complete(lease, candidate, Participant)
            with pytest.raises(PermissionError):
                store.open_exact(scope, reference, "spec")
            if commit:
                uow.commit()
    handle = store.open_exact(scope, reference, "spec")
    retirement = SqlAlchemyAttemptRetirementReader(
        physical_db, timeout_seconds=2, lock_timeout_ms=1000
    ).read_retirement(lease.identity)
    assert retirement is not None and retirement.publication is not None

    def cleanup_attempt():
        with (
            pytest.raises(DBAPIError, match="terminal diagram generation"),
            Session(physical_db) as session,
            session.begin(),
        ):
            session.execute(
                update(Generation)
                .where(Generation.id == reference.generation_id)
                .values(
                    state="DELETING",
                    accepted_reference=None,
                    acceptance_context=None,
                    accepted_at=None,
                    deletion_nonce=uuid4(),
                    deletion_actor=uuid4(),
                    deleting_at=datetime.now(UTC),
                    retirement_snapshot=retirement.model_dump(mode="json"),
                )
            )

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(cleanup_attempt)
            assert handle.read(len(values["spec.json"])) == values["spec.json"]
            future.result(timeout=5)
    finally:
        handle.close()
    cleanup_attempt()  # accepted history cannot be GC'd even after the pin closes
    print(
        json.dumps(
            {
                "proof": "physical-m1-commit-rollback-pin-cleanup",
                "result": "PASS",
                "generation": str(reference.generation_id),
            }
        )
    )


def test_prepare_exact_retired_orphan_for_separate_operator_phase(physical_db):
    """Real seal + actual public M1 expiry/recovery; no synthetic retirement."""
    from backend.platform.delivery.model import Eligibility
    from backend.platform.delivery.ownership import SqlAlchemyAttemptRetirementReader
    from backend.platform.delivery.persistence import DeliveryWorkModel as Work
    from backend.platform.delivery.repository import SqlAlchemyDeliveryRepository
    from tests.p5.delivery.test_rollout import budgets
    from tests.p5.diagrams.test_database import verified_metadata
    from tests.p5.integration.test_delivery_postgres import policy

    p = prepared(DiagramTemplate.OVERVIEW)
    scope = p.descriptor.reference.scope
    binding = p.descriptor.reference.binding
    selected = policy().model_copy(update={"policy_version": "b1-operator-orphan-v1"})
    selected = selected.model_copy(
        update={
            "profiles": tuple(
                binding if x.slot == binding.slot else x for x in selected.profiles
            )
        }
    )
    with Session(physical_db) as session, session.begin():
        repo = SqlAlchemyDeliveryRepository(session)
        bundle = repo.ensure_bundle(
            scope,
            selected,
            Eligibility.ELIGIBLE,
            revisit_seconds=1,
            runtime_profile=budgets().model_dump(mode="json"),
        )
        work = session.scalar(
            select(Work.id).where(
                Work.bundle_id == bundle,
                Work.kind == "diagram",
                Work.template == "system_overview",
            )
        )
        reservation = repo.reserve(
            work,
            scope.project_id,
            reservation_seconds=1,
            correlation_id="m4:b1:orphan-proof",
        )
        assert reservation is not None
    with Session(physical_db) as session, session.begin():
        lease = SqlAlchemyDeliveryRepository(session).claim(
            reservation[0],
            binding,
            "m4-orphan-proof",
            max_executions=3,
            lease_seconds=2,
            execution_seconds=30,
        )
    assert lease is not None
    p, request, _, _ = staged(physical_db, lease)
    proof = invoke(request)
    assert proof is not None
    verified_metadata(
        physical_db,
        request.generation_id,
        value=p,
        actual_proof=proof.model_dump(mode="json"),
    )
    # Expiry is observed through M1's public recover operation, not private
    # Attempt table edits or a fabricated terminal outcome.
    import time

    time.sleep(2.1)
    with Session(physical_db) as session, session.begin():
        assert SqlAlchemyDeliveryRepository(session).recover(
            lease.identity.work.work_id,
            scope.project_id,
            max_executions=3,
            retry_seconds=1,
        )
    retirement = SqlAlchemyAttemptRetirementReader(
        physical_db, timeout_seconds=2, lock_timeout_ms=1000
    ).read_retirement(lease.identity)
    assert retirement is not None and retirement.publication is None
    with Session(physical_db) as session, session.begin():
        session.execute(
            update(Generation)
            .where(Generation.id == request.generation_id)
            .values(
                state="DELETING",
                deletion_nonce=uuid4(),
                deletion_actor=uuid4(),
                retirement_snapshot=retirement.model_dump(mode="json"),
                deleting_at=datetime.now(UTC),
            )
        )
    assert invoke(request) is None  # tombstone forbids a stale worker's reseal
    print(
        json.dumps(
            {
                "proof": "retired-orphan-operator-input",
                "generation": str(request.generation_id),
                "result": "PREPARED",
                "note": "NOT a GC pass; run separate operator phase",
            }
        )
    )


@pytest.mark.parametrize(
    "checkpoint",
    [
        "before_copy",
        "after_manifest.json",
        "after_layout.json",
        "after_members.json",
        "after_spec.json",
        "after_scene.svg",
        "after_verify",
        "after_fsync",
        "after_placement",
    ],
)
def test_actual_sealer_crash_boundaries_never_accept_partial_output(
    physical_db, checkpoint
):
    config = json.loads(
        Path(
            "/opt/stacksense/diagram-artifacts/deployment/seal-fault-cases.json"
        ).read_bytes()
    )
    generation = next(
        UUID(x["generation_id"])
        for x in config["cases"]
        if x["checkpoint"] == checkpoint
    )
    _, request, _, values = staged(physical_db, generation_id=generation)
    assert invoke(request) is None  # fixed OS sealer died, no verification reply
    with Session(physical_db) as session:
        row = session.get(Generation, generation)
        assert row.state == "STAGING" and row.accepted_reference is None
        assert row.seal_proof is None
    final = STORE_ROOT / "sealed" / str(generation)
    if checkpoint == "after_placement":
        # A complete physical generation without PostgreSQL/M1 acceptance is
        # private. Byte presence is never a READY/readiness claim.
        for name, content in values.items():
            assert (final / name).read_bytes() == content
    else:
        assert not final.exists()
    print(
        json.dumps(
            {
                "proof": "sealer-crash",
                "checkpoint": checkpoint,
                "generation": str(generation),
                "result": "PASS",
            }
        )
    )
