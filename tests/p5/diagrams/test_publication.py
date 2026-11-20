"""Real PG/M1 boundaries; application-only FS fixture is not OS certification."""

# ruff: noqa: F811

import hashlib
import json
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import (
    DiagramTemplate,
)
from backend.platform.delivery.model import Eligibility
from backend.platform.delivery.persistence import DELIVERY_TABLES, DeliveryWorkModel
from backend.platform.delivery.publication import (
    PublicationContractViolation,
    PublicationUnitOfWork,
)
from backend.platform.delivery.repository import SqlAlchemyDeliveryRepository
from backend.platform.diagrams import artifacts
from backend.platform.diagrams.artifact_contracts import SealRequest
from backend.platform.diagrams.artifacts import CandidateArtifactWriter, PrincipalSealer
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import (
    MemberDescriptor,
)
from backend.platform.diagrams.export import svg_bytes
from backend.platform.diagrams.persistence import DiagramGenerationModel as Generation
from backend.platform.diagrams.persistence import DiagramReadPinModel as Pin
from backend.platform.diagrams.repository import (
    DatabaseReadAuthority,
    DiagramPublicationPort,
    DiagramRepository,
    metadata_operation,
    metadata_session,
)
from backend.platform.diagrams.service import DiagramReader
from tests.p5.delivery.test_rollout import budgets
from tests.p5.diagrams.conftest import empty_parts
from tests.p5.diagrams.test_c2_consumers import prepared
from tests.p5.diagrams.test_database import diagram_db  # noqa: F401
from tests.p5.integration.test_delivery_postgres import policy


def lease_for(engine, template, selected_scope=None, *, claim=True):
    initial = prepared(template)
    selected = policy().model_copy(
        update={
            "profiles": tuple(
                (
                    prepared(p.slot.template).descriptor.reference.binding
                    if isinstance(p.slot.template, DiagramTemplate)
                    else p
                )
                for p in policy().profiles
            )
        }
    )
    scope = selected_scope or initial.descriptor.reference.scope
    with engine.begin() as c:
        for table in DELIVERY_TABLES:
            table.create(c, checkfirst=True)
    with Session(engine) as s, s.begin():
        repo = SqlAlchemyDeliveryRepository(s)
        bundle = repo.ensure_bundle(
            scope,
            selected,
            Eligibility.ELIGIBLE,
            revisit_seconds=1,
            runtime_profile=budgets().model_dump(mode="json"),
        )
        work = s.scalar(
            select(DeliveryWorkModel.id).where(
                DeliveryWorkModel.bundle_id == bundle,
                DeliveryWorkModel.kind == "diagram",
                DeliveryWorkModel.template == template.value,
            )
        )
        reservation = repo.reserve(
            work, scope.project_id, reservation_seconds=2, correlation_id="m4-b3-test"
        )
    with Session(engine) as s, s.begin():
        if not claim:
            return reservation[0], initial
        lease = SqlAlchemyDeliveryRepository(s).claim(
            reservation[0],
            initial.descriptor.reference.binding,
            "m4-b3-test",
            max_executions=3,
            lease_seconds=120,
            execution_seconds=180,
        )
    assert lease is not None
    return lease, initial


def candidate(
    engine, template, tmp_path, monkeypatch, *, prepared_value=None, catalog=None
):
    if template != DiagramTemplate.OVERVIEW:
        overview, output, _, _ = candidate(
            engine, DiagramTemplate.OVERVIEW, tmp_path, monkeypatch
        )
        with PublicationUnitOfWork(
            engine, timeout_seconds=5, lock_timeout_ms=1000
        ) as uow:

            def dependencies(session, receipt):
                def validate(item):
                    uow.enlist(DiagramPublicationPort).validate_ready(
                        item.accepted.reference, uow.context(item.prepared.attempt)
                    )

                SqlAlchemyDeliveryRepository(session).coordinate_dependencies(
                    overview.identity.work.bundle_id, validate, tentative=receipt
                )

            uow.complete(
                overview,
                output,
                DiagramPublicationPort,
                stage_dependencies=dependencies,
            )
            uow.commit()
    lease, initial = lease_for(engine, template)
    if prepared_value is not None:
        assert (
            prepared_value.descriptor.manifest.scope
            == initial.descriptor.manifest.scope
        )
        assert (
            prepared_value.descriptor.manifest.binding
            == initial.descriptor.manifest.binding
        )
        initial = prepared_value
    a = lease.identity
    repo = DiagramRepository(engine)
    gid, aid = repo.reserve(a)
    assert repo.reserve(a) == (gid, aid)
    for name in ("staging", "sealed", "locks"):
        (tmp_path / name).mkdir(mode=0o700, exist_ok=True)
    monkeypatch.setattr(artifacts, "STORE_ROOT", tmp_path)
    payloads = {
        "spec": initial.spec.to_bytes(),
        "layout": initial.layout.to_bytes(),
        "members": (catalog or empty_parts(template)[1]).to_bytes(),
        "svg": svg_bytes(initial.spec, initial.layout, DiagramLimits()),
    }
    members = tuple(
        MemberDescriptor.model_validate_json(
            json.dumps(
                dict(
                    member=name,
                    file_name="scene.svg" if name == "svg" else name + ".json",
                    media_type="image/svg+xml" if name == "svg" else "application/json",
                    schema_version="1.0.0",
                    size_bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                )
            )
        )
        for name, data in sorted(payloads.items())
    )
    manifest = initial.descriptor.manifest.model_copy(
        update={
            "scope": a.work.scope,
            "binding": a.work.binding,
            "input_fingerprint": a.work.input_fingerprint,
            "generation_id": gid,
            "artifact_id": aid,
            "members": members,
        }
    )
    data = manifest.to_bytes()
    repo.stage_manifest(a, manifest)
    request = SealRequest(
        protocol=1,
        attempt=a,
        generation_id=gid,
        artifact_id=aid,
        members=members,
        manifest_sha256=hashlib.sha256(data).hexdigest(),
        manifest_size=len(data),
    )
    writer = CandidateArtifactWriter()
    writer.stage(request, data, payloads, monotonic() + 10, lambda: None)

    class Metadata:
        def require_staging(self, request):
            with Session(engine) as s:
                row = s.get(Generation, request.generation_id)
                assert row.state == "STAGING"
                assert row.attempt_snapshot == request.attempt.model_dump(mode="json")
                assert row.manifest_sha256 == request.manifest_sha256

        def require_deleting(self, gid):
            raise PermissionError("not authorized")

    class ApplicationOnlySealer(PrincipalSealer):
        def __init__(self):
            self.metadata, self.limits = Metadata(), DiagramLimits()

    proof = ApplicationOnlySealer().seal(request)
    writer.verify(request, monotonic() + 10)
    output = repo.mark_sealed(a, gid, proof)
    return lease, output, repo, request


@pytest.mark.parametrize("template", list(DiagramTemplate))
def test_real_staging_seal_m1_rollback_commit_and_exact_m5_read(
    diagram_db,
    tmp_path,
    monkeypatch,
    template,  # noqa: F811
):
    engine, _, _ = diagram_db
    lease, output, repo, request = candidate(engine, template, tmp_path, monkeypatch)
    authority = DatabaseReadAuthority(engine, DiagramLimits(), actor_id=None)
    store = artifacts.LocalGeneratedArtifactStore(authority, DiagramLimits())
    for commit in (False, True):
        with PublicationUnitOfWork(
            engine, timeout_seconds=5, lock_timeout_ms=1000
        ) as uow:
            receipt = uow.complete(lease, output, DiagramPublicationPort)
            ref = receipt.accepted.reference
            with Session(engine) as s:
                assert s.get(Generation, ref.generation_id).state == "SEALED_VERIFIED"
            if commit:
                uow.commit()
    result = DiagramReader(store, DiagramLimits()).read_exact(ref.scope, ref)
    assert result.spec.template == template
    assert result.descriptor.reference == ref
    assert repo.prepared(lease.identity, ref.generation_id) == output
    with Session(engine) as s:
        assert not s.scalars(select(Pin)).all()
    # Rehash physical bytes rather than trusting unchanged stored digest labels.
    path = tmp_path / "sealed" / str(ref.generation_id) / "spec.json"
    path.chmod(0o600)  # Test-only ordinary identity; not physical immutability claim.
    path.write_bytes(path.read_bytes().replace(b"1.0.0", b"9.0.0", 1))
    with pytest.raises(ValueError, match="diagram_integrity_error"):
        DiagramReader(store, DiagramLimits()).read_exact(ref.scope, ref)


@pytest.mark.parametrize(
    "field", ["generation_id", "artifact_id", "size_bytes", "attempt"]
)
def test_altered_prepared_descriptor_never_publishes(
    diagram_db, tmp_path, monkeypatch, field
):  # noqa: F811
    engine, _, _ = diagram_db
    lease, output, _, _ = candidate(
        engine, DiagramTemplate.OVERVIEW, tmp_path, monkeypatch
    )
    if field == "attempt":
        altered = output.model_copy(
            update={"attempt": output.attempt.model_copy(update={"fence": 999})}
        )
    else:
        altered = output.model_copy(
            update={
                "candidate": output.candidate.model_copy(
                    update={field: 1 if field == "size_bytes" else uuid4()}
                )
            }
        )
    with (
        pytest.raises((ValueError, RuntimeError)),
        PublicationUnitOfWork(
            engine,
            timeout_seconds=5,
            lock_timeout_ms=1000,
        ) as uow,
    ):
        uow.complete(lease, altered, DiagramPublicationPort)
    with Session(engine) as s:
        assert (
            s.get(Generation, output.candidate.generation_id).state == "SEALED_VERIFIED"
        )


@pytest.mark.parametrize("operation", ["commit", "rollback", "close"])
def test_m4_guard_violation_is_sticky_even_when_caught(
    diagram_db, tmp_path, monkeypatch, operation
):
    engine, _, _ = diagram_db
    lease, output, _, _ = candidate(
        engine, DiagramTemplate.OVERVIEW, tmp_path, monkeypatch
    )

    class MisbehavingPort(DiagramPublicationPort):
        def publish_prepared(self, prepared, context):
            try:
                getattr(self.session, operation)()
            except PublicationContractViolation:
                pass
            return super().publish_prepared(prepared, context)

    with (
        pytest.raises(PublicationContractViolation),
        PublicationUnitOfWork(engine, timeout_seconds=5, lock_timeout_ms=1000) as uow,
    ):
        uow.complete(lease, output, MisbehavingPort)
    with Session(engine) as s:
        assert (
            s.get(Generation, output.candidate.generation_id).state == "SEALED_VERIFIED"
        )


def test_pin_lifetime_and_cleanup_reject_accepted_generation(
    diagram_db, tmp_path, monkeypatch
):
    from backend.platform.delivery.ownership import SqlAlchemyAttemptRetirementReader

    engine, _, _ = diagram_db
    lease, output, repo, _ = candidate(
        engine, DiagramTemplate.OVERVIEW, tmp_path, monkeypatch
    )
    with PublicationUnitOfWork(engine, timeout_seconds=5, lock_timeout_ms=1000) as uow:
        ref = uow.complete(lease, output, DiagramPublicationPort).accepted.reference
        uow.commit()
    authority = DatabaseReadAuthority(engine, DiagramLimits(), actor_id=None)
    handle = artifacts.LocalGeneratedArtifactStore(
        authority, DiagramLimits()
    ).open_exact(ref.scope, ref, "spec")
    try:
        with Session(engine) as s:
            assert len(s.scalars(select(Pin)).all()) == 1
        with pytest.raises(ValueError):
            repo.reserve_deletion(
                lease.identity,
                ref.generation_id,
                SqlAlchemyAttemptRetirementReader(
                    engine, timeout_seconds=2, lock_timeout_ms=1000
                ),
                uuid4(),
                DiagramLimits(),
            )
    finally:
        handle.close()
    with Session(engine) as s:
        assert not s.scalars(select(Pin)).all()
    authority.recheck(ref.scope, ref)


def test_publication_and_prepared_reads_do_not_load_fonts_or_invoke_sealer(
    diagram_db, tmp_path, monkeypatch
):
    from backend.platform.diagrams.fonts import DiagramFonts

    engine, _, _ = diagram_db
    lease, output, _, _ = candidate(
        engine, DiagramTemplate.OVERVIEW, tmp_path, monkeypatch
    )

    def forbidden(*args, **kwargs):
        pytest.fail("publication/read invoked build-time external capability")

    monkeypatch.setattr(DiagramFonts, "__init__", forbidden)
    monkeypatch.setattr(CandidateArtifactWriter, "seal", forbidden)
    monkeypatch.setattr(CandidateArtifactWriter, "verify", forbidden)
    with PublicationUnitOfWork(engine, timeout_seconds=5, lock_timeout_ms=1000) as uow:
        ref = uow.complete(lease, output, DiagramPublicationPort).accepted.reference
        uow.commit()
    store = artifacts.LocalGeneratedArtifactStore(
        DatabaseReadAuthority(engine, DiagramLimits(), actor_id=None), DiagramLimits()
    )
    assert (
        DiagramReader(store, DiagramLimits())
        .read_exact(ref.scope, ref)
        .descriptor.reference
        == ref
    )


def test_owned_metadata_deadline_cancels_its_real_query_not_other_connections(
    diagram_db,
):
    from sqlalchemy import text

    engine, _, _ = diagram_db
    before = monotonic()
    with (
        pytest.raises(TimeoutError),
        metadata_operation(before + 1.2),
        metadata_session(engine) as s,
    ):
        s.execute(text("SELECT pg_sleep(10)"))
    assert monotonic() - before < 2
    with engine.connect() as c:
        assert c.scalar(text("SELECT 1")) == 1


def test_project_admission_is_exclusive_and_releases_after_failure(diagram_db):
    engine, _, _ = diagram_db
    repo = DiagramRepository(engine)
    project = uuid4()
    with repo.build_admission(project, DiagramLimits()):
        with (
            pytest.raises(ValueError, match="diagram_store_unavailable"),
            repo.build_admission(project, DiagramLimits()),
        ):
            pytest.fail("same project admitted concurrently")
        with repo.build_admission(uuid4(), DiagramLimits()):
            pass
    with repo.build_admission(project, DiagramLimits()):
        pass


def test_same_attempt_reservation_is_unique_across_connections(diagram_db):
    from concurrent.futures import ThreadPoolExecutor

    engine, _, _ = diagram_db
    lease, _ = lease_for(engine, DiagramTemplate.OVERVIEW)
    repo = DiagramRepository(engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda _: repo.reserve(lease.identity), range(2)))
    assert rows[0] == rows[1]
    with Session(engine) as s:
        assert len(s.scalars(select(Generation)).all()) == 1


def test_retired_orphan_gc_is_reserved_read_back_and_idempotent(
    diagram_db,
    tmp_path,
    monkeypatch,
):
    """Actual FS/PG/public M1 retirement; clock advances only in test policy."""
    from datetime import datetime, timedelta

    from backend.platform.delivery.ownership import SqlAlchemyAttemptRetirementReader
    from backend.platform.diagrams import repository as module
    from backend.platform.diagrams.artifact_runtime.seal_generation import (
        DatabaseSealerMetadata,
        MetadataConfig,
    )
    from backend.platform.diagrams.service import DiagramCleanupService

    engine, schema, url = diagram_db
    lease, output, repo, request = candidate(
        engine, DiagramTemplate.OVERVIEW, tmp_path, monkeypatch
    )
    with Session(engine) as s, s.begin():
        assert SqlAlchemyDeliveryRepository(s).finish_failure(
            lease,
            code="test_retired_orphan",
            retryable=False,
            max_executions=3,
            retry_seconds=1,
        )
    retirement = SqlAlchemyAttemptRetirementReader(
        engine, timeout_seconds=2, lock_timeout_ms=1000
    )
    actor = uuid4()
    limits = DiagramLimits(orphan_grace_seconds=3600)
    with pytest.raises(ValueError):
        repo.reserve_deletion(
            lease.identity, request.generation_id, retirement, actor, limits
        )

    class AdvancedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz) + timedelta(hours=2)

    monkeypatch.setattr(module, "datetime", AdvancedClock)
    config = MetadataConfig.model_validate_json(
        json.dumps(
            dict(
                version="1.0.0",
                database_url=url,
                schema=schema,
                profiles=[],
            )
        )
    )
    metadata = object.__new__(DatabaseSealerMetadata)
    metadata.initialize(config, cleanup=True)

    class ApplicationOnlySealer(PrincipalSealer):
        def __init__(self):
            self.metadata, self.limits = metadata, limits

    class ApplicationOnlyGC:
        def delete_reserved(self, gid, deadline):
            assert monotonic() < deadline
            metadata.require_deleting(gid)
            with pytest.raises(ValueError):
                # Retired tombstone forbids a stale worker resealing.
                ApplicationOnlySealer().seal(request)
            ApplicationOnlySealer().delete_reserved(gid)

    try:
        service = DiagramCleanupService(repo, retirement, ApplicationOnlyGC(), limits)
        service.delete_retired(lease.identity, request.generation_id, actor)
        service.delete_retired(lease.identity, request.generation_id, actor)
    finally:
        metadata.close()
    assert not (tmp_path / "sealed" / str(request.generation_id)).exists()
    with Session(engine) as s:
        assert s.get(Generation, request.generation_id).state == "DELETED"
