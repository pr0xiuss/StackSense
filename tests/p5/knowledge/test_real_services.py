"""Real isolated PG + ES acceptance. No fake physical guarantees.

Explicit M2_TEST_ES_* settings and P5_TEST_DATABASE_URL are required. Never
read deployment credentials or fall back to the application database.
"""

import os
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform.delivery.contracts import (
    HandlerProfile,
    WorkExecutionContext,
    WorkKind,
    WorkSlot,
    execution_control,
)
from backend.platform.delivery.model import Eligibility
from backend.platform.delivery.persistence import DeliveryOutputModel as Output
from backend.platform.delivery.persistence import DeliveryWorkModel as Work
from backend.platform.delivery.publication import PublicationUnitOfWork
from backend.platform.delivery.repository import SqlAlchemyDeliveryRepository
from backend.platform.knowledge.contracts import SearchRequest
from backend.platform.knowledge.elasticsearch import (
    SEARCH_INDEX_MAPPINGS,
    SEARCH_INDEX_SETTINGS,
)
from backend.platform.knowledge.es_backend import (
    ElasticsearchBackend,
)
from backend.platform.knowledge.persistence import SEARCH_TABLES
from backend.platform.knowledge.projection import KnowledgeProjector
from backend.platform.knowledge.reader import SearchReader
from backend.platform.knowledge.repository import (
    SearchPublicationPort,
    SqlAlchemySearchRepository,
)
from backend.platform.knowledge.service import SearchWorkHandler
from backend.platform.knowledge.verification import SearchVerifier
from tests.p5.integration.test_delivery_postgres import policy
from tests.p5.knowledge.conftest import make_test_document, make_test_profile


@pytest.fixture
def physical_backend():
    endpoint = os.environ.get("M2_TEST_ES_URL")
    if endpoint is None:
        pytest.skip("Explicit isolated M2_TEST_ES_URL required for physical ES proofs")
    if endpoint != "https://localhost:19200":
        pytest.fail(
            "M2 physical experiment requires its isolated TLS loopback container"
        )
    from elasticsearch import Elasticsearch

    admin = Elasticsearch(
        endpoint,
        basic_auth=("elastic", os.environ["M2_TEST_ES_ADMIN_PASSWORD"]),
        ca_certs=os.environ["M2_TEST_ES_CA"],
        request_timeout=15,
        max_retries=0,
    )
    created, key_ids, clients, encoded_keys = [], [], [], []
    privileges = (
        ["create_index"],
        ["create_doc"],
        ["manage"],
        ["read", "view_index_metadata"],
        ["delete_index"],
    )
    for role_index, permissions in enumerate(privileges):
        key = admin.security.create_api_key(
            name="m2-isolated-" + uuid4().hex,
            expiration="1h",
            role_descriptors={
                "isolated": {
                    "cluster": ["monitor"] if role_index == 0 else [],
                    "indices": [
                        {"names": ["stacksense-search-*"], "privileges": permissions}
                    ],
                }
            },
        )
        key_ids.append(key["id"])
        encoded_keys.append(key["encoded"])
        clients.append(
            Elasticsearch(
                endpoint,
                api_key=key["encoded"],
                ca_certs=os.environ["M2_TEST_ES_CA"],
                request_timeout=15,
                max_retries=0,
            )
        )

    import json

    from backend.platform.knowledge.configuration import configured_backend

    binding = HandlerProfile(
        slot=WorkSlot(kind=WorkKind.SEARCH), profile=make_test_profile()
    )
    raw = json.dumps(
        {
            "binding": binding.model_dump(mode="json"),
            "endpoint": endpoint,
            "ca_certs": os.environ["M2_TEST_ES_CA"],
            "server_version": "9.5.6",
            "client_version": "9.5.1",
            **dict(
                zip(
                    (
                        "provisioner_api_key",
                        "writer_api_key",
                        "sealer_api_key",
                        "reader_api_key",
                        "cleanup_api_key",
                    ),
                    encoded_keys,
                    strict=True,
                )
            ),
            "request_seconds": 15,
            "bulk_documents": 25,
            "bulk_bytes": 1048576,
            "readback_page": 20,
            "pit_seconds": 120,
            "cancel_seconds": 0.5,
            "status_page_size": 10,
            "status_max_pages": 10,
            "index_settings": SEARCH_INDEX_SETTINGS,
        }
    )
    # Exercise production compatibility/configuration, not just adapter methods.
    configured = configured_backend(raw)
    for client in clients:
        client.close()
    clients = list(vars(configured.clients).values())

    class TrackedBackend(ElasticsearchBackend):
        deployment_raw = raw

        def create_index(self, index_name, settings, mappings):
            created.append(index_name)
            return super().create_index(index_name, settings, mappings)

    backend = TrackedBackend(configured.clients, configured.budgets)
    try:
        yield backend, admin
    finally:
        for name in created:
            if admin.indices.exists(index=name):
                admin.indices.delete(index=name)
        admin.security.invalidate_api_key(ids=key_ids)
        for client in clients:
            client.close()
        configured_backend.cache_clear()
        admin.close()


@pytest.fixture
def search_engine(delivery_engine):
    for table in SEARCH_TABLES:
        table.create(delivery_engine)
    return delivery_engine


def indexed_projection(backend):
    document, scope = make_test_document()
    profile = make_test_profile()
    projection = KnowledgeProjector().project(document, scope, profile)
    generation = uuid4()
    name = "stacksense-search-it-" + generation.hex
    physical = backend.create_index(name, SEARCH_INDEX_SETTINGS, SEARCH_INDEX_MAPPINGS)
    rows = [
        r.to_stored_envelope(generation_id=generation, index_uuid=physical)
        for r in projection.records
    ]
    assert backend.bulk_index_records(name, rows).failed == 0
    return scope, profile, projection, generation, name, physical, rows


def test_real_seal_excludes_stale_writer_and_exact_readback(physical_backend):
    backend, admin = physical_backend
    scope, profile, projection, generation, name, physical, rows = indexed_projection(
        backend
    )
    backend.drain_and_seal_index(name)
    assert backend.bulk_index_records(name, rows).failed == len(rows)
    from elasticsearch import AuthorizationException

    with pytest.raises(AuthorizationException):
        backend.clients.writer.indices.put_settings(
            index=name, settings={"index.blocks.write": False}
        )
    result = SearchVerifier(backend).verify(
        scope=scope,
        profile=profile,
        candidate_id=uuid4(),
        attempt_id=uuid4(),
        generation_id=generation,
        index_name=name,
        index_uuid=physical,
        expected_projection=projection,
    )
    assert result.verified
    assert backend.inspect_index(name)["sealed"]


@pytest.mark.parametrize("field", ["title", "project_id", "generation_id"])
def test_real_verifier_recomputes_payload_not_digest_labels(physical_backend, field):
    backend, admin = physical_backend
    scope, profile, projection, generation, name, physical, rows = indexed_projection(
        backend
    )
    changed = {**rows[0], field: str(uuid4())}
    admin.index(index=name, id=changed["storage_key"], document=changed)
    backend.drain_and_seal_index(name)
    result = SearchVerifier(backend).verify(
        scope=scope,
        profile=profile,
        candidate_id=uuid4(),
        attempt_id=uuid4(),
        generation_id=generation,
        index_name=name,
        index_uuid=physical,
        expected_projection=projection,
    )
    assert not result.verified


def test_real_inflight_writer_cannot_change_generation_after_seal(physical_backend):
    import hashlib
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    backend, _ = physical_backend
    _, _, _, _, name, _, rows = indexed_projection(backend)
    writes = []
    for index in range(1000):
        row = {
            **rows[0],
            "storage_key": hashlib.sha256(f"seal-race-{index}".encode()).hexdigest(),
        }
        writes.append(row)
    started = Event()

    def write():
        started.set()
        return backend.bulk_index_records(name, writes)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(write)
        assert started.wait(5)
        backend.drain_and_seal_index(name)
        sealed_inventory = sorted(
            row["storage_key"] for row in backend.iter_records(name)
        )
        future.result(timeout=15)
    assert sealed_inventory == sorted(
        row["storage_key"] for row in backend.iter_records(name)
    )
    assert backend.inspect_index(name)["sealed"] is True


def test_real_m1_to_m2_staging_publication_and_exact_search(
    search_engine, physical_backend
):
    backend, admin = physical_backend
    document, scope = make_test_document()
    profile = make_test_profile()
    binding = HandlerProfile(slot=WorkSlot(kind=WorkKind.SEARCH), profile=profile)
    selected = policy()
    selected = selected.model_copy(
        update={
            "profiles": tuple(
                binding if p.slot.kind == WorkKind.SEARCH else p
                for p in selected.profiles
            )
        }
    )
    with Session(search_engine) as session, session.begin():
        repo = SqlAlchemyDeliveryRepository(session)
        bundle = repo.ensure_bundle(
            scope, selected, Eligibility.ELIGIBLE, revisit_seconds=1
        )
        work_id = session.scalar(
            select(Work.id).where(
                Work.bundle_id == bundle, Work.kind == WorkKind.SEARCH
            )
        )
        payload, _ = repo.reserve(
            work_id, scope.project_id, reservation_seconds=2, correlation_id="real-m2"
        )
    with Session(search_engine) as session, session.begin():
        lease = SqlAlchemyDeliveryRepository(session).claim(
            payload,
            binding,
            "real-m2",
            max_executions=3,
            lease_seconds=60,
            execution_seconds=120,
        )
    assert lease is not None
    # Producer transaction/connection has committed and closed BEFORE M1 opens
    # its independent publication UoW. This reproduces the original staging bug.
    with Session(search_engine) as staging:
        prepared = SearchWorkHandler(
            backend=backend,
            repository=SqlAlchemySearchRepository(staging),
            document_loader=lambda _: document,
        ).execute(
            WorkExecutionContext(
                attempt=lease.identity,
                deadline=lease.deadline,
                control=execution_control(lambda: None),
            )
        )
    with PublicationUnitOfWork(
        search_engine, timeout_seconds=10, lock_timeout_ms=1000
    ) as uow:
        receipt = uow.complete(
            lease,
            prepared,
            lambda session: SearchPublicationPort(session, backend=backend),
        )
        with Session(search_engine) as observer:
            assert observer.scalar(select(Output.id)) is None
            assert (
                SqlAlchemySearchRepository(observer).get_active_generation(
                    project_id=scope.project_id,
                    architecture_version_id=scope.architecture_version_id,
                )
                is None
            )
        uow.commit()
    actor = uuid4()
    with Session(search_engine) as reading:
        reader = SearchReader(
            backend=backend,
            repository=SqlAlchemySearchRepository(reading),
            cursor_secret="real-test-only-key-" * 3,
            cursor_ttl_seconds=120,
        )
        page = reader.search(
            SearchRequest(
                project_id=scope.project_id,
                architecture_version_id=scope.architecture_version_id,
                q="Service",
                limit=1,
            ),
            actor_id=actor,
        )
        assert page.generation_id == receipt.accepted.reference.generation_id
        assert page.items
        assert page.scope == scope
        reading.commit()
    assert page.next_cursor is not None
    seen = {item.knowledge_key for item in page.items}
    cursor = page.next_cursor
    for _ in range(page.total_hits):
        if cursor is None:
            break
        with Session(search_engine) as reading:
            reader = SearchReader(
                backend=backend,
                repository=SqlAlchemySearchRepository(reading),
                cursor_secret="real-test-only-key-" * 3,
                cursor_ttl_seconds=120,
            )
            next_page = reader.search(
                SearchRequest(
                    project_id=scope.project_id,
                    architecture_version_id=scope.architecture_version_id,
                    q="Service",
                    limit=1,
                    cursor=cursor,
                ),
                actor_id=actor,
            )
            assert next_page.generation_id == page.generation_id
            assert next_page.items[0].knowledge_key not in seen
            seen.update(item.knowledge_key for item in next_page.items)
            cursor = next_page.next_cursor
            reading.commit()
    assert cursor is None
    assert len(seen) == page.total_hits
    # This fixture is restricted to the disposable loopback service above.
    # Reconnect after a real ES process restart; accepted PostgreSQL metadata is
    # not recreated and the published generation remains the same exact index.
    import subprocess
    from time import monotonic, sleep

    subprocess.run(
        ["docker", "restart", "stacksense-m2-spike-20261117"],
        check=True,
        capture_output=True,
        timeout=60,
    )
    # Node HTTP availability precedes security and data-shard recovery. This is
    # an isolated restart-test startup allowance, not a production query budget.
    restart_deadline = monotonic() + 120
    while True:
        try:
            health = admin.cluster.health(wait_for_status="yellow", timeout="1s")
            if (
                not health["timed_out"]
                and health["unassigned_primary_shards"] == 0
                and admin.security.authenticate()["username"] == "elastic"
                and backend.inspect_index(
                    f"stacksense-search-{scope.project_id.hex}-{prepared.candidate.generation_id.hex}"
                )["sealed"]
            ):
                break
        except Exception:
            pass  # Only readiness probing, bounded below; not test success.
        if monotonic() >= restart_deadline:
            pytest.fail("Isolated ES did not recover after restart")
        sleep(0.5)
    with Session(search_engine) as reading:
        reader = SearchReader(
            backend=backend,
            repository=SqlAlchemySearchRepository(reading),
            cursor_secret="real-test-only-key-" * 3,
            cursor_ttl_seconds=120,
        )
        recovered = reader.search(
            SearchRequest(
                project_id=scope.project_id,
                architecture_version_id=scope.architecture_version_id,
                q="Service",
                limit=10,
            ),
            actor_id=actor,
        )
        assert recovered.generation_id == receipt.accepted.reference.generation_id
        assert len(recovered.items) == len(seen)


def test_production_registry_loads_published_model_and_enlists_c0(
    search_engine, physical_backend, monkeypatch
):
    from types import SimpleNamespace

    from pydantic import SecretStr

    from backend.platform.analysis.architecture.persistence import (
        SqlAlchemyArchitectureRepository,
    )
    from backend.platform.delivery.source import PublishedVersionReader
    from backend.platform.delivery_composition import get_output_handler_registry
    from backend.platform.graph.source import SqlAlchemyPublishedArchitectureSource
    from backend.platform.projects.infra.base import Base
    from tests.p3.analysis.test_m4_persistence import _analysis, _document, _validated

    backend, _ = physical_backend
    Base.metadata.create_all(search_engine)
    document = _document()
    with Session(search_engine) as session:
        _analysis(session, document)
        source = SqlAlchemyArchitectureRepository(session)
        source.reserve_version(document)
        source.mark_validating(document.architecture_version_id, document.analysis_id)
        source.publish(_validated(document))
        session.commit()
        header = (
            SqlAlchemyPublishedArchitectureSource(session)
            .list_published(limit=1)
            .items[0]
        )
        assert header.architecture_version_id == document.architecture_version_id
        scope = PublishedVersionReader.scope(header)
    monkeypatch.setattr(
        "backend.platform.config.get_settings",
        lambda: SimpleNamespace(
            search_deployment_json=SecretStr(backend.deployment_raw)
        ),
    )
    monkeypatch.setattr(
        "backend.platform.dependency_injection.get_database_engine",
        lambda: search_engine,
    )
    monkeypatch.setattr(
        "backend.platform.knowledge.dependencies.get_search_backend", lambda: backend
    )
    registry = get_output_handler_registry()
    binding = registry.profiles[0]
    selected = policy()
    selected = selected.model_copy(
        update={
            "profiles": tuple(
                binding if p.slot == binding.slot else p for p in selected.profiles
            )
        }
    )
    with Session(search_engine) as session, session.begin():
        repo = SqlAlchemyDeliveryRepository(session)
        bundle = repo.ensure_bundle(
            scope, selected, Eligibility.ELIGIBLE, revisit_seconds=1
        )
        work_id = session.scalar(
            select(Work.id).where(
                Work.bundle_id == bundle,
                Work.kind == WorkKind.SEARCH,
                Work.is_current.is_(True),
            )
        )
        payload, _ = repo.reserve(
            work_id,
            scope.project_id,
            reservation_seconds=2,
            correlation_id="production-registry",
        )
    with Session(search_engine) as session, session.begin():
        lease = SqlAlchemyDeliveryRepository(session).claim(
            payload,
            binding,
            "production-registry",
            max_executions=3,
            lease_seconds=60,
            execution_seconds=120,
        )
    assert lease is not None
    prepared = registry.execute(
        WorkExecutionContext(
            attempt=lease.identity,
            deadline=lease.deadline,
            control=execution_control(lambda: None),
        )
    )
    # Dedicated staging Session is already closed before the real C0 UoW.
    with PublicationUnitOfWork(
        search_engine, timeout_seconds=10, lock_timeout_ms=1000
    ) as uow:
        accepted = uow.complete(
            lease, prepared, registry.resolve(binding).publication_factory
        )
        uow.commit()
    with Session(search_engine) as session:
        page = SearchReader(
            backend=backend,
            repository=SqlAlchemySearchRepository(session),
            cursor_secret="production-registry-test-secret-" * 2,
            cursor_ttl_seconds=120,
        ).search(
            SearchRequest(
                project_id=scope.project_id,
                architecture_version_id=scope.architecture_version_id,
                q="service",
            ),
            actor_id=uuid4(),
        )
        assert page.generation_id == accepted.accepted.reference.generation_id
        assert page.items


@pytest.mark.parametrize("count", [100, 1000, 10000])
def test_isolated_capacity_measurement(physical_backend, count):
    """Measurement only: these fixture sizes do not establish production caps."""
    import json
    import tracemalloc
    from time import monotonic

    from tests.p5.knowledge.conftest import make_test_entity

    backend, admin = physical_backend
    tracemalloc.start()
    base, _ = make_test_document()
    entities = base.entities + tuple(
        make_test_entity(
            f"architecture://entity/service/fixture-{i}", name=f"Fixture Service {i}"
        )
        for i in range(count)
    )
    document, scope = make_test_document(entities=entities)
    started = monotonic()
    profile = make_test_profile()
    projection = KnowledgeProjector().project(document, scope, profile)
    normalization = monotonic() - started
    generation = uuid4()
    name = "stacksense-search-it-" + generation.hex
    physical = backend.create_index(name, SEARCH_INDEX_SETTINGS, SEARCH_INDEX_MAPPINGS)
    started = monotonic()
    rows = [
        r.to_stored_envelope(generation_id=generation, index_uuid=physical)
        for r in projection.records
    ]
    assert backend.bulk_index_records(name, rows).failed == 0
    backend.drain_and_seal_index(name)
    writing = monotonic() - started
    started = monotonic()
    result = SearchVerifier(backend).verify(
        scope=scope,
        profile=profile,
        candidate_id=uuid4(),
        attempt_id=uuid4(),
        generation_id=generation,
        index_name=name,
        index_uuid=physical,
        expected_projection=projection,
    )
    verification = monotonic() - started
    assert result.verified
    stats = admin.indices.stats(index=name)
    python_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    print(
        "M2_ISOLATED_MEASUREMENT",
        json.dumps(
            {
                "records": projection.counts.total_records,
                "normalize_seconds": round(normalization, 4),
                "write_seal_seconds": round(writing, 4),
                "verify_seconds": round(verification, 4),
                "store_bytes": stats["_all"]["total"]["store"]["size_in_bytes"],
                "document_bytes": sum(len(json.dumps(row).encode()) for row in rows),
                "python_traced_peak_bytes": python_peak,
                "production_approval": False,
            },
            sort_keys=True,
        ),
    )


def test_real_deadline_cancels_database_work(physical_backend):
    from time import monotonic, sleep

    from backend.platform.knowledge.contracts import SearchDeadlineExceededError
    from tests.p5.knowledge.conftest import make_test_entity

    backend, admin = physical_backend
    base, _ = make_test_document()
    document, scope = make_test_document(
        entities=base.entities
        + tuple(
            make_test_entity(f"architecture://entity/service/deadline-{i}")
            for i in range(1000)
        )
    )
    projection = KnowledgeProjector().project(document, scope, make_test_profile())
    generation = uuid4()
    name = "stacksense-search-it-" + generation.hex
    physical = backend.create_index(name, SEARCH_INDEX_SETTINGS, SEARCH_INDEX_MAPPINGS)
    rows = [
        r.to_stored_envelope(generation_id=generation, index_uuid=physical)
        for r in projection.records
    ]
    assert backend.bulk_index_records(name, rows).failed == 0
    backend.drain_and_seal_index(name)
    pit = backend.open_pit(name, 60)
    started = monotonic()
    try:
        with pytest.raises(SearchDeadlineExceededError):
            with backend.operation(started + 1):
                backend._search(
                    pit,
                    {
                        "script_score": {
                            "query": {"match_all": {}},
                            "script": {
                                "source": "double x=0; for(int i=0;i<100000;i++)"
                                "{x+=Math.sin(i);} return x+1;"
                            },
                        }
                    },
                    10,
                    None,
                    ["_score"],
                )
        assert monotonic() - started < 2
        stop_deadline = monotonic() + 2
        while True:
            # The official client marks task inspection as technical preview;
            # capture that documented warning, retaining task assertions below.
            from elasticsearch.exceptions import GeneralAvailabilityWarning

            with pytest.warns(GeneralAvailabilityWarning):
                tasks = admin.tasks.list(
                    actions="indices:data/read/search*,indices:data/read/async_search*",
                    detailed=True,
                )
            if not any(node.get("tasks") for node in tasks.get("nodes", {}).values()):
                break
            if monotonic() >= stop_deadline:
                pytest.fail("Search database work survived cancellation")
            sleep(0.05)
    finally:
        backend.close_pit(pit)


@pytest.fixture
def real_prepared(search_engine, physical_backend):
    backend, _ = physical_backend
    document, scope = make_test_document()
    binding = HandlerProfile(
        slot=WorkSlot(kind=WorkKind.SEARCH), profile=make_test_profile()
    )
    selected = policy().model_copy(
        update={
            "profiles": tuple(
                binding if item.slot.kind == WorkKind.SEARCH else item
                for item in policy().profiles
            )
        }
    )
    with Session(search_engine) as session, session.begin():
        repo = SqlAlchemyDeliveryRepository(session)
        bundle = repo.ensure_bundle(
            scope, selected, Eligibility.ELIGIBLE, revisit_seconds=1
        )
        work_id = session.scalar(
            select(Work.id).where(
                Work.bundle_id == bundle, Work.kind == WorkKind.SEARCH
            )
        )
        payload, _ = repo.reserve(
            work_id,
            scope.project_id,
            reservation_seconds=2,
            correlation_id="m2-real-race",
        )
    with Session(search_engine) as session, session.begin():
        lease = SqlAlchemyDeliveryRepository(session).claim(
            payload,
            binding,
            "real-m2",
            max_executions=3,
            lease_seconds=60,
            execution_seconds=120,
        )
    with Session(search_engine) as staging:
        prepared = SearchWorkHandler(
            backend=backend,
            repository=SqlAlchemySearchRepository(staging),
            document_loader=lambda _: document,
        ).execute(
            WorkExecutionContext(
                attempt=lease.identity,
                deadline=lease.deadline,
                control=execution_control(lambda: None),
            )
        )
    return backend, scope, lease, prepared


def test_real_publication_cleanup_race_keeps_live_and_accepted(
    search_engine, real_prepared
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from backend.platform.delivery.dependencies import build_attempt_retirement_reader
    from backend.platform.knowledge.persistence import SearchGenerationModel
    from backend.platform.knowledge.service import SearchCleanupService
    from tests.p5.delivery.test_rollout import budgets

    backend, scope, lease, prepared = real_prepared
    retirement = build_attempt_retirement_reader(search_engine, budgets())
    with Session(search_engine) as session:
        cleanup = SearchCleanupService(
            SqlAlchemySearchRepository(session), backend, session, retirement
        )
        # A live fenced publisher cannot be retired by a producer's local mark.
        assert cleanup.cleanup_orphans(older_than_seconds=0, max_items=10) == 0
    entered, release = Event(), Event()

    def publish():
        with PublicationUnitOfWork(
            search_engine, timeout_seconds=10, lock_timeout_ms=1000
        ) as uow:
            uow.complete(
                lease, prepared, lambda s: SearchPublicationPort(s, backend=backend)
            )
            entered.set()
            assert release.wait(5)
            uow.commit()

    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(publish)
        assert entered.wait(5)
        try:
            with Session(search_engine) as session:
                cleanup = SearchCleanupService(
                    SqlAlchemySearchRepository(session), backend, session, retirement
                )
                assert cleanup.cleanup_orphans(older_than_seconds=0, max_items=10) == 0
        finally:
            release.set()
        task.result()
    with Session(search_engine) as session:
        cleanup = SearchCleanupService(
            SqlAlchemySearchRepository(session), backend, session, retirement
        )
        assert cleanup.cleanup_orphans(older_than_seconds=0, max_items=10) == 0
        assert (
            session.get(SearchGenerationModel, prepared.candidate.generation_id).state
            == "ACTIVE"
        )


def test_real_retired_orphan_cleanup_uses_m1_authority(search_engine, real_prepared):
    from backend.platform.delivery.dependencies import build_attempt_retirement_reader
    from backend.platform.knowledge.persistence import SearchGenerationModel
    from backend.platform.knowledge.service import SearchCleanupService
    from tests.p5.delivery.test_rollout import budgets

    backend, scope, lease, prepared = real_prepared
    with Session(search_engine) as session, session.begin():
        assert SqlAlchemyDeliveryRepository(session).finish_failure(
            lease,
            code="fixture_integrity_failure",
            retryable=False,
            max_executions=3,
            retry_seconds=0.01,
        )
    with Session(search_engine) as session:
        cleanup = SearchCleanupService(
            SqlAlchemySearchRepository(session),
            backend,
            session,
            build_attempt_retirement_reader(search_engine, budgets()),
        )
        assert cleanup.cleanup_orphans(older_than_seconds=0, max_items=10) == 1
        assert (
            session.get(SearchGenerationModel, prepared.candidate.generation_id).state
            == "DELETED"
        )
        assert cleanup.cleanup_orphans(older_than_seconds=0, max_items=10) == 0


def test_real_post_backend_pointer_change_and_cursor_actor_binding(
    search_engine, real_prepared
):
    from backend.platform.knowledge.contracts import (
        SearchCursorExpiredError,
        SearchCursorInvalidError,
        SearchGenerationChangedError,
    )
    from backend.platform.knowledge.persistence import SearchResourceModel

    backend, scope, lease, prepared = real_prepared
    with PublicationUnitOfWork(
        search_engine, timeout_seconds=10, lock_timeout_ms=1000
    ) as uow:
        uow.complete(
            lease, prepared, lambda s: SearchPublicationPort(s, backend=backend)
        )
        uow.commit()
    actor = uuid4()
    request = SearchRequest(
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        q="Service",
        limit=1,
    )
    with Session(search_engine) as session:
        reader = SearchReader(
            backend=backend,
            repository=SqlAlchemySearchRepository(session),
            cursor_secret="real-test-key-" * 4,
            cursor_ttl_seconds=120,
        )
        page = reader.search(request, actor_id=actor)
        session.commit()
        with pytest.raises(SearchCursorInvalidError):
            reader.search(
                request.model_copy(update={"cursor": page.next_cursor}),
                actor_id=uuid4(),
            )
        session.rollback()
        assert page.next_cursor is not None
        with pytest.raises(SearchCursorInvalidError):
            reader.search(
                request.model_copy(update={"cursor": "!" + page.next_cursor[1:]}),
                actor_id=actor,
            )
        session.rollback()
        # Expired/closed server PIT must map to 410, not silently start a fresh
        # search. Retain the valid signed cursor and durable pin to reach ES.
        import base64
        import json

        envelope = json.loads(base64.urlsafe_b64decode(page.next_cursor))
        backend.close_pit(envelope["f"]["state"]["pit"])
        with pytest.raises(SearchCursorExpiredError):
            reader.search(
                request.model_copy(update={"cursor": page.next_cursor}),
                actor_id=actor,
            )
        session.rollback()
        original = backend.search_page

        def change_pointer(*args, **kwargs):
            result = original(*args, **kwargs)
            with Session(search_engine) as writer, writer.begin():
                resource = writer.scalar(
                    select(SearchResourceModel).where(
                        SearchResourceModel.project_id == scope.project_id,
                        SearchResourceModel.architecture_version_id
                        == scope.architecture_version_id,
                    )
                )
                resource.active_generation_id = None
            return result

        backend.search_page = change_pointer
        try:
            with pytest.raises(SearchGenerationChangedError):
                reader.search(request, actor_id=actor)
        finally:
            backend.search_page = original


@pytest.mark.parametrize(
    "alteration", ["descriptor", "physical_seal", "accepted_receipt"]
)
def test_real_publication_and_readiness_reject_tampering(
    search_engine, real_prepared, physical_backend, alteration
):
    import json
    from datetime import UTC, datetime, timedelta

    from backend.platform.delivery.contracts import DeliveryContractError
    from backend.platform.delivery.publication import PublicationContext
    from backend.platform.knowledge.persistence import (
        SearchGenerationModel,
        SearchPublicationReceiptModel,
    )

    backend, scope, lease, prepared = real_prepared
    _, admin = physical_backend
    if alteration == "descriptor":
        forged = prepared.model_copy(
            update={
                "candidate": prepared.candidate.model_copy(
                    update={"artifact_id": uuid4()}
                )
            }
        )
        with pytest.raises(DeliveryContractError):
            with PublicationUnitOfWork(
                search_engine, timeout_seconds=10, lock_timeout_ms=1000
            ) as uow:
                uow.complete(
                    lease, forged, lambda s: SearchPublicationPort(s, backend=backend)
                )
        return
    with PublicationUnitOfWork(
        search_engine, timeout_seconds=10, lock_timeout_ms=1000
    ) as uow:
        receipt = uow.complete(
            lease, prepared, lambda s: SearchPublicationPort(s, backend=backend)
        )
        uow.commit()
    with Session(search_engine) as session:
        if alteration == "physical_seal":
            generation = session.get(
                SearchGenerationModel, prepared.candidate.generation_id
            )
            admin.indices.put_settings(
                index=generation.index_name, settings={"index.blocks.write": False}
            )
        else:
            row = session.scalar(
                select(SearchPublicationReceiptModel).where(
                    SearchPublicationReceiptModel.generation_id
                    == prepared.candidate.generation_id
                )
            )
            value = json.loads(json.dumps(row.artifact_reference))
            value["artifact_id"] = str(uuid4())
            row.artifact_reference = value
            session.commit()
        with pytest.raises(DeliveryContractError):
            SearchPublicationPort(session, backend=backend).validate_ready(
                receipt.accepted.reference,
                PublicationContext(
                    transaction_id=uuid4(),
                    attempt=lease.identity,
                    deadline=datetime.now(UTC) + timedelta(seconds=5),
                ),
            )
