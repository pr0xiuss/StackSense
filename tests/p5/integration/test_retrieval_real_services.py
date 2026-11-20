"""M3 acceptance against isolated PostgreSQL, sealed ES and verified Neo4j.

Requires the explicitly isolated M2_TEST_ES_* / P5_TEST_DATABASE_URL fixtures
and M3_TEST_NEO4J_URI=bolt://localhost:17687. Never uses application data.
"""

import os
import subprocess
import time
from contextlib import ExitStack
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from backend.api.error_handlers import register_exception_handlers
from backend.api.v1.retrieval import router
from backend.platform.analysis.architecture.persistence import (
    SqlAlchemyArchitectureRepository,
)
from backend.platform.config import Settings, get_settings
from backend.platform.database import DatabaseSettings
from backend.platform.delivery.contracts import (
    WorkExecutionContext,
    WorkKind,
    execution_control,
)
from backend.platform.delivery.model import Eligibility
from backend.platform.delivery.persistence import DeliveryWorkModel as Work
from backend.platform.delivery.publication import PublicationUnitOfWork
from backend.platform.delivery.repository import SqlAlchemyDeliveryRepository
from backend.platform.delivery.source import PublishedVersionReader
from backend.platform.graph.executor import ProjectionExecutor
from backend.platform.graph.lifecycle import GraphProjectionLifecycle
from backend.platform.graph.neo4j import Neo4jInfrastructure
from backend.platform.graph.persistence import SqlAlchemyGraphProjectionRepository
from backend.platform.graph.projection_store import Neo4jProjectionStore
from backend.platform.graph.source import SqlAlchemyPublishedArchitectureSource
from backend.platform.graph.verification import GraphVerifier
from backend.platform.knowledge.repository import (
    SearchPublicationPort,
    SqlAlchemySearchRepository,
)
from backend.platform.knowledge.retrieval_configuration import (
    RetrievalBudget,
    RetrievalPolicy,
    operation_budget,
)
from backend.platform.knowledge.retrieval_dependencies import _session
from backend.platform.knowledge.service import SearchWorkHandler
from backend.platform.projects.infra.base import Base
from tests.p3.analysis.test_m4_persistence import _analysis, _document, _validated
from tests.p5.integration.test_delivery_postgres import policy as delivery_policy
from tests.p5.knowledge.test_real_services import (
    physical_backend as physical_backend,
)
from tests.p5.knowledge.test_real_services import (
    search_engine as search_engine,
)


@pytest.fixture
def real_pipeline(search_engine, physical_backend, monkeypatch, request):
    uri = os.environ.get("M3_TEST_NEO4J_URI")
    if uri != "bolt://localhost:17687":
        pytest.skip("Explicit isolated M3_TEST_NEO4J_URI required")
    backend, admin = physical_backend
    Base.metadata.create_all(search_engine)
    original = _document()
    # P3 persistence fixtures use a synthetic `rule_id`; this source fixture
    # uses the actual P4-allowlisted producer field before publication.
    document = replace(
        original,
        content_digest="",
        entities=tuple(
            replace(e, metadata={"promotion_rule_id": "m3.fixture.v1"})
            for e in original.entities
        ),
        relationships=tuple(
            replace(r, metadata={"promotion_rule_id": "m3.fixture.v1"})
            for r in original.relationships
        ),
    )
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
        scope = PublishedVersionReader.scope(header)
    # Use the deployment's exact approved producer binding.
    from backend.platform.knowledge.configuration import parse_deployment

    binding = parse_deployment(backend.deployment_raw).binding
    selected = delivery_policy().model_copy(
        update={
            "profiles": tuple(
                binding if p.slot.kind == WorkKind.SEARCH else p
                for p in delivery_policy().profiles
            )
        }
    )
    with Session(search_engine) as session, session.begin():
        repo = SqlAlchemyDeliveryRepository(session)
        bundle = repo.ensure_bundle(
            scope, selected, Eligibility.ELIGIBLE, revisit_seconds=1
        )
        work = session.scalar(
            select(Work.id).where(
                Work.bundle_id == bundle, Work.kind == WorkKind.SEARCH
            )
        )
        payload, _ = repo.reserve(
            work, scope.project_id, reservation_seconds=2, correlation_id="m3-real"
        )
    with Session(search_engine) as session, session.begin():
        lease = SqlAlchemyDeliveryRepository(session).claim(
            payload,
            binding,
            "m3-real",
            max_executions=3,
            lease_seconds=60,
            execution_seconds=120,
        )
    assert lease is not None

    def load(exact):
        with Session(search_engine) as session:
            return SqlAlchemyPublishedArchitectureSource(session).load_exact(
                exact.architecture_version_id, exact.project_id
            )

    with Session(search_engine) as session:
        prepared = SearchWorkHandler(
            backend=backend,
            repository=SqlAlchemySearchRepository(session),
            document_loader=load,
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
        uow.commit()
    # Experimental limits, explicit and isolated: not approved production defaults.
    trial = RetrievalPolicy(
        max_source_calls=50,
        max_chain_work_units=5000,
        max_cursor_bytes=4096,
        total_deadline_seconds=10.0,
        finalization_reserve_seconds=0.5,
    )
    settings = Settings(
        _env_file=None,
        neo4j_uri=uri,
        neo4j_health_timeout_seconds=20.0,
        neo4j_password=SecretStr("isolated-m3-verification-only"),
        search_deployment_json=SecretStr(backend.deployment_raw),
        search_cursor_secret=SecretStr("m3-real-search-test-key-" * 3),
        retrieval_cursor_secret=SecretStr("m3-real-context-test-key-" * 3),
        retrieval_policy_json=trial.model_dump_json(),
    )
    schema = search_engine.get_execution_options()["schema_translate_map"][None]
    database_url = search_engine.url.update_query_dict(
        {"options": f"-csearch_path={schema}"}
    )
    monkeypatch.setattr(
        "backend.platform.knowledge.retrieval_dependencies.get_database_settings",
        lambda: DatabaseSettings(
            _env_file=None,
            database_url=SecretStr(database_url.render_as_string(hide_password=False)),
        ),
    )
    monkeypatch.setattr(
        "backend.platform.knowledge.retrieval_dependencies.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr("backend.platform.config.get_settings", lambda: settings)
    monkeypatch.setattr(
        "backend.platform.knowledge.dependencies.get_search_backend", lambda: backend
    )
    infra = Neo4jInfrastructure(settings)
    request.addfinalizer(infra.close)
    try:
        infra.initialize()
    except Exception:
        infra.close()
        raise
    store = Neo4jProjectionStore(infra.driver, settings)
    executor = ProjectionExecutor(
        settings=settings,
        store=store,
        verifier=GraphVerifier(store=store),
        session_factory=lambda: Session(search_engine),
    )
    with Session(search_engine) as session:
        decision = GraphProjectionLifecycle(
            SqlAlchemyGraphProjectionRepository(session)
        ).reconcile_published(header, correlation_id="m3-real-graph")
        session.commit()
    assert decision.work is not None
    projected = executor.execute(decision.work, worker_id="m3-real-graph")
    assert projected.status == "completed", (projected.failure_code, projected.reason)
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_settings] = lambda: settings
    headers = {
        "X-Service-Token": settings.internal_api_secret_key.get_secret_value(),
        "X-Actor-Id": str(uuid4()),
        "X-Actor-Role": "VIEWER",
        "X-Project-Id": str(scope.project_id),
    }
    client = TestClient(app)
    url = f"/api/v1/architecture-versions/{scope.architecture_version_id}/knowledge"
    try:
        yield (
            client,
            url,
            headers,
            scope,
            search_engine,
            backend,
            admin,
            receipt,
            executor,
            decision,
            trial,
        )
    finally:
        client.close()
        infra.close()


def test_real_fenced_publication_to_c3_search_and_pinned_continuation(real_pipeline):
    client, url, headers, scope, engine, backend, _, receipt, *_ = real_pipeline
    payload = {
        "operation": "lookup",
        "q": "API",
        "limit": 1,
        "document_kinds": ["entity"],
    }
    first = client.post(
        url + f"/query?project_id={scope.project_id}", headers=headers, json=payload
    )
    assert first.status_code == 200, first.text
    data = first.json()
    assert data["facts"]
    search = next(
        o for o in data["source_observations"] if o["source_kind"] == "search"
    )
    assert search["generation_id"] == str(receipt.accepted.reference.generation_id)
    assert (
        search["search_scope"]["configuration_fingerprint"]
        == scope.configuration_fingerprint
    )
    assert data["next_cursor"]
    # The first HTTP response committed pins on a separate connection.
    next_page = client.post(
        url + f"/query?project_id={scope.project_id}",
        headers=headers,
        json={**payload, "cursor": data["next_cursor"]},
    )
    assert next_page.status_code == 200, next_page.text
    assert next_page.json()["facts"][0]["record_id"] != data["facts"][0]["record_id"]
    forged = {**headers, "X-Actor-Id": str(uuid4())}
    assert (
        client.post(
            url + f"/query?project_id={scope.project_id}",
            headers=forged,
            json={**payload, "cursor": data["next_cursor"]},
        ).status_code
        == 422
    )


def test_real_graph_context_uses_canonical_ids_and_provenance(real_pipeline):
    client, url, headers, scope, engine, *_ = real_pipeline
    from backend.platform.analysis.architecture.service import ArchitectureQueryService

    with Session(engine) as session:
        entities = ArchitectureQueryService(
            SqlAlchemyArchitectureRepository(session)
        ).list_entities(
            scope.architecture_version_id, scope.project_id, limit=100, offset=0
        )
        source = next(e for e in entities.items if e.kind == "service")
    response = client.post(
        url + f"/context?project_id={scope.project_id}",
        headers=headers,
        json={
            "subjects": [{"selector_type": "record_id", "record_id": str(source.id)}],
            "operations": ["dependencies"],
            "required_sources": ["canonical", "graph"],
            "optional_sources": [],
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["facts"]) == 2 and len(data["relationships"]) == 1
    assert data["relationships"][0]["source_logical_id"] == source.logical_id
    assert data["scope"]["completeness"] is not None
    assert data["evidence"][0]["producer_id"] == "python-ast"
    assert data["unresolved"][0]["candidate_references"] == ["configured-host"]
    assert any(o["source_kind"] == "graph" for o in data["source_observations"])
    assert data["limits_and_usage"]["total_output_bytes"] == len(response.content)


def test_real_postgresql_statement_timeout_terminates_work(real_pipeline):
    *_, trial = real_pipeline
    with operation_budget(RetrievalBudget(trial)), ExitStack() as stack:
        readonly = _session(stack, readonly=True)
        assert readonly.scalar(text("SHOW transaction_read_only")) == "on"
        with pytest.raises(DBAPIError) as rejected:
            readonly.execute(text("UPDATE analyses SET status=status WHERE false"))
        assert getattr(rejected.value.orig, "sqlstate", None) == "25006"
    budget = RetrievalBudget(
        trial.model_copy(
            update={
                "total_deadline_seconds": 0.25,
                "finalization_reserve_seconds": 0.01,
            }
        )
    )
    started = time.monotonic()
    with operation_budget(budget), ExitStack() as stack:
        session = _session(stack, readonly=True)
        with pytest.raises(DBAPIError) as error:
            session.execute(text("SELECT pg_sleep(2)"))
        assert getattr(error.value.orig, "sqlstate", None) == "57014"
    assert time.monotonic() - started < 1.0
    engine = real_pipeline[4]
    with engine.connect() as connection:
        active = connection.scalar(
            text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE pid <> pg_backend_pid() AND state='active' "
                "AND query LIKE '%pg_sleep(2)%'"
            )
        )
        assert active == 0


def test_real_invalid_delegation_opens_no_dependencies(real_pipeline, monkeypatch):
    client, url, headers, scope, *_ = real_pipeline
    monkeypatch.setattr(
        "backend.platform.knowledge.retrieval_dependencies._session",
        lambda *a, **k: pytest.fail("Database opened before authorization"),
    )
    bad = {**headers, "X-Project-Id": str(uuid4())}
    response = client.post(
        url + f"/query?project_id={scope.project_id}",
        headers=bad,
        json={"operation": "lookup", "q": "API"},
    )
    assert response.status_code == 403


def test_real_c3_recovers_exact_generation_after_isolated_es_restart(real_pipeline):
    client, url, headers, scope, engine, backend, admin, receipt, *_ = real_pipeline
    endpoint = url + f"/query?project_id={scope.project_id}"
    before = client.post(
        endpoint, headers=headers, json={"operation": "lookup", "q": "API"}
    )
    assert before.status_code == 200, before.text
    generation = str(receipt.accepted.reference.generation_id)
    subprocess.run(
        ["docker", "restart", "stacksense-m3-verification-elasticsearch-1"],
        check=True,
        capture_output=True,
        timeout=60,
    )
    # Bounded disposable-service startup allowance, not a retrieval timeout.
    ready_by = time.monotonic() + 120
    while True:
        try:
            health = admin.cluster.health(wait_for_status="yellow", timeout="1s")
            if not health["timed_out"] and health["unassigned_primary_shards"] == 0:
                admin.security.authenticate()
                break
        except Exception:
            pass
        if time.monotonic() >= ready_by:
            pytest.fail("Disposable Elasticsearch did not recover after restart")
        time.sleep(0.5)
    after = client.post(
        endpoint, headers=headers, json={"operation": "lookup", "q": "API"}
    )
    assert after.status_code == 200, after.text
    observed = next(
        o for o in after.json()["source_observations"] if o["source_kind"] == "search"
    )
    assert observed["generation_id"] == generation
    assert after.json()["facts"] == before.json()["facts"]


def test_real_expired_pit_is_typed_and_never_restarted(real_pipeline, monkeypatch):
    client, url, headers, scope, _, backend, *_ = real_pipeline
    opened = []
    original = backend.open_pit

    def track(*args, **kwargs):
        pit = original(*args, **kwargs)
        opened.append(pit)
        return pit

    monkeypatch.setattr(backend, "open_pit", track)
    body = {"operation": "lookup", "q": "API", "limit": 1, "document_kinds": ["entity"]}
    first = client.post(
        url + f"/query?project_id={scope.project_id}", headers=headers, json=body
    )
    assert first.status_code == 200, first.text
    cursor = first.json()["next_cursor"]
    assert cursor and opened
    backend.close_pit(opened[0])
    resumed = client.post(
        url + f"/query?project_id={scope.project_id}",
        headers=headers,
        json={**body, "cursor": cursor},
    )
    assert resumed.status_code == 410, resumed.text
    assert resumed.json()["error"]["code"] == "retrieval_cursor_expired"


def test_real_graph_rebuild_during_rehydration_rejects_old_generation(
    real_pipeline, monkeypatch
):
    client, url, headers, scope, engine, _, _, _, executor, decision, *_ = real_pipeline
    from backend.platform.analysis.architecture.service import ArchitectureQueryService
    from backend.platform.knowledge.retrieval_adapters import CanonicalReadAdapter

    with Session(engine) as session:
        entities = ArchitectureQueryService(
            SqlAlchemyArchitectureRepository(session)
        ).list_entities(
            scope.architecture_version_id, scope.project_id, limit=100, offset=0
        )
        source = next(e for e in entities.items if e.kind == "service")
        lifecycle = GraphProjectionLifecycle(
            SqlAlchemyGraphProjectionRepository(session)
        )
        _, payload = lifecycle.request_rebuild(
            decision.work.projection_id,
            actor_id=uuid4(),
            actor_role="OWNER",
            correlation_id="m3-switch",
        )
        session.commit()
    original = CanonicalReadAdapter.get_entity
    count = 0

    def rehydrate(self, *args, **kwargs):
        nonlocal count
        count += 1
        # First two reads resolve/load the anchor; third rehydrates graph output.
        if count == 3:
            rebuilt = executor.execute(payload, worker_id="m3-switch")
            assert rebuilt.status == "completed", rebuilt.failure_code
        return original(self, *args, **kwargs)

    monkeypatch.setattr(CanonicalReadAdapter, "get_entity", rehydrate)
    response = client.post(
        url + f"/query?project_id={scope.project_id}",
        headers=headers,
        json={
            "operation": "dependencies",
            "subject": {"selector_type": "record_id", "record_id": str(source.id)},
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "retrieval_generation_changed"


def test_real_all_graph_operations_are_available(real_pipeline):
    client, url, headers, scope, engine, *_ = real_pipeline
    from backend.platform.analysis.architecture.service import ArchitectureQueryService

    with Session(engine) as session:
        entities = ArchitectureQueryService(
            SqlAlchemyArchitectureRepository(session)
        ).list_entities(
            scope.architecture_version_id, scope.project_id, limit=100, offset=0
        )
        source = next(e for e in entities.items if e.kind == "service")
        target = next(e for e in entities.items if e.kind == "external_api")
    for operation, anchor in (
        ("dependencies", source),
        ("dependents", target),
        ("containment", source),
        ("paths", source),
    ):
        body = {
            "operation": operation,
            "subject": {"selector_type": "record_id", "record_id": str(anchor.id)},
        }
        if operation == "paths":
            body["target"] = {"selector_type": "record_id", "record_id": str(target.id)}
        response = client.post(
            url + f"/query?project_id={scope.project_id}", headers=headers, json=body
        )
        assert response.status_code == 200, (operation, response.text)
        if operation == "paths":
            assert response.json()["paths"][0]["hop_count"] == 1
