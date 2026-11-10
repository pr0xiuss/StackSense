"""Python built-in AST parser and parser-neutral generic fact extraction."""

from __future__ import annotations

import ast
import hashlib
import re
import sys
import time
from collections.abc import Callable
from pathlib import PurePosixPath

from backend.platform.analysis.domain.constants import DiagnosticSeverity
from backend.platform.analysis.syntax.base import (
    ParserAdapter,
    ParserRequest,
    ParserResult,
    SourceEncodingError,
    create_parsing_diagnostic,
    normalize_source_encoding,
)
from backend.platform.analysis.syntax.limits import (
    FactAccumulator,
    FactLimitExceededError,
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
    SourceEncodingMetadata,
    SourceRange,
    SyntaxDocument,
    SyntaxFact,
    build_fact_key,
    sort_facts,
)

_SAFE_DOTTED_NAME = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")
_MAX_SIGNATURE_CHARS = 2_048
_HTTP_METHOD_BY_SUFFIX = {
    "get": "GET",
    "post": "POST",
    "put": "PUT",
    "patch": "PATCH",
    "delete": "DELETE",
    "options": "OPTIONS",
    "head": "HEAD",
    "websocket": "WEBSOCKET",
    "route": "GET",
}


def _safe_route_path(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 2_048:
        return None
    if "://" in value or any(ord(char) < 32 for char in value):
        return None
    return value


class PythonAstAdapter(ParserAdapter):
    """Parse Python without executing it and emit parser-neutral F2 facts."""

    adapter_id = "python-ast"
    adapter_version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    supported_languages = ("python",)

    @staticmethod
    def _dotted_name(node: ast.AST | None) -> str:
        if isinstance(node, ast.Call):
            return PythonAstAdapter._dotted_name(node.func)
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            prefix = PythonAstAdapter._dotted_name(node.value)
            return f"{prefix}.{node.attr}" if prefix else node.attr
        return ""

    @staticmethod
    def _safe_annotation(node: ast.AST | None) -> str:
        """Render bounded structural type syntax without retaining literals."""
        if node is None:
            return ""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return PythonAstAdapter._dotted_name(node)
        if isinstance(node, ast.Subscript):
            base = PythonAstAdapter._safe_annotation(node.value)
            arg = PythonAstAdapter._safe_annotation(node.slice)
            return f"{base}[{arg}]" if base and arg else base
        if isinstance(node, (ast.Tuple, ast.List)):
            return ", ".join(
                part
                for item in node.elts
                if (part := PythonAstAdapter._safe_annotation(item))
            )
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            left = PythonAstAdapter._safe_annotation(node.left)
            right = PythonAstAdapter._safe_annotation(node.right)
            return f"{left} | {right}" if left and right else left or right
        return ""

    @classmethod
    def _signature(cls, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        pieces: list[str] = []
        for arg in (*node.args.posonlyargs, *node.args.args):
            annotation = cls._safe_annotation(arg.annotation)
            pieces.append(f"{arg.arg}: {annotation}" if annotation else arg.arg)
        if node.args.vararg:
            pieces.append(f"*{node.args.vararg.arg}")
        for arg in node.args.kwonlyargs:
            annotation = cls._safe_annotation(arg.annotation)
            pieces.append(f"{arg.arg}: {annotation}" if annotation else arg.arg)
        if node.args.kwarg:
            pieces.append(f"**{node.args.kwarg.arg}")
        result = f"({', '.join(pieces)})"
        returns = cls._safe_annotation(node.returns)
        if returns:
            result += f" -> {returns}"
        return result[:_MAX_SIGNATURE_CHARS]

    @staticmethod
    def _module_name(path: str) -> tuple[str, DeclarationKind]:
        parts = list(PurePosixPath(path).with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts.pop()
            return ".".join(parts) or "__root__", DeclarationKind.PACKAGE
        return ".".join(parts), DeclarationKind.MODULE

    def parse(self, request: ParserRequest) -> ParserResult:
        start_time = time.perf_counter()
        if len(request.content) > request.max_file_size_bytes:
            return self._failure(
                request,
                start_time,
                "file_size_exceeded",
                "Artifact exceeds maximum allowed size of "
                f"{request.max_file_size_bytes} bytes",
            )

        try:
            canonical_bytes, text, encoding_meta = normalize_source_encoding(
                request.content, "python"
            )
        except SourceEncodingError as exc:
            return self._failure(
                request,
                start_time,
                "source_decode_error",
                f"Strict encoding decode failed: {exc}",
            )

        content_hash = hashlib.sha256(canonical_bytes).hexdigest()
        framework_hints: dict[str, dict[str, str]] = {}
        try:
            tree = ast.parse(text, filename=request.path)
        except SyntaxError as exc:
            diag = create_parsing_diagnostic(
                request.analysis_id,
                request.artifact_id,
                request.path,
                "syntax_error",
                f"Python syntax error: {exc.msg}",
                DiagnosticSeverity.ERROR,
                exc.lineno,
                exc.offset,
            )
            return ParserResult(
                success=True,
                document=self._document(
                    request,
                    content_hash,
                    encoding_meta,
                    ParseStatus.FAILED,
                    (),
                    (str(diag.id),),
                ),
                diagnostics=(diag,),
                execution_time_seconds=time.perf_counter() - start_time,
            )
        except Exception as exc:
            return self._failure(
                request,
                start_time,
                "parser_exception",
                f"Unexpected parser failure: {type(exc).__name__}",
            )

        line_starts = [0]
        for index, byte in enumerate(canonical_bytes):
            if byte == 10:
                line_starts.append(index + 1)

        def source_range(node: ast.AST) -> SourceRange:
            line = max(1, min(getattr(node, "lineno", 1), len(line_starts)))
            end_line = max(
                line, min(getattr(node, "end_lineno", line), len(line_starts))
            )
            column = max(0, getattr(node, "col_offset", 0))
            end_column = max(0, getattr(node, "end_col_offset", column))
            start_byte = min(line_starts[line - 1] + column, len(canonical_bytes))
            end_byte = min(
                max(start_byte, line_starts[end_line - 1] + end_column),
                len(canonical_bytes),
            )
            return SourceRange(
                start_byte,
                end_byte,
                line,
                end_line,
                column,
                end_column,
            )

        def identifier_range(
            node: ast.AST, name: str, keyword_bytes: int
        ) -> SourceRange:
            line = getattr(node, "lineno", 1)
            column = getattr(node, "col_offset", 0) + keyword_bytes
            proxy = ast.Name(id=name, ctx=ast.Load())
            proxy.lineno = line
            proxy.end_lineno = line
            proxy.col_offset = column
            proxy.end_col_offset = column + len(name.encode("utf-8"))
            return source_range(proxy)

        def outer_declaration_range(
            node: ast.AST, decorators: list[ast.expr]
        ) -> SourceRange:
            outer = source_range(node)
            if not decorators:
                return outer
            start = source_range(decorators[0])
            return SourceRange(
                start.start_byte,
                outer.end_byte,
                start.start_line,
                outer.end_line,
                start.start_column,
                outer.end_column,
            )

        accumulator = FactAccumulator(request.max_facts_per_artifact)
        try:
            module_name, module_kind = self._module_name(request.path)
            last_line = canonical_bytes.rsplit(b"\n", 1)[-1]
            full_range = SourceRange(
                0,
                len(canonical_bytes),
                1,
                max(1, encoding_meta.line_count),
                0,
                len(last_line),
            )
            module_key = build_fact_key(
                request.path, f"decl_{module_kind.value}", module_name, full_range
            )
            accumulator.add(
                DeclarationFact(
                    module_key,
                    module_kind,
                    module_name,
                    module_name,
                    None,
                    (),
                    (),
                    None,
                    full_range,
                    full_range,
                )
            )

            decorator_call_nodes: set[int] = set()
            stack: list[tuple[ast.AST, str, str, bool]] = [
                (tree, module_key, module_name, False)
            ]
            while stack:
                node, container_key, qualified_container, in_class = stack.pop()
                next_key, next_qualified, next_in_class = (
                    container_key,
                    qualified_container,
                    in_class,
                )

                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    decorator_call_nodes.update(
                        id(item)
                        for item in node.decorator_list
                        if isinstance(item, ast.Call)
                    )
                    declaration_range = outer_declaration_range(
                        node, node.decorator_list
                    )
                    kind = (
                        DeclarationKind.METHOD if in_class else DeclarationKind.FUNCTION
                    )
                    qualified = f"{qualified_container}.{node.name}"
                    key = build_fact_key(
                        request.path, f"decl_{kind.value}", qualified, declaration_range
                    )
                    decorators = tuple(
                        name
                        for item in node.decorator_list
                        if (name := self._dotted_name(item))
                    )
                    accumulator.add(
                        DeclarationFact(
                            key,
                            kind,
                            node.name,
                            qualified,
                            container_key,
                            (
                                ("async",)
                                if isinstance(node, ast.AsyncFunctionDef)
                                else ()
                            ),
                            decorators,
                            self._signature(node),
                            declaration_range,
                            identifier_range(
                                node,
                                node.name,
                                10 if isinstance(node, ast.AsyncFunctionDef) else 4,
                            ),
                        )
                    )
                    self._add_decorators(
                        accumulator,
                        request.path,
                        node.decorator_list,
                        key,
                        source_range,
                        framework_hints,
                    )
                    next_key, next_qualified, next_in_class = key, qualified, False

                elif isinstance(node, ast.ClassDef):
                    decorator_call_nodes.update(
                        id(item)
                        for item in node.decorator_list
                        if isinstance(item, ast.Call)
                    )
                    declaration_range = outer_declaration_range(
                        node, node.decorator_list
                    )
                    qualified = f"{qualified_container}.{node.name}"
                    key = build_fact_key(
                        request.path, "decl_class", qualified, declaration_range
                    )
                    decorators = tuple(
                        name
                        for item in node.decorator_list
                        if (name := self._dotted_name(item))
                    )
                    accumulator.add(
                        DeclarationFact(
                            key,
                            DeclarationKind.CLASS,
                            node.name,
                            qualified,
                            container_key,
                            (),
                            decorators,
                            None,
                            declaration_range,
                            identifier_range(node, node.name, 6),
                        )
                    )
                    for base in node.bases:
                        name = self._dotted_name(base)
                        if name:
                            rng = source_range(base)
                            accumulator.add(
                                ReferenceFact(
                                    build_fact_key(
                                        request.path, "inheritance", name, rng
                                    ),
                                    ReferenceKind.INHERITANCE,
                                    key,
                                    name,
                                    rng,
                                )
                            )
                    self._add_decorators(
                        accumulator,
                        request.path,
                        node.decorator_list,
                        key,
                        source_range,
                        framework_hints,
                    )
                    next_key, next_qualified, next_in_class = key, qualified, True

                elif isinstance(node, ast.Import):
                    rng = source_range(node)
                    for alias in node.names:
                        accumulator.add(
                            ImportFact(
                                build_fact_key(request.path, "import", alias.name, rng),
                                ImportKind.MODULE,
                                alias.name,
                                0,
                                None,
                                alias.asname,
                                False,
                                False,
                                rng,
                            )
                        )

                elif isinstance(node, ast.ImportFrom):
                    rng = source_range(node)
                    for alias in node.names:
                        accumulator.add(
                            ImportFact(
                                build_fact_key(
                                    request.path,
                                    "import_from",
                                    f"{node.module or ''}:{alias.name}",
                                    rng,
                                ),
                                (
                                    ImportKind.ALL
                                    if alias.name == "*"
                                    else ImportKind.NAMED
                                ),
                                node.module or "",
                                node.level,
                                alias.name,
                                alias.asname,
                                False,
                                False,
                                rng,
                            )
                        )

                elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = (
                        node.targets if isinstance(node, ast.Assign) else [node.target]
                    )
                    for target in targets:
                        if isinstance(target, ast.Name):
                            rng = source_range(target)
                            qualified = f"{qualified_container}.{target.id}"
                            accumulator.add(
                                DeclarationFact(
                                    build_fact_key(
                                        request.path, "decl_variable", qualified, rng
                                    ),
                                    DeclarationKind.VARIABLE,
                                    target.id,
                                    qualified,
                                    container_key,
                                    ("constant",) if target.id.isupper() else (),
                                    (),
                                    (
                                        self._safe_annotation(node.annotation)
                                        if isinstance(node, ast.AnnAssign)
                                        else None
                                    ),
                                    rng,
                                    rng,
                                )
                            )
                    if (
                        isinstance(node, ast.Assign)
                        and any(
                            isinstance(target, ast.Name) and target.id == "__all__"
                            for target in node.targets
                        )
                        and isinstance(node.value, (ast.List, ast.Tuple))
                    ):
                        for exported in node.value.elts:
                            if (
                                isinstance(exported, ast.Constant)
                                and isinstance(exported.value, str)
                                and exported.value.isidentifier()
                            ):
                                rng = source_range(exported)
                                accumulator.add(
                                    ExportFact(
                                        build_fact_key(
                                            request.path,
                                            "export_named",
                                            exported.value,
                                            rng,
                                        ),
                                        ExportKind.NAMED,
                                        exported.value,
                                        exported.value,
                                        None,
                                        False,
                                        False,
                                        rng,
                                    )
                                )

                elif isinstance(node, ast.Call):
                    if id(node) in decorator_call_nodes:
                        for child in reversed(list(ast.iter_child_nodes(node))):
                            stack.append(
                                (child, next_key, next_qualified, next_in_class)
                            )
                        continue
                    name = self._dotted_name(node.func)
                    if name and _SAFE_DOTTED_NAME.fullmatch(name):
                        rng = source_range(node.func)
                        fact_key = build_fact_key(request.path, "call", name, rng)
                        accumulator.add(
                            ReferenceFact(
                                fact_key,
                                ReferenceKind.CALL,
                                container_key,
                                name,
                                rng,
                            )
                        )
                        self._add_route_hint(framework_hints, fact_key, name, node)

                elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                    name = self._dotted_name(node)
                    if name and _SAFE_DOTTED_NAME.fullmatch(name):
                        rng = source_range(node)
                        accumulator.add(
                            ReferenceFact(
                                build_fact_key(request.path, "attribute", name, rng),
                                ReferenceKind.ATTRIBUTE,
                                container_key,
                                name,
                                rng,
                            )
                        )

                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    rng = source_range(node)
                    accumulator.add(
                        ReferenceFact(
                            build_fact_key(request.path, "name", node.id, rng),
                            ReferenceKind.NAME,
                            container_key,
                            node.id,
                            rng,
                        )
                    )

                for child in reversed(list(ast.iter_child_nodes(node))):
                    stack.append((child, next_key, next_qualified, next_in_class))

        except FactLimitExceededError as exc:
            diag = create_parsing_diagnostic(
                request.analysis_id,
                request.artifact_id,
                request.path,
                "resource_limit_exceeded",
                str(exc),
                DiagnosticSeverity.ERROR,
                details={
                    "limit": request.max_facts_per_artifact,
                    "scope": "artifact_facts",
                },
            )
            return ParserResult(
                success=True,
                document=self._document(
                    request,
                    content_hash,
                    encoding_meta,
                    ParseStatus.FAILED,
                    (),
                    (str(diag.id),),
                ),
                diagnostics=(diag,),
                execution_time_seconds=time.perf_counter() - start_time,
                error_message="Artifact fact limit exceeded",
            )

        try:
            facts = sort_facts(accumulator.facts)  # type: ignore[arg-type]
        except ValueError:
            return self._fact_integrity_failure(
                request, start_time, content_hash, encoding_meta
            )
        return ParserResult(
            success=True,
            document=self._document(
                request, content_hash, encoding_meta, ParseStatus.PARSED, facts, ()
            ),
            execution_time_seconds=time.perf_counter() - start_time,
            framework_hints=framework_hints,
        )

    def _add_decorators(
        self,
        accumulator: FactAccumulator,
        path: str,
        decorators: list[ast.expr],
        source_key: str,
        range_builder: Callable[[ast.AST], SourceRange],
        framework_hints: dict[str, dict[str, str]],
    ) -> None:
        for decorator in decorators:
            name = self._dotted_name(decorator)
            if name:
                rng = range_builder(decorator)
                fact_key = build_fact_key(path, "decorator", name, rng)
                accumulator.add(
                    ReferenceFact(
                        fact_key,
                        ReferenceKind.DECORATOR,
                        source_key,
                        name,
                        rng,
                    )
                )
                if isinstance(decorator, ast.Call):
                    self._add_route_hint(framework_hints, fact_key, name, decorator)

    @staticmethod
    def _add_route_hint(
        framework_hints: dict[str, dict[str, str]],
        fact_key: str,
        name: str,
        call: ast.Call,
    ) -> None:
        suffix = name.rsplit(".", 1)[-1]
        method = _HTTP_METHOD_BY_SUFFIX.get(suffix)
        if method is None or not call.args:
            return
        first = call.args[0]
        path = (
            _safe_route_path(first.value) if isinstance(first, ast.Constant) else None
        )
        if path is not None:
            framework_hints[fact_key] = {"method": method, "path": path}

    def _document(
        self,
        request: ParserRequest,
        content_hash: str,
        encoding: SourceEncodingMetadata,
        status: ParseStatus,
        facts: tuple[SyntaxFact, ...],
        diagnostic_ids: tuple[str, ...],
    ) -> SyntaxDocument:
        return SyntaxDocument(
            request.artifact_id,
            request.path,
            content_hash,
            "python",
            self.adapter_version,
            self.adapter_id,
            self.adapter_version,
            sys.version_info.major * 100 + sys.version_info.minor,
            status,
            encoding,
            facts,
            diagnostic_ids,
        )

    def _fact_integrity_failure(
        self,
        request: ParserRequest,
        start_time: float,
        content_hash: str,
        encoding: SourceEncodingMetadata,
    ) -> ParserResult:
        diag = create_parsing_diagnostic(
            request.analysis_id,
            request.artifact_id,
            request.path,
            "fact_integrity_error",
            "Conflicting parser-neutral fact identities were produced",
            DiagnosticSeverity.ERROR,
        )
        return ParserResult(
            True,
            self._document(
                request,
                content_hash,
                encoding,
                ParseStatus.FAILED,
                (),
                (str(diag.id),),
            ),
            (diag,),
            time.perf_counter() - start_time,
            error_message="Fact identity collision",
        )

    @staticmethod
    def _failure(
        request: ParserRequest, start_time: float, code: str, message: str
    ) -> ParserResult:
        diag = create_parsing_diagnostic(
            request.analysis_id,
            request.artifact_id,
            request.path,
            code,
            message,
            DiagnosticSeverity.ERROR,
        )
        return ParserResult(
            False,
            None,
            (diag,),
            time.perf_counter() - start_time,
            error_message=message,
        )
