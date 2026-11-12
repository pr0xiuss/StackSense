"""Unit tests for independent read-back verifier and complete corruption matrix."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from backend.platform.graph.model import (
    GRAPH_SCHEMA_VERSION,
    PROJECTION_CONTRACT_VERSION,
    PROJECTOR_VERSION,
    SOURCE_CONTRACT_VERSION,
    ProjectionCounts,
)
from backend.platform.graph.projection import (
    MANIFEST_STATE_BUILDING,
    MANIFEST_STATE_READY,
    ProjectionPlan,
    build_projection_plan,
)
from backend.platform.graph.projection_store import (
    ProjectionStoreUnavailableError,
    StaleFenceError,
    compute_fence_digest,
)
from backend.platform.graph.verification import (
    GRAPH_SCHEMA_INCOMPATIBLE,
    GRAPH_VERIFICATION_COUNT_MISMATCH,
    GRAPH_VERIFICATION_ENDPOINT_MISMATCH,
    GRAPH_VERIFICATION_KEY_MISMATCH,
    GRAPH_VERIFICATION_PAYLOAD_MISMATCH,
    GRAPH_VERIFICATION_SCOPE_MISMATCH,
    PROJECTION_CONTRACT_MISMATCH,
    PROJECTION_SOURCE_MISMATCH,
    GraphVerifier,
)
from tests.fixtures.p4.graph.fixtures import (
    DEFAULT_GENERATION_ID,
    small_document,
)


class FakeProjectionStore:
    """Configurable in-memory fake projection store for verification unit testing."""

    def __init__(self, plan: ProjectionPlan, lease_token: str = "valid-token") -> None:
        self.plan = plan
        self.lease_token = lease_token
        self.fence_digest: str | None = compute_fence_digest(lease_token)
        self.manifest_state = MANIFEST_STATE_BUILDING
        self.manifest_exists = True
        self.manifest_labels: list[str] = ["ProjectionManifest"]
        self.manifest_source_content_digest = plan.source_content_digest
        self.manifest_source_schema_version = SOURCE_CONTRACT_VERSION
        self.manifest_graph_schema_version = GRAPH_SCHEMA_VERSION
        self.manifest_projector_version = PROJECTOR_VERSION
        self.manifest_projection_contract_version = PROJECTION_CONTRACT_VERSION
        self.manifest_project_id = str(plan.project_id).lower()
        self.manifest_architecture_version_id = str(
            plan.architecture_version_id
        ).lower()
        self.manifest_generation_id = str(plan.generation_id).lower()

        # Expected summaries in manifest
        self.manifest_expected_entities_count = plan.expected_counts.entities
        self.manifest_expected_relationships_count = plan.expected_counts.relationships
        self.manifest_expected_evidence_count = plan.expected_counts.evidence
        self.manifest_expected_unresolved_count = plan.expected_counts.unresolved
        self.manifest_expected_conflicts_count = plan.expected_counts.conflicts
        self.manifest_expected_key_set_digest = plan.key_set_digest
        self.manifest_expected_endpoint_digest = plan.endpoint_digest
        self.manifest_expected_payload_digest = plan.payload_digest
        self.manifest_expected_evidence_summary_digest = plan.evidence_summary_digest
        self.manifest_expected_unresolved_summary_digest = (
            plan.unresolved_summary_digest
        )
        self.manifest_expected_conflict_summary_digest = plan.conflict_summary_digest
        self.manifest_actual_evidence_summary_digest: str | None = None
        self.manifest_actual_unresolved_summary_digest: str | None = None
        self.manifest_actual_conflict_summary_digest: str | None = None

        # Graph node and edge data (sorted copies from plan)
        self.nodes_data: list[dict[str, Any]] = [
            {
                "projection_key": n.projection_key,
                "properties": dict(n.properties),
                "labels": ["ArchitectureEntity"],
            }
            for n in plan.nodes
        ]
        self.relationships_data: list[dict[str, Any]] = [
            {
                "projection_key": r.projection_key,
                "source_key": r.source_projection_key,
                "target_key": r.target_projection_key,
                "rel_type": "ARCH_RELATIONSHIP",
                "properties": dict(r.properties),
            }
            for r in plan.relationships
        ]

        self.any_nodes_count_override: int | None = None
        self.any_rels_count_override: int | None = None
        self.fail_finalize_stale = False

    def get_manifest(self, generation_key: str) -> dict[str, Any] | None:
        if not self.manifest_exists:
            return None
        return {
            "generation_key": generation_key,
            "state": self.manifest_state,
            "fence_digest": self.fence_digest,
            "labels": list(self.manifest_labels),
            "project_id": self.manifest_project_id,
            "architecture_version_id": self.manifest_architecture_version_id,
            "generation_id": self.manifest_generation_id,
            "source_content_digest": self.manifest_source_content_digest,
            "source_schema_version": self.manifest_source_schema_version,
            "graph_schema_version": self.manifest_graph_schema_version,
            "projector_version": self.manifest_projector_version,
            "projection_contract_version": self.manifest_projection_contract_version,
            "expected_entities_count": self.manifest_expected_entities_count,
            "expected_relationships_count": self.manifest_expected_relationships_count,
            "expected_evidence_count": self.manifest_expected_evidence_count,
            "expected_unresolved_count": self.manifest_expected_unresolved_count,
            "expected_conflicts_count": self.manifest_expected_conflicts_count,
            "expected_key_set_digest": self.manifest_expected_key_set_digest,
            "expected_endpoint_digest": self.manifest_expected_endpoint_digest,
            "expected_payload_digest": self.manifest_expected_payload_digest,
            "expected_evidence_summary_digest": (
                self.manifest_expected_evidence_summary_digest
            ),
            "expected_unresolved_summary_digest": (
                self.manifest_expected_unresolved_summary_digest
            ),
            "expected_conflict_summary_digest": (
                self.manifest_expected_conflict_summary_digest
            ),
            "actual_evidence_summary_digest": (
                self.manifest_actual_evidence_summary_digest
            ),
            "actual_unresolved_summary_digest": (
                self.manifest_actual_unresolved_summary_digest
            ),
            "actual_conflict_summary_digest": (
                self.manifest_actual_conflict_summary_digest
            ),
        }

    def count_nodes(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
    ) -> tuple[int, int]:
        total = len(self.nodes_data)
        distinct = len({row["projection_key"] for row in self.nodes_data})
        return total, distinct

    def count_any_nodes_in_scope(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
    ) -> int:
        if self.any_nodes_count_override is not None:
            return self.any_nodes_count_override
        return len(self.nodes_data)

    def enumerate_nodes(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        cursor: str | None = None,
        page_size: int = 1000,
    ) -> list[dict[str, Any]]:
        sorted_nodes = sorted(self.nodes_data, key=lambda x: x["projection_key"])
        if cursor is not None:
            sorted_nodes = [x for x in sorted_nodes if x["projection_key"] > cursor]
        return sorted_nodes[:page_size]

    def count_relationships(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
    ) -> tuple[int, int]:
        total = len(self.relationships_data)
        distinct = len({row["projection_key"] for row in self.relationships_data})
        return total, distinct

    def count_any_relationships_in_scope(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
    ) -> int:
        if self.any_rels_count_override is not None:
            return self.any_rels_count_override
        return len(self.relationships_data)

    def enumerate_relationships(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        cursor: str | None = None,
        page_size: int = 1000,
    ) -> list[dict[str, Any]]:
        sorted_rels = sorted(self.relationships_data, key=lambda x: x["projection_key"])
        if cursor is not None:
            sorted_rels = [x for x in sorted_rels if x["projection_key"] > cursor]
        return sorted_rels[:page_size]

    def finalize_manifest(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        lease_token: str,
        actual_counts: ProjectionCounts,
        actual_key_set_digest: str,
        actual_endpoint_digest: str,
        actual_payload_digest: str,
        actual_evidence_summary_digest: str,
        actual_unresolved_summary_digest: str,
        actual_conflict_summary_digest: str,
    ) -> None:
        if self.fail_finalize_stale:
            raise StaleFenceError("Finalize fence mismatch")
        self.manifest_state = MANIFEST_STATE_READY
        self.fence_digest = None
        self.manifest_actual_evidence_summary_digest = actual_evidence_summary_digest
        self.manifest_actual_unresolved_summary_digest = (
            actual_unresolved_summary_digest
        )
        self.manifest_actual_conflict_summary_digest = actual_conflict_summary_digest

    # Dummy implementations for Protocol completeness
    def claim_candidate(self, **kwargs: Any) -> None:
        pass

    def reset_candidate(self, **kwargs: Any) -> int:
        return 0

    def write_nodes(self, **kwargs: Any) -> int:
        return len(self.nodes_data)

    def write_relationships(self, **kwargs: Any) -> int:
        return len(self.relationships_data)

    def delete_generation(self, **kwargs: Any) -> int:
        return 0


@pytest.fixture
def plan() -> ProjectionPlan:
    doc = small_document()
    return build_projection_plan(doc, generation_id=DEFAULT_GENERATION_ID)


def test_verification_succeeds_on_valid_candidate(plan: ProjectionPlan) -> None:
    store = FakeProjectionStore(plan, lease_token="valid-token")
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")

    assert result.verified is True
    assert result.failure_code is None
    assert result.failure_message is None
    assert result.actual_counts == plan.expected_counts
    assert result.actual_key_set_digest == plan.key_set_digest
    assert result.actual_endpoint_digest == plan.endpoint_digest
    assert result.actual_payload_digest == plan.payload_digest
    assert store.manifest_state == MANIFEST_STATE_READY
    assert store.fence_digest is None

    # Verify receipt translation
    receipt = result.to_receipt(
        resource_id=uuid4(),
        attempt_id=uuid4(),
        generation_id=plan.generation_id,
        project_id=plan.project_id,
        architecture_version_id=plan.architecture_version_id,
        lease_owner="worker-1",
        lease_token="valid-token",
        source_content_digest=plan.source_content_digest,
        source_schema_version=SOURCE_CONTRACT_VERSION,
    )
    assert receipt.verified is True
    assert receipt.summaries_match() is True


def test_verification_fails_if_manifest_missing(plan: ProjectionPlan) -> None:
    store = FakeProjectionStore(plan)
    store.manifest_exists = False
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == GRAPH_VERIFICATION_SCOPE_MISMATCH
    assert "not found" in str(result.failure_message)


def test_verification_fails_on_invalid_manifest_labels(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    store.manifest_labels = ["ProjectionManifest", "ExtraLabel"]
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == GRAPH_SCHEMA_INCOMPATIBLE
    assert "labels" in str(result.failure_message).lower()


def test_verification_fails_on_manifest_state_not_building(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    store.manifest_state = MANIFEST_STATE_READY
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == GRAPH_VERIFICATION_SCOPE_MISMATCH
    assert "BUILDING" in str(result.failure_message)


def test_verification_fails_on_manifest_fence_mismatch(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan, lease_token="token-A")
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="token-B")
    assert result.verified is False
    assert result.failure_code == GRAPH_VERIFICATION_SCOPE_MISMATCH
    assert "fence mismatch" in str(result.failure_message).lower()


@pytest.mark.parametrize(
    ("attr", "val"),
    [
        ("manifest_project_id", "00000000-0000-0000-0000-000000000000"),
        ("manifest_architecture_version_id", "00000000-0000-0000-0000-000000000000"),
        ("manifest_generation_id", "00000000-0000-0000-0000-000000000000"),
    ],
)
def test_verification_fails_on_manifest_scope_mismatch(
    plan: ProjectionPlan, attr: str, val: str
) -> None:
    store = FakeProjectionStore(plan)
    setattr(store, attr, val)
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == GRAPH_VERIFICATION_SCOPE_MISMATCH


def test_verification_fails_on_graph_schema_version_mismatch(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    store.manifest_graph_schema_version = "2.0.0"
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == GRAPH_SCHEMA_INCOMPATIBLE


def test_verification_fails_on_projector_version_mismatch(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    store.manifest_projector_version = "2.0.0"
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == PROJECTION_CONTRACT_MISMATCH


def test_verification_fails_on_source_content_digest_mismatch(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    store.manifest_source_content_digest = "corrupted-source-sha"
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == PROJECTION_SOURCE_MISMATCH


def test_verification_fails_on_manifest_expected_counts_mismatch(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    store.manifest_expected_entities_count += 1
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == PROJECTION_CONTRACT_MISMATCH


def test_verification_fails_on_duplicate_node_keys_in_graph(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    # Duplicate first node
    store.nodes_data.append(dict(store.nodes_data[0]))
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code in (
        GRAPH_VERIFICATION_KEY_MISMATCH,
        GRAPH_VERIFICATION_COUNT_MISMATCH,
    )


def test_verification_fails_on_node_count_mismatch(plan: ProjectionPlan) -> None:
    store = FakeProjectionStore(plan)
    store.nodes_data.pop()  # Drop one node
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == GRAPH_VERIFICATION_COUNT_MISMATCH


def test_verification_fails_on_unexpected_node_label(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    store.any_nodes_count_override = len(store.nodes_data) + 1  # Extra unlabelled node
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == GRAPH_SCHEMA_INCOMPATIBLE


def test_verification_fails_on_duplicate_canonical_logical_id(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    # Replace second node's logical_id with first node's logical_id
    duplicate_logical_id = store.nodes_data[0]["properties"]["logical_id"]
    props = dict(store.nodes_data[1]["properties"])
    props["logical_id"] = duplicate_logical_id
    store.nodes_data[1]["properties"] = props
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == GRAPH_VERIFICATION_KEY_MISMATCH


def test_verification_fails_on_missing_or_extra_node_keys(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    store.nodes_data[0] = dict(store.nodes_data[0])
    store.nodes_data[0]["projection_key"] = "tampered-node-key"
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == GRAPH_VERIFICATION_KEY_MISMATCH


def test_verification_fails_on_duplicate_relationship_keys_in_graph(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    store.relationships_data.append(dict(store.relationships_data[0]))
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code in (
        GRAPH_VERIFICATION_KEY_MISMATCH,
        GRAPH_VERIFICATION_COUNT_MISMATCH,
    )


def test_verification_fails_on_relationship_count_mismatch(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    store.relationships_data.pop()
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == GRAPH_VERIFICATION_COUNT_MISMATCH


def test_verification_fails_on_unexpected_relationship_type(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    store.relationships_data[0] = dict(store.relationships_data[0])
    store.relationships_data[0]["rel_type"] = "DEPENDS_ON"  # Rogue type
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == GRAPH_SCHEMA_INCOMPATIBLE


def test_verification_fails_on_endpoint_not_in_node_set(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    store.relationships_data[0] = dict(store.relationships_data[0])
    store.relationships_data[0]["target_key"] = "non-existent-target-key"
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == GRAPH_VERIFICATION_ENDPOINT_MISMATCH


def test_verification_fails_on_endpoint_direction_reversed(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    store.relationships_data[0] = dict(store.relationships_data[0])
    # Swap source and target
    src = store.relationships_data[0]["source_key"]
    tgt = store.relationships_data[0]["target_key"]
    store.relationships_data[0]["source_key"] = tgt
    store.relationships_data[0]["target_key"] = src
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == GRAPH_VERIFICATION_ENDPOINT_MISMATCH
    assert "direction" in str(result.failure_message).lower()


def test_verification_fails_on_canonical_kind_mismatch(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    store.relationships_data[0] = dict(store.relationships_data[0])
    props = dict(store.relationships_data[0]["properties"])
    props["canonical_kind"] = "CONTAINS"  # Tampered kind
    store.relationships_data[0]["properties"] = props
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == GRAPH_VERIFICATION_ENDPOINT_MISMATCH
    assert "canonical kind" in str(result.failure_message).lower()


def test_verification_fails_on_property_alteration_payload_digest_mismatch(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    store.nodes_data[0] = dict(store.nodes_data[0])
    props = dict(store.nodes_data[0]["properties"])
    props["name"] = "TamperedName"
    store.nodes_data[0]["properties"] = props
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    assert result.verified is False
    assert result.failure_code == GRAPH_VERIFICATION_PAYLOAD_MISMATCH
    assert "payload digest" in str(result.failure_message).lower()


def test_verification_fails_if_manifest_finalize_loses_fence(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)
    store.fail_finalize_stale = True
    verifier = GraphVerifier(store=store)

    with pytest.raises(StaleFenceError, match="fence mismatch"):
        verifier.verify_candidate(plan=plan, lease_token="valid-token")


def test_verification_propagates_transient_store_unavailability(
    plan: ProjectionPlan,
) -> None:
    store = FakeProjectionStore(plan)

    def unavailable(_: str) -> dict[str, Any] | None:
        raise ProjectionStoreUnavailableError("Neo4j unavailable")

    store.get_manifest = unavailable  # type: ignore[method-assign]
    verifier = GraphVerifier(store=store)

    with pytest.raises(ProjectionStoreUnavailableError, match="unavailable"):
        verifier.verify_candidate(plan=plan, lease_token="valid-token")


def test_failed_receipt_summaries_match_is_false(plan: ProjectionPlan) -> None:
    store = FakeProjectionStore(plan)
    store.manifest_exists = False
    verifier = GraphVerifier(store=store)

    result = verifier.verify_candidate(plan=plan, lease_token="valid-token")
    receipt = result.to_receipt(
        resource_id=uuid4(),
        attempt_id=uuid4(),
        generation_id=plan.generation_id,
        project_id=plan.project_id,
        architecture_version_id=plan.architecture_version_id,
        lease_owner="worker-1",
        lease_token="valid-token",
        source_content_digest=plan.source_content_digest,
        source_schema_version=SOURCE_CONTRACT_VERSION,
    )
    assert receipt.verified is False
    assert receipt.summaries_match() is False
    assert receipt.actual_counts is None
