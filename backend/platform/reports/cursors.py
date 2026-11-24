"""Bounded stateless, signed C4 pagination keysets.

Tokens never confer authorization. Every page reauthorizes project,
version, report, and actor access before returning results.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from datetime import UTC, datetime
from time import time
from typing import Literal
from uuid import UUID

from pydantic import field_serializer

from backend.platform.reports.contracts import FrozenReportModel


class ReportCursorKey(FrozenReportModel):
    """Sort key tuple for keyset pagination."""

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


class ReportCursor(FrozenReportModel):
    """Signed, tamper-proof pagination cursor for report history."""

    v: Literal[1] = 1
    kid: str
    operation: Literal["collection", "generations"]
    actor_id: UUID
    project_id: UUID
    version_id: UUID
    report_id: UUID | None = None
    after: ReportCursorKey
    high_water: ReportCursorKey | None = None
    profile: str | None = None
    page_size: int | None = None
    issued_at: int
    expires_at: int


class ReportCursorSigner:
    """Signs and verifies tamper-proof pagination tokens using HMAC-SHA256."""

    def __init__(self, key_id: str, secret: str, ttl: int = 600) -> None:
        if (
            not 1 <= len(key_id.encode()) <= 64
            or len(secret.encode()) < 32
            or not 1 <= ttl <= 600
        ):
            raise ValueError("report_runtime_unavailable")
        self.key_id = key_id
        self.secret = secret.encode()
        self.ttl = ttl

    @staticmethod
    def _encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    @classmethod
    def _decode(cls, value: str) -> bytes:
        if re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
            raise ValueError("report_cursor_invalid")
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        if cls._encode(raw) != value:
            raise ValueError("report_cursor_invalid")
        return raw

    def issue(self, cursor: ReportCursor) -> str:
        raw = cursor.to_bytes()
        signature = hmac.digest(
            self.secret, b"ss.report.cursor.1\0" + raw, hashlib.sha256
        )
        result = self._encode(raw) + "." + self._encode(signature)
        if len(result) > 4096:
            raise ValueError("report_limit_exceeded")
        return result

    def read(self, token: str) -> ReportCursor:
        try:
            if len(token.encode()) > 4096:
                raise ValueError()
            parts = token.split(".")
            if len(parts) != 2:
                raise ValueError()
            raw, signature = self._decode(parts[0]), self._decode(parts[1])
            expected = hmac.digest(
                self.secret, b"ss.report.cursor.1\0" + raw, hashlib.sha256
            )
            if not hmac.compare_digest(signature, expected):
                raise ValueError()
            value = ReportCursor.from_bytes(raw, max_bytes=4096)
            now = int(time())
            if (
                value.kid != self.key_id
                or value.issued_at > now
                or not 0 < value.expires_at - value.issued_at <= self.ttl
            ):
                raise ValueError()
        except (ValueError, TypeError, UnicodeError) as exc:
            raise ValueError("report_cursor_invalid") from exc
        if int(time()) >= value.expires_at:
            raise ValueError("report_cursor_expired")
        return value


__all__ = [
    "ReportCursor",
    "ReportCursorKey",
    "ReportCursorSigner",
]
