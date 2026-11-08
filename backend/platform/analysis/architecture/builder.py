"""Evidence-backed Architecture Model construction from frozen F3."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import replace
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
            if item.target_key is not None:
                target_logical_id = _single_identity(ir_to_entities, item.target_key)
                if target_logical_id is None:
                    continue
                if kind == ArchitectureRelationshipKind.DEPENDS_ON:
                    kind = _dependency_relationship_kind(
                        entities_by_id[source_logical_id],
                        entities_by_id[target_logical_id],
                        item.metadata,
                    )
                    rule_id = f"{rule_id}.{kind.value}"
                mapped_evidence = _map_evidence_ids(
                    source.snapshot_id,
                    source_evidence,
                    item.evidence_keys,
                    evidence,
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
