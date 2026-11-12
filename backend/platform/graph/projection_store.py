"""Neo4j projection store adapter for bounded writes, fencing, and enumeration."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Final, LiteralString, Protocol
from uuid import UUID

from neo4j import Driver, ManagedTransaction, Query, Transaction
from neo4j.exceptions import DriverError, Neo4jError

from backend.platform.config import Settings
from backend.platform.graph.model import (
    GRAPH_SCHEMA_VERSION,
    PROJECTOR_VERSION,
    SOURCE_CONTRACT_VERSION,
    ProjectionCounts,
)
from backend.platform.graph.projection import (
    MANIFEST_STATE_BUILDING,
    MANIFEST_STATE_READY,
    ProjectedNodeRecord,
    ProjectedRelationshipRecord,
    ProjectionError,
    compute_generation_key,
)

# Fixed Cypher statements for manifest claim and locking
_CLAIM_MANIFEST_QUERY: Final[LiteralString] = (
    "MERGE (m:ProjectionManifest {generation_key: $generation_key}) "
    "ON CREATE SET "
    "    m.lock_epoch = 1, "
    "    m.state = $state_building, "
    "    m.fence_digest = $fence_digest, "
    "    m.project_id = $project_id, "
    "    m.architecture_version_id = $architecture_version_id, "
    "    m.generation_id = $generation_id, "
    "    m.source_content_digest = $source_content_digest, "
    "    m.source_schema_version = $source_schema_version, "
    "    m.graph_schema_version = $graph_schema_version, "
    "    m.projector_version = $projector_version, "
    "    m.expected_entities_count = $expected_entities_count, "
    "    m.expected_relationships_count = $expected_relationships_count, "
    "    m.expected_evidence_count = $expected_evidence_count, "
    "    m.expected_unresolved_count = $expected_unresolved_count, "
    "    m.expected_conflicts_count = $expected_conflicts_count, "
    "    m.expected_key_set_digest = $expected_key_set_digest, "
    "    m.expected_endpoint_digest = $expected_endpoint_digest, "
    "    m.expected_payload_digest = $expected_payload_digest, "
    "    m.created_at = $created_at "
    "ON MATCH SET "
    "    m.lock_epoch = coalesce(m.lock_epoch, 0) + 1 "
    "RETURN m.state AS state, "
    "       m.fence_digest AS old_fence_digest, "
    "       m.project_id AS project_id, "
    "       m.architecture_version_id AS architecture_version_id, "
    "       m.generation_id AS generation_id, "
    "       (m.lock_epoch = 1) AS created"
)

_UPDATE_CLAIM_FENCE_QUERY: Final[LiteralString] = (
    "MATCH (m:ProjectionManifest {generation_key: $generation_key}) "
    "SET m.fence_digest = $fence_digest, "
    "    m.updated_at = $updated_at "
    "RETURN m.state AS state"
)

_LOCK_MANIFEST_QUERY: Final[LiteralString] = (
    "MATCH (m:ProjectionManifest {generation_key: $generation_key}) "
    "SET m.lock_epoch = coalesce(m.lock_epoch, 0) + 1 "
    "RETURN m.state AS state, "
    "       m.fence_digest AS fence_digest, "
    "       m.project_id AS project_id, "
    "       m.architecture_version_id AS architecture_version_id, "
    "       m.generation_id AS generation_id"
)

# Fixed Cypher statements for batch writes
_WRITE_NODES_BATCH_QUERY: Final[LiteralString] = (
    "UNWIND $batch AS item "
    "MERGE (n:ArchitectureEntity {projection_key: item.projection_key}) "
    "SET n = item.properties "
    "RETURN count(n) AS written_count"
)

_WRITE_RELATIONSHIPS_BATCH_QUERY: Final[LiteralString] = (
    "UNWIND $batch AS item "
    "MATCH (s:ArchitectureEntity { "
    "    projection_key: item.source_key, "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}) "
    "MATCH (t:ArchitectureEntity { "
    "    projection_key: item.target_key, "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}) "
    "MERGE (s)-[r:ARCH_RELATIONSHIP {projection_key: item.projection_key}]->(t) "
    "SET r = item.properties "
    "RETURN count(r) AS written_count"
)

# Fixed Cypher statements for bounded resets and deletions
_DELETE_RELATIONSHIPS_PAGE_QUERY: Final[LiteralString] = (
    "MATCH (s:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "})-[r:ARCH_RELATIONSHIP { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}]->(t:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}) "
    "WITH r LIMIT $batch_size "
    "DELETE r "
    "RETURN count(r) AS deleted_count"
)

_DELETE_NODES_PAGE_QUERY: Final[LiteralString] = (
    "MATCH (n:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}) "
    "WITH n LIMIT $batch_size "
    "DELETE n "
    "RETURN count(n) AS deleted_count"
)

_DELETE_MANIFEST_QUERY: Final[LiteralString] = (
    "MATCH (m:ProjectionManifest { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}) "
    "DELETE m "
    "RETURN count(m) AS deleted_count"
)

# Fixed Cypher statement for finalization to READY
_FINALIZE_MANIFEST_QUERY: Final[LiteralString] = (
    "MATCH (m:ProjectionManifest {generation_key: $generation_key}) "
    "SET m.lock_epoch = coalesce(m.lock_epoch, 0) + 1 "
    "WITH m "
    "WHERE m.state = $state_building AND m.fence_digest = $fence_digest "
    "SET m.state = $state_ready, "
    "    m.fence_digest = null, "
    "    m.actual_entities_count = $actual_entities_count, "
    "    m.actual_relationships_count = $actual_relationships_count, "
    "    m.actual_evidence_count = $actual_evidence_count, "
    "    m.actual_unresolved_count = $actual_unresolved_count, "
    "    m.actual_conflicts_count = $actual_conflicts_count, "
    "    m.actual_key_set_digest = $actual_key_set_digest, "
    "    m.actual_endpoint_digest = $actual_endpoint_digest, "
    "    m.actual_payload_digest = $actual_payload_digest, "
    "    m.verified_at = $verified_at "
    "RETURN m.state AS state"
)

# Fixed Cypher statements for independent read-back inspection
_GET_MANIFEST_QUERY: Final[LiteralString] = (
    "MATCH (m:ProjectionManifest {generation_key: $generation_key}) "
    "RETURN m.generation_key AS generation_key, "
    "       m.state AS state, "
    "       m.project_id AS project_id, "
    "       m.architecture_version_id AS architecture_version_id, "
    "       m.generation_id AS generation_id, "
    "       m.source_content_digest AS source_content_digest, "
    "       m.source_schema_version AS source_schema_version, "
    "       m.graph_schema_version AS graph_schema_version, "
    "       m.projector_version AS projector_version, "
    "       m.fence_digest AS fence_digest, "
    "       m.lock_epoch AS lock_epoch, "
    "       m.expected_entities_count AS expected_entities_count, "
    "       m.expected_relationships_count AS expected_relationships_count, "
    "       m.expected_evidence_count AS expected_evidence_count, "
    "       m.expected_unresolved_count AS expected_unresolved_count, "
    "       m.expected_conflicts_count AS expected_conflicts_count, "
    "       m.expected_key_set_digest AS expected_key_set_digest, "
    "       m.expected_endpoint_digest AS expected_endpoint_digest, "
    "       m.expected_payload_digest AS expected_payload_digest, "
    "       m.actual_entities_count AS actual_entities_count, "
    "       m.actual_relationships_count AS actual_relationships_count, "
    "       m.actual_evidence_count AS actual_evidence_count, "
    "       m.actual_unresolved_count AS actual_unresolved_count, "
    "       m.actual_conflicts_count AS actual_conflicts_count, "
    "       m.actual_key_set_digest AS actual_key_set_digest, "
    "       m.actual_endpoint_digest AS actual_endpoint_digest, "
    "       m.actual_payload_digest AS actual_payload_digest, "
    "       labels(m) AS labels"
)

_COUNT_NODES_QUERY: Final[LiteralString] = (
    "MATCH (n:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}) "
    "RETURN count(n) AS total_count, "
    "       count(DISTINCT n.projection_key) AS distinct_count"
)

_COUNT_ANY_NODES_IN_SCOPE_QUERY: Final[LiteralString] = (
    "MATCH (n { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}) "
    "WHERE NOT n:ProjectionManifest "
    "RETURN count(n) AS total_count"
)

_ENUMERATE_NODES_PAGE_QUERY: Final[LiteralString] = (
    "MATCH (n:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}) "
    "WHERE $cursor IS NULL OR n.projection_key > $cursor "
    "RETURN n.projection_key AS projection_key, "
    "       properties(n) AS properties, "
    "       labels(n) AS labels "
    "ORDER BY n.projection_key ASC "
    "LIMIT $page_size"
)

_COUNT_RELATIONSHIPS_QUERY: Final[LiteralString] = (
    "MATCH (s:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "})-[r:ARCH_RELATIONSHIP { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}]->(t:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}) "
    "RETURN count(r) AS total_count, "
    "       count(DISTINCT r.projection_key) AS distinct_count"
)

_COUNT_ANY_RELATIONSHIPS_IN_SCOPE_QUERY: Final[LiteralString] = (
    "MATCH ()-[r { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}]->() "
    "RETURN count(r) AS total_count"
)

_ENUMERATE_RELATIONSHIPS_PAGE_QUERY: Final[LiteralString] = (
    "MATCH (s:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "})-[r:ARCH_RELATIONSHIP { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}]->(t:ArchitectureEntity { "
    "    project_id: $project_id, "
    "    architecture_version_id: $architecture_version_id, "
    "    generation_id: $generation_id "
    "}) "
    "WHERE $cursor IS NULL OR r.projection_key > $cursor "
    "RETURN r.projection_key AS projection_key, "
    "       s.projection_key AS source_key, "
    "       t.projection_key AS target_key, "
    "       type(r) AS rel_type, "
    "       properties(r) AS properties "
    "ORDER BY r.projection_key ASC "
    "LIMIT $page_size"
)


# Exception hierarchy for projection store operations
class ProjectionStoreError(ProjectionError):
    """Base error for projection store operations."""


class StaleFenceError(ProjectionStoreError):
    """Raised when manifest lock or fence check detects a stale or superseded worker."""

    def __init__(self, message: str = "Stale fence detected") -> None:
        super().__init__(message, code="graph_write_unavailable")


class ManifestLockError(ProjectionStoreError):
    """Raised when manifest cannot be locked or does not exist."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="graph_write_unavailable")


class ProjectionStoreScopeError(ProjectionStoreError):
    """Raised when manifest scope does not match expected generation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="graph_verification_scope_mismatch")


class ProjectionStoreStateError(ProjectionStoreError):
    """Raised when manifest state forbids candidate mutation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="graph_write_unavailable")


class GraphWriteIncompleteError(ProjectionStoreError):
    """Raised when a batch write does not write the expected number of records."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="graph_write_incomplete")


def compute_fence_digest(lease_token: str) -> str:
    """Compute the SHA-256 fence digest from the raw ephemeral lease token."""
    return hashlib.sha256(lease_token.encode("utf-8")).hexdigest().lower()


class ProjectionStore(Protocol):
    """Public protocol for narrow, isolated graph projection persistence."""

    def claim_candidate(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        lease_token: str,
        source_content_digest: str,
        source_schema_version: str = SOURCE_CONTRACT_VERSION,
        graph_schema_version: str = GRAPH_SCHEMA_VERSION,
        projector_version: str = PROJECTOR_VERSION,
        expected_counts: ProjectionCounts,
        expected_key_set_digest: str,
        expected_endpoint_digest: str,
        expected_payload_digest: str,
    ) -> None:
        """Atomically claim or fence an isolated candidate generation."""

    def reset_candidate(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        lease_token: str,
        page_size: int = 1000,
    ) -> int:
        """Boundedly delete candidate nodes and edges while preserving manifest."""

    def write_nodes(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        lease_token: str,
        nodes: Sequence[ProjectedNodeRecord],
        batch_size: int = 500,
    ) -> int:
        """Write nodes in bounded transactions under active manifest fence."""

    def write_relationships(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        lease_token: str,
        relationships: Sequence[ProjectedRelationshipRecord],
        batch_size: int = 1000,
    ) -> int:
        """Write relationships in bounded transactions under active manifest fence."""

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
    ) -> None:
        """Conditionally transition manifest from BUILDING to READY and clear fence."""

    def get_manifest(
        self,
        generation_key: str,
    ) -> dict[str, Any] | None:
        """Inspect manifest by generation key in a fresh read session."""

    def count_nodes(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
    ) -> tuple[int, int]:
        """Return (total, distinct_keys) for ArchitectureEntity nodes in scope."""

    def count_any_nodes_in_scope(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
    ) -> int:
        """Return total non-manifest nodes in scope to detect unexpected labels."""

    def enumerate_nodes(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        cursor: str | None = None,
        page_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return a page of ArchitectureEntity nodes sorted by projection_key ASC."""

    def count_relationships(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
    ) -> tuple[int, int]:
        """Return (total, distinct_keys) for ARCH_RELATIONSHIP edges in scope."""

    def count_any_relationships_in_scope(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
    ) -> int:
        """Return total count of relationships in scope to detect unexpected types."""

    def enumerate_relationships(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        cursor: str | None = None,
        page_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return a page of ARCH_RELATIONSHIP edges sorted by projection_key ASC."""

    def delete_generation(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        batch_size: int = 1000,
    ) -> int:
        """Boundedly delete an entire candidate generation (rels, nodes, manifest)."""


class Neo4jProjectionStore:
    """Official driver adapter implementing isolated, fenced graph projection."""

    def __init__(
        self,
        driver: Driver,
        settings: Settings,
    ) -> None:
        self._driver = driver
        self._settings = settings
        self._database = settings.neo4j_database
        self._timeout = settings.graph_projection_query_timeout_seconds

    def _lock_and_verify_manifest(
        self,
        tx: Transaction | ManagedTransaction,
        *,
        generation_key: str,
        project_id: str,
        architecture_version_id: str,
        generation_id: str,
        expected_fence_digest: str,
    ) -> None:
        """Acquire exclusive node write lock on ProjectionManifest and verify fence."""
        result = tx.run(
            _LOCK_MANIFEST_QUERY,
            generation_key=generation_key,
        ).single()

        if result is None:
            raise ManifestLockError(
                f"ProjectionManifest '{generation_key}' does not exist"
            )
        if result["state"] != MANIFEST_STATE_BUILDING:
            raise ProjectionStoreStateError(
                f"ProjectionManifest is not BUILDING (was {result['state']})"
            )
        if (
            result["project_id"] != project_id
            or result["architecture_version_id"] != architecture_version_id
            or result["generation_id"] != generation_id
        ):
            raise ProjectionStoreScopeError("ProjectionManifest scope mismatch")
        if result["fence_digest"] != expected_fence_digest:
            raise StaleFenceError("ProjectionManifest fence mismatch (stale worker)")

    def claim_candidate(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        lease_token: str,
        source_content_digest: str,
        source_schema_version: str = SOURCE_CONTRACT_VERSION,
        graph_schema_version: str = GRAPH_SCHEMA_VERSION,
        projector_version: str = PROJECTOR_VERSION,
        expected_counts: ProjectionCounts,
        expected_key_set_digest: str,
        expected_endpoint_digest: str,
        expected_payload_digest: str,
    ) -> None:
        """Claim a candidate generation or install a new fence if already BUILDING."""
        gen_key = compute_generation_key(
            project_id, architecture_version_id, generation_id
        )
        fence_digest = compute_fence_digest(lease_token)
        now_iso = datetime.now(UTC).isoformat()
        p_id = str(project_id).lower()
        a_id = str(architecture_version_id).lower()
        g_id = str(generation_id).lower()

        try:
            with self._driver.session(database=self._database) as session:
                with session.begin_transaction(timeout=self._timeout) as tx:
                    row = tx.run(
                        _CLAIM_MANIFEST_QUERY,
                        generation_key=gen_key,
                        state_building=MANIFEST_STATE_BUILDING,
                        fence_digest=fence_digest,
                        project_id=p_id,
                        architecture_version_id=a_id,
                        generation_id=g_id,
                        source_content_digest=source_content_digest,
                        source_schema_version=source_schema_version,
                        graph_schema_version=graph_schema_version,
                        projector_version=projector_version,
                        expected_entities_count=expected_counts.entities,
                        expected_relationships_count=expected_counts.relationships,
                        expected_evidence_count=expected_counts.evidence,
                        expected_unresolved_count=expected_counts.unresolved,
                        expected_conflicts_count=expected_counts.conflicts,
                        expected_key_set_digest=expected_key_set_digest,
                        expected_endpoint_digest=expected_endpoint_digest,
                        expected_payload_digest=expected_payload_digest,
                        created_at=now_iso,
                    ).single()

                    if row is None:
                        raise ProjectionStoreError("Claim query returned no result")

                    if not row["created"]:
                        # Check state and scope on existing manifest before fence update
                        if row["state"] != MANIFEST_STATE_BUILDING:
                            raise ProjectionStoreStateError(
                                f"Cannot claim generation in state '{row['state']}'"
                            )
                        if (
                            row["project_id"] != p_id
                            or row["architecture_version_id"] != a_id
                            or row["generation_id"] != g_id
                        ):
                            raise ProjectionStoreScopeError(
                                "Scope mismatch on existing ProjectionManifest"
                            )

                        tx.run(
                            _UPDATE_CLAIM_FENCE_QUERY,
                            generation_key=gen_key,
                            fence_digest=fence_digest,
                            updated_at=now_iso,
                        ).consume()

                    tx.commit()
        except ProjectionStoreError:
            raise
        except (DriverError, Neo4jError) as err:
            raise ProjectionStoreError(
                f"Neo4j claim operation failed: {type(err).__name__}"
            ) from None

    def reset_candidate(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        lease_token: str,
        page_size: int = 1000,
    ) -> int:
        """Boundedly delete candidate nodes and edges while preserving manifest."""
        gen_key = compute_generation_key(
            project_id, architecture_version_id, generation_id
        )
        fence_digest = compute_fence_digest(lease_token)
        p_id = str(project_id).lower()
        a_id = str(architecture_version_id).lower()
        g_id = str(generation_id).lower()
        total_deleted = 0

        try:
            with self._driver.session(database=self._database) as session:
                # 1. Boundedly delete relationships in pages under manifest lock
                while True:
                    with session.begin_transaction(timeout=self._timeout) as tx:
                        self._lock_and_verify_manifest(
                            tx,
                            generation_key=gen_key,
                            project_id=p_id,
                            architecture_version_id=a_id,
                            generation_id=g_id,
                            expected_fence_digest=fence_digest,
                        )
                        del_row = tx.run(
                            _DELETE_RELATIONSHIPS_PAGE_QUERY,
                            project_id=p_id,
                            architecture_version_id=a_id,
                            generation_id=g_id,
                            batch_size=page_size,
                        ).single()
                        deleted = del_row["deleted_count"] if del_row is not None else 0
                        tx.commit()
                        total_deleted += deleted
                        if deleted == 0:
                            break

                # 2. Boundedly delete nodes in pages under manifest lock
                while True:
                    with session.begin_transaction(timeout=self._timeout) as tx:
                        self._lock_and_verify_manifest(
                            tx,
                            generation_key=gen_key,
                            project_id=p_id,
                            architecture_version_id=a_id,
                            generation_id=g_id,
                            expected_fence_digest=fence_digest,
                        )
                        del_row = tx.run(
                            _DELETE_NODES_PAGE_QUERY,
                            project_id=p_id,
                            architecture_version_id=a_id,
                            generation_id=g_id,
                            batch_size=page_size,
                        ).single()
                        deleted = del_row["deleted_count"] if del_row is not None else 0
                        tx.commit()
                        total_deleted += deleted
                        if deleted == 0:
                            break
        except ProjectionStoreError:
            raise
        except (DriverError, Neo4jError) as err:
            raise ProjectionStoreError(
                f"Neo4j reset operation failed: {type(err).__name__}"
            ) from None

        return total_deleted

    def write_nodes(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        lease_token: str,
        nodes: Sequence[ProjectedNodeRecord],
        batch_size: int = 500,
    ) -> int:
        """Write nodes in bounded transactions under active manifest fence."""
        if not nodes:
            return 0

        gen_key = compute_generation_key(
            project_id, architecture_version_id, generation_id
        )
        fence_digest = compute_fence_digest(lease_token)
        p_id = str(project_id).lower()
        a_id = str(architecture_version_id).lower()
        g_id = str(generation_id).lower()
        total_written = 0

        try:
            with self._driver.session(database=self._database) as session:
                for idx in range(0, len(nodes), batch_size):
                    chunk = nodes[idx : idx + batch_size]
                    batch_payload = [
                        {
                            "projection_key": node.projection_key,
                            "properties": node.properties,
                        }
                        for node in chunk
                    ]

                    with session.begin_transaction(timeout=self._timeout) as tx:
                        self._lock_and_verify_manifest(
                            tx,
                            generation_key=gen_key,
                            project_id=p_id,
                            architecture_version_id=a_id,
                            generation_id=g_id,
                            expected_fence_digest=fence_digest,
                        )
                        row = tx.run(
                            _WRITE_NODES_BATCH_QUERY,
                            batch=batch_payload,
                        ).single()
                        written = row["written_count"] if row is not None else 0
                        if written != len(chunk):
                            raise GraphWriteIncompleteError(
                                f"Expected {len(chunk)} nodes written, got {written}"
                            )
                        tx.commit()
                        total_written += written
        except ProjectionStoreError:
            raise
        except (DriverError, Neo4jError) as err:
            raise ProjectionStoreError(
                f"Neo4j write nodes failed: {type(err).__name__}"
            ) from None

        return total_written

    def write_relationships(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        lease_token: str,
        relationships: Sequence[ProjectedRelationshipRecord],
        batch_size: int = 1000,
    ) -> int:
        """Write relationships in bounded transactions under active manifest fence."""
        if not relationships:
            return 0

        gen_key = compute_generation_key(
            project_id, architecture_version_id, generation_id
        )
        fence_digest = compute_fence_digest(lease_token)
        p_id = str(project_id).lower()
        a_id = str(architecture_version_id).lower()
        g_id = str(generation_id).lower()
        total_written = 0

        try:
            with self._driver.session(database=self._database) as session:
                for idx in range(0, len(relationships), batch_size):
                    chunk = relationships[idx : idx + batch_size]
                    batch_payload = [
                        {
                            "projection_key": rel.projection_key,
                            "source_key": rel.source_projection_key,
                            "target_key": rel.target_projection_key,
                            "properties": rel.properties,
                        }
                        for rel in chunk
                    ]

                    with session.begin_transaction(timeout=self._timeout) as tx:
                        self._lock_and_verify_manifest(
                            tx,
                            generation_key=gen_key,
                            project_id=p_id,
                            architecture_version_id=a_id,
                            generation_id=g_id,
                            expected_fence_digest=fence_digest,
                        )
                        row = tx.run(
                            _WRITE_RELATIONSHIPS_BATCH_QUERY,
                            batch=batch_payload,
                            project_id=p_id,
                            architecture_version_id=a_id,
                            generation_id=g_id,
                        ).single()
                        written = row["written_count"] if row is not None else 0
                        if written != len(chunk):
                            raise GraphWriteIncompleteError(
                                f"Expected {len(chunk)} relationships written, "
                                f"got {written} (endpoint missing in scope)"
                            )
                        tx.commit()
                        total_written += written
        except ProjectionStoreError:
            raise
        except (DriverError, Neo4jError) as err:
            raise ProjectionStoreError(
                f"Neo4j write relationships failed: {type(err).__name__}"
            ) from None

        return total_written

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
    ) -> None:
        """Conditionally transition manifest from BUILDING to READY and clear fence."""
        gen_key = compute_generation_key(
            project_id, architecture_version_id, generation_id
        )
        fence_digest = compute_fence_digest(lease_token)
        now_iso = datetime.now(UTC).isoformat()

        try:
            with self._driver.session(database=self._database) as session:
                with session.begin_transaction(timeout=self._timeout) as tx:
                    row = tx.run(
                        _FINALIZE_MANIFEST_QUERY,
                        generation_key=gen_key,
                        state_building=MANIFEST_STATE_BUILDING,
                        state_ready=MANIFEST_STATE_READY,
                        fence_digest=fence_digest,
                        actual_entities_count=actual_counts.entities,
                        actual_relationships_count=actual_counts.relationships,
                        actual_evidence_count=actual_counts.evidence,
                        actual_unresolved_count=actual_counts.unresolved,
                        actual_conflicts_count=actual_counts.conflicts,
                        actual_key_set_digest=actual_key_set_digest,
                        actual_endpoint_digest=actual_endpoint_digest,
                        actual_payload_digest=actual_payload_digest,
                        verified_at=now_iso,
                    ).single()

                    if row is None:
                        raise StaleFenceError(
                            "Finalize failed: manifest not in BUILDING or fence lost"
                        )
                    tx.commit()
        except ProjectionStoreError:
            raise
        except (DriverError, Neo4jError) as err:
            raise ProjectionStoreError(
                f"Neo4j finalize failed: {type(err).__name__}"
            ) from None

    def get_manifest(
        self,
        generation_key: str,
    ) -> dict[str, Any] | None:
        """Inspect manifest by generation key in a fresh read session."""
        try:
            with self._driver.session(database=self._database) as session:
                record = session.run(
                    Query(_GET_MANIFEST_QUERY, timeout=self._timeout),
                    generation_key=generation_key,
                ).single()
                if record is None:
                    return None
                return dict(record.data())
        except (DriverError, Neo4jError) as err:
            raise ProjectionStoreError(
                f"Neo4j get manifest failed: {type(err).__name__}"
            ) from None

    def count_nodes(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
    ) -> tuple[int, int]:
        """Return (total, distinct_keys) for ArchitectureEntity nodes in scope."""
        p_id = str(project_id).lower()
        a_id = str(architecture_version_id).lower()
        g_id = str(generation_id).lower()
        try:
            with self._driver.session(database=self._database) as session:
                record = session.run(
                    Query(_COUNT_NODES_QUERY, timeout=self._timeout),
                    project_id=p_id,
                    architecture_version_id=a_id,
                    generation_id=g_id,
                ).single()
                if record is None:
                    return 0, 0
                return int(record["total_count"]), int(record["distinct_count"])
        except (DriverError, Neo4jError) as err:
            raise ProjectionStoreError(
                f"Neo4j count nodes failed: {type(err).__name__}"
            ) from None

    def count_any_nodes_in_scope(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
    ) -> int:
        """Return total non-manifest nodes in scope to detect unexpected labels."""
        p_id = str(project_id).lower()
        a_id = str(architecture_version_id).lower()
        g_id = str(generation_id).lower()
        try:
            with self._driver.session(database=self._database) as session:
                record = session.run(
                    Query(_COUNT_ANY_NODES_IN_SCOPE_QUERY, timeout=self._timeout),
                    project_id=p_id,
                    architecture_version_id=a_id,
                    generation_id=g_id,
                ).single()
                if record is None:
                    return 0
                return int(record["total_count"])
        except (DriverError, Neo4jError) as err:
            raise ProjectionStoreError(
                f"Neo4j count any nodes failed: {type(err).__name__}"
            ) from None

    def enumerate_nodes(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        cursor: str | None = None,
        page_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return a page of ArchitectureEntity nodes sorted by projection_key ASC."""
        p_id = str(project_id).lower()
        a_id = str(architecture_version_id).lower()
        g_id = str(generation_id).lower()
        try:
            with self._driver.session(database=self._database) as session:
                records = session.run(
                    Query(_ENUMERATE_NODES_PAGE_QUERY, timeout=self._timeout),
                    project_id=p_id,
                    architecture_version_id=a_id,
                    generation_id=g_id,
                    cursor=cursor,
                    page_size=page_size,
                ).data()
                return records
        except (DriverError, Neo4jError) as err:
            raise ProjectionStoreError(
                f"Neo4j enumerate nodes failed: {type(err).__name__}"
            ) from None

    def count_relationships(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
    ) -> tuple[int, int]:
        """Return (total, distinct_keys) for ARCH_RELATIONSHIP edges in scope."""
        p_id = str(project_id).lower()
        a_id = str(architecture_version_id).lower()
        g_id = str(generation_id).lower()
        try:
            with self._driver.session(database=self._database) as session:
                record = session.run(
                    Query(_COUNT_RELATIONSHIPS_QUERY, timeout=self._timeout),
                    project_id=p_id,
                    architecture_version_id=a_id,
                    generation_id=g_id,
                ).single()
                if record is None:
                    return 0, 0
                return int(record["total_count"]), int(record["distinct_count"])
        except (DriverError, Neo4jError) as err:
            raise ProjectionStoreError(
                f"Neo4j count relationships failed: {type(err).__name__}"
            ) from None

    def count_any_relationships_in_scope(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
    ) -> int:
        """Return total count of relationships in scope to detect unexpected types."""
        p_id = str(project_id).lower()
        a_id = str(architecture_version_id).lower()
        g_id = str(generation_id).lower()
        try:
            with self._driver.session(database=self._database) as session:
                record = session.run(
                    Query(
                        _COUNT_ANY_RELATIONSHIPS_IN_SCOPE_QUERY, timeout=self._timeout
                    ),
                    project_id=p_id,
                    architecture_version_id=a_id,
                    generation_id=g_id,
                ).single()
                if record is None:
                    return 0
                return int(record["total_count"])
        except (DriverError, Neo4jError) as err:
            raise ProjectionStoreError(
                f"Neo4j count any relationships failed: {type(err).__name__}"
            ) from None

    def enumerate_relationships(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        cursor: str | None = None,
        page_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return a page of ARCH_RELATIONSHIP edges sorted by projection_key ASC."""
        p_id = str(project_id).lower()
        a_id = str(architecture_version_id).lower()
        g_id = str(generation_id).lower()
        try:
            with self._driver.session(database=self._database) as session:
                records = session.run(
                    Query(_ENUMERATE_RELATIONSHIPS_PAGE_QUERY, timeout=self._timeout),
                    project_id=p_id,
                    architecture_version_id=a_id,
                    generation_id=g_id,
                    cursor=cursor,
                    page_size=page_size,
                ).data()
                return records
        except (DriverError, Neo4jError) as err:
            raise ProjectionStoreError(
                f"Neo4j enumerate relationships failed: {type(err).__name__}"
            ) from None

    def delete_generation(
        self,
        *,
        project_id: UUID,
        architecture_version_id: UUID,
        generation_id: UUID,
        batch_size: int = 1000,
    ) -> int:
        """Boundedly delete an entire candidate generation (rels, nodes, manifest)."""
        p_id = str(project_id).lower()
        a_id = str(architecture_version_id).lower()
        g_id = str(generation_id).lower()
        total_deleted = 0

        try:
            with self._driver.session(database=self._database) as session:
                # 1. Delete relationships in pages
                while True:
                    with session.begin_transaction(timeout=self._timeout) as tx:
                        del_row = tx.run(
                            _DELETE_RELATIONSHIPS_PAGE_QUERY,
                            project_id=p_id,
                            architecture_version_id=a_id,
                            generation_id=g_id,
                            batch_size=batch_size,
                        ).single()
                        deleted = del_row["deleted_count"] if del_row is not None else 0
                        tx.commit()
                        total_deleted += deleted
                        if deleted == 0:
                            break

                # 2. Delete nodes in pages
                while True:
                    with session.begin_transaction(timeout=self._timeout) as tx:
                        del_row = tx.run(
                            _DELETE_NODES_PAGE_QUERY,
                            project_id=p_id,
                            architecture_version_id=a_id,
                            generation_id=g_id,
                            batch_size=batch_size,
                        ).single()
                        deleted = del_row["deleted_count"] if del_row is not None else 0
                        tx.commit()
                        total_deleted += deleted
                        if deleted == 0:
                            break

                # 3. Delete manifest
                with session.begin_transaction(timeout=self._timeout) as tx:
                    del_row = tx.run(
                        _DELETE_MANIFEST_QUERY,
                        project_id=p_id,
                        architecture_version_id=a_id,
                        generation_id=g_id,
                    ).single()
                    deleted = del_row["deleted_count"] if del_row is not None else 0
                    tx.commit()
                    total_deleted += deleted
        except (DriverError, Neo4jError) as err:
            raise ProjectionStoreError(
                f"Neo4j delete generation failed: {type(err).__name__}"
            ) from None

        return total_deleted
