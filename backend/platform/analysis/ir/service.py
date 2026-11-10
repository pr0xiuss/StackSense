"""Intermediate Representation (IR) construction service (Phase 3 Module 3).

Transforms immutable F2 RepositoryInspectionResult into an immutable, parser-neutral,
versioned F3 IRDocument.
"""

from __future__ import annotations

from backend.platform.analysis.domain.constants import (
    ANALYZER_VERSION,
    IR_SCHEMA_VERSION,
)
from backend.platform.analysis.inspection.model import (
    ArtifactProcessingOutcome,
    RepositoryInspectionResult,
)
from backend.platform.analysis.ir.model import (
    IRCompleteness,
    IRConflict,
    IRConstructionError,
    IRDocument,
    IREntity,
    IREntityKind,
    IREvidence,
    IREvidenceStrength,
    IRFactStatus,
    IRRelationship,
    IRRelationshipKind,
    IRUnresolvedReason,
    IRUnresolvedReference,
    build_conflict_key,
    build_entity_key,
    build_evidence_key,
    build_relationship_key,
    build_unresolved_key,
    validate_safe_string,
)
from backend.platform.analysis.ir.validator import IRValidator
from backend.platform.analysis.syntax.model import (
    DeclarationFact,
    DeclarationKind,
    ExportFact,
    FrameworkFact,
    ImportFact,
    ManifestFact,
    ParseStatus,
    ReferenceFact,
    ReferenceKind,
)

_REFERENCE_KIND_MAP: dict[ReferenceKind, IRRelationshipKind] = {
    ReferenceKind.CALL: IRRelationshipKind.STATIC_CALL_REFERENCE,
    ReferenceKind.INHERITANCE: IRRelationshipKind.INHERITS,
    ReferenceKind.DECORATOR: IRRelationshipKind.USES_FRAMEWORK,
    ReferenceKind.REACT_COMPOSITION: IRRelationshipKind.COMPOSES,
}


def _detection_evidence_strength(
    signals: tuple[str, ...],
) -> IREvidenceStrength:
    """Classify detection evidence by the strongest signal actually present."""
    if any(signal.startswith("syntax_import:") for signal in signals):
        return IREvidenceStrength.FRAMEWORK_STRUCTURAL
    if any(signal == "shebang" or signal.startswith("shebang:") for signal in signals):
        return IREvidenceStrength.DIRECT_SOURCE
    if any(
        signal.startswith("dependency:") or "dependencies" in signal
        for signal in signals
    ):
        return IREvidenceStrength.DEPENDENCY
    return IREvidenceStrength.CONFIGURATION


class IRConstructionService:
    """Stateless transformation service converting F2 to F3 IRDocument."""

    def __init__(
        self,
        analyzer_version: str = ANALYZER_VERSION,
        validator: IRValidator | None = None,
    ) -> None:
        self._analyzer_version = analyzer_version
        self._validator = validator or IRValidator(
            expected_analyzer_version=self._analyzer_version
        )

    def construct(
        self,
        inspection_result: RepositoryInspectionResult,
        expected_schema_version: str = IR_SCHEMA_VERSION,
        validate: bool = True,
    ) -> IRDocument:
        """Construct a validated immutable IRDocument from an inspection result."""
        # 1. Consumer boundary validation
        if not isinstance(inspection_result, RepositoryInspectionResult):
            raise IRConstructionError(
                f"Expected RepositoryInspectionResult, got "
                f"{type(inspection_result).__name__}"
            )
        if inspection_result.f2_version != "1.0.0":
            raise IRConstructionError(
                f"Unsupported F2 contract version: "
                f"{inspection_result.f2_version!r} (expected '1.0.0')"
            )
        if expected_schema_version != IR_SCHEMA_VERSION:
            raise IRConstructionError(
                f"Unsupported expected IR schema version: "
                f"{expected_schema_version!r} (expected {IR_SCHEMA_VERSION!r})"
            )

        entities: dict[str, IREntity] = {}
        relationships: dict[str, IRRelationship] = {}
        evidence: dict[str, IREvidence] = {}
        unresolved: dict[str, IRUnresolvedReference] = {}
        conflicts: dict[str, IRConflict] = {}

        def add_evidence(ev: IREvidence) -> str:
            if ev.evidence_key not in evidence:
                evidence[ev.evidence_key] = ev
            return ev.evidence_key

        def add_entity(entity: IREntity) -> str:
            key = entity.ir_key
            if key in entities:
                existing = entities[key]
                if (
                    existing.kind == entity.kind
                    and existing.name == entity.name
                    and existing.qualified_name == entity.qualified_name
                ):
                    merged_ev = tuple(
                        sorted(set(existing.evidence_keys + entity.evidence_keys))
                    )
                    entities[key] = IREntity(
                        ir_key=existing.ir_key,
                        kind=existing.kind,
                        name=existing.name,
                        qualified_name=existing.qualified_name,
                        artifact_id=existing.artifact_id,
                        module_key=existing.module_key,
                        container_key=existing.container_key,
                        language=existing.language or entity.language,
                        framework=existing.framework or entity.framework,
                        status=existing.status,
                        evidence_keys=merged_ev,
                        metadata=dict(existing.metadata),
                    )
                else:
                    conf_key = build_conflict_key("entity_semantic_mismatch", key)
                    competing = tuple(
                        sorted(set(existing.evidence_keys + entity.evidence_keys))
                    )
                    conflicts[conf_key] = IRConflict(
                        conflict_key=conf_key,
                        conflict_type="entity_semantic_mismatch",
                        subject_key=key,
                        competing_evidence_keys=competing,
                        details={
                            "existing_name": existing.name,
                            "new_name": entity.name,
                        },
                    )
                    entities[key] = IREntity(
                        ir_key=existing.ir_key,
                        kind=existing.kind,
                        name=existing.name,
                        qualified_name=existing.qualified_name,
                        artifact_id=existing.artifact_id,
                        module_key=existing.module_key,
                        container_key=existing.container_key,
                        language=existing.language,
                        framework=existing.framework,
                        status=IRFactStatus.CONFLICTING,
                        evidence_keys=competing,
                        metadata=dict(existing.metadata),
                    )
            else:
                entities[key] = entity
            return key

        def add_relationship(rel: IRRelationship) -> str:
            key = rel.ir_key
            if key in relationships:
                existing = relationships[key]
                if (
                    existing.kind == rel.kind
                    and existing.source_key == rel.source_key
                    and existing.target_key == rel.target_key
                    and existing.unresolved_reference_key
                    == rel.unresolved_reference_key
                ):
                    merged_ev = tuple(
                        sorted(set(existing.evidence_keys + rel.evidence_keys))
                    )
                    relationships[key] = IRRelationship(
                        ir_key=existing.ir_key,
                        kind=existing.kind,
                        source_key=existing.source_key,
                        target_key=existing.target_key,
                        unresolved_reference_key=existing.unresolved_reference_key,
                        status=existing.status,
                        evidence_keys=merged_ev,
                        metadata=dict(existing.metadata),
                    )
                else:
                    conf_key = build_conflict_key("relationship_semantic_mismatch", key)
                    competing = tuple(
                        sorted(set(existing.evidence_keys + rel.evidence_keys))
                    )
                    conflicts[conf_key] = IRConflict(
                        conflict_key=conf_key,
                        conflict_type="relationship_semantic_mismatch",
                        subject_key=key,
                        competing_evidence_keys=competing,
                        details={
                            "existing_target": existing.target_key,
                            "new_target": rel.target_key,
                        },
                    )
                    relationships[key] = IRRelationship(
                        ir_key=existing.ir_key,
                        kind=existing.kind,
                        source_key=existing.source_key,
                        target_key=existing.target_key,
                        unresolved_reference_key=existing.unresolved_reference_key,
                        status=IRFactStatus.CONFLICTING,
                        evidence_keys=competing,
                        metadata=dict(existing.metadata),
                    )
            else:
                relationships[key] = rel
            return key

        def add_unresolved(unres: IRUnresolvedReference) -> str:
            key = unres.unresolved_key
            if key in unresolved:
                existing = unresolved[key]
                merged_ev = tuple(
                    sorted(set(existing.evidence_keys + unres.evidence_keys))
                )
                merged_candidates = tuple(
                    sorted(
                        set(existing.candidate_references + unres.candidate_references)
                    )
                )
                unresolved[key] = IRUnresolvedReference(
                    unresolved_key=existing.unresolved_key,
                    source_key=existing.source_key,
                    relationship_kind=existing.relationship_kind,
                    target_name=existing.target_name,
                    reason=existing.reason,
                    candidate_references=merged_candidates,
                    evidence_keys=merged_ev,
                    metadata=dict(existing.metadata),
                )
            else:
                unresolved[key] = unres
            return key

        # 2. Root entities: Repository and Snapshot
        repo_key = build_entity_key(
            IREntityKind.REPOSITORY, str(inspection_result.repository_id)
        )
        snapshot_key = build_entity_key(
            IREntityKind.SNAPSHOT, str(inspection_result.snapshot_id)
        )

        repo_ev_key = build_evidence_key("repository_inspection_root", "root", None)
        add_evidence(
            IREvidence(
                evidence_key=repo_ev_key,
                artifact_id=None,
                path="root",
                source_record_type="repository_inspection_root",
                strength=IREvidenceStrength.CONFIGURATION,
                upstream_analyzer_version=inspection_result.analyzer_version,
                m3_transformation_version=self._analyzer_version,
                metadata={
                    "configuration_fingerprint": (
                        inspection_result.configuration_fingerprint
                    ),
                },
            )
        )

        add_entity(
            IREntity(
                ir_key=repo_key,
                kind=IREntityKind.REPOSITORY,
                name=f"repo-{inspection_result.repository_id}",
                status=IRFactStatus.CONFIRMED,
                evidence_keys=(repo_ev_key,),
            )
        )

        add_entity(
            IREntity(
                ir_key=snapshot_key,
                kind=IREntityKind.SNAPSHOT,
                name=f"snapshot-{inspection_result.snapshot_id}",
                status=IRFactStatus.CONFIRMED,
                evidence_keys=(repo_ev_key,),
            )
        )

        add_relationship(
            IRRelationship(
                ir_key=build_relationship_key(
                    IRRelationshipKind.CONTAINS, repo_key, snapshot_key
                ),
                kind=IRRelationshipKind.CONTAINS,
                source_key=repo_key,
                target_key=snapshot_key,
                status=IRFactStatus.CONFIRMED,
                evidence_keys=(repo_ev_key,),
            )
        )

        # 3. Normalize inventory
        # Map path to artifact_key for cross-linking
        artifact_keys_by_path: dict[str, str] = {}
        for entry in inspection_result.inventory:
            art_key = build_entity_key(IREntityKind.ARTIFACT, entry.path)
            artifact_keys_by_path[entry.path] = art_key

            art_ev_key = build_evidence_key("inventory_entry", entry.path, None)
            add_evidence(
                IREvidence(
                    evidence_key=art_ev_key,
                    artifact_id=entry.artifact_id,
                    path=entry.path,
                    source_record_type="inventory_entry",
                    strength=IREvidenceStrength.CONFIGURATION,
                    upstream_analyzer_version=inspection_result.analyzer_version,
                    m3_transformation_version=self._analyzer_version,
                    metadata={
                        "role": entry.analysis_role.value,
                        "outcome": entry.processing_outcome.value,
                        "category": entry.original_category,
                        "support_level": entry.original_support_level,
                        "content_hash": entry.content_hash,
                        "size_bytes": entry.size_bytes,
                        "is_test": entry.is_test,
                        "is_generated": entry.is_generated,
                        "is_sensitive": entry.is_sensitive,
                        "reason_codes": list(entry.reason_codes),
                    },
                )
            )

            add_entity(
                IREntity(
                    ir_key=art_key,
                    kind=IREntityKind.ARTIFACT,
                    name=entry.path.split("/")[-1],
                    qualified_name=entry.path,
                    artifact_id=entry.artifact_id,
                    language=entry.detected_language,
                    status=IRFactStatus.CONFIRMED,
                    evidence_keys=(art_ev_key,),
                    metadata={
                        "role": entry.analysis_role.value,
                        "outcome": entry.processing_outcome.value,
                        "size_bytes": entry.size_bytes,
                    },
                )
            )

            add_relationship(
                IRRelationship(
                    ir_key=build_relationship_key(
                        IRRelationshipKind.CONTAINS, snapshot_key, art_key
                    ),
                    kind=IRRelationshipKind.CONTAINS,
                    source_key=snapshot_key,
                    target_key=art_key,
                    status=IRFactStatus.CONFIRMED,
                    evidence_keys=(art_ev_key,),
                )
            )

        # 4. Normalize detections
        for ld in inspection_result.language_detections:
            ld_ev_key = build_evidence_key(
                "language_detection", ld.path, None, ld.language
            )
            add_evidence(
                IREvidence(
                    evidence_key=ld_ev_key,
                    artifact_id=ld.artifact_id,
                    path=ld.path,
                    source_record_type="language_detection",
                    strength=_detection_evidence_strength(ld.evidence_signals),
                    upstream_analyzer_version=inspection_result.analyzer_version,
                    m3_transformation_version=self._analyzer_version,
                    metadata={
                        "language": ld.language,
                        "confidence": ld.confidence,
                        "signals": list(ld.evidence_signals),
                    },
                )
            )
            matched_art_key = artifact_keys_by_path.get(ld.path)
            if matched_art_key and matched_art_key in entities:
                ent = entities[matched_art_key]
                entities[matched_art_key] = IREntity(
                    ir_key=ent.ir_key,
                    kind=ent.kind,
                    name=ent.name,
                    qualified_name=ent.qualified_name,
                    artifact_id=ent.artifact_id,
                    module_key=ent.module_key,
                    container_key=ent.container_key,
                    language=ld.language or ent.language,
                    framework=ent.framework,
                    status=ent.status,
                    evidence_keys=tuple(sorted(set(ent.evidence_keys + (ld_ev_key,)))),
                    metadata={
                        **ent.metadata,
                        "language": ld.language,
                        "language_confidence": ld.confidence,
                    },
                )

        for rd in inspection_result.runtime_detections:
            rd_ev_key = build_evidence_key(
                "runtime_detection", "root", None, f"{rd.runtime}_{rd.target}"
            )
            add_evidence(
                IREvidence(
                    evidence_key=rd_ev_key,
                    artifact_id=None,
                    path="root",
                    source_record_type="runtime_detection",
                    strength=_detection_evidence_strength(rd.evidence_signals),
                    upstream_analyzer_version=inspection_result.analyzer_version,
                    m3_transformation_version=self._analyzer_version,
                    metadata={
                        "runtime": rd.runtime,
                        "target": rd.target,
                        "signals": list(rd.evidence_signals),
                    },
                )
            )

        for fd in inspection_result.framework_detections:
            fd_ev_key = build_evidence_key(
                "framework_detection", "root", None, fd.framework
            )
            add_evidence(
                IREvidence(
                    evidence_key=fd_ev_key,
                    artifact_id=None,
                    path="root",
                    source_record_type="framework_detection",
                    strength=_detection_evidence_strength(fd.evidence_signals),
                    upstream_analyzer_version=inspection_result.analyzer_version,
                    m3_transformation_version=self._analyzer_version,
                    metadata={
                        "framework": fd.framework,
                        "status": fd.status,
                        "version": fd.version,
                        "signals": list(fd.evidence_signals),
                    },
                )
            )

        # 5. Normalize Syntax Documents and Facts
        for doc in inspection_result.syntax_documents:
            doc_art_key = artifact_keys_by_path.get(doc.path)
            if not doc_art_key:
                doc_art_key = build_entity_key(IREntityKind.ARTIFACT, doc.path)
                add_entity(
                    IREntity(
                        ir_key=doc_art_key,
                        kind=IREntityKind.ARTIFACT,
                        name=doc.path.split("/")[-1],
                        qualified_name=doc.path,
                        artifact_id=doc.artifact_id,
                        language=doc.language,
                        status=IRFactStatus.CONFIRMED,
                    )
                )

            module_key = build_entity_key(IREntityKind.MODULE, doc.path)
            doc_ev_key = build_evidence_key("syntax_document", doc.path, None)
            add_evidence(
                IREvidence(
                    evidence_key=doc_ev_key,
                    artifact_id=doc.artifact_id,
                    path=doc.path,
                    source_record_type="syntax_document",
                    parser_adapter_id=doc.parser_adapter_id,
                    parser_adapter_version=doc.parser_adapter_version,
                    grammar_abi_version=doc.grammar_abi_version,
                    strength=IREvidenceStrength.DIRECT_SOURCE,
                    upstream_analyzer_version=inspection_result.analyzer_version,
                    m3_transformation_version=self._analyzer_version,
                    metadata={
                        "language": doc.language,
                        "parse_status": doc.parse_status.value,
                    },
                )
            )

            add_entity(
                IREntity(
                    ir_key=module_key,
                    kind=IREntityKind.MODULE,
                    name=doc.path.split("/")[-1],
                    qualified_name=doc.path,
                    artifact_id=doc.artifact_id,
                    language=doc.language,
                    status=IRFactStatus.CONFIRMED,
                    evidence_keys=(doc_ev_key,),
                )
            )

            add_relationship(
                IRRelationship(
                    ir_key=build_relationship_key(
                        IRRelationshipKind.CONTAINS, doc_art_key, module_key
                    ),
                    kind=IRRelationshipKind.CONTAINS,
                    source_key=doc_art_key,
                    target_key=module_key,
                    status=IRFactStatus.CONFIRMED,
                    evidence_keys=(doc_ev_key,),
                )
            )

            # Build document-local declaration indexes for exact local resolution
            local_declarations_by_name: dict[str, list[tuple[str, str, str | None]]] = (
                {}
            )
            local_symbols_by_fact_key: dict[str, str] = {}
            local_container_by_fact_key: dict[str, str | None] = {}
            for fact in doc.facts:
                if isinstance(fact, DeclarationFact):
                    decl_kind = (
                        IREntityKind.MODULE
                        if fact.kind
                        in (DeclarationKind.MODULE, DeclarationKind.PACKAGE)
                        else (
                            IREntityKind.COMPONENT
                            if fact.kind == DeclarationKind.REACT_COMPONENT
                            else IREntityKind.SYMBOL
                        )
                    )
                    dr = fact.declaration_range
                    range_disc = f"{dr.start_byte}_{dr.end_byte}"
                    sym_key = build_entity_key(
                        decl_kind, doc.path, fact.name, range_disc
                    )
                    local_declarations_by_name.setdefault(fact.name, []).append(
                        (sym_key, fact.fact_key, fact.container_key)
                    )
                    local_symbols_by_fact_key[fact.fact_key] = sym_key
                    local_container_by_fact_key[fact.fact_key] = fact.container_key

            def resolve_local_declaration(
                name: str,
                source_fact_key: str | None,
                declarations_by_name: dict[
                    str, list[tuple[str, str, str | None]]
                ] = local_declarations_by_name,
                container_by_fact_key: dict[
                    str, str | None
                ] = local_container_by_fact_key,
            ) -> list[str]:
                """Resolve a name in the nearest visible document-local scope."""
                declarations = declarations_by_name.get(name, [])
                if not declarations:
                    return []
                if source_fact_key is not None:
                    recursive = [
                        ir_key
                        for ir_key, fact_key, _ in declarations
                        if fact_key == source_fact_key
                    ]
                    if recursive:
                        return recursive

                scope = source_fact_key
                visited: set[str | None] = set()
                while scope not in visited:
                    visited.add(scope)
                    scoped = [
                        ir_key
                        for ir_key, _, container_key in declarations
                        if container_key == scope
                    ]
                    if scoped:
                        return scoped
                    scope = (
                        container_by_fact_key.get(scope) if scope is not None else None
                    )
                    if scope is None:
                        module_scoped = [
                            ir_key
                            for ir_key, _, container_key in declarations
                            if container_key is None
                        ]
                        return module_scoped
                return []

            # Normalize facts
            for fact in doc.facts:
                if isinstance(fact, DeclarationFact):
                    entity_kind = (
                        IREntityKind.MODULE
                        if fact.kind
                        in (DeclarationKind.MODULE, DeclarationKind.PACKAGE)
                        else (
                            IREntityKind.COMPONENT
                            if fact.kind == DeclarationKind.REACT_COMPONENT
                            else IREntityKind.SYMBOL
                        )
                    )
                    dr = fact.declaration_range
                    range_disc = f"{dr.start_byte}_{dr.end_byte}"
                    sym_key = build_entity_key(
                        entity_kind, doc.path, fact.name, range_disc
                    )
                    if fact.signature_text:
                        validate_safe_string("signature_text", fact.signature_text)
                    container_ir_key = None
                    if fact.container_key is not None:
                        container_ir_key = local_symbols_by_fact_key.get(
                            fact.container_key
                        )
                        if container_ir_key is None:
                            raise IRConstructionError(
                                "Declaration container_key does not reference a "
                                f"declaration in {doc.path}: {fact.container_key}"
                            )
                    fact_ev_key = build_evidence_key(
                        "declaration_fact", doc.path, fact.fact_key
                    )
                    add_evidence(
                        IREvidence(
                            evidence_key=fact_ev_key,
                            artifact_id=doc.artifact_id,
                            path=doc.path,
                            source_record_type="declaration_fact",
                            source_fact_key=fact.fact_key,
                            source_range=fact.declaration_range,
                            parser_adapter_id=doc.parser_adapter_id,
                            parser_adapter_version=doc.parser_adapter_version,
                            grammar_abi_version=doc.grammar_abi_version,
                            strength=IREvidenceStrength.DIRECT_SOURCE,
                            upstream_analyzer_version=inspection_result.analyzer_version,
                            m3_transformation_version=self._analyzer_version,
                            metadata={
                                "declaration_kind": fact.kind.value,
                                "modifiers": list(fact.modifiers),
                                "decorators": list(fact.decorators),
                                "signature_text": fact.signature_text,
                            },
                        )
                    )

                    add_entity(
                        IREntity(
                            ir_key=sym_key,
                            kind=entity_kind,
                            name=fact.name,
                            qualified_name=fact.qualified_name
                            or f"{doc.path}::{fact.name}",
                            artifact_id=doc.artifact_id,
                            module_key=module_key,
                            container_key=container_ir_key,
                            language=doc.language,
                            status=IRFactStatus.CONFIRMED,
                            evidence_keys=(fact_ev_key,),
                            metadata={
                                "declaration_kind": fact.kind.value,
                                "modifiers": list(fact.modifiers),
                                "decorators": list(fact.decorators),
                            },
                        )
                    )

                    add_relationship(
                        IRRelationship(
                            ir_key=build_relationship_key(
                                IRRelationshipKind.DECLARES,
                                container_ir_key or module_key,
                                sym_key,
                            ),
                            kind=IRRelationshipKind.DECLARES,
                            source_key=container_ir_key or module_key,
                            target_key=sym_key,
                            status=IRFactStatus.CONFIRMED,
                            evidence_keys=(fact_ev_key,),
                        )
                    )

                elif isinstance(fact, ImportFact):
                    fact_ev_key = build_evidence_key(
                        "import_fact", doc.path, fact.fact_key
                    )
                    add_evidence(
                        IREvidence(
                            evidence_key=fact_ev_key,
                            artifact_id=doc.artifact_id,
                            path=doc.path,
                            source_record_type="import_fact",
                            source_fact_key=fact.fact_key,
                            source_range=fact.range,
                            parser_adapter_id=doc.parser_adapter_id,
                            parser_adapter_version=doc.parser_adapter_version,
                            grammar_abi_version=doc.grammar_abi_version,
                            strength=IREvidenceStrength.DIRECT_SOURCE,
                            upstream_analyzer_version=inspection_result.analyzer_version,
                            m3_transformation_version=self._analyzer_version,
                            metadata={
                                "source_module": fact.source_module,
                                "imported_name": fact.imported_name,
                                "local_alias": fact.local_alias,
                                "is_type_only": fact.is_type_only,
                                "is_commonjs": fact.is_commonjs,
                                "import_kind": fact.kind.value,
                            },
                        )
                    )

                    unres_key = build_unresolved_key(
                        module_key,
                        IRRelationshipKind.IMPORTS,
                        fact.source_module,
                        fact.fact_key,
                    )
                    add_unresolved(
                        IRUnresolvedReference(
                            unresolved_key=unres_key,
                            source_key=module_key,
                            relationship_kind=IRRelationshipKind.IMPORTS,
                            target_name=fact.source_module,
                            reason=IRUnresolvedReason.NOT_FOUND,
                            candidate_references=(fact.source_module,),
                            evidence_keys=(fact_ev_key,),
                            metadata={
                                "source_module": fact.source_module,
                                "imported_name": fact.imported_name,
                                "local_alias": fact.local_alias,
                            },
                        )
                    )

                    add_relationship(
                        IRRelationship(
                            ir_key=build_relationship_key(
                                IRRelationshipKind.IMPORTS, module_key, None, unres_key
                            ),
                            kind=IRRelationshipKind.IMPORTS,
                            source_key=module_key,
                            target_key=None,
                            unresolved_reference_key=unres_key,
                            status=IRFactStatus.CONFIRMED,
                            evidence_keys=(fact_ev_key,),
                            metadata={
                                "source_module": fact.source_module,
                                "imported_name": fact.imported_name,
                                "local_alias": fact.local_alias,
                            },
                        )
                    )

                elif isinstance(fact, ExportFact):
                    fact_ev_key = build_evidence_key(
                        "export_fact", doc.path, fact.fact_key
                    )
                    add_evidence(
                        IREvidence(
                            evidence_key=fact_ev_key,
                            artifact_id=doc.artifact_id,
                            path=doc.path,
                            source_record_type="export_fact",
                            source_fact_key=fact.fact_key,
                            source_range=fact.range,
                            parser_adapter_id=doc.parser_adapter_id,
                            parser_adapter_version=doc.parser_adapter_version,
                            grammar_abi_version=doc.grammar_abi_version,
                            strength=IREvidenceStrength.DIRECT_SOURCE,
                            upstream_analyzer_version=inspection_result.analyzer_version,
                            m3_transformation_version=self._analyzer_version,
                            metadata={
                                "exported_name": fact.exported_name,
                                "local_name": fact.local_name,
                                "source_module": fact.source_module,
                                "is_type_only": fact.is_type_only,
                                "is_commonjs": fact.is_commonjs,
                                "export_kind": fact.kind.value,
                            },
                        )
                    )

                    lookup_name = fact.local_name or fact.exported_name
                    candidates = resolve_local_declaration(lookup_name, None)
                    target_key: str | None = None
                    export_unres_key: str | None = None
                    if len(candidates) == 1:
                        target_key = candidates[0]
                    elif len(candidates) > 1:
                        export_unres_key = build_unresolved_key(
                            module_key,
                            IRRelationshipKind.EXPORTS,
                            lookup_name,
                            fact.fact_key,
                        )
                        add_unresolved(
                            IRUnresolvedReference(
                                unresolved_key=export_unres_key,
                                source_key=module_key,
                                relationship_kind=IRRelationshipKind.EXPORTS,
                                target_name=lookup_name,
                                reason=IRUnresolvedReason.AMBIGUOUS,
                                candidate_references=tuple(candidates),
                                evidence_keys=(fact_ev_key,),
                            )
                        )
                    else:
                        export_unres_key = build_unresolved_key(
                            module_key,
                            IRRelationshipKind.EXPORTS,
                            lookup_name,
                            fact.fact_key,
                        )
                        add_unresolved(
                            IRUnresolvedReference(
                                unresolved_key=export_unres_key,
                                source_key=module_key,
                                relationship_kind=IRRelationshipKind.EXPORTS,
                                target_name=lookup_name,
                                reason=IRUnresolvedReason.NOT_FOUND,
                                candidate_references=(lookup_name,),
                                evidence_keys=(fact_ev_key,),
                            )
                        )

                    add_relationship(
                        IRRelationship(
                            ir_key=build_relationship_key(
                                IRRelationshipKind.EXPORTS,
                                module_key,
                                target_key,
                                export_unres_key or "none",
                            ),
                            kind=IRRelationshipKind.EXPORTS,
                            source_key=module_key,
                            target_key=target_key,
                            unresolved_reference_key=export_unres_key,
                            status=(
                                IRFactStatus.CONFIRMED
                                if target_key
                                else (
                                    IRFactStatus.CONFLICTING
                                    if len(candidates) > 1
                                    else IRFactStatus.UNRESOLVED
                                )
                            ),
                            evidence_keys=(fact_ev_key,),
                            metadata={"exported_name": fact.exported_name},
                        )
                    )

                elif isinstance(fact, ReferenceFact):
                    fact_ev_key = build_evidence_key(
                        "reference_fact", doc.path, fact.fact_key
                    )
                    add_evidence(
                        IREvidence(
                            evidence_key=fact_ev_key,
                            artifact_id=doc.artifact_id,
                            path=doc.path,
                            source_record_type="reference_fact",
                            source_fact_key=fact.fact_key,
                            source_range=fact.range,
                            parser_adapter_id=doc.parser_adapter_id,
                            parser_adapter_version=doc.parser_adapter_version,
                            grammar_abi_version=doc.grammar_abi_version,
                            strength=IREvidenceStrength.DIRECT_SOURCE,
                            upstream_analyzer_version=inspection_result.analyzer_version,
                            m3_transformation_version=self._analyzer_version,
                            metadata={
                                "reference_kind": fact.kind.value,
                                "target_name": fact.target_name,
                            },
                        )
                    )

                    rel_kind = _REFERENCE_KIND_MAP.get(fact.kind)
                    if rel_kind is None:
                        # NAME and ATTRIBUTE facts establish source evidence but do
                        # not prove a call or another supported F3 relationship.
                        continue

                    source_key = module_key
                    if fact.source_declaration_key:
                        source_key = local_symbols_by_fact_key.get(
                            fact.source_declaration_key, module_key
                        )

                    candidates = resolve_local_declaration(
                        fact.target_name, fact.source_declaration_key
                    )
                    target_key = None
                    ref_unres_key = None
                    if len(candidates) == 1:
                        target_key = candidates[0]
                    elif len(candidates) > 1:
                        ref_unres_key = build_unresolved_key(
                            source_key, rel_kind, fact.target_name, fact.fact_key
                        )
                        add_unresolved(
                            IRUnresolvedReference(
                                unresolved_key=ref_unres_key,
                                source_key=source_key,
                                relationship_kind=rel_kind,
                                target_name=fact.target_name,
                                reason=IRUnresolvedReason.AMBIGUOUS,
                                candidate_references=tuple(candidates),
                                evidence_keys=(fact_ev_key,),
                            )
                        )
                    else:
                        ref_unres_key = build_unresolved_key(
                            source_key, rel_kind, fact.target_name, fact.fact_key
                        )
                        add_unresolved(
                            IRUnresolvedReference(
                                unresolved_key=ref_unres_key,
                                source_key=source_key,
                                relationship_kind=rel_kind,
                                target_name=fact.target_name,
                                reason=IRUnresolvedReason.NOT_FOUND,
                                candidate_references=(fact.target_name,),
                                evidence_keys=(fact_ev_key,),
                            )
                        )

                    add_relationship(
                        IRRelationship(
                            ir_key=build_relationship_key(
                                rel_kind,
                                source_key,
                                target_key,
                                ref_unres_key or fact.fact_key,
                            ),
                            kind=rel_kind,
                            source_key=source_key,
                            target_key=target_key,
                            unresolved_reference_key=ref_unres_key,
                            status=(
                                IRFactStatus.CONFIRMED
                                if target_key
                                else (
                                    IRFactStatus.CONFLICTING
                                    if len(candidates) > 1
                                    else IRFactStatus.UNRESOLVED
                                )
                            ),
                            evidence_keys=(fact_ev_key,),
                            metadata={
                                "reference_kind": fact.kind.value,
                                "target_name": fact.target_name,
                            },
                        )
                    )

                elif isinstance(fact, FrameworkFact):
                    fact_ev_key = build_evidence_key(
                        "framework_fact", doc.path, fact.fact_key
                    )
                    add_evidence(
                        IREvidence(
                            evidence_key=fact_ev_key,
                            artifact_id=doc.artifact_id,
                            path=doc.path,
                            source_record_type="framework_fact",
                            source_fact_key=fact.fact_key,
                            source_range=fact.range,
                            framework_name=fact.framework_name,
                            supporting_fact_keys=fact.supporting_fact_keys,
                            strength=IREvidenceStrength.FRAMEWORK_STRUCTURAL,
                            upstream_analyzer_version=inspection_result.analyzer_version,
                            m3_transformation_version=self._analyzer_version,
                            metadata={
                                "fact_type": fact.fact_type,
                                "details": dict(fact.details),
                            },
                        )
                    )

                    if (
                        "route" in fact.fact_type.lower()
                        or "endpoint" in fact.fact_type.lower()
                    ):
                        ep_start = str(fact.range.start_byte if fact.range else 0)
                        ep_key = build_entity_key(
                            IREntityKind.ENDPOINT, doc.path, fact.name, ep_start
                        )
                        add_entity(
                            IREntity(
                                ir_key=ep_key,
                                kind=IREntityKind.ENDPOINT,
                                name=fact.name,
                                qualified_name=f"{doc.path}::{fact.name}",
                                artifact_id=doc.artifact_id,
                                module_key=module_key,
                                framework=fact.framework_name,
                                status=IRFactStatus.INFERRED,
                                evidence_keys=(fact_ev_key,),
                                metadata=dict(fact.details),
                            )
                        )
                        add_relationship(
                            IRRelationship(
                                ir_key=build_relationship_key(
                                    IRRelationshipKind.DECLARES_ROUTE,
                                    module_key,
                                    ep_key,
                                ),
                                kind=IRRelationshipKind.DECLARES_ROUTE,
                                source_key=module_key,
                                target_key=ep_key,
                                status=IRFactStatus.CONFIRMED,
                                evidence_keys=(fact_ev_key,),
                            )
                        )
                    else:
                        add_relationship(
                            IRRelationship(
                                ir_key=build_relationship_key(
                                    IRRelationshipKind.USES_FRAMEWORK,
                                    module_key,
                                    None,
                                    f"{fact.framework_name}_{fact.fact_key}",
                                ),
                                kind=IRRelationshipKind.USES_FRAMEWORK,
                                source_key=module_key,
                                target_key=None,
                                status=IRFactStatus.CONFIRMED,
                                evidence_keys=(fact_ev_key,),
                                metadata={
                                    "framework": fact.framework_name,
                                    "fact_type": fact.fact_type,
                                    **{
                                        key: fact.details[key]
                                        for key in ("path", "mount_target")
                                        if isinstance(fact.details.get(key), str)
                                    },
                                },
                            )
                        )

                elif isinstance(fact, ManifestFact):
                    fact_ev_key = build_evidence_key(
                        "manifest_fact", doc.path, fact.fact_key
                    )
                    add_evidence(
                        IREvidence(
                            evidence_key=fact_ev_key,
                            artifact_id=doc.artifact_id,
                            path=doc.path,
                            source_record_type="manifest_fact",
                            source_fact_key=fact.fact_key,
                            source_range=fact.range,
                            strength=IREvidenceStrength.DEPENDENCY,
                            upstream_analyzer_version=inspection_result.analyzer_version,
                            m3_transformation_version=self._analyzer_version,
                            metadata={
                                "manifest_type": fact.manifest_type,
                                "name": fact.name,
                                "version": fact.version,
                                "scope": fact.scope,
                                "is_dev": fact.is_dev,
                            },
                        )
                    )

                    add_relationship(
                        IRRelationship(
                            ir_key=build_relationship_key(
                                IRRelationshipKind.DECLARES_DEPENDENCY,
                                doc_art_key,
                                None,
                                fact.name,
                            ),
                            kind=IRRelationshipKind.DECLARES_DEPENDENCY,
                            source_key=doc_art_key,
                            target_key=None,
                            unresolved_reference_key=None,
                            status=IRFactStatus.CONFIRMED,
                            evidence_keys=(fact_ev_key,),
                            metadata={
                                "dependency_name": fact.name,
                                "version": fact.version,
                                "is_dev": fact.is_dev,
                                "scope": fact.scope,
                                "manifest_type": fact.manifest_type,
                            },
                        )
                    )

        # 6. Completeness calculation
        total_inv = len(inspection_result.inventory)
        analyzed_count = sum(
            1
            for e in inspection_result.inventory
            if e.processing_outcome
            in (
                ArtifactProcessingOutcome.ANALYZED,
                ArtifactProcessingOutcome.ANALYZED_WITH_WARNINGS,
            )
        )
        failed_count = sum(
            1
            for e in inspection_result.inventory
            if e.processing_outcome == ArtifactProcessingOutcome.FAILED
        )
        not_proc_count = sum(
            1
            for e in inspection_result.inventory
            if e.processing_outcome == ArtifactProcessingOutcome.NOT_PROCESSED
        )
        syntax_failed = sum(
            1
            for d in inspection_result.syntax_documents
            if d.parse_status in (ParseStatus.FAILED, ParseStatus.PARSED_WITH_ERRORS)
        )
        is_partial = (
            failed_count > 0
            or not_proc_count > 0
            or syntax_failed > 0
            or inspection_result.coverage.failed_artifacts > 0
        )

        completeness = IRCompleteness(
            total_inventory_artifacts=total_inv,
            analyzed_artifacts=analyzed_count,
            failed_artifacts=failed_count,
            total_syntax_documents=len(inspection_result.syntax_documents),
            total_syntax_facts=sum(
                len(d.facts) for d in inspection_result.syntax_documents
            ),
            total_entities=len(entities),
            total_relationships=len(relationships),
            total_unresolved_references=len(unresolved),
            total_conflicts=len(conflicts),
            is_partial=is_partial,
        )

        # 7. Construct and return canonical IRDocument
        ir_doc = IRDocument(
            analysis_id=inspection_result.analysis_id,
            project_id=inspection_result.project_id,
            repository_id=inspection_result.repository_id,
            snapshot_id=inspection_result.snapshot_id,
            configuration_fingerprint=inspection_result.configuration_fingerprint,
            entities=tuple(entities.values()),
            relationships=tuple(relationships.values()),
            evidence=tuple(evidence.values()),
            unresolved_references=tuple(unresolved.values()),
            conflicts=tuple(conflicts.values()),
            completeness=completeness,
            ir_schema_version=IR_SCHEMA_VERSION,
            f2_version=inspection_result.f2_version,
            analyzer_version=self._analyzer_version,
            diagnostic_ids=inspection_result.diagnostic_ids,
        )

        if validate:
            self._validator.validate(ir_doc)

        return ir_doc
