"""M1 lifecycle domain contract tests."""

from dataclasses import replace
from uuid import uuid4

import pytest

from backend.platform.graph.model import ProjectionCounts, VerificationReceipt


def test_projection_counts_reject_negative_values() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        ProjectionCounts(-1, 0, 0, 0, 0)


def test_verification_requires_counts_and_all_digests_to_match() -> None:
    counts = ProjectionCounts(2, 1, 3, 0, 0)
    receipt = VerificationReceipt(
        resource_id=uuid4(),
        attempt_id=uuid4(),
        generation_id=uuid4(),
        project_id=uuid4(),
        architecture_version_id=uuid4(),
        lease_owner="worker-1",
        lease_token="opaque-token",
        contract_version="1.0.0",
        source_content_digest="source",
        source_schema_version="1.0.0",
        graph_schema_version="1.0.0",
        projector_version="1.0.0",
        verified=True,
        expected_counts=counts,
        actual_counts=counts,
        expected_key_set_digest="keys",
        actual_key_set_digest="keys",
        expected_endpoint_digest="endpoints",
        actual_endpoint_digest="endpoints",
        expected_payload_digest="payload",
        actual_payload_digest="payload",
    )
    assert receipt.summaries_match()
    assert not replace(receipt, actual_payload_digest="different").summaries_match()
