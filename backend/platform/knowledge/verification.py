"""Independent verification of candidate search index generations before publication.

Performs match-all readback, key set verification, payload digest computation,
and count validation against projected records per §7.4 and §7.10.
"""

from __future__ import annotations

import collections
import hashlib
from typing import Final
from uuid import UUID, uuid4

from backend.platform.delivery.contracts import ProducerProfile, VersionScope
from backend.platform.knowledge.elasticsearch import SearchIndexBackend
from backend.platform.knowledge.model import (
    C1_CONTRACT_VERSION,
    KnowledgeCounts,
    KnowledgeDocumentKind,
    KnowledgeProjection,
    SearchVerificationResult,
    canonical_json,
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
        generation_id: UUID,
        index_name: str,
        index_uuid: str,
        expected_projection: KnowledgeProjection,
    ) -> SearchVerificationResult:
        """Independently read back candidate index.

        Audits returned summaries against expected projection.
        """
        attempt_id = uuid4()
        summaries = self._backend.read_all_record_summaries(index_name)

        # 1. Compute actual counts
        kind_counts: collections.Counter[str] = collections.Counter()
        for s in summaries:
            kind_counts[s.document_kind] += 1

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

        if actual_counts != expected_projection.counts:
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
