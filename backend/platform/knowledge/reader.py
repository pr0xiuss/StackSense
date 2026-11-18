"""Bounded lexical search reader and cursor pagination service.

Implements internal SearchReader, scoped authorization/filtering, generation-bound
HMAC/PIT pagination, final pointer check, and read pins per §7.4, §7.10, and §7.12.3.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import sys
from datetime import UTC, datetime
from time import monotonic
from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from backend.platform.delivery.contracts import ArtifactReference
from backend.platform.knowledge.contracts import (
    MAX_SEARCH_CURSOR_LENGTH,
    SearchBackendUnavailableError,
    SearchCursorExpiredError,
    SearchCursorInvalidError,
    SearchDeadlineExceededError,
    SearchGenerationChangedError,
    SearchHit,
    SearchIntegrityError,
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
    compute_knowledge_key,
    compute_storage_key,
    stored_record_digest,
)
from backend.platform.knowledge.repository import SqlAlchemySearchRepository


def encode_cursor(
    *,
    generation_id: UUID,
    project_id: UUID,
    architecture_version_id: UUID,
    query_hash: str,
    secret: str,
    ttl_seconds: float,
    state: dict[str, object],
) -> str:
    """Encode pagination state into a signed, URL-safe base64 cursor."""
    now = datetime.now(UTC).timestamp()
    expires_at = now + ttl_seconds
    fields = {
        "v": C1_CONTRACT_VERSION,
        "gen": str(generation_id),
        "proj": str(project_id),
        "arch": str(architecture_version_id),
        "qh": query_hash,
        "exp": expires_at,
        "state": state,
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
) -> dict[str, Any]:
    """Decode an exact signed PIT/search-after envelope, never an offset."""
    if len(cursor) > MAX_SEARCH_CURSOR_LENGTH:
        raise SearchCursorInvalidError(
            "Pagination cursor exceeds maximum permitted length"
        )

    try:
        raw_bytes = base64.b64decode(
            cursor.encode("ascii"), altchars=b"-_", validate=True
        )
        envelope = json.loads(raw_bytes.decode("utf-8"))
        fields: dict[str, Any] = envelope["f"]
        signature = envelope["sig"]
        if (
            set(envelope) != {"f", "sig"}
            or not isinstance(fields, dict)
            or set(fields) != {"v", "gen", "proj", "arch", "qh", "exp", "state"}
            or fields.get("v") != C1_CONTRACT_VERSION
        ):
            raise ValueError("Unsupported cursor shape/version")
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SearchCursorInvalidError("Pagination cursor is malformed") from exc

    raw_json = canonical_json(fields)
    expected_sig = hmac.new(
        secret.encode("utf-8"), raw_json.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not isinstance(signature, str) or not hmac.compare_digest(
        signature, expected_sig
    ):
        raise SearchCursorInvalidError(
            "Pagination cursor signature verification failed"
        )

    expiry = fields.get("exp")
    if (
        not isinstance(expiry, (int, float))
        or isinstance(expiry, bool)
        or not math.isfinite(expiry)
    ):
        raise SearchCursorInvalidError("Invalid cursor expiry")
    now = datetime.now(UTC).timestamp()
    if now > expiry:
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

    return fields


class SearchReader:
    """Bounded lexical search execution engine against active index generations."""

    def __init__(
        self,
        *,
        backend: SearchIndexBackend,
        repository: SqlAlchemySearchRepository,
        cursor_secret: str,
        cursor_ttl_seconds: float,
    ) -> None:
        self._backend = backend
        self._repo = repository
        self._cursor_secret = cursor_secret
        if len(cursor_secret.encode()) < 32:
            raise ValueError("search cursor secret must have at least 32 bytes")
        self._cursor_ttl = cursor_ttl_seconds
        if not math.isfinite(cursor_ttl_seconds) or cursor_ttl_seconds <= 0:
            raise ValueError("explicit positive cursor lifetime required")

    def search(
        self, request: SearchRequest, *, actor_id: UUID | None = None
    ) -> SearchPage:
        """Only committed exact references and signed PIT/search-after sessions."""
        from backend.platform.delivery.contracts import DeliveryContractError
        from backend.platform.knowledge.repository import SearchPublicationPort

        request = SearchRequest.model_validate(request)
        deadline = monotonic() + request.timeout_seconds
        pit_id: str | None = None
        pin_id: UUID | None = None
        keep_open = False
        try:
            with self._backend.operation(deadline):
                self._repo.read_deadline(deadline)
                resource = self._repo.get_resource(
                    request.project_id, request.architecture_version_id
                )
                if resource is None or resource.active_generation_id is None:
                    raise SearchNotReadyError()
                gen = self._repo.get_generation(resource.active_generation_id)
                receipt = self._repo.get_publication_receipt(
                    resource.active_generation_id
                )
                if gen is None or receipt is None:
                    raise SearchIntegrityError("Accepted search reference is missing")
                ref = ArtifactReference.model_validate_json(
                    json.dumps(receipt.artifact_reference)
                )
                if (
                    ref.scope.project_id != request.project_id
                    or ref.scope.architecture_version_id
                    != request.architecture_version_id
                ):
                    raise SearchIntegrityError("Search reference scope mismatch")
                manifest = SearchPublicationPort(self._repo._session).require_accepted(
                    ref
                )
                physical = self._backend.inspect_index(manifest.index_name)
                if (
                    physical["uuid"] != manifest.index_uuid
                    or physical["sealed"] is not True
                ):
                    raise SearchIntegrityError("Search physical identity/seal mismatch")
                query_hash = hashlib.sha256(
                    canonical_json(
                        {
                            "q": request.q,
                            "mode": request.mode,
                            "kinds": request.document_kinds,
                            "entity_kinds": request.entity_kinds,
                            "statuses": request.statuses,
                            "limit": request.limit,
                            "actor": str(actor_id) if actor_id else None,
                            "index": manifest.index_uuid,
                            "profile": ref.binding.model_dump(mode="json"),
                        }
                    ).encode()
                ).hexdigest()
                after = None
                expiry = datetime.now(UTC).timestamp() + self._cursor_ttl
                if request.cursor:
                    fields = decode_cursor(
                        request.cursor,
                        expected_generation_id=gen.generation_id,
                        expected_project_id=request.project_id,
                        expected_architecture_version_id=request.architecture_version_id,
                        expected_query_hash=query_hash,
                        secret=self._cursor_secret,
                    )
                    state = fields.get("state")
                    if not isinstance(state, dict) or not isinstance(
                        state.get("pit"), str
                    ):
                        raise SearchCursorInvalidError()
                    pit_id = state["pit"]
                    after = state.get("after")
                    if not isinstance(after, list) or not after:
                        raise SearchCursorInvalidError()
                    expiry = fields["exp"]
                    try:
                        pin_id = UUID(state["pin"])
                    except (ValueError, TypeError, KeyError) as exc:
                        raise SearchCursorInvalidError() from exc
                    pin = self._repo.require_read_pin(pin_id, gen.generation_id, pit_id)
                else:
                    pit_id = self._backend.open_pit(
                        manifest.index_name, self._cursor_ttl
                    )
                    pin_id = self._repo.acquire_read_pin(
                        generation_id=gen.generation_id,
                        pit_id=pit_id,
                        ttl_seconds=self._cursor_ttl,
                    ).pin_id
                    pin = self._repo.require_read_pin(pin_id, gen.generation_id, pit_id)
                rows, total, pit_id = self._backend.search_page(
                    manifest.index_name,
                    pit_id=pit_id,
                    scope=ref.scope,
                    generation_id=str(gen.generation_id),
                    index_uuid=manifest.index_uuid,
                    query=request.q,
                    document_kinds=(
                        tuple(k.value for k in request.document_kinds)
                        if request.document_kinds
                        else None
                    ),
                    entity_kinds=request.entity_kinds,
                    statuses=request.statuses,
                    size=request.limit + 1,
                    after=after,
                )
                pin.pit_id = pit_id  # Elasticsearch may rotate PIT handles.
                self._repo._session.flush()
                hits = []
                for rec in rows[: request.limit]:
                    if (
                        stored_record_digest(rec, ref.scope)
                        != rec.get("record_semantic_digest")
                        or rec.get("storage_key")
                        != compute_storage_key(
                            c1_version=C1_CONTRACT_VERSION,
                            knowledge_key=rec["knowledge_key"],
                            generation_id=gen.generation_id,
                        )
                        or rec.get("knowledge_key")
                        != compute_knowledge_key(
                            c1_version=C1_CONTRACT_VERSION,
                            project_id=ref.scope.project_id,
                            architecture_version_id=ref.scope.architecture_version_id,
                            document_kind=KnowledgeDocumentKind(rec["document_kind"]),
                            canonical_reference=rec["canonical_reference"],
                        )
                    ):
                        raise SearchIntegrityError("Search record integrity mismatch")
                    if any(
                        rec.get(key) != value
                        for key, value in {
                            "project_id": str(ref.scope.project_id),
                            "architecture_version_id": str(
                                ref.scope.architecture_version_id
                            ),
                            "generation_id": str(gen.generation_id),
                            "index_uuid": manifest.index_uuid,
                            "repository_id": str(ref.scope.repository_id),
                            "analysis_id": str(ref.scope.analysis_id),
                            "snapshot_id": str(ref.scope.snapshot_id),
                        }.items()
                    ):
                        raise SearchIntegrityError(
                            "Returned search record scope mismatch"
                        )
                    hits.append(
                        SearchHit(
                            knowledge_key=rec["knowledge_key"],
                            document_kind=KnowledgeDocumentKind(rec["document_kind"]),
                            canonical_reference=rec["canonical_reference"],
                            title=rec["title"],
                            kind=rec.get("kind"),
                            status=rec.get("status"),
                            source_logical_id=rec.get("source_logical_id"),
                            target_logical_id=rec.get("target_logical_id"),
                            evidence_ids=tuple(rec.get("evidence_ids") or ()),
                            source_reference=(
                                SourceReferenceDescriptor.model_validate_json(
                                    json.dumps(rec["source_reference"])
                                )
                                if rec.get("source_reference")
                                else None
                            ),
                            rank_tier=rec["_rank_tier"],
                            score=rec["_score"],
                            scope=ref.scope,
                        )
                    )
                if monotonic() >= deadline:
                    raise SearchDeadlineExceededError()
                if self._backend.inspect_index(manifest.index_name) != physical:
                    raise SearchIntegrityError(
                        "Search physical identity changed during read"
                    )
                self._repo.read_deadline(deadline)
                current = self._repo.get_active_generation(
                    project_id=request.project_id,
                    architecture_version_id=request.architecture_version_id,
                )
                if (
                    gen is None
                    or current is None
                    or current.generation_id != gen.generation_id
                ):
                    raise SearchGenerationChangedError()
                has_more = len(rows) > request.limit
                next_cursor = None
                if has_more:
                    next_cursor = encode_cursor(
                        generation_id=gen.generation_id,
                        project_id=request.project_id,
                        architecture_version_id=request.architecture_version_id,
                        query_hash=query_hash,
                        secret=self._cursor_secret,
                        ttl_seconds=expiry - datetime.now(UTC).timestamp(),
                        state={
                            "pit": pit_id,
                            "after": rows[request.limit - 1]["_sort"],
                            "pin": str(pin_id),
                        },
                    )
                page = SearchPage(
                    scope=ref.scope,
                    generation_id=gen.generation_id,
                    index_uuid=manifest.index_uuid,
                    items=tuple(hits),
                    total_hits=total,
                    has_more=has_more,
                    next_cursor=next_cursor,
                )
            keep_open = has_more
            return page
        except DeliveryContractError as exc:
            raise SearchIntegrityError(
                "Search accepted metadata integrity failure"
            ) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise SearchIntegrityError("Malformed accepted search data") from exc
        except SQLAlchemyError as exc:
            if getattr(getattr(exc, "orig", None), "sqlstate", None) in {
                "57014",
                "55P03",
            }:
                raise SearchDeadlineExceededError() from exc
            raise SearchBackendUnavailableError("Search metadata unavailable") from exc
        finally:
            succeeded = sys.exc_info()[0] is None
            if not keep_open:
                if pit_id is not None:
                    self._backend.close_pit(pit_id)
                if pin_id is not None:
                    self._repo.release_read_pin(pin_id)
            if succeeded:
                # Includes result mapping and PIT/pin cleanup, not just HTTP.
                self._repo.read_deadline(deadline)
                current = self._repo.get_active_generation(
                    project_id=request.project_id,
                    architecture_version_id=request.architecture_version_id,
                )
                if (
                    gen is None
                    or current is None
                    or current.generation_id != gen.generation_id
                ):
                    raise SearchGenerationChangedError()
                if monotonic() >= deadline:
                    raise SearchDeadlineExceededError()
