"""P5-C3 explicit retrieval policy configuration.

This module defines the typed RetrievalPolicy deployment configuration adhering
to §7A.9 and §7A.11 of PROJECT_CONTEXT.md. Missing, invalid, or malformed
configuration safely disables M3 retrieval operations via RetrievalUnavailableError.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from threading import BoundedSemaphore
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from backend.platform.knowledge.retrieval_contracts import (
    RetrievalCapacityExceededError,
    RetrievalDeadlineExceededError,
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
    max_source_calls: int = Field(default=20, gt=0)
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
    max_concurrent_operations: int = Field(default=1, gt=0)

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
        values = json.loads(raw)
        required = set(RetrievalPolicy.model_fields) - {"policy_version"}
        if not isinstance(values, dict) or not required.issubset(values):
            raise ValueError("Every operating limit must be explicit")
        return RetrievalPolicy.model_validate_json(raw)
    except Exception as exc:
        raise RetrievalUnavailableError(
            "Invalid or missing retrieval policy configuration",
        ) from exc


class RetrievalBudget:
    """One deadline and aggregate work account for an entire public operation."""

    def __init__(self, policy: RetrievalPolicy, *, prior_work: int = 0) -> None:
        self.policy = policy
        self.deadline = time.monotonic() + policy.total_deadline_seconds
        self.calls = 0
        self.work = prior_work
        self.rows: dict[str, int] = {}
        self.search_pages = 0
        self.final_calls = 0

    def reserve_final_checks(self, *, search: bool, graph: bool) -> None:
        self.final_calls = 1 + int(search) + int(graph)
        if (
            self.policy.max_source_calls <= self.final_calls
            or self.policy.max_chain_work_units <= self.final_calls
        ):
            raise RetrievalCapacityExceededError(
                "Final validation cannot fit operating budget"
            )
        if search and self.policy.max_search_pages < 2:
            raise RetrievalCapacityExceededError(
                "Search and final probe cannot fit page budget"
            )

    def remaining(self, *, reserve: bool = True) -> float:
        seconds = self.deadline - time.monotonic()
        if reserve:
            seconds -= self.policy.finalization_reserve_seconds
        if seconds <= 0:
            raise RetrievalDeadlineExceededError()
        return seconds

    def charge(self, units: int = 1) -> None:
        self.work += units
        if self.work > self.policy.max_chain_work_units:
            raise RetrievalCapacityExceededError("Continuation work budget exhausted")

    def call(self, source: str, *, final: bool = False) -> float:
        remaining = self.remaining(reserve=not final)
        if final:
            self.final_calls = max(0, self.final_calls - 1)
        elif self.calls + 1 + self.final_calls > self.policy.max_source_calls:
            raise RetrievalCapacityExceededError("Required final calls are reserved")
        self.calls += 1
        self.charge()
        if self.calls > self.policy.max_source_calls:
            raise RetrievalCapacityExceededError("Source call budget exhausted")
        if source == "search":
            self.search_pages += 1
            if self.search_pages > self.policy.max_search_pages:
                raise RetrievalCapacityExceededError("Search page budget exhausted")
        return remaining

    def scanned(self, collection: str, count: int) -> None:
        self.charge(count)
        self.rows[collection] = self.rows.get(collection, 0) + count
        if self.rows[collection] > self.policy.canonical_max_rows_per_collection:
            raise RetrievalCapacityExceededError("Canonical scan budget exhausted")
        self.remaining()


CURRENT_RETRIEVAL_BUDGET: ContextVar[RetrievalBudget | None] = ContextVar(
    "c3_operation_budget", default=None
)


@contextmanager
def operation_budget(budget: RetrievalBudget) -> Iterator[None]:
    semaphore = _admission(
        budget.policy.compute_fingerprint(), budget.policy.max_concurrent_operations
    )
    if not semaphore.acquire(blocking=False):
        raise RetrievalCapacityExceededError("Process retrieval admission exhausted")
    token = CURRENT_RETRIEVAL_BUDGET.set(budget)
    try:
        yield
    finally:
        CURRENT_RETRIEVAL_BUDGET.reset(token)
        semaphore.release()


@lru_cache(maxsize=1)
def _admission(fingerprint: str, limit: int) -> BoundedSemaphore:
    return BoundedSemaphore(limit)


@lru_cache(maxsize=1)
def get_configured_policy(raw: str) -> RetrievalPolicy:
    """Cached retrieval policy accessor."""
    return parse_retrieval_policy(raw)


__all__ = [
    "RetrievalPolicy",
    "get_configured_policy",
    "parse_retrieval_policy",
]
