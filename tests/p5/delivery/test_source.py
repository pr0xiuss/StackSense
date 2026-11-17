"""Public-port discovery/eligibility, exact history and rescan contracts."""

import ast
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from backend.platform.analysis.application.dto import AnalysisResponse
from backend.platform.analysis.domain.constants import AnalysisStatus
from backend.platform.delivery.contracts import DeliveryContractError
from backend.platform.delivery.model import Eligibility
from backend.platform.delivery.source import PublishedVersionReader
from backend.platform.graph.model import ProjectionCounts
from backend.platform.graph.source import (
    PublishedArchitectureCursor,
    PublishedArchitectureHeader,
    PublishedArchitecturePage,
)
from tests.fixtures.p4.graph.fixtures import small_document


class PublicSourceFixture:
    def __init__(self):
        self.document = small_document()
        doc = self.document
        self.header = PublishedArchitectureHeader(
            contract_version="1.0.0",
            architecture_version_id=doc.architecture_version_id,
            analysis_id=doc.analysis_id,
            project_id=doc.project_id,
            repository_id=doc.repository_id,
            snapshot_id=doc.snapshot_id,
            sequence_number=1,
            published_at=datetime.now(UTC),
            configuration_fingerprint=doc.configuration_fingerprint,
            analyzer_version=doc.analyzer_version,
            ir_schema_version=doc.ir_schema_version,
            architecture_schema_version=doc.architecture_schema_version,
            content_digest=doc.content_digest,
            counts=ProjectionCounts(
                len(doc.entities),
                len(doc.relationships),
                len(doc.evidence),
                len(doc.unresolved_relationships),
                len(doc.conflicts),
            ),
        )
        self.headers = [self.header]
        self.loads = []
        self.analysis = AnalysisResponse(
            id=doc.analysis_id,
            project_id=doc.project_id,
            repository_id=doc.repository_id,
            snapshot_id=doc.snapshot_id,
            status="completed",
            configuration={},
            version=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            published_version_id=uuid4(),
        )

    def get_analysis(self, analysis_id, project_id):
        assert (analysis_id, project_id) == (self.analysis.id, self.analysis.project_id)
        return self.analysis

    def list_published(self, *, limit, after=None):
        def key(h):
            return (
                h.project_id,
                h.repository_id,
                h.sequence_number,
                h.architecture_version_id,
            )

        rows = sorted(self.headers, key=key)
        if after:
            rows = [h for h in rows if key(h) > key(after)]
        selected = rows[:limit]
        last = selected[-1] if selected else None
        cursor = (
            PublishedArchitectureCursor(
                last.project_id,
                last.repository_id,
                last.sequence_number,
                last.architecture_version_id,
            )
            if last and len(rows) > limit
            else None
        )
        return PublishedArchitecturePage(tuple(selected), cursor)

    def load_exact(self, version_id, project_id):
        self.loads.append((version_id, project_id))
        return self.document


@pytest.mark.parametrize("status", list(AnalysisStatus))
def test_all_frozen_analysis_states_and_eligibility_revisit(
    status: AnalysisStatus,
) -> None:
    source = PublicSourceFixture()
    source.analysis = replace(source.analysis, status=status.value)
    reader = PublishedVersionReader(source, source.get_analysis)
    inspection = reader.inspect_eligibility(source.header)
    expected = (
        Eligibility.ELIGIBLE
        if status in {AnalysisStatus.COMPLETED, AnalysisStatus.COMPLETED_WITH_WARNINGS}
        else (
            Eligibility.INELIGIBLE
            if status in {AnalysisStatus.FAILED, AnalysisStatus.CANCELLED}
            else Eligibility.WAITING
        )
    )
    assert inspection.eligibility == expected
    assert len(source.loads) == (1 if expected == Eligibility.ELIGIBLE else 0)
    # Published but still-running inputs are revisitable, never permanently lost.
    source.analysis = replace(source.analysis, status="completed")
    assert reader.inspect_eligibility(source.header).eligibility == Eligibility.ELIGIBLE


def test_historical_exact_version_not_latest_and_no_source_cache() -> None:
    source = PublicSourceFixture()
    reader = PublishedVersionReader(source, source.get_analysis)
    assert source.analysis.published_version_id != source.header.architecture_version_id
    reader.inspect_eligibility(source.header)
    assert source.loads == [
        (source.header.architecture_version_id, source.header.project_id)
    ]
    source.document = replace(source.document, architecture_version_id=uuid4())
    with pytest.raises(DeliveryContractError):
        reader.load_exact(source.header)


def test_page_end_resets_cursor_new_earlier_insertion_visible_next_sweep() -> None:
    source = PublicSourceFixture()
    source.headers = [replace(source.header, sequence_number=n) for n in (2, 3)]
    reader = PublishedVersionReader(source, source.get_analysis)
    first = reader.list_published(limit=1)
    assert first.next_cursor is not None
    source.headers.append(replace(source.header, sequence_number=1))
    end = reader.list_published(limit=1, cursor=first.next_cursor)
    assert [h.sequence_number for h in end.items] == [3]
    assert end.next_cursor is None
    restarted = reader.list_published(limit=1, cursor=None)
    assert [h.sequence_number for h in restarted.items] == [1]
    # A crash may replay the page; identity remains the same for durable dedup B2.
    assert reader.list_published(limit=1) == restarted


@pytest.mark.parametrize(
    "field",
    [
        "project_id",
        "repository_id",
        "snapshot_id",
        "analysis_id",
        "content_digest",
        "configuration_fingerprint",
        "analyzer_version",
        "ir_schema_version",
        "architecture_schema_version",
        "counts",
        "contract_version",
    ],
)
def test_invalid_header_or_document_fails_closed(field: str) -> None:
    source = PublicSourceFixture()
    replacement = (
        "e" * 64
        if field == "content_digest"
        else (
            ProjectionCounts(0, 0, 0, 0, 0)
            if field == "counts"
            else uuid4() if field.endswith("_id") else "wrong"
        )
    )
    header = replace(source.header, **{field: replacement})
    reader = PublishedVersionReader(source, lambda *_: source.analysis)
    with pytest.raises(DeliveryContractError):
        reader.inspect_eligibility(header)


def test_missing_document_unknown_status_and_read_errors_not_fabricated_failure() -> (
    None
):
    source = PublicSourceFixture()
    reader = PublishedVersionReader(source, source.get_analysis)
    source.document = None
    with pytest.raises(DeliveryContractError):
        reader.inspect_eligibility(source.header)
    source.analysis = replace(source.analysis, status="invented")
    with pytest.raises(DeliveryContractError):
        reader.inspect_eligibility(source.header)

    def unavailable(*_):
        raise ConnectionError("fixture unavailable")

    reader = PublishedVersionReader(source, unavailable)
    with pytest.raises(ConnectionError):
        reader.inspect_eligibility(source.header)


@pytest.mark.parametrize("limit", [0, 501, True])
def test_bounded_pages(limit: int) -> None:
    source = PublicSourceFixture()
    with pytest.raises(DeliveryContractError):
        PublishedVersionReader(source, source.get_analysis).list_published(limit=limit)


def test_duplicate_bad_cursor_source_page_rejected() -> None:
    source = PublicSourceFixture()
    source.headers = [source.header, source.header]
    with pytest.raises(DeliveryContractError):
        PublishedVersionReader(source, source.get_analysis).list_published(limit=2)


def test_delivery_imports_no_private_providers_or_output_modules() -> None:
    # Resolve repository root explicitly, independent of pytest working directory.
    root = Path(__file__).resolve().parents[3] / "backend" / "platform" / "delivery"
    assert root.is_dir()
    forbidden = (
        "backend.platform.analysis.infra",
        "backend.platform.analysis.architecture.persistence",
        "backend.platform.analysis.architecture.repository",
        "backend.platform.graph.persistence",
        "backend.platform.graph.lifecycle",
        "backend.worker",
        "backend.platform.knowledge",
        "backend.platform.diagrams",
        "backend.platform.reports",
    )
    for file in root.glob("*.py"):
        for node in ast.walk(ast.parse(file.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(forbidden), (file.name, node.module)
