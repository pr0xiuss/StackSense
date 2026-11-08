"""Tree-sitter JS/TS/JSX/TSX parser-neutral generic fact extraction."""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Iterable

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

_SAFE_REFERENCE_NAME = re.compile(
    r"^[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*$"
)
_DECLARATION_NODE_TYPES = {
    "class_declaration": DeclarationKind.CLASS,
    "abstract_class_declaration": DeclarationKind.CLASS,
    "interface_declaration": DeclarationKind.INTERFACE,
    "type_alias_declaration": DeclarationKind.TYPE_ALIAS,
}
_HTTP_METHOD_BY_SUFFIX = {
    "get": "GET",
    "post": "POST",
    "put": "PUT",
    "patch": "PATCH",
    "delete": "DELETE",
    "options": "OPTIONS",
    "head": "HEAD",
    "Get": "GET",
    "Post": "POST",
    "Put": "PUT",
    "Patch": "PATCH",
    "Delete": "DELETE",
}


def _safe_route_path(value: str) -> str | None:
    if not value or len(value) > 2_048:
        return None
    if "://" in value or any(ord(char) < 32 for char in value):
        return None
    return value


class TreeSitterJsTsAdapter(ParserAdapter):
    """Parse JS-family source once and emit only parser-neutral F2 facts."""

    adapter_id = "tree-sitter-javascript-typescript"
    adapter_version = "0.25.2"
    supported_languages = ("javascript", "typescript", "jsx", "tsx")

    def __init__(self) -> None:
        self._languages = {
            "javascript": Language(tree_sitter_javascript.language()),
            "jsx": Language(tree_sitter_javascript.language()),
            "typescript": Language(tree_sitter_typescript.language_typescript()),
            "tsx": Language(tree_sitter_typescript.language_tsx()),
        }

    def _get_parser(self, language: str) -> Parser:
        try:
            return Parser(self._languages[language.lower().strip()])
        except KeyError as exc:
            raise ValueError(
                f"Unsupported language for JS/TS adapter: {language}"
            ) from exc

    @staticmethod
    def _text(node: Node | None) -> str:
        if node is None or node.text is None:
            return ""
        return node.text.decode("utf-8")

    @classmethod
    def _string_value(cls, node: Node | None) -> str:
        text = cls._text(node)
        if len(text) >= 2 and text[0] in "'\"`" and text[-1] == text[0]:
            return text[1:-1]
        return ""

    @staticmethod
    def _range(node: Node) -> SourceRange:
        return SourceRange(
            node.start_byte,
            node.end_byte,
            node.start_point[0] + 1,
            node.end_point[0] + 1,
            node.start_point[1],
            node.end_point[1],
        )

    @staticmethod
    def _walk(node: Node) -> Iterable[Node]:
        stack = [node]
        while stack:
            current = stack.pop()
            yield current
            stack.extend(reversed(current.named_children))

    @classmethod
    def _first(cls, node: Node, *types: str) -> Node | None:
        return next((item for item in cls._walk(node) if item.type in types), None)

    @classmethod
    def _decorator_name(cls, node: Node) -> str:
        call = cls._first(node, "call_expression")
        target = call.child_by_field_name("function") if call else None
        if target is None:
            target = cls._first(node, "identifier", "member_expression")
        name = cls._text(target)
        return name if _SAFE_REFERENCE_NAME.fullmatch(name) else ""

    @classmethod
    def _contains_jsx(cls, node: Node) -> bool:
        return any(item.type.startswith("jsx_") for item in cls._walk(node))

    @staticmethod
    def _decorator_nodes(node: Node) -> tuple[Node, ...]:
        """Return decorators grammatically associated with a declaration."""
        direct = tuple(child for child in node.children if child.type == "decorator")
        if direct:
            return direct
        parent = node.parent
        if parent is None:
            return ()
        if parent.type == "export_statement":
            return tuple(
                child for child in parent.children if child.type == "decorator"
            )
        siblings = list(parent.children)
        try:
            index = siblings.index(node)
        except ValueError:
            return ()
        decorators: list[Node] = []
        for sibling in reversed(siblings[:index]):
            if sibling.type == "comment":
                continue
            if sibling.type != "decorator":
                break
            decorators.append(sibling)
        return tuple(reversed(decorators))

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
            canonical_bytes, _, encoding_meta = normalize_source_encoding(
                request.content, request.language
            )
        except SourceEncodingError as exc:
            return self._failure(
                request,
                start_time,
                "source_decode_error",
                f"Strict UTF-8 decode failed: {exc}",
            )

        content_hash = hashlib.sha256(canonical_bytes).hexdigest()
        framework_hints: dict[str, dict[str, str]] = {}
        try:
            tree = self._get_parser(request.language).parse(canonical_bytes)
        except Exception as exc:
            return self._failure(
                request,
                start_time,
                "parser_exception",
                f"Tree-sitter parser failure: {type(exc).__name__}",
            )

        diagnostics = []
        status = ParseStatus.PARSED
        if tree.root_node.has_error:
            status = ParseStatus.PARSED_WITH_ERRORS
            diagnostics.append(
                create_parsing_diagnostic(
                    request.analysis_id,
                    request.artifact_id,
                    request.path,
                    "syntax_error_recoverable",
                    "Source contains recoverable syntax errors identified by "
                    "Tree-sitter",
                    DiagnosticSeverity.WARNING,
                )
            )

        accumulator = FactAccumulator(request.max_facts_per_artifact)
        try:
            stack: list[tuple[Node, str | None, str | None]] = [
                (tree.root_node, None, None)
            ]
            while stack:
                node, container_key, container_name = stack.pop()
                next_key, next_name = container_key, container_name

                if node.type in _DECLARATION_NODE_TYPES:
                    name_node = node.child_by_field_name("name")
                    name = self._text(name_node) or "anonymous"
                    rng = self._range(node)
                    kind = _DECLARATION_NODE_TYPES[node.type]
                    qualified = f"{container_name}.{name}" if container_name else name
                    key = build_fact_key(
                        request.path, f"decl_{kind.value}", qualified, rng
                    )
                    decorators = tuple(
                        decorator
                        for child in self._decorator_nodes(node)
                        if (decorator := self._decorator_name(child))
                    )
                    modifiers = tuple(
                        modifier
                        for modifier in ("abstract", "export", "default")
                        if modifier.encode() in (node.text or b"").split()[:4]
                    )
                    accumulator.add(
                        DeclarationFact(
                            key,
                            kind,
                            name,
                            qualified,
                            container_key,
                            modifiers,
                            decorators,
                            None,
                            rng,
                            self._range(name_node) if name_node else rng,
                        )
                    )
                    self._add_decorator_and_heritage_facts(
                        accumulator, request.path, node, key, framework_hints
                    )
                    next_key, next_name = key, qualified

                elif node.type in (
                    "function_declaration",
                    "generator_function_declaration",
                ):
                    name_node = node.child_by_field_name("name")
                    name = self._text(name_node) or "anonymous"
                    rng = self._range(node)
                    qualified = f"{container_name}.{name}" if container_name else name
                    kind = (
                        DeclarationKind.REACT_COMPONENT
                        if name[0].isupper() and self._contains_jsx(node)
                        else DeclarationKind.FUNCTION
                    )
                    key = build_fact_key(
                        request.path, f"decl_{kind.value}", qualified, rng
                    )
                    accumulator.add(
                        DeclarationFact(
                            key,
                            kind,
                            name,
                            qualified,
                            container_key,
                            ("async",) if b"async" in (node.text or b"")[:16] else (),
                            (),
                            None,
                            rng,
                            self._range(name_node) if name_node else rng,
                        )
                    )
                    next_key, next_name = key, qualified

                elif node.type == "method_definition":
                    name_node = node.child_by_field_name("name")
                    name = self._text(name_node) or "anonymous"
                    rng = self._range(node)
                    qualified = f"{container_name}.{name}" if container_name else name
                    key = build_fact_key(request.path, "decl_method", qualified, rng)
                    decorators = tuple(
                        decorator
                        for child in self._decorator_nodes(node)
                        if (decorator := self._decorator_name(child))
                    )
                    raw_prefix = (node.text or b"")[:64]
                    modifiers = tuple(
                        item
                        for item in ("static", "async", "abstract", "get", "set")
                        if item.encode() in raw_prefix.split()
                    )
                    accumulator.add(
                        DeclarationFact(
                            key,
                            DeclarationKind.METHOD,
                            name,
                            qualified,
                            container_key,
                            modifiers,
                            decorators,
                            None,
                            rng,
                            self._range(name_node) if name_node else rng,
                        )
                    )
                    self._add_decorator_and_heritage_facts(
                        accumulator, request.path, node, key, framework_hints
                    )
                    next_key, next_name = key, qualified

                elif node.type == "variable_declarator":
                    name_node = node.child_by_field_name("name")
                    value_node = node.child_by_field_name("value")
                    name = self._text(name_node)
                    value_type = value_node.type if value_node else ""
                    # Local scalar bindings are intentionally left to M3 symbol
                    # normalization. M2 retains module/class variables and named
                    # function/component expressions as architectural evidence.
                    should_declare = container_key is None or value_type in (
                        "arrow_function",
                        "function_expression",
                    )
                    if should_declare and name and _SAFE_REFERENCE_NAME.fullmatch(name):
                        rng = self._range(node)
                        if value_type in ("arrow_function", "function_expression"):
                            kind = (
                                DeclarationKind.REACT_COMPONENT
                                if name[0].isupper()
                                and value_node is not None
                                and self._contains_jsx(value_node)
                                else DeclarationKind.FUNCTION
                            )
                        else:
                            kind = DeclarationKind.VARIABLE
                        qualified = (
                            f"{container_name}.{name}" if container_name else name
                        )
                        key = build_fact_key(
                            request.path, f"decl_{kind.value}", qualified, rng
                        )
                        accumulator.add(
                            DeclarationFact(
                                key,
                                kind,
                                name,
                                qualified,
                                container_key,
                                (
                                    ("constant",)
                                    if node.parent
                                    and node.parent.type == "lexical_declaration"
                                    and self._text(node.parent)
                                    .lstrip()
                                    .startswith("const ")
                                    else ()
                                ),
                                (),
                                None,
                                rng,
                                self._range(name_node) if name_node else rng,
                            )
                        )
                        if value_type in ("arrow_function", "function_expression"):
                            next_key, next_name = key, qualified

                elif node.type == "import_statement":
                    self._add_import_facts(accumulator, request.path, node)

                elif node.type == "export_statement":
                    self._add_export_facts(accumulator, request.path, node)

                elif node.type == "call_expression":
                    target = node.child_by_field_name("function")
                    name = self._text(target)
                    if node.parent is not None and node.parent.type == "decorator":
                        name = ""
                    if name and _SAFE_REFERENCE_NAME.fullmatch(name):
                        rng = self._range(target or node)
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
                    self._add_commonjs_import(
                        accumulator, request.path, node, container_key
                    )

                elif node.type == "member_expression":
                    name = self._text(node)
                    if name and _SAFE_REFERENCE_NAME.fullmatch(name):
                        rng = self._range(node)
                        accumulator.add(
                            ReferenceFact(
                                build_fact_key(request.path, "attribute", name, rng),
                                ReferenceKind.ATTRIBUTE,
                                container_key,
                                name,
                                rng,
                            )
                        )

                elif node.type in ("jsx_element", "jsx_self_closing_element"):
                    name_node = node.child_by_field_name("name")
                    if name_node is None:
                        opening = self._first(node, "jsx_opening_element")
                        name_node = (
                            opening.child_by_field_name("name") if opening else None
                        )
                    name = self._text(name_node)
                    if (
                        name
                        and name[0].isupper()
                        and _SAFE_REFERENCE_NAME.fullmatch(name)
                    ):
                        rng = self._range(name_node or node)
                        accumulator.add(
                            ReferenceFact(
                                build_fact_key(
                                    request.path, "react_composition", name, rng
                                ),
                                ReferenceKind.REACT_COMPOSITION,
                                container_key,
                                name,
                                rng,
                            )
                        )

                elif node.type == "assignment_expression":
                    self._add_commonjs_export(accumulator, request.path, node)

                for child in reversed(node.named_children):
                    stack.append((child, next_key, next_name))

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
                True,
                self._document(
                    request,
                    content_hash,
                    encoding_meta,
                    ParseStatus.FAILED,
                    (),
                    (str(diag.id),),
                ),
                (diag,),
                time.perf_counter() - start_time,
                error_message="Artifact fact limit exceeded",
            )

        try:
            facts = sort_facts(accumulator.facts)  # type: ignore[arg-type]
        except ValueError:
            return self._fact_integrity_failure(
                request, start_time, content_hash, encoding_meta
            )
        return ParserResult(
            True,
            self._document(
                request,
                content_hash,
                encoding_meta,
                status,
                facts,
                tuple(str(item.id) for item in diagnostics),
            ),
            tuple(diagnostics),
            time.perf_counter() - start_time,
            framework_hints=framework_hints,
        )

    def _add_decorator_and_heritage_facts(
        self,
        accumulator: FactAccumulator,
        path: str,
        node: Node,
        source_key: str,
        framework_hints: dict[str, dict[str, str]],
    ) -> None:
        for item in self._decorator_nodes(node):
            name = self._decorator_name(item)
            if name:
                rng = self._range(item)
                fact_key = build_fact_key(
                    path, ReferenceKind.DECORATOR.value, name, rng
                )
                accumulator.add(
                    ReferenceFact(
                        fact_key,
                        ReferenceKind.DECORATOR,
                        source_key,
                        name,
                        rng,
                    )
                )
                call = self._first(item, "call_expression")
                if call is not None:
                    self._add_route_hint(framework_hints, fact_key, name, call)
        heritage_roots = tuple(
            child
            for child in node.children
            if child.type
            in ("class_heritage", "extends_type_clause", "implements_clause")
        )
        for root in heritage_roots:
            clauses = tuple(
                item
                for item in self._walk(root)
                if item.type
                in ("extends_clause", "extends_type_clause", "implements_clause")
            ) or (root,)
            for item in clauses:
                candidates = [
                    child
                    for child in self._walk(item)
                    if child.type
                    in ("identifier", "type_identifier", "member_expression")
                ]
                for candidate in candidates:
                    value = self._text(candidate)
                    if value and _SAFE_REFERENCE_NAME.fullmatch(value):
                        rng = self._range(candidate)
                        accumulator.add(
                            ReferenceFact(
                                build_fact_key(path, "inheritance", value, rng),
                                ReferenceKind.INHERITANCE,
                                source_key,
                                value,
                                rng,
                            )
                        )

    @classmethod
    def _add_route_hint(
        cls,
        framework_hints: dict[str, dict[str, str]],
        fact_key: str,
        name: str,
        call: Node,
    ) -> None:
        method = _HTTP_METHOD_BY_SUFFIX.get(name.rsplit(".", 1)[-1])
        arguments = call.child_by_field_name("arguments")
        first = (
            arguments.named_children[0]
            if arguments and arguments.named_children
            else None
        )
        path = _safe_route_path(cls._string_value(first))
        if method is not None and path is not None:
            framework_hints[fact_key] = {"method": method, "path": path}

    def _add_import_facts(
        self, accumulator: FactAccumulator, path: str, node: Node
    ) -> None:
        source = self._string_value(node.child_by_field_name("source"))
        if not source:
            return
        rng = self._range(node)
        relative = len(source) - len(source.lstrip("."))
        clause = next((c for c in node.children if c.type == "import_clause"), None)
        if clause is None:
            accumulator.add(
                ImportFact(
                    build_fact_key(path, "import_side_effect", source, rng),
                    ImportKind.SIDE_EFFECT,
                    source,
                    relative,
                    None,
                    None,
                    False,
                    False,
                    rng,
                )
            )
            return
        direct_identifier = next(
            (c for c in clause.children if c.type == "identifier"), None
        )
        if direct_identifier:
            alias = self._text(direct_identifier)
            accumulator.add(
                ImportFact(
                    build_fact_key(path, "import_default", f"{source}:{alias}", rng),
                    ImportKind.DEFAULT,
                    source,
                    relative,
                    "default",
                    alias,
                    False,
                    False,
                    rng,
                )
            )
        namespace = self._first(clause, "namespace_import")
        if namespace:
            alias_node = self._first(namespace, "identifier")
            alias = self._text(alias_node)
            accumulator.add(
                ImportFact(
                    build_fact_key(path, "import_all", f"{source}:{alias}", rng),
                    ImportKind.ALL,
                    source,
                    relative,
                    "*",
                    alias or None,
                    False,
                    False,
                    rng,
                )
            )
        for specifier in (
            c for c in self._walk(clause) if c.type == "import_specifier"
        ):
            imported = self._text(specifier.child_by_field_name("name"))
            imported_alias = self._text(specifier.child_by_field_name("alias")) or None
            is_type = self._text(specifier).lstrip().startswith("type ")
            accumulator.add(
                ImportFact(
                    build_fact_key(
                        path,
                        "import_named",
                        f"{source}:{imported}:{imported_alias or ''}",
                        rng,
                    ),
                    ImportKind.NAMED,
                    source,
                    relative,
                    imported,
                    imported_alias,
                    is_type,
                    False,
                    rng,
                )
            )

    def _add_export_facts(
        self, accumulator: FactAccumulator, path: str, node: Node
    ) -> None:
        rng = self._range(node)
        source = self._string_value(node.child_by_field_name("source")) or None
        raw = self._text(node).lstrip()
        clause = next((c for c in node.children if c.type == "export_clause"), None)
        declaration = node.child_by_field_name("declaration")
        if clause:
            for specifier in (
                c for c in self._walk(clause) if c.type == "export_specifier"
            ):
                local = self._text(specifier.child_by_field_name("name"))
                exported = self._text(specifier.child_by_field_name("alias")) or local
                accumulator.add(
                    ExportFact(
                        build_fact_key(
                            path, "export_named", f"{local}:{exported}", rng
                        ),
                        ExportKind.RE_EXPORT if source else ExportKind.NAMED,
                        local,
                        exported,
                        source,
                        self._text(specifier).lstrip().startswith("type "),
                        False,
                        rng,
                    )
                )
        elif declaration:
            name_node = declaration.child_by_field_name("name") or self._first(
                declaration, "variable_declarator"
            )
            if name_node and name_node.type == "variable_declarator":
                name_node = name_node.child_by_field_name("name")
            name = self._text(name_node)
            if name:
                accumulator.add(
                    ExportFact(
                        build_fact_key(path, "export_named", name, rng),
                        ExportKind.NAMED,
                        name,
                        name,
                        source,
                        raw.startswith("export type "),
                        False,
                        rng,
                    )
                )
        elif "export *" in raw and source:
            accumulator.add(
                ExportFact(
                    build_fact_key(path, "export_all", source, rng),
                    ExportKind.ALL,
                    None,
                    "*",
                    source,
                    False,
                    False,
                    rng,
                )
            )
        elif raw.startswith("export default"):
            value = self._text(node.child_by_field_name("value"))
            if value and _SAFE_REFERENCE_NAME.fullmatch(value):
                accumulator.add(
                    ExportFact(
                        build_fact_key(path, "export_default", value, rng),
                        ExportKind.DEFAULT,
                        value,
                        "default",
                        None,
                        False,
                        False,
                        rng,
                    )
                )

    def _add_commonjs_import(
        self,
        accumulator: FactAccumulator,
        path: str,
        node: Node,
        source_key: str | None,
    ) -> None:
        if self._text(node.child_by_field_name("function")) != "require":
            return
        arguments = node.child_by_field_name("arguments")
        string = self._first(arguments, "string") if arguments else None
        source = self._string_value(string)
        if source:
            rng = self._range(node)
            accumulator.add(
                ImportFact(
                    build_fact_key(path, "require", source, rng),
                    ImportKind.MODULE,
                    source,
                    len(source) - len(source.lstrip(".")),
                    None,
                    None,
                    False,
                    True,
                    rng,
                )
            )

    def _add_commonjs_export(
        self, accumulator: FactAccumulator, path: str, node: Node
    ) -> None:
        left = self._text(node.child_by_field_name("left"))
        if left != "module.exports" and not left.startswith("exports."):
            return
        right = self._text(node.child_by_field_name("right"))
        exported = "default" if left == "module.exports" else left.split(".", 1)[1]
        rng = self._range(node)
        accumulator.add(
            ExportFact(
                build_fact_key(path, "commonjs_export", exported, rng),
                ExportKind.DEFAULT if exported == "default" else ExportKind.NAMED,
                right if _SAFE_REFERENCE_NAME.fullmatch(right) else None,
                exported,
                None,
                False,
                True,
                rng,
            )
        )

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
            request.language,
            None,
            self.adapter_id,
            self.adapter_version,
            int(tree_sitter.LANGUAGE_VERSION),
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
