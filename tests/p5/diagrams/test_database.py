"""Disposable real PostgreSQL proofs; never application .env or production DDL."""

import os
from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import DiagramTemplate
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import CanonicalDiagramScope
from backend.platform.diagrams.persistence import (
    DiagramGenerationModel as Generation,
)
from backend.platform.diagrams.persistence import (
    DiagramResourceModel as Resource,
)
from backend.platform.diagrams.persistence import (
    install_prototype,
)
from backend.platform.diagrams.query import SourceBudget, canonical_read_source
from backend.platform.projects.infra.base import Base
from tests.p5.delivery.test_contracts import attempt


@pytest.fixture
def diagram_db():
    value = os.environ.get("P5_TEST_DATABASE_URL")
    if not value:
        pytest.skip(
            "P5_TEST_DATABASE_URL required for disposable real PostgreSQL proof"
        )
    url = make_url(value)
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith(
        "stacksense_p5_b2_"
    ):
        pytest.fail("explicit isolated P5 PostgreSQL required")
    root = create_engine(
        url.set(drivername="postgresql+psycopg"), connect_args={"connect_timeout": 5}
    )
    schema = "p5_diagram_" + uuid4().hex
    with root.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        install_prototype(connection, schema)
    engine = root.execution_options(schema_translate_map={None: schema})
    try:
        yield engine, schema, value
    finally:
        with root.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()


def stage(engine, value=None, owner=None):
    from tests.p5.diagrams.test_c2_consumers import prepared

    p = value or prepared(DiagramTemplate.OVERVIEW)
    owner = owner or attempt(
        p.descriptor.reference.binding, p.descriptor.reference.scope
    )
    owner = owner.model_copy(
        update={
            "candidate_id": p.descriptor.reference.candidate_id,
            "work": owner.work.model_copy(
                update={"input_fingerprint": p.descriptor.reference.input_fingerprint}
            ),
        }
    )
    work = owner.work
    resource_id = p.descriptor.reference.resource_id
    generation_id = p.descriptor.reference.generation_id
    with Session(engine) as session, session.begin():
        session.add(
            Resource(
                id=resource_id,
                project_id=work.scope.project_id,
                architecture_version_id=work.scope.architecture_version_id,
                template=p.spec.template.value,
                canonical_digest=work.scope.canonical_digest,
                input_fingerprint=work.input_fingerprint,
                binding_fingerprint="a" * 64,
                scope=work.scope.model_dump(mode="json"),
                binding=work.binding.model_dump(mode="json"),
            )
        )
        session.flush()
        session.add(
            Generation(
                id=generation_id,
                resource_id=resource_id,
                project_id=work.scope.project_id,
                architecture_version_id=work.scope.architecture_version_id,
                template=p.spec.template.value,
                work_id=work.work_id,
                attempt_id=owner.attempt_id,
                candidate_id=owner.candidate_id,
                artifact_id=p.descriptor.reference.artifact_id,
                attempt_ordinal=owner.ordinal,
                fence=owner.fence,
                dispatch_epoch=owner.dispatch_epoch,
                attempt_snapshot=owner.model_dump(mode="json"),
                input_fingerprint=work.input_fingerprint,
                binding_fingerprint="a" * 64,
                state="STAGING",
            )
        )
    return resource_id, generation_id


def test_prototype_committed_staging_and_rollback_use_separate_connections(diagram_db):
    engine, _, _ = diagram_db
    _, generation = stage(engine)
    with Session(engine) as first, Session(engine) as second:
        first.execute(
            update(Generation)
            .where(Generation.id == generation)
            .values(manifest={"private": "uncommitted"})
        )
        assert second.get(Generation, generation).manifest is None
        first.rollback()
    with Session(engine) as session:
        assert session.get(Generation, generation).manifest is None


def test_prototype_cannot_accept_without_proof_or_mutate_identity(diagram_db):
    engine, _, _ = diagram_db
    resource, generation = stage(engine)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            update(Generation)
            .where(Generation.id == generation)
            .values(state="ACCEPTED")
        )
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            update(Generation).where(Generation.id == generation).values(fence=2)
        )
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            update(Resource)
            .where(Resource.id == resource)
            .values(accepted_generation_id=generation)
        )


def test_foreign_scope_rejected_and_staging_never_pin_visible(diagram_db):
    engine, _, _ = diagram_db
    _, generation = stage(engine)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            update(Generation)
            .where(Generation.id == generation)
            .values(project_id=uuid4())
        )


def verified_metadata(engine, generation, value=None, actual_proof=None):
    """Metadata-only fixture. Does NOT certify filesystem bytes or M1 acceptance."""
    from hashlib import sha256

    from tests.p5.diagrams.test_c2_consumers import prepared

    p = value or prepared(DiagramTemplate.OVERVIEW)
    manifest = p.descriptor.manifest
    ref = p.descriptor.reference
    with Session(engine) as session:
        row = session.get(Generation, generation)
        owner = row.attempt_id
    now = datetime.now(UTC)
    proof = dict(
        verification_version="1.0.0",
        manifest_sha256=sha256(manifest.to_bytes()).hexdigest(),
        member_set_digest="a" * 64,
        physical_object_id="fixture-not-physical-proof",
        sealed_at=now.isoformat(),
    )
    if actual_proof is not None:
        proof = actual_proof
    with engine.begin() as connection:
        connection.execute(
            update(Generation)
            .where(Generation.id == generation)
            .values(
                state="SEALED_VERIFIED",
                manifest=manifest.model_dump(mode="json"),
                manifest_sha256=proof["manifest_sha256"],
                spec_digest=manifest.semantic_digest,
                layout_digest=manifest.layout_digest,
                membership_digest=manifest.membership_digest,
                manifest_size=len(manifest.to_bytes()),
                total_member_bytes=sum(m.size_bytes for m in manifest.members),
                seal_proof=proof,
                sealed_at=now,
            )
        )
    return ref, dict(
        transaction_id=str(uuid4()),
        attempt_id=str(owner),
        reference=ref.model_dump(mode="json"),
    )


def test_seal_fields_immutable_and_acceptance_rollback_invisible(diagram_db):
    engine, _, _ = diagram_db
    resource, generation = stage(engine)
    ref, context = verified_metadata(engine, generation)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            update(Generation)
            .where(Generation.id == generation)
            .values(spec_digest="b" * 64)
        )
    with engine.connect() as publisher, engine.connect() as independent:
        transaction = publisher.begin()
        publisher.execute(
            update(Generation)
            .where(Generation.id == generation)
            .values(
                state="ACCEPTED",
                accepted_reference=ref.model_dump(mode="json"),
                acceptance_context=context,
                accepted_at=datetime.now(UTC),
            )
        )
        publisher.execute(
            update(Resource)
            .where(Resource.id == resource)
            .values(accepted_generation_id=generation)
        )
        assert (
            independent.scalar(
                select(Resource.accepted_generation_id).where(Resource.id == resource)
            )
            is None
        )
        transaction.rollback()
    with Session(engine) as session:
        assert session.get(Generation, generation).state == "SEALED_VERIFIED"


def test_accepted_metadata_is_terminal_and_cannot_be_deleted(diagram_db):
    engine, _, _ = diagram_db
    resource, generation = stage(engine)
    ref, context = verified_metadata(engine, generation)
    with engine.begin() as connection:
        connection.execute(
            update(Generation)
            .where(Generation.id == generation)
            .values(
                state="ACCEPTED",
                accepted_reference=ref.model_dump(mode="json"),
                acceptance_context=context,
                accepted_at=datetime.now(UTC),
            )
        )
        connection.execute(
            update(Resource)
            .where(Resource.id == resource)
            .values(accepted_generation_id=generation)
        )
    from sqlalchemy import delete

    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(delete(Generation).where(Generation.id == generation))
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            update(Generation)
            .where(Generation.id == generation)
            .values(state="DELETING")
        )
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            update(Resource)
            .where(Resource.id == resource)
            .values(canonical_digest="b" * 64)
        )


def test_json_null_and_empty_object_are_not_seal_proofs(diagram_db):
    engine, _, _ = diagram_db
    _, generation = stage(engine)
    for proof in (None, {}):
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                update(Generation)
                .where(Generation.id == generation)
                .values(
                    state="SEALED_VERIFIED",
                    manifest={},
                    seal_proof=proof,
                    manifest_sha256="a" * 64,
                    spec_digest="a" * 64,
                    layout_digest="a" * 64,
                    membership_digest="a" * 64,
                    manifest_size=1,
                    total_member_bytes=1,
                    sealed_at=datetime.now(UTC),
                )
            )
    from datetime import timedelta

    from backend.platform.diagrams.persistence import DiagramReadPinModel as Pin

    now = datetime.now(UTC)
    with pytest.raises(DBAPIError), Session(engine) as session, session.begin():
        session.add(
            Pin(
                id=uuid4(),
                generation_id=generation,
                actor_id=uuid4(),
                purpose="api",
                token_hash="a" * 64,
                created_at=now,
                expires_at=now + timedelta(seconds=120),
            )
        )


def publish_canonical(engine):
    # Existing frozen fixture helpers populate isolated input, never runtime
    # imports/private access inside the M4 public source adapter.
    from backend.platform.analysis.architecture.persistence import (
        SqlAlchemyArchitectureRepository,
    )
    from tests.p3.analysis.test_m4_persistence import _analysis, _document, _validated

    Base.metadata.create_all(engine)
    document = _document()
    with Session(engine) as session:
        _analysis(session, document)
        repository = SqlAlchemyArchitectureRepository(session)
        repository.reserve_version(document)
        repository.mark_validating(
            document.architecture_version_id, document.analysis_id
        )
        repository.publish(_validated(document))
        session.commit()
    return CanonicalDiagramScope(
        project_id=document.project_id,
        repository_id=document.repository_id,
        analysis_id=document.analysis_id,
        snapshot_id=document.snapshot_id,
        architecture_version_id=document.architecture_version_id,
        sequence_number=1,
        canonical_digest=document.content_digest,
        architecture_schema_version="1.0.0",
        ir_schema_version="1.0.0",
    )


def test_real_public_source_pages_and_final_header(diagram_db):
    engine, schema, url = diagram_db
    scope = publish_canonical(engine)
    budget = SourceBudget(DiagramLimits(), monotonic() + 15, lambda: None)
    with canonical_read_source(url, budget, read_schema=schema) as source:
        entities = list(source.scan("entities", scope, budget))
        assert len(entities) > 0
        assert all(e.record.id is not None for e in entities)


@pytest.mark.parametrize("template", list(DiagramTemplate))
def test_b2_builder_from_real_public_canonical_pages(diagram_db, template):
    from backend.platform.diagrams.builders import build_from_source
    from backend.platform.diagrams.validation import DiagramValidator

    engine, schema, url = diagram_db
    scope = publish_canonical(engine)
    results = []
    for _ in range(2):
        budget = SourceBudget(DiagramLimits(), monotonic() + 15, lambda: None)
        with canonical_read_source(url, budget, read_schema=schema) as source:
            result = build_from_source(source, scope, template, budget)
            DiagramValidator(budget.limits).semantic(result.spec, result.catalog)
            assert result.spec.scope == scope
            assert result.spec.coverage.scan_exhausted
            assert all(count == 1 for count in budget.passes.values())
            results.append(result.spec.to_bytes())
    assert results[0] == results[1]


def test_owned_provider_enforces_server_read_only_not_only_convention(
    diagram_db, monkeypatch
):
    engine, schema, url = diagram_db
    scope = publish_canonical(engine)
    import backend.platform.diagrams.query as module

    original = module.get_architecture_query_service
    captured = []

    def provider(*, session):
        captured.append(session)
        return original(session=session)

    monkeypatch.setattr(module, "get_architecture_query_service", provider)
    budget = SourceBudget(DiagramLimits(), monotonic() + 15, lambda: None)
    with canonical_read_source(url, budget, read_schema=schema) as source:
        source.header(scope, budget)
        assert captured[0].scalar(text("SHOW transaction_read_only")) == "on"
        with pytest.raises(DBAPIError) as rejected:
            captured[0].execute(update(Resource).values(accepted_generation_id=None))
        assert rejected.value.orig.sqlstate == "25006"


def test_owned_deadline_terminates_real_blocked_query_without_cancelling_others(
    diagram_db,
):
    engine, schema, url = diagram_db
    scope = publish_canonical(engine)
    from backend.platform.analysis.architecture.persistence import (
        ArchitectureVersionModel,
    )

    table = ArchitectureVersionModel.__tablename__
    with engine.connect() as blocker:
        transaction = blocker.begin()
        blocker.execute(
            text(f'LOCK TABLE "{schema}"."{table}" IN ACCESS EXCLUSIVE MODE')
        )
        before = monotonic()
        budget = SourceBudget(DiagramLimits(lock_seconds=3), before + 2, lambda: None)
        with pytest.raises((TimeoutError, DBAPIError)):
            with canonical_read_source(url, budget, read_schema=schema) as source:
                source.header(scope, budget)
        assert monotonic() - before < 4
        transaction.rollback()
    with engine.connect() as independent:
        assert independent.scalar(text("SELECT 1")) == 1
        assert (
            independent.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE application_name LIKE 'stacksense.diagram.read.%' "
                    "AND state='active'"
                )
            )
            == 0
        )
