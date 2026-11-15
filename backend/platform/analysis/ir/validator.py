"""Intermediate Representation (IR) validation engine (Phase 3 Module 3 Batch 2).

Validates schema versions, referential integrity, key uniqueness, metadata safety,
ordering invariants, completeness flags, and numeric capacity limits.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.platform.analysis.domain.constants import (
    ANALYZER_VERSION,
    DEFAULT_IR_MAX_CONFLICTS,
    DEFAULT_IR_MAX_ENTITIES,
    DEFAULT_IR_MAX_EVIDENCE,
    DEFAULT_IR_MAX_RELATIONSHIPS,
    DEFAULT_IR_MAX_SERIALIZED_BYTES,
    DEFAULT_IR_MAX_UNRESOLVED_REFERENCES,
    IR_SCHEMA_VERSION,
)
from backend.platform.analysis.ir.model import (
    IRCapacityLimitError,
    IRDocument,
    IRRelationshipKind,
    IRValidationError,
)


@dataclass(frozen=True)
class IRCapacityConfig:
    """Configurable numeric caps for intermediate representation documents."""

    max_entities: int = DEFAULT_IR_MAX_ENTITIES
    max_relationships: int = DEFAULT_IR_MAX_RELATIONSHIPS
    max_evidence: int = DEFAULT_IR_MAX_EVIDENCE
    max_unresolved_references: int = DEFAULT_IR_MAX_UNRESOLVED_REFERENCES
    max_conflicts: int = DEFAULT_IR_MAX_CONFLICTS
    max_serialized_bytes: int = DEFAULT_IR_MAX_SERIALIZED_BYTES


class IRValidator:
    """Stateless validator for Intermediate Representation (IR) documents.

    Enforces schema invariants, key uniqueness, referential integrity,
    completeness accounting, and numeric resource boundaries.
    """

    def __init__(
        self,
        caps: IRCapacityConfig | None = None,
        expected_schema_version: str = IR_SCHEMA_VERSION,
        expected_f2_version: str = "1.0.0",
        expected_analyzer_version: str = ANALYZER_VERSION,
    ) -> None:
        self._caps = caps or IRCapacityConfig()
        self._expected_schema_version = expected_schema_version
        self._expected_f2_version = expected_f2_version
        self._expected_analyzer_version = expected_analyzer_version

    @property
    def caps(self) -> IRCapacityConfig:
        """Return the capacity configuration for this validator."""
        return self._caps

    def validate(self, doc: IRDocument) -> None:
        """Validate an IRDocument against all schema, referential, and capacity rules.

        Raises:
            IRValidationError: on schema, referential, safety, or invariant violations.
            IRCapacityLimitError: on numeric capacity limit violations.
        """
        if not isinstance(doc, IRDocument):
            msg = f"Expected IRDocument, got {type(doc).__name__}"
            raise IRValidationError(msg)

        # 1. Schema & Version Invariants
        if doc.ir_schema_version != self._expected_schema_version:
            msg = (
                f"Unsupported IR schema version: {doc.ir_schema_version!r} "
                f"(expected {self._expected_schema_version!r})"
            )
            raise IRValidationError(msg)

        if doc.f2_version != self._expected_f2_version:
            msg = (
                f"Unsupported F2 contract version: {doc.f2_version!r} "
                f"(expected {self._expected_f2_version!r})"
            )
            raise IRValidationError(msg)

        if doc.analyzer_version != self._expected_analyzer_version:
            msg = (
                f"Unsupported analyzer version: {doc.analyzer_version!r} "
                f"(expected {self._expected_analyzer_version!r})"
            )
            raise IRValidationError(msg)

        if not doc.analysis_id or not doc.project_id:
            msg = "IR document must have non-empty analysis_id and project_id."
            raise IRValidationError(msg)

        if not doc.repository_id or not doc.snapshot_id:
            msg = "IR document must have non-empty repository_id and snapshot_id."
            raise IRValidationError(msg)

        if not doc.configuration_fingerprint:
            msg = "IR document must have non-empty configuration_fingerprint."
            raise IRValidationError(msg)

        # 2. Numeric Resource Caps (Entity, Relationship, Evidence Counts)
        if len(doc.entities) > self._caps.max_entities:
            msg = (
                f"Entity count {len(doc.entities)} exceeds cap "
                f"{self._caps.max_entities}"
            )
            raise IRCapacityLimitError(msg)

        if len(doc.relationships) > self._caps.max_relationships:
            msg = (
                f"Relationship count {len(doc.relationships)} exceeds cap "
                f"{self._caps.max_relationships}"
            )
            raise IRCapacityLimitError(msg)

        if len(doc.evidence) > self._caps.max_evidence:
            msg = (
                f"Evidence count {len(doc.evidence)} exceeds cap "
                f"{self._caps.max_evidence}"
            )
            raise IRCapacityLimitError(msg)

        if len(doc.unresolved_references) > self._caps.max_unresolved_references:
            msg = (
                f"Unresolved reference count {len(doc.unresolved_references)} "
                f"exceeds cap {self._caps.max_unresolved_references}"
            )
            raise IRCapacityLimitError(msg)

        if len(doc.conflicts) > self._caps.max_conflicts:
            msg = (
                f"Conflict count {len(doc.conflicts)} exceeds cap "
                f"{self._caps.max_conflicts}"
            )
            raise IRCapacityLimitError(msg)

        # 3. Global Key Uniqueness
        entity_keys: set[str] = set()
        for e in doc.entities:
            if e.ir_key in entity_keys:
                raise IRValidationError(f"Duplicate entity ir_key: {e.ir_key}")
            entity_keys.add(e.ir_key)

        ev_keys: set[str] = set()
        for ev in doc.evidence:
            if ev.evidence_key in ev_keys:
                raise IRValidationError(
                    f"Duplicate evidence evidence_key: {ev.evidence_key}"
                )
            ev_keys.add(ev.evidence_key)

        rel_keys: set[str] = set()
        for r in doc.relationships:
            if r.ir_key in rel_keys:
                raise IRValidationError(f"Duplicate relationship ir_key: {r.ir_key}")
            rel_keys.add(r.ir_key)

        unres_keys: set[str] = set()
        for u in doc.unresolved_references:
            if u.unresolved_key in unres_keys:
                raise IRValidationError(
                    f"Duplicate unresolved_reference unresolved_key: "
                    f"{u.unresolved_key}"
                )
            unres_keys.add(u.unresolved_key)

        conf_keys: set[str] = set()
        for c in doc.conflicts:
            if c.conflict_key in conf_keys:
                msg = f"Duplicate conflict conflict_key: {c.conflict_key}"
                raise IRValidationError(msg)
            conf_keys.add(c.conflict_key)

        # 4. Referential Integrity
        for r in doc.relationships:
            if r.source_key not in entity_keys:
                msg = (
                    f"Relationship {r.ir_key} references unknown source_key: "
                    f"{r.source_key}"
                )
                raise IRValidationError(msg)
            if r.target_key is not None and r.target_key not in entity_keys:
                msg = (
                    f"Relationship {r.ir_key} references unknown target_key: "
                    f"{r.target_key}"
                )
                raise IRValidationError(msg)
            if (
                r.unresolved_reference_key is not None
                and r.unresolved_reference_key not in unres_keys
            ):
                msg = (
                    f"Relationship {r.ir_key} references unknown "
                    f"unresolved_reference_key: {r.unresolved_reference_key}"
                )
                raise IRValidationError(msg)
            if (
                r.target_key is None
                and r.unresolved_reference_key is None
                and r.kind
                not in (
                    IRRelationshipKind.DECLARES_DEPENDENCY,
                    IRRelationshipKind.USES_FRAMEWORK,
                )
            ):
                msg = (
                    f"Relationship {r.ir_key} has neither target_key nor "
                    "unresolved_reference_key."
                )
                raise IRValidationError(msg)
            for k in r.evidence_keys:
                if k not in ev_keys:
                    msg = (
                        f"Relationship {r.ir_key} references unknown evidence_key: "
                        f"{k}"
                    )
                    raise IRValidationError(msg)

        for e in doc.entities:
            if e.module_key is not None and e.module_key not in entity_keys:
                raise IRValidationError(
                    f"Entity {e.ir_key} references unknown module_key: "
                    f"{e.module_key}"
                )
            if e.container_key is not None and e.container_key not in entity_keys:
                raise IRValidationError(
                    f"Entity {e.ir_key} references unknown container_key: "
                    f"{e.container_key}"
                )
            if e.container_key == e.ir_key:
                raise IRValidationError(f"Entity {e.ir_key} cannot contain itself.")
            for k in e.evidence_keys:
                if k not in ev_keys:
                    msg = f"Entity {e.ir_key} references unknown evidence_key: {k}"
                    raise IRValidationError(msg)

        for u in doc.unresolved_references:
            if u.source_key not in entity_keys:
                msg = (
                    f"Unresolved ref {u.unresolved_key} references unknown "
                    f"source_key: {u.source_key}"
                )
                raise IRValidationError(msg)
            for k in u.evidence_keys:
                if k not in ev_keys:
                    msg = (
                        f"Unresolved ref {u.unresolved_key} references unknown "
                        f"evidence_key: {k}"
                    )
                    raise IRValidationError(msg)

        all_known_subject_keys = entity_keys | rel_keys | ev_keys | unres_keys
        for c in doc.conflicts:
            if c.subject_key not in all_known_subject_keys:
                msg = (
                    f"Conflict {c.conflict_key} references unknown subject_key: "
                    f"{c.subject_key}"
                )
                raise IRValidationError(msg)
            for k in c.competing_evidence_keys:
                if k not in ev_keys:
                    msg = (
                        f"Conflict {c.conflict_key} references unknown "
                        f"evidence_key: {k}"
                    )
                    raise IRValidationError(msg)

        # 5. Completeness Accounting Invariants
        if doc.completeness.total_entities != len(doc.entities):
            msg = (
                f"Completeness total_entities ({doc.completeness.total_entities}) "
                f"does not match actual entities count ({len(doc.entities)})"
            )
            raise IRValidationError(msg)

        if doc.completeness.total_relationships != len(doc.relationships):
            msg = (
                f"Completeness total_relationships "
                f"({doc.completeness.total_relationships}) does not match "
                f"actual relationships count ({len(doc.relationships)})"
            )
            raise IRValidationError(msg)

        if doc.completeness.total_unresolved_references != len(
            doc.unresolved_references
        ):
            msg = (
                f"Completeness total_unresolved_references "
                f"({doc.completeness.total_unresolved_references}) does not "
                f"match actual unresolved count "
                f"({len(doc.unresolved_references)})"
            )
            raise IRValidationError(msg)

        if doc.completeness.total_conflicts != len(doc.conflicts):
            msg = (
                f"Completeness total_conflicts "
                f"({doc.completeness.total_conflicts}) does not match actual "
                f"conflicts count ({len(doc.conflicts)})"
            )
            raise IRValidationError(msg)

        if doc.completeness.failed_artifacts > 0 and not doc.completeness.is_partial:
            msg = "Completeness indicates failed artifacts but is_partial is False."
            raise IRValidationError(msg)

        # 6. Canonical Serialized Byte Size Cap
        payload_bytes = doc.canonical_json_size_bytes()
        if payload_bytes > self._caps.max_serialized_bytes:
            msg = (
                f"Canonical IR JSON payload size {payload_bytes} bytes exceeds "
                f"cap {self._caps.max_serialized_bytes} bytes"
            )
            raise IRCapacityLimitError(msg)


__all__ = [
    "IRCapacityConfig",
    "IRValidator",
]
