"""Export deterministic C0-C4 public schemas and C5 transport manifest fixtures.

This dev-only script exports the public model schemas, controlled enums,
transport limits, and route manifest into `c5-contracts.json` without
starting any infrastructure or mutating production code.
"""

# ruff: noqa: E402, E501

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from backend.api.v1.knowledge import SearchRebuildRequest
from backend.platform.delivery.api_contracts import (
    DeliverySummary,
    RetryAccepted,
    RetryRequest,
)
from backend.platform.delivery.contracts import DiagramTemplate
from backend.platform.delivery.reprojection import SearchReprojectionAccepted
from backend.platform.diagrams.api_contracts import (
    DiagramCollection,
    DiagramSummary,
    GenerationPage,
    MemberPage,
)
from backend.platform.diagrams.contracts import (
    DiagramSpec,
    DiagramViewRequest,
    DiagramViewResponse,
    LayoutSpec,
    PreparedDiagram,
)
from backend.platform.knowledge.contracts import (
    SearchPage,
    SearchStatus,
)
from backend.platform.knowledge.model import KnowledgeDocumentKind
from backend.platform.knowledge.retrieval_contracts import (
    ContainmentDirection,
    ContextBundle,
    ContextRequest,
    EvidencePage,
    FreshnessState,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    ResolutionState,
    RetrievalOperation,
    RetrievalOutcome,
    SelectionRationaleCode,
    SourceKind,
    TraversalDirection,
)
from backend.platform.reports.api_contracts import (
    ReportCollection,
    ReportGenerationPage,
    ReportGenerationSummary,
    ReportSummary,
)

C5_MANIFEST_VERSION = "1.0.0"

ROUTES_MANIFEST = [
    {
        "name": "delivery_status",
        "method": "GET",
        "express_path": "/architecture-versions/:versionId/delivery",
        "upstream_path": "/architecture-versions/{version_id}/delivery",
        "required_query_params": ["project_id"],
        "optional_query_params": [],
        "request_body_model": None,
        "response_model": "DeliverySummary",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "retry_delivery",
        "method": "POST",
        "express_path": "/architecture-versions/:versionId/delivery/retry",
        "upstream_path": "/architecture-versions/{version_id}/delivery/retry",
        "required_query_params": ["project_id"],
        "optional_query_params": [],
        "request_body_model": "RetryRequest",
        "response_model": "RetryAccepted",
        "status_code": 202,
        "role_required": "ADMIN",
    },
    {
        "name": "search_status",
        "method": "GET",
        "express_path": "/architecture-versions/:versionId/search/status",
        "upstream_path": "/architecture-versions/{version_id}/search/status",
        "required_query_params": ["project_id"],
        "optional_query_params": [],
        "request_body_model": None,
        "response_model": "SearchStatus",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "search",
        "method": "GET",
        "express_path": "/architecture-versions/:versionId/search",
        "upstream_path": "/architecture-versions/{version_id}/search",
        "required_query_params": ["project_id", "q"],
        "optional_query_params": [
            "mode",
            "document_kinds",
            "entity_kinds",
            "statuses",
            "limit",
            "cursor",
            "timeout_seconds",
        ],
        "request_body_model": None,
        "response_model": "SearchPage",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "search_rebuild",
        "method": "POST",
        "express_path": "/architecture-versions/:versionId/search/rebuild",
        "upstream_path": "/architecture-versions/{version_id}/search/rebuild",
        "required_query_params": ["project_id"],
        "optional_query_params": [],
        "request_body_model": "SearchRebuildRequest",
        "response_model": "SearchReprojectionAccepted",
        "status_code": 202,
        "role_required": "ADMIN",
    },
    {
        "name": "knowledge_query",
        "method": "POST",
        "express_path": "/architecture-versions/:versionId/knowledge/query",
        "upstream_path": "/architecture-versions/{version_id}/knowledge/query",
        "required_query_params": ["project_id"],
        "optional_query_params": [],
        "request_body_model": "KnowledgeQueryRequest",
        "response_model": "KnowledgeQueryResponse",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "knowledge_context",
        "method": "POST",
        "express_path": "/architecture-versions/:versionId/knowledge/context",
        "upstream_path": "/architecture-versions/{version_id}/knowledge/context",
        "required_query_params": ["project_id"],
        "optional_query_params": [],
        "request_body_model": "ContextRequest",
        "response_model": "ContextBundle",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "knowledge_evidence",
        "method": "GET",
        "express_path": "/architecture-versions/:versionId/knowledge/evidence",
        "upstream_path": "/architecture-versions/{version_id}/knowledge/evidence",
        "required_query_params": ["project_id"],
        "optional_query_params": [
            "entity_id",
            "relationship_id",
            "evidence_id",
            "limit",
            "cursor",
        ],
        "request_body_model": None,
        "response_model": "EvidencePage",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "diagram_collection",
        "method": "GET",
        "express_path": "/architecture-versions/:versionId/diagrams",
        "upstream_path": "/architecture-versions/{version_id}/diagrams",
        "required_query_params": ["project_id"],
        "optional_query_params": [],
        "request_body_model": None,
        "response_model": "DiagramCollection",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "diagram_template",
        "method": "GET",
        "express_path": "/architecture-versions/:versionId/diagrams/:template",
        "upstream_path": "/architecture-versions/{version_id}/diagrams/{template}",
        "required_query_params": ["project_id"],
        "optional_query_params": ["generation_id"],
        "request_body_model": None,
        "response_model": "DiagramSummary",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "diagram_generations",
        "method": "GET",
        "express_path": "/architecture-versions/:versionId/diagrams/:template/generations",
        "upstream_path": "/architecture-versions/{version_id}/diagrams/{template}/generations",
        "required_query_params": ["project_id"],
        "optional_query_params": ["limit", "cursor"],
        "request_body_model": None,
        "response_model": "GenerationPage",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "diagram_spec",
        "method": "GET",
        "express_path": "/architecture-versions/:versionId/diagrams/:template/generations/:generationId/spec",
        "upstream_path": "/architecture-versions/{version_id}/diagrams/{template}/generations/{generation_id}/spec",
        "required_query_params": ["project_id"],
        "optional_query_params": [],
        "request_body_model": None,
        "response_model": "DiagramSpec",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "diagram_layout",
        "method": "GET",
        "express_path": "/architecture-versions/:versionId/diagrams/:template/generations/:generationId/layout",
        "upstream_path": "/architecture-versions/{version_id}/diagrams/{template}/generations/{generation_id}/layout",
        "required_query_params": ["project_id"],
        "optional_query_params": [],
        "request_body_model": None,
        "response_model": "LayoutSpec",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "diagram_view",
        "method": "POST",
        "express_path": "/architecture-versions/:versionId/diagrams/:template/generations/:generationId/view",
        "upstream_path": "/architecture-versions/{version_id}/diagrams/{template}/generations/{generation_id}/view",
        "required_query_params": ["project_id"],
        "optional_query_params": [],
        "request_body_model": "DiagramViewRequest",
        "response_model": "DiagramViewResponse",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "diagram_members",
        "method": "GET",
        "express_path": "/architecture-versions/:versionId/diagrams/:template/generations/:generationId/members",
        "upstream_path": "/architecture-versions/{version_id}/diagrams/{template}/generations/{generation_id}/members",
        "required_query_params": ["project_id"],
        "optional_query_params": ["group_id", "entity_id", "limit", "cursor"],
        "request_body_model": None,
        "response_model": "MemberPage",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "diagram_export",
        "method": "GET",
        "express_path": "/architecture-versions/:versionId/diagrams/:template/generations/:generationId/export",
        "upstream_path": "/architecture-versions/{version_id}/diagrams/{template}/generations/{generation_id}/export",
        "required_query_params": ["project_id"],
        "optional_query_params": ["format"],
        "request_body_model": None,
        "response_model": "PreparedDiagram",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "report_collection",
        "method": "GET",
        "express_path": "/architecture-versions/:versionId/reports",
        "upstream_path": "/architecture-versions/{version_id}/reports",
        "required_query_params": ["project_id"],
        "optional_query_params": ["limit", "cursor"],
        "request_body_model": None,
        "response_model": "ReportCollection",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "report_summary",
        "method": "GET",
        "express_path": "/architecture-versions/:versionId/reports/:reportId",
        "upstream_path": "/architecture-versions/{version_id}/reports/{report_id}",
        "required_query_params": ["project_id"],
        "optional_query_params": ["generation_id"],
        "request_body_model": None,
        "response_model": "ReportSummary",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "report_generations",
        "method": "GET",
        "express_path": "/architecture-versions/:versionId/reports/:reportId/generations",
        "upstream_path": "/architecture-versions/{version_id}/reports/{report_id}/generations",
        "required_query_params": ["project_id"],
        "optional_query_params": ["limit", "cursor"],
        "request_body_model": None,
        "response_model": "ReportGenerationPage",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "report_generation_detail",
        "method": "GET",
        "express_path": "/architecture-versions/:versionId/reports/:reportId/generations/:generationId",
        "upstream_path": "/architecture-versions/{version_id}/reports/{report_id}/generations/{generation_id}",
        "required_query_params": ["project_id"],
        "optional_query_params": [],
        "request_body_model": None,
        "response_model": "ReportGenerationSummary",
        "status_code": 200,
        "role_required": "VIEWER",
    },
    {
        "name": "report_generation_download",
        "method": "GET",
        "express_path": "/architecture-versions/:versionId/reports/:reportId/generations/:generationId/download",
        "upstream_path": "/architecture-versions/{version_id}/reports/{report_id}/generations/{generation_id}/download",
        "required_query_params": ["project_id"],
        "optional_query_params": [],
        "request_body_model": None,
        "response_model": "application/pdf",
        "status_code": 200,
        "role_required": "VIEWER",
    },
]

MODELS_TO_EXPORT: dict[str, type[BaseModel]] = {
    "DeliverySummary": DeliverySummary,
    "RetryAccepted": RetryAccepted,
    "RetryRequest": RetryRequest,
    "SearchStatus": SearchStatus,
    "SearchPage": SearchPage,
    "SearchRebuildRequest": SearchRebuildRequest,
    "SearchReprojectionAccepted": SearchReprojectionAccepted,
    "KnowledgeQueryRequest": KnowledgeQueryRequest,
    "KnowledgeQueryResponse": KnowledgeQueryResponse,
    "ContextRequest": ContextRequest,
    "ContextBundle": ContextBundle,
    "EvidencePage": EvidencePage,
    "DiagramCollection": DiagramCollection,
    "DiagramSummary": DiagramSummary,
    "GenerationPage": GenerationPage,
    "DiagramSpec": DiagramSpec,
    "LayoutSpec": LayoutSpec,
    "DiagramViewRequest": DiagramViewRequest,
    "DiagramViewResponse": DiagramViewResponse,
    "MemberPage": MemberPage,
    "PreparedDiagram": PreparedDiagram,
    "ReportCollection": ReportCollection,
    "ReportSummary": ReportSummary,
    "ReportGenerationPage": ReportGenerationPage,
    "ReportGenerationSummary": ReportGenerationSummary,
}

ENUMS_TO_EXPORT: dict[str, list[str]] = {
    "DiagramTemplate": [t.value for t in DiagramTemplate],
    "RetrievalOperation": [o.value for o in RetrievalOperation],
    "ResolutionState": [s.value for s in ResolutionState],
    "RetrievalOutcome": [o.value for o in RetrievalOutcome],
    "SourceKind": [k.value for k in SourceKind],
    "FreshnessState": [f.value for f in FreshnessState],
    "TraversalDirection": [d.value for d in TraversalDirection],
    "ContainmentDirection": [c.value for c in ContainmentDirection],
    "SelectionRationaleCode": [r.value for r in SelectionRationaleCode],
    "KnowledgeDocumentKind": [k.value for k in KnowledgeDocumentKind],
    "SearchMode": ["lexical", "semantic", "hybrid"],
    "DeliveryEligibility": [
        "ELIGIBLE",
        "NOT_SCHEDULED",
        "TERMINAL",
        "WAITING_FOR_DIAGRAMS",
    ],
    "ReportStatus": ["WAITING", "BUILDING", "READY", "FAILED"],
    "ReportReadability": ["READABLE", "METADATA_ONLY", "FAILED", "UNAVAILABLE"],
}

TRANSPORT_LIMITS: dict[str, int] = {
    "max_query_bytes": 32768,
    "max_json_body_bytes": 131072,
    "max_metadata_response_bytes": 4194304,
    "max_c3_response_bytes": 2097152,
    "max_diagram_spec_bytes": 16777216,
    "max_diagram_layout_bytes": 33554432,
    "max_diagram_export_bytes": 67108864,
    "max_diagram_svg_bytes": 50331648,
    "max_pdf_bytes": 67108864,
    "read_timeout_seconds": 30,
    "context_timeout_seconds": 120,
    "artifact_spool_timeout_seconds": 90,
    "artifact_relay_timeout_seconds": 60,
    "artifact_hard_timeout_seconds": 150,
    "max_active_artifact_relays": 2,
    "max_filter_elements": 50,
    "search_page_default": 25,
    "search_page_max": 100,
    "diagram_history_page_default": 50,
    "diagram_history_page_max": 200,
    "report_history_page_default": 20,
    "report_history_page_max": 100,
    "c3_query_limit_default": 25,
    "c3_query_limit_max": 100,
}

ERROR_CODES: dict[str, list[str]] = {
    "transport": [
        "intelligence_upstream_invalid",
        "intelligence_transport_limit",
        "intelligence_transport_busy",
        "intelligence_upstream_unavailable",
        "intelligence_upstream_timeout",
    ],
    "upstream_allowed_codes": [
        "retrieval_not_found",
        "retrieval_generation_changed",
        "retrieval_cursor_expired",
        "retrieval_cursor_invalid",
        "retrieval_capacity_exceeded",
        "retrieval_invalid_request",
        "retrieval_unavailable",
        "retrieval_deadline_exceeded",
        "retrieval_integrity_failed",
        "search_invalid_mode",
        "invalid_document_kind",
        "search_not_ready",
        "search_generation_changed",
        "search_cursor_expired",
        "search_cursor_invalid",
        "search_capacity_exceeded",
        "search_deadline_exceeded",
        "search_backend_unavailable",
        "search_capability_unavailable",
        "search_integrity_failed",
        "diagram_store_unavailable",
        "diagram_input_invalid",
        "diagram_limit_exceeded",
        "diagram_range_unsupported",
        "report_range_unsupported",
        "delivery_reprojection_forbidden",
    ],
}


def build_c5_fixtures() -> dict[str, Any]:
    schemas: dict[str, Any] = {}
    for name, model_cls in MODELS_TO_EXPORT.items():
        schemas[name] = model_cls.model_json_schema()

    return {
        "c5_version": C5_MANIFEST_VERSION,
        "manifest_name": "P5_C5_TRANSPORT_MANIFEST",
        "routes": ROUTES_MANIFEST,
        "schemas": schemas,
        "enums": ENUMS_TO_EXPORT,
        "transport_limits": TRANSPORT_LIMITS,
        "error_codes": ERROR_CODES,
    }


def export_fixtures(output_path: Path) -> None:
    data = build_c5_fixtures()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    print(f"Successfully exported C5 fixtures to {output_path}")


if __name__ == "__main__":
    target = (
        Path(__file__).resolve().parent.parent.parent
        / "fixtures"
        / "p5"
        / "transport"
        / "c5-contracts.json"
    )
    export_fixtures(target)
