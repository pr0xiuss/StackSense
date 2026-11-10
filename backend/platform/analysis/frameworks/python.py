"""Django, Flask, and FastAPI enrichment over generic Python facts."""

from __future__ import annotations

from collections.abc import Mapping

from backend.platform.analysis.syntax.model import (
    DeclarationFact,
    FrameworkFact,
    ImportFact,
    ReferenceFact,
    ReferenceKind,
    SyntaxDocument,
    build_fact_key,
    sort_facts,
)


class PythonFrameworkEnricher:
    """Derive safe framework facts without source access or literal retention."""

    supported_frameworks = frozenset({"django", "flask", "fastapi"})

    def enrich(
        self,
        document: SyntaxDocument,
        frameworks: frozenset[str],
        framework_hints: Mapping[str, Mapping[str, str]] | None = None,
    ) -> tuple[FrameworkFact, ...]:
        if document.language != "python":
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
                if _python_import_matches(fact.source_module, framework)
            )
            if not import_keys:
                continue
            if framework == "django":
                produced.extend(
                    _facts_for_references(
                        document,
                        framework,
                        references,
                        import_keys,
                        {
                            "path": "route",
                            "re_path": "route",
                            "include": "route_include",
                        },
                        hints,
                    )
                )
                produced.extend(
                    _facts_for_inheritance(
                        document,
                        framework,
                        references,
                        declarations,
                        import_keys,
                        ("Model", "models.Model"),
                        "model",
                        hints,
                    )
                )
            elif framework == "flask":
                produced.extend(
                    _facts_for_suffixes(
                        document,
                        framework,
                        references,
                        import_keys,
                        {"route": "route", "before_request": "middleware"},
                        hints,
                    )
                )
            elif framework == "fastapi":
                produced.extend(
                    _facts_for_suffixes(
                        document,
                        framework,
                        references,
                        import_keys,
                        {
                            "get": "route",
                            "post": "route",
                            "put": "route",
                            "patch": "route",
                            "delete": "route",
                            "options": "route",
                            "head": "route",
                            "websocket": "route",
                            "Depends": "dependency",
                        },
                        hints,
                    )
                )
        return tuple(
            fact for fact in sort_facts(produced) if isinstance(fact, FrameworkFact)
        )


def _python_import_matches(module: str, framework: str) -> bool:
    return module == framework or module.startswith(f"{framework}.")


def _make_fact(
    document: SyntaxDocument,
    framework: str,
    fact_type: str,
    reference: ReferenceFact,
    import_keys: tuple[str, ...],
    framework_hints: Mapping[str, Mapping[str, str]],
) -> FrameworkFact:
    details = {
        "reference_kind": reference.kind.value,
        **framework_hints.get(reference.fact_key, {}),
    }
    name = (
        details["path"]
        if fact_type in {"route", "route_handler"} and "path" in details
        else reference.target_name
    )
    return FrameworkFact(
        fact_key=build_fact_key(
            document.path,
            f"framework_{framework}_{fact_type}",
            name,
            reference.range,
        ),
        framework_name=framework,
        artifact_id=document.artifact_id,
        fact_type=fact_type,
        name=name,
        details=details,
        supporting_fact_keys=tuple(sorted((*import_keys, reference.fact_key))),
        range=reference.range,
    )


def _facts_for_references(
    document: SyntaxDocument,
    framework: str,
    references: tuple[ReferenceFact, ...],
    import_keys: tuple[str, ...],
    targets: dict[str, str],
    framework_hints: Mapping[str, Mapping[str, str]],
) -> list[FrameworkFact]:
    return [
        _make_fact(
            document,
            framework,
            targets[ref.target_name],
            ref,
            import_keys,
            framework_hints,
        )
        for ref in references
        if ref.kind == ReferenceKind.CALL and ref.target_name in targets
    ]


def _facts_for_suffixes(
    document: SyntaxDocument,
    framework: str,
    references: tuple[ReferenceFact, ...],
    import_keys: tuple[str, ...],
    suffixes: dict[str, str],
    framework_hints: Mapping[str, Mapping[str, str]],
) -> list[FrameworkFact]:
    facts: list[FrameworkFact] = []
    for ref in references:
        suffix = ref.target_name.rsplit(".", 1)[-1]
        if suffix in suffixes and ref.kind in (
            ReferenceKind.CALL,
            ReferenceKind.DECORATOR,
        ):
            facts.append(
                _make_fact(
                    document,
                    framework,
                    suffixes[suffix],
                    ref,
                    import_keys,
                    framework_hints,
                )
            )
    return facts


def _facts_for_inheritance(
    document: SyntaxDocument,
    framework: str,
    references: tuple[ReferenceFact, ...],
    declarations: tuple[DeclarationFact, ...],
    import_keys: tuple[str, ...],
    bases: tuple[str, ...],
    fact_type: str,
    framework_hints: Mapping[str, Mapping[str, str]],
) -> list[FrameworkFact]:
    declaration_names = {fact.fact_key: fact.name for fact in declarations}
    facts: list[FrameworkFact] = []
    for ref in references:
        if ref.kind != ReferenceKind.INHERITANCE or ref.target_name not in bases:
            continue
        fact = _make_fact(
            document,
            framework,
            fact_type,
            ref,
            import_keys,
            framework_hints,
        )
        name = declaration_names.get(ref.source_declaration_key or "", ref.target_name)
        facts.append(
            FrameworkFact(
                fact_key=fact.fact_key,
                framework_name=fact.framework_name,
                artifact_id=fact.artifact_id,
                fact_type=fact.fact_type,
                name=name,
                details=fact.details,
                supporting_fact_keys=fact.supporting_fact_keys,
                range=fact.range,
            )
        )
    return facts
