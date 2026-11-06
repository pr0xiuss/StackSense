"""Tests for F2 contracts, models, source range coordinates, and invariants."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from backend.platform.analysis.inspection.model import (
    ArtifactAnalysisRole,
    ArtifactInventoryEntry,
    ArtifactProcessingOutcome,
    InspectionCoverage,
    RepositoryInspectionResult,
)
from backend.platform.analysis.syntax.model import (
    DeclarationFact,
    DeclarationKind,
    ImportFact,
    ImportKind,
    ParseStatus,
    ReferenceFact,
    ReferenceKind,
    SourceEncodingMetadata,
    SourceRange,
    SyntaxDocument,
    build_fact_key,
    sort_facts,
)


def test_artifact_analysis_role_enum_and_failed_rejection() -> None:
    """Verify role vocabulary and invariant that 'failed' is rejected as a role."""
    valid_roles = {
        ArtifactAnalysisRole.SEMANTIC,
        ArtifactAnalysisRole.CONFIGURATION,
        ArtifactAnalysisRole.DOCUMENTATION,
        ArtifactAnalysisRole.METADATA_ONLY,
        ArtifactAnalysisRole.IGNORED,
        ArtifactAnalysisRole.UNSUPPORTED,
    }
    assert len(valid_roles) == 6
    assert ArtifactAnalysisRole("semantic") == ArtifactAnalysisRole.SEMANTIC
    assert ArtifactAnalysisRole("ignored") == ArtifactAnalysisRole.IGNORED

    # Invariant: 'failed' is strictly an outcome, never an analysis role
    with pytest.raises(
        ValueError, match="Invariant violation.*'failed' is a processing outcome"
    ):
        ArtifactAnalysisRole("failed")


def test_artifact_processing_outcome_enum() -> None:
    """Verify processing outcome vocabulary."""
    valid_outcomes = {
        ArtifactProcessingOutcome.NOT_PROCESSED,
        ArtifactProcessingOutcome.ANALYZED,
        ArtifactProcessingOutcome.ANALYZED_WITH_WARNINGS,
        ArtifactProcessingOutcome.EXCLUDED,
        ArtifactProcessingOutcome.UNSUPPORTED,
        ArtifactProcessingOutcome.FAILED,
    }
    assert len(valid_outcomes) == 6
    assert ArtifactProcessingOutcome("failed") == ArtifactProcessingOutcome.FAILED
    assert ArtifactProcessingOutcome("analyzed") == ArtifactProcessingOutcome.ANALYZED


def test_source_range_validation_and_contains() -> None:
    """Verify SourceRange invariants and spatial containment."""
    outer = SourceRange(
        start_byte=10,
        end_byte=100,
        start_line=2,
        end_line=10,
        start_column=0,
        end_column=20,
    )
    inner = SourceRange(
        start_byte=20,
        end_byte=50,
        start_line=3,
        end_line=5,
        start_column=4,
        end_column=15,
    )
    disjoint = SourceRange(
        start_byte=150,
        end_byte=200,
        start_line=15,
        end_line=20,
        start_column=0,
        end_column=10,
    )

    assert outer.contains(inner) is True
    assert outer.contains(outer) is True
    assert outer.contains(disjoint) is False

    # Invalid byte boundaries
    with pytest.raises(ValueError, match="Invalid byte range"):
        SourceRange(
            start_byte=50,
            end_byte=10,
            start_line=1,
            end_line=1,
            start_column=0,
            end_column=10,
        )

    # Invalid line boundaries
    with pytest.raises(ValueError, match="Invalid line range"):
        SourceRange(
            start_byte=0,
            end_byte=10,
            start_line=0,
            end_line=1,
            start_column=0,
            end_column=10,
        )

    # Inverted columns on same line
    with pytest.raises(ValueError, match="Invalid column ordering"):
        SourceRange(
            start_byte=0,
            end_byte=10,
            start_line=2,
            end_line=2,
            start_column=15,
            end_column=5,
        )


def test_fact_key_derivation_and_sorting() -> None:
    """Verify deterministic fact keys and ordering."""
    r1 = SourceRange(
        start_byte=10,
        end_byte=30,
        start_line=1,
        end_line=2,
        start_column=0,
        end_column=10,
    )
    r2 = SourceRange(
        start_byte=40,
        end_byte=80,
        start_line=3,
        end_line=5,
        start_column=0,
        end_column=20,
    )

    key1 = build_fact_key("src/app.py", "decl_func", "main", r1)
    key2 = build_fact_key("src/app.py", "decl_class", "App", r2)

    assert key1 == "src/app.py::decl_func::main::10_30"
    assert key2 == "src/app.py::decl_class::App::40_80"

    fact1 = DeclarationFact(
        fact_key=key1,
        kind=DeclarationKind.FUNCTION,
        name="main",
        qualified_name=None,
        container_key=None,
        modifiers=(),
        decorators=(),
        signature_text=None,
        declaration_range=r1,
        name_range=r1,
    )
    fact2 = DeclarationFact(
        fact_key=key2,
        kind=DeclarationKind.CLASS,
        name="App",
        qualified_name=None,
        container_key=None,
        modifiers=(),
        decorators=(),
        signature_text=None,
        declaration_range=r2,
        name_range=r2,
    )

    # Sorted by start_byte, end_byte, kind, fact_key
    sorted_facts = sort_facts([fact2, fact1])
    assert sorted_facts == (fact1, fact2)


def test_syntax_document_immutability_and_sorting() -> None:
    """Verify SyntaxDocument is immutable and enforces sorted facts."""
    r1 = SourceRange(
        start_byte=0,
        end_byte=20,
        start_line=1,
        end_line=1,
        start_column=0,
        end_column=20,
    )
    r2 = SourceRange(
        start_byte=30,
        end_byte=50,
        start_line=2,
        end_line=2,
        start_column=0,
        end_column=20,
    )

    f1 = ImportFact(
        fact_key="foo::import::os::0_20",
        kind=ImportKind.MODULE,
        source_module="os",
        relative_level=0,
        imported_name=None,
        local_alias=None,
        is_type_only=False,
        is_commonjs=False,
        range=r1,
    )
    f2 = ReferenceFact(
        fact_key="foo::call::get::30_50",
        kind=ReferenceKind.CALL,
        source_declaration_key=None,
        target_name="get",
        range=r2,
    )

    doc = SyntaxDocument(
        artifact_id=uuid4(),
        path="src/index.py",
        content_hash="hash123",
        language="python",
        language_version="3.14.7",
        parser_adapter_id="python-ast",
        parser_adapter_version="1.0.0",
        grammar_abi_version=None,
        parse_status=ParseStatus.PARSED,
        encoding_metadata=SourceEncodingMetadata(
            detected_encoding="utf-8",
            has_bom=False,
            line_count=2,
            byte_count=50,
            is_utf8_clean=True,
        ),
        facts=(f2, f1),  # Unsorted input
        diagnostic_ids=(),
    )

    # __post_init__ normalizes facts to sorted order
    assert doc.facts == (f1, f2)

    # Frozen verification
    with pytest.raises(FrozenInstanceError):
        doc.path = "new_path.py"  # type: ignore[misc]


def test_repository_inspection_result_canonical_json_and_immutability() -> None:
    """Verify root inspection result structure, version, and serialization."""
    analysis_id = uuid4()
    project_id = uuid4()
    repo_id = uuid4()
    snap_id = uuid4()
    art_id = uuid4()

    entry = ArtifactInventoryEntry(
        artifact_id=art_id,
        revision_id=snap_id,
        path="src/main.py",
        content_hash="abc",
        size_bytes=100,
        original_category="source_code",
        original_support_level="full",
        detected_language="python",
        is_test=False,
        is_generated=False,
        is_sensitive=False,
        analysis_role=ArtifactAnalysisRole.SEMANTIC,
        processing_outcome=ArtifactProcessingOutcome.ANALYZED,
        reason_codes=("supported_source",),
    )

    coverage = InspectionCoverage(
        total_artifacts=1,
        total_bytes=100,
        role_counts={"semantic": 1},
        outcome_counts={"analyzed": 1},
        language_counts={"python": 1},
        processed_artifacts=1,
        failed_artifacts=0,
    )

    res = RepositoryInspectionResult(
        analysis_id=analysis_id,
        project_id=project_id,
        repository_id=repo_id,
        snapshot_id=snap_id,
        analyzer_version="0.1.0",
        configuration_fingerprint="fp123",
        inventory=(entry,),
        syntax_documents=(),
        coverage=coverage,
        f2_version="1.0.0",
    )

    assert res.f2_version == "1.0.0"

    # Canonical JSON serialization
    canon_json = res.to_canonical_json()
    assert isinstance(canon_json, str)
    parsed = json.loads(canon_json)
    assert parsed["f2_version"] == "1.0.0"
    assert parsed["analysis_id"] == str(analysis_id)
    assert parsed["inventory"][0]["path"] == "src/main.py"
    assert parsed["inventory"][0]["analysis_role"] == "semantic"
    assert parsed["inventory"][0]["processing_outcome"] == "analyzed"

    with pytest.raises(TypeError):
        coverage.role_counts["semantic"] = 2  # type: ignore[index]

    # Incompatible version rejection
    with pytest.raises(ValueError, match="Unsupported F2 contract version"):
        RepositoryInspectionResult(
            analysis_id=analysis_id,
            project_id=project_id,
            repository_id=repo_id,
            snapshot_id=snap_id,
            analyzer_version="0.1.0",
            configuration_fingerprint="fp123",
            inventory=(entry,),
            syntax_documents=(),
            coverage=coverage,
            f2_version="0.9.0",
        )
