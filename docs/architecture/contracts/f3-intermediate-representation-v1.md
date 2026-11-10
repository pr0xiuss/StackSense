# F3 — Intermediate Representation Contract v1.0.0

Status: **FROZEN / IMPLEMENTED**
Owner: Phase 3 Module 3 (Intermediate Representation & Semantic Analysis)
Consumer: Phase 3 Module 4 (Architectural Identity & Architecture Model)
Version: `1.0.0`
Last Updated: 2026-11-07

---

## 1. Scope & Ownership

This contract establishes the normative boundary between Phase 3 Module 3 (M3) and Phase 3 Module 4 (M4), with orchestration governed by Phase 3 Module 1 (M1).

1. **M3 Ownership:** M3 consumes the frozen `RepositoryInspectionResult` (F2 v1.0.0), performs deterministic fact normalization, resolves local declarations and references, integrates framework semantic facts, enforces referential integrity, validates capacity bounds, and produces the immutable `IRDocument` (F3 v1.0.0).
2. **M4 Ownership:** M4 consumes the immutable `IRDocument` via the M1 handoff port (`F3ResultReader`). M4 projects language-neutral IR entities and relationships into architectural components, boundaries, and persistent Architecture Models.
3. **M1 Orchestration:** M3 execution is driven by M1 `AnalysisOrchestrator` via `IRConstructionStageHandler` in the `IR_CONSTRUCTION` stage. Stage outputs are transported through the attempt-scoped `AnalysisAttemptStore` implementing `F3ResultWriter` and `F3ResultReader`.
4. **Boundary Invariants:**
   - M3 never invokes M2 directly and does not reconstruct F2 inspection results.
   - M4 never invokes M3 directly and never inspects raw source code or ASTs.
   - M1 alone rebuilds a lost F2 value and replays the stateless M3 constructor
     with the same immutable `AnalysisInput`, configuration fingerprint,
     analyzer version, and IR schema version. Recovery does not reopen completed
     stages or emit new public lifecycle events.
   - F3 contains no raw AST/CST nodes, no source bytes, no unallowlisted literals, no secrets/tokens, and no absolute host filesystem paths.
   - All provenance is strictly traceable to F2 syntax facts, manifest entries, or framework detections. No fabricated provenance is permitted.

---

## 2. Invariants & Guarantees

### 2.1 Determinism & Canonical Equivalence
Given identical F2 `RepositoryInspectionResult` inputs, M3 produces bitwise-identical canonical JSON representations regardless of execution platform, OS, architecture, or dictionary iteration order. All entity, relationship, evidence, unresolved reference, and conflict sequences are sorted deterministically prior to document emission.

### 2.2 Snapshot-Scoped Deterministic Key Spaces
All IR identifiers use deterministic, snapshot-scoped keys formatted as follows:
- **Entities:** `build_entity_key(kind, *parts)` -> `<kind>::<part1>::<part2>...`
  - Path is normalized with forward slashes and relative to repository root.
  - Symbols: `symbol::<path>::<name>::<range_disambiguator>`.
  - Modules: `module::<path>`.
  - Artifacts: `artifact::<path>`.
  - External packages: `external_system::<package_name>`.
- **Relationships:** `build_relationship_key(kind, source_key, target_key, disambiguator)`
  -> `rel::<kind>::<source_key>::<target_key_or_unresolved>::<disambiguator>`
- **Evidence:** `build_evidence_key(source_record_type, path, fact_key, disambiguator)`
  -> `ev::<path>::<source_record_type>::<fact_key>::<disambiguator>`
- **Unresolved References:** `build_unresolved_key(source_key, relationship_kind, target_name, disambiguator)`
  -> `unres::<source_key>::<relationship_kind>::<target_name>::<disambiguator>`
- **Conflicts:** `build_conflict_key(conflict_type, subject_key, disambiguator)`
  -> `conflict::<conflict_type>::<subject_key>::<disambiguator>`

Every caller-supplied key component is normalized to forward slashes where
applicable and percent-encoded as canonical UTF-8 with only `/._-~` left
unescaped. This encoding is lossless: spaces, underscores, percent signs, and
the `::` structural delimiter remain distinct and cannot collapse to one key.

### 2.3 Referential Integrity
1. Every relationship `source_key` MUST resolve to an entity in `IRDocument.entities`.
2. Every relationship `target_key` (when provided) MUST resolve to an entity in `IRDocument.entities`.
3. If `target_key` is None, the relationship MUST specify `unresolved_reference_key` resolving to an item in `IRDocument.unresolved_references` (unless kind is `DECLARES_DEPENDENCY` or `USES_FRAMEWORK`).
4. Every evidence key cited in `IREntity.evidence_keys`, `IRRelationship.evidence_keys`, or `IRUnresolvedReference.evidence_keys` MUST exist in `IRDocument.evidence`.
5. Duplicate entity keys or duplicate relationship keys are strictly prohibited and rejected during document validation.
6. Every entity `module_key` and `container_key` (when present) MUST resolve to
   another entity in the same document; an entity cannot contain itself.

### 2.4 Path & Metadata Safety
1. All file paths MUST be repository-relative and use forward slashes (`/`).
2. Absolute filesystem paths (e.g. Windows drive letters `C:\`, UNC shares `\\server\share`, or Unix absolute roots `/home/user`) are strictly rejected.
3. Metadata dictionaries MUST NOT contain bare sensitive keys (`password`, `secret`, `token`, `credential`, `auth`).
4. Values in metadata dictionaries MUST NOT contain UNC paths or Windows drive letters.

### 2.5 Completeness & Graceful Degradation
`IRDocument.completeness` explicitly captures analysis coverage and degradation:
- `is_partial`: Boolean flag indicating whether inspection or normalization was degraded.
- Granular counters: `total_inventory_artifacts`, `analyzed_artifacts`, `failed_artifacts`, `total_syntax_documents`, `total_syntax_facts`, `total_entities`, `total_relationships`, `total_unresolved_references`, `total_conflicts`.

---

## 3. Schema Specification

### 3.1 Document Root: `IRDocument`

```python
@dataclass(frozen=True)
class IRDocument:
    ir_schema_version: str                      # "1.0.0"
    analysis_id: UUID                           # Analysis execution attempt identifier
    project_id: UUID                            # Owning project identifier
    repository_id: UUID                         # Repository identifier
    snapshot_id: UUID                           # Immutably analyzed repository snapshot
    analyzer_version: str                       # Analyzer version
    configuration_fingerprint: str              # Analysis configuration hash
    entities: tuple[IREntity, ...]              # Sorted, unique intermediate entities
    relationships: tuple[IRRelationship, ...]   # Sorted, unique intermediate relationships
    evidence: tuple[IREvidence, ...]            # Sorted supporting evidence items
    unresolved_references: tuple[IRUnresolvedReference, ...]
    conflicts: tuple[IRConflict, ...]
    completeness: IRCompleteness
    metadata: Mapping[str, Any]                 # Safe, sanitized document metadata
```

### 3.2 Entities & Relationships

```python
@dataclass(frozen=True)
class IREntity:
    ir_key: str                                 # Deterministic entity key
    kind: IREntityKind                          # Entity vocabulary kind
    name: str                                   # Identifier name
    qualified_name: str | None = None           # Scope-qualified name
    artifact_id: UUID | None = None             # Originating artifact UUID
    module_key: str | None = None               # Containing module entity key
    container_key: str | None = None            # Parent entity key if hierarchically nested
    language: str | None = None                 # Programming language or manifest format
    framework: str | None = None                # Framework name if framework-specific
    status: IRFactStatus = IRFactStatus.CONFIRMED
    evidence_keys: tuple[str, ...] = ()         # Pointers into IRDocument.evidence
    metadata: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class IRRelationship:
    ir_key: str                                 # Deterministic relationship key
    kind: IRRelationshipKind                    # Relationship vocabulary kind
    source_key: str                             # Key of source entity
    target_key: str | None = None               # Key of target entity
    unresolved_reference_key: str | None = None # Key of unresolved reference if unresolved
    status: IRFactStatus = IRFactStatus.CONFIRMED
    evidence_keys: tuple[str, ...] = ()         # Pointers into IRDocument.evidence
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

### 3.3 Evidence, Unresolved References, and Conflicts

```python
@dataclass(frozen=True)
class IREvidence:
    evidence_key: str                           # Deterministic evidence key
    artifact_id: UUID | None                    # Originating artifact UUID
    path: str                                   # Repo-relative forward-slash path
    source_record_type: str                     # e.g. "declaration_fact", "syntax_document"
    source_fact_key: str | None = None          # Upstream F2 fact key
    source_range: SourceRange | None = None     # Canonical UTF-8 coordinate range
    parser_adapter_id: str | None = None
    parser_adapter_version: str | None = None
    grammar_abi_version: int | None = None
    framework_name: str | None = None
    supporting_fact_keys: tuple[str, ...] = ()
    upstream_analyzer_version: str = ""
    m3_transformation_version: str = ANALYZER_VERSION
    strength: IREvidenceStrength = IREvidenceStrength.DIRECT_SOURCE
    polarity: str = "supporting"
    metadata: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class IRUnresolvedReference:
    unresolved_key: str                         # Deterministic unresolved reference key
    source_key: str                             # Source entity key
    relationship_kind: IRRelationshipKind       # Reference relationship kind
    target_name: str                            # Unresolved symbol/module target name
    reason: IRUnresolvedReason                  # NOT_FOUND, AMBIGUOUS, DYNAMIC, etc.
    candidate_references: tuple[str, ...] = ()  # Ambiguous resolution candidates
    evidence_keys: tuple[str, ...] = ()         # Supporting evidence pointers
    metadata: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class IRConflict:
    conflict_key: str                           # Deterministic conflict key
    conflict_type: str                          # Conflict category
    subject_key: str                            # Key of conflicted entity/relationship
    competing_evidence_keys: tuple[str, ...]    # Conflicting evidence item keys
    details: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class IRCompleteness:
    total_inventory_artifacts: int = 0
    analyzed_artifacts: int = 0
    failed_artifacts: int = 0
    total_syntax_documents: int = 0
    total_syntax_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    total_unresolved_references: int = 0
    total_conflicts: int = 0
    is_partial: bool = False
```

---

## 4. Controlled Vocabularies

### 4.1 Entity Kinds (`IREntityKind`)
- `REPOSITORY`: Root repository entity.
- `SNAPSHOT`: Analyzed repository commit/snapshot.
- `ARTIFACT`: Ingested file or blob artifact.
- `APPLICATION`: Detected root application or deployment unit.
- `MODULE`: Source file or package module container.
- `SYMBOL`: Code-level declaration (function, class, method, interface, variable).
- `COMPONENT`: Architectural or UI component (e.g. React component).
- `ENDPOINT`: HTTP route handler / endpoint declaration.
- `EXTERNAL_SYSTEM`: External dependency package or third-party service.
- `DATABASE`: Persistence database, store, or schema entity.
- `MESSAGE_INFRASTRUCTURE`: Queue, topic, or event broker.
- `CONFIGURATION`: Configuration profile or manifest entity.

### 4.2 Relationship Kinds (`IRRelationshipKind`)
- `CONTAINS`: Structural containment (e.g. repository contains module, module contains symbol).
- `DECLARES`: Entity declares child symbol or sub-declaration.
- `IMPORTS`: Module-level import dependency.
- `EXPORTS`: Module-level public export.
- `STATIC_CALL_REFERENCE`: Static function or method invocation.
- `INHERITS`: Class inheritance or interface extension.
- `COMPOSES`: Component composition / nesting.
- `DECLARES_ROUTE`: Endpoint route declaration.
- `USES_FRAMEWORK`: Module or application adopts framework capability.
- `DECLARES_DEPENDENCY`: Project declares manifest dependency package.
- `SOURCE_REFERENCES_DEPENDENCY`: Source code references third-party dependency.

F2 `NAME` and `ATTRIBUTE` reference facts are preserved as direct evidence but
do not by themselves prove a call or any other F3 relationship.

### 4.3 Fact Status (`IRFactStatus`)
- `CONFIRMED`: Directly established by deterministic evidence.
- `INFERRED`: Derived through an explicit deterministic rule.
- `UNRESOLVED`: Available evidence is insufficient to resolve the static finding.
- `CONFLICTING`: Competing evidence remains unreconciled.

These statuses describe static IR findings only. They never assert runtime truth
or authoritative Architecture Model status.

### 4.4 Evidence Strength (`IREvidenceStrength`)
Ordered by descending verification strength:
1. `DIRECT_SOURCE`: Direct AST parse of explicit language syntax (Rank 5).
2. `FRAMEWORK_STRUCTURAL`: Framework convention or explicit decorator matching (Rank 4).
3. `CONFIGURATION`: Structured manifest or formal configuration file (Rank 3).
4. `DEPENDENCY`: Third-party package or dependency declaration (Rank 2).
5. `DOCUMENTATION`: Comments, docstrings, or documentation hints (Rank 1).

### 4.5 Unresolved Reasons (`IRUnresolvedReason`)
- `NOT_FOUND`: Target symbol or module is absent from the repository inventory.
- `AMBIGUOUS`: Multiple matching declaration candidates exist without clear disambiguation.
- `DYNAMIC`: Target is resolved dynamically via reflection, runtime lookup, or meta-programming.
- `UNSUPPORTED`: Language or construct semantics are outside parser adapter capabilities.
- `INCOMPLETE_INPUT`: Target file was unanalyzable due to syntax errors, timeouts, or caps.

---

## 5. Resource Bounds & Capacity Limits

The following owner-approved capacity limits are adopted from empirical
worst-case benchmark workloads (250,000 facts / 50 MiB F2 workload):

| Metric | Adopted Limit | Headroom vs Empirical Worst-Case |
| :--- | :--- | :--- |
| **Max Entities** | `150,000` | ~47% over observed 102,002 |
| **Max Relationships** | `500,000` | ~98% over observed 252,001 |
| **Max Evidence Items** | `500,000` | ~98% over observed 252,001 |
| **Max Unresolved References** | `150,000` | ~200% over observed 50,000 |
| **Max Conflicts** | `25,000` | Multi-fold headroom |
| **Max Serialized Bytes** | `512 MiB` (536,870,912 B) | ~44% headroom over observed 355.9 MB |

If any cap is exceeded during construction or validation:
1. `IRCapacityLimitError` is raised.
2. The stage records a diagnostic with category `RESOURCE` and code `IR_CAPACITY_LIMIT_EXCEEDED`.
3. The stage terminates with status `FAILED` and error code `IR_CAPACITY_EXCEEDED`.

---

## 6. Lifecycle & Pipeline Integration

### 6.1 Stage Definition
- **Stage Name:** `AnalysisStageName.IR_CONSTRUCTION` (`ir_construction`).
- **Position:** Immediately following `SYNTAX_EXTRACTION` (M2) and preceding `ARCHITECTURE_MODEL` (M4).
- **Mandatory:** `True`. Cannot be skipped for standard architecture analysis.

### 6.2 Error & Diagnostic Codes
| Situation | Diagnostic Code | Severity | Stage Result Error Code |
| :--- | :--- | :--- | :--- |
| Missing F2 Result | `F2_HANDOFF_UNAVAILABLE` | `ERROR` | `F2_UNAVAILABLE` |
| Attempt ID Mismatch | `F2_IDENTITY_MISMATCH` | `ERROR` | `F2_IDENTITY_MISMATCH` |
| Snapshot ID Mismatch | `F2_SNAPSHOT_MISMATCH` | `ERROR` | `F2_SNAPSHOT_MISMATCH` |
| Capacity Cap Exceeded | `IR_CAPACITY_LIMIT_EXCEEDED`| `ERROR` | `IR_CAPACITY_EXCEEDED` |
| Validation / Parse Error | `IR_CONSTRUCTION_ERROR` | `ERROR` | `IR_CONSTRUCTION_FAILED` |
| Analysis Cancelled | None (raises `AnalysisCancelledError`) | N/A | Cancelled |

---

## 7. Handoff Ports & Attempt Storage

M1 provides decoupled stage-to-stage communication via protocol ports defined in `backend.platform.analysis.application.handoff`:
- `F2ResultReader`: `read_f2_result(analysis_id, job_id, analysis_input=None) -> RepositoryInspectionResult`
- `F3ResultWriter`: `write_f3_result(analysis_id, job_id, result: IRDocument) -> None`
- `F3ResultReader`: `read_f3_result(analysis_id, job_id, analysis_input=None) -> IRDocument`
- `AnalysisAttemptStore`: In-memory thread-safe implementation of both readers
  and the writer. Writes are immutable and idempotent; non-equivalent
  replacement is rejected. Supplying `AnalysisInput` permits M1-owned recovery
  when a non-persisted value is missing. `release(analysis_id, job_id)` clears
  F2/F3 and M2 attempt state after the job reaches a terminal state.

The M3 handler publishes no stage-completed event itself. M1 orchestration emits
the single canonical lifecycle event after it commits the stage transition.

---

## 8. Change Control & Evolution

1. **Semantic Versioning:** This contract is versioned as `1.0.0`.
2. **Backward Compatibility:** Additive changes (e.g. new optional metadata keys or new enum members) increment the minor version (`1.1.0`).
3. **Breaking Changes:** Any alteration of existing record fields, key algorithms, serialization format, or vocabulary semantics requires incrementing the major version to `2.0.0` and formal architectural approval.
