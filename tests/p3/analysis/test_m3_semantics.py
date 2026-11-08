"""Semantic enrichment and relationship linking tests for Phase 3 Module 3 (IR).

Verifies document-local semantic resolution, container/scope hierarchy, aliasing,
re-exports, static calls, inheritance, composition, dynamic/ambiguous/unresolved
references, cycles, dependencies, and framework endpoint extractions.
"""

from __future__ import annotations

from backend.platform.analysis.ir import (
    IRConstructionService,
    IREntityKind,
    IRFactStatus,
    IRRelationshipKind,
    IRUnresolvedReason,
)
from backend.platform.analysis.syntax.model import (
    DeclarationKind,
    ExportKind,
    ImportKind,
    ReferenceKind,
)
from tests.p3.analysis.m3_test_helper import (
    create_mock_declaration_fact,
    create_mock_export_fact,
    create_mock_framework_fact,
    create_mock_import_fact,
    create_mock_inspection_result,
    create_mock_inventory_entry,
    create_mock_reference_fact,
    create_mock_source_range,
    create_mock_syntax_document,
)


class TestContainerAndScopeSemantics:
    """Tests container and scope relationships."""

    def test_module_contains_declarations(self) -> None:
        service = IRConstructionService()
        d_class = create_mock_declaration_fact(
            fact_key="decl::cls::1",
            name="UserService",
            kind=DeclarationKind.CLASS,
            declaration_range=create_mock_source_range(0, 100),
            name_range=create_mock_source_range(6, 17),
        )
        d_func = create_mock_declaration_fact(
            fact_key="decl::fn::1",
            name="get_user",
            kind=DeclarationKind.FUNCTION,
            declaration_range=create_mock_source_range(110, 150),
            name_range=create_mock_source_range(114, 122),
        )
        syntax_doc = create_mock_syntax_document(
            path="src/services/user.py",
            declarations=[d_class, d_func],
        )
        entry = create_mock_inventory_entry(path="src/services/user.py")
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )

        doc = service.construct(inspection)

        module_key = "module::src/services/user.py"
        declares_rels = [
            r
            for r in doc.relationships
            if r.kind == IRRelationshipKind.DECLARES and r.source_key == module_key
        ]
        target_keys = {r.target_key for r in declares_rels}
        assert "symbol::src/services/user.py::UserService::0_100" in target_keys
        assert "symbol::src/services/user.py::get_user::110_150" in target_keys

        # Artifact contains module
        art_key = "artifact::src/services/user.py"
        contains_rel = next(
            r
            for r in doc.relationships
            if r.kind == IRRelationshipKind.CONTAINS and r.source_key == art_key
        )
        assert contains_rel.target_key == module_key

    def test_same_name_members_resolve_in_nearest_lexical_container(self) -> None:
        service = IRConstructionService()
        class_a = create_mock_declaration_fact(
            fact_key="decl::class::a",
            name="A",
            kind=DeclarationKind.CLASS,
            declaration_range=create_mock_source_range(0, 100),
        )
        class_b = create_mock_declaration_fact(
            fact_key="decl::class::b",
            name="B",
            kind=DeclarationKind.CLASS,
            declaration_range=create_mock_source_range(110, 210),
        )
        method_a = create_mock_declaration_fact(
            fact_key="decl::method::a",
            name="work",
            kind=DeclarationKind.METHOD,
            container_key=class_a.fact_key,
            declaration_range=create_mock_source_range(10, 40),
        )
        method_b = create_mock_declaration_fact(
            fact_key="decl::method::b",
            name="work",
            kind=DeclarationKind.METHOD,
            container_key=class_b.fact_key,
            declaration_range=create_mock_source_range(120, 150),
        )
        caller = create_mock_declaration_fact(
            fact_key="decl::method::caller",
            name="run",
            kind=DeclarationKind.METHOD,
            container_key=class_a.fact_key,
            declaration_range=create_mock_source_range(50, 90),
        )
        reference = create_mock_reference_fact(
            fact_key="ref::call::work",
            target_name="work",
            kind=ReferenceKind.CALL,
            source_declaration_key=caller.fact_key,
        )
        syntax_doc = create_mock_syntax_document(
            path="src/scopes.py",
            declarations=[class_a, class_b, method_a, method_b, caller],
            references=[reference],
        )
        inspection = create_mock_inspection_result(
            inventory=[create_mock_inventory_entry(path="src/scopes.py")],
            syntax_documents=[syntax_doc],
        )

        document = service.construct(inspection)

        relationship = next(
            item
            for item in document.relationships
            if item.kind == IRRelationshipKind.STATIC_CALL_REFERENCE
        )
        assert relationship.target_key == "symbol::src/scopes.py::work::10_40"
        assert relationship.status == IRFactStatus.CONFIRMED


class TestAliasAndExportSemantics:
    """Tests aliasing, re-exports, and export resolution."""

    def test_imported_symbol_alias_recorded_in_metadata(self) -> None:
        service = IRConstructionService()
        imp_alias = create_mock_import_fact(
            fact_key="imp::1",
            source_module="pandas",
            imported_name="DataFrame",
            local_alias="DF",
            kind=ImportKind.NAMED,
        )
        syntax_doc = create_mock_syntax_document(
            path="src/analysis.py",
            imports=[imp_alias],
        )
        entry = create_mock_inventory_entry(path="src/analysis.py")
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )

        doc = service.construct(inspection)

        imp_rel = next(
            r for r in doc.relationships if r.kind == IRRelationshipKind.IMPORTS
        )
        assert imp_rel.metadata["imported_name"] == "DataFrame"
        assert imp_rel.metadata["local_alias"] == "DF"
        assert imp_rel.metadata["source_module"] == "pandas"

    def test_reexport_of_external_symbol_marked_unresolved(self) -> None:
        service = IRConstructionService()
        exp = create_mock_export_fact(
            fact_key="exp::1",
            exported_name="ExternalClient",
            local_name="ExternalClient",
            kind=ExportKind.NAMED,
        )
        syntax_doc = create_mock_syntax_document(
            path="src/index.ts",
            language="typescript",
            exports=[exp],
        )
        entry = create_mock_inventory_entry(path="src/index.ts")
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )

        doc = service.construct(inspection)

        exp_rel = next(
            r for r in doc.relationships if r.kind == IRRelationshipKind.EXPORTS
        )
        assert exp_rel.target_key is None
        assert exp_rel.unresolved_reference_key is not None
        assert exp_rel.status == IRFactStatus.UNRESOLVED

        unres = next(
            u
            for u in doc.unresolved_references
            if u.unresolved_key == exp_rel.unresolved_reference_key
        )
        assert unres.target_name == "ExternalClient"
        assert unres.reason == IRUnresolvedReason.NOT_FOUND


class TestInheritanceAndCompositionSemantics:
    """Tests class inheritance and component composition."""

    def test_local_inheritance_resolves_to_base_class_symbol(self) -> None:
        service = IRConstructionService()
        d_base = create_mock_declaration_fact(
            fact_key="decl::cls::base",
            name="BaseHandler",
            kind=DeclarationKind.CLASS,
            declaration_range=create_mock_source_range(0, 50),
            name_range=create_mock_source_range(6, 17),
        )
        d_sub = create_mock_declaration_fact(
            fact_key="decl::cls::sub",
            name="HttpHandler",
            kind=DeclarationKind.CLASS,
            declaration_range=create_mock_source_range(60, 120),
            name_range=create_mock_source_range(66, 77),
        )
        ref_inherit = create_mock_reference_fact(
            fact_key="ref::inherit::1",
            target_name="BaseHandler",
            kind=ReferenceKind.INHERITANCE,
            source_declaration_key="decl::cls::sub",
        )
        syntax_doc = create_mock_syntax_document(
            path="src/handlers.py",
            declarations=[d_base, d_sub],
            references=[ref_inherit],
        )
        entry = create_mock_inventory_entry(path="src/handlers.py")
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )

        doc = service.construct(inspection)

        inherit_rel = next(
            r for r in doc.relationships if r.kind == IRRelationshipKind.INHERITS
        )
        base_sym_key = "symbol::src/handlers.py::BaseHandler::0_50"
        sub_sym_key = "symbol::src/handlers.py::HttpHandler::60_120"
        assert inherit_rel.source_key == sub_sym_key
        assert inherit_rel.target_key == base_sym_key
        assert inherit_rel.unresolved_reference_key is None
        assert inherit_rel.status == IRFactStatus.CONFIRMED

    def test_react_component_composition(self) -> None:
        service = IRConstructionService()
        d_comp = create_mock_declaration_fact(
            fact_key="decl::comp::1",
            name="UserCard",
            kind=DeclarationKind.REACT_COMPONENT,
            declaration_range=create_mock_source_range(0, 80),
            name_range=create_mock_source_range(9, 17),
        )
        ref_compose = create_mock_reference_fact(
            fact_key="ref::compose::1",
            target_name="Avatar",
            kind=ReferenceKind.REACT_COMPOSITION,
            source_declaration_key="decl::comp::1",
        )
        syntax_doc = create_mock_syntax_document(
            path="src/components/UserCard.tsx",
            language="typescript",
            declarations=[d_comp],
            references=[ref_compose],
        )
        entry = create_mock_inventory_entry(path="src/components/UserCard.tsx")
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )

        doc = service.construct(inspection)

        compose_rel = next(
            r for r in doc.relationships if r.kind == IRRelationshipKind.COMPOSES
        )
        comp_key = "component::src/components/UserCard.tsx::UserCard::0_80"
        assert compose_rel.source_key == comp_key
        assert compose_rel.target_key is None  # External Avatar component unresolved
        assert compose_rel.unresolved_reference_key is not None
        assert compose_rel.status == IRFactStatus.UNRESOLVED


class TestCyclesAndRecursionTolerance:
    """Tests cycle preservation and recursive call handling."""

    def test_recursive_function_call_cycle_preserved(self) -> None:
        service = IRConstructionService()
        d_fact = create_mock_declaration_fact(
            fact_key="decl::fn::rec",
            name="factorial",
            kind=DeclarationKind.FUNCTION,
            declaration_range=create_mock_source_range(0, 60),
            name_range=create_mock_source_range(4, 13),
        )
        ref_self = create_mock_reference_fact(
            fact_key="ref::call::rec",
            target_name="factorial",
            kind=ReferenceKind.CALL,
            source_declaration_key="decl::fn::rec",
        )
        syntax_doc = create_mock_syntax_document(
            path="src/math.py",
            declarations=[d_fact],
            references=[ref_self],
        )
        entry = create_mock_inventory_entry(path="src/math.py")
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )

        doc = service.construct(inspection)

        sym_key = "symbol::src/math.py::factorial::0_60"
        call_rel = next(
            r
            for r in doc.relationships
            if r.kind == IRRelationshipKind.STATIC_CALL_REFERENCE
        )
        assert call_rel.source_key == sym_key
        assert call_rel.target_key == sym_key  # Self-recursive call edge
        assert call_rel.status == IRFactStatus.CONFIRMED


class TestFrameworkEndpointExtraction:
    """Tests framework route and endpoint extraction."""

    def test_framework_route_creates_endpoint_entity_and_declares_route_rel(
        self,
    ) -> None:
        service = IRConstructionService()
        entry = create_mock_inventory_entry(path="src/api/routes.py")
        route_fact = create_mock_framework_fact(
            fact_key="ff::route::users",
            framework_name="fastapi",
            artifact_id=entry.artifact_id,
            fact_type="api_endpoint",
            name="/api/v1/users",
            range=create_mock_source_range(0, 50),
            details={"method": "GET", "handler": "list_users"},
        )
        syntax_doc = create_mock_syntax_document(
            path="src/api/routes.py",
            framework_facts=[route_fact],
        )
        inspection = create_mock_inspection_result(
            inventory=[entry],
            syntax_documents=[syntax_doc],
        )

        doc = service.construct(inspection)

        # Endpoint entity created
        ep_entities = [e for e in doc.entities if e.kind == IREntityKind.ENDPOINT]
        assert len(ep_entities) == 1
        ep = ep_entities[0]
        assert ep.name == "/api/v1/users"
        assert ep.framework == "fastapi"
        assert ep.metadata["method"] == "GET"

        # Declares route relationship
        route_rel = next(
            r for r in doc.relationships if r.kind == IRRelationshipKind.DECLARES_ROUTE
        )
        assert route_rel.source_key == "module::src/api/routes.py"
        assert route_rel.target_key == ep.ir_key
