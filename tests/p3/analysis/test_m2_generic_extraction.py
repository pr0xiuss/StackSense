"""Batch 3 generic extraction, caps, determinism, and partial-failure tests."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from backend.platform.analysis.domain.analysis import AnalysisConfiguration
from backend.platform.analysis.domain.input import (
    AnalysisArtifact,
    AnalysisInput,
    ArtifactCatalog,
    ArtifactContentReader,
)
from backend.platform.analysis.inspection.model import ArtifactProcessingOutcome
from backend.platform.analysis.inspection.service import RepositoryInspectionService
from backend.platform.analysis.syntax.base import ParserRequest, ParserResult
from backend.platform.analysis.syntax.javascript import TreeSitterJsTsAdapter
from backend.platform.analysis.syntax.model import (
    DeclarationFact,
    DeclarationKind,
    ExportFact,
    ExportKind,
    ImportFact,
    ImportKind,
    ParseStatus,
    ReferenceFact,
    ReferenceKind,
)
from backend.platform.analysis.syntax.python import PythonAstAdapter
from backend.platform.ingestion.domain.constants import ArtifactCategory, SupportLevel


def test_python_generic_extraction_has_containers_and_structural_references() -> None:
    source = (
        b"from .base import Base as Parent\r\n"
        b"import os\r\n"
        b'__all__ = ["Child"]\r\n'
        b"CONSTANT: int = 1\r\n"
        b"@registry.model(token='never-retained')\r\n"
        b"class Child(Base):\r\n"
        b"    @audit.trace(secret='never-retained')\r\n"
        b"    async def save(self, value: str) -> bool:\r\n"
        b"        return bool(self.persist(value))\r\n"
    )
    result = PythonAstAdapter().parse(
        ParserRequest(uuid4(), "src/models.py", source, "python")
    )

    assert result.success is True
    assert result.document is not None
    facts = result.document.facts
    declarations = [fact for fact in facts if isinstance(fact, DeclarationFact)]
    by_name = {fact.name: fact for fact in declarations}
    assert by_name["src.models"].kind == DeclarationKind.MODULE
    assert by_name["Child"].qualified_name == "src.models.Child"
    assert by_name["save"].kind == DeclarationKind.METHOD
    assert by_name["save"].container_key == by_name["Child"].fact_key
    assert by_name["save"].signature_text == "(self, value: str) -> bool"
    assert by_name["CONSTANT"].modifiers == ("constant",)
    assert by_name["Child"].decorators == ("registry.model",)
    assert by_name["save"].decorators == ("audit.trace",)

    imports = [fact for fact in facts if isinstance(fact, ImportFact)]
    assert any(
        fact.source_module == "base"
        and fact.imported_name == "Base"
        and fact.local_alias == "Parent"
        and fact.relative_level == 1
        for fact in imports
    )
    exports = [fact for fact in facts if isinstance(fact, ExportFact)]
    assert any(
        fact.kind == ExportKind.NAMED and fact.exported_name == "Child"
        for fact in exports
    )
    references = [fact for fact in facts if isinstance(fact, ReferenceFact)]
    assert any(
        fact.kind == ReferenceKind.INHERITANCE and fact.target_name == "Base"
        for fact in references
    )
    assert any(
        fact.kind == ReferenceKind.CALL
        and fact.target_name == "self.persist"
        and fact.source_declaration_key == by_name["save"].fact_key
        for fact in references
    )
    assert "never-retained" not in str(facts)


def test_tsx_generic_extraction_covers_import_export_and_react_forms() -> None:
    source = b"""import React, {type FC, Header as PageHeader} from "react";
import * as helpers from "./helpers";
import "./side-effect";
const legacy = require("legacy");
@sealed
export abstract class Child extends Base implements Face {
  @trace()
  static async run() { return helpers.run(); }
}
export interface Contract extends Parent {}
export type Alias = string;
export const App = () => <PageHeader />;
export { Child as Renamed } from "./child";
export * from "./all";
export default App;
module.exports = App;
"""
    result = TreeSitterJsTsAdapter().parse(
        ParserRequest(uuid4(), "src/App.tsx", source, "tsx")
    )

    assert result.success is True
    assert result.document is not None
    facts = result.document.facts
    declarations = [fact for fact in facts if isinstance(fact, DeclarationFact)]
    by_name = {fact.name: fact for fact in declarations}
    assert by_name["Child"].kind == DeclarationKind.CLASS
    assert by_name["run"].kind == DeclarationKind.METHOD
    assert by_name["run"].container_key == by_name["Child"].fact_key
    assert by_name["Child"].decorators == ("sealed",)
    assert by_name["run"].decorators == ("trace",)
    assert by_name["Contract"].kind == DeclarationKind.INTERFACE
    assert by_name["Alias"].kind == DeclarationKind.TYPE_ALIAS
    assert by_name["App"].kind == DeclarationKind.REACT_COMPONENT

    imports = [fact for fact in facts if isinstance(fact, ImportFact)]
    assert {fact.kind for fact in imports} >= {
        ImportKind.DEFAULT,
        ImportKind.NAMED,
        ImportKind.ALL,
        ImportKind.SIDE_EFFECT,
        ImportKind.MODULE,
    }
    assert any(fact.is_type_only and fact.imported_name == "FC" for fact in imports)
    assert any(fact.is_commonjs and fact.source_module == "legacy" for fact in imports)

    exports = [fact for fact in facts if isinstance(fact, ExportFact)]
    assert {fact.kind for fact in exports} >= {
        ExportKind.NAMED,
        ExportKind.DEFAULT,
        ExportKind.ALL,
        ExportKind.RE_EXPORT,
    }
    assert any(fact.is_commonjs for fact in exports)
    references = [fact for fact in facts if isinstance(fact, ReferenceFact)]
    assert any(fact.kind == ReferenceKind.INHERITANCE for fact in references)
    assert any(fact.kind == ReferenceKind.DECORATOR for fact in references)
    assert any(
        fact.kind == ReferenceKind.DECORATOR
        and fact.target_name == "trace"
        and fact.source_declaration_key == by_name["run"].fact_key
        for fact in references
    )
    assert any(
        fact.kind == ReferenceKind.REACT_COMPOSITION
        and fact.target_name == "PageHeader"
        and fact.source_declaration_key == by_name["App"].fact_key
        for fact in references
    )


def test_per_artifact_fact_cap_is_atomic_for_both_parser_families() -> None:
    cases = (
        (PythonAstAdapter(), "python", b"def one(): pass\ndef two(): pass\n"),
        (
            TreeSitterJsTsAdapter(),
            "javascript",
            b"function one() {}\nfunction two() {}\n",
        ),
    )
    for adapter, language, content in cases:
        result = adapter.parse(
            ParserRequest(
                uuid4(),
                f"src/capped.{language}",
                content,
                language,
                max_facts_per_artifact=1,
            )
        )
        assert result.document is not None
        assert result.document.parse_status == ParseStatus.FAILED
        assert result.document.facts == ()
        assert [diagnostic.code for diagnostic in result.diagnostics] == [
            "resource_limit_exceeded"
        ]


class _MemoryReader(ArtifactContentReader):
    def __init__(self, content: dict[UUID, bytes]) -> None:
        self.content = content

    def read_bytes(
        self, artifact: AnalysisArtifact, max_bytes: int | None = None
    ) -> bytes:
        value = self.content[artifact.id]
        if max_bytes is not None and len(value) > max_bytes:
            raise ValueError("bounded reader limit exceeded")
        return value

    def open_stream(self, artifact: AnalysisArtifact):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def exists(self, artifact: AnalysisArtifact) -> bool:
        return artifact.id in self.content


@dataclass
class _InProcessExecutor:
    calls: int = 0

    def execute(self, request: ParserRequest) -> ParserResult:
        self.calls += 1
        if request.language == "python":
            return PythonAstAdapter().parse(request)
        return TreeSitterJsTsAdapter().parse(request)


def _analysis_input(files: tuple[tuple[str, bytes], ...]) -> AnalysisInput:
    revision_id = uuid4()
    artifacts = tuple(
        AnalysisArtifact(
            id=uuid4(),
            revision_id=revision_id,
            path=path,
            size_bytes=len(content),
            content_hash=f"hash-{index}",
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
        )
        for index, (path, content) in enumerate(files)
    )
    content = {
        artifact.id: file_content
        for artifact, (_, file_content) in zip(artifacts, files, strict=True)
    }
    return AnalysisInput(
        analysis_id=uuid4(),
        project_id=uuid4(),
        repository_id=uuid4(),
        snapshot_id=revision_id,
        revision_identifier="main",
        source_hash="source-hash",
        total_files=len(artifacts),
        total_bytes=sum(len(value) for value in content.values()),
        effective_configuration=AnalysisConfiguration(),
        artifact_catalog=ArtifactCatalog(artifacts),
        content_reader=_MemoryReader(content),
    )


def test_repository_extraction_isolates_file_failure_and_finalizes_detection() -> None:
    analysis_input = _analysis_input(
        (
            ("src/broken.py", b"def broken(\n"),
            ("src/server.js", b'import express from "express";\nexpress();\n'),
        )
    )
    executor = _InProcessExecutor()
    service = RepositoryInspectionService(parser_executor=executor)  # type: ignore[arg-type]
    execution = service.inspect(analysis_input, configuration_fingerprint="config-v1")

    assert executor.calls == 2
    outcomes = {
        entry.path: entry.processing_outcome for entry in execution.result.inventory
    }
    assert outcomes["src/broken.py"] == ArtifactProcessingOutcome.FAILED
    assert outcomes["src/server.js"] == ArtifactProcessingOutcome.ANALYZED
    assert {document.path for document in execution.result.syntax_documents} == {
        "src/broken.py",
        "src/server.js",
    }
    express = next(
        item
        for item in execution.result.framework_detections
        if item.framework == "express"
    )
    assert express.status == "confirmed"
    assert any(signal == "syntax_import:express" for signal in express.evidence_signals)


def test_successful_repository_extraction_is_canonical_and_parses_once() -> None:
    analysis_input = _analysis_input(
        (
            ("src/component.jsx", b"export function App() { return <Header />; }\n"),
            ("src/model.py", b"class Model:\n    pass\n"),
        )
    )
    first_executor = _InProcessExecutor()
    second_executor = _InProcessExecutor()
    first = RepositoryInspectionService(
        parser_executor=first_executor  # type: ignore[arg-type]
    ).inspect(analysis_input, configuration_fingerprint="config-v1")
    second = RepositoryInspectionService(
        parser_executor=second_executor  # type: ignore[arg-type]
    ).inspect(analysis_input, configuration_fingerprint="config-v1")

    assert first_executor.calls == 2
    assert second_executor.calls == 2
    assert first.result.to_canonical_json() == second.result.to_canonical_json()
    component = next(
        fact
        for document in first.result.syntax_documents
        for fact in document.facts
        if isinstance(fact, DeclarationFact) and fact.name == "App"
    )
    assert component.kind == DeclarationKind.REACT_COMPONENT


def test_analysis_fact_and_serialized_caps_reject_result_atomically() -> None:
    analysis_input = _analysis_input(
        (
            ("src/a.py", b"def a():\n    return helper()\n"),
            ("src/b.py", b"def b():\n    return helper()\n"),
        )
    )
    for kwargs, reason in (
        ({"max_facts_per_analysis": 1}, "analysis_fact_limit_exceeded"),
        ({"max_serialized_f2_bytes": 128}, "serialized_f2_limit_exceeded"),
    ):
        service = RepositoryInspectionService(
            parser_executor=_InProcessExecutor(),  # type: ignore[arg-type]
            **kwargs,
        )
        execution = service.inspect(
            analysis_input, configuration_fingerprint="config-v1"
        )
        assert execution.result.syntax_documents == ()
        assert execution.result.coverage.failed_artifacts == 2
        assert all(reason in entry.reason_codes for entry in execution.result.inventory)
        assert any(
            diagnostic.code == "resource_limit_exceeded"
            for diagnostic in execution.diagnostics
        )
