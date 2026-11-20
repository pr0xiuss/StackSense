"""C3-only lazy composition; all resources open after authorization and budgeting."""

from __future__ import annotations

import math
from collections.abc import Callable, Generator
from contextlib import ExitStack
from typing import Any, cast

from fastapi import Depends
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from backend.platform.analysis.application.dependencies import (
    get_architecture_query_service,
)
from backend.platform.config import get_settings
from backend.platform.dependency_injection import get_database_settings
from backend.platform.knowledge.contracts import SearchReadPort
from backend.platform.knowledge.evidence import EvidencePlanner
from backend.platform.knowledge.retrieval import KnowledgeQueryService
from backend.platform.knowledge.retrieval_adapters import (
    CanonicalReadAdapter,
    GraphReadAdapter,
)
from backend.platform.knowledge.retrieval_configuration import (
    CURRENT_RETRIEVAL_BUDGET,
    RetrievalPolicy,
    parse_retrieval_policy,
)
from backend.platform.knowledge.retrieval_contracts import (
    CanonicalReadPort,
    GraphReadPort,
    RetrievalError,
    RetrievalUnavailableError,
)

_OVERRIDE_RETRIEVAL_POLICY: RetrievalPolicy | None = None
_OVERRIDE_CURSOR_SECRET: str | None = None
_OVERRIDE_CANONICAL_PORT: CanonicalReadPort | None = None
_OVERRIDE_SEARCH_PORT: SearchReadPort | None = None
_OVERRIDE_GRAPH_PORT: GraphReadPort | None = None


def set_retrieval_policy(policy: RetrievalPolicy | None) -> None:
    global _OVERRIDE_RETRIEVAL_POLICY
    _OVERRIDE_RETRIEVAL_POLICY = policy


def set_retrieval_cursor_secret(secret: str | None) -> None:
    global _OVERRIDE_CURSOR_SECRET
    _OVERRIDE_CURSOR_SECRET = secret


def set_canonical_read_port(port: CanonicalReadPort | None) -> None:
    global _OVERRIDE_CANONICAL_PORT
    _OVERRIDE_CANONICAL_PORT = port


def set_search_read_port(port: SearchReadPort | None) -> None:
    global _OVERRIDE_SEARCH_PORT
    _OVERRIDE_SEARCH_PORT = port


def set_graph_read_port(port: GraphReadPort | None) -> None:
    global _OVERRIDE_GRAPH_PORT
    _OVERRIDE_GRAPH_PORT = port


def get_retrieval_policy() -> RetrievalPolicy:
    if _OVERRIDE_RETRIEVAL_POLICY is not None:
        return _OVERRIDE_RETRIEVAL_POLICY
    raw = get_settings().retrieval_policy_json
    if raw is None or not raw.strip():
        raise RetrievalUnavailableError("Retrieval operating policy is not configured")
    return parse_retrieval_policy(raw)


def get_retrieval_cursor_secret() -> str:
    secret = _OVERRIDE_CURSOR_SECRET
    if secret is None:
        setting = get_settings().retrieval_cursor_secret
        secret = setting.get_secret_value() if setting else None
    if secret is None or len(secret.encode()) < 32:
        raise RetrievalUnavailableError(
            "Dedicated retrieval signing key is not configured"
        )
    return secret


def _session(stack: ExitStack, *, readonly: bool) -> Session:
    budget = CURRENT_RETRIEVAL_BUDGET.get()
    if budget is None:
        raise RetrievalUnavailableError("Missing bounded operation context")
    seconds = budget.remaining()
    # NullPool avoids borrowing the platform's unbounded pool. These are private
    # M3 connections/transactions, not a new database or canonical repository.
    engine = create_engine(
        get_database_settings().database_url.get_secret_value(),
        poolclass=NullPool,
        connect_args={"connect_timeout": max(1, math.floor(seconds))},
    )
    stack.callback(engine.dispose)

    @event.listens_for(engine, "before_cursor_execute")
    def bounded_statement(
        conn: Any,
        cursor: Any,
        statement: Any,
        parameters: Any,
        context: Any,
        executemany: Any,
    ) -> None:
        current = CURRENT_RETRIEVAL_BUDGET.get()
        if current is None:
            raise RetrievalUnavailableError("Missing database deadline")
        milliseconds = max(1, math.floor(current.remaining(reserve=False) * 1000))
        cursor.execute(f"SET LOCAL statement_timeout = {milliseconds}")
        cursor.execute(f"SET LOCAL lock_timeout = {milliseconds}")

    session = Session(engine)
    stack.callback(session.close)
    if readonly:
        from sqlalchemy import text

        session.execute(text("SET TRANSACTION READ ONLY"))
    budget.remaining()
    return session


class _LazyPort:
    def __init__(self, factory: Callable[[], Any]) -> None:
        self.factory = factory
        self.port: Any = None

    def __getattr__(self, name: str) -> Any:
        def invoke(*args: Any, **kwargs: Any) -> Any:
            if self.port is None:
                self.port = self.factory()
            return getattr(self.port, name)(*args, **kwargs)

        return invoke


def get_canonical_read_port() -> Generator[CanonicalReadPort]:
    if _OVERRIDE_CANONICAL_PORT is not None:
        yield _OVERRIDE_CANONICAL_PORT
        return
    with ExitStack() as stack:
        yield cast(
            CanonicalReadPort,
            _LazyPort(
                lambda: CanonicalReadAdapter(
                    get_architecture_query_service(_session(stack, readonly=True))
                )
            ),
        )


def get_search_read_port() -> Generator[SearchReadPort | None]:
    if _OVERRIDE_SEARCH_PORT is not None:
        yield _OVERRIDE_SEARCH_PORT
        return
    with ExitStack() as stack:

        def factory() -> Any:
            from backend.platform.knowledge.dependencies import (
                get_search_backend,
                get_search_reader,
                get_search_repository,
            )

            settings = get_settings()
            if (
                settings.search_deployment_json is None
                or settings.search_cursor_secret is None
            ):
                raise RetrievalUnavailableError(
                    "Search is not configured", cause="search_unavailable"
                )
            session = _session(stack, readonly=False)
            reader = get_search_reader(
                get_search_backend(), get_search_repository(session)
            )

            class CommittedRead:
                def search(self, request: Any, *, actor_id: Any) -> Any:
                    try:
                        result = reader.search(request, actor_id=actor_id)
                        session.commit()
                        budget = CURRENT_RETRIEVAL_BUDGET.get()
                        if budget is not None:
                            budget.remaining(reserve=False)
                        return result
                    except Exception:
                        session.rollback()
                        raise

            return CommittedRead()

        yield cast(SearchReadPort, _LazyPort(factory))


def get_graph_read_port() -> Generator[GraphReadPort | None]:
    if _OVERRIDE_GRAPH_PORT is not None:
        yield _OVERRIDE_GRAPH_PORT
        return
    with ExitStack() as stack:

        def factory() -> GraphReadPort:
            from backend.platform.graph.dependencies import (
                get_graph_generation_reader,
                get_graph_query_repository,
                get_graph_query_service,
            )

            settings = get_settings()
            budget = CURRENT_RETRIEVAL_BUDGET.get()
            if budget is None:
                raise RetrievalUnavailableError()
            remaining = budget.remaining()
            settings = settings.model_copy(
                update={
                    "neo4j_connection_timeout_seconds": min(
                        settings.neo4j_connection_timeout_seconds, remaining
                    ),
                    "neo4j_connection_acquisition_timeout_seconds": min(
                        settings.neo4j_connection_acquisition_timeout_seconds, remaining
                    ),
                    "neo4j_health_timeout_seconds": min(
                        settings.neo4j_health_timeout_seconds, remaining
                    ),
                }
            )
            try:
                from backend.platform.graph import Neo4jInfrastructure

                infrastructure = Neo4jInfrastructure(settings)
                stack.callback(infrastructure.close)
                infrastructure.initialize()
                reader = get_graph_generation_reader(_session(stack, readonly=True))
                service = get_graph_query_service(
                    settings,
                    reader,
                    get_graph_query_repository(settings, infrastructure),
                )
                budget.remaining()
                return GraphReadAdapter(reader, service)
            except RetrievalError:
                raise
            except Exception:
                raise RetrievalUnavailableError(
                    "Graph service unavailable", cause="graph_unavailable"
                ) from None

        yield cast(GraphReadPort, _LazyPort(factory))


def get_knowledge_query_service(
    canonical_port: CanonicalReadPort = Depends(get_canonical_read_port),
    search_port: SearchReadPort | None = Depends(get_search_read_port),
    graph_port: GraphReadPort | None = Depends(get_graph_read_port),
    policy: RetrievalPolicy = Depends(get_retrieval_policy),
    cursor_secret: str = Depends(get_retrieval_cursor_secret),
) -> KnowledgeQueryService:
    return KnowledgeQueryService(
        canonical_port,
        search_port=search_port,
        graph_port=graph_port,
        policy=policy,
        cursor_secret_key=cursor_secret,
    )


def get_evidence_planner(
    canonical_port: CanonicalReadPort = Depends(get_canonical_read_port),
    policy: RetrievalPolicy = Depends(get_retrieval_policy),
) -> EvidencePlanner:
    return EvidencePlanner(canonical_port, policy)
