"""Shared read protocol for generated delivery artifacts.

Producers specialize this protocol for their exact member types.
Callers receive verified read handles and never direct storage paths.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from backend.platform.delivery.contracts import ArtifactReference, VersionScope

MemberT = TypeVar("MemberT", contravariant=True)


class VerifiedArtifactHandle(Protocol):
    """Reader-owned bounded handle; close must release its durable read pin."""

    def read(self, size: int) -> bytes: ...

    def close(self) -> None: ...


class GeneratedArtifactStore(Protocol[MemberT]):
    """Shared read protocol for immutable generated artifact stores."""

    def open_exact(
        self,
        scope: VersionScope,
        reference: ArtifactReference,
        member: MemberT,
    ) -> VerifiedArtifactHandle: ...
