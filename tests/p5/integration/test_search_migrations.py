"""Real PostgreSQL M2 migration round-trip, independent of ORM create_all."""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect

from backend.platform.knowledge.persistence import SEARCH_TABLES


def test_search_migration_upgrade_constraints_and_downgrade(delivery_engine):
    revision = importlib.import_module(
        "backend.infra.migrations.versions.8b395e61f204_create_search_projection"
    )
    schema = delivery_engine.get_execution_options()["schema_translate_map"][None]
    with delivery_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            revision.upgrade()
            inspector = inspect(connection)
            assert {table.name for table in SEARCH_TABLES} <= set(
                inspector.get_table_names(schema=schema)
            )
            assert "attempt_identity" in {
                column["name"]
                for column in inspector.get_columns("search_generations", schema=schema)
            }
            assert any(
                check["name"] == "ck_search_generation_state"
                for check in inspector.get_check_constraints(
                    "search_generations", schema=schema
                )
            )
            assert any(
                index["name"] == "ix_search_read_pin_expiry"
                for index in inspector.get_indexes("search_read_pins", schema=schema)
            )
            revision.downgrade()
            assert not {table.name for table in SEARCH_TABLES} & set(
                inspect(connection).get_table_names(schema=schema)
            )
