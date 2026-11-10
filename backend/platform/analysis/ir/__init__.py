"""Intermediate Representation (IR) construction and normalization (Phase 3 Module 3).

Exposes canonical F3 models, vocabularies, key builders, and the construction service.
"""

from backend.platform.analysis.ir.handlers import (
    IRConstructionStageHandler,
    register_ir_stage_handler,
)
from backend.platform.analysis.ir.model import (
    ANALYZER_VERSION,
    IR_SCHEMA_VERSION,
    IRCapacityLimitError,
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
    IRValidationError,
    build_conflict_key,
    build_entity_key,
    build_evidence_key,
    build_relationship_key,
    build_unresolved_key,
    is_stronger,
)
from backend.platform.analysis.ir.service import IRConstructionService
from backend.platform.analysis.ir.validator import (
    IRCapacityConfig,
    IRValidator,
)

__all__ = [
    "ANALYZER_VERSION",
    "IR_SCHEMA_VERSION",
    "IRCapacityConfig",
    "IRCapacityLimitError",
    "IRCompleteness",
    "IRConflict",
    "IRConstructionError",
    "IRConstructionService",
    "IRConstructionStageHandler",
    "IRDocument",
    "IREntity",
    "IREntityKind",
    "IREvidence",
    "IREvidenceStrength",
    "IRFactStatus",
    "IRRelationship",
    "IRRelationshipKind",
    "IRUnresolvedReason",
    "IRUnresolvedReference",
    "IRValidationError",
    "IRValidator",
    "build_conflict_key",
    "build_entity_key",
    "build_evidence_key",
    "build_relationship_key",
    "build_unresolved_key",
    "is_stronger",
    "register_ir_stage_handler",
]
