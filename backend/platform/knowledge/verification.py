"""Independent verification of candidate search index generations before publication.

Performs match-all readback, key set verification, payload digest computation,
and count validation against projected records per §7.4 and §7.10.
"""

from __future__ import annotations

import collections
import hashlib
from typing import Any, Final
from uuid import UUID

from backend.platform.delivery.contracts import ProducerProfile, VersionScope
from backend.platform.knowledge.contracts import SearchIntegrityError
from backend.platform.knowledge.elasticsearch import (
    SEARCH_INDEX_MAPPINGS,
    SEARCH_INDEX_SETTINGS,
    RecordSummary,
    SearchIndexBackend,
    compute_mapping_hash,
    compute_settings_hash,
)
from backend.platform.knowledge.model import (
    C1_CONTRACT_VERSION,
    KnowledgeCounts,
    KnowledgeDocumentKind,
    KnowledgeProjection,
    SearchVerificationResult,
    canonical_json,
    stored_record_digest,
)

VERIFIER_VERSION: Final[str] = "1.0.0"
SEAL_PROTOCOL_VERSION: Final[str] = "1.0.0"
MAPPING_VERSION: Final[str] = "1.0.0"


class SearchVerifier:
    """Independent candidate validator auditing Elasticsearch records."""

    def __init__(self, backend: SearchIndexBackend) -> None:
        self._backend = backend

    def verify(
        self,
        *,
        scope: VersionScope,
        profile: ProducerProfile,
        candidate_id: UUID,
        attempt_id: UUID,
        generation_id: UUID,
        index_name: str,
        index_uuid: str,
        expected_projection: KnowledgeProjection,
        expected_settings: dict[str, Any] | None = None,
    ) -> SearchVerificationResult:
        """Independently read back candidate index.

        Audits returned summaries against expected projection.
        """
        actual = self._backend.inspect_index(index_name)
        physical_valid = (
            actual["uuid"] == index_uuid
            and actual["sealed"] is True
            and actual["mapping_hash"] == compute_mapping_hash(SEARCH_INDEX_MAPPINGS)
            and actual["settings_hash"]
            == compute_settings_hash(
                expected_settings
                if expected_settings is not None
                else SEARCH_INDEX_SETTINGS
            )
        )
        expected_envelopes = {
            r.to_stored_envelope(generation_id=generation_id, index_uuid=index_uuid)[
                "storage_key"
            ]: r.to_stored_envelope(generation_id=generation_id, index_uuid=index_uuid)
            for r in expected_projection.records
        }
        summaries = []
        seen: set[str] = set()
        payload_valid = True
        for record in self._backend.iter_records(index_name):
            key = record.get("storage_key", "")
            expected = expected_envelopes.get(key)
            if (
                key in seen
                or expected is None
                or canonical_json(record) != canonical_json(expected)
            ):
                payload_valid = False
            seen.add(key)
            recomputed_digest = stored_record_digest(record, scope)
            if recomputed_digest != record.get("record_semantic_digest"):
                payload_valid = False
            summaries.append(
                RecordSummary(
                    key,
                    record.get("knowledge_key", ""),
                    record.get("document_kind", ""),
                    recomputed_digest,
                )
            )
        physical_valid = (
            physical_valid and self._backend.inspect_index(index_name) == actual
        )

        # 1. Compute actual counts
        kind_counts: collections.Counter[str] = collections.Counter()
        for s in summaries:
            kind_counts[s.document_kind] += 1
        if set(kind_counts) - {kind.value for kind in KnowledgeDocumentKind}:
            raise SearchIntegrityError("Unexpected physical document kind")

        actual_counts = KnowledgeCounts(
            entities=kind_counts[KnowledgeDocumentKind.ENTITY.value],
            relationships=kind_counts[KnowledgeDocumentKind.RELATIONSHIP.value],
            evidence=kind_counts[KnowledgeDocumentKind.EVIDENCE.value],
            unresolved=kind_counts[KnowledgeDocumentKind.UNRESOLVED.value],
            conflicts=kind_counts[KnowledgeDocumentKind.CONFLICT.value],
            architecture_summaries=kind_counts[
                KnowledgeDocumentKind.ARCHITECTURE_SUMMARY.value
            ],
            total_records=len(summaries),
        )

        # 2. Compute key set digests
        actual_keys = sorted(s.knowledge_key for s in summaries)
        actual_key_set_digest = hashlib.sha256(
            canonical_json(actual_keys).encode("utf-8")
        ).hexdigest()

        expected_keys = sorted(r.knowledge_key for r in expected_projection.records)
        expected_key_set_digest = hashlib.sha256(
            canonical_json(expected_keys).encode("utf-8")
        ).hexdigest()

        # 3. Compute payload digests
        sorted_actual_pairs = sorted(
            [[s.knowledge_key, s.record_semantic_digest] for s in summaries],
            key=lambda item: item[0],
        )
        actual_payload_digest = hashlib.sha256(
            canonical_json(sorted_actual_pairs).encode("utf-8")
        ).hexdigest()

        sorted_expected_pairs = sorted(
            [[r.knowledge_key, r.record_digest] for r in expected_projection.records],
            key=lambda item: item[0],
        )
        expected_payload_digest = hashlib.sha256(
            canonical_json(sorted_expected_pairs).encode("utf-8")
        ).hexdigest()

        # 4. Check for mismatches
        verified = True
        failure_code: str | None = None
        failure_reason: str | None = None

        if not physical_valid:
            verified = False
            failure_code = "physical_identity_or_seal_mismatch"
        elif actual_counts != expected_projection.counts:
            verified = False
            failure_code = "count_mismatch"
            failure_reason = (
                f"Actual counts {actual_counts} do not match "
                f"expected {expected_projection.counts}"
            )
        elif actual_key_set_digest != expected_key_set_digest:
            verified = False
            failure_code = "key_set_digest_mismatch"
            failure_reason = (
                f"Actual key set digest {actual_key_set_digest} != "
                f"expected {expected_key_set_digest}"
            )
        elif actual_payload_digest != expected_payload_digest:
            verified = False
            failure_code = "payload_digest_mismatch"
            failure_reason = (
                f"Actual payload digest {actual_payload_digest} != "
                f"expected {expected_payload_digest}"
            )
        elif not payload_valid:
            verified = False
            failure_code = "stored_payload_mismatch"

        return SearchVerificationResult(
            c1_version=C1_CONTRACT_VERSION,
            scope=scope,
            attempt_id=attempt_id,
            candidate_id=candidate_id,
            generation_id=generation_id,
            profile=profile,
            index_uuid=index_uuid,
            expected_counts=expected_projection.counts,
            actual_counts=actual_counts,
            expected_key_set_digest=expected_key_set_digest,
            actual_key_set_digest=actual_key_set_digest,
            expected_payload_digest=expected_payload_digest,
            actual_payload_digest=actual_payload_digest,
            mapping_version=MAPPING_VERSION,
            verifier_version=VERIFIER_VERSION,
            seal_version=SEAL_PROTOCOL_VERSION,
            verified=verified,
            failure_code=failure_code,
            failure_reason=failure_reason,
        )


__all__ = [
    "MAPPING_VERSION",
    "SEAL_PROTOCOL_VERSION",
    "SearchVerifier",
    "VERIFIER_VERSION",
]
