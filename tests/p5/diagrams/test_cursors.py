"""Signed continuation integrity; no cursor is an authorization credential."""

from time import time
from uuid import uuid4

import pytest

from backend.platform.delivery.contracts import DiagramTemplate
from backend.platform.diagrams.cursors import CursorKey, CursorSigner, DiagramCursor


def token(signer, **changes):
    values = dict(
        kid=signer.key_id,
        operation="members",
        actor_id=uuid4(),
        project_id=uuid4(),
        version_id=uuid4(),
        template=DiagramTemplate.OVERVIEW,
        resource_id=uuid4(),
        generation_id=uuid4(),
        semantic_digest="a" * 64,
        request_digest="b" * 64,
        high_water=None,
        after=CursorKey(accepted_at=None, id=uuid4()),
        issued_at=int(time()),
        expires_at=int(time()) + 600,
        mode="exact",
    )
    values.update(changes)
    return signer.issue(DiagramCursor(**values))


def test_signed_closed_round_trip_and_expiry(monkeypatch):
    signer = CursorSigner("key-1", "secret" * 8)
    value = token(signer)
    decoded = signer.read(value)
    assert decoded.generation_id and len(value) < 4096
    monkeypatch.setattr(
        "backend.platform.diagrams.cursors.time", lambda: decoded.expires_at
    )
    with pytest.raises(ValueError, match="diagram_cursor_expired"):
        signer.read(value)


@pytest.mark.parametrize(
    "change",
    [
        lambda t: t + "=",
        lambda t: t[:-1] + ("A" if t[-1] != "A" else "B"),
        lambda t: "x." + t.split(".")[1],
        lambda t: "x" * 4097,
        lambda t: t + ".x",
    ],
)
def test_malformed_or_forged_tokens_never_parse_as_valid(change):
    signer = CursorSigner("key-1", "secret" * 8)
    with pytest.raises(ValueError, match="diagram_cursor_invalid"):
        signer.read(change(token(signer)))


def test_wrong_secret_and_key_rotation_fail_closed():
    first = CursorSigner("key-1", "secret" * 8)
    value = token(first)
    for other in [
        CursorSigner("key-2", "secret" * 8),
        CursorSigner("key-1", "different" * 8),
    ]:
        with pytest.raises(ValueError, match="diagram_cursor_invalid"):
            other.read(value)
