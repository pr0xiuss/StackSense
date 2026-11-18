"""Adversarial regressions; these do not claim real ES/PG guarantees."""

from datetime import UTC, datetime, timedelta
from time import sleep
from uuid import uuid4

import pytest

from backend.platform.delivery.contracts import DeliveryContractError, OutputDigests
from backend.platform.delivery.publication import PublicationContext
from backend.platform.knowledge.contracts import (
    SearchBackendUnavailableError,
    SearchDeadlineExceededError,
    SearchGenerationChangedError,
    SearchRequest,
)
from backend.platform.knowledge.dependencies import (
    get_search_backend,
    set_search_backend,
)
from backend.platform.knowledge.elasticsearch import (
    SEARCH_INDEX_MAPPINGS,
    SEARCH_INDEX_SETTINGS,
    InMemorySearchBackend,
)
from backend.platform.knowledge.projection import KnowledgeProjector
from backend.platform.knowledge.verification import SearchVerifier
from tests.p5.knowledge.conftest import make_test_profile, make_test_scope
from tests.p5.knowledge.test_api import knowledge_api as knowledge_api
from tests.p5.knowledge.test_api import search_path
from tests.p5.knowledge.test_publication import pub_env as pub_env
from tests.p5.knowledge.test_reader import (
    reader_env as reader_env,
)
from tests.p5.knowledge.test_reader import (
    stage_and_publish_test_index,
)
from tests.p5.knowledge.test_service import service_env as service_env


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "tampered"),
        ("project_id", str(uuid4())),
        ("generation_id", str(uuid4())),
        ("storage_key", "wrong-key"),
    ],
)
def test_full_payload_corruption_not_hidden_by_original_digest(
    sample_doc_and_scope, field, value
):
    doc, scope = sample_doc_and_scope
    profile = make_test_profile()
    projection = KnowledgeProjector().project(doc, scope, profile)
    backend = InMemorySearchBackend()
    physical = backend.create_index(
        "candidate", SEARCH_INDEX_SETTINGS, SEARCH_INDEX_MAPPINGS
    )
    gen = uuid4()
    rows = [
        r.to_stored_envelope(generation_id=gen, index_uuid=physical)
        for r in projection.records
    ]
    rows[0][field] = value
    backend.bulk_index_records("candidate", rows)
    backend.drain_and_seal_index("candidate")
    result = SearchVerifier(backend).verify(
        scope=scope,
        profile=profile,
        candidate_id=uuid4(),
        attempt_id=uuid4(),
        generation_id=gen,
        index_name="candidate",
        index_uuid=physical,
        expected_projection=projection,
    )
    assert not result.verified


def test_nested_record_data_is_immutable(sample_doc_and_scope):
    doc, scope = sample_doc_and_scope
    record = KnowledgeProjector().project(doc, scope).records[0]
    with pytest.raises(TypeError):
        record.text_fields["injected"] = "bad"
    assert record.record_digest == record.compute_semantic_digest()


def _deployment_configuration():
    from backend.platform.delivery.contracts import HandlerProfile, WorkKind, WorkSlot

    return {
        "binding": HandlerProfile(
            slot=WorkSlot(kind=WorkKind.SEARCH), profile=make_test_profile()
        ).model_dump(mode="json"),
        "endpoint": "https://localhost:19200",
        "ca_certs": "/fixture/ca.pem",
        "server_version": "9.5.6",
        "client_version": "9.5.1",
        **{
            f"{role}_api_key": "test-secret-not-for-errors"
            for role in ("provisioner", "writer", "sealer", "reader", "cleanup")
        },
        "request_seconds": 5,
        "cancel_seconds": 0.5,
        "bulk_documents": 25,
        "bulk_bytes": 1048576,
        "readback_page": 20,
        "pit_seconds": 120,
        "status_page_size": 10,
        "status_max_pages": 10,
        "index_settings": SEARCH_INDEX_SETTINGS,
    }


def test_deployment_rejects_cancellation_outside_operation_budget():
    import json

    from backend.platform.knowledge.configuration import parse_deployment

    raw = _deployment_configuration()
    raw["cancel_seconds"] = raw["request_seconds"]
    with pytest.raises(SearchBackendUnavailableError):
        parse_deployment(json.dumps(raw))


@pytest.mark.parametrize(
    "field,value",
    [
        (field, 0)
        for field in (
            "request_seconds",
            "bulk_documents",
            "bulk_bytes",
            "readback_page",
            "pit_seconds",
            "cancel_seconds",
            "status_page_size",
            "status_max_pages",
        )
    ]
    + [("status_page_size", 501)],
)
def test_explicit_read_and_adjacent_backend_budgets_are_validated(field, value):
    import json

    from backend.platform.knowledge.configuration import parse_deployment

    raw = _deployment_configuration()
    raw[field] = value
    with pytest.raises(SearchBackendUnavailableError):
        parse_deployment(json.dumps(raw))


@pytest.mark.parametrize("failure", ["client_creation", "server_version"])
def test_configuration_failure_closes_clients_and_has_safe_error(monkeypatch, failure):
    import json
    from types import SimpleNamespace

    from backend.platform.knowledge import configuration

    clients = []

    class Client:
        closed = False

        def __init__(self, *args, **kwargs):
            if failure == "client_creation" and len(clients) == 2:
                raise ValueError("test-secret-not-for-errors")
            clients.append(self)

        def info(self):
            return {"version": {"number": "0.0.0"}}

        def close(self):
            self.closed = True

    monkeypatch.setattr(
        configuration.importlib,
        "import_module",
        lambda _: SimpleNamespace(Elasticsearch=Client),
    )
    monkeypatch.setattr(
        configuration.importlib.metadata,
        "version",
        lambda _: _deployment_configuration()["client_version"],
    )
    configuration.configured_backend.cache_clear()
    with pytest.raises(SearchBackendUnavailableError) as error:
        configuration.configured_backend(json.dumps(_deployment_configuration()))
    assert clients and all(client.closed for client in clients)
    assert "test-secret-not-for-errors" not in str(error.value)
    configuration.configured_backend.cache_clear()


def test_unvalidated_record_copy_rejected_at_serialization(sample_doc_and_scope):
    doc, scope = sample_doc_and_scope
    record = KnowledgeProjector().project(doc, scope).records[0]
    forged = record.model_copy(update={"title": "forged without a new digest"})
    with pytest.raises(ValueError):
        forged.to_stored_envelope(generation_id=uuid4(), index_uuid="fixture")


def test_dependency_outage_is_structured_503(knowledge_api):
    from backend.platform.knowledge.dependencies import get_search_reader

    client, app, _, _, scope = knowledge_api

    def unavailable():
        raise SearchBackendUnavailableError()

    app.dependency_overrides[get_search_reader] = unavailable
    response = client.get(search_path(scope))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "search_backend_unavailable"


def test_no_in_memory_production_fallback(monkeypatch):
    from backend.platform.config import get_settings

    monkeypatch.setattr(get_settings(), "search_deployment_json", None)
    set_search_backend(None)
    with pytest.raises(SearchBackendUnavailableError):
        get_search_backend()


@pytest.mark.parametrize("mode", ["semantic", "hybrid", "invented"])
def test_unavailable_modes_never_execute_lexical(knowledge_api, mode):
    client, app, reader, status, scope = knowledge_api

    def forbidden(*args, **kwargs):
        raise AssertionError("unavailable mode executed lexical")

    reader.search = forbidden
    response = client.get(search_path(scope) + "&mode=" + mode)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == (
        "search_capability_unavailable"
        if mode in {"semantic", "hybrid"}
        else "search_invalid_mode"
    )


def test_historical_acceptance_cannot_be_cleanup_marked(reader_env):
    reader, backend, repo, session = reader_env
    scope = make_test_scope()
    _, old, index = stage_and_publish_test_index(repo, backend, session, scope, [])
    stage_and_publish_test_index(repo, backend, session, scope, [])
    assert repo.get_generation(old).state == "HISTORICAL"
    with pytest.raises(DeliveryContractError):
        repo.mark_cleanup(old)
    assert index in backend._indexes


@pytest.mark.parametrize("failure", ["slow", "pointer"])
def test_deadline_and_pointer_validated_after_backend(reader_env, failure):
    reader, backend, repo, session = reader_env
    scope = make_test_scope()
    stage_and_publish_test_index(repo, backend, session, scope, [])
    original = backend.search_page

    def interleave(*args, **kwargs):
        result = original(*args, **kwargs)
        if failure == "slow":
            sleep(0.08)
        else:
            repo.get_resource(
                scope.project_id, scope.architecture_version_id
            ).active_generation_id = uuid4()
            session.flush()
        return result

    backend.search_page = interleave
    with pytest.raises(
        SearchDeadlineExceededError
        if failure == "slow"
        else SearchGenerationChangedError
    ):
        reader.search(
            SearchRequest(
                project_id=scope.project_id,
                architecture_version_id=scope.architecture_version_id,
                q="test",
                timeout_seconds=0.05,
            )
        )


def test_publication_rejects_forged_staged_manifest(pub_env):
    from backend.platform.delivery.contracts import (
        AttemptIdentity,
        WorkExecutionContext,
        WorkIdentity,
        execution_control,
    )

    doc, scope, profile, binding, handler, port, repo, session = pub_env
    work = WorkIdentity(
        scope=scope,
        bundle_id=uuid4(),
        work_id=uuid4(),
        run_number=1,
        binding=binding,
        bundle_fingerprint="b" * 64,
        input_fingerprint="1" * 64,
    )
    attempt = AttemptIdentity(
        work=work,
        attempt_id=uuid4(),
        ordinal=1,
        fence=1,
        dispatch_epoch=uuid4(),
        candidate_id=uuid4(),
    )
    deadline = datetime.now(UTC) + timedelta(minutes=2)
    prepared = handler.execute(
        WorkExecutionContext(
            attempt=attempt, deadline=deadline, control=execution_control(lambda: None)
        )
    )
    forged = prepared.model_copy(
        update={
            "candidate": prepared.candidate.model_copy(
                update={"digests": OutputDigests(content="f" * 64)}
            )
        }
    )
    context = PublicationContext(
        transaction_id=uuid4(), attempt=attempt, deadline=deadline
    )
    with pytest.raises(DeliveryContractError):
        port.publish_prepared(forged, context)


def test_orphan_cleanup_needs_exact_retirement_and_keeps_tombstone(service_env):
    from types import SimpleNamespace

    from backend.platform.delivery.contracts import AttemptRetirement
    from backend.platform.knowledge.service import SearchCleanupService

    handler, context, repo, backend, session = service_env
    prepared = handler.execute(context)
    gen = repo.get_generation(prepared.candidate.generation_id)
    index = gen.index_name
    retired = AttemptRetirement(
        attempt=context.attempt, outcome="EXPIRED", ended_at=datetime.now(UTC)
    )
    cleanup = SearchCleanupService(
        repo,
        backend,
        session,
        retirement_reader=SimpleNamespace(read_retirement=lambda a: retired),
    )
    assert cleanup.cleanup_orphans(older_than_seconds=0, max_items=10) == 1
    assert index not in backend._indexes
    assert repo.get_generation(gen.generation_id).state == "DELETED"
    assert cleanup.cleanup_orphans(older_than_seconds=0, max_items=10) == 0
