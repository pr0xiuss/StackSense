"""Tests for Elasticsearch index operations, mappings, hashes, and sealing."""

from __future__ import annotations

import pytest

from backend.platform.knowledge.contracts import (
    SearchBackendUnavailableError,
    SearchIntegrityError,
)
from backend.platform.knowledge.elasticsearch import (
    SEARCH_INDEX_MAPPINGS,
    SEARCH_INDEX_SETTINGS,
    InMemorySearchBackend,
    compute_mapping_hash,
    compute_settings_hash,
)


def test_mapping_and_settings_hashes_determinism():
    h_map1 = compute_mapping_hash(SEARCH_INDEX_MAPPINGS)
    h_map2 = compute_mapping_hash(SEARCH_INDEX_MAPPINGS)
    assert h_map1 == h_map2
    assert len(h_map1) == 64

    h_set1 = compute_settings_hash(SEARCH_INDEX_SETTINGS)
    h_set2 = compute_settings_hash(SEARCH_INDEX_SETTINGS)
    assert h_set1 == h_set2
    assert len(h_set1) == 64


def test_in_memory_backend_index_lifecycle():
    backend = InMemorySearchBackend()
    idx_name = "stacksense-search-test-1"

    # 1. Create index
    uuid1 = backend.create_index(
        index_name=idx_name,
        settings=SEARCH_INDEX_SETTINGS,
        mappings=SEARCH_INDEX_MAPPINGS,
    )
    assert uuid1.startswith("uuid-")

    # Duplicate creation rejected
    with pytest.raises(SearchIntegrityError, match="already exists"):
        backend.create_index(
            index_name=idx_name,
            settings=SEARCH_INDEX_SETTINGS,
            mappings=SEARCH_INDEX_MAPPINGS,
        )

    # 2. Bulk index
    records = [
        {
            "storage_key": "s1",
            "knowledge_key": "k1",
            "document_kind": "entity",
            "record_semantic_digest": "d1",
        },
        {
            "storage_key": "s2",
            "knowledge_key": "k2",
            "document_kind": "relationship",
            "record_semantic_digest": "d2",
        },
    ]
    res = backend.bulk_index_records(idx_name, records)
    assert res.total == 2
    assert res.successful == 2
    assert res.failed == 0

    # 3. Refresh and seal
    backend.refresh_index(idx_name)
    backend.drain_and_seal_index(idx_name)

    # 4. Writes after seal rejected (fail-closed!)
    with pytest.raises(SearchIntegrityError, match="sealed; writes rejected"):
        backend.bulk_index_records(
            idx_name,
            [
                {
                    "storage_key": "s3",
                    "knowledge_key": "k3",
                    "document_kind": "entity",
                    "record_semantic_digest": "d3",
                }
            ],
        )

    # 5. Read back summaries
    summaries = backend.read_all_record_summaries(idx_name)
    assert len(summaries) == 2
    assert summaries[0].storage_key == "s1"
    assert summaries[0].knowledge_key == "k1"
    assert summaries[1].storage_key == "s2"

    # 6. Delete index
    backend.delete_index(idx_name)
    with pytest.raises(SearchBackendUnavailableError, match="not found"):
        backend.read_all_record_summaries(idx_name)


def test_in_memory_backend_simulated_failures():
    backend = InMemorySearchBackend()
    idx_name = "stacksense-search-test-fail"
    backend.create_index(
        index_name=idx_name,
        settings=SEARCH_INDEX_SETTINGS,
        mappings=SEARCH_INDEX_MAPPINGS,
    )

    # Bulk error simulation
    backend.simulate_failure("bulk_error")
    res = backend.bulk_index_records(
        idx_name,
        [
            {
                "storage_key": "s1",
                "knowledge_key": "k1",
                "document_kind": "entity",
                "record_semantic_digest": "d1",
            }
        ],
    )
    assert res.failed == 1
    assert len(res.errors) == 1

    # Seal error simulation
    backend.simulate_failure("seal_error")
    with pytest.raises(SearchBackendUnavailableError, match="Failed to seal"):
        backend.drain_and_seal_index(idx_name)

    # Outage simulation
    backend.simulate_failure("outage")
    assert backend.is_healthy() is False
    with pytest.raises(SearchBackendUnavailableError, match="unreachable"):
        backend.refresh_index(idx_name)
