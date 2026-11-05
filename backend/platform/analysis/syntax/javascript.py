"""JavaScript and TypeScript Tree-sitter parser adapter for Phase 3 Module 2."""

from __future__ import annotations

import hashlib
import time

import tree_sitter
import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from backend.platform.analysis.domain.constants import DiagnosticSeverity
from backend.platform.analysis.syntax.base import (
    ParserAdapter,
    ParserRequest,
    ParserResult,
    SourceEncodingError,
    create_parsing_diagnostic,
    normalize_source_encoding,
)
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
    SourceRange,
    SyntaxDocument,
    SyntaxFact,
    build_fact_key,
    sort_facts,
)


class TreeSitterJsTsAdapter(ParserAdapter):
    """Parser adapter for JS, TS, JSX, and TSX using official Tree-sitter grammars."""

    adapter_id = "tree-sitter-javascript-typescript"
    adapter_version = "0.25.2"
    supported_languages = ("javascript", "typescript", "jsx", "tsx")

    def __init__(self) -> None:
        self._languages: dict[str, Language] = {
            "javascript": Language(tree_sitter_javascript.language()),
            "jsx": Language(tree_sitter_javascript.language()),
            "typescript": Language(tree_sitter_typescript.language_typescript()),
            "tsx": Language(tree_sitter_typescript.language_tsx()),
        }

    def _get_parser(self, language: str) -> Parser:
        norm_lang = language.lower().strip()
        if norm_lang not in self._languages:
            raise ValueError(f"Unsupported language for JS/TS adapter: {language}")
        return Parser(self._languages[norm_lang])

    def parse(self, request: ParserRequest) -> ParserResult:
        """Parse JS/TS/JSX/TSX source content into a SyntaxDocument."""
        start_time = time.perf_counter()

        # Enforce pre-read file size ceiling
        if len(request.content) > request.max_file_size_bytes:
            diag = create_parsing_diagnostic(
                analysis_id=request.analysis_id,
                artifact_id=request.artifact_id,
                artifact_path=request.path,
                code="file_size_exceeded",
                message=(
                    f"Artifact exceeds maximum allowed size of "
                    f"{request.max_file_size_bytes} bytes"
                ),
                severity=DiagnosticSeverity.ERROR,
            )
            return ParserResult(
                success=False,
                document=None,
                diagnostics=(diag,),
                execution_time_seconds=time.perf_counter() - start_time,
                error_message="File size ceiling exceeded",
            )

        # Normalize encoding and validate strict UTF-8
        try:
            canonical_bytes, text, encoding_meta = normalize_source_encoding(
                request.content, request.language
            )
        except SourceEncodingError as exc:
            diag = create_parsing_diagnostic(
                analysis_id=request.analysis_id,
                artifact_id=request.artifact_id,
                artifact_path=request.path,
                code="source_decode_error",
                message=f"Strict UTF-8 decode failed: {exc}",
                severity=DiagnosticSeverity.ERROR,
            )
            return ParserResult(
                success=False,
                document=None,
                diagnostics=(diag,),
                execution_time_seconds=time.perf_counter() - start_time,
                error_message=str(exc),
            )

        content_hash = hashlib.sha256(canonical_bytes).hexdigest()

        try:
            parser = self._get_parser(request.language)
            tree = parser.parse(canonical_bytes)
        except Exception as exc:
            diag = create_parsing_diagnostic(
                analysis_id=request.analysis_id,
                artifact_id=request.artifact_id,
                artifact_path=request.path,
                code="parser_exception",
                message=f"Tree-sitter parser failure: {exc}",
                severity=DiagnosticSeverity.ERROR,
            )
            return ParserResult(
                success=False,
                document=None,
                diagnostics=(diag,),
                execution_time_seconds=time.perf_counter() - start_time,
                error_message=str(exc),
            )

        diagnostics_list = []
        parse_status = ParseStatus.PARSED

        # Check for syntax errors reported by tree-sitter
        if tree.root_node.has_error:
            parse_status = ParseStatus.PARSED_WITH_ERRORS
            diag = create_parsing_diagnostic(
                analysis_id=request.analysis_id,
                artifact_id=request.artifact_id,
                artifact_path=request.path,
                code="syntax_error_recoverable",
                message=(
                    "Source file contains recoverable syntax errors "
                    "identified by Tree-sitter"
                ),
                severity=DiagnosticSeverity.WARNING,
            )
            diagnostics_list.append(diag)

        def make_node_range(node: Node) -> SourceRange:
            return SourceRange(
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                start_column=node.start_point[1],
                end_column=node.end_point[1],
            )

        facts: list[SyntaxFact] = []

        # Iterative AST traversal using stack to prevent recursion depth issues
        stack: list[Node] = [tree.root_node]
        while stack:
            curr = stack.pop()
            node_type = curr.type

            if node_type in (
                "function_declaration",
                "method_definition",
                "arrow_function",
            ):
                name_node = curr.child_by_field_name("name")
                name = (
                    name_node.text.decode("utf-8")
                    if name_node and name_node.text
                    else "anonymous"
                )
                d_range = make_node_range(curr)
                n_range = make_node_range(name_node) if name_node else d_range
                fact_key = build_fact_key(request.path, "decl_function", name, d_range)
                kind = (
                    DeclarationKind.METHOD
                    if node_type == "method_definition"
                    else DeclarationKind.FUNCTION
                )
                facts.append(
                    DeclarationFact(
                        fact_key=fact_key,
                        kind=kind,
                        name=name,
                        qualified_name=None,
                        container_key=None,
                        modifiers=(),
                        decorators=(),
                        signature_text=None,
                        declaration_range=d_range,
                        name_range=n_range,
                    )
                )

            elif node_type == "class_declaration":
                name_node = curr.child_by_field_name("name")
                name = (
                    name_node.text.decode("utf-8")
                    if name_node and name_node.text
                    else "anonymous"
                )
                d_range = make_node_range(curr)
                n_range = make_node_range(name_node) if name_node else d_range
                fact_key = build_fact_key(request.path, "decl_class", name, d_range)
                facts.append(
                    DeclarationFact(
                        fact_key=fact_key,
                        kind=DeclarationKind.CLASS,
                        name=name,
                        qualified_name=None,
                        container_key=None,
                        modifiers=(),
                        decorators=(),
                        signature_text=None,
                        declaration_range=d_range,
                        name_range=n_range,
                    )
                )

            elif node_type == "interface_declaration":
                name_node = curr.child_by_field_name("name")
                name = (
                    name_node.text.decode("utf-8")
                    if name_node and name_node.text
                    else "anonymous"
                )
                d_range = make_node_range(curr)
                n_range = make_node_range(name_node) if name_node else d_range
                fact_key = build_fact_key(request.path, "decl_interface", name, d_range)
                facts.append(
                    DeclarationFact(
                        fact_key=fact_key,
                        kind=DeclarationKind.INTERFACE,
                        name=name,
                        qualified_name=None,
                        container_key=None,
                        modifiers=(),
                        decorators=(),
                        signature_text=None,
                        declaration_range=d_range,
                        name_range=n_range,
                    )
                )

            elif node_type == "type_alias_declaration":
                name_node = curr.child_by_field_name("name")
                name = (
                    name_node.text.decode("utf-8")
                    if name_node and name_node.text
                    else "anonymous"
                )
                d_range = make_node_range(curr)
                n_range = make_node_range(name_node) if name_node else d_range
                fact_key = build_fact_key(
                    request.path, "decl_type_alias", name, d_range
                )
                facts.append(
                    DeclarationFact(
                        fact_key=fact_key,
                        kind=DeclarationKind.TYPE_ALIAS,
                        name=name,
                        qualified_name=None,
                        container_key=None,
                        modifiers=(),
                        decorators=(),
                        signature_text=None,
                        declaration_range=d_range,
                        name_range=n_range,
                    )
                )

            elif node_type == "import_statement":
                source_node = curr.child_by_field_name("source")
                source_text = (
                    source_node.text.decode("utf-8").strip("\"'")
                    if source_node and source_node.text
                    else ""
                )
                r = make_node_range(curr)
                fact_key = build_fact_key(request.path, "import", source_text, r)
                facts.append(
                    ImportFact(
                        fact_key=fact_key,
                        kind=ImportKind.MODULE,
                        source_module=source_text,
                        relative_level=1 if source_text.startswith(".") else 0,
                        imported_name=None,
                        local_alias=None,
                        is_type_only=curr.type == "import_type",
                        is_commonjs=False,
                        range=r,
                    )
                )

            elif node_type == "export_statement":
                r = make_node_range(curr)
                fact_key = build_fact_key(request.path, "export", "export", r)
                facts.append(
                    ExportFact(
                        fact_key=fact_key,
                        kind=ExportKind.NAMED,
                        local_name=None,
                        exported_name="",
                        source_module=None,
                        is_type_only=False,
                        is_commonjs=False,
                        range=r,
                    )
                )

            elif node_type == "call_expression":
                func_node = curr.child_by_field_name("function")
                func_name = (
                    func_node.text.decode("utf-8")
                    if func_node and func_node.text
                    else ""
                )
                if func_name:
                    r = make_node_range(curr)
                    fact_key = build_fact_key(request.path, "call", func_name, r)
                    facts.append(
                        ReferenceFact(
                            fact_key=fact_key,
                            kind=ReferenceKind.CALL,
                            source_declaration_key=None,
                            target_name=func_name,
                            range=r,
                        )
                    )

            elif node_type in ("jsx_element", "jsx_self_closing_element"):
                opening_node = (
                    curr.child_by_field_name("open_tag")
                    or curr.child_by_field_name("opening_element")
                    if node_type == "jsx_element"
                    else curr
                )
                tag_name_node = (
                    opening_node.child_by_field_name("name") if opening_node else None
                )
                tag_name = (
                    tag_name_node.text.decode("utf-8")
                    if tag_name_node and tag_name_node.text
                    else ""
                )
                if tag_name and tag_name[0].isupper():
                    # React component composition
                    r = make_node_range(curr)
                    fact_key = build_fact_key(
                        request.path, "react_composition", tag_name, r
                    )
                    facts.append(
                        ReferenceFact(
                            fact_key=fact_key,
                            kind=ReferenceKind.REACT_COMPOSITION,
                            source_declaration_key=None,
                            target_name=tag_name,
                            range=r,
                        )
                    )

            # Push children in reverse order so they are popped in natural order
            for child in reversed(curr.children):
                stack.append(child)

        sorted_facts = sort_facts(facts)

        doc = SyntaxDocument(
            artifact_id=request.artifact_id,
            path=request.path,
            content_hash=content_hash,
            language=request.language,
            language_version=None,
            parser_adapter_id=self.adapter_id,
            parser_adapter_version=self.adapter_version,
            grammar_abi_version=int(tree_sitter.LANGUAGE_VERSION),
            parse_status=parse_status,
            encoding_metadata=encoding_meta,
            facts=sorted_facts,
            diagnostic_ids=tuple(str(d.id) for d in diagnostics_list),
        )

        return ParserResult(
            success=True,
            document=doc,
            diagnostics=tuple(diagnostics_list),
            execution_time_seconds=time.perf_counter() - start_time,
        )
