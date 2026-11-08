"""M4 Batch 1 deterministic resolution and promotion tests."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from backend.platform.analysis.architecture import (
    ArchitectureEntity,
    ArchitectureEntityKind,
    ArchitectureFactStatus,
    ArchitectureIdentityCollisionError,
    HistoricalIdentityRecord,
    IdentityResolutionService,
    semantic_signature,
)
from backend.platform.analysis.ir import (
    IRCompleteness,
    IRDocument,
    IREntity,
    IREntityKind,
    IREvidence,
    IREvidenceStrength,
    IRFactStatus,
)

ANALYSIS_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROJECT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
REPOSITORY_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
SNAPSHOT_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


def _evidence(key: str, path: str = "src/app.py") -> IREvidence:
    return IREvidence(
        evidence_key=key,
        artifact_id=None,
        path=path,
        source_record_type="declaration_fact",
        source_fact_key=key,
        parser_adapter_id="python-ast",
        parser_adapter_version="1.0.0",
        upstream_analyzer_version="0.1.0",
        strength=IREvidenceStrength.DIRECT_SOURCE,
    )


def _document(
    entities: tuple[IREntity, ...], evidence: tuple[IREvidence, ...]
) -> IRDocument:
    return IRDocument(
        analysis_id=ANALYSIS_ID,
        project_id=PROJECT_ID,
        repository_id=REPOSITORY_ID,
        snapshot_id=SNAPSHOT_ID,
        configuration_fingerprint="cfg",
        entities=entities,
        relationships=(),
        evidence=evidence,
        unresolved_references=(),
        conflicts=(),
        completeness=IRCompleteness(
            total_entities=len(entities), total_syntax_facts=len(evidence)
        ),
    )


def _component(
    ir_key: str, evidence_key: str, *, name: str = "UsersController"
) -> IREntity:
    return IREntity(
        ir_key=ir_key,
        kind=IREntityKind.COMPONENT,
        name=name,
        qualified_name="api.users.UsersController",
        framework="fastapi",
        status=IRFactStatus.CONFIRMED,
        evidence_keys=(evidence_key,),
        metadata={
            "application_namespace": "api",
            "architectural_role": "controller",
        },
    )


def test_cross_producer_equivalents_merge_and_preserve_all_evidence() -> None:
    first, second = _evidence("ev-a"), _evidence("ev-b")
    doc = _document(
        (_component("ir-a", "ev-a"), _component("ir-b", "ev-b")),
        (first, second),
    )
    result = IdentityResolutionService().resolve(doc)
    assert len(result.entities) == 1
    entity = result.entities[0]
    assert entity.kind == ArchitectureEntityKind.CONTROLLER
    assert entity.source_ir_keys == ("ir-a", "ir-b")
    assert entity.status == ArchitectureFactStatus.SUPPORTED
    assert len(entity.evidence_ids) == 2
    assert {item.source_evidence_key for item in result.evidence} == {"ev-a", "ev-b"}
    assert all(item.producer_id == "python-ast" for item in result.evidence)


def test_resolution_is_byte_deterministic_under_input_reordering() -> None:
    a, b = _evidence("ev-a"), _evidence("ev-b")
    entities = (_component("ir-a", "ev-a"), _component("ir-b", "ev-b"))
    forward = IdentityResolutionService().resolve(_document(entities, (a, b)))
    reverse = IdentityResolutionService().resolve(
        _document(tuple(reversed(entities)), (b, a))
    )
    assert forward.to_canonical_json() == reverse.to_canonical_json()


def test_low_level_symbols_and_unscoped_modules_are_not_promoted() -> None:
    evidence = _evidence("ev-symbol")
    symbol = IREntity(
        ir_key="symbol-one",
        kind=IREntityKind.SYMBOL,
        name="helper",
        qualified_name="src.app.helper",
        evidence_keys=(evidence.evidence_key,),
    )
    module = IREntity(
        ir_key="module-one",
        kind=IREntityKind.MODULE,
        name="app.py",
        qualified_name="src/app.py",
        evidence_keys=(evidence.evidence_key,),
    )
    result = IdentityResolutionService().resolve(
        _document((symbol, module), (evidence,))
    )
    assert result.entities == ()
    assert result.evidence == ()


def test_same_name_in_different_scopes_remains_distinct() -> None:
    first, second = _evidence("ev-a"), _evidence("ev-b")
    left = _component("ir-a", "ev-a")
    right = replace(
        _component("ir-b", "ev-b"),
        metadata={
            "application_namespace": "admin",
            "architectural_role": "controller",
        },
    )
    result = IdentityResolutionService().resolve(
        _document((left, right), (first, second))
    )
    assert len(result.entities) == 2
    assert len({item.logical_id for item in result.entities}) == 2


def test_endpoint_requires_method_path_and_application_scope() -> None:
    evidence = _evidence("ev-route", "src/routes.py")
    incomplete = IREntity(
        ir_key="endpoint-one",
        kind=IREntityKind.ENDPOINT,
        name="users",
        qualified_name="src.routes.users",
        status=IRFactStatus.INFERRED,
        evidence_keys=(evidence.evidence_key,),
        metadata={"method": "GET", "application_namespace": "api"},
    )
    complete = replace(incomplete, metadata={**incomplete.metadata, "path": "/users"})
    assert (
        IdentityResolutionService()
        .resolve(_document((incomplete,), (evidence,)))
        .entities
        == ()
    )
    promoted = (
        IdentityResolutionService()
        .resolve(_document((complete,), (evidence,)))
        .entities
    )
    assert len(promoted) == 1
    assert promoted[0].kind == ArchitectureEntityKind.ENDPOINT
    assert promoted[0].name == "GET /users"


def test_same_route_with_different_handlers_is_preserved_as_conflict() -> None:
    first, second = _evidence("ev-route-a"), _evidence("ev-route-b")
    base = IREntity(
        ir_key="endpoint-a",
        kind=IREntityKind.ENDPOINT,
        name="users",
        qualified_name="src.routes.users",
        evidence_keys=(first.evidence_key,),
        metadata={
            "method": "GET",
            "path": "/users",
            "application_namespace": "api",
        },
    )
    competing = replace(
        base,
        ir_key="endpoint-b",
        qualified_name="src.admin.users",
        evidence_keys=(second.evidence_key,),
    )

    resolved = IdentityResolutionService().resolve(
        _document((base, competing), (first, second))
    )

    assert len(resolved.entities) == 2
    assert len(resolved.conflicts) == 1
    assert all(
        entity.status == ArchitectureFactStatus.CONFLICTING
        for entity in resolved.entities
    )


def test_promotion_requires_evidence_and_qualified_source_identity() -> None:
    evidence = _evidence("ev-component")
    no_evidence = replace(_component("ir-a", "ev-component"), evidence_keys=())
    no_qualified_name = replace(_component("ir-b", "ev-component"), qualified_name=None)

    resolved = IdentityResolutionService().resolve(
        _document((no_evidence, no_qualified_name), (evidence,))
    )

    assert resolved.entities == ()


def test_exact_historical_signature_reuses_prior_logical_id() -> None:
    evidence = _evidence("ev-a")
    document = _document((_component("ir-a", "ev-a"),), (evidence,))
    initial = IdentityResolutionService().resolve(document)
    entity = initial.entities[0]
    historical_id = (
        f"architecture://project/{PROJECT_ID}/repository/{REPOSITORY_ID}"
        "/controller/application~api/historical-anchor"
    )

    class History:
        def list_latest_identities(
            self, project_id: UUID, repository_id: UUID
        ) -> tuple[HistoricalIdentityRecord, ...]:
            assert project_id == PROJECT_ID and repository_id == REPOSITORY_ID
            return (
                HistoricalIdentityRecord(
                    logical_id=historical_id,
                    semantic_signature=entity.semantic_signature,
                    kind=entity.kind,
                ),
            )

    resolved = IdentityResolutionService(history=History()).resolve(document)
    assert resolved.entities[0].logical_id == historical_id


def test_historical_identity_from_another_scope_is_ignored() -> None:
    evidence = _evidence("ev-a")
    document = _document((_component("ir-a", "ev-a"),), (evidence,))
    current = IdentityResolutionService().resolve(document).entities[0]

    class OtherScopeHistory:
        def list_latest_identities(
            self, project_id: UUID, repository_id: UUID
        ) -> tuple[HistoricalIdentityRecord, ...]:
            return (
                HistoricalIdentityRecord(
                    logical_id=(
                        "architecture://project/other/repository/other/"
                        "component/application~api/controller"
                    ),
                    semantic_signature=current.semantic_signature,
                    kind=current.kind,
                ),
            )

    resolved = IdentityResolutionService(history=OtherScopeHistory()).resolve(document)

    assert resolved.entities[0].logical_id == current.logical_id


def test_ambiguous_exact_historical_matches_fail_closed() -> None:
    evidence = _evidence("ev-a")
    document = _document((_component("ir-a", "ev-a"),), (evidence,))
    current = IdentityResolutionService().resolve(document).entities[0]

    class AmbiguousHistory:
        def list_latest_identities(
            self, project_id: UUID, repository_id: UUID
        ) -> tuple[HistoricalIdentityRecord, ...]:
            prefix = (
                f"architecture://project/{PROJECT_ID}/repository/{REPOSITORY_ID}"
                "/controller/application~api/"
            )
            return (
                HistoricalIdentityRecord(
                    logical_id=f"{prefix}first",
                    semantic_signature=current.semantic_signature,
                    kind=current.kind,
                ),
                HistoricalIdentityRecord(
                    logical_id=f"{prefix}second",
                    semantic_signature=current.semantic_signature,
                    kind=current.kind,
                ),
            )

    with pytest.raises(
        ArchitectureIdentityCollisionError, match="ambiguous exact matches"
    ):
        IdentityResolutionService(history=AmbiguousHistory()).resolve(document)


def test_display_name_change_does_not_define_identity() -> None:
    evidence = _evidence("ev-a")
    original = _component("ir-a", "ev-a", name="Users Controller")
    renamed = replace(original, name="User Requests")
    first = IdentityResolutionService().resolve(_document((original,), (evidence,)))
    second = IdentityResolutionService().resolve(_document((renamed,), (evidence,)))
    assert first.entities[0].logical_id == second.entities[0].logical_id
    assert first.entities[0].semantic_signature == second.entities[0].semantic_signature


def test_collision_disambiguation_is_full_digest_and_order_independent() -> None:
    resolver = IdentityResolutionService()
    base = ArchitectureEntity(
        logical_id="architecture://same",
        semantic_signature=semantic_signature({"anchor": "one"}),
        kind=ArchitectureEntityKind.COMPONENT,
        name="One",
        namespace=("api",),
        status=ArchitectureFactStatus.CONFIRMED,
        evidence_ids=("ev-one",),
        source_ir_keys=("ir-one",),
    )
    other = replace(
        base,
        semantic_signature=semantic_signature({"anchor": "two"}),
        name="Two",
        evidence_ids=("ev-two",),
        source_ir_keys=("ir-two",),
    )
    forward, conflicts = resolver._merge_and_disambiguate([base, other])
    reverse, reverse_conflicts = resolver._merge_and_disambiguate([other, base])
    assert [item.logical_id for item in forward] == [
        item.logical_id for item in reverse
    ]
    assert conflicts == reverse_conflicts
    assert len(conflicts) == 1
    assert all("/disambiguator/sha256-" in item.logical_id for item in forward)
    assert all(item.status == ArchitectureFactStatus.CONFLICTING for item in forward)
