"""Elasticsearch index management, mapping schemas, and sealing protocol.

Implements generation-scoped physical index operations, strict mappings,
deterministic hash computation, and sealed candidate isolation per §7.4 and §7.12.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Final, NamedTuple, Protocol
from uuid import uuid4

from backend.platform.knowledge.contracts import (
    SearchBackendUnavailableError,
    SearchIntegrityError,
)
from backend.platform.knowledge.model import canonical_json

SEARCH_INDEX_SETTINGS: Final[dict[str, Any]] = {
    "index": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "auto_expand_replicas": "0-1",
        "refresh_interval": "1s",
    }
}

SEARCH_INDEX_MAPPINGS: Final[dict[str, Any]] = {
    "dynamic": "strict",
    "properties": {
        "c1_version": {"type": "keyword"},
        "project_id": {"type": "keyword"},
        "architecture_version_id": {"type": "keyword"},
        "repository_id": {"type": "keyword"},
        "snapshot_id": {"type": "keyword"},
        "analysis_id": {"type": "keyword"},
        "generation_id": {"type": "keyword"},
        "index_uuid": {"type": "keyword"},
        "document_kind": {"type": "keyword"},
        "canonical_reference": {"type": "keyword"},
        "knowledge_key": {"type": "keyword"},
        "storage_key": {"type": "keyword"},
        "title": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
        },
        "text_fields": {
            "type": "object",
            "dynamic": True,
        },
        "kind": {"type": "keyword"},
        "status": {"type": "keyword"},
        "source_logical_id": {"type": "keyword"},
        "target_logical_id": {"type": "keyword"},
        "evidence_ids": {"type": "keyword"},
        "source_reference": {
            "type": "object",
            "dynamic": True,
        },
        "safe_metadata": {
            "type": "object",
            "dynamic": True,
        },
        "record_semantic_digest": {"type": "keyword"},
    },
}


def compute_mapping_hash(mappings: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 digest of mapping definition."""
    return hashlib.sha256(canonical_json(mappings).encode("utf-8")).hexdigest()


def compute_settings_hash(settings: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 digest of index settings."""
    return hashlib.sha256(canonical_json(settings).encode("utf-8")).hexdigest()


class RecordSummary(NamedTuple):
    """Independent readback descriptor for candidate index verification."""

    storage_key: str
    knowledge_key: str
    document_kind: str
    record_semantic_digest: str


@dataclass(frozen=True, slots=True)
class BulkIndexResult:
    """Outcome descriptor of a bulk indexing request."""

    total: int
    successful: int
    failed: int
    errors: tuple[dict[str, Any], ...] = ()


class SearchIndexBackend(Protocol):
    """Protocol for physical search index storage and lifecycle operations."""

    def create_index(
        self,
        index_name: str,
        settings: dict[str, Any],
        mappings: dict[str, Any],
    ) -> str:
        """Create concrete index and return its unique physical index UUID."""
        ...

    def bulk_index_records(
        self, index_name: str, records: list[dict[str, Any]]
    ) -> BulkIndexResult:
        """Index a batch of documents into the candidate index."""
        ...

    def refresh_index(self, index_name: str) -> None:
        """Explicitly refresh index to make newly written documents visible."""
        ...

    def drain_and_seal_index(self, index_name: str) -> None:
        """Apply write-block and wait for in-flight requests to drain."""
        ...

    def read_all_record_summaries(self, index_name: str) -> list[RecordSummary]:
        """Perform match-all read of records for independent verification."""
        ...

    def search_records(
        self,
        index_name: str,
        *,
        query: str,
        document_kinds: tuple[str, ...] | None = None,
        entity_kinds: tuple[str, ...] | None = None,
        statuses: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        """Search records matching the lexical query and optional filters."""
        ...

    def delete_index(self, index_name: str) -> None:
        """Delete physical index."""
        ...

    def is_healthy(self) -> bool:
        """Check whether storage backend is responsive and available."""
        ...


class InMemorySearchBackend:
    """High-fidelity in-memory search backend for testing and simulation."""

    def __init__(self) -> None:
        self._indexes: dict[str, dict[str, Any]] = {}
        self._simulate_failure: str | None = None

    def simulate_failure(self, failure_kind: str | None) -> None:
        """Configure simulation of backend errors.

        Supported kinds: 'outage', 'bulk_error', 'seal_error'.
        """
        self._simulate_failure = failure_kind

    def create_index(
        self,
        index_name: str,
        settings: dict[str, Any],
        mappings: dict[str, Any],
    ) -> str:
        if self._simulate_failure == "outage":
            raise SearchBackendUnavailableError("Storage backend is unreachable")
        if index_name in self._indexes:
            raise SearchIntegrityError(f"Index {index_name} already exists")

        idx_uuid = f"uuid-{uuid4().hex[:12]}"
        self._indexes[index_name] = {
            "uuid": idx_uuid,
            "settings": dict(settings),
            "mappings": dict(mappings),
            "sealed": False,
            "records": {},
        }
        return idx_uuid

    def bulk_index_records(
        self, index_name: str, records: list[dict[str, Any]]
    ) -> BulkIndexResult:
        if self._simulate_failure == "outage":
            raise SearchBackendUnavailableError("Storage backend is unreachable")
        idx = self._indexes.get(index_name)
        if idx is None:
            raise SearchBackendUnavailableError(f"Index {index_name} not found")
        if idx["sealed"]:
            raise SearchIntegrityError(f"Index {index_name} is sealed; writes rejected")

        if self._simulate_failure == "bulk_error":
            errors = ({"error": "Simulated bulk item rejection", "status": 400},)
            return BulkIndexResult(
                total=len(records),
                successful=0,
                failed=len(records),
                errors=errors,
            )

        successful = 0
        for rec in records:
            storage_key = rec["storage_key"]
            idx["records"][storage_key] = dict(rec)
            successful += 1

        return BulkIndexResult(total=len(records), successful=successful, failed=0)

    def refresh_index(self, index_name: str) -> None:
        if self._simulate_failure == "outage":
            raise SearchBackendUnavailableError("Storage backend is unreachable")
        if index_name not in self._indexes:
            raise SearchBackendUnavailableError(f"Index {index_name} not found")

    def drain_and_seal_index(self, index_name: str) -> None:
        if self._simulate_failure == "outage":
            raise SearchBackendUnavailableError("Storage backend is unreachable")
        if self._simulate_failure == "seal_error":
            raise SearchBackendUnavailableError("Failed to seal candidate index")
        idx = self._indexes.get(index_name)
        if idx is None:
            raise SearchBackendUnavailableError(f"Index {index_name} not found")
        idx["sealed"] = True

    def read_all_record_summaries(self, index_name: str) -> list[RecordSummary]:
        if self._simulate_failure == "outage":
            raise SearchBackendUnavailableError("Storage backend is unreachable")
        idx = self._indexes.get(index_name)
        if idx is None:
            raise SearchBackendUnavailableError(f"Index {index_name} not found")

        summaries = [
            RecordSummary(
                storage_key=rec["storage_key"],
                knowledge_key=rec["knowledge_key"],
                document_kind=rec["document_kind"],
                record_semantic_digest=rec["record_semantic_digest"],
            )
            for rec in idx["records"].values()
        ]
        return sorted(summaries, key=lambda s: s.storage_key)

    def search_records(
        self,
        index_name: str,
        *,
        query: str,
        document_kinds: tuple[str, ...] | None = None,
        entity_kinds: tuple[str, ...] | None = None,
        statuses: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        if self._simulate_failure == "outage":
            raise SearchBackendUnavailableError("Storage backend is unreachable")
        idx = self._indexes.get(index_name)
        if idx is None:
            raise SearchBackendUnavailableError(f"Index {index_name} not found")

        q_norm = query.strip().lower()
        q_tokens = [t for t in q_norm.split() if t]

        matches: list[dict[str, Any]] = []
        for rec in idx["records"].values():
            if (
                document_kinds is not None
                and rec.get("document_kind") not in document_kinds
            ):
                continue
            if entity_kinds is not None and rec.get("kind") not in entity_kinds:
                continue
            if statuses is not None and rec.get("status") not in statuses:
                continue

            c_ref = rec.get("canonical_reference", "").lower()
            title = rec.get("title", "").lower()
            k_key = rec.get("knowledge_key", "").lower()
            kind_val = (rec.get("kind") or "").lower()

            text_fields = rec.get("text_fields", {})
            tf_values = " ".join(str(v).lower() for v in text_fields.values())

            # Tier 1: exact identifier match
            is_tier_1 = (
                q_norm == c_ref
                or q_norm == title
                or q_norm == k_key
                or (kind_val and q_norm == kind_val)
            )

            is_tier_2 = False
            score = 0.0
            if is_tier_1:
                rank_tier = 1
                score = 100.0
                if q_norm == c_ref:
                    score += 20.0
                if q_norm == title:
                    score += 10.0
            else:
                rank_tier = 2
                matched_tokens = 0
                if q_norm in c_ref:
                    is_tier_2 = True
                    score += 15.0
                if q_norm in title:
                    is_tier_2 = True
                    score += 10.0
                if q_norm in tf_values:
                    is_tier_2 = True
                    score += 5.0
                for token in q_tokens:
                    if token in c_ref or token in title or token in tf_values:
                        matched_tokens += 1
                        score += 2.0
                if q_tokens and matched_tokens == len(q_tokens):
                    is_tier_2 = True

            if is_tier_1 or is_tier_2:
                entry = dict(rec)
                entry["_rank_tier"] = rank_tier
                entry["_score"] = float(score)
                matches.append(entry)

        matches.sort(key=lambda m: (m["_rank_tier"], -m["_score"], m["knowledge_key"]))
        return matches

    def delete_index(self, index_name: str) -> None:
        self._indexes.pop(index_name, None)

    def is_healthy(self) -> bool:
        return self._simulate_failure != "outage"


__all__ = [
    "BulkIndexResult",
    "InMemorySearchBackend",
    "RecordSummary",
    "SEARCH_INDEX_MAPPINGS",
    "SEARCH_INDEX_SETTINGS",
    "SearchIndexBackend",
    "compute_mapping_hash",
    "compute_settings_hash",
]
