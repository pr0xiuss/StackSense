"""Evidence-backed Architecture Model construction from frozen F3."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import replace
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID

from backend.platform.analysis.architecture.identity import (
    IdentityResolutionService,
    map_ir_evidence,
)
from backend.platform.analysis.architecture.model import (
    ArchitectureCompleteness,
    ArchitectureConflict,
    ArchitectureDocument,
    ArchitectureEntity,
    ArchitectureEntityKind,
    ArchitectureEvidence,
    ArchitectureFactStatus,
    ArchitectureIdentityConflict,
    ArchitectureRelationship,
    ArchitectureRelationshipKind,
    ArchitectureUnresolvedReason,
    ArchitectureUnresolvedRelationship,
    ResolvedArchitectureInput,
    ValidatedArchitectureModel,
    build_relationship_logical_id,
    encode_identity_component,
    semantic_signature,
)
from backend.platform.analysis.architecture.validator import ArchitectureValidator
from backend.platform.analysis.ir.model import (
    IRConflict,
    IRDocument,
    IREntity,
    IREvidence,
    IRFactStatus,
    IRRelationshipKind,
    IRUnresolvedReason,
)

_RELATIONSHIP_RULES = {
    IRRelationshipKind.CONTAINS: (
        ArchitectureRelationshipKind.CONTAINS,
        "m4.relationship.contains.v1",
    ),
    IRRelationshipKind.DECLARES: (
        ArchitectureRelationshipKind.CONTAINS,
        "m4.relationship.declares_contains.v1",
    ),
    IRRelationshipKind.IMPORTS: (
        ArchitectureRelationshipKind.IMPORTS,
        "m4.relationship.static_import.v1",
    ),
    IRRelationshipKind.STATIC_CALL_REFERENCE: (
        ArchitectureRelationshipKind.CALLS,
        "m4.relationship.static_call.v1",
    ),
    IRRelationshipKind.INHERITS: (
        ArchitectureRelationshipKind.EXTENDS,
        "m4.relationship.static_inheritance.v1",
    ),
    IRRelationshipKind.SOURCE_REFERENCES_DEPENDENCY: (
        ArchitectureRelationshipKind.DEPENDS_ON,
        "m4.relationship.source_dependency.v1",
    ),
    IRRelationshipKind.COMPOSES: (
        ArchitectureRelationshipKind.DEPENDS_ON,
        "m4.relationship.static_composition.v1",
    ),
    IRRelationshipKind.DECLARES_ROUTE: (
        ArchitectureRelationshipKind.CONTAINS,
        "m4.relationship.declares_route.v1",
    ),
}

_UNRESOLVED_REASON_MAP = {
    IRUnresolvedReason.NOT_FOUND: ArchitectureUnresolvedReason.NOT_FOUND,
    IRUnresolvedReason.AMBIGUOUS: ArchitectureUnresolvedReason.AMBIGUOUS,
    IRUnresolvedReason.DYNAMIC: ArchitectureUnresolvedReason.DYNAMIC,
    IRUnresolvedReason.UNSUPPORTED: ArchitectureUnresolvedReason.UNSUPPORTED,
    IRUnresolvedReason.INCOMPLETE_INPUT: ArchitectureUnresolvedReason.INCOMPLETE_INPUT,
}


class ArchitectureBuilder:
    """Construct and validate one canonical in-memory Architecture Model."""

    def __init__(
        self,
        validator: ArchitectureValidator,
        resolver: IdentityResolutionService | None = None,
    ) -> None:
        self._validator = validator
        self._resolver = resolver or IdentityResolutionService()

    def build(
        self, document: IRDocument, architecture_version_id: UUID
    ) -> ValidatedArchitectureModel:
        resolved = self._resolver.resolve(document)
        model = self.construct_candidate(document, resolved, architecture_version_id)
        return self._validator.validate(model)

    def construct_candidate(
        self,
        document: IRDocument,
        resolved: ResolvedArchitectureInput,
        architecture_version_id: UUID,
    ) -> ArchitectureDocument:
        """Construct an unvalidated candidate from the immutable M4 handoff.

        Stage orchestration deliberately separates durable candidate reservation
        from validation/publication.  The caller must validate the returned
        document before it can be published.
        """
        if resolved.analysis_id != document.analysis_id:
            raise ValueError("resolved architecture input does not match F3 analysis")
        return self._construct(document, resolved, architecture_version_id)

    def validate(self, document: ArchitectureDocument) -> ValidatedArchitectureModel:
        """Validate a constructed candidate through the configured validator."""
        return self._validator.validate(document)

    def _construct(
        self,
        source: IRDocument,
        resolved: ResolvedArchitectureInput,
        architecture_version_id: UUID,
    ) -> ArchitectureDocument:
        ir_to_entities = _index_entities_by_ir_key(resolved.entities)
        entities_by_id = {item.logical_id: item for item in resolved.entities}
        source_entities_by_key = {item.ir_key: item for item in source.entities}
        source_evidence = {item.evidence_key: item for item in source.evidence}
        evidence = {item.logical_id: item for item in resolved.evidence}
        relationships: list[ArchitectureRelationship] = []
        unresolved_relationships: list[ArchitectureUnresolvedRelationship] = []
        unresolved_by_key = {
            item.unresolved_key: item for item in source.unresolved_references
        }

        for item in source.relationships:
            rule = _RELATIONSHIP_RULES.get(item.kind)
            source_logical_id = _single_identity(ir_to_entities, item.source_key)
            if rule is None or source_logical_id is None:
                continue
            kind, rule_id = rule
            if (
                kind == ArchitectureRelationshipKind.CALLS
                and entities_by_id[source_logical_id].kind
                == ArchitectureEntityKind.MODULE
            ):
                kind = ArchitectureRelationshipKind.DEPENDS_ON
                rule_id = "m4.relationship.module_static_reference.v1"
            if item.target_key is not None:
                target_logical_id = _single_identity(ir_to_entities, item.target_key)
                if target_logical_id is None:
                    target = source_entities_by_key.get(item.target_key)
                    if not _preserve_unpromoted_relationship(
                        item.kind,
                        entities_by_id[source_logical_id],
                        target,
                    ):
                        # Low-level IR containment may intentionally terminate at
                        # a symbol that is not architecturally promoted. The same
                        # applies to static source facts that do not establish an
                        # architectural target.
                        continue
                    mapped_evidence = _map_evidence_ids(
                        source.snapshot_id,
                        source_evidence,
                        item.evidence_keys,
                        evidence,
                    )
                    unresolved_relationships.append(
                        _unresolved_relationship(
                            source,
                            kind=kind,
                            source_logical_id=source_logical_id,
                            target_descriptor=_entity_descriptor(
                                target, item.target_key
                            ),
                            reason=ArchitectureUnresolvedReason.UNSUPPORTED,
                            status=ArchitectureFactStatus.UNRESOLVED,
                            evidence_ids=mapped_evidence,
                            source_ir_keys=(item.ir_key,),
                            candidate_references=(item.target_key,),
                            rule_id=f"{rule_id}.unpromoted_target",
                        )
                    )
                    continue
                if source_logical_id == target_logical_id:
                    continue
                mapped_evidence = _map_evidence_ids(
                    source.snapshot_id,
                    source_evidence,
                    item.evidence_keys,
                    evidence,
                )
                kind, rule_id = _relationship_kind_for_target(
                    kind,
                    rule_id,
                    entities_by_id[source_logical_id],
                    entities_by_id[target_logical_id],
                    item.metadata,
                )
                relationships.append(
                    _relationship(
                        source,
                        kind=kind,
                        source_logical_id=source_logical_id,
                        target_logical_id=target_logical_id,
                        status=_status(item.status),
                        evidence_ids=mapped_evidence,
                        source_ir_keys=(item.ir_key,),
                        rule_id=rule_id,
                    )
                )
            elif item.unresolved_reference_key is not None:
                unresolved = unresolved_by_key[item.unresolved_reference_key]
                target_logical_id = _resolve_descriptor_identity(
                    unresolved.target_name,
                    source_entity=entities_by_id[source_logical_id],
                    entities=resolved.entities,
                )
                if target_logical_id is not None:
                    if source_logical_id != target_logical_id:
                        mapped_evidence = _map_evidence_ids(
                            source.snapshot_id,
                            source_evidence,
                            tuple(
                                sorted(
                                    set(item.evidence_keys + unresolved.evidence_keys)
                                )
                            ),
                            evidence,
                        )
                        resolved_kind, resolved_rule_id = _relationship_kind_for_target(
                            kind,
                            rule_id,
                            entities_by_id[source_logical_id],
                            entities_by_id[target_logical_id],
                            item.metadata,
                        )
                        relationships.append(
                            _relationship(
                                source,
                                kind=resolved_kind,
                                source_logical_id=source_logical_id,
                                target_logical_id=target_logical_id,
                                status=ArchitectureFactStatus.INFERRED,
                                evidence_ids=mapped_evidence,
                                source_ir_keys=(item.ir_key, unresolved.unresolved_key),
                                rule_id=(
                                    f"{resolved_rule_id}.exact_cross_file_resolution"
                                ),
                            )
                        )
                    continue
                if not _preserve_unresolved_relationship(
                    item.kind,
                    entities_by_id[source_logical_id],
                    unresolved.target_name,
                ):
                    continue
                mapped_evidence = _map_evidence_ids(
                    source.snapshot_id,
                    source_evidence,
                    tuple(sorted(set(item.evidence_keys + unresolved.evidence_keys))),
                    evidence,
                )
                unresolved_relationships.append(
                    _unresolved_relationship(
                        source,
                        kind=kind,
                        source_logical_id=source_logical_id,
                        target_descriptor=unresolved.target_name,
                        reason=_UNRESOLVED_REASON_MAP[unresolved.reason],
                        status=_status(item.status),
                        evidence_ids=mapped_evidence,
                        source_ir_keys=(item.ir_key, unresolved.unresolved_key),
                        candidate_references=unresolved.candidate_references,
                        rule_id=rule_id,
                    )
                )

        relationships.extend(_scope_relationships(source, resolved.entities, evidence))
        relationships.extend(_route_handler_relationships(source, resolved.entities))
        merged_relationships = _merge_relationships(relationships)
        merged_unresolved = _merge_unresolved(unresolved_relationships)
        conflicts = [_identity_conflict(source, item) for item in resolved.conflicts]
        conflicts.extend(
            _source_conflict(source, item, source_evidence, evidence)
            for item in source.conflicts
        )

        completeness = ArchitectureCompleteness(
            total_inventory_artifacts=source.completeness.total_inventory_artifacts,
            analyzed_artifacts=source.completeness.analyzed_artifacts,
            failed_artifacts=source.completeness.failed_artifacts,
            total_syntax_documents=source.completeness.total_syntax_documents,
            total_syntax_facts=source.completeness.total_syntax_facts,
            source_entities=len(source.entities),
            source_relationships=len(source.relationships),
            source_unresolved_references=len(source.unresolved_references),
            source_conflicts=len(source.conflicts),
            architecture_entities=len(resolved.entities),
            architecture_relationships=len(merged_relationships),
            architecture_unresolved_relationships=len(merged_unresolved),
            architecture_conflicts=len(conflicts),
            is_partial=source.completeness.is_partial,
        )
        return ArchitectureDocument(
            architecture_version_id=architecture_version_id,
            analysis_id=source.analysis_id,
            project_id=source.project_id,
            repository_id=source.repository_id,
            snapshot_id=source.snapshot_id,
            configuration_fingerprint=source.configuration_fingerprint,
            analyzer_version=source.analyzer_version,
            ir_schema_version=source.ir_schema_version,
            architecture_schema_version=resolved.architecture_schema_version,
            entities=resolved.entities,
            relationships=tuple(merged_relationships),
            evidence=tuple(evidence.values()),
            unresolved_relationships=tuple(merged_unresolved),
            conflicts=tuple(conflicts),
            completeness=completeness,
            source_diagnostic_ids=source.diagnostic_ids,
        )


class ArchitectureFoundationBuilder:
    """Batch 1 compatibility facade for identity-only consumers."""

    def __init__(self, resolver: IdentityResolutionService | None = None) -> None:
        self._resolver = resolver or IdentityResolutionService()

    def resolve_foundation(self, document: IRDocument) -> ResolvedArchitectureInput:
        return self._resolver.resolve(document)


def _index_entities_by_ir_key(
    entities: tuple[ArchitectureEntity, ...],
) -> dict[str, tuple[str, ...]]:
    values: dict[str, list[str]] = defaultdict(list)
    for entity in entities:
        for source_key in entity.source_ir_keys:
            values[source_key].append(entity.logical_id)
    return {key: tuple(sorted(set(ids))) for key, ids in values.items()}


def _single_identity(index: dict[str, tuple[str, ...]], ir_key: str) -> str | None:
    values = index.get(ir_key, ())
    return values[0] if len(values) == 1 else None


def _entity_descriptor(entity: IREntity | None, fallback: str) -> str:
    if entity is None:
        return fallback
    return entity.qualified_name or entity.name


def _resolve_descriptor_identity(
    descriptor: str,
    *,
    source_entity: ArchitectureEntity,
    entities: tuple[ArchitectureEntity, ...],
) -> str | None:
    """Resolve one static import descriptor to an exact module/dependency entity."""
    dependency_matches = [
        entity.logical_id
        for entity in entities
        if isinstance(entity.metadata.get("dependency_name"), str)
        and _dependency_matches_descriptor(
            str(entity.metadata["dependency_name"]), descriptor
        )
        and entity.metadata.get("application_namespace")
        == source_entity.metadata.get("application_namespace")
    ]
    if len(dependency_matches) == 1:
        return dependency_matches[0]

    source_path = source_entity.metadata.get("qualified_name")
    module_paths = {
        str(entity.metadata["qualified_name"]): entity.logical_id
        for entity in entities
        if entity.kind == ArchitectureEntityKind.MODULE
        and isinstance(entity.metadata.get("qualified_name"), str)
    }
    candidates = _module_path_candidates(
        descriptor,
        source_path if isinstance(source_path, str) else None,
    )
    exact = {
        logical_id
        for path, logical_id in module_paths.items()
        if _module_path_matches(path, candidates)
    }
    return next(iter(exact)) if len(exact) == 1 else None


def _dependency_matches_descriptor(dependency_name: str, descriptor: str) -> bool:
    if dependency_name.startswith("@"):
        descriptor_root = "/".join(descriptor.split("/")[:2])
    else:
        descriptor_root = descriptor.split("/", maxsplit=1)[0].split(".", maxsplit=1)[0]
    return descriptor_root == dependency_name


def _module_path_candidates(
    descriptor: str, source_path: str | None
) -> tuple[str, ...]:
    normalized = descriptor.replace("\\", "/")
    bases: set[str] = set()
    if normalized.startswith(".") and source_path is not None:
        parent = PurePosixPath(source_path).parent
        parts: list[str] = list(parent.parts)
        for part in PurePosixPath(normalized).parts:
            if part in {"", "."}:
                continue
            if part == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(part)
        bases.add("/".join(parts))
    else:
        dotted = normalized.lstrip(".").replace(".", "/")
        if dotted:
            bases.add(dotted)
    return tuple(sorted(bases))


def _module_path_matches(path: str, candidates: tuple[str, ...]) -> bool:
    normalized_path = path.replace("\\", "/")
    without_extension = _without_source_extension(normalized_path)
    for candidate in candidates:
        normalized_candidate = _without_source_extension(candidate)
        if without_extension == normalized_candidate or without_extension.endswith(
            f"/{normalized_candidate}"
        ):
            return True
        if (
            without_extension.endswith("/index")
            and without_extension[:-6] == normalized_candidate
        ):
            return True
        if without_extension.endswith("/__init__") and without_extension[:-9].endswith(
            normalized_candidate
        ):
            return True
    return False


def _without_source_extension(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".py"}:
        return path[: -len(suffix)]
    return path


def _preserve_unpromoted_relationship(
    kind: IRRelationshipKind,
    source: ArchitectureEntity,
    target: IREntity | None,
) -> bool:
    """Keep only unresolved records that still describe architecture.

    F3 intentionally contains source-level declarations and references.  An
    unpromoted function, hook, DOM method, or local variable is not thereby an
    unresolved Architecture Model entity.  Backend architectural roles remain
    useful diagnostics when their statically referenced target was not promoted.
    """
    if kind in {IRRelationshipKind.CONTAINS, IRRelationshipKind.DECLARES}:
        return False
    return (
        target is not None
        and kind
        in {
            IRRelationshipKind.STATIC_CALL_REFERENCE,
            IRRelationshipKind.SOURCE_REFERENCES_DEPENDENCY,
            IRRelationshipKind.INHERITS,
        }
        and _is_backend_architectural_source(source)
    )


def _preserve_unresolved_relationship(
    kind: IRRelationshipKind,
    source: ArchitectureEntity,
    target_descriptor: str,
) -> bool:
    if kind == IRRelationshipKind.IMPORTS:
        # Relative source imports represent repository-internal module edges.
        # Styles/assets and bare runtime/library imports remain available in F3
        # but are not missing Architecture Model entities.
        suffix = PurePosixPath(target_descriptor).suffix.lower()
        return target_descriptor.startswith(".") and suffix not in {
            ".css",
            ".scss",
            ".sass",
            ".less",
            ".svg",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
        }
    if kind in {
        IRRelationshipKind.STATIC_CALL_REFERENCE,
        IRRelationshipKind.INHERITS,
        IRRelationshipKind.SOURCE_REFERENCES_DEPENDENCY,
    }:
        return _is_backend_architectural_source(source)
    return False


def _is_backend_architectural_source(entity: ArchitectureEntity) -> bool:
    if entity.metadata.get("architectural_role") == "frontend_component":
        return False
    return entity.kind in {
        ArchitectureEntityKind.SERVICE,
        ArchitectureEntityKind.CONTROLLER,
        ArchitectureEntityKind.WORKER,
        ArchitectureEntityKind.DATA_REPOSITORY,
        ArchitectureEntityKind.COMPONENT,
    }


def _relationship_kind_for_target(
    kind: ArchitectureRelationshipKind,
    rule_id: str,
    source: ArchitectureEntity,
    target: ArchitectureEntity,
    metadata: Mapping[str, Any],
) -> tuple[ArchitectureRelationshipKind, str]:
    if kind == ArchitectureRelationshipKind.IMPORTS and target.kind not in {
        ArchitectureEntityKind.MODULE,
        ArchitectureEntityKind.COMPONENT,
        ArchitectureEntityKind.LIBRARY,
    }:
        return (
            ArchitectureRelationshipKind.DEPENDS_ON,
            f"{rule_id}.static_infrastructure_dependency",
        )
    if kind == ArchitectureRelationshipKind.DEPENDS_ON:
        resolved = _dependency_relationship_kind(source, target, metadata)
        return resolved, f"{rule_id}.{resolved.value}"
    return kind, rule_id


def _dependency_relationship_kind(
    source: ArchitectureEntity,
    target: ArchitectureEntity,
    metadata: Mapping[str, Any],
) -> ArchitectureRelationshipKind:
    if target.kind == ArchitectureEntityKind.DATABASE and source.kind in {
        ArchitectureEntityKind.SERVICE,
        ArchitectureEntityKind.COMPONENT,
        ArchitectureEntityKind.DATA_REPOSITORY,
    }:
        return ArchitectureRelationshipKind.PERSISTS_TO
    if target.kind in {
        ArchitectureEntityKind.EXTERNAL_SERVICE,
        ArchitectureEntityKind.EXTERNAL_API,
        ArchitectureEntityKind.MESSAGE_BROKER,
    }:
        return ArchitectureRelationshipKind.CONNECTS_TO
    if target.kind in {
        ArchitectureEntityKind.LIBRARY,
        ArchitectureEntityKind.CONFIGURATION_COMPONENT,
    }:
        return ArchitectureRelationshipKind.USES
    if target.kind in {ArchitectureEntityKind.QUEUE, ArchitectureEntityKind.TOPIC}:
        action = metadata.get("messaging_action")
        if action == "consume":
            return ArchitectureRelationshipKind.CONSUMES
        if action == "produce":
            return ArchitectureRelationshipKind.PRODUCES
    return ArchitectureRelationshipKind.DEPENDS_ON


def _map_evidence_ids(
    snapshot_id: UUID,
    source: dict[str, IREvidence],
    source_keys: tuple[str, ...],
    output: dict[str, ArchitectureEvidence],
) -> tuple[str, ...]:
    mapped_ids: list[str] = []
    for key in source_keys:
        mapped = map_ir_evidence(snapshot_id, source[key])
        output[mapped.logical_id] = mapped
        mapped_ids.append(mapped.logical_id)
    return tuple(mapped_ids)


def _relationship(
    document: IRDocument,
    *,
    kind: ArchitectureRelationshipKind,
    source_logical_id: str,
    target_logical_id: str,
    status: ArchitectureFactStatus,
    evidence_ids: tuple[str, ...],
    source_ir_keys: tuple[str, ...],
    rule_id: str,
) -> ArchitectureRelationship:
    return ArchitectureRelationship(
        logical_id=build_relationship_logical_id(
            project_id=document.project_id,
            repository_id=document.repository_id,
            kind=kind,
            source_logical_id=source_logical_id,
            target_logical_id=target_logical_id,
        ),
        kind=kind,
        source_logical_id=source_logical_id,
        target_logical_id=target_logical_id,
        status=status,
        evidence_ids=evidence_ids,
        source_ir_keys=source_ir_keys,
        metadata={"transformation_rule_ids": (rule_id,)},
    )


def _unresolved_relationship(
    document: IRDocument,
    *,
    kind: ArchitectureRelationshipKind,
    source_logical_id: str,
    target_descriptor: str,
    reason: ArchitectureUnresolvedReason,
    status: ArchitectureFactStatus,
    evidence_ids: tuple[str, ...],
    source_ir_keys: tuple[str, ...],
    candidate_references: tuple[str, ...],
    rule_id: str,
) -> ArchitectureUnresolvedRelationship:
    return ArchitectureUnresolvedRelationship(
        logical_id=build_relationship_logical_id(
            project_id=document.project_id,
            repository_id=document.repository_id,
            kind=kind,
            source_logical_id=source_logical_id,
            target_logical_id=None,
            unresolved_descriptor=target_descriptor,
        ),
        kind=kind,
        source_logical_id=source_logical_id,
        target_descriptor=target_descriptor,
        reason=reason,
        status=status,
        evidence_ids=evidence_ids,
        source_ir_keys=source_ir_keys,
        candidate_references=candidate_references,
        metadata={"transformation_rule_ids": (rule_id,)},
    )


def _scope_relationships(
    document: IRDocument,
    entities: tuple[ArchitectureEntity, ...],
    evidence: dict[str, ArchitectureEvidence],
) -> list[ArchitectureRelationship]:
    applications: dict[str, list[ArchitectureEntity]] = defaultdict(list)
    for entity in entities:
        scope = entity.metadata.get("application_namespace")
        if isinstance(scope, str) and entity.kind in {
            ArchitectureEntityKind.APPLICATION,
            ArchitectureEntityKind.FRONTEND_APPLICATION,
        }:
            applications[scope].append(entity)
    output: list[ArchitectureRelationship] = []
    for entity in entities:
        if entity.kind in {
            ArchitectureEntityKind.APPLICATION,
            ArchitectureEntityKind.FRONTEND_APPLICATION,
        }:
            continue
        scope = entity.metadata.get("application_namespace")
        owners = applications.get(scope, ()) if isinstance(scope, str) else ()
        if len(owners) != 1:
            continue
        owner = owners[0]
        if entity.kind == ArchitectureEntityKind.ENDPOINT:
            kind = ArchitectureRelationshipKind.EXPOSES
        elif entity.kind in {
            ArchitectureEntityKind.SERVICE,
            ArchitectureEntityKind.MODULE,
            ArchitectureEntityKind.COMPONENT,
            ArchitectureEntityKind.CONTROLLER,
            ArchitectureEntityKind.WORKER,
            ArchitectureEntityKind.DATA_REPOSITORY,
        }:
            kind = ArchitectureRelationshipKind.CONTAINS
        else:
            continue
        output.append(
            _relationship(
                document,
                kind=kind,
                source_logical_id=owner.logical_id,
                target_logical_id=entity.logical_id,
                status=entity.status,
                evidence_ids=entity.evidence_ids,
                source_ir_keys=entity.source_ir_keys,
                rule_id=(
                    "m4.relationship.application_exposes_endpoint.v1"
                    if kind == ArchitectureRelationshipKind.EXPOSES
                    else "m4.relationship.application_contains_scoped_entity.v1"
                ),
            )
        )
        for evidence_id in entity.evidence_ids:
            if evidence_id not in evidence:
                raise KeyError(f"missing scoped entity evidence: {evidence_id}")
    return output


def _route_handler_relationships(
    document: IRDocument,
    entities: tuple[ArchitectureEntity, ...],
) -> list[ArchitectureRelationship]:
    handlers: dict[str, list[ArchitectureEntity]] = defaultdict(list)
    for entity in entities:
        qualified = entity.metadata.get("qualified_name")
        if isinstance(qualified, str):
            handlers[qualified].append(entity)
    output: list[ArchitectureRelationship] = []
    for endpoint in entities:
        if endpoint.kind != ArchitectureEntityKind.ENDPOINT:
            continue
        handler = endpoint.metadata.get("handler")
        matches = handlers.get(handler, ()) if isinstance(handler, str) else ()
        if len(matches) != 1:
            continue
        output.append(
            _relationship(
                document,
                kind=ArchitectureRelationshipKind.ROUTES_TO,
                source_logical_id=endpoint.logical_id,
                target_logical_id=matches[0].logical_id,
                status=ArchitectureFactStatus.CONFIRMED,
                evidence_ids=tuple(
                    sorted(set(endpoint.evidence_ids + matches[0].evidence_ids))
                ),
                source_ir_keys=tuple(
                    sorted(set(endpoint.source_ir_keys + matches[0].source_ir_keys))
                ),
                rule_id="m4.relationship.endpoint_routes_to_exact_handler.v1",
            )
        )
    return output


def _merge_relationships(
    relationships: list[ArchitectureRelationship],
) -> list[ArchitectureRelationship]:
    groups: dict[str, list[ArchitectureRelationship]] = defaultdict(list)
    for relationship in relationships:
        groups[relationship.logical_id].append(relationship)
    merged: list[ArchitectureRelationship] = []
    for logical_id in sorted(groups):
        group = groups[logical_id]
        first = sorted(group, key=lambda item: item.source_ir_keys)[0]
        merged.append(
            replace(
                first,
                status=_merged_status([item.status for item in group]),
                evidence_ids=tuple(
                    evidence for item in group for evidence in item.evidence_ids
                ),
                source_ir_keys=tuple(
                    source_key for item in group for source_key in item.source_ir_keys
                ),
                metadata={
                    "transformation_rule_ids": tuple(
                        sorted(
                            {
                                rule_id
                                for item in group
                                for rule_id in item.metadata.get(
                                    "transformation_rule_ids", ()
                                )
                                if isinstance(rule_id, str)
                            }
                        )
                    )
                },
            )
        )
    return merged


def _merge_unresolved(
    relationships: list[ArchitectureUnresolvedRelationship],
) -> list[ArchitectureUnresolvedRelationship]:
    groups: dict[str, list[ArchitectureUnresolvedRelationship]] = defaultdict(list)
    for relationship in relationships:
        groups[relationship.logical_id].append(relationship)
    output: list[ArchitectureUnresolvedRelationship] = []
    for logical_id in sorted(groups):
        group = groups[logical_id]
        first = sorted(group, key=lambda item: item.source_ir_keys)[0]
        output.append(
            replace(
                first,
                status=_merged_status([item.status for item in group]),
                evidence_ids=tuple(
                    evidence for item in group for evidence in item.evidence_ids
                ),
                source_ir_keys=tuple(
                    source_key for item in group for source_key in item.source_ir_keys
                ),
                candidate_references=tuple(
                    candidate
                    for item in group
                    for candidate in item.candidate_references
                ),
                metadata={
                    "transformation_rule_ids": tuple(
                        sorted(
                            {
                                rule_id
                                for item in group
                                for rule_id in item.metadata.get(
                                    "transformation_rule_ids", ()
                                )
                                if isinstance(rule_id, str)
                            }
                        )
                    )
                },
            )
        )
    return output


def _identity_conflict(
    document: IRDocument, source: ArchitectureIdentityConflict
) -> ArchitectureConflict:
    signature = semantic_signature(
        {
            "type": "identity_collision",
            "subject": source.logical_id,
            "signatures": source.semantic_signatures,
        }
    )
    return ArchitectureConflict(
        logical_id=f"conflict://snapshot/{str(document.snapshot_id).lower()}/{signature}",
        conflict_type="identity_collision",
        subject_key=source.logical_id,
        evidence_ids=source.evidence_ids,
        details={
            "semantic_signatures": source.semantic_signatures,
            "source_ir_keys": source.source_ir_keys,
            "reason": source.reason,
        },
    )


def _source_conflict(
    document: IRDocument,
    source: IRConflict,
    source_evidence: dict[str, IREvidence],
    evidence: dict[str, ArchitectureEvidence],
) -> ArchitectureConflict:
    mapped = _map_evidence_ids(
        document.snapshot_id,
        source_evidence,
        source.competing_evidence_keys,
        evidence,
    )
    return ArchitectureConflict(
        logical_id=(
            f"conflict://snapshot/{str(document.snapshot_id).lower()}/"
            f"{encode_identity_component(source.conflict_key)}"
        ),
        conflict_type=source.conflict_type,
        subject_key=source.subject_key,
        evidence_ids=mapped,
        details=source.details,
    )


def _status(status: IRFactStatus) -> ArchitectureFactStatus:
    return ArchitectureFactStatus(status.value)


def _merged_status(statuses: list[ArchitectureFactStatus]) -> ArchitectureFactStatus:
    values = set(statuses)
    if ArchitectureFactStatus.CONFLICTING in values:
        return ArchitectureFactStatus.CONFLICTING
    if ArchitectureFactStatus.UNRESOLVED in values:
        return ArchitectureFactStatus.UNRESOLVED
    if len(statuses) > 1:
        return ArchitectureFactStatus.SUPPORTED
    return statuses[0]


__all__ = ["ArchitectureBuilder", "ArchitectureFoundationBuilder"]
