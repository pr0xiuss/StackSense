"""Architectural boundary tests for Module 3 (Repository Domain & Registration)."""

from pathlib import Path


def test_repository_files_use_absolute_imports() -> None:
    """Ensure all files in backend/platform/repositories/ use absolute imports."""
    repo_root = Path("backend/platform/repositories")

    for file_path in repo_root.rglob("*.py"):
        lines = file_path.read_text().splitlines()
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            # Flag relative imports like 'from . import' or 'from ..foo import'
            if stripped.startswith("from .") or stripped.startswith("from .."):
                raise AssertionError(
                    f"Relative import found in {file_path}:{idx}: '{stripped}'. "
                    f"StackSense architecture mandates absolute imports."
                )


def test_repository_domain_is_pure_python() -> None:
    """Ensure Repository domain model has zero framework dependencies."""
    domain_file = Path("backend/platform/repositories/domain/repository.py")
    content = domain_file.read_text()

    forbidden_terms = [
        "fastapi",
        "pydantic",
        "sqlalchemy",
        "sqlmodel",
        "alembic",
    ]

    for term in forbidden_terms:
        assert (
            term not in content.lower()
        ), f"Forbidden framework dependency '{term}' found in {domain_file}"


def test_no_organization_layer_in_repositories() -> None:
    """Ensure no Organization models, columns, or references were introduced."""
    repo_root = Path("backend/platform/repositories")

    for file_path in repo_root.rglob("*.py"):
        content = file_path.read_text().lower()
        assert (
            "organization_id" not in content
        ), f"Forbidden 'organization_id' found in {file_path}"
        assert (
            "organization" not in content
        ), f"Forbidden 'organization' construct found in {file_path}"


def test_no_independent_repository_rbac() -> None:
    """Ensure repository authorization derives from ProjectAccess without repo RBAC."""
    repo_root = Path("backend/platform/repositories")

    for file_path in repo_root.rglob("*.py"):
        content = file_path.read_text().lower()
        assert (
            "repositoryrole" not in content
        ), f"Forbidden independent RepositoryRole found in {file_path}"
        assert (
            "repositoryaccess" not in content
        ), f"Forbidden independent RepositoryAccess found in {file_path}"
