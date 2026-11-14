"""P4-Q1 cursor codec, fingerprinting, and cryptographic validation.

This module implements the HMAC-SHA256 Base64URL pagination cursor contract
for Phase 4 Module 3 (Graph Query and Exploration API), adhering to the
tamper-proof, generation-bound pagination invariants specified in Section 7D.E.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from backend.platform.graph.query_contracts import (
    GraphCursorExpiredError,
    GraphCursorInvalidError,
    GraphCursorScopeMismatchError,
    GraphGenerationChangedError,
    GraphReadScope,
)

CURSOR_CONTRACT_VERSION: Final[str] = "1"
DEFAULT_CURSOR_TTL_SECONDS: Final[int] = 900  # 15 minutes
MAX_CURSOR_ENCODED_BYTES: Final[int] = 2048
MIN_CURSOR_SECRET_BYTES: Final[int] = 32


@dataclass(frozen=True, slots=True)
class GraphCursorPayload:
    """Decoded and validated pagination cursor payload."""

    version: str
    issued_at: int
    expires_at: int
    project_id: UUID
    architecture_version_id: UUID
    generation_id: UUID
    operation: str
    fingerprint: str
    position: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to a serializable dictionary."""
        return {
            "version": self.version,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "project_id": str(self.project_id),
            "architecture_version_id": str(self.architecture_version_id),
            "generation_id": str(self.generation_id),
            "operation": self.operation,
            "fingerprint": self.fingerprint,
            "position": self.position,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphCursorPayload:
        """Construct payload from a dictionary, validating required fields."""
        try:
            version = str(data["version"])
            issued_at = int(data["issued_at"])
            expires_at = int(data["expires_at"])
            project_id = UUID(str(data["project_id"]))
            architecture_version_id = UUID(str(data["architecture_version_id"]))
            generation_id = UUID(str(data["generation_id"]))
            operation = str(data["operation"])
            fingerprint = str(data["fingerprint"])
            position = dict(data.get("position") or {})
        except (KeyError, ValueError, TypeError) as exc:
            raise GraphCursorInvalidError(
                "Cursor payload contains invalid or missing fields"
            ) from exc

        return cls(
            version=version,
            issued_at=issued_at,
            expires_at=expires_at,
            project_id=project_id,
            architecture_version_id=architecture_version_id,
            generation_id=generation_id,
            operation=operation,
            fingerprint=fingerprint,
            position=position,
        )


def _b64url_encode(data: bytes) -> str:
    """Encode bytes to Base64URL string without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    """Decode Base64URL string without padding to bytes."""
    rem = len(s) % 4
    if rem > 0:
        s += "=" * (4 - rem)
    try:
        return base64.urlsafe_b64decode(s.encode("ascii"))
    except Exception as exc:
        raise GraphCursorInvalidError("Invalid Base64URL encoding") from exc


def _canonical_json(data: Any) -> str:
    """Serialize data to byte-deterministic canonical JSON."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _normalize_param_value(val: Any) -> Any:
    """Normalize parameter value for canonical fingerprint computation."""
    if isinstance(val, UUID):
        return str(val)
    if hasattr(val, "value"):  # Enum or StrEnum
        return str(val.value)
    if isinstance(val, (list, tuple, set, frozenset)):
        # Normalize elements recursively and sort if collection was unordered
        normalized_items = [_normalize_param_value(item) for item in val]
        if isinstance(val, (set, frozenset)):
            return sorted(normalized_items, key=lambda x: str(x))
        return normalized_items
    if isinstance(val, dict):
        return {str(k): _normalize_param_value(v) for k, v in sorted(val.items())}
    if val is None or isinstance(val, (int, float, str, bool)):
        return val
    return str(val)


def compute_query_fingerprint(params: dict[str, Any]) -> str:
    """Compute SHA-256 fingerprint over canonical JSON of query parameters."""
    normalized = {str(k): _normalize_param_value(v) for k, v in sorted(params.items())}
    canonical = _canonical_json(normalized)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def encode_cursor(
    *,
    scope: GraphReadScope,
    operation: str,
    fingerprint: str,
    position: dict[str, Any],
    secret_key: str,
    ttl_seconds: int = DEFAULT_CURSOR_TTL_SECONDS,
    now: datetime | None = None,
) -> str:
    """Generate an opaque HMAC-SHA256 signed Base64URL cursor.

    Format: base64url(canonical-json-payload).base64url(hmac)
    """
    if not secret_key:
        raise ValueError("Cursor secret key must not be empty")

    now_ts = int(now.timestamp()) if now else int(time.time())
    expires_ts = now_ts + ttl_seconds

    payload = GraphCursorPayload(
        version=CURSOR_CONTRACT_VERSION,
        issued_at=now_ts,
        expires_at=expires_ts,
        project_id=scope.project_id,
        architecture_version_id=scope.architecture_version_id,
        generation_id=scope.generation_id,
        operation=operation,
        fingerprint=fingerprint,
        position=position,
    )

    canonical_payload_json = _canonical_json(payload.to_dict())
    payload_b64 = _b64url_encode(canonical_payload_json.encode("utf-8"))

    mac = hmac.new(
        secret_key.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    sig_b64 = _b64url_encode(mac)

    cursor_str = f"{payload_b64}.{sig_b64}"
    if len(cursor_str.encode("ascii")) > MAX_CURSOR_ENCODED_BYTES:
        raise GraphCursorInvalidError("Generated cursor exceeds maximum length")

    return cursor_str


def decode_cursor(
    cursor_str: str,
    secret_key: str,
) -> GraphCursorPayload:
    """Decode and verify HMAC signature of an opaque cursor without semantic checks.

    Fails closed with GraphCursorInvalidError if malformed or tampered.
    """
    if not secret_key:
        raise ValueError("Cursor secret key must not be empty")

    if not cursor_str or len(cursor_str) > MAX_CURSOR_ENCODED_BYTES:
        raise GraphCursorInvalidError("Pagination cursor is malformed or too large")

    parts = cursor_str.split(".")
    if len(parts) != 2:
        raise GraphCursorInvalidError("Pagination cursor format is invalid")

    payload_b64, sig_b64 = parts[0], parts[1]

    # Verify signature first before parsing payload content
    expected_mac = hmac.new(
        secret_key.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    expected_sig_b64 = _b64url_encode(expected_mac)
    # Compare the canonical Base64URL representation rather than decoded bytes.
    # Non-canonical encodings can decode to the same bytes when unused trailing
    # bits differ and must still be rejected as cursor tampering.
    if not hmac.compare_digest(expected_sig_b64, sig_b64):
        raise GraphCursorInvalidError("Pagination cursor signature verification failed")

    # Decode and parse payload JSON
    try:
        payload_bytes = _b64url_decode(payload_b64)
        payload_dict = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        raise GraphCursorInvalidError(
            "Pagination cursor payload is unreadable"
        ) from exc

    if not isinstance(payload_dict, dict):
        raise GraphCursorInvalidError("Pagination cursor payload must be a JSON object")

    payload = GraphCursorPayload.from_dict(payload_dict)

    if payload.version != CURSOR_CONTRACT_VERSION:
        raise GraphCursorInvalidError(
            f"Unsupported cursor contract version '{payload.version}'"
        )

    return payload


def validate_cursor(
    cursor_str: str,
    *,
    secret_key: str,
    expected_scope: GraphReadScope,
    expected_operation: str,
    expected_fingerprint: str,
    current_time_epoch: int | None = None,
) -> GraphCursorPayload:
    """Verify cryptographic authenticity, scope, active generation, and TTL.

    This implements the pagination invariants in Section 7D.E:
    - Tamper or formatting errors fail closed (GraphCursorInvalidError).
    - Expiration fails closed (GraphCursorExpiredError).
    - Scope or fingerprint mismatches fail closed (GraphCursorScopeMismatchError).
    - Active generation changes fail closed (GraphGenerationChangedError).
    """
    payload = decode_cursor(cursor_str, secret_key)

    # 1. Verify expiration
    now_epoch = (
        current_time_epoch if current_time_epoch is not None else int(time.time())
    )
    if now_epoch >= payload.expires_at:
        raise GraphCursorExpiredError(
            "Pagination cursor has expired; please restart the query"
        )

    # 2. Verify project scope
    if payload.project_id != expected_scope.project_id:
        raise GraphCursorScopeMismatchError(
            "Cursor project does not match authorized request scope"
        )

    # 3. Verify architecture version scope
    if payload.architecture_version_id != expected_scope.architecture_version_id:
        raise GraphCursorScopeMismatchError(
            "Cursor architecture version does not match request scope"
        )

    # 4. Verify operation type
    if payload.operation != expected_operation:
        raise GraphCursorScopeMismatchError(
            f"Cursor operation '{payload.operation}' does not match "
            f"expected operation '{expected_operation}'"
        )

    # 5. Verify query parameter fingerprint
    if payload.fingerprint != expected_fingerprint:
        raise GraphCursorScopeMismatchError(
            "Cursor parameters do not match current query configuration"
        )

    # 6. Verify active generation binding (M3 invariant: never silently restart)
    if payload.generation_id != expected_scope.generation_id:
        raise GraphGenerationChangedError(
            f"Active projection generation changed from {payload.generation_id} "
            f"to {expected_scope.generation_id}; please restart query"
        )

    return payload


__all__ = [
    "CURSOR_CONTRACT_VERSION",
    "DEFAULT_CURSOR_TTL_SECONDS",
    "MAX_CURSOR_ENCODED_BYTES",
    "MIN_CURSOR_SECRET_BYTES",
    "GraphCursorPayload",
    "compute_query_fingerprint",
    "decode_cursor",
    "encode_cursor",
    "validate_cursor",
]
