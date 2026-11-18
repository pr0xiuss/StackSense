"""Unit tests for P5-C3 retrieval configuration and policy validation.

Adheres to §7A.9 and §7A.11 of PROJECT_CONTEXT.md.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.platform.knowledge.retrieval_configuration import (
    RetrievalPolicy,
    parse_retrieval_policy,
)
from backend.platform.knowledge.retrieval_contracts import (
    RetrievalUnavailableError,
)


def test_default_retrieval_policy_is_valid():
    policy = RetrievalPolicy()
    assert policy.policy_version == "1.0.0"
    assert policy.canonical_page_size == 100
    assert policy.max_graph_depth == 5
    assert policy.max_graph_nodes == 500
    assert policy.total_deadline_seconds > policy.finalization_reserve_seconds
    fp = policy.compute_fingerprint()
    assert len(fp) == 64


def test_invalid_policy_relationships_rejected():
    # Reserve >= deadline rejected
    with pytest.raises(ValidationError):
        RetrievalPolicy(
            total_deadline_seconds=5.0,
            finalization_reserve_seconds=5.0,
        )

    with pytest.raises(ValidationError):
        RetrievalPolicy(
            total_deadline_seconds=2.0,
            finalization_reserve_seconds=3.0,
        )

    # Exceeding hard bounds rejected
    with pytest.raises(ValidationError):
        RetrievalPolicy(max_graph_depth=10)  # ceiling is 5

    with pytest.raises(ValidationError):
        RetrievalPolicy(canonical_page_size=200)  # ceiling is 100


def test_parse_retrieval_policy_safe_disablement_on_invalid_or_missing():
    with pytest.raises(RetrievalUnavailableError) as exc_info:
        parse_retrieval_policy("invalid json")
    assert exc_info.value.code == "retrieval_unavailable"

    with pytest.raises(RetrievalUnavailableError) as exc_info2:
        parse_retrieval_policy('{"policy_version": "99.0.0"}')
    assert exc_info2.value.code == "retrieval_unavailable"


def test_retrieval_policy_fingerprint_deterministic():
    p1 = RetrievalPolicy(max_selected_facts=50)
    p2 = RetrievalPolicy(max_selected_facts=50)
    p3 = RetrievalPolicy(max_selected_facts=100)

    assert p1.compute_fingerprint() == p2.compute_fingerprint()
    assert p1.compute_fingerprint() != p3.compute_fingerprint()
