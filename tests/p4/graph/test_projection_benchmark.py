"""Reproducible reference workload for P4 projection-limit measurements."""

from __future__ import annotations

from dataclasses import replace
from time import perf_counter

from backend.platform.graph.projection import build_projection_plan
from tests.fixtures.p4.graph.fixtures import (
    DEFAULT_GENERATION_ID,
    make_completeness,
    make_entity,
    make_relationship,
    small_document,
)


def test_reference_projection_transform_measurement() -> None:
    """Measure a deterministic 2,500-node/5,000-edge transform workload."""
    entity_count = 2_500
    relationship_count = 5_000
    entities = tuple(
        make_entity(f"entity://benchmark/{index}", name=f"Service{index}")
        for index in range(entity_count)
    )
    relationships = tuple(
        make_relationship(
            f"relationship://benchmark/{index}",
            entities[index % entity_count].logical_id,
            entities[(index + 1) % entity_count].logical_id,
        )
        for index in range(relationship_count)
    )
    document = replace(
        small_document(),
        entities=entities,
        relationships=relationships,
        completeness=make_completeness(
            entities=entity_count,
            relationships=relationship_count,
            evidence=1,
        ),
        content_digest="",
    )

    started = perf_counter()
    plan = build_projection_plan(document, generation_id=DEFAULT_GENERATION_ID)
    elapsed = perf_counter() - started

    assert len(plan.nodes) == entity_count
    assert len(plan.relationships) == relationship_count
    print(
        "P4 projection reference workload: "
        f"{entity_count} nodes, {relationship_count} relationships, "
        f"{document.canonical_payload_size} source bytes, {elapsed:.4f}s transform"
    )
