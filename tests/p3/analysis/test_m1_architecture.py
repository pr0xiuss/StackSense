"""Architectural boundary, pure-domain, and absolute-import tests for Module 1."""

from pathlib import Path

from backend.platform.analysis.domain.input import AnalysisArtifact


def test_analysis_files_use_absolute_imports() -> None:
    """Ensure all files in backend/platform/analysis use absolute imports."""
    analysis_root = Path("backend/platform/analysis")

    for file_path in analysis_root.rglob("*.py"):
        lines = file_path.read_text().splitlines()
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("from .") or stripped.startswith("from .."):
                raise AssertionError(
                    f"Relative import found in {file_path}:{idx}: '{stripped}'. "
                    f"StackSense architecture mandates absolute imports."
                )


def test_p3_analysis_tests_use_absolute_imports() -> None:
    """Ensure all test files in tests/p3/analysis use absolute imports."""
    tests_root = Path("tests/p3/analysis")

    for file_path in tests_root.rglob("*.py"):
        lines = file_path.read_text().splitlines()
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("from .") or stripped.startswith("from .."):
                raise AssertionError(
                    f"Relative import found in {file_path}:{idx}: '{stripped}'. "
                    f"StackSense architecture mandates absolute imports."
                )


def test_analysis_domain_is_pure_python() -> None:
    """Ensure Analysis domain models have zero framework or broker dependencies."""
    domain_root = Path("backend/platform/analysis/domain")

    forbidden_terms = [
        "fastapi",
        "pydantic",
        "sqlalchemy",
        "sqlmodel",
        "alembic",
        "celery",
        "kombu",
        "pika",
    ]

    for file_path in domain_root.rglob("*.py"):
        content = file_path.read_text().lower()
        for term in forbidden_terms:
            assert (
                f"import {term}" not in content and f"from {term}" not in content
            ), f"Forbidden framework dependency '{term}' found in {file_path}"


def test_no_downstream_module_leakage_in_m1() -> None:
    """Ensure M1 does not import or implement downstream modules (M2-M4).

    Change-Control (ACR-M2-001):
    When M1 was authored, backend/platform/analysis contained only M1 code.
    With M2 implementation introducing approved Tree-sitter parsers under
    backend/platform/analysis/syntax, this test is scoped to M1-owned packages
    (application, domain, infra, repositories) to preserve strict M1 isolation
    without incorrectly penalizing M2 for its own approved dependencies.
    """
    m1_dirs = [
        Path("backend/platform/analysis/application"),
        Path("backend/platform/analysis/domain"),
        Path("backend/platform/analysis/infra"),
        Path("backend/platform/analysis/repositories"),
    ]

    forbidden_packages = [
        "tree_sitter",
        "tree_sitter_languages",
        "backend.platform.architecture",
        "backend.platform.ir",
        "backend.platform.analysis.m2",
        "backend.platform.analysis.m3",
        "backend.platform.analysis.m4",
    ]

    for m1_dir in m1_dirs:
        for file_path in m1_dir.rglob("*.py"):
            content = file_path.read_text().lower()
            for term in forbidden_packages:
                assert (
                    term not in content
                ), f"Forbidden downstream leakage '{term}' found in {file_path}"


def test_storage_key_not_exposed_on_domain_analysis_artifact() -> None:
    """Ensure AnalysisArtifact does not expose internal storage_key across boundary."""
    fields = AnalysisArtifact.__annotations__.keys()
    assert "storage_key" not in fields
    assert "absolute_path" not in fields


def test_no_organization_layer_in_analysis() -> None:
    """Ensure Project is primary boundary and Organization is not introduced."""
    analysis_root = Path("backend/platform/analysis")

    for file_path in analysis_root.rglob("*.py"):
        content = file_path.read_text().lower()
        assert (
            "organization_id" not in content
        ), f"Forbidden 'organization_id' found in {file_path}"
        assert (
            "organization" not in content
        ), f"Forbidden 'organization' found in {file_path}"


def test_production_composition_never_reads_express_owned_postgres_tables() -> None:
    """Production API/worker composition must use the authorized Express API."""
    for path in (
        Path("backend/platform/analysis/application/dependencies.py"),
        Path("backend/worker/tasks.py"),
    ):
        content = path.read_text()
        for forbidden in (
            "SqlAlchemyRevisionRepository",
            "SqlAlchemyArtifactRepository",
            "LocalStorageService",
            "SqlAlchemyProjectRepository",
            "SqlAlchemyRepositoryRepository",
        ):
            assert (
                forbidden not in content
            ), f"Cross-database adapter in {path}: {forbidden}"
