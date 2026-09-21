"""Basic StackSense architecture validation."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"


def test_backend_uses_absolute_imports() -> None:
    """Backend Python modules must not contain relative imports."""
    python_files = BACKEND_ROOT.rglob("*.py")

    for file_path in python_files:
        content = file_path.read_text(encoding="utf-8")

        for line in content.splitlines():
            stripped = line.strip()

            assert not stripped.startswith("from .")
            assert not stripped.startswith("import .")


def test_accidental_platform_typo_module_does_not_exist() -> None:
    """The accidental duplicate platform directory must not return."""
    assert not (BACKEND_ROOT / "plaform").exists()
