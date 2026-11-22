"""Canonical C4 serialization, hashing algorithms, and resource identity derivation."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel

from backend.platform.delivery.contracts import (
    HandlerProfile,
    VersionScope,
)
from backend.platform.delivery.contracts import (
    fingerprint as c0_fingerprint,
)
from backend.platform.reports.contracts import (
    C4_VERSION,
    FrozenReportModel,
    ReportContractError,
    ReportSpec,
)


def _canonicalize(value: Any) -> Any:
    if isinstance(value, FrozenReportModel):
        return _canonicalize(value.model_dump(mode="python"))
    if isinstance(value, BaseModel):
        return _canonicalize(value.model_dump(mode="python"))
    if isinstance(value, UUID):
        return str(value).lower()
    if isinstance(value, datetime):
        utc_dt = value.astimezone(UTC)
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, str):
        value.encode("utf-8", errors="strict")
        return value
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        if abs(value) > (2**53 - 1):
            raise ReportContractError("Integer outside safe JSON 53-bit range")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ReportContractError("Non-finite floating point numbers not permitted")
        return value
    if isinstance(value, Mapping):
        sorted_keys = sorted(str(k) for k in value.keys())
        return {k: _canonicalize(value[k]) for k in sorted_keys}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    raise ReportContractError(
        f"Unsupported canonical serialization type: {type(value)}"
    )


def c4_canonical_json(value: Any) -> str:
    """Canonical C4 JSON encoder: compact separators, UTF-8, sorted keys."""
    canonical = _canonicalize(value)
    return json.dumps(
        canonical,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def c4_canonical_bytes(value: Any) -> bytes:
    """Return UTF-8 encoded canonical JSON bytes."""
    return c4_canonical_json(value).encode("utf-8")


def c4_digest(tag: str, value: Any) -> str:
    """Tagged SHA-256 digest of canonical data."""
    envelope = [tag, C4_VERSION, value]
    return hashlib.sha256(c4_canonical_bytes(envelope)).hexdigest()


def c4_report_resource_id(
    scope: VersionScope,
    binding: HandlerProfile,
    input_fingerprint: str,
) -> UUID:
    """Derive deterministic report resource UUID per §15.5.3."""
    c0_hash = c0_fingerprint(
        "report.resource",
        {
            "scope": scope.semantic_identity(),
            "binding": binding,
            "input_fingerprint": input_fingerprint,
        },
    )
    return uuid5(NAMESPACE_URL, f"stacksense:report-resource:1:{c0_hash}")


def c4_binding_digest(binding: HandlerProfile) -> str:
    """Compute deterministic SHA256 digest over HandlerProfile."""
    return hashlib.sha256(
        c4_canonical_bytes(binding.model_dump(mode="python"))
    ).hexdigest()


def c4_report_spec_digest(spec: ReportSpec) -> str:
    """Compute report_spec_digest over specification without report_spec_digest."""
    raw = spec.model_dump(mode="python", exclude={"report_spec_digest"})
    return c4_digest("ss.report.spec", raw)


def c4_render_fingerprint(
    report_spec_digest: str,
    renderer_profile_digest: str,
    asset_hashes: tuple[tuple[str, str], ...],
    limits_digest: str,
    page_placement_digest: str,
) -> str:
    """Compute render_fingerprint over spec digest, profile, assets, and placement."""
    payload = [
        "ss.report.render",
        C4_VERSION,
        report_spec_digest,
        renderer_profile_digest,
        sorted(asset_hashes),
        limits_digest,
        page_placement_digest,
    ]
    return hashlib.sha256(c4_canonical_bytes(payload)).hexdigest()


def c4_source_snapshot_digest(
    version_id: UUID,
    analysis_id: UUID,
    canonical_digest: str,
    captured_data: Mapping[str, Any],
    receipt_ids: tuple[UUID, ...],
    asset_hashes: tuple[str, ...],
) -> str:
    """Compute source_snapshot_digest over captured DTOs and diagram receipts."""
    payload = {
        "architecture_version_id": str(version_id),
        "analysis_id": str(analysis_id),
        "canonical_digest": canonical_digest,
        "captured_data": captured_data,
        "receipt_ids": [str(r) for r in sorted(receipt_ids)],
        "asset_hashes": sorted(asset_hashes),
    }
    return c4_digest("ss.report.snapshot", payload)
