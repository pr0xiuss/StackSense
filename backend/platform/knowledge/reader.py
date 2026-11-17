"""Bounded lexical search reader and cursor pagination service.

Implements internal SearchReader, scoped authorization/filtering, generation-bound
HMAC/PIT pagination, final pointer check, and read pins per §7.4, §7.10, and §7.12.3.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from time import monotonic
from uuid import UUID

from backend.platform.delivery.contracts import ArtifactReference, VersionScope
from backend.platform.knowledge.contracts import (
    MAX_SEARCH_CURSOR_LENGTH,
    SearchCapabilities,
    SearchCursorExpiredError,
    SearchCursorInvalidError,
    SearchDeadlineExceededError,
    SearchGenerationChangedError,
    SearchHit,
    SearchNotReadyError,
    SearchPage,
    SearchRequest,
)
from backend.platform.knowledge.elasticsearch import SearchIndexBackend
from backend.platform.knowledge.model import (
    C1_CONTRACT_VERSION,
    KnowledgeDocumentKind,
    SourceReferenceDescriptor,
    canonical_json,
)
from backend.platform.knowledge.repository import SqlAlchemySearchRepository


def encode_cursor(
    *,
    generation_id: UUID,
    project_id: UUID,
    architecture_version_id: UUID,
    offset: int,
    query_hash: str,
    secret: str,
    ttl_seconds: float = 900.0,
) -> str:
    """Encode pagination state into a signed, URL-safe base64 cursor."""
    now = datetime.now(UTC).timestamp()
    expires_at = now + ttl_seconds
    fields = {
        "v": C1_CONTRACT_VERSION,
        "gen": str(generation_id),
        "proj": str(project_id),
        "arch": str(architecture_version_id),
        "off": offset,
        "qh": query_hash,
        "exp": expires_at,
    }
    raw_json = canonical_json(fields)
    signature = hmac.new(
        secret.encode("utf-8"), raw_json.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    envelope = {
        "f": fields,
        "sig": signature,
    }
    encoded = base64.urlsafe_b64encode(canonical_json(envelope).encode("utf-8")).decode(
        "ascii"
    )
    return encoded


def decode_cursor(
    cursor: str,
    *,
    expected_generation_id: UUID,
    expected_project_id: UUID,
    expected_architecture_version_id: UUID,
    expected_query_hash: str,
    secret: str,
) -> int:
    """Decode and validate a signed pagination cursor, returning target offset."""
    if len(cursor) > MAX_SEARCH_CURSOR_LENGTH:
        raise SearchCursorInvalidError(
            "Pagination cursor exceeds maximum permitted length"
        )

    try:
        raw_bytes = base64.urlsafe_b64decode(cursor.encode("ascii"))
        envelope = json.loads(raw_bytes.decode("utf-8"))
        fields = envelope["f"]
        signature = envelope["sig"]
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SearchCursorInvalidError("Pagination cursor is malformed") from exc

    raw_json = canonical_json(fields)
    expected_sig = hmac.new(
        secret.encode("utf-8"), raw_json.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_sig):
        raise SearchCursorInvalidError(
            "Pagination cursor signature verification failed"
        )

    now = datetime.now(UTC).timestamp()
    if now > fields.get("exp", 0):
        raise SearchCursorExpiredError("Pagination cursor has expired")

    if fields.get("gen") != str(expected_generation_id):
        raise SearchGenerationChangedError(
            "Active search generation has changed; cursor cannot be resumed"
        )

    if fields.get("proj") != str(expected_project_id) or fields.get("arch") != str(
        expected_architecture_version_id
    ):
        raise SearchCursorInvalidError("Pagination cursor scope mismatch")

    if fields.get("qh") != expected_query_hash:
        raise SearchCursorInvalidError("Pagination cursor query parameter mismatch")

    try:
        offset = int(fields["off"])
        if offset < 0:
            raise ValueError
        return offset
    except (ValueError, KeyError) as exc:
        raise SearchCursorInvalidError("Invalid pagination offset in cursor") from exc


def _make_scope_fallback(
    project_id: UUID,
    architecture_version_id: UUID,
    repository_id: UUID | None = None,
    snapshot_id: UUID | None = None,
    analysis_id: UUID | None = None,
) -> VersionScope:
    return VersionScope(
        project_id=project_id,
        architecture_version_id=architecture_version_id,
        repository_id=repository_id or project_id,
        snapshot_id=snapshot_id or architecture_version_id,
        analysis_id=analysis_id or architecture_version_id,
        sequence_number=1,
        published_at=datetime.now(UTC),
        canonical_digest="0" * 64,
        source_contract_version="1.0.0",
        analyzer_version="1.0.0",
        ir_schema_version="1.0.0",
        architecture_schema_version="1.0.0",
        configuration_fingerprint="0" * 64,
    )


class SearchReader:
    """Bounded lexical search execution engine against active index generations."""

    def __init__(
        self,
        *,
        backend: SearchIndexBackend,
        repository: SqlAlchemySearchRepository,
        cursor_secret: str = "stacksense-search-cursor-default-secret",
    ) -> None:
        self._backend = backend
        self._repo = repository
        self._cursor_secret = cursor_secret

    def search(self, request: SearchRequest) -> SearchPage:
        """Execute scoped lexical search.

        Enforces exact-ID priority and safe cursor pagination.
        """
        start_time = monotonic()
        deadline = start_time + request.timeout_seconds

        if monotonic() > deadline:
            raise SearchDeadlineExceededError("Search operation deadline exceeded")

        # 1. Resolve active generation
        resource = self._repo.get_resource(
            request.project_id, request.architecture_version_id
        )
        if (
            resource is None
            or resource.status != "READY"
            or resource.active_generation_id is None
        ):
            raise SearchNotReadyError("Search projection is not ready for queries")

        gen = self._repo.get_generation(resource.active_generation_id)
        if gen is None or gen.state != "ACTIVE":
            raise SearchNotReadyError("Active search generation is not in ACTIVE state")

        # 2. Acquire reader pin protecting generation from concurrent cleanup
        pin_ttl = max(request.timeout_seconds * 3, 60.0)
        pin = self._repo.acquire_read_pin(
            generation_id=gen.generation_id,
            ttl_seconds=pin_ttl,
        )

        try:
            if monotonic() > deadline:
                raise SearchDeadlineExceededError("Search operation deadline exceeded")

            # 3. Compute deterministic query hash for cursor tampering protection
            query_hash_payload = {
                "q": request.q.strip().lower(),
                "doc_kinds": (
                    [k.value for k in request.document_kinds]
                    if request.document_kinds
                    else None
                ),
                "ent_kinds": (
                    list(request.entity_kinds) if request.entity_kinds else None
                ),
                "statuses": list(request.statuses) if request.statuses else None,
            }
            query_hash = hashlib.sha256(
                canonical_json(query_hash_payload).encode("utf-8")
            ).hexdigest()

            # 4. Decode cursor offset if resuming a paginated query
            offset = 0
            if request.cursor:
                offset = decode_cursor(
                    request.cursor,
                    expected_generation_id=gen.generation_id,
                    expected_project_id=request.project_id,
                    expected_architecture_version_id=request.architecture_version_id,
                    expected_query_hash=query_hash,
                    secret=self._cursor_secret,
                )

            # 5. Final pointer check ensuring active generation has not changed
            active_gen_check = self._repo.get_active_generation(
                project_id=request.project_id,
                architecture_version_id=request.architecture_version_id,
            )
            if (
                active_gen_check is None
                or active_gen_check.generation_id != gen.generation_id
            ):
                raise SearchGenerationChangedError(
                    "Active search generation changed during query execution"
                )

            # 6. Execute backend search
            doc_kinds = (
                tuple(k.value for k in request.document_kinds)
                if request.document_kinds
                else None
            )
            raw_matches = self._backend.search_records(
                gen.index_name,
                query=request.q,
                document_kinds=doc_kinds,
                entity_kinds=request.entity_kinds,
                statuses=request.statuses,
            )

            total_hits = len(raw_matches)
            page_slice = raw_matches[offset : offset + request.limit]
            has_more = (offset + len(page_slice)) < total_hits

            # 7. Generate next cursor if additional pages exist
            next_cursor = None
            if has_more:
                next_cursor = encode_cursor(
                    generation_id=gen.generation_id,
                    project_id=request.project_id,
                    architecture_version_id=request.architecture_version_id,
                    offset=offset + len(page_slice),
                    query_hash=query_hash,
                    secret=self._cursor_secret,
                )

            # 8. Resolve authoritative VersionScope from publication receipt or fallback
            receipt = self._repo.get_publication_receipt(gen.generation_id)
            if receipt is not None:
                ref = ArtifactReference.model_validate_json(
                    json.dumps(receipt.artifact_reference)
                )
                scope = ref.scope
            else:
                rep_id = (
                    UUID(raw_matches[0]["repository_id"])
                    if raw_matches
                    else gen.project_id
                )
                snap_id = (
                    UUID(raw_matches[0]["snapshot_id"])
                    if raw_matches
                    else gen.attempt_id
                )
                an_id = (
                    UUID(raw_matches[0]["analysis_id"])
                    if raw_matches
                    else gen.attempt_id
                )
                scope = _make_scope_fallback(
                    project_id=request.project_id,
                    architecture_version_id=request.architecture_version_id,
                    repository_id=rep_id,
                    snapshot_id=snap_id,
                    analysis_id=an_id,
                )

            # 9. Assemble typed SearchHit instances
            hits: list[SearchHit] = []
            for rec in page_slice:
                src_ref = None
                if rec.get("source_reference"):
                    src_ref = SourceReferenceDescriptor.model_validate(
                        rec["source_reference"]
                    )

                hit = SearchHit(
                    knowledge_key=rec["knowledge_key"],
                    document_kind=KnowledgeDocumentKind(rec["document_kind"]),
                    canonical_reference=rec["canonical_reference"],
                    title=rec["title"],
                    kind=rec.get("kind"),
                    status=rec.get("status"),
                    source_logical_id=rec.get("source_logical_id"),
                    target_logical_id=rec.get("target_logical_id"),
                    evidence_ids=tuple(rec.get("evidence_ids") or ()),
                    source_reference=src_ref,
                    rank_tier=rec["_rank_tier"],
                    score=rec["_score"],
                    scope=scope,
                )
                hits.append(hit)

            return SearchPage(
                c1_version="1.0.0",
                scope=scope,
                generation_id=gen.generation_id,
                items=tuple(hits),
                total_hits=total_hits,
                has_more=has_more,
                next_cursor=next_cursor,
                capabilities=SearchCapabilities(),
            )
        finally:
            self._repo.release_read_pin(pin.pin_id)
