"""Whole-model validation and explicit resource-cap enforcement for M4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.platform.analysis.architecture.model import (
    ARCHITECTURE_SCHEMA_VERSION,
    ArchitectureCapacityError,
    ArchitectureDocument,
    ArchitectureEntityKind,
    ArchitectureRelationshipKind,
    ArchitectureValidationError,
    ValidatedArchitectureModel,
)
from backend.platform.analysis.domain.constants import IR_SCHEMA_VERSION

if TYPE_CHECKING:
    from backend.platform.config import Settings


@dataclass(frozen=True)
class ArchitectureCapacityConfig:
    """Approved production limits for Architecture Model construction."""

    max_entities: int = 25_000
    max_relationships: int = 50_000
    max_evidence: int = 75_000
    max_unresolved_relationships: int = 10_000
    max_conflicts: int = 5_000
    max_serialized_bytes: int = 128 * 1024 * 1024

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")

    @classmethod
    def from_settings(cls, settings: Settings) -> ArchitectureCapacityConfig:
        """Map the production Settings boundary to the approved M4 limits."""
        return cls(
            max_entities=settings.architecture_max_entities,
            max_relationships=settings.architecture_max_relationships,
            max_evidence=settings.architecture_max_evidence,
            max_unresolved_relationships=(
                settings.architecture_max_unresolved_relationships
            ),
            max_conflicts=settings.architecture_max_conflicts,
            max_serialized_bytes=settings.architecture_max_serialized_bytes,
        )


_DIRECTION_RULES: dict[
    ArchitectureRelationshipKind,
    tuple[set[ArchitectureEntityKind], set[ArchitectureEntityKind]],
] = {
    ArchitectureRelationshipKind.CONTAINS: (
        {
            ArchitectureEntityKind.APPLICATION,
            ArchitectureEntityKind.FRONTEND_APPLICATION,
            ArchitectureEntityKind.SERVICE,
            ArchitectureEntityKind.MODULE,
            ArchitectureEntityKind.COMPONENT,
            ArchitectureEntityKind.CONTROLLER,
            ArchitectureEntityKind.MESSAGE_BROKER,
        },
        set(ArchitectureEntityKind),
    ),
    ArchitectureRelationshipKind.EXPOSES: (
        {
            ArchitectureEntityKind.APPLICATION,
            ArchitectureEntityKind.FRONTEND_APPLICATION,
            ArchitectureEntityKind.SERVICE,
            ArchitectureEntityKind.CONTROLLER,
        },
        {ArchitectureEntityKind.ENDPOINT},
    ),
    ArchitectureRelationshipKind.ROUTES_TO: (
        {ArchitectureEntityKind.ENDPOINT, ArchitectureEntityKind.CONTROLLER},
        {
            ArchitectureEntityKind.COMPONENT,
            ArchitectureEntityKind.CONTROLLER,
            ArchitectureEntityKind.SERVICE,
        },
    ),
    ArchitectureRelationshipKind.IMPORTS: (
        {
            ArchitectureEntityKind.MODULE,
            ArchitectureEntityKind.COMPONENT,
            ArchitectureEntityKind.CONTROLLER,
            ArchitectureEntityKind.SERVICE,
        },
        {
            ArchitectureEntityKind.MODULE,
            ArchitectureEntityKind.COMPONENT,
            ArchitectureEntityKind.LIBRARY,
        },
    ),
    ArchitectureRelationshipKind.CALLS: (
        {
            ArchitectureEntityKind.APPLICATION,
            ArchitectureEntityKind.FRONTEND_APPLICATION,
            ArchitectureEntityKind.SERVICE,
            ArchitectureEntityKind.COMPONENT,
            ArchitectureEntityKind.CONTROLLER,
            ArchitectureEntityKind.ENDPOINT,
            ArchitectureEntityKind.WORKER,
        },
        {
            ArchitectureEntityKind.SERVICE,
            ArchitectureEntityKind.COMPONENT,
            ArchitectureEntityKind.CONTROLLER,
            ArchitectureEntityKind.ENDPOINT,
            ArchitectureEntityKind.EXTERNAL_API,
        },
    ),
    ArchitectureRelationshipKind.DEPENDS_ON: (
        set(ArchitectureEntityKind),
        set(ArchitectureEntityKind),
    ),
    ArchitectureRelationshipKind.USES: (
        set(ArchitectureEntityKind),
        {
            ArchitectureEntityKind.CONFIGURATION_COMPONENT,
            ArchitectureEntityKind.LIBRARY,
        },
    ),
    ArchitectureRelationshipKind.EXTENDS: (
        {
            ArchitectureEntityKind.COMPONENT,
            ArchitectureEntityKind.CONTROLLER,
            ArchitectureEntityKind.SERVICE,
        },
        {
            ArchitectureEntityKind.COMPONENT,
            ArchitectureEntityKind.CONTROLLER,
            ArchitectureEntityKind.SERVICE,
        },
    ),
    ArchitectureRelationshipKind.IMPLEMENTS: (
        {
            ArchitectureEntityKind.COMPONENT,
            ArchitectureEntityKind.CONTROLLER,
            ArchitectureEntityKind.SERVICE,
        },
        {ArchitectureEntityKind.COMPONENT},
    ),
    ArchitectureRelationshipKind.CONSUMES: (
        {
            ArchitectureEntityKind.WORKER,
            ArchitectureEntityKind.SERVICE,
            ArchitectureEntityKind.COMPONENT,
        },
        {ArchitectureEntityKind.QUEUE, ArchitectureEntityKind.TOPIC},
    ),
    ArchitectureRelationshipKind.PRODUCES: (
        {
            ArchitectureEntityKind.WORKER,
            ArchitectureEntityKind.SERVICE,
            ArchitectureEntityKind.COMPONENT,
        },
        {ArchitectureEntityKind.QUEUE, ArchitectureEntityKind.TOPIC},
    ),
    ArchitectureRelationshipKind.CONNECTS_TO: (
        {
            ArchitectureEntityKind.APPLICATION,
            ArchitectureEntityKind.FRONTEND_APPLICATION,
            ArchitectureEntityKind.SERVICE,
            ArchitectureEntityKind.COMPONENT,
        },
        {
            ArchitectureEntityKind.EXTERNAL_SERVICE,
            ArchitectureEntityKind.EXTERNAL_API,
            ArchitectureEntityKind.MESSAGE_BROKER,
        },
    ),
    ArchitectureRelationshipKind.PERSISTS_TO: (
        {
            ArchitectureEntityKind.SERVICE,
            ArchitectureEntityKind.COMPONENT,
            ArchitectureEntityKind.DATA_REPOSITORY,
        },
        {ArchitectureEntityKind.DATABASE},
    ),
}


class ArchitectureValidator:
    def __init__(self, capacity: ArchitectureCapacityConfig) -> None:
        self._capacity = capacity

    def validate(self, document: ArchitectureDocument) -> ValidatedArchitectureModel:
        self._validate_root(document)
        self._validate_capacity(document)
        self._validate_references(document)
        self._validate_direction(document)
        self._validate_containment(document)
        self._validate_completeness(document)
        self._validate_digest(document)
        return ValidatedArchitectureModel(document=document)

    @staticmethod
    def _validate_root(document: ArchitectureDocument) -> None:
        if document.ir_schema_version != IR_SCHEMA_VERSION:
            raise ArchitectureValidationError("unsupported IR schema version")
        if document.architecture_schema_version != ARCHITECTURE_SCHEMA_VERSION:
            raise ArchitectureValidationError("unsupported architecture schema version")
        prefix = (
            f"architecture://project/{str(document.project_id).lower()}"
            f"/repository/{str(document.repository_id).lower()}/"
        )
        ids = [item.logical_id for item in document.entities]
        if len(ids) != len(set(ids)):
            raise ArchitectureValidationError("duplicate architecture entity ID")
        if any(not logical_id.startswith(prefix) for logical_id in ids):
            raise ArchitectureValidationError("entity logical ID escapes model scope")
        scoped_collections = (
            ("relationship", document.relationships),
            ("unresolved relationship", document.unresolved_relationships),
        )
        for label, records in scoped_collections:
            logical_ids = [item.logical_id for item in records]
            if len(logical_ids) != len(set(logical_ids)):
                raise ArchitectureValidationError(f"duplicate {label} ID")
            if any(not logical_id.startswith(prefix) for logical_id in logical_ids):
                raise ArchitectureValidationError(f"{label} ID escapes model scope")
        evidence_prefix = f"evidence://snapshot/{str(document.snapshot_id).lower()}/"
        evidence_ids = [item.logical_id for item in document.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ArchitectureValidationError("duplicate architecture evidence ID")
        if any(not item.startswith(evidence_prefix) for item in evidence_ids):
            raise ArchitectureValidationError("evidence ID escapes snapshot scope")
        conflict_ids = [item.logical_id for item in document.conflicts]
        if len(conflict_ids) != len(set(conflict_ids)):
            raise ArchitectureValidationError("duplicate architecture conflict ID")

    def _validate_capacity(self, document: ArchitectureDocument) -> None:
        checks = (
            ("entities", len(document.entities), self._capacity.max_entities),
            (
                "relationships",
                len(document.relationships),
                self._capacity.max_relationships,
            ),
            ("evidence", len(document.evidence), self._capacity.max_evidence),
            (
                "unresolved relationships",
                len(document.unresolved_relationships),
                self._capacity.max_unresolved_relationships,
            ),
            ("conflicts", len(document.conflicts), self._capacity.max_conflicts),
        )
        for label, actual, limit in checks:
            if actual > limit:
                raise ArchitectureCapacityError(
                    dimension=label.replace(" ", "_"),
                    actual=actual,
                    limit=limit,
                )
        size = len(document.to_canonical_json().encode("utf-8"))
        if size > self._capacity.max_serialized_bytes:
            raise ArchitectureCapacityError(
                dimension="canonical_payload_bytes",
                actual=size,
                limit=self._capacity.max_serialized_bytes,
            )

    @staticmethod
    def _validate_references(document: ArchitectureDocument) -> None:
        entities = {item.logical_id for item in document.entities}
        evidence = {item.logical_id for item in document.evidence}
        referenced_evidence: set[str] = set()
        for entity in document.entities:
            if not set(entity.evidence_ids) <= evidence:
                raise ArchitectureValidationError("entity references missing evidence")
            referenced_evidence.update(entity.evidence_ids)
        for relationship in document.relationships:
            if relationship.source_logical_id not in entities:
                raise ArchitectureValidationError("relationship source is missing")
            if relationship.target_logical_id not in entities:
                raise ArchitectureValidationError("relationship target is missing")
            if not set(relationship.evidence_ids) <= evidence:
                raise ArchitectureValidationError(
                    "relationship references missing evidence"
                )
            referenced_evidence.update(relationship.evidence_ids)
        for unresolved in document.unresolved_relationships:
            if unresolved.source_logical_id not in entities:
                raise ArchitectureValidationError(
                    "unresolved relationship source is missing"
                )
            if not set(unresolved.evidence_ids) <= evidence:
                raise ArchitectureValidationError(
                    "unresolved relationship references missing evidence"
                )
            referenced_evidence.update(unresolved.evidence_ids)
        for conflict in document.conflicts:
            if not set(conflict.evidence_ids) <= evidence:
                raise ArchitectureValidationError(
                    "conflict references missing evidence"
                )
            referenced_evidence.update(conflict.evidence_ids)
        if referenced_evidence != evidence:
            raise ArchitectureValidationError("model contains unreferenced evidence")

    @staticmethod
    def _validate_direction(document: ArchitectureDocument) -> None:
        entities = {item.logical_id: item for item in document.entities}
        for relationship in document.relationships:
            source_kinds, target_kinds = _DIRECTION_RULES[relationship.kind]
            if entities[relationship.source_logical_id].kind not in source_kinds:
                raise ArchitectureValidationError(
                    f"invalid {relationship.kind.value} source kind"
                )
            if entities[relationship.target_logical_id].kind not in target_kinds:
                raise ArchitectureValidationError(
                    f"invalid {relationship.kind.value} target kind"
                )
        for unresolved_relationship in document.unresolved_relationships:
            source_kinds, _ = _DIRECTION_RULES[unresolved_relationship.kind]
            if (
                entities[unresolved_relationship.source_logical_id].kind
                not in source_kinds
            ):
                raise ArchitectureValidationError(
                    "invalid unresolved "
                    f"{unresolved_relationship.kind.value} source kind"
                )
        exposed_endpoints = {
            relationship.target_logical_id
            for relationship in document.relationships
            if relationship.kind == ArchitectureRelationshipKind.EXPOSES
        }
        for entity in document.entities:
            if (
                entity.kind == ArchitectureEntityKind.ENDPOINT
                and entity.logical_id not in exposed_endpoints
            ):
                raise ArchitectureValidationError(
                    "endpoint lacks a resolved exposing application boundary"
                )

    @staticmethod
    def _validate_containment(document: ArchitectureDocument) -> None:
        children: dict[str, set[str]] = {}
        for relationship in document.relationships:
            if relationship.kind == ArchitectureRelationshipKind.CONTAINS:
                children.setdefault(relationship.source_logical_id, set()).add(
                    relationship.target_logical_id
                )

        def visit(node: str, active: set[str], complete: set[str]) -> None:
            if node in active:
                raise ArchitectureValidationError(
                    "containment hierarchy contains a cycle"
                )
            if node in complete:
                return
            active.add(node)
            for child in sorted(children.get(node, ())):
                visit(child, active, complete)
            active.remove(node)
            complete.add(node)

        complete: set[str] = set()
        for root in sorted(children):
            visit(root, set(), complete)

    @staticmethod
    def _validate_completeness(document: ArchitectureDocument) -> None:
        completeness = document.completeness
        expected = (
            (completeness.architecture_entities, len(document.entities)),
            (completeness.architecture_relationships, len(document.relationships)),
            (
                completeness.architecture_unresolved_relationships,
                len(document.unresolved_relationships),
            ),
            (completeness.architecture_conflicts, len(document.conflicts)),
        )
        if any(recorded != actual for recorded, actual in expected):
            raise ArchitectureValidationError(
                "architecture completeness counts mismatch"
            )
        if completeness.analyzed_artifacts + completeness.failed_artifacts > (
            completeness.total_inventory_artifacts
        ):
            raise ArchitectureValidationError(
                "artifact completeness counts are invalid"
            )
        if completeness.failed_artifacts and not completeness.is_partial:
            raise ArchitectureValidationError(
                "failed artifacts require partial completeness"
            )

    @staticmethod
    def _validate_digest(document: ArchitectureDocument) -> None:
        if document.content_digest != document.calculate_content_digest():
            raise ArchitectureValidationError("architecture content digest is invalid")


__all__ = [
    "ArchitectureCapacityConfig",
    "ArchitectureValidator",
]
