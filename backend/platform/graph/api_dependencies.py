"""FastAPI dependency providers for P4-D1 Graph API infrastructure."""

from typing import Annotated
from uuid import uuid4

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from backend.platform.dependency_injection import get_database_session
from backend.platform.errors import AnalysisInputError
from backend.platform.graph.api_service import (
    GraphApiService,
    GraphProjectionStatusReader,
    SqlAlchemyGraphProjectionStatusReader,
)
from backend.platform.graph.dependencies import get_graph_projection_lifecycle
from backend.platform.graph.lifecycle import GraphProjectionLifecycle


def get_graph_status_reader(
    session: Annotated[Session, Depends(get_database_session)],
) -> GraphProjectionStatusReader:
    """Provide the request-scoped single-statement PostgreSQL status reader."""
    return SqlAlchemyGraphProjectionStatusReader(session)


def get_graph_api_service(
    status_reader: Annotated[
        GraphProjectionStatusReader, Depends(get_graph_status_reader)
    ],
    lifecycle: Annotated[
        GraphProjectionLifecycle, Depends(get_graph_projection_lifecycle)
    ],
    session: Annotated[Session, Depends(get_database_session)],
) -> GraphApiService:
    """Provide the M4 graph application service facade."""
    return GraphApiService(
        status_reader=status_reader,
        lifecycle=lifecycle,
        commit_fn=session.commit,
        rollback_fn=session.rollback,
    )


def get_correlation_id(
    x_correlation_id: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
) -> str:
    """Validate a caller correlation header (1..255 chars) or generate UUID."""
    if x_correlation_id is not None:
        if 1 <= len(x_correlation_id) <= 255:
            return x_correlation_id
        raise AnalysisInputError(
            "X-Correlation-Id header must be between 1 and 255 characters.",
            details={"header": "X-Correlation-Id", "length": len(x_correlation_id)},
        )
    return str(uuid4())
