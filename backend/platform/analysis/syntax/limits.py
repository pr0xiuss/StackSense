"""Approved resource limits for M2 generic syntax extraction."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MAX_FACTS_PER_ARTIFACT = 25_000
DEFAULT_MAX_FACTS_PER_ANALYSIS = 250_000
DEFAULT_MAX_SERIALIZED_F2_BYTES = 50 * 1024 * 1024


class FactLimitExceededError(Exception):
    """Raised before an incomplete fact set could escape an extractor."""


@dataclass
class FactAccumulator:
    """Collect facts atomically while enforcing the per-artifact ceiling."""

    max_facts: int = DEFAULT_MAX_FACTS_PER_ARTIFACT

    def __post_init__(self) -> None:
        if self.max_facts <= 0:
            raise ValueError("max_facts must be positive")
        self._facts: list[object] = []

    def add(self, fact: object) -> None:
        if len(self._facts) >= self.max_facts:
            raise FactLimitExceededError(
                f"Artifact exceeded the approved limit of {self.max_facts} facts"
            )
        self._facts.append(fact)

    @property
    def facts(self) -> tuple[object, ...]:
        return tuple(self._facts)
