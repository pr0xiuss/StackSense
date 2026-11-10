"""Test helpers for Phase 3 Module 3 IR tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID, uuid4

from backend.platform.analysis.domain.constants import ANALYZER_VERSION
from backend.platform.analysis.inspection.model import (
    ArtifactAnalysisRole,
    ArtifactInventoryEntry,
    ArtifactProcessingOutcome,
    FrameworkDetection,
    InspectionCoverage,
    LanguageDetection,
    RepositoryInspectionResult,
    RuntimeDetection,
)
from backend.platform.analysis.syntax.model import (
    DeclarationFact,
    DeclarationKind,
    ExportFact,
    ExportKind,
    FrameworkFact,
    ImportFact,
    ImportKind,
    ManifestFact,
    ParseStatus,
    ReferenceFact,
    ReferenceKind,
    SourceEncodingMetadata,
    SourceRange,
    SyntaxDocument,
    SyntaxFact,
)
from backend.platform.ingestion.domain.constants import (
    ArtifactCategory,
    SupportLevel,
)


def create_mock_source_range(
    start_byte: int = 0,
    end_byte: int = 10,
    start_line: int = 1,
    end_line: int = 1,
    start_column: int = 0,
    end_column: int = 10,
) -> SourceRange:
    """Create a valid SourceRange coordinate tuple."""
    return SourceRange(
        start_byte=start_byte,
        end_byte=end_byte,
        start_line=start_line,
        end_line=end_line,
        start_column=start_column,
        end_column=end_column,
    )


def create_mock_inventory_entry(
    path: str = "src/main.py",
    artifact_id: UUID | None = None,
    revision_id: UUID | None = None,
    detected_language: str = "python",
    role: ArtifactAnalysisRole = ArtifactAnalysisRole.SEMANTIC,
    outcome: ArtifactProcessingOutcome = ArtifactProcessingOutcome.ANALYZED,
    category: ArtifactCategory = ArtifactCategory.SOURCE_CODE,
    support_level: SupportLevel = SupportLevel.FULL,
    size_bytes: int = 512,
    content_hash: str = "a" * 64,
) -> ArtifactInventoryEntry:
    """Create an ArtifactInventoryEntry for testing."""
    return ArtifactInventoryEntry(
        artifact_id=artifact_id or uuid4(),
        revision_id=revision_id or uuid4(),
        path=path,
        detected_language=detected_language,
        analysis_role=role,
        processing_outcome=outcome,
        original_category=category.value,
        original_support_level=support_level.value,
        size_bytes=size_bytes,
        content_hash=content_hash,
        is_test=False,
        is_generated=False,
        is_sensitive=False,
        reason_codes=(),
    )


def create_mock_declaration_fact(
    fact_key: str = "decl::1",
    name: str = "foo",
    kind: DeclarationKind = DeclarationKind.FUNCTION,
    qualified_name: str | None = None,
    container_key: str | None = None,
    modifiers: tuple[str, ...] = (),
    decorators: tuple[str, ...] = (),
    signature_text: str | None = None,
    declaration_range: SourceRange | None = None,
    name_range: SourceRange | None = None,
) -> DeclarationFact:
    """Create a DeclarationFact with defaults."""
    decl_r = declaration_range or create_mock_source_range(0, 50)
    name_r = name_range or create_mock_source_range(4, 7)
    return DeclarationFact(
        fact_key=fact_key,
        kind=kind,
        name=name,
        qualified_name=qualified_name,
        container_key=container_key,
        modifiers=modifiers,
        decorators=decorators,
        signature_text=signature_text,
        declaration_range=decl_r,
        name_range=name_r,
    )


def create_mock_import_fact(
    fact_key: str = "imp::1",
    source_module: str = "os.path",
    kind: ImportKind = ImportKind.NAMED,
    relative_level: int = 0,
    imported_name: str | None = "join",
    local_alias: str | None = None,
    is_type_only: bool = False,
    is_commonjs: bool = False,
    range: SourceRange | None = None,
) -> ImportFact:
    """Create an ImportFact with defaults."""
    return ImportFact(
        fact_key=fact_key,
        kind=kind,
        source_module=source_module,
        relative_level=relative_level,
        imported_name=imported_name,
        local_alias=local_alias,
        is_type_only=is_type_only,
        is_commonjs=is_commonjs,
        range=range or create_mock_source_range(0, 20),
    )


def create_mock_export_fact(
    fact_key: str = "exp::1",
    exported_name: str = "foo",
    kind: ExportKind = ExportKind.NAMED,
    local_name: str | None = "foo",
    source_module: str | None = None,
    is_type_only: bool = False,
    is_commonjs: bool = False,
    range: SourceRange | None = None,
) -> ExportFact:
    """Create an ExportFact with defaults."""
    return ExportFact(
        fact_key=fact_key,
        kind=kind,
        local_name=local_name,
        exported_name=exported_name,
        source_module=source_module,
        is_type_only=is_type_only,
        is_commonjs=is_commonjs,
        range=range or create_mock_source_range(0, 20),
    )


def create_mock_reference_fact(
    fact_key: str = "ref::1",
    target_name: str = "bar",
    kind: ReferenceKind = ReferenceKind.CALL,
    source_declaration_key: str | None = None,
    range: SourceRange | None = None,
) -> ReferenceFact:
    """Create a ReferenceFact with defaults."""
    return ReferenceFact(
        fact_key=fact_key,
        kind=kind,
        source_declaration_key=source_declaration_key,
        target_name=target_name,
        range=range or create_mock_source_range(0, 20),
    )


def create_mock_manifest_fact(
    fact_key: str = "man::1",
    manifest_type: str = "package.json",
    name: str = "react",
    version: str | None = "^18.2.0",
    scope: str | None = None,
    is_dev: bool = False,
    raw_key: str = "dependencies.react",
    range: SourceRange | None = None,
) -> ManifestFact:
    """Create a ManifestFact with defaults."""
    return ManifestFact(
        fact_key=fact_key,
        manifest_type=manifest_type,
        name=name,
        version=version,
        scope=scope,
        is_dev=is_dev,
        raw_key=raw_key,
        range=range,
    )


def create_mock_framework_fact(
    fact_key: str = "fw::1",
    framework_name: str = "express",
    artifact_id: UUID | None = None,
    fact_type: str = "route",
    name: str = "GET /api/users",
    details: Mapping[str, object] | None = None,
    supporting_fact_keys: tuple[str, ...] = (),
    range: SourceRange | None = None,
) -> FrameworkFact:
    """Create a FrameworkFact with defaults."""
    return FrameworkFact(
        fact_key=fact_key,
        framework_name=framework_name,
        artifact_id=artifact_id or uuid4(),
        fact_type=fact_type,
        name=name,
        details=details or {},
        supporting_fact_keys=supporting_fact_keys,
        range=range,
    )


def create_mock_syntax_document(
    path: str = "src/main.py",
    language: str = "python",
    artifact_id: UUID | None = None,
    facts: Sequence[SyntaxFact] = (),
    declarations: Sequence[DeclarationFact] = (),
    imports: Sequence[ImportFact] = (),
    exports: Sequence[ExportFact] = (),
    references: Sequence[ReferenceFact] = (),
    framework_facts: Sequence[FrameworkFact] = (),
    manifest_facts: Sequence[ManifestFact] = (),
    parser_adapter_id: str = "mock-tree-sitter",
    parser_adapter_version: str = "1.0.0",
    grammar_abi_version: int | None = 14,
    parse_status: ParseStatus = ParseStatus.PARSED,
) -> SyntaxDocument:
    """Create a SyntaxDocument containing given facts."""
    all_facts = (
        *facts,
        *declarations,
        *imports,
        *exports,
        *references,
        *framework_facts,
        *manifest_facts,
    )
    return SyntaxDocument(
        artifact_id=artifact_id or uuid4(),
        path=path,
        content_hash="mock-content-hash",
        language=language,
        language_version=None,
        parser_adapter_id=parser_adapter_id,
        parser_adapter_version=parser_adapter_version,
        grammar_abi_version=grammar_abi_version,
        parse_status=parse_status,
        encoding_metadata=SourceEncodingMetadata(
            detected_encoding="utf-8",
            has_bom=False,
            line_count=10,
            byte_count=100,
            is_utf8_clean=True,
        ),
        facts=all_facts,
        diagnostic_ids=(),
    )


def create_mock_inspection_result(
    analysis_id: UUID | None = None,
    project_id: UUID | None = None,
    repository_id: UUID | None = None,
    snapshot_id: UUID | None = None,
    f2_version: str = "1.0.0",
    inventory: Sequence[ArtifactInventoryEntry] = (),
    syntax_documents: Sequence[SyntaxDocument] = (),
    language_detections: Sequence[LanguageDetection] = (),
    runtime_detections: Sequence[RuntimeDetection] = (),
    framework_detections: Sequence[FrameworkDetection] = (),
    config_fingerprint: str = "cfg-hash-test",
    analyzer_version: str = ANALYZER_VERSION,
    coverage: InspectionCoverage | None = None,
) -> RepositoryInspectionResult:
    """Create a synthetic F2 RepositoryInspectionResult for testing."""
    inv_tuple = tuple(inventory)
    failed = sum(
        1 for e in inv_tuple if e.processing_outcome == ArtifactProcessingOutcome.FAILED
    )
    mock_cov = coverage or InspectionCoverage(
        total_artifacts=len(inv_tuple),
        total_bytes=sum(e.size_bytes for e in inv_tuple),
        role_counts={},
        outcome_counts={},
        language_counts={},
        processed_artifacts=len(inv_tuple) - failed,
        failed_artifacts=failed,
    )
    return RepositoryInspectionResult(
        analysis_id=analysis_id or uuid4(),
        project_id=project_id or uuid4(),
        repository_id=repository_id or uuid4(),
        snapshot_id=snapshot_id or uuid4(),
        analyzer_version=analyzer_version,
        configuration_fingerprint=config_fingerprint,
        inventory=inv_tuple,
        syntax_documents=tuple(syntax_documents),
        coverage=mock_cov,
        f2_version=f2_version,
        language_detections=tuple(language_detections),
        runtime_detections=tuple(runtime_detections),
        framework_detections=tuple(framework_detections),
    )
