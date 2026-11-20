"""Real public-port scan gate; explicit isolated PostgreSQL only, no private reads.

Run in a fresh pytest process with -s to retain JSON measurements. Trial envelopes
are not production policy. A failed required-success case requires escalation.
"""

import json
import os
import platform
from dataclasses import replace
from time import perf_counter
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.platform.analysis.architecture.model import (
    build_entity_logical_id,
    semantic_signature,
)
from backend.platform.analysis.architecture.persistence import (
    SqlAlchemyArchitectureRepository,
)
from backend.platform.analysis.architecture.service import ArchitectureQueryService
from backend.platform.knowledge.retrieval import KnowledgeQueryService
from backend.platform.knowledge.retrieval_adapters import CanonicalReadAdapter
from backend.platform.knowledge.retrieval_configuration import RetrievalPolicy
from backend.platform.knowledge.retrieval_contracts import (
    KnowledgeQueryRequest,
    ResolutionState,
    RetrievalDeadlineExceededError,
    RetrievalOperation,
    RetrievalPrincipal,
    SubjectSelector,
)
from backend.platform.projects.infra.base import Base
from tests.p3.analysis.test_m4_persistence import _analysis, _document, _validated
from tests.p5.benchmarks.test_retrieval_capacity import current_rss_mib
from tests.p5.knowledge.test_real_services import search_engine as search_engine


@pytest.mark.parametrize("size", [300, 3000, 25000])
def test_real_canonical_resolution_gate(search_engine, size, capsys):
    if os.environ.get("M3_CANONICAL_MEASUREMENT") != "1":
        pytest.skip("Explicit M3_CANONICAL_MEASUREMENT=1 for measured scan gate")
    Base.metadata.create_all(search_engine)
    base = _document()
    entity = base.entities[0]
    entities = tuple(
        replace(
            entity,
            logical_id=build_entity_logical_id(
                project_id=base.project_id,
                repository_id=base.repository_id,
                kind=entity.kind,
                namespace_parts=entity.namespace,
                anchor_parts=(f"node-{i:06d}",),
            ),
            name=f"Node{i:06d}",
            semantic_signature=semantic_signature({"node": i}),
        )
        for i in range(size)
    )
    document = replace(
        base,
        content_digest="",
        entities=entities,
        relationships=(),
        unresolved_relationships=(),
        conflicts=(),
        completeness=replace(
            base.completeness,
            source_entities=size,
            source_relationships=0,
            source_unresolved_references=0,
            source_conflicts=0,
            architecture_entities=size,
            architecture_relationships=0,
            architecture_unresolved_relationships=0,
            architecture_conflicts=0,
        ),
    )
    with Session(search_engine) as session:
        _analysis(session, document)
        repo = SqlAlchemyArchitectureRepository(session)
        repo.reserve_version(document)
        repo.mark_validating(document.architecture_version_id, document.analysis_id)
        repo.publish(_validated(document))
        session.commit()
    # Explicit experimental envelope: five seconds, complete canonical scan,
    # bounded 100-row pages, no search/graph and no retained full-model cache.
    policy = RetrievalPolicy(
        canonical_max_rows_per_collection=size,
        max_source_calls=size // 100 + 10,
        max_chain_work_units=size + 1000,
        total_deadline_seconds=5.0,
        finalization_reserve_seconds=0.5,
    )
    measurements = []
    for repeat in range(2):
        for label, index in (
            ("early", 0),
            ("middle", size // 2),
            ("late", size - 1),
            ("missing", None),
        ):
            with Session(search_engine) as session:
                service = KnowledgeQueryService(
                    CanonicalReadAdapter(
                        ArchitectureQueryService(
                            SqlAlchemyArchitectureRepository(session)
                        )
                    ),
                    policy=policy,
                    cursor_secret_key="isolated-canonical-gate-secret-32bytes",
                )
                before = current_rss_mib()
                started = perf_counter()
                failure = None
                try:
                    result = service.query(
                        KnowledgeQueryRequest(
                            project_id=document.project_id,
                            architecture_version_id=document.architecture_version_id,
                            operation=RetrievalOperation.LOOKUP,
                            subject=SubjectSelector(
                                selector_type="entity_name",
                                name=(
                                    f"Node{index:06d}"
                                    if index is not None
                                    else "Absent"
                                ),
                            ),
                        ),
                        principal=RetrievalPrincipal(
                            actor_id=uuid4(),
                            project_id=document.project_id,
                            role="VIEWER",
                        ),
                    )
                except RetrievalDeadlineExceededError:
                    failure = "retrieval_deadline_exceeded"
                elapsed = perf_counter() - started
                expected = (
                    ResolutionState.RESOLVED
                    if index is not None
                    else ResolutionState.NOT_FOUND
                )
                if failure is None:
                    assert result.resolved_subject.state == expected
                    assert result.resolved_subject.scan_complete
                    assert elapsed < policy.total_deadline_seconds
                measurements.append(
                    {
                        "case": label,
                        "repeat": repeat,
                        "seconds": round(elapsed, 4),
                        "rss_before_mib": before,
                        "rss_after_mib": current_rss_mib(),
                        "failure": failure,
                    }
                )
    with capsys.disabled():
        print(
            json.dumps(
                {
                    "canonical_gate": size,
                    "python": platform.python_version(),
                    "policy": policy.model_dump(mode="json"),
                    "measurements": measurements,
                },
                sort_keys=True,
            )
        )
    assert not any(
        m["failure"] for m in measurements
    ), "Required-success canonical scan gate failed; upstream change control required"
