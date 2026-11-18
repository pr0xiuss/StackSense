"""FastAPI dependency injection providers for P5-C3 Controlled Retrieval.

Wires canonical, search, and graph adapters, configuration policies, query
services, and evidence planners adhering to §7A.10 and §7A.11 of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.platform.analysis.application.dependencies import (
    get_architecture_query_service,
)
from backend.platform.analysis.architecture.service import ArchitectureQueryService
from backend.platform.config import get_settings
from backend.platform.dependency_injection import get_database_session
from backend.platform.knowledge.contracts import SearchReadPort
from backend.platform.knowledge.evidence import EvidencePlanner
from backend.platform.knowledge.retrieval import KnowledgeQueryService
from backend.platform.knowledge.retrieval_adapters import (
    CanonicalReadAdapter,
    GraphReadAdapter,
    SearchReadAdapter,
)
from backend.platform.knowledge.retrieval_configuration import (
    RetrievalPolicy,
    parse_retrieval_policy,
)
from backend.platform.knowledge.retrieval_contracts import (
    CanonicalReadPort,
    GraphReadPort,
)

logger = logging.getLogger(__name__)

_OVERRIDE_RETRIEVAL_POLICY: RetrievalPolicy | None = None
_OVERRIDE_CURSOR_SECRET: str | None = None
_OVERRIDE_CANONICAL_PORT: CanonicalReadPort | None = None
_OVERRIDE_SEARCH_PORT: SearchReadPort | None = None
_OVERRIDE_GRAPH_PORT: GraphReadPort | None = None


def set_retrieval_policy(policy: RetrievalPolicy | None) -> None:
    """Override RetrievalPolicy for testing."""
    global _OVERRIDE_RETRIEVAL_POLICY
    _OVERRIDE_RETRIEVAL_POLICY = policy


def set_retrieval_cursor_secret(secret: str | None) -> None:
    """Override cursor signing secret for testing."""
    global _OVERRIDE_CURSOR_SECRET
    _OVERRIDE_CURSOR_SECRET = secret


def set_canonical_read_port(port: CanonicalReadPort | None) -> None:
    """Override CanonicalReadPort for testing."""
    global _OVERRIDE_CANONICAL_PORT
    _OVERRIDE_CANONICAL_PORT = port


def set_search_read_port(port: SearchReadPort | None) -> None:
    """Override SearchReadPort for testing."""
    global _OVERRIDE_SEARCH_PORT
    _OVERRIDE_SEARCH_PORT = port


def set_graph_read_port(port: GraphReadPort | None) -> None:
    """Override GraphReadPort for testing."""
    global _OVERRIDE_GRAPH_PORT
    _OVERRIDE_GRAPH_PORT = port


def get_retrieval_policy() -> RetrievalPolicy:
    """Resolve configured RetrievalPolicy, failing safe with 503 if invalid."""
    if _OVERRIDE_RETRIEVAL_POLICY is not None:
        return _OVERRIDE_RETRIEVAL_POLICY

    settings = get_settings()
    raw = settings.retrieval_policy_json
    if raw is None or not raw.strip():
        # Default policy if no JSON configured
        return RetrievalPolicy()
    return parse_retrieval_policy(raw)


def get_retrieval_cursor_secret() -> str:
    """Resolve secret key used to HMAC-sign C3 stateless continuation cursors."""
    if _OVERRIDE_CURSOR_SECRET is not None:
        return _OVERRIDE_CURSOR_SECRET

    settings = get_settings()
    if settings.retrieval_cursor_secret is not None:
        return settings.retrieval_cursor_secret.get_secret_value()
    # Fallback to jwt_secret_key in development
    return settings.jwt_secret_key.get_secret_value()


def get_canonical_read_port(
    arch_service: Annotated[
        ArchitectureQueryService, Depends(get_architecture_query_service)
    ],
) -> CanonicalReadPort:
    """Provide bounded canonical read adapter over ArchitectureQueryService."""
    if _OVERRIDE_CANONICAL_PORT is not None:
        return _OVERRIDE_CANONICAL_PORT
    return CanonicalReadAdapter(arch_service)


def get_search_read_port(
    session: Annotated[Session, Depends(get_database_session)],
) -> SearchReadPort | None:
    """Provide optional SearchReadPort, failing safe to None if unconfigured."""
    if _OVERRIDE_SEARCH_PORT is not None:
        return _OVERRIDE_SEARCH_PORT

    try:
        from backend.platform.config import get_settings

        settings = get_settings()
        secret = getattr(settings, "search_cursor_secret", None)
        raw = getattr(settings, "search_deployment_json", None)
        if secret is None or raw is None:
            return None

        from backend.platform.knowledge.configuration import parse_deployment
        from backend.platform.knowledge.dependencies import (
            get_search_backend,
            get_search_repository,
        )
        from backend.platform.knowledge.reader import SearchReader

        backend = get_search_backend()
        repo = get_search_repository(session)
        deployment = parse_deployment(raw.get_secret_value())
        reader = SearchReader(
            backend=backend,
            repository=repo,
            cursor_secret=secret.get_secret_value(),
            cursor_ttl_seconds=deployment.pit_seconds,
        )
        return SearchReadAdapter(reader)
    except Exception as exc:
        logger.debug("Search service unavailable for retrieval: %s", exc)
        return None


def get_graph_read_port(
    session: Annotated[Session, Depends(get_database_session)],
) -> GraphReadPort | None:
    """Provide optional GraphReadPort, failing safe to None if unconfigured."""
    if _OVERRIDE_GRAPH_PORT is not None:
        return _OVERRIDE_GRAPH_PORT

    import os

    if not os.environ.get("GRAPH_RETRIEVAL_ENABLED") and not os.environ.get(
        "NEO4J_TEST_URI"
    ):
        return None

    try:
        from backend.platform.config import get_settings
        from backend.platform.graph.dependencies import (
            get_graph_generation_reader,
            get_graph_query_repository,
            get_graph_query_service,
            get_neo4j_infrastructure,
        )

        settings = get_settings()
        gen_reader = get_graph_generation_reader(session)
        infra_gen = get_neo4j_infrastructure(settings)
        infra = next(infra_gen)
        query_repo = get_graph_query_repository(settings, infra)
        query_svc = get_graph_query_service(settings, gen_reader, query_repo)
        return GraphReadAdapter(generation_reader=gen_reader, query_service=query_svc)
    except Exception as exc:
        logger.debug("Graph service unavailable for retrieval: %s", exc)
        return None


def get_knowledge_query_service(
    canonical_port: Annotated[CanonicalReadPort, Depends(get_canonical_read_port)],
    search_port: Annotated[SearchReadPort | None, Depends(get_search_read_port)],
    graph_port: Annotated[GraphReadPort | None, Depends(get_graph_read_port)],
    policy: Annotated[RetrievalPolicy, Depends(get_retrieval_policy)],
    cursor_secret: Annotated[str, Depends(get_retrieval_cursor_secret)],
) -> KnowledgeQueryService:
    """Provide KnowledgeQueryService wired with available adapters and policy."""
    return KnowledgeQueryService(
        canonical_port=canonical_port,
        search_port=search_port,
        graph_port=graph_port,
        policy=policy,
        cursor_secret_key=cursor_secret,
    )


def get_evidence_planner(
    canonical_port: Annotated[CanonicalReadPort, Depends(get_canonical_read_port)],
    policy: Annotated[RetrievalPolicy, Depends(get_retrieval_policy)],
) -> EvidencePlanner:
    """Provide EvidencePlanner wired with canonical port and policy."""
    return EvidencePlanner(canonical_port=canonical_port, policy=policy)


__all__ = [
    "get_canonical_read_port",
    "get_evidence_planner",
    "get_graph_read_port",
    "get_knowledge_query_service",
    "get_retrieval_cursor_secret",
    "get_retrieval_policy",
    "get_search_read_port",
    "set_canonical_read_port",
    "set_graph_read_port",
    "set_retrieval_cursor_secret",
    "set_retrieval_policy",
    "set_search_read_port",
]
