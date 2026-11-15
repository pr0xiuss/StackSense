"""Independent read-back graph projection verifier and corruption taxonomy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from uuid import UUID

from backend.platform.graph.model import (
    GRAPH_SCHEMA_VERSION,
    PROJECTION_CONTRACT_VERSION,
    PROJECTOR_VERSION,
    SOURCE_CONTRACT_VERSION,
    ProjectionCounts,
    VerificationReceipt,
)
from backend.platform.graph.projection import (
    MANIFEST_STATE_BUILDING,
    MANIFEST_STATE_READY,
    ProjectedNodeRecord,
    ProjectedRelationshipRecord,
    ProjectionPlan,
    compute_endpoint_digest,
    compute_key_set_digest,
    compute_payload_digest,
)
from backend.platform.graph.projection_store import (
    ProjectionStore,
    ProjectionStoreError,
    ProjectionStoreUnavailableError,
    StaleFenceError,
    compute_fence_digest,
)

# Standard safe failure codes
PROJECTION_SOURCE_MISSING: Final = "projection_source_missing"
PROJECTION_SOURCE_MISMATCH: Final = "projection_source_mismatch"
PROJECTION_CONTRACT_MISMATCH: Final = "projection_contract_mismatch"
PROJECTION_CAPACITY_EXCEEDED: Final = "projection_capacity_exceeded"
PROJECTION_METADATA_INVALID: Final = "projection_metadata_invalid"
GRAPH_SCHEMA_INCOMPATIBLE: Final = "graph_schema_incompatible"
GRAPH_WRITE_UNAVAILABLE: Final = "graph_write_unavailable"
GRAPH_WRITE_INCOMPLETE: Final = "graph_write_incomplete"
GRAPH_VERIFICATION_SCOPE_MISMATCH: Final = "graph_verification_scope_mismatch"
GRAPH_VERIFICATION_COUNT_MISMATCH: Final = "graph_verification_count_mismatch"
GRAPH_VERIFICATION_KEY_MISMATCH: Final = "graph_verification_key_mismatch"
GRAPH_VERIFICATION_ENDPOINT_MISMATCH: Final = "graph_verification_endpoint_mismatch"
GRAPH_VERIFICATION_PAYLOAD_MISMATCH: Final = "graph_verification_payload_mismatch"
GRAPH_INTERNAL_ERROR: Final = "graph_internal_error"


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Internal M2 verification result before translation to VerificationReceipt."""

    verified: bool
    generation_key: str
    expected_counts: ProjectionCounts
    actual_counts: ProjectionCounts | None
    expected_key_set_digest: str | None
    actual_key_set_digest: str | None
    expected_endpoint_digest: str | None
    actual_endpoint_digest: str | None
    expected_payload_digest: str | None
    actual_payload_digest: str | None
    failure_code: str | None = None
    failure_message: str | None = None

    def to_receipt(
        self,
        *,
        resource_id: UUID,
        attempt_id: UUID,
        generation_id: UUID,
        project_id: UUID,
        architecture_version_id: UUID,
        lease_owner: str,
        lease_token: str,
        contract_version: str = PROJECTION_CONTRACT_VERSION,
        source_content_digest: str,
        source_schema_version: str = SOURCE_CONTRACT_VERSION,
        graph_schema_version: str = GRAPH_SCHEMA_VERSION,
        projector_version: str = PROJECTOR_VERSION,
    ) -> VerificationReceipt:
        """Translate this result to the frozen M1 VerificationReceipt envelope."""
        return VerificationReceipt(
            resource_id=resource_id,
            attempt_id=attempt_id,
            generation_id=generation_id,
            project_id=project_id,
            architecture_version_id=architecture_version_id,
            lease_owner=lease_owner,
            lease_token=lease_token,
            contract_version=contract_version,
            source_content_digest=source_content_digest,
            source_schema_version=source_schema_version,
            graph_schema_version=graph_schema_version,
            projector_version=projector_version,
            verified=self.verified,
            expected_counts=self.expected_counts,
            actual_counts=self.actual_counts,
            expected_key_set_digest=self.expected_key_set_digest,
            actual_key_set_digest=self.actual_key_set_digest,
            expected_endpoint_digest=self.expected_endpoint_digest,
            actual_endpoint_digest=self.actual_endpoint_digest,
            expected_payload_digest=self.expected_payload_digest,
            actual_payload_digest=self.actual_payload_digest,
            failure_code=self.failure_code,
            failure_message=self.failure_message,
        )


class GraphVerifier:
    """Performs independent read-back verification of candidate projection data."""

    def __init__(self, store: ProjectionStore) -> None:
        self._store = store

    def verify_candidate(
        self,
        *,
        plan: ProjectionPlan,
        lease_token: str,
        resource_id: UUID | None = None,
        attempt_id: UUID | None = None,
        projection_contract_version: str = PROJECTION_CONTRACT_VERSION,
        source_content_digest: str | None = None,
        source_schema_version: str = SOURCE_CONTRACT_VERSION,
        graph_schema_version: str = GRAPH_SCHEMA_VERSION,
        projector_version: str = PROJECTOR_VERSION,
    ) -> VerificationResult:
        """Independently query and prove the completeness of a candidate generation."""
        expected_src_digest = (
            source_content_digest
            if source_content_digest is not None
            else plan.source_content_digest
        )

        # 1. Inspect ProjectionManifest
        try:
            manifest = self._store.get_manifest(plan.generation_key)
        except ProjectionStoreUnavailableError:
            raise
        except ProjectionStoreError as err:
            return self._fail(
                plan,
                code=GRAPH_WRITE_UNAVAILABLE,
                message=f"Failed to query ProjectionManifest: {err}",
            )

        if manifest is None:
            return self._fail(
                plan,
                code=GRAPH_VERIFICATION_SCOPE_MISMATCH,
                message="ProjectionManifest not found in graph",
            )

        # Validate manifest label
        labels = manifest.get("labels")
        if not isinstance(labels, list) or labels != ["ProjectionManifest"]:
            return self._fail(
                plan,
                code=GRAPH_SCHEMA_INCOMPATIBLE,
                message=f"Invalid ProjectionManifest labels: {labels}",
            )

        # Validate state
        state = manifest.get("state")
        if state != MANIFEST_STATE_BUILDING:
            return self._fail(
                plan,
                code=GRAPH_VERIFICATION_SCOPE_MISMATCH,
                message=f"ProjectionManifest state is '{state}', expected BUILDING",
            )

        # Validate fence
        expected_fence = compute_fence_digest(lease_token)
        actual_fence = manifest.get("fence_digest")
        if actual_fence != expected_fence:
            return self._fail(
                plan,
                code=GRAPH_VERIFICATION_SCOPE_MISMATCH,
                message="ProjectionManifest fence mismatch (stale worker)",
            )

        # Validate manifest scope
        p_id = str(plan.project_id).lower()
        a_id = str(plan.architecture_version_id).lower()
        g_id = str(plan.generation_id).lower()

        if (
            str(manifest.get("project_id")).lower() != p_id
            or str(manifest.get("architecture_version_id")).lower() != a_id
            or str(manifest.get("generation_id")).lower() != g_id
        ):
            return self._fail(
                plan,
                code=GRAPH_VERIFICATION_SCOPE_MISMATCH,
                message="ProjectionManifest scope fields mismatch",
            )

        if (
            resource_id is not None
            and manifest.get("resource_id") != str(resource_id).lower()
        ):
            return self._fail(
                plan,
                code=PROJECTION_CONTRACT_MISMATCH,
                message="Manifest resource_id mismatch",
            )
        if (
            attempt_id is not None
            and manifest.get("attempt_id") != str(attempt_id).lower()
        ):
            return self._fail(
                plan,
                code=PROJECTION_CONTRACT_MISMATCH,
                message="Manifest attempt_id mismatch",
            )
        if manifest.get("projection_contract_version") != projection_contract_version:
            return self._fail(
                plan,
                code=PROJECTION_CONTRACT_MISMATCH,
                message="Manifest projection_contract_version mismatch",
            )

        # Validate versions and source digest
        if manifest.get("source_schema_version") != source_schema_version:
            return self._fail(
                plan,
                code=PROJECTION_CONTRACT_MISMATCH,
                message="Manifest source_schema_version mismatch",
            )
        if manifest.get("graph_schema_version") != graph_schema_version:
            return self._fail(
                plan,
                code=GRAPH_SCHEMA_INCOMPATIBLE,
                message="Manifest graph_schema_version mismatch",
            )
        if manifest.get("projector_version") != projector_version:
            return self._fail(
                plan,
                code=PROJECTION_CONTRACT_MISMATCH,
                message="Manifest projector_version mismatch",
            )
        if (
            expected_src_digest
            and manifest.get("source_content_digest") != expected_src_digest
        ):
            return self._fail(
                plan,
                code=PROJECTION_SOURCE_MISMATCH,
                message="Manifest source_content_digest mismatch",
            )

        if (
            manifest.get("expected_evidence_summary_digest")
            != plan.evidence_summary_digest
            or manifest.get("expected_unresolved_summary_digest")
            != plan.unresolved_summary_digest
            or manifest.get("expected_conflict_summary_digest")
            != plan.conflict_summary_digest
        ):
            return self._fail(
                plan,
                code=PROJECTION_CONTRACT_MISMATCH,
                message="Manifest expected summary digests mismatch source plan",
            )

        # Validate expected counts in manifest
        if (
            manifest.get("expected_entities_count") != plan.expected_counts.entities
            or manifest.get("expected_relationships_count")
            != plan.expected_counts.relationships
            or manifest.get("expected_evidence_count") != plan.expected_counts.evidence
            or manifest.get("expected_unresolved_count")
            != plan.expected_counts.unresolved
            or manifest.get("expected_conflicts_count")
            != plan.expected_counts.conflicts
        ):
            return self._fail(
                plan,
                code=PROJECTION_CONTRACT_MISMATCH,
                message="Manifest expected counts mismatch source plan",
            )

        # Validate expected digests in manifest
        if (
            manifest.get("expected_key_set_digest") != plan.key_set_digest
            or manifest.get("expected_endpoint_digest") != plan.endpoint_digest
            or manifest.get("expected_payload_digest") != plan.payload_digest
        ):
            return self._fail(
                plan,
                code=PROJECTION_CONTRACT_MISMATCH,
                message="Manifest expected digests mismatch source plan",
            )

        # 2. Node Verification
        try:
            total_nodes, distinct_nodes = self._store.count_nodes(
                project_id=plan.project_id,
                architecture_version_id=plan.architecture_version_id,
                generation_id=plan.generation_id,
            )
            any_nodes = self._store.count_any_nodes_in_scope(
                project_id=plan.project_id,
                architecture_version_id=plan.architecture_version_id,
                generation_id=plan.generation_id,
            )
        except ProjectionStoreUnavailableError:
            raise
        except ProjectionStoreError as err:
            return self._fail(
                plan,
                code=GRAPH_WRITE_UNAVAILABLE,
                message=f"Failed to query node counts: {err}",
            )

        if total_nodes != distinct_nodes:
            return self._fail(
                plan,
                code=GRAPH_VERIFICATION_KEY_MISMATCH,
                message="Duplicate node projection keys detected in Neo4j",
            )
        if total_nodes != plan.expected_counts.entities:
            return self._fail(
                plan,
                code=GRAPH_VERIFICATION_COUNT_MISMATCH,
                message=(
                    f"Node count mismatch: expected {plan.expected_counts.entities}, "
                    f"found {total_nodes}"
                ),
            )
        if any_nodes != total_nodes:
            return self._fail(
                plan,
                code=GRAPH_SCHEMA_INCOMPATIBLE,
                message=(
                    f"Found {any_nodes} total nodes in scope but {total_nodes} "
                    "with ArchitectureEntity label"
                ),
            )

        actual_nodes: list[ProjectedNodeRecord] = []
        actual_node_keys: list[str] = []
        seen_logical_ids: set[str] = set()
        node_cursor: str | None = None

        while True:
            try:
                page = self._store.enumerate_nodes(
                    project_id=plan.project_id,
                    architecture_version_id=plan.architecture_version_id,
                    generation_id=plan.generation_id,
                    cursor=node_cursor,
                    page_size=1000,
                )
            except ProjectionStoreUnavailableError:
                raise
            except ProjectionStoreError as err:
                return self._fail(
                    plan,
                    code=GRAPH_WRITE_UNAVAILABLE,
                    message=f"Failed to enumerate nodes: {err}",
                )

            if not page:
                break

            for row in page:
                key = str(row["projection_key"])
                props = dict(row["properties"])
                node_labels = row.get("labels")

                if node_labels != ["ArchitectureEntity"]:
                    return self._fail(
                        plan,
                        code=GRAPH_SCHEMA_INCOMPATIBLE,
                        message=f"Node '{key}' has invalid labels: {node_labels}",
                    )

                if (
                    str(props.get("project_id")).lower() != p_id
                    or str(props.get("architecture_version_id")).lower() != a_id
                    or str(props.get("generation_id")).lower() != g_id
                    or props.get("generation_key") != plan.generation_key
                ):
                    return self._fail(
                        plan,
                        code=GRAPH_VERIFICATION_SCOPE_MISMATCH,
                        message=f"Node '{key}' scope properties mismatch",
                    )

                log_id = str(props.get("logical_id"))
                if log_id in seen_logical_ids:
                    return self._fail(
                        plan,
                        code=GRAPH_VERIFICATION_KEY_MISMATCH,
                        message=f"Duplicate entity logical_id '{log_id}'",
                    )
                seen_logical_ids.add(log_id)

                node_rec = ProjectedNodeRecord(
                    project_id=UUID(str(props["project_id"])),
                    architecture_version_id=UUID(str(props["architecture_version_id"])),
                    generation_id=UUID(str(props["generation_id"])),
                    generation_key=str(props["generation_key"]),
                    projection_key=key,
                    architecture_entity_id=UUID(str(props["architecture_entity_id"])),
                    logical_id=log_id,
                    semantic_signature=str(props["semantic_signature"]),
                    canonical_kind=str(props["canonical_kind"]),
                    name=str(props["name"]),
                    namespace=tuple(props.get("namespace", ())),
                    fact_status=str(props["fact_status"]),
                    evidence_logical_ids=tuple(props.get("evidence_logical_ids", ())),
                    properties=props,
                )
                actual_nodes.append(node_rec)
                actual_node_keys.append(key)

            node_cursor = actual_node_keys[-1]

        expected_node_keys = [n.projection_key for n in plan.nodes]
        if actual_node_keys != expected_node_keys:
            return self._fail(
                plan,
                code=GRAPH_VERIFICATION_KEY_MISMATCH,
                message="Actual node keys do not match expected canonical node keys",
            )

        # 3. Relationship Verification
        try:
            total_rels, distinct_rels = self._store.count_relationships(
                project_id=plan.project_id,
                architecture_version_id=plan.architecture_version_id,
                generation_id=plan.generation_id,
            )
            any_rels = self._store.count_any_relationships_in_scope(
                project_id=plan.project_id,
                architecture_version_id=plan.architecture_version_id,
                generation_id=plan.generation_id,
            )
        except ProjectionStoreUnavailableError:
            raise
        except ProjectionStoreError as err:
            return self._fail(
                plan,
                code=GRAPH_WRITE_UNAVAILABLE,
                message=f"Failed to query relationship counts: {err}",
            )

        if total_rels != distinct_rels:
            return self._fail(
                plan,
                code=GRAPH_VERIFICATION_KEY_MISMATCH,
                message="Duplicate relationship projection keys detected in Neo4j",
            )
        if total_rels != plan.expected_counts.relationships:
            return self._fail(
                plan,
                code=GRAPH_VERIFICATION_COUNT_MISMATCH,
                message=(
                    f"Relationship count mismatch: expected "
                    f"{plan.expected_counts.relationships}, found {total_rels}"
                ),
            )
        if any_rels != total_rels:
            return self._fail(
                plan,
                code=GRAPH_SCHEMA_INCOMPATIBLE,
                message=(
                    f"Found {any_rels} total relationships in scope but "
                    f"{total_rels} of type ARCH_RELATIONSHIP"
                ),
            )

        actual_relationships: list[ProjectedRelationshipRecord] = []
        actual_rel_keys: list[str] = []
        node_key_set = set(actual_node_keys)
        expected_rels_by_key = {r.projection_key: r for r in plan.relationships}
        rel_cursor: str | None = None

        while True:
            try:
                page = self._store.enumerate_relationships(
                    project_id=plan.project_id,
                    architecture_version_id=plan.architecture_version_id,
                    generation_id=plan.generation_id,
                    cursor=rel_cursor,
                    page_size=1000,
                )
            except ProjectionStoreUnavailableError:
                raise
            except ProjectionStoreError as err:
                return self._fail(
                    plan,
                    code=GRAPH_WRITE_UNAVAILABLE,
                    message=f"Failed to enumerate relationships: {err}",
                )

            if not page:
                break

            for row in page:
                key = str(row["projection_key"])
                src_key = str(row["source_key"])
                tgt_key = str(row["target_key"])
                rel_type = str(row.get("rel_type"))
                props = dict(row["properties"])

                if rel_type != "ARCH_RELATIONSHIP":
                    return self._fail(
                        plan,
                        code=GRAPH_SCHEMA_INCOMPATIBLE,
                        message=(f"Relationship '{key}' has invalid type '{rel_type}'"),
                    )

                if (
                    str(props.get("project_id")).lower() != p_id
                    or str(props.get("architecture_version_id")).lower() != a_id
                    or str(props.get("generation_id")).lower() != g_id
                    or props.get("generation_key") != plan.generation_key
                ):
                    return self._fail(
                        plan,
                        code=GRAPH_VERIFICATION_SCOPE_MISMATCH,
                        message=f"Relationship '{key}' scope properties mismatch",
                    )

                if src_key not in node_key_set:
                    return self._fail(
                        plan,
                        code=GRAPH_VERIFICATION_ENDPOINT_MISMATCH,
                        message=(
                            f"Relationship '{key}' source key '{src_key}' not in "
                            "verified node set"
                        ),
                    )
                if tgt_key not in node_key_set:
                    return self._fail(
                        plan,
                        code=GRAPH_VERIFICATION_ENDPOINT_MISMATCH,
                        message=(
                            f"Relationship '{key}' target key '{tgt_key}' not in "
                            "verified node set"
                        ),
                    )

                expected_rel = expected_rels_by_key.get(key)
                if expected_rel is None:
                    return self._fail(
                        plan,
                        code=GRAPH_VERIFICATION_KEY_MISMATCH,
                        message=f"Unexpected relationship key '{key}'",
                    )

                if (
                    src_key != expected_rel.source_projection_key
                    or tgt_key != expected_rel.target_projection_key
                ):
                    return self._fail(
                        plan,
                        code=GRAPH_VERIFICATION_ENDPOINT_MISMATCH,
                        message=f"Relationship '{key}' endpoint direction mismatch",
                    )

                if str(props.get("canonical_kind")) != expected_rel.canonical_kind:
                    return self._fail(
                        plan,
                        code=GRAPH_VERIFICATION_ENDPOINT_MISMATCH,
                        message=f"Relationship '{key}' canonical kind mismatch",
                    )

                rel_rec = ProjectedRelationshipRecord(
                    project_id=UUID(str(props["project_id"])),
                    architecture_version_id=UUID(str(props["architecture_version_id"])),
                    generation_id=UUID(str(props["generation_id"])),
                    generation_key=str(props["generation_key"]),
                    projection_key=key,
                    architecture_relationship_id=UUID(
                        str(props["architecture_relationship_id"])
                    ),
                    logical_id=str(props["logical_id"]),
                    canonical_kind=str(props["canonical_kind"]),
                    status=str(props["status"]),
                    source_logical_id=str(props["source_logical_id"]),
                    target_logical_id=str(props["target_logical_id"]),
                    source_projection_key=src_key,
                    target_projection_key=tgt_key,
                    evidence_logical_ids=tuple(props.get("evidence_logical_ids", ())),
                    properties=props,
                )
                actual_relationships.append(rel_rec)
                actual_rel_keys.append(key)

            rel_cursor = actual_rel_keys[-1]

        expected_rel_keys = [r.projection_key for r in plan.relationships]
        if actual_rel_keys != expected_rel_keys:
            return self._fail(
                plan,
                code=GRAPH_VERIFICATION_KEY_MISMATCH,
                message=(
                    "Actual relationship keys do not match expected canonical "
                    "relationship keys"
                ),
            )

        # 4. Digest Recomputations from independent read-back data
        actual_key_set_digest = compute_key_set_digest(
            actual_node_keys, actual_rel_keys
        )
        if actual_key_set_digest != plan.key_set_digest:
            return self._fail(
                plan,
                code=GRAPH_VERIFICATION_PAYLOAD_MISMATCH,
                message="Recomputed key-set digest does not match expected digest",
                actual_counts=plan.expected_counts,
                actual_key_set_digest=actual_key_set_digest,
            )

        actual_endpoint_digest = compute_endpoint_digest(actual_relationships)
        if actual_endpoint_digest != plan.endpoint_digest:
            return self._fail(
                plan,
                code=GRAPH_VERIFICATION_PAYLOAD_MISMATCH,
                message="Recomputed endpoint digest does not match expected digest",
                actual_counts=plan.expected_counts,
                actual_key_set_digest=actual_key_set_digest,
                actual_endpoint_digest=actual_endpoint_digest,
            )

        actual_payload_digest = compute_payload_digest(
            project_id=plan.project_id,
            architecture_version_id=plan.architecture_version_id,
            generation_id=plan.generation_id,
            generation_key=plan.generation_key,
            counts=plan.expected_counts,
            nodes=actual_nodes,
            relationships=actual_relationships,
            evidence_summary_digest=plan.evidence_summary_digest,
            unresolved_summary_digest=plan.unresolved_summary_digest,
            conflict_summary_digest=plan.conflict_summary_digest,
        )
        if actual_payload_digest != plan.payload_digest:
            return self._fail(
                plan,
                code=GRAPH_VERIFICATION_PAYLOAD_MISMATCH,
                message="Recomputed payload digest does not match expected digest",
                actual_counts=plan.expected_counts,
                actual_key_set_digest=actual_key_set_digest,
                actual_endpoint_digest=actual_endpoint_digest,
                actual_payload_digest=actual_payload_digest,
            )

        # 5. Conditionally Finalize ProjectionManifest from BUILDING to READY
        try:
            self._store.finalize_manifest(
                project_id=plan.project_id,
                architecture_version_id=plan.architecture_version_id,
                generation_id=plan.generation_id,
                lease_token=lease_token,
                actual_counts=plan.expected_counts,
                actual_key_set_digest=actual_key_set_digest,
                actual_endpoint_digest=actual_endpoint_digest,
                actual_payload_digest=actual_payload_digest,
                actual_evidence_summary_digest=plan.evidence_summary_digest,
                actual_unresolved_summary_digest=plan.unresolved_summary_digest,
                actual_conflict_summary_digest=plan.conflict_summary_digest,
            )
        except StaleFenceError:
            raise
        except ProjectionStoreUnavailableError:
            raise
        except ProjectionStoreError as err:
            return self._fail(
                plan,
                code=GRAPH_WRITE_UNAVAILABLE,
                message=f"Manifest finalization failed: {err}",
            )

        finalized_manifest = self._store.get_manifest(plan.generation_key)
        if (
            finalized_manifest is None
            or finalized_manifest.get("state") != MANIFEST_STATE_READY
        ):
            return self._fail(
                plan,
                code=GRAPH_VERIFICATION_SCOPE_MISMATCH,
                message="Finalized ProjectionManifest is not READY",
            )
        if (
            finalized_manifest.get("actual_evidence_summary_digest")
            != plan.evidence_summary_digest
            or finalized_manifest.get("actual_unresolved_summary_digest")
            != plan.unresolved_summary_digest
            or finalized_manifest.get("actual_conflict_summary_digest")
            != plan.conflict_summary_digest
        ):
            return self._fail(
                plan,
                code=GRAPH_VERIFICATION_PAYLOAD_MISMATCH,
                message="Finalized ProjectionManifest summary digests mismatch",
            )

        # All checks passed successfully!
        return VerificationResult(
            verified=True,
            generation_key=plan.generation_key,
            expected_counts=plan.expected_counts,
            actual_counts=plan.expected_counts,
            expected_key_set_digest=plan.key_set_digest,
            actual_key_set_digest=actual_key_set_digest,
            expected_endpoint_digest=plan.endpoint_digest,
            actual_endpoint_digest=actual_endpoint_digest,
            expected_payload_digest=plan.payload_digest,
            actual_payload_digest=actual_payload_digest,
            failure_code=None,
            failure_message=None,
        )

    def _fail(
        self,
        plan: ProjectionPlan,
        *,
        code: str,
        message: str,
        actual_counts: ProjectionCounts | None = None,
        actual_key_set_digest: str | None = None,
        actual_endpoint_digest: str | None = None,
        actual_payload_digest: str | None = None,
    ) -> VerificationResult:
        """Construct a failed VerificationResult with sanitized details."""
        return VerificationResult(
            verified=False,
            generation_key=plan.generation_key,
            expected_counts=plan.expected_counts,
            actual_counts=actual_counts,
            expected_key_set_digest=plan.key_set_digest,
            actual_key_set_digest=actual_key_set_digest,
            expected_endpoint_digest=plan.endpoint_digest,
            actual_endpoint_digest=actual_endpoint_digest,
            expected_payload_digest=plan.payload_digest,
            actual_payload_digest=actual_payload_digest,
            failure_code=code,
            failure_message=message,
        )
