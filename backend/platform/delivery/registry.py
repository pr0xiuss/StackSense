"""Fixed, immutable exact-profile registry; no dynamic module imports."""

from dataclasses import dataclass
from types import MappingProxyType

from backend.platform.delivery.contracts import (
    DeliveryContractError,
    HandlerProfile,
    PreparedOutput,
    WorkExecutionContext,
    WorkHandler,
)
from backend.platform.delivery.publication import ProducerPublicationFactory


class HandlerUnavailable(DeliveryContractError):
    """Do not claim or consume an execution when capability is unavailable."""


@dataclass(frozen=True, slots=True)
class HandlerRegistration:
    binding: HandlerProfile
    handler: WorkHandler
    publication_factory: ProducerPublicationFactory

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding", HandlerProfile.model_validate(self.binding))
        if not callable(getattr(self.handler, "execute", None)) or not callable(
            self.publication_factory
        ):
            raise DeliveryContractError("invalid handler/publication registration")


class WorkHandlerRegistry:
    def __init__(self, registrations: tuple[HandlerRegistration, ...] = ()) -> None:
        entries: dict[HandlerProfile, HandlerRegistration] = {}
        for item in registrations:
            if item.binding in entries:
                raise DeliveryContractError("duplicate delivery handler profile")
            entries[item.binding] = item
        self._entries = MappingProxyType(entries)

    def resolve(self, binding: HandlerProfile) -> HandlerRegistration:
        binding = HandlerProfile.model_validate(binding)
        registration = self._entries.get(binding)
        if registration is None:
            raise HandlerUnavailable("handler unavailable for pinned profile")
        return registration

    def execute(self, context: WorkExecutionContext) -> PreparedOutput:
        """No claim/publication here; worker orchestration belongs to B2."""
        context = WorkExecutionContext.model_validate(context)
        registration = self.resolve(context.attempt.work.binding)
        context.control.checkpoint()
        prepared = PreparedOutput.model_validate(registration.handler.execute(context))
        context.control.checkpoint()
        prepared.require_binding(context.attempt)
        return prepared

    @property
    def profiles(self) -> tuple[HandlerProfile, ...]:
        return tuple(
            sorted(
                (item.binding for item in self._entries.values()),
                key=lambda b: (
                    b.slot.kind,
                    b.slot.template or "",
                    b.profile.model_dump_json(),
                ),
            )
        )
