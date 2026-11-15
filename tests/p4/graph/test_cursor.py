"""Unit tests for P4-Q1 cursor codec, fingerprinting, and cryptographic validation."""

import time
from uuid import UUID, uuid4

import pytest

from backend.platform.graph.cursor import (
    CURSOR_CONTRACT_VERSION,
    DEFAULT_CURSOR_TTL_SECONDS,
    MAX_CURSOR_ENCODED_BYTES,
    compute_query_fingerprint,
    decode_cursor,
    encode_cursor,
    validate_cursor,
)
from backend.platform.graph.model import ProjectionCounts
from backend.platform.graph.query_contracts import (
    GraphCursorExpiredError,
    GraphCursorInvalidError,
    GraphCursorScopeMismatchError,
    GraphGenerationChangedError,
    GraphReadScope,
    GraphRelationshipKind,
    TraversalDirection,
)

SAMPLE_SECRET = "test-secret-at-least-32-bytes-long-for-hmac-sha256"
OTHER_SECRET = "another-completely-different-secret-32-bytes-long"


def _make_scope(
    project_id: UUID | None = None,
    architecture_version_id: UUID | None = None,
    generation_id: UUID | None = None,
) -> GraphReadScope:
    return GraphReadScope(
        project_id=project_id or uuid4(),
        architecture_version_id=architecture_version_id or uuid4(),
        generation_id=generation_id or uuid4(),
        resource_state="COMPLETED",
        graph_schema_version="1.0.0",
        projector_version="1.0.0",
        counts=ProjectionCounts(10, 20, 30, 0, 0),
    )


def test_cursor_encode_decode_round_trip() -> None:
    scope = _make_scope()
    fingerprint = compute_query_fingerprint({"op": "window", "limit": 50})
    position = {"node_key": "proj-key-1", "edge_key": "proj-rel-2"}

    cursor_str = encode_cursor(
        scope=scope,
        operation="window",
        fingerprint=fingerprint,
        position=position,
        secret_key=SAMPLE_SECRET,
        ttl_seconds=900,
    )

    assert isinstance(cursor_str, str)
    assert "." in cursor_str
    assert "=" not in cursor_str  # Padding omitted
    assert len(cursor_str.split(".")) == 2

    payload = decode_cursor(cursor_str, SAMPLE_SECRET)
    assert payload.version == CURSOR_CONTRACT_VERSION
    assert payload.project_id == scope.project_id
    assert payload.architecture_version_id == scope.architecture_version_id
    assert payload.generation_id == scope.generation_id
    assert payload.operation == "window"
    assert payload.fingerprint == fingerprint
    assert payload.position == position
    assert payload.expires_at == payload.issued_at + 900


def test_tampered_payload_or_signature_rejected() -> None:
    scope = _make_scope()
    fingerprint = compute_query_fingerprint({"op": "window"})
    cursor_str = encode_cursor(
        scope=scope,
        operation="window",
        fingerprint=fingerprint,
        position={"k": "v"},
        secret_key=SAMPLE_SECRET,
    )

    payload_b64, sig_b64 = cursor_str.split(".")

    # Tamper payload
    tampered_payload = "a" + payload_b64[1:]
    with pytest.raises(GraphCursorInvalidError):
        decode_cursor(f"{tampered_payload}.{sig_b64}", SAMPLE_SECRET)

    # Tamper signature
    tampered_sig = sig_b64[:-1] + ("A" if sig_b64[-1] != "A" else "B")
    with pytest.raises(GraphCursorInvalidError):
        decode_cursor(f"{payload_b64}.{tampered_sig}", SAMPLE_SECRET)

    # Wrong secret
    with pytest.raises(GraphCursorInvalidError):
        decode_cursor(cursor_str, OTHER_SECRET)


def test_malformed_and_oversized_cursors() -> None:
    with pytest.raises(GraphCursorInvalidError):
        decode_cursor("", SAMPLE_SECRET)

    with pytest.raises(GraphCursorInvalidError):
        decode_cursor("no_dots_here", SAMPLE_SECRET)

    with pytest.raises(GraphCursorInvalidError):
        decode_cursor("a.b.c", SAMPLE_SECRET)

    # Oversized cursor > MAX_CURSOR_ENCODED_BYTES
    oversized = "a" * (MAX_CURSOR_ENCODED_BYTES + 1)
    with pytest.raises(GraphCursorInvalidError):
        decode_cursor(oversized, SAMPLE_SECRET)


def test_validate_cursor_success() -> None:
    scope = _make_scope()
    fingerprint = compute_query_fingerprint({"direction": "both", "depth": 2})
    position = {"depth": 1, "rel_key": "r1"}

    now_ts = int(time.time())
    cursor_str = encode_cursor(
        scope=scope,
        operation="neighborhood",
        fingerprint=fingerprint,
        position=position,
        secret_key=SAMPLE_SECRET,
        ttl_seconds=DEFAULT_CURSOR_TTL_SECONDS,
    )

    payload = validate_cursor(
        cursor_str,
        secret_key=SAMPLE_SECRET,
        expected_scope=scope,
        expected_operation="neighborhood",
        expected_fingerprint=fingerprint,
        current_time_epoch=now_ts,
    )
    assert payload.position == position


def test_validate_cursor_expired() -> None:
    scope = _make_scope()
    fingerprint = compute_query_fingerprint({})
    now_ts = int(time.time())

    cursor_str = encode_cursor(
        scope=scope,
        operation="window",
        fingerprint=fingerprint,
        position={},
        secret_key=SAMPLE_SECRET,
        ttl_seconds=60,
    )

    with pytest.raises(GraphCursorExpiredError, match="expired"):
        validate_cursor(
            cursor_str,
            secret_key=SAMPLE_SECRET,
            expected_scope=scope,
            expected_operation="window",
            expected_fingerprint=fingerprint,
            current_time_epoch=now_ts + 61,
        )


def test_validate_cursor_scope_mismatch() -> None:
    scope1 = _make_scope()
    fingerprint1 = compute_query_fingerprint({"page": 1})
    fingerprint2 = compute_query_fingerprint({"page": 2})

    cursor_str = encode_cursor(
        scope=scope1,
        operation="window",
        fingerprint=fingerprint1,
        position={},
        secret_key=SAMPLE_SECRET,
    )

    # 1. Project mismatch
    diff_project_scope = GraphReadScope(
        project_id=uuid4(),
        architecture_version_id=scope1.architecture_version_id,
        generation_id=scope1.generation_id,
        resource_state="COMPLETED",
        graph_schema_version="1.0.0",
        projector_version="1.0.0",
        counts=scope1.counts,
    )
    with pytest.raises(GraphCursorScopeMismatchError, match="project"):
        validate_cursor(
            cursor_str,
            secret_key=SAMPLE_SECRET,
            expected_scope=diff_project_scope,
            expected_operation="window",
            expected_fingerprint=fingerprint1,
        )

    # 2. Version mismatch
    diff_version_scope = GraphReadScope(
        project_id=scope1.project_id,
        architecture_version_id=uuid4(),
        generation_id=scope1.generation_id,
        resource_state="COMPLETED",
        graph_schema_version="1.0.0",
        projector_version="1.0.0",
        counts=scope1.counts,
    )
    with pytest.raises(GraphCursorScopeMismatchError, match="version"):
        validate_cursor(
            cursor_str,
            secret_key=SAMPLE_SECRET,
            expected_scope=diff_version_scope,
            expected_operation="window",
            expected_fingerprint=fingerprint1,
        )

    # 3. Operation mismatch
    with pytest.raises(GraphCursorScopeMismatchError, match="operation"):
        validate_cursor(
            cursor_str,
            secret_key=SAMPLE_SECRET,
            expected_scope=scope1,
            expected_operation="neighborhood",
            expected_fingerprint=fingerprint1,
        )

    # 4. Fingerprint mismatch
    with pytest.raises(GraphCursorScopeMismatchError, match="parameters"):
        validate_cursor(
            cursor_str,
            secret_key=SAMPLE_SECRET,
            expected_scope=scope1,
            expected_operation="window",
            expected_fingerprint=fingerprint2,
        )


def test_validate_cursor_generation_changed() -> None:
    scope_g1 = _make_scope()
    fingerprint = compute_query_fingerprint({"op": "window"})

    cursor_str = encode_cursor(
        scope=scope_g1,
        operation="window",
        fingerprint=fingerprint,
        position={},
        secret_key=SAMPLE_SECRET,
    )

    # New generation G2 in PostgreSQL
    scope_g2 = GraphReadScope(
        project_id=scope_g1.project_id,
        architecture_version_id=scope_g1.architecture_version_id,
        generation_id=uuid4(),  # Different active generation
        resource_state="COMPLETED",
        graph_schema_version="1.0.0",
        projector_version="1.0.0",
        counts=scope_g1.counts,
    )

    with pytest.raises(GraphGenerationChangedError, match="generation changed"):
        validate_cursor(
            cursor_str,
            secret_key=SAMPLE_SECRET,
            expected_scope=scope_g2,
            expected_operation="window",
            expected_fingerprint=fingerprint,
        )


def test_compute_query_fingerprint_normalization() -> None:
    entity_id = uuid4()
    params_a = {
        "operation": "neighborhood",
        "entity_id": entity_id,
        "direction": TraversalDirection.BOTH,
        "depth": 2,
        "kinds": [GraphRelationshipKind.CALLS, GraphRelationshipKind.IMPORTS],
    }
    params_b = {
        "depth": 2,
        "kinds": [GraphRelationshipKind.CALLS, GraphRelationshipKind.IMPORTS],
        "entity_id": str(entity_id),
        "direction": "both",
        "operation": "neighborhood",
    }

    # Different key ordering and str vs enum / UUID normalize to same fingerprint
    fp_a = compute_query_fingerprint(params_a)
    fp_b = compute_query_fingerprint(params_b)
    assert fp_a == fp_b

    # Changing a value changes the fingerprint
    params_c = dict(params_a)
    params_c["depth"] = 3
    assert compute_query_fingerprint(params_c) != fp_a
