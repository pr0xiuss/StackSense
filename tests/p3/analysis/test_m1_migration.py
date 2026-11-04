"""Tests for Alembic migration definitions and metadata consistency."""

from backend.infra.migrations.versions import (
    c4b1897a0f12_create_analysis_lifecycle_tables as migration_module,
)
from backend.platform.projects.infra.base import Base


def test_migration_attributes() -> None:
    """Validate Alembic revision identifiers and dependencies."""
    assert migration_module.revision == "c4b1897a0f12"
    assert migration_module.down_revision == "9296ffc9a48c"
    assert callable(migration_module.upgrade)
    assert callable(migration_module.downgrade)


def test_metadata_contains_all_analysis_tables() -> None:
    """Verify that all 5 M1 tables are registered with SQLAlchemy Base.metadata."""
    table_names = Base.metadata.tables.keys()

    expected_tables = [
        "analyses",
        "analysis_jobs",
        "analysis_stages",
        "analysis_events",
        "analysis_diagnostics",
    ]

    for table_name in expected_tables:
        assert (
            table_name in table_names
        ), f"Table '{table_name}' missing from Base.metadata"


def test_analysis_table_schema() -> None:
    """Verify column definitions and constraints on analyses table."""
    table = Base.metadata.tables["analyses"]
    cols = table.columns.keys()

    expected_cols = [
        "id",
        "project_id",
        "repository_id",
        "snapshot_id",
        "status",
        "configuration",
        "completeness",
        "published_version_id",
        "error_code",
        "error_message",
        "idempotency_key",
        "version",
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
    ]
    for col in expected_cols:
        assert col in cols, f"Column '{col}' missing from analyses table"


def test_analysis_jobs_table_schema() -> None:
    """Verify column definitions on analysis_jobs table."""
    table = Base.metadata.tables["analysis_jobs"]
    cols = table.columns.keys()

    expected_cols = [
        "id",
        "analysis_id",
        "project_id",
        "status",
        "attempt",
        "max_attempts",
        "worker_id",
        "heartbeat_at",
        "started_at",
        "completed_at",
        "error_code",
        "error_message",
        "version",
        "created_at",
        "updated_at",
    ]
    for col in expected_cols:
        assert col in cols, f"Column '{col}' missing from analysis_jobs table"


def test_analysis_stages_table_schema() -> None:
    """Verify column definitions on analysis_stages table."""
    table = Base.metadata.tables["analysis_stages"]
    cols = table.columns.keys()

    expected_cols = [
        "id",
        "analysis_id",
        "job_id",
        "stage_name",
        "status",
        "stage_order",
        "is_mandatory",
        "processed_items",
        "total_items",
        "started_at",
        "completed_at",
        "error_code",
        "error_message",
        "version",
        "created_at",
        "updated_at",
    ]
    for col in expected_cols:
        assert col in cols, f"Column '{col}' missing from analysis_stages table"


def test_analysis_events_table_schema() -> None:
    """Verify column definitions on analysis_events table."""
    table = Base.metadata.tables["analysis_events"]
    cols = table.columns.keys()

    expected_cols = [
        "id",
        "analysis_id",
        "sequence_number",
        "event_type",
        "timestamp",
        "payload",
    ]
    for col in expected_cols:
        assert col in cols, f"Column '{col}' missing from analysis_events table"


def test_analysis_diagnostics_table_schema() -> None:
    """Verify column definitions on analysis_diagnostics table."""
    table = Base.metadata.tables["analysis_diagnostics"]
    cols = table.columns.keys()

    expected_cols = [
        "id",
        "analysis_id",
        "job_id",
        "stage",
        "code",
        "category",
        "severity",
        "scope",
        "message",
        "retryability",
        "details",
        "artifact_id",
        "artifact_path",
        "source_line",
        "source_column",
        "created_at",
    ]
    for col in expected_cols:
        assert col in cols, f"Column '{col}' missing from analysis_diagnostics table"
