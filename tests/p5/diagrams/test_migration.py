"""Migration DDL must not replay unrelated application-metadata listeners."""

import importlib

from sqlalchemy import create_mock_engine

from backend.platform.diagrams.persistence import DIAGRAM_TABLES
from backend.platform.projects.infra.access_model import ProjectAccessModel
from backend.platform.projects.infra.base import Base


def test_upgrade_emits_only_diagram_ddl_with_platform_models_loaded(monkeypatch):
    migration = importlib.import_module(
        "backend.infra.migrations.versions.7d4a6c2e910b_create_diagram_artifacts"
    )
    assert ProjectAccessModel.__table__ is Base.metadata.tables["project_access"]
    original_tables = dict(Base.metadata.tables)
    statements = []

    def execute(statement, *args, **kwargs):
        statements.append(str(statement.compile(dialect=connection.dialect)))

    connection = create_mock_engine("postgresql+psycopg://", execute)
    monkeypatch.setattr(connection, "scalar", lambda statement: "public", raising=False)
    monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
    guards = []
    monkeypatch.setattr(
        migration, "install_guards", lambda bind, schema: guards.append((bind, schema))
    )

    migration.upgrade()

    ddl = "\n".join(statements)
    assert "CREATE TYPE" not in ddl
    assert "project_role" not in ddl
    assert "project_access" not in ddl
    assert ddl.count("CREATE TABLE") == 3
    for table in DIAGRAM_TABLES:
        assert f"CREATE TABLE {table.name}" in ddl
    assert "fk_diagram_active_generation" in ddl
    assert "FOREIGN KEY" in ddl
    assert guards == [(connection, "public")]
    assert dict(Base.metadata.tables) == original_tables
    assert all(table.metadata is Base.metadata for table in DIAGRAM_TABLES)
