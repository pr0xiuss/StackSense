"""Language, runtime, and preliminary framework candidate detection."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from backend.platform.analysis.domain.constants import (
    DiagnosticCategory,
    DiagnosticScope,
    DiagnosticSeverity,
    FailureRetryability,
)
from backend.platform.analysis.domain.diagnostic import AnalysisDiagnostic
from backend.platform.analysis.domain.input import (
    AnalysisArtifact,
    ArtifactContentReader,
)
from backend.platform.analysis.inspection.model import (
    ArtifactAnalysisRole,
    ArtifactInventoryEntry,
    ArtifactProcessingOutcome,
    DetectionEvidence,
    FrameworkDetection,
    LanguageDetection,
    RuntimeDetection,
)

FRAMEWORK_TARGETS: tuple[str, ...] = (
    "django",
    "flask",
    "fastapi",
    "express",
    "nestjs",
    "nextjs",
)


def parse_safe_requirements_txt(content: str) -> dict[str, str | None]:
    """Extract allowlisted package names and versions from requirements.txt."""
    dependencies: dict[str, str | None] = {}
    for line in content.splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#") or clean.startswith("-"):
            continue
        # Split on comments
        clean = clean.split("#")[0].strip()
        # Parse package name and version
        for op in ("==", ">=", "<=", "~=", ">", "<", "!="):
            if op in clean:
                parts = clean.split(op, 1)
                pkg_name = parts[0].strip().lower()
                version = parts[1].strip()
                if pkg_name:
                    dependencies[pkg_name] = version
                break
        else:
            pkg_name = clean.split(";")[0].strip().lower()
            if pkg_name:
                dependencies[pkg_name] = None
    return dependencies


def parse_safe_package_json(content: str) -> dict[str, str | None]:
    """Extract allowlisted dependencies from package.json without secrets."""
    dependencies: dict[str, str | None] = {}
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("package.json root must be a JSON object")
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        sec_dict = data.get(section)
        if isinstance(sec_dict, dict):
            for k, v in sec_dict.items():
                dependencies[k.lower().strip()] = str(v).strip() if v else None
    return dependencies


class DetectionService:
    """Performs metadata/manifest-based language, runtime, and candidate
    framework detection.
    """

    def detect_languages(
        self, inventory: Iterable[ArtifactInventoryEntry]
    ) -> tuple[LanguageDetection, ...]:
        """Produce language detections for all inventory entries with
        identified languages.
        """
        detections: list[LanguageDetection] = []
        for entry in inventory:
            if entry.detected_language:
                detections.append(
                    LanguageDetection(
                        artifact_id=entry.artifact_id,
                        path=entry.path,
                        language=entry.detected_language,
                        confidence="confirmed",
                        evidence_signals=(f"extension_match:{entry.path}",),
                    )
                )
        return tuple(sorted(detections, key=lambda d: d.path))

    def detect_runtimes(
        self, inventory: Iterable[ArtifactInventoryEntry]
    ) -> tuple[RuntimeDetection, ...]:
        """Detect execution runtimes (python, node, browser) from inventory metadata."""
        runtimes: list[RuntimeDetection] = []
        paths = [e.path.lower() for e in inventory]
        langs = {e.detected_language for e in inventory if e.detected_language}

        has_python = "python" in langs or any(
            p.endswith(("requirements.txt", "pipfile", "pyproject.toml")) for p in paths
        )
        if has_python:
            runtimes.append(
                RuntimeDetection(
                    runtime="python",
                    target="cpython",
                    evidence_signals=("python_sources_or_manifests_present",),
                )
            )

        has_node = any(
            lang_name in langs for lang_name in ("javascript", "typescript")
        ) or any(p.endswith("package.json") for p in paths)
        if has_node:
            runtimes.append(
                RuntimeDetection(
                    runtime="node",
                    target="nodejs",
                    evidence_signals=("node_sources_or_package_json_present",),
                )
            )

        has_browser = any(lang_name in langs for lang_name in ("jsx", "tsx")) or any(
            p.endswith(
                ("index.html", "vite.config.js", "vite.config.ts", "next.config.js")
            )
            for p in paths
        )
        if has_browser:
            runtimes.append(
                RuntimeDetection(
                    runtime="browser",
                    target="web",
                    evidence_signals=("ui_markup_or_components_present",),
                )
            )

        return tuple(sorted(runtimes, key=lambda r: r.runtime))

    def detect_framework_candidates(
        self,
        artifacts: Iterable[AnalysisArtifact],
        inventory: Iterable[ArtifactInventoryEntry],
        content_reader: ArtifactContentReader | None = None,
        analysis_id: UUID | None = None,
    ) -> tuple[
        tuple[FrameworkDetection, ...],
        tuple[DetectionEvidence, ...],
        tuple[AnalysisDiagnostic, ...],
    ]:
        """Detect preliminary framework candidates from path signals and
        permitted manifests.
        """
        artifacts_by_path = {a.path.replace("\\", "/"): a for a in artifacts}
        inv_by_path = {e.path.replace("\\", "/"): e for e in inventory}
        detections: list[FrameworkDetection] = []
        evidence_list: list[DetectionEvidence] = []
        diagnostics: list[AnalysisDiagnostic] = []

        manifest_dependencies: dict[str, str | None] = {}

        # Safely read permitted manifests if content reader is available
        if content_reader is not None:
            for path, art in artifacts_by_path.items():
                entry = inv_by_path.get(path)
                if entry is None:
                    continue

                # Gate: strictly skip ineligible, ignored, sensitive,
                # or excluded entries
                if entry.analysis_role not in (
                    ArtifactAnalysisRole.CONFIGURATION,
                    ArtifactAnalysisRole.SEMANTIC,
                ):
                    continue
                if entry.processing_outcome in (
                    ArtifactProcessingOutcome.EXCLUDED,
                    ArtifactProcessingOutcome.FAILED,
                ):
                    continue
                if entry.is_sensitive:
                    continue

                posix_parts = PurePosixPath(path).parts
                if any(
                    p.lower()
                    in (
                        "node_modules",
                        ".venv",
                        "venv",
                        "__pycache__",
                        "dist",
                        "build",
                    )
                    for p in posix_parts
                ):
                    continue

                posix_name = PurePosixPath(path).name.lower()
                if posix_name == "package.json":
                    try:
                        content_bytes = content_reader.read_bytes(
                            art, max_bytes=1024 * 1024
                        )
                        text = content_bytes.decode("utf-8", errors="strict")
                        try:
                            pkg_deps = parse_safe_package_json(text)
                            manifest_dependencies.update(pkg_deps)
                        except Exception as json_err:
                            diagnostics.append(
                                AnalysisDiagnostic(
                                    id=uuid4(),
                                    analysis_id=analysis_id or uuid4(),
                                    code="manifest_syntax_error",
                                    category=DiagnosticCategory.PARSING,
                                    severity=DiagnosticSeverity.WARNING,
                                    scope=DiagnosticScope.FILE,
                                    message=(
                                        f"Failed to parse package.json at {path}: "
                                        f"{json_err}"
                                    ),
                                    retryability=FailureRetryability.NON_RETRYABLE,
                                    created_at=datetime.now(UTC),
                                    stage="framework_detection",
                                    artifact_id=art.id,
                                    artifact_path=path,
                                )
                            )
                    except UnicodeDecodeError as decode_err:
                        diagnostics.append(
                            AnalysisDiagnostic(
                                id=uuid4(),
                                analysis_id=analysis_id or uuid4(),
                                code="manifest_decode_failed",
                                category=DiagnosticCategory.PARSING,
                                severity=DiagnosticSeverity.WARNING,
                                scope=DiagnosticScope.FILE,
                                message=(
                                    f"Manifest at {path} is not valid UTF-8: "
                                    f"{decode_err}"
                                ),
                                retryability=FailureRetryability.NON_RETRYABLE,
                                created_at=datetime.now(UTC),
                                stage="framework_detection",
                                artifact_id=art.id,
                                artifact_path=path,
                            )
                        )
                    except Exception as read_err:
                        diagnostics.append(
                            AnalysisDiagnostic(
                                id=uuid4(),
                                analysis_id=analysis_id or uuid4(),
                                code="manifest_read_failed",
                                category=DiagnosticCategory.PARSING,
                                severity=DiagnosticSeverity.WARNING,
                                scope=DiagnosticScope.FILE,
                                message=(
                                    f"Failed to read manifest at {path}: {read_err}"
                                ),
                                retryability=FailureRetryability.NON_RETRYABLE,
                                created_at=datetime.now(UTC),
                                stage="framework_detection",
                                artifact_id=art.id,
                                artifact_path=path,
                            )
                        )
                elif posix_name == "requirements.txt":
                    try:
                        content_bytes = content_reader.read_bytes(
                            art, max_bytes=1024 * 1024
                        )
                        text = content_bytes.decode("utf-8", errors="strict")
                        manifest_dependencies.update(parse_safe_requirements_txt(text))
                    except UnicodeDecodeError as decode_err:
                        diagnostics.append(
                            AnalysisDiagnostic(
                                id=uuid4(),
                                analysis_id=analysis_id or uuid4(),
                                code="manifest_decode_failed",
                                category=DiagnosticCategory.PARSING,
                                severity=DiagnosticSeverity.WARNING,
                                scope=DiagnosticScope.FILE,
                                message=(
                                    f"Manifest at {path} is not valid UTF-8: "
                                    f"{decode_err}"
                                ),
                                retryability=FailureRetryability.NON_RETRYABLE,
                                created_at=datetime.now(UTC),
                                stage="framework_detection",
                                artifact_id=art.id,
                                artifact_path=path,
                            )
                        )
                    except Exception as read_err:
                        diagnostics.append(
                            AnalysisDiagnostic(
                                id=uuid4(),
                                analysis_id=analysis_id or uuid4(),
                                code="manifest_read_failed",
                                category=DiagnosticCategory.PARSING,
                                severity=DiagnosticSeverity.WARNING,
                                scope=DiagnosticScope.FILE,
                                message=(
                                    f"Failed to read manifest at {path}: {read_err}"
                                ),
                                retryability=FailureRetryability.NON_RETRYABLE,
                                created_at=datetime.now(UTC),
                                stage="framework_detection",
                                artifact_id=art.id,
                                artifact_path=path,
                            )
                        )

        inv_paths = {e.path.lower(): e for e in inventory}

        # 1. Django
        django_signals: list[str] = []
        if "django" in manifest_dependencies:
            django_signals.append("dependency:django")
        for path_key, entry in inv_paths.items():
            if path_key.endswith(("manage.py", "wsgi.py", "asgi.py")):
                django_signals.append(f"path_signal:{entry.path}")
                evidence_list.append(
                    DetectionEvidence(
                        artifact_id=entry.artifact_id,
                        path=entry.path,
                        signal_code="django_path_marker",
                        observed_token=PurePosixPath(entry.path).name,
                        analyzer_id="m2_preliminary_detector",
                        polarity="supporting",
                    )
                )
        if django_signals:
            detections.append(
                FrameworkDetection(
                    framework="django",
                    status="candidate",
                    version=manifest_dependencies.get("django"),
                    evidence_signals=tuple(django_signals),
                )
            )

        # 2. Flask
        flask_signals: list[str] = []
        if "flask" in manifest_dependencies:
            flask_signals.append("dependency:flask")
        if flask_signals:
            detections.append(
                FrameworkDetection(
                    framework="flask",
                    status="candidate",
                    version=manifest_dependencies.get("flask"),
                    evidence_signals=tuple(flask_signals),
                )
            )

        # 3. FastAPI
        fastapi_signals: list[str] = []
        if "fastapi" in manifest_dependencies:
            fastapi_signals.append("dependency:fastapi")
        if fastapi_signals:
            detections.append(
                FrameworkDetection(
                    framework="fastapi",
                    status="candidate",
                    version=manifest_dependencies.get("fastapi"),
                    evidence_signals=tuple(fastapi_signals),
                )
            )

        # 4. Express
        express_signals: list[str] = []
        if "express" in manifest_dependencies:
            express_signals.append("dependency:express")
        if express_signals:
            detections.append(
                FrameworkDetection(
                    framework="express",
                    status="candidate",
                    version=manifest_dependencies.get("express"),
                    evidence_signals=tuple(express_signals),
                )
            )

        # 5. NestJS
        nestjs_signals: list[str] = []
        if (
            "@nestjs/core" in manifest_dependencies
            or "@nestjs/common" in manifest_dependencies
        ):
            nestjs_signals.append("dependency:@nestjs")
        for path_key, entry in inv_paths.items():
            if path_key.endswith("nest-cli.json"):
                nestjs_signals.append("path_signal:nest-cli.json")
                evidence_list.append(
                    DetectionEvidence(
                        artifact_id=entry.artifact_id,
                        path=entry.path,
                        signal_code="nest_cli_config",
                        observed_token="nest-cli.json",
                        analyzer_id="m2_preliminary_detector",
                        polarity="supporting",
                    )
                )
        if nestjs_signals:
            detections.append(
                FrameworkDetection(
                    framework="nestjs",
                    status="candidate",
                    version=manifest_dependencies.get("@nestjs/core"),
                    evidence_signals=tuple(nestjs_signals),
                )
            )

        # 6. Next.js
        nextjs_signals: list[str] = []
        if "next" in manifest_dependencies:
            nextjs_signals.append("dependency:next")
        for path_key, entry in inv_paths.items():
            if "next.config" in path_key:
                nextjs_signals.append(f"path_signal:{entry.path}")
                evidence_list.append(
                    DetectionEvidence(
                        artifact_id=entry.artifact_id,
                        path=entry.path,
                        signal_code="next_config",
                        observed_token=PurePosixPath(entry.path).name,
                        analyzer_id="m2_preliminary_detector",
                        polarity="supporting",
                    )
                )
        if nextjs_signals:
            detections.append(
                FrameworkDetection(
                    framework="nextjs",
                    status="candidate",
                    version=manifest_dependencies.get("next"),
                    evidence_signals=tuple(nextjs_signals),
                )
            )

        sorted_detections = tuple(sorted(detections, key=lambda d: d.framework))
        sorted_evidence = tuple(
            sorted(evidence_list, key=lambda e: (e.path, e.signal_code))
        )
        return sorted_detections, sorted_evidence, tuple(diagnostics)
