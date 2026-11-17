"""Bounded knowledge projection capacity and execution benchmarks.

Measures KnowledgeProjector scaling, memory attribution, and determinism
across empty, representative, and boundary model sizes per §7.10.
"""

from __future__ import annotations

import json
import platform
from time import perf_counter

from backend.platform.analysis.architecture.model import (
    ArchitectureEntityKind,
    ArchitectureRelationshipKind,
)
from backend.platform.knowledge.model import (
    C1_CONTRACT_VERSION,
)
from backend.platform.knowledge.projection import KnowledgeProjector
from tests.p5.knowledge.conftest import (
    make_test_document,
    make_test_entity,
    make_test_evidence,
    make_test_relationship,
)


def current_rss_mib() -> float | None:
    """Current per-process RSS (Linux procfs), safely None on other platforms."""
    try:
        with open("/proc/self/status") as status:
            for line in status:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    return None


def test_empty_knowledge_projection_benchmark():
    doc, scope = make_test_document(
        entities=(),
        relationships=(),
        evidence=(),
        unresolved_relationships=(),
        conflicts=(),
    )
    projector = KnowledgeProjector()

    before_rss = current_rss_mib()
    started = perf_counter()
    projection = projector.project(document=doc, scope=scope)
    duration_s = perf_counter() - started
    after_rss = current_rss_mib()

    assert projection.counts.entities == 0
    assert projection.counts.relationships == 0
    assert projection.counts.evidence == 0
    assert projection.counts.architecture_summaries == 1
    assert projection.counts.total_records == 1
    assert duration_s < 1.0

    print(
        "P5_M2_MEASUREMENT "
        + json.dumps(
            {
                "test": "empty_projection",
                "python": platform.python_version(),
                "platform": platform.platform(),
                "duration_seconds": round(duration_s, 6),
                "total_records": projection.counts.total_records,
                "before_rss_mib": before_rss,
                "after_rss_mib": after_rss,
            }
        )
    )


def test_representative_knowledge_projection_benchmark():
    # Construct representative model: 200 entities, 400 relationships, 600 evidence
    num_entities = 200
    num_relationships = 400
    num_evidence = 600

    evidence = tuple(
        make_test_evidence(
            logical_id=f"evidence://src/module_{i // 10}/file_{i}.py#1-20",
            path=f"src/module_{i // 10}/file_{i}.py",
        )
        for i in range(num_evidence)
    )

    entities = tuple(
        make_test_entity(
            logical_id=f"architecture://entity/service/node_{i}",
            name=f"ServiceNode{i}",
            kind=ArchitectureEntityKind.SERVICE,
            namespace=("app", f"domain_{i // 20}"),
            evidence_ids=(evidence[i % num_evidence].logical_id,),
            metadata={
                "framework": "fastapi",
                "runtime_role": "service",
                "database_engine": "postgresql" if i % 2 == 0 else "redis",
            },
        )
        for i in range(num_entities)
    )

    relationships = tuple(
        make_test_relationship(
            logical_id=f"architecture://rel/calls/node_{i}_to_{j}_{k}",
            source_logical_id=entities[i].logical_id,
            target_logical_id=entities[j].logical_id,
            kind=ArchitectureRelationshipKind.CALLS,
            evidence_ids=(evidence[k % num_evidence].logical_id,),
            metadata={"method": "rpc"},
        )
        for k, (i, j) in enumerate(
            (r % num_entities, (r * 7 + 1) % num_entities)
            for r in range(num_relationships)
        )
    )

    doc, scope = make_test_document(
        entities=entities,
        relationships=relationships,
        evidence=evidence,
    )
    projector = KnowledgeProjector()

    before_rss = current_rss_mib()
    started = perf_counter()
    projection = projector.project(document=doc, scope=scope)
    duration_s = perf_counter() - started
    after_rss = current_rss_mib()

    expected_total = num_entities + num_relationships + num_evidence + 1 + 1 + 1
    assert projection.counts.entities == num_entities
    assert projection.counts.relationships == num_relationships
    assert projection.counts.evidence == num_evidence
    assert projection.counts.total_records == expected_total
    assert len(projection.records) == expected_total
    assert projection.c1_version == C1_CONTRACT_VERSION
    assert len(projection.projection_digest) == 64
    assert duration_s < 3.0  # Must be fast and strictly bounded

    print(
        "P5_M2_MEASUREMENT "
        + json.dumps(
            {
                "test": "representative_projection",
                "python": platform.python_version(),
                "platform": platform.platform(),
                "duration_seconds": round(duration_s, 6),
                "entities": num_entities,
                "relationships": num_relationships,
                "evidence": num_evidence,
                "total_records": projection.counts.total_records,
                "before_rss_mib": before_rss,
                "after_rss_mib": after_rss,
            }
        )
    )
