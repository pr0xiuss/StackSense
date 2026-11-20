"""Bounded stateless, signed C2 keysets. Tokens never confer authorization."""

import base64
import hashlib
import hmac
import re
from datetime import UTC, datetime
from time import time
from typing import Literal
from uuid import UUID

from pydantic import field_serializer

from backend.platform.delivery.contracts import DiagramTemplate
from backend.platform.diagrams.contracts import ClosedRecord, H, N
from backend.platform.diagrams.model import canonical_bytes, load_json


class CursorKey(ClosedRecord):
    accepted_at: datetime | None
    id: UUID

    @field_serializer("accepted_at")
    def utc(self, value: datetime | None) -> str | None:
        return (
            value.astimezone(UTC)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
            if value
            else None
        )


class DiagramCursor(ClosedRecord):
    v: Literal[1] = 1
    kid: str
    operation: Literal["history", "members"]
    actor_id: UUID
    project_id: UUID
    version_id: UUID
    template: DiagramTemplate
    resource_id: UUID
    generation_id: UUID
    semantic_digest: H
    request_digest: H
    high_water: CursorKey | None
    after: CursorKey
    issued_at: N
    expires_at: N
    mode: Literal["active", "exact"]


class CursorSigner:
    def __init__(self, key_id: str, secret: str, ttl: int = 600) -> None:
        if (
            not 1 <= len(key_id.encode()) <= 64
            or len(secret.encode()) < 32
            or not 1 <= ttl <= 600
        ):
            raise ValueError("diagram_runtime_unavailable")
        self.key_id, self.secret, self.ttl = key_id, secret.encode(), ttl

    @staticmethod
    def _encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    @classmethod
    def _decode(cls, value: str) -> bytes:
        if re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
            raise ValueError("diagram_cursor_invalid")
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        if cls._encode(raw) != value:
            raise ValueError("diagram_cursor_invalid")
        return raw

    def issue(self, cursor: DiagramCursor) -> str:
        raw = cursor.to_bytes()
        signature = hmac.digest(
            self.secret, b"ss.diagram.cursor.1\0" + raw, hashlib.sha256
        )
        result = self._encode(raw) + "." + self._encode(signature)
        if len(result) > 4096:
            raise ValueError("diagram_limit_exceeded")
        return result

    def read(self, token: str) -> DiagramCursor:
        try:
            if len(token.encode()) > 4096:
                raise ValueError()
            a, b = token.split(".")
            raw, signature = self._decode(a), self._decode(b)
            expected = hmac.digest(
                self.secret, b"ss.diagram.cursor.1\0" + raw, hashlib.sha256
            )
            if not hmac.compare_digest(signature, expected):
                raise ValueError()
            value = DiagramCursor.model_validate_json(
                canonical_bytes(load_json(raw, max_bytes=4096))
            )
            if (
                value.kid != self.key_id
                or value.issued_at > int(time())
                or not 0 < value.expires_at - value.issued_at <= self.ttl
            ):
                raise ValueError()
        except (ValueError, TypeError, UnicodeError) as exc:
            raise ValueError("diagram_cursor_invalid") from exc
        if int(time()) >= value.expires_at:
            raise ValueError("diagram_cursor_expired")
        return value
