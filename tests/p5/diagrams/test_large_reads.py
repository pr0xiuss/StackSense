"""Real PG/M1/application-store prepared reads at the approved scene profiles."""

# ruff: noqa: F811
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
from time import monotonic
from uuid import uuid4

import pytest

from backend.platform.delivery.contracts import DiagramTemplate
from backend.platform.delivery.publication import PublicationUnitOfWork
from backend.platform.diagrams.artifacts import LocalGeneratedArtifactStore
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import PreparedDiagram
from backend.platform.diagrams.repository import (
    DatabaseReadAuthority,
    DiagramPublicationPort,
)
from backend.platform.diagrams.service import DiagramReader
from tests.p5.diagrams.test_builders import build, data, entity, relation
from tests.p5.diagrams.test_database import diagram_db  # noqa: F401
from tests.p5.diagrams.test_publication import candidate


@pytest.mark.skipif(
    os.environ.get("M4_B1_ESSENTIAL_PROOFS") != "1",
    reason="opt-in real labelled large artifact read experiment",
)
@pytest.mark.parametrize("count", [150, 500])
def test_large_exact_reader_under_unchanged_read_deadline(
    diagram_db, tmp_path, monkeypatch, count
):
    engine, _, _ = diagram_db
    path = (
        Path(__file__).resolve().parents[2]
        / f"fixtures/p5/diagrams/b4_stress{count}.json.gz.b64"
    )
    value = PreparedDiagram.from_bytes(
        gzip.decompress(base64.b64decode(path.read_bytes())),
        max_bytes=128 * 1024 * 1024,
    )
    limits = (
        DiagramLimits(max_nodes=150, max_edges=600, max_groups=64, max_depth=3)
        if count == 150
        else DiagramLimits()
    )
    entities = tuple(entity(i + 1) for i in range(count))
    relations = tuple(
        relation(i + 1, entities[i], entities[i + 1])
        for i in range(count - 1)
        if i % 5 != 4
    )
    built = build(data(entities, relations), DiagramTemplate.DEPENDENCY, limits=limits)
    # C2 set arrays canonicalize at serialization, not by tuple object order.
    assert built.spec.to_bytes() == value.spec.to_bytes()
    lease, output, _, _ = candidate(
        engine,
        DiagramTemplate.DEPENDENCY,
        tmp_path,
        monkeypatch,
        prepared_value=value,
        catalog=built.catalog,
    )
    with PublicationUnitOfWork(engine, timeout_seconds=5, lock_timeout_ms=1000) as uow:
        receipt = uow.complete(lease, output, DiagramPublicationPort)
        uow.commit()
    reader = DiagramReader(
        LocalGeneratedArtifactStore(
            DatabaseReadAuthority(engine, limits, actor_id=None), limits
        ),
        limits,
    )
    started = monotonic()
    result = reader.read_exact(
        receipt.accepted.reference.scope, receipt.accepted.reference
    )
    elapsed = monotonic() - started
    assert len(result.spec.nodes) == count
    print(
        "M4_B4_EXACT_READ_MEASUREMENT "
        + json.dumps(
            {
                "count": count,
                "seconds": elapsed,
                "configured_read_seconds": limits.read_seconds,
                "scope": (
                    "real PG/M1/application-sealed accepted read; "
                    "not production OS certification"
                ),
            }
        )
    )
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.api.v1 import diagrams as api
    from backend.platform.analysis.application.dependencies import (
        DelegatedRequestContext,
        get_delegated_context,
    )
    from backend.platform.diagrams.cursors import CursorSigner
    from backend.platform.diagrams.repository import DiagramQueryRepository
    from backend.platform.diagrams.service import DiagramService
    from tests.p5.diagrams.test_api import record_for

    actor = uuid4()
    authority = DatabaseReadAuthority(engine, limits, actor_id=actor, purpose="api")
    service = DiagramService(
        DiagramQueryRepository(engine),
        DiagramReader(LocalGeneratedArtifactStore(authority, limits), limits),
        limits,
        CursorSigner("large-read-test", "isolated-large-read-cursor-secret"),
        None,
        None,
    )
    app = FastAPI()
    app.include_router(api.router, prefix="/api/v1")
    reference = receipt.accepted.reference
    record = record_for(result)
    app.dependency_overrides[get_delegated_context] = lambda: DelegatedRequestContext(
        actor, "VIEWER", project_id=record.project_id
    )
    app.dependency_overrides[api.get_diagram_version_reader] = (
        lambda: lambda version, project, deadline: record
    )
    app.dependency_overrides[api.service_factory] = lambda: lambda: service
    path = (
        f"/api/v1/architecture-versions/{record.id}/diagrams/dependency_map"
        f"/generations/{reference.generation_id}"
    )
    with TestClient(app) as client:
        for member, params in [
            ("layout", {}),
            ("export", {"format": "json"}),
            ("export", {"format": "svg"}),
        ]:
            started = monotonic()
            response = client.get(
                path + "/" + member,
                params={"project_id": str(record.project_id), **params},
            )
            elapsed = monotonic() - started
            assert response.status_code == 200, response.text[:1000]
            assert response.headers["content-length"] == str(len(response.content))
            expected = (
                "sha-256=:"
                + base64.b64encode(hashlib.sha256(response.content).digest()).decode()
                + ":"
            )
            assert response.headers["content-digest"] == expected
            print(
                "M4_B4_HTTP_READ_MEASUREMENT "
                + json.dumps(
                    {
                        "count": count,
                        "member": member,
                        "format": params.get("format"),
                        "seconds": elapsed,
                        "bytes": len(response.content),
                        "scope": (
                            "real M1/PG/store/HTTP with delegated/header fixtures; "
                            "not deployment certification"
                        ),
                    }
                )
            )
