"""Real isolated PostgreSQL migration exercise, never the application schema."""

# ruff: noqa: F811

import importlib
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from backend.platform.delivery.contracts import DiagramTemplate
from backend.platform.delivery.publication import PublicationUnitOfWork
from backend.platform.diagrams.repository import DiagramPublicationPort
from tests.p5.diagrams.test_database import diagram_db  # noqa: F401
from tests.p5.diagrams.test_publication import candidate


@pytest.mark.parametrize("accepted", [False, True])
def test_additive_migration_upgrade_and_safe_rollback(
    diagram_db, tmp_path, monkeypatch, accepted
):
    engine, _, _ = diagram_db
    schema = "p5_diagram_" + uuid4().hex
    migration = importlib.import_module(
        "backend.infra.migrations.versions.7d4a6c2e910b_create_diagram_artifacts"
    )
    assert migration.down_revision == "26c95d71b603"
    with engine.begin() as c:
        c.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    try:
        with isolated.begin() as c:
            c.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            with Operations.context(MigrationContext.configure(c)):
                migration.upgrade()
            assert set(inspect(c).get_table_names(schema=schema)) == {
                "diagram_resource",
                "diagram_generation",
                "diagram_read_pin",
            }
        if accepted:
            lease, output, _, _ = candidate(
                isolated, DiagramTemplate.OVERVIEW, tmp_path, monkeypatch
            )
            with PublicationUnitOfWork(
                isolated, timeout_seconds=5, lock_timeout_ms=1000
            ) as uow:
                uow.complete(lease, output, DiagramPublicationPort)
                uow.commit()
            with (
                pytest.raises(RuntimeError, match="prevent downgrade"),
                isolated.begin() as c,
            ):
                c.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                with Operations.context(MigrationContext.configure(c)):
                    migration.downgrade()
            with isolated.connect() as c:
                assert (
                    c.scalar(
                        text(f'SELECT count(*) FROM "{schema}".diagram_generation')
                    )
                    == 1
                )
        else:
            with isolated.begin() as c:
                c.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                with Operations.context(MigrationContext.configure(c)):
                    migration.downgrade()
                assert not inspect(c).get_table_names(schema=schema)
    finally:
        with engine.begin() as c:
            c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
