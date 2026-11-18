"""P5-C3 explicit retrieval policy configuration.

This module defines the typed RetrievalPolicy deployment configuration adhering
to §7A.9 and §7A.11 of PROJECT_CONTEXT.md. Missing, invalid, or malformed
configuration safely disables M3 retrieval operations via RetrievalUnavailableError.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from backend.platform.knowledge.retrieval_contracts import (
    RetrievalUnavailableError,
)


class RetrievalPolicy(BaseModel):
    """Explicit versioned deployment policy for bounded C3 retrieval (§7A.9)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    policy_version: Literal["1.0.0"] = "1.0.0"
    max_query_bytes: int = Field(default=500, gt=0, le=2048)
    max_identifier_bytes: int = Field(default=1024, gt=0, le=2048)
    max_subjects: int = Field(default=50, gt=0, le=100)
    max_filters: int = Field(default=20, gt=0, le=50)
    max_operations: int = Field(default=10, gt=0, le=20)
    canonical_page_size: int = Field(default=100, gt=0, le=100)
    canonical_max_rows_per_collection: int = Field(default=1000, gt=0)
    max_retained_candidates: int = Field(default=100, gt=0, le=500)
    max_source_calls: int = Field(default=20, gt=0, le=50)
    max_search_pages: int = Field(default=5, gt=0, le=10)
    max_search_streams: int = Field(default=1, gt=0, le=1)
    max_final_probes: int = Field(default=1, gt=0, le=1)
    max_graph_depth: int = Field(default=5, gt=0, le=5)
    max_graph_nodes: int = Field(default=500, gt=0, le=500)
    max_graph_edges: int = Field(default=1000, gt=0, le=1000)
    max_graph_paths: int = Field(default=25, gt=0, le=25)
    max_selected_facts: int = Field(default=100, gt=0, le=500)
    max_selected_relationships: int = Field(default=200, gt=0, le=1000)
    max_selected_evidence: int = Field(default=100, gt=0, le=500)
    max_selected_unresolved: int = Field(default=50, gt=0, le=200)
    max_selected_conflicts: int = Field(default=50, gt=0, le=200)
    max_output_bytes: int = Field(default=262144, gt=0, le=2097152)  # 256 KiB
    max_cursor_bytes: int = Field(default=2048, gt=0, le=4096)
    cursor_ttl_seconds: float = Field(
        default=300.0, gt=0, le=3600.0, allow_inf_nan=False
    )
    total_deadline_seconds: float = Field(
        default=5.0, gt=0, le=30.0, allow_inf_nan=False
    )
    finalization_reserve_seconds: float = Field(
        default=0.5, gt=0, le=5.0, allow_inf_nan=False
    )
    max_chain_pages: int = Field(default=10, gt=0, le=50)
    max_chain_work_units: int = Field(default=500, gt=0)

    @model_validator(mode="after")
    def validate_budget_relationships(self) -> Self:
        if self.finalization_reserve_seconds >= self.total_deadline_seconds:
            raise ValueError(
                "finalization_reserve_seconds must be strictly less than "
                "total_deadline_seconds"
            )
        return self

    def compute_fingerprint(self) -> str:
        """Deterministic SHA-256 fingerprint over sorted policy values."""
        raw = self.model_dump_json()
        data = json.loads(raw)
        canonical_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def parse_retrieval_policy(raw: str) -> RetrievalPolicy:
    """Parse JSON string into RetrievalPolicy or raise RetrievalUnavailableError."""
    try:
        return RetrievalPolicy.model_validate_json(raw)
    except Exception as exc:
        raise RetrievalUnavailableError(
            "Invalid or missing retrieval policy configuration",
            cause=str(exc),
        ) from exc


@lru_cache(maxsize=1)
def get_configured_policy(raw: str) -> RetrievalPolicy:
    """Cached retrieval policy accessor."""
    return parse_retrieval_policy(raw)


__all__ = [
    "RetrievalPolicy",
    "get_configured_policy",
    "parse_retrieval_policy",
]
