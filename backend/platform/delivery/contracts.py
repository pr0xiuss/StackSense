"""C0 delivery contract candidate. Freeze requires explicit owner review.

These immutable values carry identities, not source/spec bytes or credentials.
Storage sealing, authorization and database fencing require owner-module proof;
constructing a value is never proof that an artifact is committed or immutable.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal, Protocol, Self, runtime_checkable
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

C0_VERSION: Literal["1.0.0"] = "1.0.0"
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
# Contract identifiers, not operational payload/configuration/admission limits.
Token = Annotated[
    str, Field(min_length=1, max_length=256, pattern=r"^[a-zA-Z0-9_.:-]+$")
]
PositiveInt = Annotated[StrictInt, Field(gt=0)]
NonnegativeInt = Annotated[StrictInt, Field(ge=0)]


class DeliveryContractError(ValueError):
    """Safe contract mismatch; never include candidate contents in the message."""


class FrozenContract(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, revalidate_instances="always"
    )

    contract_version: Literal["1.0.0"] = C0_VERSION

    @field_validator("sealed", "admission_approved", mode="before", check_fields=False)
    @classmethod
    def literal_boolean(cls, value: object) -> object:
        # Pydantic Literal[True] otherwise accepts the integer 1, even in strict
        # models. Neither a seal claim nor fleet approval accepts coercion.
        if type(value) is not bool or value is not True:
            raise DeliveryContractError("an explicit true boolean is required")
        return value

    @field_validator("*", mode="after")
    @classmethod
    def valid_unicode(cls, value: object) -> object:
        if isinstance(value, str):
            value.encode("utf-8", errors="strict")
        return value


class WorkKind(StrEnum):
    SEARCH = "search_projection"
    DIAGRAM = "diagram"
    REPORT = "report"


class DiagramTemplate(StrEnum):
    OVERVIEW = "system_overview"
    COMPONENT = "component_architecture"
    DEPENDENCY = "dependency_map"
    DATA_FLOW = "data_flow"


class VersionScope(FrozenContract):
    project_id: UUID
    repository_id: UUID
    analysis_id: UUID
    snapshot_id: UUID
    architecture_version_id: UUID
    sequence_number: PositiveInt
    published_at: AwareDatetime
    canonical_digest: Digest
    source_contract_version: Literal["1.0.0"]
    analyzer_version: Token
    ir_schema_version: Token
    architecture_schema_version: Token
    # Frozen source fingerprints are opaque; copy, never reinterpret/rehash.
    configuration_fingerprint: Annotated[str, Field(min_length=1)]

    @field_validator("published_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    def semantic_identity(self) -> dict[str, object]:
        """Publication time is provenance, never a semantic fingerprint input."""
        return self.model_dump(mode="json", exclude={"published_at"})


class WorkSlot(FrozenContract):
    kind: WorkKind
    template: DiagramTemplate | Literal["architecture_analysis"] | None = None

    @model_validator(mode="after")
    def supported(self) -> Self:
        valid = (
            self.kind == WorkKind.SEARCH
            and self.template is None
            or self.kind == WorkKind.DIAGRAM
            and isinstance(self.template, DiagramTemplate)
            or self.kind == WorkKind.REPORT
            and self.template == "architecture_analysis"
        )
        if not valid:
            raise DeliveryContractError("unsupported delivery kind/template")
        return self


class ProducerProfile(FrozenContract):
    producer_id: Token
    producer_version: Token
    generator_version: Token
    output_schema_version: Token
    configuration_fingerprint: Digest


class HandlerProfile(FrozenContract):
    slot: WorkSlot
    profile: ProducerProfile


class DeliveryPolicy(FrozenContract):
    policy_version: Token
    execution_policy_fingerprint: Digest
    profiles: tuple[HandlerProfile, ...]
    required_templates: tuple[DiagramTemplate, ...] = tuple(DiagramTemplate)
    overview_policy: Literal["hold_until_ready_or_final_failure"] = (
        "hold_until_ready_or_final_failure"
    )
    report_type: Literal["architecture_analysis"] = "architecture_analysis"

    @model_validator(mode="after")
    def complete(self) -> Self:
        expected = {
            WorkSlot(kind=WorkKind.SEARCH),
            WorkSlot(kind=WorkKind.REPORT, template="architecture_analysis"),
        }
        expected.update(
            WorkSlot(kind=WorkKind.DIAGRAM, template=t) for t in DiagramTemplate
        )
        slots = [item.slot for item in self.profiles]
        if len(set(slots)) != len(slots) or set(slots) != expected:
            raise DeliveryContractError(
                "policy requires exactly six pinned slot profiles"
            )
        if len(self.required_templates) != 4 or set(self.required_templates) != set(
            DiagramTemplate
        ):
            raise DeliveryContractError("automatic report requires all four templates")
        object.__setattr__(
            self,
            "profiles",
            tuple(
                sorted(
                    self.profiles, key=lambda p: (p.slot.kind, p.slot.template or "")
                )
            ),
        )
        object.__setattr__(
            self, "required_templates", tuple(sorted(self.required_templates))
        )
        return self


def _canonical(value: object) -> object:
    if isinstance(value, FrozenContract):
        value = type(value).model_validate(value)
    if isinstance(value, VersionScope):
        return _canonical(value.semantic_identity())
    if isinstance(value, BaseModel):
        return _canonical(
            {
                name: getattr(value, name)
                for name, info in type(value).model_fields.items()
                if not info.exclude
            }
        )
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, StrEnum):
        return str(value)
    if isinstance(value, str):
        value.encode("utf-8", errors="strict")
        return value
    if value is None or type(value) in (bool, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise DeliveryContractError("canonical JSON keys must be strings")
        return {str(_canonical(key)): _canonical(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    raise DeliveryContractError("unsupported canonical JSON value")


def fingerprint(tag: str, value: object) -> str:
    """Tagged canonical JSON. Callers explicitly sort set-like collections."""
    if not tag:
        raise DeliveryContractError("fingerprint tag required")
    payload = _canonical({"contract": C0_VERSION, "type": tag, "value": value})
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def bundle_fingerprint(scope: VersionScope, policy: DeliveryPolicy) -> str:
    return fingerprint(
        "delivery.bundle", {"scope": scope.semantic_identity(), "policy": policy}
    )


def work_fingerprint(bundle_digest: str, binding: HandlerProfile) -> str:
    return fingerprint("delivery.work", {"bundle": bundle_digest, "binding": binding})


class WorkIdentity(FrozenContract):
    scope: VersionScope
    bundle_id: UUID
    work_id: UUID
    run_number: PositiveInt
    binding: HandlerProfile
    bundle_fingerprint: Digest
    input_fingerprint: Digest

    def run_fingerprint(self) -> str:
        return fingerprint(
            "delivery.run",
            {
                "bundle": self.bundle_id,
                "slot": self.binding.slot,
                "input": self.input_fingerprint,
                "run": self.run_number,
            },
        )


class AttemptIdentity(FrozenContract):
    work: WorkIdentity
    attempt_id: UUID
    ordinal: PositiveInt
    fence: PositiveInt
    dispatch_epoch: UUID
    candidate_id: UUID


class StopReason(StrEnum):
    STOP_REQUESTED = "execution_stop"
    OWNERSHIP_LOST = "ownership_lost"
    DEADLINE = "deadline_exceeded"


class ExecutionStopped(RuntimeError):
    def __init__(self, reason: StopReason) -> None:
        self.reason = reason
        super().__init__(reason.value)


@runtime_checkable
class ExecutionControl(Protocol):
    """Producer can observe/stop its execution, never mutate lifecycle/fences."""

    def checkpoint(self) -> None: ...

    def should_stop(self) -> bool: ...


class _CooperativeControl:
    def __init__(self, observe: Callable[[], StopReason | None]) -> None:
        self._observe = observe
        self._reason: StopReason | None = None

    def should_stop(self) -> bool:
        if self._reason is None:
            self._reason = self._observe()
        return self._reason is not None

    def checkpoint(self) -> None:
        if self.should_stop():
            assert self._reason is not None
            raise ExecutionStopped(self._reason)


def execution_control(observe: Callable[[], StopReason | None]) -> ExecutionControl:
    """M1 supplies liveness/deadline observations; no producer cancellation API."""
    return _CooperativeControl(observe)


class WorkExecutionContext(FrozenContract):
    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, arbitrary_types_allowed=True
    )
    attempt: AttemptIdentity
    deadline: AwareDatetime
    control: ExecutionControl = Field(exclude=True)
    prerequisites: BarrierReceipt | None = None

    @model_validator(mode="after")
    def exact_prerequisites(self) -> Self:
        if self.attempt.work.binding.slot.kind == WorkKind.REPORT:
            barrier, work = self.prerequisites, self.attempt.work
            if (
                barrier is None
                or barrier.scope != work.scope
                or barrier.report_profile != work.binding.profile
                or barrier.input_fingerprint() != work.input_fingerprint
                or any(
                    r.prepared.attempt.work.bundle_id != work.bundle_id
                    or r.prepared.attempt.work.bundle_fingerprint
                    != work.bundle_fingerprint
                    for r in barrier.diagrams
                )
            ):
                raise DeliveryContractError(
                    "report requires exact pinned prerequisites"
                )
        elif self.prerequisites is not None:
            raise DeliveryContractError(
                "only report execution consumes diagram prerequisites"
            )
        return self


class OutputDigests(FrozenContract):
    content: Digest
    spec: Digest | None = None
    layout: Digest | None = None


class CandidateSeal(FrozenContract):
    generation_id: UUID
    artifact_id: UUID
    size_bytes: NonnegativeInt
    digests: OutputDigests
    sealed: Literal[True]


class PreparedOutput(FrozenContract):
    attempt: AttemptIdentity
    candidate: CandidateSeal

    @model_validator(mode="after")
    def diagram_digests(self) -> Self:
        if self.attempt.work.binding.slot.kind == WorkKind.DIAGRAM and (
            self.candidate.digests.spec is None or self.candidate.digests.layout is None
        ):
            raise DeliveryContractError(
                "diagram candidate requires spec/layout digests"
            )
        return self

    def require_binding(self, expected: AttemptIdentity) -> None:
        validated = PreparedOutput.model_validate(self)
        expected = AttemptIdentity.model_validate(expected)
        if validated.attempt != expected:
            raise DeliveryContractError("prepared output ownership/profile mismatch")


class ArtifactReference(FrozenContract):
    scope: VersionScope
    binding: HandlerProfile
    input_fingerprint: Digest
    resource_id: UUID
    candidate_id: UUID
    generation_id: UUID
    artifact_id: UUID
    size_bytes: NonnegativeInt
    digests: OutputDigests
    sealed: Literal[True]

    @model_validator(mode="after")
    def diagram_digests(self) -> Self:
        if self.binding.slot.kind == WorkKind.DIAGRAM and (
            self.digests.spec is None or self.digests.layout is None
        ):
            raise DeliveryContractError(
                "diagram reference requires spec/layout digests"
            )
        return self


class AcceptedOutput(FrozenContract):
    reference: ArtifactReference

    def require_candidate(self, prepared: PreparedOutput) -> None:
        validated = AcceptedOutput.model_validate(self)
        prepared = PreparedOutput.model_validate(prepared)
        ref, work, seal = validated.reference, prepared.attempt.work, prepared.candidate
        if (
            ref.scope != work.scope
            or ref.binding != work.binding
            or ref.input_fingerprint != work.input_fingerprint
            or ref.candidate_id != prepared.attempt.candidate_id
            or ref.generation_id != seal.generation_id
            or ref.artifact_id != seal.artifact_id
            or ref.size_bytes != seal.size_bytes
            or ref.digests != seal.digests
        ):
            raise DeliveryContractError(
                "accepted reference does not match sealed candidate"
            )


class PublicationReceipt(FrozenContract):
    receipt_id: UUID
    prepared: PreparedOutput
    accepted: AcceptedOutput

    @model_validator(mode="after")
    def exact(self) -> Self:
        self.accepted.require_candidate(self.prepared)
        return self


class DependencyReceipt(FrozenContract):
    """Pinned prerequisite/release evidence; never itself proof of SQL commit."""

    scope: VersionScope
    prerequisite_work_id: UUID
    reason: Literal["prerequisite_ready", "overview_final_failure"]
    output: PublicationReceipt | None = None

    @model_validator(mode="after")
    def exact(self) -> Self:
        if self.reason == "prerequisite_ready":
            if (
                self.output is None
                or self.output.prepared.attempt.work.work_id
                != self.prerequisite_work_id
                or self.output.accepted.reference.scope != self.scope
            ):
                raise DeliveryContractError("dependency requires exact prerequisite")
        elif self.output is not None:
            raise DeliveryContractError("failed overview release cannot claim READY")
        return self


class BarrierReceipt(FrozenContract):
    scope: VersionScope
    report_profile: ProducerProfile
    diagrams: tuple[PublicationReceipt, ...]

    @model_validator(mode="after")
    def four_exact(self) -> Self:
        refs = [item.accepted.reference for item in self.diagrams]
        if len(refs) != 4 or {r.binding.slot.template for r in refs} != set(
            DiagramTemplate
        ):
            raise DeliveryContractError(
                "barrier requires four distinct diagram templates"
            )
        if any(
            r.scope != self.scope or r.binding.slot.kind != WorkKind.DIAGRAM
            for r in refs
        ):
            raise DeliveryContractError("barrier reference scope/kind mismatch")
        if len({item.prepared.attempt.work.bundle_id for item in self.diagrams}) != 1:
            raise DeliveryContractError("barrier cannot mix bundles")
        for identities in (
            [item.receipt_id for item in self.diagrams],
            [item.prepared.attempt.work.work_id for item in self.diagrams],
            [item.prepared.attempt.attempt_id for item in self.diagrams],
            [item.prepared.attempt.candidate_id for item in self.diagrams],
        ):
            if len(set(identities)) != 4:
                raise DeliveryContractError(
                    "barrier requires distinct acceptance identities"
                )
        if (
            len(
                {
                    item.prepared.attempt.work.bundle_fingerprint
                    for item in self.diagrams
                }
            )
            != 1
        ):
            raise DeliveryContractError("barrier cannot mix bundle policies")
        object.__setattr__(
            self,
            "diagrams",
            tuple(
                sorted(
                    self.diagrams,
                    key=lambda r: r.accepted.reference.binding.slot.template or "",
                )
            ),
        )
        return self

    def require_policy(self, policy: DeliveryPolicy, bundle_id: UUID) -> None:
        """Coordinator also validates committed READY via producer public ports."""
        validated = BarrierReceipt.model_validate(self)
        policy = DeliveryPolicy.model_validate(policy)
        expected = {p.slot: p.profile for p in policy.profiles}
        report = WorkSlot(kind=WorkKind.REPORT, template="architecture_analysis")
        if validated.report_profile != expected[report]:
            raise DeliveryContractError("barrier report profile mismatch")
        expected_bundle = bundle_fingerprint(validated.scope, policy)
        for item in validated.diagrams:
            work = item.prepared.attempt.work
            if (
                work.bundle_id != bundle_id
                or work.bundle_fingerprint != expected_bundle
                or work.binding.profile != expected[work.binding.slot]
                or work.input_fingerprint
                != work_fingerprint(expected_bundle, work.binding)
            ):
                raise DeliveryContractError("barrier prerequisite policy mismatch")

    def input_fingerprint(self) -> str:
        # Receipts contain no commit timestamps, lease tokens or correlation IDs.
        return fingerprint("delivery.report-prerequisites", self)


class DeliveryWorkPayload(FrozenContract):
    contract_version: Literal["1.0.0"]
    work_id: UUID
    bundle_id: UUID
    project_id: UUID
    architecture_version_id: UUID
    dispatch_epoch: UUID
    correlation_id: Token

    def require_work(self, work: WorkIdentity, dispatch_epoch: UUID) -> None:
        validated = DeliveryWorkPayload.model_validate(self)
        work = WorkIdentity.model_validate(work)
        if (
            validated.work_id,
            validated.bundle_id,
            validated.project_id,
            validated.architecture_version_id,
            validated.dispatch_epoch,
        ) != (
            work.work_id,
            work.bundle_id,
            work.scope.project_id,
            work.scope.architecture_version_id,
            dispatch_epoch,
        ):
            raise DeliveryContractError("worker payload scope/run/epoch mismatch")


class RetryClass(StrEnum):
    TRANSIENT = "transient"
    INTEGRITY = "integrity"
    CAPACITY = "capacity"
    PERMANENT = "permanent"


class DeliveryFailure(FrozenContract):
    code: Annotated[Token, Field(max_length=128)]
    retry_class: RetryClass
    source_capability: Token


class DeliveryExecutionFailure(RuntimeError):
    """Producer supplies a validated classification, never raw exception text."""

    def __init__(self, failure: DeliveryFailure) -> None:
        self.failure = DeliveryFailure.model_validate(failure)
        super().__init__(self.failure.code)


class WorkHandler(Protocol):
    def execute(self, context: WorkExecutionContext) -> PreparedOutput: ...


class AttemptRetirement(FrozenContract):
    """Trusted M1 read result, not a client-supplied cleanup authorization.

    Retirement is irreversible for this attempt UUID. It never proves that the
    producer's artifact is unreferenced, grace has elapsed, or deletion is safe.
    """

    attempt: AttemptIdentity
    outcome: Literal["COMPLETED", "FAILED", "EXPIRED", "CANCELLED"]
    ended_at: AwareDatetime
    publication: PublicationReceipt | None = None

    @model_validator(mode="after")
    def exact(self) -> Self:
        if self.outcome == "COMPLETED":
            if (
                self.publication is None
                or self.publication.prepared.attempt != self.attempt
            ):
                raise DeliveryContractError(
                    "completed retirement requires exact acceptance"
                )
        elif self.publication is not None:
            raise DeliveryContractError(
                "unpublished retirement cannot claim acceptance"
            )
        return self


class AttemptRetirementReader(Protocol):
    def read_retirement(self, attempt: AttemptIdentity) -> AttemptRetirement | None:
        """None for unknown/live/uncommitted attempts, including expired leases.

        Consumers must still serialize producer cleanup versus publication,
        reject accepted/pinned references, and enforce an approved grace period.
        """
        ...
