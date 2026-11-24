"""FastAPI boundary tests for the Architecture Analysis Report API."""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1 import reports as api
from backend.platform.analysis.application.dependencies import (
    DelegatedRequestContext,
    get_architecture_query_service,
    get_delegated_context,
)
from backend.platform.analysis.architecture.dto import ArchitectureVersionResponse
from backend.platform.delivery.artifacts import VerifiedArtifactHandle
from backend.platform.delivery.contracts import (
    ArtifactReference,
    HandlerProfile,
    OutputDigests,
    ProducerProfile,
    VersionScope,
    WorkKind,
    WorkSlot,
)
from backend.platform.reports.api_contracts import (
    ReportCollection,
    ReportGenerationPage,
    ReportGenerationSummary,
    ReportRetryResponse,
    ReportSlotStatus,
    ReportSummary,
)
from backend.platform.reports.configuration import ReportLimits
from backend.platform.reports.contracts import (
    ReportArtifactMember,
)
from backend.platform.reports.cursors import (
    ReportCursor,
    ReportCursorKey,
    ReportCursorSigner,
)


class FakeHandle(VerifiedArtifactHandle):
    def __init__(self, data: bytes) -> None:
        self.stream = io.BytesIO(data)
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        return self.stream.read(size)

    def close(self) -> None:
        self.closed = True


def make_version_record(
    version_id: UUID, project_id: UUID
) -> ArchitectureVersionResponse:
    return ArchitectureVersionResponse(
        id=version_id,
        analysis_id=uuid4(),
        project_id=project_id,
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        sequence_number=1,
        architecture_schema_version="1.0.0",
        ir_schema_version="1.0.0",
        content_digest="a" * 64,
        entity_count=10,
        relationship_count=5,
        evidence_count=12,
        unresolved_relationship_count=1,
        conflict_count=0,
        completeness={},
        published_at=datetime.now(UTC),
    )


@pytest.fixture
def api_fixture():
    project_id = uuid4()
    version_id = uuid4()
    report_id = uuid4()
    generation_id = uuid4()
    actor_id = uuid4()

    record = make_version_record(version_id, project_id)
    scope = VersionScope(
        project_id=project_id,
        repository_id=record.repository_id,
        analysis_id=record.analysis_id,
        snapshot_id=record.snapshot_id,
        architecture_version_id=version_id,
        sequence_number=1,
        published_at=datetime.now(UTC),
        canonical_digest="a" * 64,
        source_contract_version="1.0.0",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        configuration_fingerprint="c" * 64,
    )

    profile = HandlerProfile(
        slot=WorkSlot(kind=WorkKind.REPORT, template="architecture_analysis"),
        profile=ProducerProfile(
            producer_id="stacksense.reports",
            producer_version="1.0.0",
            generator_version="1.0.0",
            output_schema_version="1.0.0",
            configuration_fingerprint="0" * 64,
        ),
    )

    pdf_bytes = b"%PDF-1.4 sample verified report bytes"
    pdf_sha = hashlib.sha256(pdf_bytes).hexdigest()

    reference = ArtifactReference(
        scope=scope,
        binding=profile,
        input_fingerprint="f" * 64,
        resource_id=report_id,
        candidate_id=uuid4(),
        generation_id=generation_id,
        artifact_id=uuid4(),
        size_bytes=1024,
        sealed=True,
        digests=OutputDigests(content="1" * 64, spec="2" * 64, layout=None),
    )

    pdf_member = ReportArtifactMember(
        member="pdf",
        file_name="report.pdf",
        media_type="application/pdf",
        schema_version="1.0.0",
        size_bytes=len(pdf_bytes),
        sha256=pdf_sha,
    )

    signer = ReportCursorSigner(key_id="k1", secret="a" * 32, ttl=600)

    class FakeVersions:
        def get_version(self, v_id: UUID, p_id: UUID) -> ArchitectureVersionResponse:
            if v_id != version_id or p_id != project_id:
                raise ValueError("report_not_found")
            return record

    class FakeService:
        def __init__(self) -> None:
            self.limits = ReportLimits()
            self.retry_state = "FAILED"
            self.expected_report_id = report_id
            self.expected_generation_id = generation_id

        def collection(self, **kwargs: Any) -> ReportCollection:
            summary = ReportSummary(
                scope=scope,
                report_id=report_id,
                report_type="architecture_analysis",
                profile=profile,
                input_fingerprint="f" * 64,
                availability="READY",
                readability="verified",
                reference=reference,
                pdf_size_bytes=len(pdf_bytes),
                pdf_sha256=pdf_sha,
                page_count=3,
                spec_digest="2" * 64,
                created_at=datetime.now(UTC),
                accepted_at=datetime.now(UTC),
                observed_at=datetime.now(UTC),
            )
            return ReportCollection(
                scope=scope,
                automatic=ReportSlotStatus(
                    status="READY",
                    waiting_on=(),
                    reference=reference,
                ),
                items=(summary,),
                next_cursor=None,
            )

        def summary(
            self,
            record: ArchitectureVersionResponse,
            runtime: Any,
            role: str,
            report_id: UUID,
            generation_id: UUID | None = None,
        ) -> ReportSummary:
            return ReportSummary(
                scope=scope,
                report_id=report_id,
                report_type="architecture_analysis",
                profile=profile,
                input_fingerprint="f" * 64,
                availability="READY",
                readability="verified",
                reference=reference,
                pdf_size_bytes=len(pdf_bytes),
                pdf_sha256=pdf_sha,
                page_count=3,
                spec_digest="2" * 64,
                created_at=datetime.now(UTC),
                accepted_at=datetime.now(UTC),
                observed_at=datetime.now(UTC),
            )

        def generations(
            self,
            record: ArchitectureVersionResponse,
            report_id: UUID,
            actor_id: UUID,
            limit: int = 20,
            cursor: str | None = None,
        ) -> ReportGenerationPage:
            if cursor is not None:
                c = signer.read(cursor)
                if c.report_id != report_id:
                    raise ValueError("report_cursor_invalid")

            item = ReportGenerationSummary(
                generation_id=generation_id,
                artifact_id=uuid4(),
                accepted_at=datetime.now(UTC),
                page_count=3,
                pdf_size_bytes=len(pdf_bytes),
                pdf_sha256=pdf_sha,
                report_spec_digest="0" * 64,
                reference=reference,
            )
            next_cur = None
            if cursor is None:
                next_cur = signer.issue(
                    ReportCursor(
                        kid="k1",
                        operation="generations",
                        actor_id=actor_id,
                        project_id=project_id,
                        version_id=version_id,
                        report_id=report_id,
                        after=ReportCursorKey(
                            accepted_at=datetime.now(UTC), id=generation_id
                        ),
                        issued_at=int(datetime.now(UTC).timestamp()),
                        expires_at=int(datetime.now(UTC).timestamp()) + 600,
                    )
                )
            return ReportGenerationPage(
                scope=scope,
                report_id=report_id,
                items=(item,),
                next_cursor=next_cur,
            )

        def generation_detail(
            self,
            record: ArchitectureVersionResponse,
            report_id: UUID,
            generation_id: UUID,
        ) -> ReportGenerationSummary:
            if (
                report_id != self.expected_report_id
                or generation_id != self.expected_generation_id
            ):
                raise ValueError("report_not_found")
            return ReportGenerationSummary(
                generation_id=self.expected_generation_id,
                artifact_id=uuid4(),
                accepted_at=datetime.now(UTC),
                page_count=3,
                pdf_size_bytes=len(pdf_bytes),
                pdf_sha256=pdf_sha,
                report_spec_digest="0" * 64,
                reference=reference,
            )

        def open_pdf(
            self,
            record: ArchitectureVersionResponse,
            report_id: UUID,
            generation_id: UUID | None = None,
        ) -> tuple[
            VerifiedArtifactHandle, ReportArtifactMember, ArchitectureVersionResponse
        ]:
            if report_id != self.expected_report_id:
                raise ValueError("report_not_found")
            if (
                generation_id is not None
                and generation_id != self.expected_generation_id
            ):
                raise ValueError("report_not_found")
            return FakeHandle(pdf_bytes), pdf_member, record

        def retry(
            self,
            record: ArchitectureVersionResponse,
            report_id: UUID,
            idempotency_key: str,
            actor_id: UUID,
            role: str,
            runtime: Any,
        ) -> ReportRetryResponse:
            if role not in {"OWNER", "ADMIN"}:
                raise ValueError("report_forbidden")
            if self.retry_state != "FAILED":
                raise ValueError("report_conflict")
            return ReportRetryResponse(
                scope=scope,
                report_id=report_id,
                work_id=uuid4(),
                operation_id=uuid4(),
                state="PENDING",
            )

    service = FakeService()
    context = DelegatedRequestContext(
        actor_id=actor_id,
        role="OWNER",
        project_id=project_id,
    )

    app = FastAPI()
    app.include_router(api.router, prefix="/api/v1")
    app.dependency_overrides[get_delegated_context] = lambda: context
    app.dependency_overrides[get_architecture_query_service] = FakeVersions
    app.dependency_overrides[api.get_report_service_dependency] = lambda: service
    app.dependency_overrides[api.get_delivery_coordinator] = lambda: None

    with TestClient(app) as client:
        yield (
            client,
            record,
            report_id,
            generation_id,
            context,
            service,
            pdf_bytes,
            signer,
        )


def test_reports_collection_endpoint(api_fixture):
    client, record, report_id, _, _, _, _, _ = api_fixture
    url = f"/api/v1/architecture-versions/{record.id}/reports"
    res = client.get(url, params={"project_id": str(record.project_id)})
    assert res.status_code == 200, res.text
    data = res.json()
    assert "scope" in data
    assert data["automatic"]["status"] == "READY"
    assert len(data["items"]) == 1
    assert data["items"][0]["report_id"] == str(report_id)
    assert data["items"][0]["availability"] == "READY"


def test_report_summary_endpoint(api_fixture):
    client, record, report_id, gen_id, _, _, _, _ = api_fixture
    url = f"/api/v1/architecture-versions/{record.id}/reports/{report_id}"
    res = client.get(url, params={"project_id": str(record.project_id)})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["report_id"] == str(report_id)
    assert data["availability"] == "READY"
    assert data["page_count"] == 3

    # Historical generation query
    res_hist = client.get(
        url,
        params={
            "project_id": str(record.project_id),
            "generation_id": str(gen_id),
        },
    )
    assert res_hist.status_code == 200


def test_report_generations_history_and_cursor(api_fixture):
    client, record, report_id, gen_id, _, _, _, signer = api_fixture
    url = f"/api/v1/architecture-versions/{record.id}/reports/{report_id}/generations"
    res = client.get(url, params={"project_id": str(record.project_id), "limit": 10})
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["generation_id"] == str(gen_id)
    assert data["next_cursor"] is not None

    # Follow next_cursor
    res_page2 = client.get(
        url,
        params={
            "project_id": str(record.project_id),
            "cursor": data["next_cursor"],
        },
    )
    assert res_page2.status_code == 200

    # Tampered cursor -> approved 400 report_cursor_invalid
    res_tampered = client.get(
        url,
        params={
            "project_id": str(record.project_id),
            "cursor": data["next_cursor"] + "corrupt",
        },
    )
    assert res_tampered.status_code == 400
    assert res_tampered.json()["error"]["code"] == "report_cursor_invalid"

    # Expired cursor -> 410 report_cursor_expired
    expired_cur = signer.issue(
        ReportCursor(
            kid="k1",
            operation="generations",
            actor_id=record.project_id,
            project_id=record.project_id,
            version_id=record.id,
            report_id=report_id,
            after=ReportCursorKey(accepted_at=datetime.now(UTC), id=gen_id),
            issued_at=int(datetime.now(UTC).timestamp()) - 500,
            expires_at=int(datetime.now(UTC).timestamp()) - 100,
        )
    )
    res_expired = client.get(
        url,
        params={
            "project_id": str(record.project_id),
            "cursor": expired_cur,
        },
    )
    assert res_expired.status_code == 410
    assert res_expired.json()["error"]["code"] == "report_cursor_expired"


def test_report_generation_detail_endpoint(api_fixture):
    client, record, report_id, gen_id, _, _, _, _ = api_fixture
    prefix = f"/api/v1/architecture-versions/{record.id}/reports/{report_id}"
    url = f"{prefix}/generations/{gen_id}"
    res = client.get(url, params={"project_id": str(record.project_id)})
    assert res.status_code == 200, res.text
    assert res.json()["generation_id"] == str(gen_id)

    # Unknown generation
    res_not_found = client.get(
        f"{prefix}/generations/{uuid4()}",
        params={"project_id": str(record.project_id)},
    )
    assert res_not_found.status_code == 404


def test_report_download_active_and_exact(api_fixture):
    client, record, report_id, gen_id, _, _, pdf_bytes, _ = api_fixture

    # Active download
    active_url = (
        f"/api/v1/architecture-versions/{record.id}/reports/{report_id}/download"
    )
    res_active = client.get(active_url, params={"project_id": str(record.project_id)})
    assert res_active.status_code == 404  # No mutable download alias.

    # Exact generation download
    prefix = f"/api/v1/architecture-versions/{record.id}/reports/{report_id}"
    exact_url = f"{prefix}/generations/{gen_id}/download"
    res_exact = client.get(exact_url, params={"project_id": str(record.project_id)})
    assert res_exact.status_code == 200
    assert res_exact.content == pdf_bytes
    assert res_exact.headers["cache-control"] == "private, no-store"
    assert res_exact.headers["content-type"] == "application/pdf"
    assert res_exact.headers["content-length"] == str(len(pdf_bytes))
    assert res_exact.headers["x-content-type-options"] == "nosniff"


def test_report_download_rejects_range_header(api_fixture):
    client, record, report_id, gen_id, _, _, _, _ = api_fixture
    url = (
        f"/api/v1/architecture-versions/{record.id}/reports/{report_id}"
        f"/generations/{gen_id}/download"
    )
    res = client.get(
        url,
        params={"project_id": str(record.project_id)},
        headers={"Range": "bytes=0-100"},
    )
    assert res.status_code == 416
    assert res.json()["error"]["code"] == "report_range_unsupported"


def test_report_retry_endpoint_is_not_a_parallel_lifecycle(api_fixture):
    client, record, report_id, *_ = api_fixture
    response = client.post(
        f"/api/v1/architecture-versions/{record.id}/reports/{report_id}/retry",
        params={"project_id": str(record.project_id)},
        json={"idempotency_key": "retry-1"},
    )
    assert response.status_code == 404
    # Actual retries remain owned by the existing delivery/retry route and its tests.


def test_report_authentication_and_cross_project(api_fixture):
    client, record, report_id, _, context, _, _, _ = api_fixture
    url = f"/api/v1/architecture-versions/{record.id}/reports"

    # 1. Unauthenticated actor
    object.__setattr__(context, "actor_id", None)
    res_auth = client.get(url, params={"project_id": str(record.project_id)})
    assert res_auth.status_code == 401
    assert res_auth.json()["error"]["code"] == "report_authentication_required"

    # 2. Cross-project request mismatch
    object.__setattr__(context, "actor_id", uuid4())
    res_cross = client.get(url, params={"project_id": str(uuid4())})
    assert res_cross.status_code in (403, 404)
