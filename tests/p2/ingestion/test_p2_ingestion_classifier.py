"""Classification pipeline unit tests."""

from backend.platform.ingestion.application.classifier import (
    ArtifactClassifier,
)
from backend.platform.ingestion.domain.constants import (
    ArtifactCategory,
    SupportLevel,
)


def test_classifier_build_cache_and_ignored() -> None:
    classifier = ArtifactClassifier()
    cases = [
        (
            "node_modules/express/index.js",
            ArtifactCategory.BUILD_CACHE_ARTIFACTS,
            SupportLevel.IGNORED,
        ),
        (
            ".git/objects/01/abcdef",
            ArtifactCategory.BUILD_CACHE_ARTIFACTS,
            SupportLevel.IGNORED,
        ),
        (
            "src/__pycache__/app.cpython-314.pyc",
            ArtifactCategory.BUILD_CACHE_ARTIFACTS,
            SupportLevel.IGNORED,
        ),
        (
            "venv/bin/activate",
            ArtifactCategory.BUILD_CACHE_ARTIFACTS,
            SupportLevel.IGNORED,
        ),
        (
            "dist/bundle.js",
            ArtifactCategory.BUILD_CACHE_ARTIFACTS,
            SupportLevel.IGNORED,
        ),
        (
            "build/app.min.js",
            ArtifactCategory.BUILD_CACHE_ARTIFACTS,
            SupportLevel.IGNORED,
        ),
        (
            "static/main.min.js",
            ArtifactCategory.GENERATED_ARTIFACTS,
            SupportLevel.IGNORED,
        ),
        (
            "static/main.min.css",
            ArtifactCategory.GENERATED_ARTIFACTS,
            SupportLevel.IGNORED,
        ),
    ]

    for path, expected_cat, expected_support in cases:
        cat, support = classifier.classify(path, size_bytes=100)
        assert cat == expected_cat, f"Mismatch for {path}"
        assert support == expected_support, f"Mismatch for {path}"


def test_classifier_secrets_and_locks() -> None:
    classifier = ArtifactClassifier()
    cases = [
        (".env", ArtifactCategory.ENVIRONMENT_SECRETS, SupportLevel.METADATA),
        (
            ".env.production",
            ArtifactCategory.ENVIRONMENT_SECRETS,
            SupportLevel.METADATA,
        ),
        (
            "keys/server.key",
            ArtifactCategory.ENVIRONMENT_SECRETS,
            SupportLevel.METADATA,
        ),
        ("id_rsa", ArtifactCategory.ENVIRONMENT_SECRETS, SupportLevel.METADATA),
        (
            "package-lock.json",
            ArtifactCategory.DEPENDENCY_METADATA,
            SupportLevel.METADATA,
        ),
        ("poetry.lock", ArtifactCategory.DEPENDENCY_METADATA, SupportLevel.METADATA),
    ]

    for path, expected_cat, expected_support in cases:
        cat, support = classifier.classify(path, size_bytes=100)
        assert cat == expected_cat
        assert support == expected_support


def test_classifier_source_and_markup() -> None:
    classifier = ArtifactClassifier()
    cases = [
        ("src/main.py", ArtifactCategory.SOURCE_CODE, SupportLevel.FULL),
        ("src/index.ts", ArtifactCategory.SOURCE_CODE, SupportLevel.FULL),
        ("backend/server.go", ArtifactCategory.SOURCE_CODE, SupportLevel.FULL),
        ("lib/core.rs", ArtifactCategory.SOURCE_CODE, SupportLevel.FULL),
        ("templates/index.html", ArtifactCategory.MARKUP_UI, SupportLevel.FULL),
        ("styles/main.css", ArtifactCategory.MARKUP_UI, SupportLevel.FULL),
        ("components/App.vue", ArtifactCategory.MARKUP_UI, SupportLevel.FULL),
    ]

    for path, expected_cat, expected_support in cases:
        cat, support = classifier.classify(path, size_bytes=100)
        assert cat == expected_cat
        assert support == expected_support


def test_classifier_tests_and_architecture() -> None:
    classifier = ArtifactClassifier()
    cases = [
        ("tests/unit/test_app.py", ArtifactCategory.TESTS, SupportLevel.FULL),
        ("src/components/button.spec.ts", ArtifactCategory.TESTS, SupportLevel.FULL),
        ("docs/system.drawio", ArtifactCategory.ARCHITECTURE_ASSETS, SupportLevel.FULL),
        ("diagrams/arch.puml", ArtifactCategory.ARCHITECTURE_ASSETS, SupportLevel.FULL),
        ("docs/flow.mermaid", ArtifactCategory.ARCHITECTURE_ASSETS, SupportLevel.FULL),
    ]

    for path, expected_cat, expected_support in cases:
        cat, support = classifier.classify(path, size_bytes=100)
        assert cat == expected_cat
        assert support == expected_support


def test_classifier_large_file_size_check() -> None:
    classifier = ArtifactClassifier()
    # Normal file under 5MB
    cat, support = classifier.classify("src/big.py", size_bytes=2 * 1024 * 1024)
    assert cat == ArtifactCategory.SOURCE_CODE
    assert support == SupportLevel.FULL

    # File exceeding 5MB limit
    cat_large, support_large = classifier.classify(
        "src/giant.py", size_bytes=6 * 1024 * 1024
    )
    assert cat_large == ArtifactCategory.SOURCE_CODE
    assert support_large == SupportLevel.UNSUPPORTED
