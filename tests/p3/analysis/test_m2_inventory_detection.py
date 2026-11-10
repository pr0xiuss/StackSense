"""Tests for M2 inventory building, exclusions, sensitive policy, and detection."""

from __future__ import annotations

import json
import random
from uuid import uuid4

import pytest

from backend.platform.analysis.domain.analysis import AnalysisConfiguration
from backend.platform.analysis.domain.input import (
    AnalysisArtifact,
    ArtifactContentReader,
)
from backend.platform.analysis.inspection.detection import (
    DetectionService,
)
from backend.platform.analysis.inspection.inventory import InventoryBuilder
from backend.platform.analysis.inspection.model import (
    ArtifactAnalysisRole,
    ArtifactProcessingOutcome,
    RepositoryInspectionResult,
)
from backend.platform.analysis.syntax.model import ManifestFact
from backend.platform.ingestion.domain.constants import ArtifactCategory, SupportLevel


class RecordingContentReader(ArtifactContentReader):
    """Test reader that records all accessed artifact paths."""

    def __init__(self, file_map: dict[str, bytes] | None = None) -> None:
        self.file_map = file_map or {}
        self.read_paths: list[str] = []

    def read_bytes(
        self, artifact: AnalysisArtifact, max_bytes: int | None = None
    ) -> bytes:
        self.read_paths.append(artifact.path)
        content = self.file_map.get(artifact.path, b"")
        if max_bytes is not None:
            return content[:max_bytes]
        return content

    def open_stream(self, artifact: AnalysisArtifact):
        raise NotImplementedError

    def exists(self, artifact: AnalysisArtifact) -> bool:
        return artifact.path in self.file_map


def test_inventory_builder_exhaustive_role_mapping() -> None:
    """Verify that every artifact receives exactly one valid role and separate
    outcome.
    """
    rev_id = uuid4()
    builder = InventoryBuilder()

    test_artifacts = [
        # 1. Supported Python source
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="src/app.py",
            size_bytes=100,
            content_hash="h1",
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
        ),
        # 2. Supported TypeScript test
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="tests/unit.test.ts",
            size_bytes=200,
            content_hash="h2",
            category=ArtifactCategory.TESTS,
            support_level=SupportLevel.FULL,
        ),
        # 3. Safe configuration / manifest
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="package.json",
            size_bytes=300,
            content_hash="h3",
            category=ArtifactCategory.DEPENDENCY_METADATA,
            support_level=SupportLevel.METADATA,
        ),
        # 4. Documentation
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="docs/README.md",
            size_bytes=400,
            content_hash="h4",
            category=ArtifactCategory.DOCUMENTATION,
            support_level=SupportLevel.METADATA,
        ),
        # 5. Build cache / node_modules
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="node_modules/pkg/index.js",
            size_bytes=500,
            content_hash="h5",
            category=ArtifactCategory.BUILD_CACHE_ARTIFACTS,
            support_level=SupportLevel.IGNORED,
        ),
        # 6. Binary artifact
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="assets/logo.png",
            size_bytes=600,
            content_hash="h6",
            category=ArtifactCategory.BINARY_ARTIFACTS,
            support_level=SupportLevel.UNSUPPORTED,
        ),
        # 7. Unsupported language (e.g. Java)
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="backend/Main.java",
            size_bytes=700,
            content_hash="h7",
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
        ),
    ]

    inventory, coverage = builder.build_inventory(test_artifacts)
    assert len(inventory) == 7

    roles_by_path = {e.path: (e.analysis_role, e.processing_outcome) for e in inventory}

    assert roles_by_path["src/app.py"] == (
        ArtifactAnalysisRole.SEMANTIC,
        ArtifactProcessingOutcome.NOT_PROCESSED,
    )
    assert roles_by_path["tests/unit.test.ts"] == (
        ArtifactAnalysisRole.SEMANTIC,
        ArtifactProcessingOutcome.NOT_PROCESSED,
    )
    assert roles_by_path["package.json"] == (
        ArtifactAnalysisRole.CONFIGURATION,
        ArtifactProcessingOutcome.NOT_PROCESSED,
    )
    assert roles_by_path["docs/README.md"] == (
        ArtifactAnalysisRole.DOCUMENTATION,
        ArtifactProcessingOutcome.NOT_PROCESSED,
    )
    assert roles_by_path["node_modules/pkg/index.js"] == (
        ArtifactAnalysisRole.IGNORED,
        ArtifactProcessingOutcome.EXCLUDED,
    )
    assert roles_by_path["assets/logo.png"] == (
        ArtifactAnalysisRole.IGNORED,
        ArtifactProcessingOutcome.EXCLUDED,
    )
    assert roles_by_path["backend/Main.java"] == (
        ArtifactAnalysisRole.UNSUPPORTED,
        ArtifactProcessingOutcome.UNSUPPORTED,
    )

    # Invariant: failed is never a role in any inventory entry
    for entry in inventory:
        assert entry.analysis_role != "failed"

    assert coverage.total_artifacts == 7
    assert coverage.role_counts["semantic"] == 2
    assert coverage.role_counts["configuration"] == 1
    assert coverage.role_counts["documentation"] == 1
    assert coverage.role_counts["ignored"] == 2
    assert coverage.role_counts["unsupported"] == 1


def test_sensitive_content_policy_and_zero_content_read() -> None:
    """Verify sensitive files (.env, keys, credentials) are never read and
    assigned METADATA_ONLY.
    """
    rev_id = uuid4()
    builder = InventoryBuilder()

    secret_artifacts = [
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path=".env",
            size_bytes=50,
            content_hash="s1",
            category=ArtifactCategory.ENVIRONMENT_SECRETS,
            support_level=SupportLevel.IGNORED,
        ),
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="config/credentials.json",
            size_bytes=120,
            content_hash="s2",
            category=ArtifactCategory.CONFIGURATION,
            support_level=SupportLevel.METADATA,
        ),
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="keys/id_rsa",
            size_bytes=1600,
            content_hash="s3",
            category=ArtifactCategory.ENVIRONMENT_SECRETS,
            support_level=SupportLevel.IGNORED,
        ),
    ]

    inventory, _ = builder.build_inventory(secret_artifacts)
    for entry in inventory:
        assert entry.is_sensitive is True
        assert entry.analysis_role == ArtifactAnalysisRole.METADATA_ONLY
        assert "prohibited_sensitive" in entry.reason_codes

    # Verify detection service never accesses content of sensitive artifacts
    reader = RecordingContentReader(
        {
            ".env": b"SECRET_KEY=leaked_password_123",
            "config/credentials.json": b'{"private_key": "raw_secret"}',
            "keys/id_rsa": b"-----BEGIN RSA PRIVATE KEY-----",
        }
    )
    detector = DetectionService()
    detector.detect_framework_candidates(
        secret_artifacts, inventory, content_reader=reader
    )

    # Content reader was NEVER called for sensitive files
    assert len(reader.read_paths) == 0


def test_user_exclusions_and_inclusions_precedence() -> None:
    """Verify include_paths and exclude_paths with gitwildmatch precedence."""
    rev_id = uuid4()
    config = AnalysisConfiguration(
        include_paths=("src/**", "tests/**"),
        exclude_paths=("src/legacy/**", "**/*.tmp"),
    )
    builder = InventoryBuilder(config)

    artifacts = [
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="src/main.py",
            size_bytes=100,
            content_hash="h1",
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
        ),
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="src/legacy/old.py",  # Excluded by exclude_paths
            size_bytes=100,
            content_hash="h2",
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
        ),
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="scripts/deploy.py",  # Outside include_paths
            size_bytes=100,
            content_hash="h3",
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
        ),
    ]

    inventory, _ = builder.build_inventory(artifacts)
    roles = {
        e.path: (e.analysis_role, e.processing_outcome, e.reason_codes)
        for e in inventory
    }

    assert roles["src/main.py"][0] == ArtifactAnalysisRole.SEMANTIC
    assert roles["src/legacy/old.py"][0] == ArtifactAnalysisRole.IGNORED
    assert "user_excluded" in roles["src/legacy/old.py"][2]

    assert roles["scripts/deploy.py"][0] == ArtifactAnalysisRole.IGNORED
    assert "not_included" in roles["scripts/deploy.py"][2]


def test_language_and_runtime_detection() -> None:
    """Verify multi-language and multi-runtime detection from metadata without
    source parsing.
    """
    rev_id = uuid4()
    builder = InventoryBuilder()
    detector = DetectionService()

    artifacts = [
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="backend/server.py",
            size_bytes=100,
            content_hash="h1",
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
        ),
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="frontend/src/index.tsx",
            size_bytes=200,
            content_hash="h2",
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
        ),
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="frontend/package.json",
            size_bytes=150,
            content_hash="h3",
            category=ArtifactCategory.DEPENDENCY_METADATA,
            support_level=SupportLevel.METADATA,
        ),
    ]

    inventory, _ = builder.build_inventory(artifacts)

    lang_detections = detector.detect_languages(inventory)
    langs = {d.path: d.language for d in lang_detections}
    assert langs["backend/server.py"] == "python"
    assert langs["frontend/src/index.tsx"] == "tsx"

    runtimes = detector.detect_runtimes(inventory)
    runtime_names = {r.runtime for r in runtimes}
    assert "python" in runtime_names
    assert "node" in runtime_names
    assert "browser" in runtime_names


def test_preliminary_framework_candidate_detection_from_manifests() -> None:
    """Verify preliminary detection of candidate frameworks from manifests and
    path signals.
    """
    rev_id = uuid4()
    builder = InventoryBuilder()
    detector = DetectionService()

    req_txt = "fastapi==0.110.0\nuvicorn>=0.28.0\n"
    pkg_json = json.dumps(
        {
            "name": "fullstack-app",
            "dependencies": {
                "express": "^4.19.2",
                "next": "^14.2.0",
                "react": "^18.2.0",
            },
            "devDependencies": {
                "@nestjs/core": "^10.3.0",
            },
            "private": True,
            "secret_env_not_leaked": "super_secret_token",
        }
    )

    artifacts = [
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="requirements.txt",
            size_bytes=len(req_txt),
            content_hash="h1",
            category=ArtifactCategory.DEPENDENCY_METADATA,
            support_level=SupportLevel.METADATA,
        ),
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="package.json",
            size_bytes=len(pkg_json),
            content_hash="h2",
            category=ArtifactCategory.DEPENDENCY_METADATA,
            support_level=SupportLevel.METADATA,
        ),
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="manage.py",
            size_bytes=20,
            content_hash="h3",
            category=ArtifactCategory.CONFIGURATION,
            support_level=SupportLevel.METADATA,
        ),
    ]

    reader = RecordingContentReader(
        {
            "requirements.txt": req_txt.encode("utf-8"),
            "package.json": pkg_json.encode("utf-8"),
            "manage.py": b"# django marker\n",
        }
    )

    inventory, _ = builder.build_inventory(artifacts)
    detections, evidence, diags = detector.detect_framework_candidates(
        artifacts, inventory, content_reader=reader
    )

    detected_frameworks = {d.framework: d for d in detections}

    assert "fastapi" in detected_frameworks
    assert detected_frameworks["fastapi"].version == "0.110.0"
    assert detected_frameworks["fastapi"].status == "candidate"

    assert "express" in detected_frameworks
    assert detected_frameworks["express"].version == "^4.19.2"
    assert detected_frameworks["express"].status == "candidate"

    assert "nextjs" in detected_frameworks
    assert detected_frameworks["nextjs"].version == "^14.2.0"

    assert "nestjs" in detected_frameworks
    assert detected_frameworks["nestjs"].version == "^10.3.0"

    assert "django" in detected_frameworks
    assert any(
        "manage.py" in sig for sig in detected_frameworks["django"].evidence_signals
    )


def test_inventory_determinism_shuffled_order() -> None:
    """Verify inventory building and serialization is strictly deterministic
    regardless of input order.
    """
    rev_id = uuid4()
    builder = InventoryBuilder()
    detector = DetectionService()

    artifacts = [
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path=f"src/file_{i:03d}.py",
            size_bytes=100 + i,
            content_hash=f"hash_{i}",
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
        )
        for i in range(20)
    ]

    inv1, cov1 = builder.build_inventory(artifacts)
    langs1 = detector.detect_languages(inv1)
    runtimes1 = detector.detect_runtimes(inv1)
    res1 = RepositoryInspectionResult(
        analysis_id=uuid4(),
        project_id=uuid4(),
        repository_id=uuid4(),
        snapshot_id=rev_id,
        analyzer_version="1.0.0",
        configuration_fingerprint="fingerprint_1",
        inventory=inv1,
        syntax_documents=(),
        coverage=cov1,
        language_detections=langs1,
        runtime_detections=runtimes1,
    )

    # Shuffle input list
    shuffled = list(artifacts)
    random.seed(42)
    random.shuffle(shuffled)

    inv2, cov2 = builder.build_inventory(shuffled)
    langs2 = detector.detect_languages(inv2)
    runtimes2 = detector.detect_runtimes(inv2)
    res2 = RepositoryInspectionResult(
        analysis_id=res1.analysis_id,
        project_id=res1.project_id,
        repository_id=res1.repository_id,
        snapshot_id=rev_id,
        analyzer_version="1.0.0",
        configuration_fingerprint="fingerprint_1",
        inventory=inv2,
        syntax_documents=(),
        coverage=cov2,
        language_detections=langs2,
        runtime_detections=runtimes2,
    )

    # Must be byte-identical in canonical JSON
    assert res1.to_canonical_json() == res2.to_canonical_json()
    assert [e.path for e in inv1] == [e.path for e in inv2]
    assert [e.path for e in inv1] == sorted([e.path for e in inv1])
    assert cov1 == cov2


def test_detection_and_evidence_determinism_shuffled_order() -> None:
    """Verify framework candidates, evidence signals, and full F2 inspection
    canonical JSON serialization are strictly deterministic across shuffled
    input orders.
    """
    rev_id = uuid4()
    builder = InventoryBuilder()
    detector = DetectionService()

    reader = RecordingContentReader(
        {
            "package.json": (
                b'{"dependencies": {"express": "^4.19.2", '
                b'"@nestjs/core": "^10.3.0", "next": "^14.2.0"}}'
            ),
            "requirements.txt": (b"fastapi==0.110.0\ndjango==5.0.3\nflask==3.0.2\n"),
        }
    )

    artifacts = [
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="package.json",
            size_bytes=150,
            content_hash="h_pkg",
            category=ArtifactCategory.DEPENDENCY_METADATA,
            support_level=SupportLevel.METADATA,
        ),
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="requirements.txt",
            size_bytes=100,
            content_hash="h_req",
            category=ArtifactCategory.DEPENDENCY_METADATA,
            support_level=SupportLevel.METADATA,
        ),
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="manage.py",
            size_bytes=200,
            content_hash="h_man",
            category=ArtifactCategory.CONFIGURATION,
            support_level=SupportLevel.FULL,
        ),
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="nest-cli.json",
            size_bytes=80,
            content_hash="h_nest",
            category=ArtifactCategory.CONFIGURATION,
            support_level=SupportLevel.FULL,
        ),
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="next.config.js",
            size_bytes=90,
            content_hash="h_next",
            category=ArtifactCategory.CONFIGURATION,
            support_level=SupportLevel.FULL,
        ),
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="src/server.py",
            size_bytes=300,
            content_hash="h_srv",
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
        ),
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="src/app.tsx",
            size_bytes=400,
            content_hash="h_tsx",
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
        ),
    ]

    # Run 1: Original order
    inv1, cov1 = builder.build_inventory(artifacts)
    langs1 = detector.detect_languages(inv1)
    runtimes1 = detector.detect_runtimes(inv1)
    fw1, ev1, diags1 = detector.detect_framework_candidates(
        artifacts, inv1, content_reader=reader
    )

    shared_analysis_id = uuid4()
    shared_proj_id = uuid4()
    shared_repo_id = uuid4()

    res1 = RepositoryInspectionResult(
        analysis_id=shared_analysis_id,
        project_id=shared_proj_id,
        repository_id=shared_repo_id,
        snapshot_id=rev_id,
        analyzer_version="1.0.0",
        configuration_fingerprint="fingerprint_det",
        inventory=inv1,
        syntax_documents=(),
        coverage=cov1,
        language_detections=langs1,
        runtime_detections=runtimes1,
        framework_detections=fw1,
    )

    # Run 2: Shuffled order
    shuffled = list(artifacts)
    random.seed(99)
    random.shuffle(shuffled)

    inv2, cov2 = builder.build_inventory(shuffled)
    langs2 = detector.detect_languages(inv2)
    runtimes2 = detector.detect_runtimes(inv2)
    fw2, ev2, diags2 = detector.detect_framework_candidates(
        shuffled, inv2, content_reader=reader
    )

    res2 = RepositoryInspectionResult(
        analysis_id=shared_analysis_id,
        project_id=shared_proj_id,
        repository_id=shared_repo_id,
        snapshot_id=rev_id,
        analyzer_version="1.0.0",
        configuration_fingerprint="fingerprint_det",
        inventory=inv2,
        syntax_documents=(),
        coverage=cov2,
        language_detections=langs2,
        runtime_detections=runtimes2,
        framework_detections=fw2,
    )

    # Verify identical detection, evidence, and canonical JSON byte equality
    assert fw1 == fw2
    assert [d.framework for d in fw1] == sorted([d.framework for d in fw1])
    assert ev1 == ev2
    assert [e.signal_code for e in ev1] == [e.signal_code for e in ev2]
    assert cov1 == cov2
    assert res1.to_canonical_json() == res2.to_canonical_json()
    assert res1.to_canonical_json().encode("utf-8") == res2.to_canonical_json().encode(
        "utf-8"
    )


def test_manifest_reads_gated_by_inventory_eligibility() -> None:
    """Verify that detect_framework_candidates never reads ineligible manifests
    such as third-party node_modules or user-excluded manifests.
    """
    rev_id = uuid4()
    config = AnalysisConfiguration(exclude_paths=("scripts/**",))
    builder = InventoryBuilder(config)
    detector = DetectionService()

    root_pkg = AnalysisArtifact(
        id=uuid4(),
        revision_id=rev_id,
        path="package.json",
        size_bytes=100,
        content_hash="h1",
        category=ArtifactCategory.DEPENDENCY_METADATA,
        support_level=SupportLevel.METADATA,
    )
    ignored_pkg = AnalysisArtifact(
        id=uuid4(),
        revision_id=rev_id,
        path="node_modules/express/package.json",
        size_bytes=500,
        content_hash="h2",
        category=ArtifactCategory.DEPENDENCY_METADATA,
        support_level=SupportLevel.METADATA,
    )
    excluded_pkg = AnalysisArtifact(
        id=uuid4(),
        revision_id=rev_id,
        path="scripts/package.json",
        size_bytes=200,
        content_hash="h3",
        category=ArtifactCategory.DEPENDENCY_METADATA,
        support_level=SupportLevel.METADATA,
    )

    all_artifacts = [root_pkg, ignored_pkg, excluded_pkg]
    inventory, _ = builder.build_inventory(all_artifacts)

    # Confirm roles in inventory
    inv_map = {e.path: e for e in inventory}
    assert inv_map["package.json"].analysis_role == ArtifactAnalysisRole.CONFIGURATION
    assert (
        inv_map["node_modules/express/package.json"].analysis_role
        == ArtifactAnalysisRole.IGNORED
    )
    assert inv_map["scripts/package.json"].analysis_role == ArtifactAnalysisRole.IGNORED

    reader = RecordingContentReader(
        {
            "package.json": b'{"dependencies": {"express": "^4.19.0"}}',
            "node_modules/express/package.json": b'{"name": "express"}',
            "scripts/package.json": b'{"name": "scripts"}',
        }
    )

    detections, evidence, diags = detector.detect_framework_candidates(
        all_artifacts, inventory, content_reader=reader
    )

    # Only root package.json must have been read!
    assert "package.json" in reader.read_paths
    assert "node_modules/express/package.json" not in reader.read_paths
    assert "scripts/package.json" not in reader.read_paths
    assert len(reader.read_paths) == 1
    assert any(d.framework == "express" for d in detections)


def test_malformed_manifest_emits_diagnostic() -> None:
    """Verify that unparseable or non-UTF8 manifests emit an AnalysisDiagnostic."""
    rev_id = uuid4()
    builder = InventoryBuilder()
    detector = DetectionService()

    bad_pkg = AnalysisArtifact(
        id=uuid4(),
        revision_id=rev_id,
        path="package.json",
        size_bytes=50,
        content_hash="h_bad",
        category=ArtifactCategory.DEPENDENCY_METADATA,
        support_level=SupportLevel.METADATA,
    )
    inventory, _ = builder.build_inventory([bad_pkg])

    reader = RecordingContentReader({"package.json": b"{this is not valid json;}"})

    detections, evidence, diags = detector.detect_framework_candidates(
        [bad_pkg], inventory, content_reader=reader
    )

    assert len(diags) == 1
    assert diags[0].code == "manifest_syntax_error"
    assert diags[0].artifact_path == "package.json"


def test_generated_artifacts_policy_excludes_generated_and_minified_code() -> None:
    """Verify that generated code, minified bundles, and GENERATED_ARTIFACTS
    category receive IGNORED role and are not treated as SEMANTIC.
    """
    rev_id = uuid4()
    builder = InventoryBuilder()

    artifacts = [
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="dist/bundle.min.js",
            size_bytes=5000,
            content_hash="h1",
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
        ),
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="src/generated_code.py",
            size_bytes=2000,
            content_hash="h2",
            category=ArtifactCategory.GENERATED_ARTIFACTS,
            support_level=SupportLevel.FULL,
        ),
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path="public/app.bundle.js",
            size_bytes=3000,
            content_hash="h3",
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
        ),
    ]

    inventory, _ = builder.build_inventory(artifacts)
    roles = {
        e.path: (e.analysis_role, e.processing_outcome, e.reason_codes)
        for e in inventory
    }

    assert roles["dist/bundle.min.js"][0] == ArtifactAnalysisRole.IGNORED
    assert roles["dist/bundle.min.js"][1] == ArtifactProcessingOutcome.EXCLUDED

    assert roles["src/generated_code.py"][0] == ArtifactAnalysisRole.IGNORED
    assert roles["src/generated_code.py"][1] == ArtifactProcessingOutcome.EXCLUDED
    assert "generated_code" in roles["src/generated_code.py"][2]

    assert roles["public/app.bundle.js"][0] == ArtifactAnalysisRole.IGNORED
    assert roles["public/app.bundle.js"][1] == ArtifactProcessingOutcome.EXCLUDED


def test_all_artifact_categories_mapping_matrix() -> None:
    """Verify exhaustive role mapping across all 16 ArtifactCategory values."""
    rev_id = uuid4()
    builder = InventoryBuilder()

    categories = [
        (
            ArtifactCategory.SOURCE_CODE,
            "src/service.py",
            ArtifactAnalysisRole.SEMANTIC,
        ),
        (
            ArtifactCategory.TESTS,
            "tests/test_service.py",
            ArtifactAnalysisRole.SEMANTIC,
        ),
        (
            ArtifactCategory.CONFIGURATION,
            "config/settings.yaml",
            ArtifactAnalysisRole.CONFIGURATION,
        ),
        (
            ArtifactCategory.DEPENDENCY_METADATA,
            "requirements.txt",
            ArtifactAnalysisRole.CONFIGURATION,
        ),
        (
            ArtifactCategory.INFRASTRUCTURE,
            "docker/Dockerfile",
            ArtifactAnalysisRole.CONFIGURATION,
        ),
        (
            ArtifactCategory.DATABASE_ARTIFACTS,
            "migrations/001.sql",
            ArtifactAnalysisRole.CONFIGURATION,
        ),
        (
            ArtifactCategory.DOCUMENTATION,
            "docs/README.md",
            ArtifactAnalysisRole.DOCUMENTATION,
        ),
        (
            ArtifactCategory.MARKUP_UI,
            "public/index.html",
            ArtifactAnalysisRole.METADATA_ONLY,
        ),
        (
            ArtifactCategory.ARCHITECTURE_ASSETS,
            "diagrams/arch.drawio",
            ArtifactAnalysisRole.METADATA_ONLY,
        ),
        (
            ArtifactCategory.DATA_FILES,
            "data/samples.csv",
            ArtifactAnalysisRole.METADATA_ONLY,
        ),
        (
            ArtifactCategory.ENVIRONMENT_SECRETS,
            ".env.production",
            ArtifactAnalysisRole.METADATA_ONLY,
        ),
        (
            ArtifactCategory.GENERATED_ARTIFACTS,
            "gen/stubs.py",
            ArtifactAnalysisRole.IGNORED,
        ),
        (
            ArtifactCategory.BUILD_CACHE_ARTIFACTS,
            ".cache/manifest",
            ArtifactAnalysisRole.IGNORED,
        ),
        (
            ArtifactCategory.BINARY_ARTIFACTS,
            "bin/app.dll",
            ArtifactAnalysisRole.IGNORED,
        ),
        (
            ArtifactCategory.IMAGES,
            "assets/logo.png",
            ArtifactAnalysisRole.IGNORED,
        ),
        (
            ArtifactCategory.UNKNOWN_UNSUPPORTED,
            "unknown.xyz",
            ArtifactAnalysisRole.UNSUPPORTED,
        ),
    ]

    artifacts = [
        AnalysisArtifact(
            id=uuid4(),
            revision_id=rev_id,
            path=path,
            size_bytes=100,
            content_hash=f"h_{cat.value}",
            category=cat,
            support_level=SupportLevel.FULL,
        )
        for cat, path, _ in categories
    ]

    inventory, _ = builder.build_inventory(artifacts)
    role_map = {e.path: e.analysis_role for e in inventory}

    for cat, path, expected_role in categories:
        assert (
            role_map[path] == expected_role
        ), f"Category {cat} mapped to {role_map[path]} instead of {expected_role}"


def test_invalid_or_duplicate_normalized_paths_are_rejected() -> None:
    """Inventory never aliases traversal, absolute, or duplicate paths."""
    revision_id = uuid4()

    def artifact(path: str) -> AnalysisArtifact:
        return AnalysisArtifact(
            id=uuid4(),
            revision_id=revision_id,
            path=path,
            size_bytes=1,
            content_hash="hash",
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
        )

    builder = InventoryBuilder()
    for unsafe_path in ("/etc/passwd", "../app.py", "src/../app.py", "C:\\app.py"):
        with pytest.raises(ValueError, match="path"):
            builder.build_inventory((artifact(unsafe_path),))

    duplicate = artifact("src/app.py")
    with pytest.raises(ValueError, match="duplicate normalized paths"):
        builder.build_inventory((duplicate, artifact("src/app.py")))


def test_inventory_enforces_m2_five_mib_ceiling_over_larger_f1_config() -> None:
    """The user-configurable F1 read bound cannot weaken M2's parser ceiling."""
    artifact = AnalysisArtifact(
        id=uuid4(),
        revision_id=uuid4(),
        path="src/large.py",
        size_bytes=(5 * 1024 * 1024) + 1,
        content_hash="large",
        category=ArtifactCategory.SOURCE_CODE,
        support_level=SupportLevel.FULL,
    )
    inventory, _ = InventoryBuilder(
        AnalysisConfiguration(max_file_size_bytes=50 * 1024 * 1024)
    ).build_inventory((artifact,))

    assert inventory[0].analysis_role == ArtifactAnalysisRole.METADATA_ONLY
    assert inventory[0].processing_outcome == ArtifactProcessingOutcome.EXCLUDED
    assert inventory[0].reason_codes == ("oversized_file",)


def test_ignored_artifacts_do_not_influence_runtime_or_framework_detection() -> None:
    """Build-cache path markers cannot create language/runtime/framework claims."""
    artifact = AnalysisArtifact(
        id=uuid4(),
        revision_id=uuid4(),
        path="node_modules/example/manage.py",
        size_bytes=10,
        content_hash="ignored",
        category=ArtifactCategory.SOURCE_CODE,
        support_level=SupportLevel.FULL,
    )
    inventory, _ = InventoryBuilder().build_inventory((artifact,))
    detector = DetectionService()

    assert detector.detect_languages(inventory) == ()
    assert detector.detect_runtimes(inventory) == ()
    frameworks, evidence, diagnostics = detector.detect_framework_candidates(
        (artifact,), inventory
    )
    assert frameworks == ()
    assert evidence == ()
    assert diagnostics == ()


def test_conflicting_manifest_versions_are_deterministic_and_explicit() -> None:
    """Conflicting dependency versions do not depend on artifact input order."""
    revision_id = uuid4()
    artifacts = [
        AnalysisArtifact(
            id=uuid4(),
            revision_id=revision_id,
            path=path,
            size_bytes=50,
            content_hash=path,
            category=ArtifactCategory.DEPENDENCY_METADATA,
            support_level=SupportLevel.METADATA,
        )
        for path in ("apps/a/package.json", "apps/b/package.json")
    ]
    reader = RecordingContentReader(
        {
            "apps/a/package.json": b'{"dependencies":{"express":"^4"}}',
            "apps/b/package.json": b'{"dependencies":{"express":"^5"}}',
        }
    )
    inventory, _ = InventoryBuilder().build_inventory(artifacts)
    detector = DetectionService()

    first = detector.detect_framework_candidates(artifacts, inventory, reader)
    second = detector.detect_framework_candidates(
        reversed(artifacts), inventory, reader
    )

    assert first == second
    express = next(item for item in first[0] if item.framework == "express")
    assert express.version is None
    assert any(item.polarity == "conflicting" for item in first[1])


def test_manifest_dependency_credentials_never_enter_f2() -> None:
    revision_id = uuid4()
    marker = "credential-marker"
    package = json.dumps(
        {
            "dependencies": {
                "express": f"https://user:{marker}@registry.invalid/express.tgz"
            }
        }
    ).encode()
    requirement = f"fastapi @ https://user:{marker}@example.invalid/pkg.whl\n".encode()
    artifacts = [
        AnalysisArtifact(
            id=uuid4(),
            revision_id=revision_id,
            path=path,
            size_bytes=len(content),
            content_hash=f"hash-{index}",
            category=ArtifactCategory.DEPENDENCY_METADATA,
            support_level=SupportLevel.METADATA,
        )
        for index, (path, content) in enumerate(
            (("package.json", package), ("requirements.txt", requirement))
        )
    ]
    reader = RecordingContentReader(
        {"package.json": package, "requirements.txt": requirement}
    )
    inventory, _ = InventoryBuilder().build_inventory(artifacts)
    manifests = []

    DetectionService().detect_framework_candidates(
        artifacts,
        inventory,
        content_reader=reader,
        manifest_documents=manifests,
    )

    rendered = repr(manifests)
    facts = [
        fact
        for document in manifests
        for fact in document.facts
        if isinstance(fact, ManifestFact)
    ]
    assert marker not in rendered
    assert "registry.invalid" not in rendered
    assert "example.invalid" not in rendered
    assert {(fact.name, fact.version) for fact in facts} == {
        ("express", None),
        ("fastapi", None),
    }
