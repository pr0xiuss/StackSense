"""Low-level copy/integrity tests; explicitly NOT separate-principal proofs."""

import hashlib
import os
import sys

import pytest

from backend.platform.diagrams.artifacts import DIRECTORY, _copy_member, _read_hash

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "POSIX directory file descriptors (dir_fd) and inode operations"
        " require Linux/POSIX"
    ),
)


def test_fresh_inode_is_not_the_stale_staging_inode(tmp_path):
    incoming, outgoing = tmp_path / "in", tmp_path / "out"
    incoming.mkdir()
    outgoing.mkdir()
    source = incoming / "spec.json"
    source.write_bytes(b"original")
    retained = source.open("r+b")
    a, b = os.open(incoming, DIRECTORY), os.open(outgoing, DIRECTORY)
    try:
        digest = hashlib.sha256(b"original").hexdigest()
        _copy_member(a, b, "spec.json", 8, digest)
        retained.write(b"corrupt!")
        retained.flush()
        assert (outgoing / "spec.json").read_bytes() == b"original"
        assert source.stat().st_ino != (outgoing / "spec.json").stat().st_ino
        assert _read_hash(b, "spec.json", 8, digest) == b"original"
        # This same-UID test proves only copy semantics, not worker exclusion.
    finally:
        retained.close()
        os.close(a)
        os.close(b)


@pytest.mark.parametrize("attack", ["symlink", "hardlink", "hash", "size"])
def test_copy_rejects_unsafe_sources(tmp_path, attack):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    item = source / "spec.json"
    item.write_bytes(b"original")
    if attack == "symlink":
        item.unlink()
        item.symlink_to(tmp_path / "foreign")
    if attack == "hardlink":
        os.link(item, source / "alias")
    a, b = os.open(source, DIRECTORY), os.open(target, DIRECTORY)
    try:
        with pytest.raises((OSError, ValueError)):
            _copy_member(
                a,
                b,
                "spec.json",
                9 if attack == "size" else 8,
                (
                    "0" * 64
                    if attack == "hash"
                    else hashlib.sha256(b"original").hexdigest()
                ),
            )
    finally:
        os.close(a)
        os.close(b)


def test_corruption_does_not_trust_unchanged_digest_labels(tmp_path):
    (tmp_path / "spec.json").write_bytes(b"corrupt!")
    fd = os.open(tmp_path, DIRECTORY)
    try:
        with pytest.raises(ValueError):
            _read_hash(fd, "spec.json", 8, hashlib.sha256(b"original").hexdigest())
    finally:
        os.close(fd)


def test_expired_read_hash_does_not_open_a_member(tmp_path):
    fd = os.open(tmp_path, DIRECTORY)
    try:
        with pytest.raises(TimeoutError):
            _read_hash(fd, "absent.json", 1, "a" * 64, deadline=0)
    finally:
        os.close(fd)


def test_unaccepted_read_rejected_before_any_store_access():
    from contextlib import contextmanager

    from backend.platform.diagrams.artifacts import LocalGeneratedArtifactStore
    from backend.platform.diagrams.configuration import DiagramLimits
    from tests.p5.diagrams.test_c2_consumers import prepared

    class Denied:
        @contextmanager
        def pinned(self, scope, reference):
            raise PermissionError("unaccepted fixture")
            yield

        def recheck(self, scope, reference):
            raise AssertionError("should not reach final read")

    p = prepared()
    with pytest.raises(PermissionError):
        LocalGeneratedArtifactStore(Denied(), DiagramLimits()).open_exact(
            p.descriptor.reference.scope, p.descriptor.reference, "spec"
        )


def test_exact_generation_reader_rehashes_bytes_and_releases_pin_on_corruption(
    tmp_path, monkeypatch
):
    from contextlib import contextmanager

    import backend.platform.diagrams.artifacts as module
    from backend.platform.diagrams.configuration import DiagramLimits
    from tests.p5.diagrams.test_c2_consumers import prepared

    p = prepared()
    root = tmp_path / "sealed" / str(p.descriptor.reference.generation_id)
    root.mkdir(parents=True)
    (root / "manifest.json").write_bytes(p.descriptor.manifest.to_bytes())
    (root / "spec.json").write_bytes(p.spec.to_bytes())

    class FixtureAuthority:
        count = 0

        @contextmanager
        def pinned(self, scope, reference):
            assert reference == p.descriptor.reference
            self.count += 1
            try:
                yield p.descriptor.manifest
            finally:
                self.count -= 1

        def recheck(self, scope, reference):
            assert self.count == 1

    monkeypatch.setattr(module, "STORE_ROOT", tmp_path)
    authority = FixtureAuthority()
    store = module.LocalGeneratedArtifactStore(authority, DiagramLimits())
    handle = store.open_exact(
        p.descriptor.reference.scope, p.descriptor.reference, "spec"
    )
    assert authority.count == 1
    try:
        assert handle.read(len(p.spec.to_bytes())) == p.spec.to_bytes()
        assert handle.read(1) == b""
        with pytest.raises(ValueError):
            handle.read(-1)
    finally:
        handle.close()
    assert authority.count == 0
    with pytest.raises(ValueError):
        handle.read(1)
    (root / "spec.json").write_bytes(b"X" * len(p.spec.to_bytes()))
    with pytest.raises(ValueError):
        store.open_exact(p.descriptor.reference.scope, p.descriptor.reference, "spec")
    assert authority.count == 0
    # Synthetic authority proves adapter binding/cleanup only, not durable pins
    # or physically separate users; those mandatory real proofs remain blocked.
