"""Express, NestJS, and Next.js enrichment over generic JS/TS facts."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath

from backend.platform.analysis.syntax.model import (
    DeclarationFact,
    DeclarationKind,
    FrameworkFact,
    ImportFact,
    ReferenceFact,
    ReferenceKind,
    SyntaxDocument,
    build_fact_key,
    sort_facts,
)


class JavaScriptFrameworkEnricher:
    """Derive framework structure from allowlisted generic syntax evidence."""

    supported_frameworks = frozenset({"express", "nestjs", "nextjs"})

    def enrich(
        self,
        document: SyntaxDocument,
        frameworks: frozenset[str],
        framework_hints: Mapping[str, Mapping[str, str]] | None = None,
    ) -> tuple[FrameworkFact, ...]:
        if document.language not in {"javascript", "typescript", "jsx", "tsx"}:
            return ()
        imports = tuple(fact for fact in document.facts if isinstance(fact, ImportFact))
        references = tuple(
            fact for fact in document.facts if isinstance(fact, ReferenceFact)
        )
        declarations = tuple(
            fact for fact in document.facts if isinstance(fact, DeclarationFact)
        )
        produced: list[FrameworkFact] = []
        hints = framework_hints or {}
        for framework in sorted(frameworks):
            import_keys = tuple(
                fact.fact_key
                for fact in imports
                if _import_matches(fact.source_module, framework)
            )
            if not import_keys and framework != "nextjs":
                continue
            if framework == "express":
                for ref in references:
                    suffix = ref.target_name.rsplit(".", 1)[-1]
                    if ref.kind == ReferenceKind.CALL and suffix in {
                        "get",
                        "post",
                        "put",
                        "patch",
                        "delete",
                        "options",
                        "head",
                        "use",
                    }:
                        produced.append(
                            _make_fact(
                                document,
                                framework,
                                "middleware" if suffix == "use" else "route",
                                ref.target_name,
                                ref,
                                import_keys,
                                hints,
                            )
                        )
            elif framework == "nestjs":
                decorator_types = {
                    "Controller": "controller",
                    "Module": "module",
                    "Injectable": "provider",
                    "Get": "route",
                    "Post": "route",
                    "Put": "route",
                    "Patch": "route",
                    "Delete": "route",
                }
                for ref in references:
                    suffix = ref.target_name.rsplit(".", 1)[-1]
                    if (
                        ref.kind == ReferenceKind.DECORATOR
                        and suffix in decorator_types
                    ):
                        produced.append(
                            _make_fact(
                                document,
                                framework,
                                decorator_types[suffix],
                                ref.target_name,
                                ref,
                                import_keys,
                                hints,
                            )
                        )
            elif framework == "nextjs":
                path = PurePosixPath(document.path)
                is_page = path.name.startswith("page.") or "pages" in path.parts
                is_route = path.name.startswith("route.") or "api" in path.parts
                for declaration in declarations:
                    if is_page and declaration.kind == DeclarationKind.REACT_COMPONENT:
                        produced.append(
                            _declaration_fact(
                                document,
                                framework,
                                "page",
                                declaration,
                                import_keys,
                                hints,
                            )
                        )
                    elif (
                        is_route
                        and declaration.kind
                        in {
                            DeclarationKind.FUNCTION,
                            DeclarationKind.METHOD,
                        }
                        and declaration.name.upper()
                        in {
                            "GET",
                            "POST",
                            "PUT",
                            "PATCH",
                            "DELETE",
                            "OPTIONS",
                            "HEAD",
                        }
                    ):
                        produced.append(
                            _declaration_fact(
                                document,
                                framework,
                                "route_handler",
                                declaration,
                                import_keys,
                                hints,
                            )
                        )
        return tuple(
            fact for fact in sort_facts(produced) if isinstance(fact, FrameworkFact)
        )


def _import_matches(module: str, framework: str) -> bool:
    if framework == "nestjs":
        return module.startswith("@nestjs/")
    if framework == "nextjs":
        return module == "next" or module.startswith("next/")
    return module == framework


def _make_fact(
    document: SyntaxDocument,
    framework: str,
    fact_type: str,
    name: str,
    reference: ReferenceFact,
    import_keys: tuple[str, ...],
    framework_hints: Mapping[str, Mapping[str, str]],
) -> FrameworkFact:
    details = {
        "reference_kind": reference.kind.value,
        **framework_hints.get(reference.fact_key, {}),
    }
    fact_name = details.get("path", name) if fact_type == "route" else name
    return FrameworkFact(
        fact_key=build_fact_key(
            document.path,
            f"framework_{framework}_{fact_type}",
            fact_name,
            reference.range,
        ),
        framework_name=framework,
        artifact_id=document.artifact_id,
        fact_type=fact_type,
        name=fact_name,
        details=details,
        supporting_fact_keys=tuple(sorted((*import_keys, reference.fact_key))),
        range=reference.range,
    )


def _declaration_fact(
    document: SyntaxDocument,
    framework: str,
    fact_type: str,
    declaration: DeclarationFact,
    import_keys: tuple[str, ...],
    framework_hints: Mapping[str, Mapping[str, str]],
) -> FrameworkFact:
    details = {
        "declaration_kind": declaration.kind.value,
        **framework_hints.get(declaration.fact_key, {}),
    }
    if framework == "nextjs" and fact_type == "route_handler":
        details.update(
            {
                "method": declaration.name.upper(),
                "path": _nextjs_route_path(document.path),
            }
        )
    fact_name = details.get("path", declaration.name)
    return FrameworkFact(
        fact_key=build_fact_key(
            document.path,
            f"framework_{framework}_{fact_type}",
            fact_name,
            declaration.declaration_range,
        ),
        framework_name=framework,
        artifact_id=document.artifact_id,
        fact_type=fact_type,
        name=fact_name,
        details=details,
        supporting_fact_keys=tuple(sorted((*import_keys, declaration.fact_key))),
        range=declaration.declaration_range,
    )


def _nextjs_route_path(path: str) -> str:
    parts = list(PurePosixPath(path).parts)
    if "app" in parts:
        parts = parts[parts.index("app") + 1 :]
    elif "pages" in parts:
        parts = parts[parts.index("pages") + 1 :]
    if parts:
        parts.pop()
    visible = [
        part for part in parts if not (part.startswith("(") and part.endswith(")"))
    ]
    return "/" + "/".join(visible)
