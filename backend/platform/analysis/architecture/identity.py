"""Deterministic M4 identity resolution over frozen F3 documents."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Any, Protocol
from uuid import UUID

from backend.platform.analysis.architecture.model import (
    ArchitectureEntity,
    ArchitectureEntityKind,
    ArchitectureEvidence,
    ArchitectureEvidencePolarity,
    ArchitectureEvidenceStrength,
    ArchitectureFactStatus,
    ArchitectureIdentityCollisionError,
    ArchitectureIdentityConflict,
    ArchitectureModelError,
    ResolvedArchitectureInput,
    build_entity_logical_id,
    build_evidence_logical_id,
    normalize_route_path,
    semantic_signature,
)
from backend.platform.analysis.domain.constants import ARCHITECTURE_SCHEMA_VERSION
from backend.platform.analysis.ir.model import (
    IRDocument,
    IREntity,
    IREntityKind,
    IREvidence,
)


@dataclass(frozen=True)
class HistoricalIdentityRecord:
    logical_id: str
    semantic_signature: str
    kind: ArchitectureEntityKind


class HistoricalIdentityReader(Protocol):
    def list_latest_identities(
        self, project_id: UUID, repository_id: UUID
    ) -> tuple[HistoricalIdentityRecord, ...]: ...


@dataclass(frozen=True)
class PromotionDecision:
    kind: ArchitectureEntityKind
    namespace_parts: tuple[str, ...]
    anchor_parts: tuple[str, ...]
    name: str
    status: ArchitectureFactStatus
    rule_id: str
    metadata: dict[str, Any]


class InitialPromotionRuleTable:
    """Conservative Batch 1 rules; Batch 2 completes relationship semantics."""

    def decide(
        self,
        entity: IREntity,
        *,
        default_application_scope: str | None = None,
    ) -> PromotionDecision | None:
        if not entity.evidence_keys:
            return None
        metadata = dict(entity.metadata)

        if entity.kind == IREntityKind.DATABASE:
            engine = metadata.get("database_engine")
            scope = metadata.get("application_namespace")
            if not isinstance(engine, str) or not isinstance(scope, str):
                return None
            if metadata.get("usage_evidence") is not True:
                return None
            return PromotionDecision(
                kind=ArchitectureEntityKind.DATABASE,
                namespace_parts=("database", scope),
                anchor_parts=(engine,),
                name=entity.name,
                status=_status(entity),
                rule_id="m4.database.configured_usage.v1",
                metadata={
                    "application_namespace": scope,
                    "database_engine": engine,
                },
            )

        if entity.kind == IREntityKind.EXTERNAL_SYSTEM:
            system_type = metadata.get("external_kind")
            anchor = metadata.get("identity_anchor")
            scope = metadata.get("application_namespace")
            if not isinstance(anchor, str) or not isinstance(scope, str):
                return None
            if metadata.get("usage_evidence") is not True:
                return None
            external_kind = {
                "service": ArchitectureEntityKind.EXTERNAL_SERVICE,
                "api": ArchitectureEntityKind.EXTERNAL_API,
            }.get(
                system_type if isinstance(system_type, str) else "",
                ArchitectureEntityKind.UNKNOWN,
            )
            unresolved_reason = metadata.get("unresolved_reason")
            if external_kind == ArchitectureEntityKind.UNKNOWN and not isinstance(
                unresolved_reason, str
            ):
                return None
            return PromotionDecision(
                kind=external_kind,
                namespace_parts=("external", scope),
                anchor_parts=(anchor,),
                name=entity.name,
                status=_status(entity),
                rule_id=f"m4.external.{external_kind.value}.configured_usage.v1",
                metadata={
                    "application_namespace": scope,
                    "external_kind": system_type or "unknown",
                    "unresolved_reason": unresolved_reason,
                },
            )

        if entity.kind == IREntityKind.MESSAGE_INFRASTRUCTURE:
            infrastructure_type = metadata.get("infrastructure_kind")
            anchor = metadata.get("identity_anchor")
            scope = metadata.get("application_namespace")
            message_kind = {
                "broker": ArchitectureEntityKind.MESSAGE_BROKER,
                "queue": ArchitectureEntityKind.QUEUE,
                "topic": ArchitectureEntityKind.TOPIC,
            }.get(infrastructure_type if isinstance(infrastructure_type, str) else "")
            if (
                message_kind is None
                or not isinstance(anchor, str)
                or not isinstance(scope, str)
            ):
                return None
            if metadata.get("usage_evidence") is not True:
                return None
            return PromotionDecision(
                kind=message_kind,
                namespace_parts=("messaging", scope),
                anchor_parts=(anchor,),
                name=entity.name,
                status=_status(entity),
                rule_id=f"m4.messaging.{message_kind.value}.configured_usage.v1",
                metadata={
                    "application_namespace": scope,
                    "infrastructure_kind": infrastructure_type,
                },
            )

        if entity.kind == IREntityKind.CONFIGURATION:
            anchor = metadata.get("identity_anchor")
            scope = metadata.get("application_namespace")
            if metadata.get("architecture_effect") is not True:
                return None
            if not isinstance(anchor, str) or not isinstance(scope, str):
                return None
            return PromotionDecision(
                kind=ArchitectureEntityKind.CONFIGURATION_COMPONENT,
                namespace_parts=("configuration", scope),
                anchor_parts=(anchor,),
                name=entity.name,
                status=_status(entity),
                rule_id="m4.configuration.architecture_effect.v1",
                metadata={"application_namespace": scope},
            )

        if entity.kind == IREntityKind.APPLICATION:
            boundary = metadata.get("runtime_role") or metadata.get("entry_point")
            if not isinstance(boundary, str) or not entity.evidence_keys:
                return None
            kind = (
                ArchitectureEntityKind.FRONTEND_APPLICATION
                if boundary.lower() in {"browser", "client", "frontend"}
                else ArchitectureEntityKind.APPLICATION
            )
            return PromotionDecision(
                kind=kind,
                namespace_parts=("application",),
                anchor_parts=(entity.qualified_name or entity.name, boundary),
                name=entity.name,
                status=_status(entity),
                rule_id="m4.application.explicit_boundary.v1",
                metadata={
                    "runtime_role": boundary,
                    "application_namespace": metadata.get(
                        "application_namespace", entity.qualified_name or entity.name
                    ),
                },
            )

        if entity.kind == IREntityKind.MODULE:
            if not entity.qualified_name:
                return None
            scope = metadata.get("application_namespace")
            if not isinstance(scope, str):
                if metadata.get("shared_boundary") is not True:
                    return None
                scope = "shared"
            return PromotionDecision(
                kind=ArchitectureEntityKind.MODULE,
                namespace_parts=("application", scope),
                anchor_parts=(entity.qualified_name or entity.name,),
                name=entity.name,
                status=_status(entity),
                rule_id="m4.module.scoped_package.v1",
                metadata={
                    "application_namespace": scope,
                    "qualified_name": entity.qualified_name,
                },
            )

        if entity.kind == IREntityKind.COMPONENT:
            if not entity.qualified_name:
                return None
            role = metadata.get("architectural_role")
            if not isinstance(role, str) and entity.framework is None:
                return None
            scope = metadata.get("application_namespace")
            if not isinstance(scope, str):
                scope = default_application_scope
            if not isinstance(scope, str):
                return None
            kind = self._component_kind(role)
            if kind == ArchitectureEntityKind.LIBRARY and not (
                metadata.get("manifest_declared") is True
                and metadata.get("source_referenced") is True
            ):
                return None
            return PromotionDecision(
                kind=kind,
                namespace_parts=("application", scope),
                anchor_parts=(entity.qualified_name or entity.name, kind.value),
                name=entity.name,
                status=_status(entity),
                rule_id="m4.component.structural_role.v1",
                metadata={
                    "application_namespace": scope,
                    "architectural_role": role or "component",
                    "framework": entity.framework,
                    "qualified_name": entity.qualified_name,
                },
            )

        if entity.kind == IREntityKind.ENDPOINT:
            method = metadata.get("method") or metadata.get("http_method")
            path = metadata.get("path") or metadata.get("route_path")
            scope = metadata.get("application_namespace")
            if not isinstance(scope, str):
                scope = default_application_scope
            if not all(isinstance(value, str) for value in (method, path, scope)):
                return None
            if not entity.qualified_name:
                return None
            assert isinstance(method, str) and isinstance(path, str)
            assert isinstance(scope, str)
            method, path = method.upper(), normalize_route_path(path)
            return PromotionDecision(
                kind=ArchitectureEntityKind.ENDPOINT,
                namespace_parts=("application", scope),
                anchor_parts=(method, path),
                name=f"{method} {path}",
                status=_status(entity),
                rule_id="m4.endpoint.explicit_route.v1",
                metadata={
                    "application_namespace": scope,
                    "method": method,
                    "path": path,
                    "handler": entity.qualified_name,
                },
            )
        return None

    @staticmethod
    def _component_kind(role: object) -> ArchitectureEntityKind:
        if isinstance(role, str):
            mapped = {
                "controller": ArchitectureEntityKind.CONTROLLER,
                "worker": ArchitectureEntityKind.WORKER,
                "data_repository": ArchitectureEntityKind.DATA_REPOSITORY,
                "service": ArchitectureEntityKind.SERVICE,
                "library": ArchitectureEntityKind.LIBRARY,
            }.get(role.lower())
            if mapped is not None:
                return mapped
        return ArchitectureEntityKind.COMPONENT


class IdentityResolutionService:
    def __init__(
        self,
        *,
        rules: InitialPromotionRuleTable | None = None,
        history: HistoricalIdentityReader | None = None,
    ) -> None:
        self._rules = rules or InitialPromotionRuleTable()
        self._history = history

    def resolve(self, document: IRDocument) -> ResolvedArchitectureInput:
        evidence_by_key = {item.evidence_key: item for item in document.evidence}
        used_evidence: dict[str, ArchitectureEvidence] = {}
        root_candidates = _root_application_candidates(document, evidence_by_key)
        candidates: list[ArchitectureEntity] = list(root_candidates)
        mapped_evidence_by_id = {
            mapped.logical_id: mapped
            for source in document.evidence
            for mapped in (map_ir_evidence(document.snapshot_id, source),)
        }
        for candidate in root_candidates:
            for evidence_id in candidate.evidence_ids:
                used_evidence[evidence_id] = mapped_evidence_by_id[evidence_id]
        root_scopes = {
            item.metadata["application_namespace"]
            for item in root_candidates
            if isinstance(item.metadata.get("application_namespace"), str)
        }
        default_scope = next(iter(root_scopes)) if len(root_scopes) == 1 else None
        for source in document.entities:
            decision = self._rules.decide(
                source, default_application_scope=default_scope
            )
            if decision is None:
                continue
            missing = set(source.evidence_keys) - evidence_by_key.keys()
            if missing:
                raise ArchitectureModelError(
                    f"candidate {source.ir_key} has missing evidence: {sorted(missing)}"
                )
            semantic: dict[str, Any] = {
                "kind": decision.kind.value,
                "namespace": decision.namespace_parts,
                "anchor": decision.anchor_parts,
            }
            discriminator = decision.metadata.get("handler")
            if decision.kind == ArchitectureEntityKind.ENDPOINT and isinstance(
                discriminator, str
            ):
                semantic["identity_discriminator"] = discriminator
            signature = semantic_signature(semantic)
            logical_id = build_entity_logical_id(
                project_id=document.project_id,
                repository_id=document.repository_id,
                kind=decision.kind,
                namespace_parts=decision.namespace_parts,
                anchor_parts=decision.anchor_parts,
            )
            evidence_ids: list[str] = []
            has_conflicting_evidence = False
            for key in source.evidence_keys:
                mapped = map_ir_evidence(document.snapshot_id, evidence_by_key[key])
                used_evidence[mapped.logical_id] = mapped
                evidence_ids.append(mapped.logical_id)
                has_conflicting_evidence = (
                    has_conflicting_evidence
                    or mapped.polarity == ArchitectureEvidencePolarity.CONFLICTING
                )
            candidates.append(
                ArchitectureEntity(
                    logical_id=logical_id,
                    semantic_signature=signature,
                    kind=decision.kind,
                    name=decision.name,
                    namespace=decision.namespace_parts,
                    status=(
                        ArchitectureFactStatus.CONFLICTING
                        if has_conflicting_evidence
                        else decision.status
                    ),
                    evidence_ids=tuple(evidence_ids),
                    source_ir_keys=(source.ir_key,),
                    metadata={
                        **decision.metadata,
                        "promotion_rule_id": decision.rule_id,
                    },
                )
            )
        resolved, conflicts = self._merge_and_disambiguate(candidates)
        resolved = self._apply_exact_history(document, resolved)
        return ResolvedArchitectureInput(
            analysis_id=document.analysis_id,
            project_id=document.project_id,
            repository_id=document.repository_id,
            snapshot_id=document.snapshot_id,
            configuration_fingerprint=document.configuration_fingerprint,
            analyzer_version=document.analyzer_version,
            ir_schema_version=document.ir_schema_version,
            architecture_schema_version=ARCHITECTURE_SCHEMA_VERSION,
            entities=tuple(resolved),
            evidence=tuple(used_evidence.values()),
            conflicts=tuple(conflicts),
            source_diagnostic_ids=document.diagnostic_ids,
        )

    def _merge_and_disambiguate(
        self, candidates: list[ArchitectureEntity]
    ) -> tuple[list[ArchitectureEntity], list[ArchitectureIdentityConflict]]:
        groups: dict[str, list[ArchitectureEntity]] = defaultdict(list)
        for candidate in candidates:
            groups[candidate.logical_id].append(candidate)
        output: list[ArchitectureEntity] = []
        conflicts: list[ArchitectureIdentityConflict] = []
        for base_id in sorted(groups):
            by_signature: dict[str, list[ArchitectureEntity]] = defaultdict(list)
            for candidate in groups[base_id]:
                by_signature[candidate.semantic_signature].append(candidate)
            if len(by_signature) == 1:
                output.append(_merge_equivalent(next(iter(by_signature.values()))))
                continue
            signatures = tuple(sorted(by_signature))
            conflicts.append(
                ArchitectureIdentityConflict(
                    logical_id=base_id,
                    semantic_signatures=signatures,
                    source_ir_keys=tuple(
                        key for item in groups[base_id] for key in item.source_ir_keys
                    ),
                    evidence_ids=tuple(
                        key for item in groups[base_id] for key in item.evidence_ids
                    ),
                )
            )
            for signature in signatures:
                merged = _merge_equivalent(by_signature[signature])
                output.append(
                    replace(
                        merged,
                        logical_id=f"{base_id}/disambiguator/sha256-{signature}",
                        status=ArchitectureFactStatus.CONFLICTING,
                    )
                )
        return output, conflicts

    def _apply_exact_history(
        self, document: IRDocument, entities: list[ArchitectureEntity]
    ) -> list[ArchitectureEntity]:
        if self._history is None:
            return entities
        prior = self._history.list_latest_identities(
            document.project_id, document.repository_id
        )
        scope_prefix = (
            f"architecture://project/{str(document.project_id).lower()}"
            f"/repository/{str(document.repository_id).lower()}/"
        )
        prior_groups: dict[tuple[ArchitectureEntityKind, str], set[str]] = defaultdict(
            set
        )
        for item in prior:
            if item.logical_id.startswith(f"{scope_prefix}{item.kind.value}/"):
                prior_groups[(item.kind, item.semantic_signature)].add(item.logical_id)
        ambiguous = [key for key, ids in prior_groups.items() if len(ids) > 1]
        if ambiguous:
            raise ArchitectureIdentityCollisionError(
                "historical identities contain ambiguous exact matches"
            )
        prior_by_signature = {key: next(iter(ids)) for key, ids in prior_groups.items()}
        return [
            replace(
                entity,
                logical_id=prior_by_signature.get(
                    (entity.kind, entity.semantic_signature), entity.logical_id
                ),
            )
            for entity in entities
        ]


def _status(entity: IREntity) -> ArchitectureFactStatus:
    return {
        "confirmed": ArchitectureFactStatus.CONFIRMED,
        "inferred": ArchitectureFactStatus.INFERRED,
        "unresolved": ArchitectureFactStatus.UNRESOLVED,
        "conflicting": ArchitectureFactStatus.CONFLICTING,
    }[entity.status.value]


def map_ir_evidence(snapshot_id: UUID, source: IREvidence) -> ArchitectureEvidence:
    source_range = None
    if source.source_range is not None:
        source_range = {
            "start_byte": source.source_range.start_byte,
            "end_byte": source.source_range.end_byte,
            "start_line": source.source_range.start_line,
            "end_line": source.source_range.end_line,
            "start_column": source.source_range.start_column,
            "end_column": source.source_range.end_column,
        }
    return ArchitectureEvidence(
        logical_id=build_evidence_logical_id(snapshot_id, source.evidence_key),
        source_evidence_key=source.evidence_key,
        source_record_type=source.source_record_type,
        path=source.path,
        artifact_id=source.artifact_id,
        source_fact_key=source.source_fact_key,
        source_range=source_range,
        producer_id=source.parser_adapter_id,
        producer_version=source.parser_adapter_version,
        strength=ArchitectureEvidenceStrength(source.strength.value),
        polarity=ArchitectureEvidencePolarity(source.polarity),
        metadata=_evidence_metadata(source),
    )


def _evidence_metadata(source: IREvidence) -> dict[str, Any]:
    allowed_by_record = {
        "framework_detection": {"framework", "status", "version", "signals"},
        "runtime_detection": {"runtime", "target", "signals"},
        "language_detection": {"language", "confidence", "signals"},
        "framework_fact": {"fact_type"},
        "declaration_fact": {"declaration_kind", "modifiers", "decorators"},
        "import_fact": {
            "source_module",
            "imported_name",
            "local_alias",
            "is_type_only",
            "is_commonjs",
            "import_kind",
        },
        "manifest_fact": {
            "manifest_type",
            "name",
            "version",
            "scope",
            "is_dev",
        },
        "inventory_entry": {
            "role",
            "outcome",
            "category",
            "support_level",
            "is_test",
            "is_generated",
            "is_sensitive",
            "reason_codes",
        },
        "reference_fact": {"reference_kind", "target_name"},
        "syntax_document": {"language", "parse_status"},
    }
    allowed = allowed_by_record.get(source.source_record_type, set())
    metadata = {key: value for key, value in source.metadata.items() if key in allowed}
    metadata.update(
        {
            "framework_name": source.framework_name,
            "grammar_abi_version": source.grammar_abi_version,
            "supporting_fact_keys": source.supporting_fact_keys,
            "upstream_analyzer_version": source.upstream_analyzer_version,
            "m3_transformation_version": source.m3_transformation_version,
        }
    )
    return metadata


def _root_application_candidates(
    document: IRDocument,
    evidence_by_key: dict[str, IREvidence],
) -> tuple[ArchitectureEntity, ...]:
    candidates: list[ArchitectureEntity] = []
    for source in sorted(evidence_by_key.values(), key=lambda item: item.evidence_key):
        if source.source_record_type != "framework_detection":
            continue
        framework = source.metadata.get("framework")
        status = source.metadata.get("status")
        if not isinstance(framework, str) or status != "confirmed":
            continue
        application_namespace = f"root:{framework}"
        kind = (
            ArchitectureEntityKind.FRONTEND_APPLICATION
            if framework == "nextjs"
            else ArchitectureEntityKind.APPLICATION
        )
        semantic = {
            "kind": kind.value,
            "namespace": ("repository_root",),
            "anchor": (framework, "application"),
        }
        evidence = map_ir_evidence(document.snapshot_id, source)
        candidates.append(
            ArchitectureEntity(
                logical_id=build_entity_logical_id(
                    project_id=document.project_id,
                    repository_id=document.repository_id,
                    kind=kind,
                    namespace_parts=("repository_root",),
                    anchor_parts=(framework, "application"),
                ),
                semantic_signature=semantic_signature(semantic),
                kind=kind,
                name=f"{framework} application",
                namespace=("repository_root",),
                status=(
                    ArchitectureFactStatus.CONFLICTING
                    if evidence.polarity == ArchitectureEvidencePolarity.CONFLICTING
                    else ArchitectureFactStatus.SUPPORTED
                ),
                evidence_ids=(evidence.logical_id,),
                source_ir_keys=(),
                metadata={
                    "application_namespace": application_namespace,
                    "framework": framework,
                    "promotion_rule_id": "m4.application.confirmed_framework_root.v1",
                },
            )
        )
    return tuple(candidates)


def _merge_equivalent(group: list[ArchitectureEntity]) -> ArchitectureEntity:
    first = sorted(group, key=lambda item: item.source_ir_keys)[0]
    if any(
        item.kind != first.kind or item.semantic_signature != first.semantic_signature
        for item in group
    ):
        raise ArchitectureIdentityCollisionError("non-equivalent entity merge")
    statuses = {item.status for item in group}
    if ArchitectureFactStatus.CONFLICTING in statuses:
        merged_status = ArchitectureFactStatus.CONFLICTING
    elif ArchitectureFactStatus.UNRESOLVED in statuses:
        merged_status = ArchitectureFactStatus.UNRESOLVED
    elif len(group) > 1:
        merged_status = ArchitectureFactStatus.SUPPORTED
    else:
        merged_status = first.status
    return replace(
        first,
        status=merged_status,
        evidence_ids=tuple(key for item in group for key in item.evidence_ids),
        source_ir_keys=tuple(key for item in group for key in item.source_ir_keys),
    )


__all__ = [
    "HistoricalIdentityReader",
    "HistoricalIdentityRecord",
    "IdentityResolutionService",
    "InitialPromotionRuleTable",
    "map_ir_evidence",
    "PromotionDecision",
]
