"""Published Architecture Model API authorization and mapping tests."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.platform.analysis.application.dependencies import (
    get_architecture_query_service,
)
from backend.platform.analysis.architecture.dto import (
    ArchitectureCollectionResponse,
    ArchitectureEntityResponse,
    ArchitectureVersionResponse,
)
from backend.platform.config import get_settings
from backend.platform.errors import ArchitectureResultNotFoundError

SECRET = get_settings().internal_api_secret_key.get_secret_value()
PROJECT_ID = uuid4()
VERSION_ID = uuid4()
ANALYSIS_ID = uuid4()


def _headers(project_id: UUID = PROJECT_ID) -> dict[str, str]:
    return {
        "X-Service-Token": SECRET,
        "X-Actor-Id": str(uuid4()),
        "X-Actor-Role": "VIEWER",
        "X-Project-Id": str(project_id),
    }


class _QueryStub:
    def get_for_analysis(
        self, analysis_id: UUID, project_id: UUID
    ) -> ArchitectureVersionResponse:
        if analysis_id != ANALYSIS_ID:
            raise ArchitectureResultNotFoundError()
        return self.get_version(VERSION_ID, project_id)

    def get_version(
        self, version_id: UUID, project_id: UUID
    ) -> ArchitectureVersionResponse:
        return ArchitectureVersionResponse(
            id=version_id,
            analysis_id=ANALYSIS_ID,
            project_id=project_id,
            repository_id=uuid4(),
            snapshot_id=uuid4(),
            sequence_number=1,
            architecture_schema_version="1.0.0",
            ir_schema_version="1.0.0",
            content_digest="a" * 64,
            entity_count=1,
            relationship_count=0,
            evidence_count=1,
            unresolved_relationship_count=0,
            conflict_count=0,
            completeness={},
            published_at=datetime.now(UTC),
        )

    def list_entities(
        self,
        version_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
        kind: str | None = None,
        status: str | None = None,
    ) -> ArchitectureCollectionResponse:
        entity = ArchitectureEntityResponse(
            id=uuid4(),
            logical_id="architecture://safe/entity",
            kind=kind or "service",
            name="API",
            namespace=("application",),
            status=status or "confirmed",
            evidence_ids=("evidence://safe",),
            source_ir_keys=("service",),
            metadata={},
        )
        return ArchitectureCollectionResponse(
            items=[entity], total=3, limit=limit, offset=offset
        )


def test_version_route_requires_service_auth_and_project_scope() -> None:
    app.dependency_overrides[get_architecture_query_service] = lambda: _QueryStub()
    client = TestClient(app)
    try:
        assert (
            client.get(
                f"/api/v1/architecture-versions/{VERSION_ID}",
                params={"project_id": str(PROJECT_ID)},
            ).status_code
            == 401
        )
        response = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}",
            params={"project_id": str(PROJECT_ID)},
            headers=_headers(uuid4()),
        )
        assert response.status_code == 403
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_published_routes_return_bounded_pagination_and_structured_404() -> None:
    app.dependency_overrides[get_architecture_query_service] = lambda: _QueryStub()
    client = TestClient(app)
    try:
        response = client.get(
            f"/api/v1/architecture-versions/{VERSION_ID}/entities",
            params={"project_id": str(PROJECT_ID), "limit": 1, "offset": 2},
            headers=_headers(),
        )
        assert response.status_code == 200
        assert response.json()["total"] == 3
        assert response.json()["limit"] == 1
        assert response.json()["offset"] == 2

        missing = client.get(
            f"/api/v1/analyses/{uuid4()}/architecture",
            params={"project_id": str(PROJECT_ID)},
            headers=_headers(),
        )
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "architecture_result_not_found"
    finally:
        client.close()
        app.dependency_overrides.clear()
