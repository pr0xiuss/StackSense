"""Language, runtime, and preliminary framework candidate detection."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import PurePosixPath
from uuid import UUID, uuid5

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
from backend.platform.analysis.syntax.model import (
    ImportFact,
    ManifestFact,
    ParseStatus,
    SourceEncodingMetadata,
    SyntaxDocument,
    build_fact_key,
    sort_facts,
)

FRAMEWORK_TARGETS: tuple[str, ...] = (
    "django",
    "flask",
    "fastapi",
    "express",
    "nestjs",
    "nextjs",
)


def _is_detection_eligible(entry: ArtifactInventoryEntry) -> bool:
    return (
        entry.analysis_role
        in (ArtifactAnalysisRole.CONFIGURATION, ArtifactAnalysisRole.SEMANTIC)
        and entry.processing_outcome
        not in (ArtifactProcessingOutcome.EXCLUDED, ArtifactProcessingOutcome.FAILED)
        and not entry.is_sensitive
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
            if entry.detected_language and _is_detection_eligible(entry):
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
        eligible = tuple(entry for entry in inventory if _is_detection_eligible(entry))
        paths = [e.path.lower() for e in eligible]
        langs = {e.detected_language for e in eligible if e.detected_language}

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
        manifest_documents: list[SyntaxDocument] | None = None,
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

        manifest_dependencies: dict[str, list[tuple[str, UUID, str | None]]] = {}

        # Safely read permitted manifests if content reader is available
        if content_reader is not None:
            for path, art in sorted(artifacts_by_path.items()):
                entry = inv_by_path.get(path)
                if entry is None:
                    continue

                # Gate: strictly skip ineligible, ignored, sensitive,
                # or excluded entries
                if not _is_detection_eligible(entry):
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
                            for name, version in sorted(pkg_deps.items()):
                                manifest_dependencies.setdefault(name, []).append(
                                    (path, art.id, version)
                                )
                            if manifest_documents is not None:
                                manifest_documents.append(
                                    _manifest_document(
                                        art,
                                        path,
                                        content_bytes,
                                        "package_json",
                                        pkg_deps,
                                    )
                                )
                        except Exception as json_err:
                            diagnostics.append(
                                AnalysisDiagnostic(
                                    id=uuid5(
                                        analysis_id or art.id,
                                        f"m2:manifest_syntax_error:{path}",
                                    ),
                                    analysis_id=analysis_id or art.id,
                                    code="manifest_syntax_error",
                                    category=DiagnosticCategory.PARSING,
                                    severity=DiagnosticSeverity.WARNING,
                                    scope=DiagnosticScope.FILE,
                                    message=(
                                        f"Failed to parse package.json at {path} "
                                        f"({type(json_err).__name__})"
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
                                id=uuid5(
                                    analysis_id or art.id,
                                    f"m2:manifest_decode_failed:{path}",
                                ),
                                analysis_id=analysis_id or art.id,
                                code="manifest_decode_failed",
                                category=DiagnosticCategory.PARSING,
                                severity=DiagnosticSeverity.WARNING,
                                scope=DiagnosticScope.FILE,
                                message=(
                                    f"Manifest at {path} is not valid UTF-8 "
                                    f"(byte {decode_err.start})"
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
                                id=uuid5(
                                    analysis_id or art.id,
                                    f"m2:manifest_read_failed:{path}",
                                ),
                                analysis_id=analysis_id or art.id,
                                code="manifest_read_failed",
                                category=DiagnosticCategory.PARSING,
                                severity=DiagnosticSeverity.WARNING,
                                scope=DiagnosticScope.FILE,
                                message=(
                                    f"Failed to read manifest at {path} "
                                    f"({type(read_err).__name__})"
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
                        requirements = parse_safe_requirements_txt(text)
                        for name, version in sorted(requirements.items()):
                            manifest_dependencies.setdefault(name, []).append(
                                (path, art.id, version)
                            )
                        if manifest_documents is not None:
                            manifest_documents.append(
                                _manifest_document(
                                    art,
                                    path,
                                    content_bytes,
                                    "requirements_txt",
                                    requirements,
                                )
                            )
                    except UnicodeDecodeError as decode_err:
                        diagnostics.append(
                            AnalysisDiagnostic(
                                id=uuid5(
                                    analysis_id or art.id,
                                    f"m2:manifest_decode_failed:{path}",
                                ),
                                analysis_id=analysis_id or art.id,
                                code="manifest_decode_failed",
                                category=DiagnosticCategory.PARSING,
                                severity=DiagnosticSeverity.WARNING,
                                scope=DiagnosticScope.FILE,
                                message=(
                                    f"Manifest at {path} is not valid UTF-8 "
                                    f"(byte {decode_err.start})"
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
                                id=uuid5(
                                    analysis_id or art.id,
                                    f"m2:manifest_read_failed:{path}",
                                ),
                                analysis_id=analysis_id or art.id,
                                code="manifest_read_failed",
                                category=DiagnosticCategory.PARSING,
                                severity=DiagnosticSeverity.WARNING,
                                scope=DiagnosticScope.FILE,
                                message=(
                                    f"Failed to read manifest at {path} "
                                    f"({type(read_err).__name__})"
                                ),
                                retryability=FailureRetryability.NON_RETRYABLE,
                                created_at=datetime.now(UTC),
                                stage="framework_detection",
                                artifact_id=art.id,
                                artifact_path=path,
                            )
                        )

        inv_paths = {e.path.lower(): e for e in inventory if _is_detection_eligible(e)}

        def dependency_signals(
            framework: str, *package_names: str
        ) -> tuple[list[str], str | None]:
            signals: list[str] = []
            versions: set[str] = set()
            all_records: list[tuple[str, UUID, str | None, str]] = []
            for package_name in package_names:
                records = sorted(
                    manifest_dependencies.get(package_name, ()),
                    key=lambda record: (record[0], str(record[1]), record[2] or ""),
                )
                if records:
                    signals.append(f"dependency:{package_name}")
                for path, artifact_id, version in records:
                    all_records.append((path, artifact_id, version, package_name))
                    if version:
                        versions.add(version)
                    evidence_list.append(
                        DetectionEvidence(
                            artifact_id=artifact_id,
                            path=path,
                            signal_code=f"{framework}_dependency",
                            observed_token=package_name,
                            analyzer_id="m2_preliminary_detector",
                            polarity="supporting",
                        )
                    )
            if len(versions) > 1:
                for path, artifact_id, _, package_name in all_records:
                    evidence_list.append(
                        DetectionEvidence(
                            artifact_id=artifact_id,
                            path=path,
                            signal_code=f"{framework}_dependency_version_conflict",
                            observed_token=package_name,
                            analyzer_id="m2_preliminary_detector",
                            polarity="conflicting",
                        )
                    )
            return signals, next(iter(versions)) if len(versions) == 1 else None

        # 1. Django
        django_signals, django_version = dependency_signals("django", "django")
        for path_key, entry in inv_paths.items():
            if PurePosixPath(path_key).name in ("manage.py", "wsgi.py", "asgi.py"):
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
                    version=django_version,
                    evidence_signals=tuple(django_signals),
                )
            )

        # 2. Flask
        flask_signals, flask_version = dependency_signals("flask", "flask")
        if flask_signals:
            detections.append(
                FrameworkDetection(
                    framework="flask",
                    status="candidate",
                    version=flask_version,
                    evidence_signals=tuple(flask_signals),
                )
            )

        # 3. FastAPI
        fastapi_signals, fastapi_version = dependency_signals("fastapi", "fastapi")
        if fastapi_signals:
            detections.append(
                FrameworkDetection(
                    framework="fastapi",
                    status="candidate",
                    version=fastapi_version,
                    evidence_signals=tuple(fastapi_signals),
                )
            )

        # 4. Express
        express_signals, express_version = dependency_signals("express", "express")
        if express_signals:
            detections.append(
                FrameworkDetection(
                    framework="express",
                    status="candidate",
                    version=express_version,
                    evidence_signals=tuple(express_signals),
                )
            )

        # 5. NestJS
        nestjs_signals, nestjs_version = dependency_signals(
            "nestjs", "@nestjs/core", "@nestjs/common"
        )
        if nestjs_signals:
            nestjs_signals = ["dependency:@nestjs"]
        for path_key, entry in inv_paths.items():
            if PurePosixPath(path_key).name == "nest-cli.json":
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
                    version=nestjs_version,
                    evidence_signals=tuple(nestjs_signals),
                )
            )

        # 6. Next.js
        nextjs_signals, nextjs_version = dependency_signals("nextjs", "next")
        for path_key, entry in inv_paths.items():
            next_path = PurePosixPath(path_key)
            if next_path.name in (
                "next.config.js",
                "next.config.mjs",
                "next.config.ts",
            ):
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
            elif (
                next_path.name.startswith(("page.", "route."))
                and "app" in next_path.parts
            ) or "pages" in next_path.parts:
                nextjs_signals.append(f"path_signal:{entry.path}")
                evidence_list.append(
                    DetectionEvidence(
                        artifact_id=entry.artifact_id,
                        path=entry.path,
                        signal_code="next_route_convention",
                        observed_token=next_path.name,
                        analyzer_id="m2_preliminary_detector",
                        polarity="supporting",
                    )
                )
        if nextjs_signals:
            detections.append(
                FrameworkDetection(
                    framework="nextjs",
                    status="candidate",
                    version=nextjs_version,
                    evidence_signals=tuple(nextjs_signals),
                )
            )

        sorted_detections = tuple(sorted(detections, key=lambda d: d.framework))
        sorted_evidence = tuple(
            sorted(evidence_list, key=lambda e: (e.path, e.signal_code))
        )
        return sorted_detections, sorted_evidence, tuple(diagnostics)

    def finalize_framework_detections(
        self,
        candidates: Iterable[FrameworkDetection],
        syntax_documents: Iterable[SyntaxDocument],
    ) -> tuple[FrameworkDetection, ...]:
        """Finalize candidate state from the already-produced generic facts.

        This method never parses source and never creates framework-specific facts.
        A manifest/path-only candidate remains ``supported``; an allowlisted generic
        import signal upgrades it to ``confirmed``.
        """
        module_frameworks: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("django", ("django",)),
            ("flask", ("flask",)),
            ("fastapi", ("fastapi",)),
            ("express", ("express",)),
            ("nestjs", ("@nestjs/",)),
            ("nextjs", ("next", "next/")),
        )
        imported_modules = {
            fact.source_module
            for document in syntax_documents
            if document.parse_status.value != "failed"
            for fact in document.facts
            if isinstance(fact, ImportFact)
        }
        candidate_map = {candidate.framework: candidate for candidate in candidates}
        finalized: list[FrameworkDetection] = []
        for framework, prefixes in module_frameworks:
            candidate = candidate_map.get(framework)
            syntax_matches = sorted(
                module
                for module in imported_modules
                if any(
                    (
                        module.startswith(prefix)
                        if prefix.endswith("/")
                        else module == prefix
                    )
                    for prefix in prefixes
                )
            )
            if candidate is None and not syntax_matches:
                continue
            signals = list(candidate.evidence_signals if candidate else ())
            signals.extend(f"syntax_import:{module}" for module in syntax_matches)
            independent_candidate_signals = {
                (
                    "dependency"
                    if signal.startswith("dependency:")
                    else "path" if signal.startswith("path_signal:") else signal
                )
                for signal in signals
            }
            corroborated_candidate = len(independent_candidate_signals) >= 2
            finalized.append(
                FrameworkDetection(
                    framework=framework,
                    status=(
                        "confirmed"
                        if syntax_matches or corroborated_candidate
                        else "supported"
                    ),
                    version=candidate.version if candidate else None,
                    evidence_signals=tuple(sorted(set(signals))),
                )
            )
        return tuple(finalized)


def _manifest_document(
    artifact: AnalysisArtifact,
    path: str,
    content: bytes,
    manifest_type: str,
    dependencies: dict[str, str | None],
) -> SyntaxDocument:
    """Build safe dependency facts from one already-read permitted manifest."""
    dependency_records: list[tuple[str, str | None, str | None, bool]] = []
    if manifest_type == "package_json":
        data = json.loads(content.decode("utf-8"))
        if isinstance(data, dict):
            for section in ("dependencies", "devDependencies", "peerDependencies"):
                values = data.get(section)
                if isinstance(values, dict):
                    dependency_records.extend(
                        (
                            str(name).lower().strip(),
                            str(version).strip() if version else None,
                            section,
                            section == "devDependencies",
                        )
                        for name, version in values.items()
                    )
    else:
        dependency_records.extend(
            (name, version, "runtime", False) for name, version in dependencies.items()
        )
    facts = tuple(
        ManifestFact(
            fact_key=build_fact_key(
                path,
                "manifest_dependency",
                f"{manifest_type}:{scope}:{name}",
                None,
            ),
            manifest_type=manifest_type,
            name=name,
            version=version,
            scope=scope,
            is_dev=is_dev,
            raw_key=name,
            range=None,
        )
        for name, version, scope, is_dev in sorted(
            dependency_records,
            key=lambda record: (record[2] or "", record[0], record[1] or ""),
        )
    )
    return SyntaxDocument(
        artifact_id=artifact.id,
        path=path,
        content_hash=artifact.content_hash,
        language=manifest_type,
        language_version=None,
        parser_adapter_id="safe-manifest",
        parser_adapter_version="1.0.0",
        grammar_abi_version=None,
        parse_status=ParseStatus.PARSED,
        encoding_metadata=SourceEncodingMetadata(
            detected_encoding="utf-8",
            has_bom=False,
            line_count=content.count(b"\n") + 1,
            byte_count=len(content),
            is_utf8_clean=True,
        ),
        facts=sort_facts(facts),
        diagnostic_ids=(),
    )
