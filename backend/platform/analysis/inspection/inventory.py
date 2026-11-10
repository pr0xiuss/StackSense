"""Deterministic inventory builder and role/outcome classification."""

from __future__ import annotations

import posixpath
from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import Any

import pathspec

from backend.platform.analysis.domain.analysis import AnalysisConfiguration
from backend.platform.analysis.domain.input import AnalysisArtifact
from backend.platform.analysis.inspection.model import (
    ArtifactAnalysisRole,
    ArtifactInventoryEntry,
    ArtifactProcessingOutcome,
    InspectionCoverage,
)
from backend.platform.ingestion.domain.constants import ArtifactCategory

SUPPORTED_LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
}

CONFIGURATION_FILENAMES: frozenset[str] = frozenset(
    {
        "package.json",
        "requirements.txt",
        "pipfile",
        "pyproject.toml",
        "tsconfig.json",
        "next.config.js",
        "next.config.mjs",
        "nest-cli.json",
        "dockerfile",
        "compose.yml",
        "compose.yaml",
        "docker-compose.yml",
        "docker-compose.yaml",
    }
)

DOCUMENTATION_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".md",
        ".rst",
        ".txt",
        ".adoc",
        ".pdf",
    }
)

SENSITIVE_FILENAME_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*id_rsa*",
    "*id_dsa*",
    "*id_ed25519*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*credentials*.json",
    "*secret*.json",
    "*.keystore",
    "*.jks",
)

BUILD_CACHE_DIRECTORIES: tuple[str, ...] = (
    "node_modules/",
    "dist/",
    "build/",
    "__pycache__/",
    ".git/",
    ".venv/",
    "venv/",
    ".tox/",
    ".pytest_cache/",
    ".ruff_cache/",
)

DEFAULT_MAX_ANALYZABLE_FILE_SIZE_BYTES = 5 * 1024 * 1024


class InventoryBuilder:
    """Builds and classifies an immutable repository inventory."""

    def __init__(
        self,
        configuration: AnalysisConfiguration | None = None,
        max_analyzable_file_size_bytes: int = DEFAULT_MAX_ANALYZABLE_FILE_SIZE_BYTES,
    ) -> None:
        self.configuration = configuration or AnalysisConfiguration()
        if max_analyzable_file_size_bytes <= 0:
            raise ValueError("max_analyzable_file_size_bytes must be positive")
        self._max_analyzable_file_size_bytes = min(
            self.configuration.max_file_size_bytes,
            max_analyzable_file_size_bytes,
        )
        self._exclude_spec: pathspec.PathSpec[Any] | None = None
        self._include_spec: pathspec.PathSpec[Any] | None = None

        if self.configuration.exclude_paths:
            self._exclude_spec = pathspec.PathSpec.from_lines(
                "gitignore", self.configuration.exclude_paths
            )
        if self.configuration.include_paths:
            self._include_spec = pathspec.PathSpec.from_lines(
                "gitignore", self.configuration.include_paths
            )

        self._sensitive_spec: pathspec.PathSpec[Any] = pathspec.PathSpec.from_lines(
            "gitignore", SENSITIVE_FILENAME_PATTERNS
        )

    def _normalize_path(self, path: str) -> str:
        """Return normalized repository-relative POSIX path."""
        if not path or "\x00" in path:
            raise ValueError("Artifact path must be a non-empty safe relative path")
        p = path.replace("\\", "/")
        if p.startswith("/"):
            raise ValueError(f"Artifact path must be repository-relative: {path}")
        while p.startswith("./"):
            p = p[2:]
        parts = PurePosixPath(p).parts
        if (
            not p
            or p == "."
            or posixpath.normpath(p) != p
            or any(part in ("", ".", "..") for part in parts)
            or (parts and parts[0].endswith(":"))
        ):
            raise ValueError(f"Artifact path is not safely normalized: {path}")
        return p

    def detect_language_from_path(self, path: str) -> str | None:
        """Detect language purely from file extension or standard name."""
        posix = PurePosixPath(self._normalize_path(path))
        ext = posix.suffix.lower()
        return SUPPORTED_LANGUAGE_EXTENSIONS.get(ext)

    def is_sensitive(self, artifact: AnalysisArtifact, norm_path: str) -> bool:
        """Check if artifact contains sensitive keys, tokens, or credentials."""
        if artifact.category == ArtifactCategory.ENVIRONMENT_SECRETS:
            return True
        posix = PurePosixPath(norm_path)
        return self._sensitive_spec.match_file(posix.name)

    def is_generated(self, artifact: AnalysisArtifact, norm_path: str) -> bool:
        """Check if artifact is generated code or a build lockfile."""
        if artifact.category == ArtifactCategory.GENERATED_ARTIFACTS:
            return True
        lower = norm_path.lower()
        if (
            lower.endswith(".min.js")
            or lower.endswith(".min.css")
            or lower.endswith(".bundle.js")
            or lower.endswith(".chunk.js")
        ):
            return True
        name = PurePosixPath(norm_path).name.lower()
        return name in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml")

    def is_test(self, artifact: AnalysisArtifact, norm_path: str) -> bool:
        """Check if artifact is a test file or test suite."""
        if artifact.category == ArtifactCategory.TESTS:
            return True
        parts = PurePosixPath(norm_path).parts
        if any(
            p.lower() in ("test", "tests", "__tests__", "spec", "specs") for p in parts
        ):
            return True
        name = PurePosixPath(norm_path).name.lower()
        if name.startswith("test_") or name.endswith("_test.py"):
            return True
        return any(
            name.endswith(sfx)
            for sfx in (
                ".test.js",
                ".spec.js",
                ".test.ts",
                ".spec.ts",
                ".test.jsx",
                ".test.tsx",
            )
        )

    def classify_artifact(self, artifact: AnalysisArtifact) -> ArtifactInventoryEntry:
        """Classify a single AnalysisArtifact into an ArtifactInventoryEntry."""
        norm_path = self._normalize_path(artifact.path)
        is_sens = self.is_sensitive(artifact, norm_path)
        is_gen = self.is_generated(artifact, norm_path)
        is_tst = self.is_test(artifact, norm_path)
        detected_lang = self.detect_language_from_path(norm_path)

        posix = PurePosixPath(norm_path)
        name_lower = posix.name.lower()
        ext_lower = posix.suffix.lower()

        role: ArtifactAnalysisRole
        outcome: ArtifactProcessingOutcome
        reasons: list[str] = []

        # Rule 1: Mandatory safety policy (sensitive / secrets)
        if is_sens or artifact.category == ArtifactCategory.ENVIRONMENT_SECRETS:
            role = ArtifactAnalysisRole.METADATA_ONLY
            outcome = ArtifactProcessingOutcome.NOT_PROCESSED
            reasons.append("prohibited_sensitive")

        # Rule 1b: Build cache or binary artifacts
        elif artifact.category in (
            ArtifactCategory.BINARY_ARTIFACTS,
            ArtifactCategory.IMAGES,
            ArtifactCategory.BUILD_CACHE_ARTIFACTS,
        ) or any(
            norm_path.startswith(bc) or f"/{bc}" in norm_path
            for bc in BUILD_CACHE_DIRECTORIES
        ):
            role = ArtifactAnalysisRole.IGNORED
            outcome = ArtifactProcessingOutcome.EXCLUDED
            reasons.append("build_cache_or_binary")

        # Rule 1c: Generated artifacts (minified, bundles, generated code)
        elif artifact.category == ArtifactCategory.GENERATED_ARTIFACTS or is_gen:
            role = ArtifactAnalysisRole.IGNORED
            outcome = ArtifactProcessingOutcome.EXCLUDED
            reasons.append("generated_code")

        # Rule 1d: Oversized file ceiling
        elif artifact.size_bytes > self._max_analyzable_file_size_bytes:
            role = ArtifactAnalysisRole.METADATA_ONLY
            outcome = ArtifactProcessingOutcome.EXCLUDED
            reasons.append("oversized_file")

        # Rule 2: Explicit user exclusion
        elif self._exclude_spec and self._exclude_spec.match_file(norm_path):
            role = ArtifactAnalysisRole.IGNORED
            outcome = ArtifactProcessingOutcome.EXCLUDED
            reasons.append("user_excluded")

        # Rule 3: Explicit user inclusion filter
        elif self._include_spec and not self._include_spec.match_file(norm_path):
            role = ArtifactAnalysisRole.IGNORED
            outcome = ArtifactProcessingOutcome.EXCLUDED
            reasons.append("not_included")

        # Rule 4: Supported source files
        elif detected_lang is not None:
            role = ArtifactAnalysisRole.SEMANTIC
            outcome = ArtifactProcessingOutcome.NOT_PROCESSED
            reasons.append("supported_test" if is_tst else "supported_source")

        # Rule 5: Configuration and manifests
        elif (
            artifact.category
            in (
                ArtifactCategory.CONFIGURATION,
                ArtifactCategory.DEPENDENCY_METADATA,
                ArtifactCategory.INFRASTRUCTURE,
                ArtifactCategory.DATABASE_ARTIFACTS,
            )
            or name_lower in CONFIGURATION_FILENAMES
        ):
            role = ArtifactAnalysisRole.CONFIGURATION
            outcome = ArtifactProcessingOutcome.NOT_PROCESSED
            reasons.append("manifest_or_configuration")

        # Rule 6: Documentation
        elif (
            artifact.category == ArtifactCategory.DOCUMENTATION
            or ext_lower in DOCUMENTATION_EXTENSIONS
        ):
            role = ArtifactAnalysisRole.DOCUMENTATION
            outcome = ArtifactProcessingOutcome.NOT_PROCESSED
            reasons.append("documentation")

        # Rule 7: Markup UI (HTML, CSS templates not parsed as JS/TS)
        elif artifact.category == ArtifactCategory.MARKUP_UI or ext_lower in (
            ".html",
            ".htm",
            ".css",
            ".scss",
            ".sass",
            ".less",
        ):
            role = ArtifactAnalysisRole.METADATA_ONLY
            outcome = ArtifactProcessingOutcome.NOT_PROCESSED
            reasons.append("markup_ui")

        # Rule 8: Architecture assets & data files
        elif artifact.category in (
            ArtifactCategory.ARCHITECTURE_ASSETS,
            ArtifactCategory.DATA_FILES,
        ):
            role = ArtifactAnalysisRole.METADATA_ONLY
            outcome = ArtifactProcessingOutcome.NOT_PROCESSED
            reasons.append("data_or_asset")

        # Rule 9: Unsupported file type
        else:
            role = ArtifactAnalysisRole.UNSUPPORTED
            outcome = ArtifactProcessingOutcome.UNSUPPORTED
            reasons.append("unsupported_file_type")

        return ArtifactInventoryEntry(
            artifact_id=artifact.id,
            revision_id=artifact.revision_id,
            path=norm_path,
            content_hash=artifact.content_hash,
            size_bytes=artifact.size_bytes,
            original_category=artifact.category.value,
            original_support_level=artifact.support_level.value,
            detected_language=detected_lang,
            is_test=is_tst,
            is_generated=is_gen,
            is_sensitive=is_sens,
            analysis_role=role,
            processing_outcome=outcome,
            reason_codes=tuple(reasons),
        )

    def build_inventory(
        self, artifacts: Iterable[AnalysisArtifact]
    ) -> tuple[tuple[ArtifactInventoryEntry, ...], InspectionCoverage]:
        """Classify artifacts, order deterministically by path, and calculate
        coverage.
        """
        entries = [self.classify_artifact(art) for art in artifacts]
        # Sort lexicographically by normalized relative path
        sorted_entries = tuple(sorted(entries, key=lambda e: e.path))
        paths = [entry.path for entry in sorted_entries]
        if len(paths) != len(set(paths)):
            raise ValueError("Artifact inventory contains duplicate normalized paths")

        total_bytes = sum(e.size_bytes for e in sorted_entries)
        role_counts: dict[str, int] = {}
        outcome_counts: dict[str, int] = {}
        language_counts: dict[str, int] = {}
        processed_count = 0
        failed_count = 0

        for e in sorted_entries:
            role_counts[e.analysis_role.value] = (
                role_counts.get(e.analysis_role.value, 0) + 1
            )
            outcome_counts[e.processing_outcome.value] = (
                outcome_counts.get(e.processing_outcome.value, 0) + 1
            )
            lang_key = e.detected_language or "unknown"
            language_counts[lang_key] = language_counts.get(lang_key, 0) + 1

            if e.processing_outcome in (
                ArtifactProcessingOutcome.ANALYZED,
                ArtifactProcessingOutcome.ANALYZED_WITH_WARNINGS,
            ):
                processed_count += 1
            elif e.processing_outcome == ArtifactProcessingOutcome.FAILED:
                failed_count += 1

        coverage = InspectionCoverage(
            total_artifacts=len(sorted_entries),
            total_bytes=total_bytes,
            role_counts=role_counts,
            outcome_counts=outcome_counts,
            language_counts=language_counts,
            processed_artifacts=processed_count,
            failed_artifacts=failed_count,
        )

        return sorted_entries, coverage
