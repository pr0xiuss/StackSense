"""Artifact classification pipeline per master.txt Appendix G."""

import fnmatch
from pathlib import PurePosixPath

from backend.platform.ingestion.domain.constants import (
    MAX_INDIVIDUAL_FILE_SIZE_BYTES,
    ArtifactCategory,
    SupportLevel,
)

# Canonical categorization patterns
BUILD_CACHE_DIRS = {
    "node_modules",
    "vendor",
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    ".gradle",
    ".idea",
    ".vscode",
}

DEPENDENCY_LOCK_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "cargo.lock",
    "go.sum",
    "requirements.txt",
}

CONFIG_FILES = {
    "dockerfile",
    "compose.yml",
    "compose.yaml",
    "docker-compose.yml",
    "package.json",
    "tsconfig.json",
    "pyproject.toml",
    "cargo.toml",
    "pom.xml",
    "build.gradle",
}

SOURCE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".java",
    ".kt",
    ".scala",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".cc",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
}

MARKUP_EXTENSIONS = {
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".vue",
    ".svelte",
}

CONFIG_EXTENSIONS = {
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".xml",
}

DOC_EXTENSIONS = {
    ".md",
    ".markdown",
    ".rst",
    ".txt",
    ".adoc",
}

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".webp",
    ".bmp",
    ".tiff",
}

ARCH_EXTENSIONS = {
    ".drawio",
    ".puml",
    ".plantuml",
    ".mermaid",
}

INFRA_EXTENSIONS = {
    ".tf",
    ".tfvars",
}

DB_EXTENSIONS = {
    ".sql",
    ".prisma",
}

BINARY_EXTENSIONS = {
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".class",
    ".pyc",
    ".o",
    ".bin",
    ".wasm",
}

DATA_EXTENSIONS = {
    ".csv",
    ".tsv",
    ".parquet",
    ".arrow",
}


class ArtifactClassifier:
    """Classifies repository files into canonical categories and support levels."""

    def classify(
        self,
        relative_path: str,
        size_bytes: int,
    ) -> tuple[ArtifactCategory, SupportLevel]:
        path = PurePosixPath(relative_path.replace("\\", "/").strip("/"))
        filename = path.name.lower()
        parts = {p.lower() for p in path.parts}
        ext = path.suffix.lower()

        # 1. Build cache and ignored directories
        if any(part in BUILD_CACHE_DIRS for part in parts):
            return ArtifactCategory.BUILD_CACHE_ARTIFACTS, SupportLevel.IGNORED

        # 2. Minified / generated artifacts
        if (
            filename.endswith(".min.js")
            or filename.endswith(".min.css")
            or filename.endswith(".map")
        ):
            return ArtifactCategory.GENERATED_ARTIFACTS, SupportLevel.IGNORED

        # 3. Environment & secrets
        if (
            filename == ".env"
            or filename.startswith(".env.")
            or ext in {".pem", ".key", ".pfx"}
            or fnmatch.fnmatch(filename, "id_rsa*")
            or filename.startswith("secrets.")
        ):
            return ArtifactCategory.ENVIRONMENT_SECRETS, SupportLevel.METADATA

        # 4. Dependency metadata
        if filename in DEPENDENCY_LOCK_FILES:
            return ArtifactCategory.DEPENDENCY_METADATA, SupportLevel.METADATA

        # 5. Architecture assets
        if ext in ARCH_EXTENSIONS:
            return self._with_size_check(
                ArtifactCategory.ARCHITECTURE_ASSETS,
                SupportLevel.FULL,
                size_bytes,
            )

        # 6. Tests
        if (
            any(part in {"test", "tests", "spec", "specs"} for part in parts)
            or fnmatch.fnmatch(filename, "*test*.*")
            or fnmatch.fnmatch(filename, "*spec*.*")
        ):
            return self._with_size_check(
                ArtifactCategory.TESTS,
                SupportLevel.FULL,
                size_bytes,
            )

        # 7. Source code
        if ext in SOURCE_EXTENSIONS:
            return self._with_size_check(
                ArtifactCategory.SOURCE_CODE,
                SupportLevel.FULL,
                size_bytes,
            )

        # 8. Markup & UI
        if ext in MARKUP_EXTENSIONS:
            return self._with_size_check(
                ArtifactCategory.MARKUP_UI,
                SupportLevel.FULL,
                size_bytes,
            )

        # 9. Infrastructure
        if ext in INFRA_EXTENSIONS or filename in {"vagrantfile", "chart.yaml"}:
            return self._with_size_check(
                ArtifactCategory.INFRASTRUCTURE,
                SupportLevel.FULL,
                size_bytes,
            )

        # 10. Database artifacts
        if ext in DB_EXTENSIONS:
            return self._with_size_check(
                ArtifactCategory.DATABASE_ARTIFACTS,
                SupportLevel.FULL,
                size_bytes,
            )

        # 11. Configuration
        if filename in CONFIG_FILES or ext in CONFIG_EXTENSIONS:
            return self._with_size_check(
                ArtifactCategory.CONFIGURATION,
                SupportLevel.FULL,
                size_bytes,
            )

        # 12. Documentation
        if (
            ext in DOC_EXTENSIONS
            or filename in {"license", "notice"}
            or filename.startswith("changelog")
        ):
            return self._with_size_check(
                ArtifactCategory.DOCUMENTATION,
                SupportLevel.PARTIAL,
                size_bytes,
            )

        # 13. Images
        if ext in IMAGE_EXTENSIONS:
            return ArtifactCategory.IMAGES, SupportLevel.METADATA

        # 14. Data files
        if ext in DATA_EXTENSIONS:
            return ArtifactCategory.DATA_FILES, SupportLevel.METADATA

        # 15. Binaries
        if ext in BINARY_EXTENSIONS:
            return ArtifactCategory.BINARY_ARTIFACTS, SupportLevel.UNSUPPORTED

        # 16. Fallback
        return ArtifactCategory.UNKNOWN_UNSUPPORTED, SupportLevel.UNSUPPORTED

    @staticmethod
    def _with_size_check(
        category: ArtifactCategory,
        base_support: SupportLevel,
        size_bytes: int,
    ) -> tuple[ArtifactCategory, SupportLevel]:
        if size_bytes > MAX_INDIVIDUAL_FILE_SIZE_BYTES:
            return category, SupportLevel.UNSUPPORTED
        return category, base_support
