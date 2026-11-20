"""OS-neutral private sealing wire values. These are not acceptance proofs."""

from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, model_validator

from backend.platform.delivery.contracts import AttemptIdentity
from backend.platform.diagrams.contracts import ClosedRecord, H, MemberDescriptor, N


class SealRequest(ClosedRecord):
    protocol: Literal[1]
    attempt: AttemptIdentity
    generation_id: UUID
    artifact_id: UUID
    members: tuple[MemberDescriptor, ...]
    manifest_sha256: H
    manifest_size: N

    @model_validator(mode="after")
    def member_set(self) -> Self:
        if tuple(m.member for m in self.members) != (
            "layout",
            "members",
            "spec",
            "svg",
        ):
            raise ValueError("diagram_integrity_error")
        return self


class SealProof(ClosedRecord):
    verification_version: Literal["1.0.0"]
    manifest_sha256: H
    member_set_digest: H
    physical_object_id: str
    sealed_at: AwareDatetime
