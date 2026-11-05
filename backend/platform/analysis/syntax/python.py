"""Python built-in AST parser adapter for Phase 3 Module 2."""

from __future__ import annotations

import ast
import hashlib
import sys
import time

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


class PythonAstAdapter(ParserAdapter):
    """Parser adapter using Python's built-in `ast` module."""

    adapter_id = "python-ast"
    adapter_version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    supported_languages = ("python",)

    def parse(self, request: ParserRequest) -> ParserResult:
        """Parse Python source content into a SyntaxDocument."""
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

        # Normalize encoding and obtain canonical UTF-8 bytes and text
        try:
            canonical_bytes, text, encoding_meta = normalize_source_encoding(
                request.content, "python"
            )
        except SourceEncodingError as exc:
            diag = create_parsing_diagnostic(
                analysis_id=request.analysis_id,
                artifact_id=request.artifact_id,
                artifact_path=request.path,
                code="source_decode_error",
                message=f"Strict encoding decode failed: {exc}",
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

        # Parse AST using decoded text to prevent PEP 263 encoding header conflicts
        try:
            tree = ast.parse(text, filename=request.path)
        except SyntaxError as exc:
            diag = create_parsing_diagnostic(
                analysis_id=request.analysis_id,
                artifact_id=request.artifact_id,
                artifact_path=request.path,
                code="syntax_error",
                message=f"Python syntax error: {exc.msg}",
                severity=DiagnosticSeverity.ERROR,
                source_line=exc.lineno,
                source_column=exc.offset,
                details={"text": exc.text.strip() if exc.text else ""},
            )
            doc = SyntaxDocument(
                artifact_id=request.artifact_id,
                path=request.path,
                content_hash=content_hash,
                language="python",
                language_version=self.adapter_version,
                parser_adapter_id=self.adapter_id,
                parser_adapter_version=self.adapter_version,
                grammar_abi_version=None,
                parse_status=ParseStatus.FAILED,
                encoding_metadata=encoding_meta,
                facts=(),
                diagnostic_ids=(str(diag.id),),
            )
            return ParserResult(
                success=True,
                document=doc,
                diagnostics=(diag,),
                execution_time_seconds=time.perf_counter() - start_time,
            )
        except Exception as exc:
            diag = create_parsing_diagnostic(
                analysis_id=request.analysis_id,
                artifact_id=request.artifact_id,
                artifact_path=request.path,
                code="parser_exception",
                message=f"Unexpected parser failure: {exc}",
                severity=DiagnosticSeverity.ERROR,
            )
            return ParserResult(
                success=False,
                document=None,
                diagnostics=(diag,),
                execution_time_seconds=time.perf_counter() - start_time,
                error_message=str(exc),
            )

        # Build line start offsets for canonical byte range mapping
        line_start_offsets = [0]
        for idx, b in enumerate(canonical_bytes):
            if b == 10:  # \n
                line_start_offsets.append(idx + 1)

        def make_range(
            lineno: int,
            col_offset: int,
            end_lineno: int | None,
            end_col_offset: int | None,
        ) -> SourceRange:
            el = end_lineno if end_lineno is not None else lineno
            ec = end_col_offset if end_col_offset is not None else col_offset

            # Clamp lines
            lineno = max(1, min(lineno, len(line_start_offsets)))
            el = max(1, min(el, len(line_start_offsets)))

            start_byte = line_start_offsets[lineno - 1] + col_offset
            end_byte = line_start_offsets[el - 1] + ec
            start_byte = max(0, min(start_byte, len(canonical_bytes)))
            end_byte = max(start_byte, min(end_byte, len(canonical_bytes)))

            return SourceRange(
                start_byte=start_byte,
                end_byte=end_byte,
                start_line=lineno,
                end_line=el,
                start_column=col_offset,
                end_column=ec,
            )

        facts: list[SyntaxFact] = []

        # Extract bootstrap facts (declarations, imports, basic calls)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start_line = (
                    node.decorator_list[0].lineno
                    if node.decorator_list
                    else node.lineno
                )
                start_col = (
                    node.decorator_list[0].col_offset
                    if node.decorator_list
                    else node.col_offset
                )
                d_range = make_range(
                    start_line,
                    start_col,
                    node.end_lineno,
                    node.end_col_offset,
                )
                # Compute name range
                name_col = (
                    node.col_offset + 4
                    if isinstance(node, ast.FunctionDef)
                    else node.col_offset + 10
                )
                n_range = make_range(
                    node.lineno,
                    name_col,
                    node.lineno,
                    name_col + len(node.name),
                )
                fact_key = build_fact_key(
                    request.path, "decl_function", node.name, d_range
                )
                decorator_names = tuple(
                    ast.unparse(d) if hasattr(ast, "unparse") else str(d)
                    for d in node.decorator_list
                )
                facts.append(
                    DeclarationFact(
                        fact_key=fact_key,
                        kind=DeclarationKind.FUNCTION,
                        name=node.name,
                        qualified_name=None,
                        container_key=None,
                        modifiers=(
                            ("async",) if isinstance(node, ast.AsyncFunctionDef) else ()
                        ),
                        decorators=decorator_names,
                        signature_text=None,
                        declaration_range=d_range,
                        name_range=n_range,
                    )
                )

            elif isinstance(node, ast.ClassDef):
                start_line = (
                    node.decorator_list[0].lineno
                    if node.decorator_list
                    else node.lineno
                )
                start_col = (
                    node.decorator_list[0].col_offset
                    if node.decorator_list
                    else node.col_offset
                )
                d_range = make_range(
                    start_line,
                    start_col,
                    node.end_lineno,
                    node.end_col_offset,
                )
                name_col = node.col_offset + 6
                n_range = make_range(
                    node.lineno,
                    name_col,
                    node.lineno,
                    name_col + len(node.name),
                )
                fact_key = build_fact_key(
                    request.path, "decl_class", node.name, d_range
                )
                decorator_names = tuple(
                    ast.unparse(d) if hasattr(ast, "unparse") else str(d)
                    for d in node.decorator_list
                )
                facts.append(
                    DeclarationFact(
                        fact_key=fact_key,
                        kind=DeclarationKind.CLASS,
                        name=node.name,
                        qualified_name=None,
                        container_key=None,
                        modifiers=(),
                        decorators=decorator_names,
                        signature_text=None,
                        declaration_range=d_range,
                        name_range=n_range,
                    )
                )

            elif isinstance(node, ast.Import):
                r = make_range(
                    node.lineno, node.col_offset, node.end_lineno, node.end_col_offset
                )
                for alias in node.names:
                    fact_key = build_fact_key(request.path, "import", alias.name, r)
                    facts.append(
                        ImportFact(
                            fact_key=fact_key,
                            kind=ImportKind.MODULE,
                            source_module=alias.name,
                            relative_level=0,
                            imported_name=None,
                            local_alias=alias.asname,
                            is_type_only=False,
                            is_commonjs=False,
                            range=r,
                        )
                    )

            elif isinstance(node, ast.ImportFrom):
                r = make_range(
                    node.lineno, node.col_offset, node.end_lineno, node.end_col_offset
                )
                module_name = node.module or ""
                for alias in node.names:
                    fact_key = build_fact_key(
                        request.path, "import_from", f"{module_name}::{alias.name}", r
                    )
                    facts.append(
                        ImportFact(
                            fact_key=fact_key,
                            kind=ImportKind.NAMED,
                            source_module=module_name,
                            relative_level=node.level or 0,
                            imported_name=alias.name,
                            local_alias=alias.asname,
                            is_type_only=False,
                            is_commonjs=False,
                            range=r,
                        )
                    )

            elif isinstance(node, ast.Call):
                if hasattr(node, "lineno") and hasattr(node, "col_offset"):
                    r = make_range(
                        node.lineno,
                        node.col_offset,
                        getattr(node, "end_lineno", node.lineno),
                        getattr(node, "end_col_offset", node.col_offset),
                    )
                    func_name = ""
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    if func_name:
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

        sorted_facts = sort_facts(facts)

        doc = SyntaxDocument(
            artifact_id=request.artifact_id,
            path=request.path,
            content_hash=content_hash,
            language="python",
            language_version=self.adapter_version,
            parser_adapter_id=self.adapter_id,
            parser_adapter_version=self.adapter_version,
            grammar_abi_version=sys.version_info.major * 100 + sys.version_info.minor,
            parse_status=ParseStatus.PARSED,
            encoding_metadata=encoding_meta,
            facts=sorted_facts,
            diagnostic_ids=(),
        )

        return ParserResult(
            success=True,
            document=doc,
            diagnostics=(),
            execution_time_seconds=time.perf_counter() - start_time,
        )
