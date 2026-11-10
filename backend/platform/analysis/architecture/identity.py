"""Deterministic M4 identity resolution over frozen F3 documents."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
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
    IRRelationshipKind,
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
        resolved_framework: str | None = None,
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
            if entity.language not in {
                "python",
                "javascript",
                "typescript",
                "jsx",
                "tsx",
            }:
                return None
            if metadata.get("declaration_kind") in {"module", "package"}:
                return None
            scope = metadata.get("application_namespace")
            if not isinstance(scope, str):
                scope = default_application_scope
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
            framework = entity.framework or resolved_framework
            if not isinstance(role, str) and framework is None:
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
                    "architectural_role": (
                        role
                        or (
                            "frontend_component"
                            if framework == "react"
                            else "component"
                        )
                    ),
                    "framework": framework,
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
                    "framework": entity.framework or resolved_framework,
                    **{
                        key: metadata[key]
                        for key in ("mount_path", "declared_path")
                        if isinstance(metadata.get(key), str)
                    },
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
        scope_index = _ApplicationScopeIndex.build(document)
        root_candidates = _root_application_candidates(
            document, evidence_by_key, scope_index
        )
        dependency_candidates = _dependency_candidates(
            document, evidence_by_key, scope_index
        )
        candidates: list[ArchitectureEntity] = [
            *root_candidates,
            *dependency_candidates,
        ]
        mapped_evidence_by_id = {
            mapped.logical_id: mapped
            for source in document.evidence
            for mapped in (map_ir_evidence(document.snapshot_id, source),)
        }
        for candidate in candidates:
            for evidence_id in candidate.evidence_ids:
                used_evidence[evidence_id] = mapped_evidence_by_id[evidence_id]
        root_scopes = {
            item.metadata["application_namespace"]
            for item in root_candidates
            if isinstance(item.metadata.get("application_namespace"), str)
        }
        default_scope = next(iter(root_scopes)) if len(root_scopes) == 1 else None
        for source in document.entities:
            effective_source = scope_index.with_resolved_route_path(source)
            resolved_scope = scope_index.scope_for_entity(
                effective_source, evidence_by_key
            )
            decision = self._rules.decide(
                effective_source,
                default_application_scope=resolved_scope or default_scope,
                resolved_framework=scope_index.framework_for_entity(
                    effective_source, evidence_by_key
                ),
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


_FRAMEWORK_IMPORT_PREFIXES: dict[str, tuple[str, ...]] = {
    "django": ("django",),
    "express": ("express",),
    "fastapi": ("fastapi",),
    "flask": ("flask",),
    "nestjs": ("@nestjs/",),
    "nextjs": ("next", "next/"),
    "react": ("react", "react/", "react-dom", "react-dom/"),
}


@dataclass(frozen=True)
class _ApplicationScopeIndex:
    """Deterministic M4-owned application boundary resolution over F3 evidence.

    F3 intentionally does not assign canonical cross-file application identity.
    This index combines confirmed framework evidence, source paths and React
    component evidence without mutating the frozen F3 document.
    """

    frameworks: tuple[str, ...]
    scope_by_framework: dict[str, str]
    roots_by_framework: dict[str, tuple[str, ...]]
    frameworks_by_path: dict[str, tuple[str, ...]]
    application_evidence_keys: dict[str, tuple[str, ...]]
    route_prefixes_by_module: dict[str, str]

    @classmethod
    def build(cls, document: IRDocument) -> _ApplicationScopeIndex:
        confirmed: set[str] = set()
        detection_keys: dict[str, list[str]] = defaultdict(list)
        paths: dict[str, set[str]] = defaultdict(set)
        path_frameworks: dict[str, set[str]] = defaultdict(set)
        supporting_keys: dict[str, set[str]] = defaultdict(set)

        for evidence in document.evidence:
            if evidence.source_record_type != "framework_detection":
                continue
            framework = evidence.metadata.get("framework")
            if not isinstance(framework, str):
                continue
            if evidence.metadata.get("status") != "confirmed":
                continue
            confirmed.add(framework)
            detection_keys[framework].append(evidence.evidence_key)
            for signal in evidence.metadata.get("signals", ()):
                if isinstance(signal, str) and signal.startswith("path_signal:"):
                    path = _normalized_source_path(signal.removeprefix("path_signal:"))
                    if path is not None:
                        paths[framework].add(path)

        react_keys: set[str] = set()
        react_paths: set[str] = set()
        for evidence in document.evidence:
            path = _normalized_source_path(evidence.path)
            detected: set[str] = set()
            if evidence.source_record_type == "framework_fact" and isinstance(
                evidence.framework_name, str
            ):
                detected.add(evidence.framework_name)
            if evidence.source_record_type == "import_fact":
                source_module = evidence.metadata.get("source_module")
                if isinstance(source_module, str):
                    detected.update(_frameworks_for_import(source_module))
            if (
                evidence.source_record_type == "declaration_fact"
                and evidence.metadata.get("declaration_kind") == "react_component"
            ):
                detected.add("react")

            if "react" in detected and path is not None:
                react_keys.add(evidence.evidence_key)
                react_paths.add(path)

            for framework in detected:
                if framework != "react" and framework not in confirmed:
                    continue
                if path is not None:
                    paths[framework].add(path)
                    path_frameworks[path].add(framework)
                supporting_keys[framework].add(evidence.evidence_key)

        # Next.js is already the stronger full-stack React application boundary.
        if react_paths and "nextjs" not in confirmed:
            confirmed.add("react")
            paths["react"].update(react_paths)
            supporting_keys["react"].update(react_keys)

        frameworks = tuple(sorted(confirmed))
        scope_by_framework = {
            framework: f"root:{framework}" for framework in frameworks
        }
        roots_by_framework = {
            framework: _boundary_roots(paths.get(framework, set()))
            for framework in frameworks
        }
        evidence_keys = {
            framework: tuple(
                sorted(
                    set(detection_keys.get(framework, ()))
                    | supporting_keys.get(framework, set())
                )
            )
            for framework in frameworks
        }
        return cls(
            frameworks=frameworks,
            scope_by_framework=scope_by_framework,
            roots_by_framework=roots_by_framework,
            frameworks_by_path={
                path: tuple(sorted(values))
                for path, values in sorted(path_frameworks.items())
            },
            application_evidence_keys=evidence_keys,
            route_prefixes_by_module=_express_route_mounts(document),
        )

    def framework_for_entity(
        self,
        entity: IREntity,
        evidence_by_key: dict[str, IREvidence],
    ) -> str | None:
        if entity.framework in self.scope_by_framework:
            return entity.framework

        paths = _entity_source_paths(entity, evidence_by_key)
        exact = {
            framework
            for path in paths
            for framework in self.frameworks_by_path.get(path, ())
        }
        if len(exact) == 1:
            return next(iter(exact))

        matches: list[tuple[int, str]] = []
        for framework, roots in self.roots_by_framework.items():
            for root in roots:
                if any(_path_is_within(path, root) for path in paths):
                    matches.append((len(PurePosixPath(root).parts), framework))
        if matches:
            longest = max(length for length, _ in matches)
            strongest = {
                framework for length, framework in matches if length == longest
            }
            if len(strongest) == 1:
                return next(iter(strongest))
        return None

    def scope_for_entity(
        self,
        entity: IREntity,
        evidence_by_key: dict[str, IREvidence],
    ) -> str | None:
        framework = self.framework_for_entity(entity, evidence_by_key)
        return self.scope_by_framework.get(framework) if framework is not None else None

    def scope_for_path(self, path: str) -> str | None:
        normalized = _normalized_source_path(path)
        if normalized is None:
            return None
        exact = set(self.frameworks_by_path.get(normalized, ()))
        if len(exact) == 1:
            return self.scope_by_framework[next(iter(exact))]
        matches: list[tuple[int, str]] = []
        for framework, roots in self.roots_by_framework.items():
            for root in roots:
                if _path_is_within(normalized, root):
                    matches.append((len(PurePosixPath(root).parts), framework))
        if not matches:
            return None
        longest = max(length for length, _ in matches)
        strongest = {framework for length, framework in matches if length == longest}
        if len(strongest) != 1:
            return None
        return self.scope_by_framework[next(iter(strongest))]

    def source_root(self, framework: str) -> str | None:
        roots = self.roots_by_framework.get(framework, ())
        return roots[0] if len(roots) == 1 else None

    def with_resolved_route_path(self, entity: IREntity) -> IREntity:
        if entity.kind != IREntityKind.ENDPOINT or entity.framework != "express":
            return entity
        if not entity.qualified_name:
            return entity
        module_path = entity.qualified_name.split("::", maxsplit=1)[0]
        prefix = self.route_prefixes_by_module.get(
            _without_source_extension(module_path)
        )
        route = entity.metadata.get("path") or entity.metadata.get("route_path")
        if prefix is None or not isinstance(route, str):
            return entity
        mounted_path = normalize_route_path(f"{prefix.rstrip('/')}/{route.lstrip('/')}")
        return replace(
            entity,
            name=mounted_path,
            qualified_name=f"{module_path}::{mounted_path}",
            metadata={
                **entity.metadata,
                "path": mounted_path,
                "mount_path": prefix,
                "declared_path": normalize_route_path(route),
            },
        )


def _express_route_mounts(document: IRDocument) -> dict[str, str]:
    """Resolve static ``app.use('/prefix', importedRouter)`` declarations."""
    module_paths = {
        entity.ir_key: entity.qualified_name
        for entity in document.entities
        if entity.kind == IREntityKind.MODULE and entity.qualified_name
    }
    imports: dict[tuple[str, str], str] = {}
    mounts: list[tuple[str, str, str]] = []
    for relationship in document.relationships:
        if relationship.kind == IRRelationshipKind.IMPORTS:
            alias = relationship.metadata.get("local_alias")
            descriptor = relationship.metadata.get("source_module")
            if isinstance(alias, str) and isinstance(descriptor, str):
                imports[(relationship.source_key, alias)] = descriptor
        elif (
            relationship.kind == IRRelationshipKind.USES_FRAMEWORK
            and relationship.metadata.get("framework") == "express"
            and relationship.metadata.get("fact_type") == "middleware"
        ):
            prefix = relationship.metadata.get("path")
            target = relationship.metadata.get("mount_target")
            if isinstance(prefix, str) and isinstance(target, str):
                mounts.append((relationship.source_key, target, prefix))

    output: dict[str, str] = {}
    for source_key, target, prefix in sorted(mounts):
        descriptor = imports.get((source_key, target))
        source_path = module_paths.get(source_key)
        if descriptor is None or source_path is None or not descriptor.startswith("."):
            continue
        target_path = _resolve_relative_source_path(source_path, descriptor)
        existing = output.get(target_path)
        if existing is None or prefix < existing:
            output[target_path] = normalize_route_path(prefix)
    return output


def _resolve_relative_source_path(source_path: str, descriptor: str) -> str:
    parts = list(PurePosixPath(source_path).parent.parts)
    for part in PurePosixPath(descriptor.replace("\\", "/")).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
        else:
            parts.append(part)
    return _without_source_extension("/".join(parts))


def _without_source_extension(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".py"}:
        return path[: -len(suffix)]
    return path


def _frameworks_for_import(source_module: str) -> set[str]:
    matches: set[str] = set()
    for framework, prefixes in _FRAMEWORK_IMPORT_PREFIXES.items():
        if any(
            (
                source_module.startswith(prefix)
                if prefix.endswith("/")
                else source_module == prefix
            )
            for prefix in prefixes
        ):
            matches.add(framework)
    return matches


def _normalized_source_path(path: str) -> str | None:
    normalized = path.replace("\\", "/").strip("/")
    if not normalized or normalized == "root":
        return None
    return normalized


def _boundary_roots(paths: set[str]) -> tuple[str, ...]:
    parents = [PurePosixPath(path).parent.parts for path in sorted(paths)]
    if not parents:
        return ()
    common: list[str] = []
    for parts in zip(*parents, strict=False):
        if len(set(parts)) != 1:
            break
        common.append(parts[0])
    root = "/".join(common)
    return (root,) if root and root != "." else ()


def _entity_source_paths(
    entity: IREntity,
    evidence_by_key: dict[str, IREvidence],
) -> tuple[str, ...]:
    paths = {
        path
        for key in entity.evidence_keys
        if (evidence := evidence_by_key.get(key)) is not None
        if (path := _normalized_source_path(evidence.path)) is not None
    }
    if entity.qualified_name:
        qualified_path = _normalized_source_path(
            entity.qualified_name.split("::", maxsplit=1)[0]
        )
        if qualified_path is not None and "/" in qualified_path:
            paths.add(qualified_path)
    return tuple(sorted(paths))


def _path_is_within(path: str, root: str) -> bool:
    return path == root or path.startswith(f"{root}/")


def _root_application_candidates(
    document: IRDocument,
    evidence_by_key: dict[str, IREvidence],
    scope_index: _ApplicationScopeIndex,
) -> tuple[ArchitectureEntity, ...]:
    candidates: list[ArchitectureEntity] = []
    for framework in scope_index.frameworks:
        source_keys = scope_index.application_evidence_keys.get(framework, ())
        sources = tuple(evidence_by_key[key] for key in source_keys)
        if not sources:
            continue
        application_namespace = scope_index.scope_by_framework[framework]
        kind = (
            ArchitectureEntityKind.FRONTEND_APPLICATION
            if framework in {"nextjs", "react"}
            else ArchitectureEntityKind.APPLICATION
        )
        semantic = {
            "kind": kind.value,
            "namespace": ("repository_root",),
            "anchor": (framework, "application"),
        }
        evidence = tuple(
            map_ir_evidence(document.snapshot_id, source) for source in sources
        )
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
                    if any(
                        item.polarity == ArchitectureEvidencePolarity.CONFLICTING
                        for item in evidence
                    )
                    else ArchitectureFactStatus.SUPPORTED
                ),
                evidence_ids=tuple(item.logical_id for item in evidence),
                source_ir_keys=(),
                metadata={
                    "application_namespace": application_namespace,
                    "framework": framework,
                    "source_root": scope_index.source_root(framework),
                    "promotion_rule_id": "m4.application.confirmed_framework_root.v1",
                },
            )
        )
    return tuple(candidates)


_DATABASE_DEPENDENCIES: dict[str, tuple[str, str]] = {
    "@elastic/elasticsearch": ("elasticsearch", "Elasticsearch"),
    "asyncpg": ("postgresql", "PostgreSQL"),
    "elasticsearch": ("elasticsearch", "Elasticsearch"),
    "mongodb": ("mongodb", "MongoDB"),
    "mongoose": ("mongodb", "MongoDB"),
    "motor": ("mongodb", "MongoDB"),
    "mysql": ("mysql", "MySQL"),
    "mysql2": ("mysql", "MySQL"),
    "pg": ("postgresql", "PostgreSQL"),
    "postgres": ("postgresql", "PostgreSQL"),
    "psycopg": ("postgresql", "PostgreSQL"),
    "psycopg2": ("postgresql", "PostgreSQL"),
    "pymongo": ("mongodb", "MongoDB"),
    "pymysql": ("mysql", "MySQL"),
}

_EXTERNAL_SERVICE_DEPENDENCIES: dict[str, tuple[str, str]] = {
    "@aws-sdk/client-s3": ("amazon-s3", "Amazon S3"),
}


def _dependency_candidates(
    document: IRDocument,
    evidence_by_key: dict[str, IREvidence],
    scope_index: _ApplicationScopeIndex,
) -> tuple[ArchitectureEntity, ...]:
    """Promote manifest-declared dependencies that source actually imports."""
    manifests: dict[str, list[IREvidence]] = defaultdict(list)
    imports: list[tuple[str, IREvidence]] = []
    for evidence in evidence_by_key.values():
        if evidence.source_record_type == "manifest_fact":
            name = evidence.metadata.get("name")
            if isinstance(name, str) and evidence.metadata.get("is_dev") is not True:
                manifests[name.lower()].append(evidence)
        elif evidence.source_record_type == "import_fact":
            source_module = evidence.metadata.get("source_module")
            if isinstance(source_module, str):
                imports.append((source_module, evidence))

    grouped: dict[tuple[str, str], tuple[str, set[str]]] = {}
    for source_module, import_evidence in imports:
        scope = scope_index.scope_for_path(import_evidence.path)
        if scope is None:
            continue
        matches = [
            name
            for name in manifests
            if _dependency_name_matches_import(name, source_module)
        ]
        if len(matches) != 1:
            continue
        dependency_name = matches[0]
        if _frameworks_for_import(dependency_name):
            continue
        key = (scope, dependency_name)
        existing = grouped.get(key)
        evidence_keys = {
            import_evidence.evidence_key,
            *(item.evidence_key for item in manifests[dependency_name]),
        }
        if existing is None:
            grouped[key] = (dependency_name, evidence_keys)
        else:
            existing[1].update(evidence_keys)

    candidates: list[ArchitectureEntity] = []
    for (scope, dependency_name), (_, evidence_keys) in sorted(grouped.items()):
        namespace: tuple[str, ...]
        anchor: tuple[str, ...]
        if dependency_name in _DATABASE_DEPENDENCIES:
            engine, display_name = _DATABASE_DEPENDENCIES[dependency_name]
            kind = ArchitectureEntityKind.DATABASE
            namespace = ("database", scope)
            anchor = (engine,)
            rule_id = "m4.database.manifest_and_source_usage.v1"
            metadata: dict[str, Any] = {
                "application_namespace": scope,
                "database_engine": engine,
                "dependency_name": dependency_name,
                "usage_evidence": True,
            }
        elif dependency_name in _EXTERNAL_SERVICE_DEPENDENCIES:
            anchor_name, display_name = _EXTERNAL_SERVICE_DEPENDENCIES[dependency_name]
            kind = ArchitectureEntityKind.EXTERNAL_SERVICE
            namespace = ("external", scope)
            anchor = (anchor_name,)
            rule_id = "m4.external_service.manifest_and_source_usage.v1"
            metadata = {
                "application_namespace": scope,
                "external_kind": "service",
                "identity_anchor": anchor_name,
                "dependency_name": dependency_name,
                "usage_evidence": True,
            }
        else:
            display_name = dependency_name
            kind = ArchitectureEntityKind.LIBRARY
            namespace = ("application", scope, "dependency")
            anchor = (dependency_name,)
            rule_id = "m4.library.manifest_and_source_reference.v1"
            metadata = {
                "application_namespace": scope,
                "dependency_name": dependency_name,
                "manifest_declared": True,
                "source_referenced": True,
            }

        semantic = {
            "kind": kind.value,
            "namespace": namespace,
            "anchor": anchor,
        }
        mapped = tuple(
            map_ir_evidence(document.snapshot_id, evidence_by_key[key])
            for key in sorted(evidence_keys)
        )
        candidates.append(
            ArchitectureEntity(
                logical_id=build_entity_logical_id(
                    project_id=document.project_id,
                    repository_id=document.repository_id,
                    kind=kind,
                    namespace_parts=namespace,
                    anchor_parts=anchor,
                ),
                semantic_signature=semantic_signature(semantic),
                kind=kind,
                name=display_name,
                namespace=namespace,
                status=ArchitectureFactStatus.SUPPORTED,
                evidence_ids=tuple(item.logical_id for item in mapped),
                source_ir_keys=(),
                metadata={**metadata, "promotion_rule_id": rule_id},
            )
        )
    return tuple(candidates)


def _dependency_name_matches_import(dependency_name: str, source_module: str) -> bool:
    normalized = source_module.lower()
    if dependency_name.startswith("@"):
        return normalized == dependency_name or normalized.startswith(
            f"{dependency_name}/"
        )
    return (
        normalized == dependency_name
        or normalized.startswith(f"{dependency_name}/")
        or normalized.startswith(f"{dependency_name}.")
    )


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
