# PROJECT_CONTEXT.md — StackSense Engineering Context

Last reconciled: 2026-11-06
Current branch: `feature_mannan`

## 1. Project Overview

StackSense is a software repository intelligence and architecture analysis
platform. Express/MongoDB owns the platform plane (identity, projects, RBAC,
repository registration, immutable revisions, and artifact metadata). The
Python/FastAPI/PostgreSQL analysis plane owns analysis lifecycle and execution.
The two backends are intentional, independently owned systems connected only
through authenticated internal APIs.

Phase 3 is in progress. M1 and M2 are implemented, verified, and frozen. The
current task is the draft plan for M3: Intermediate Representation and Semantic
Analysis. M3 implementation has not started.

### 1.1 Authoritative sources

- `master.txt`: frozen architecture; Sections 9–12 govern lifecycle, analysis,
  IR/identity, and Architecture Model behavior.
- `docs/architecture/adr/0001-express-python-integration.md`: approved
  Express/Python ownership and integration boundary.
- `docs/architecture/contracts/f1-analysis-execution-input-v1.md`: frozen F1
  execution/input contract.
- `docs/architecture/contracts/f2-repository-inspection-syntax-v1.md`: frozen
  F2 repository inspection and parser-neutral syntax/evidence contract.
- Actual source and tests remain the implementation source of truth; this file
  is a rolling handoff, not proof of correctness.

The root `docs/` directory is retained. It contains the normative frozen ADR,
F1, and F2 records required to implement and review M3. Completed plan detail is
compacted here instead of deleting authoritative architecture history.

### 1.2 Verified repository state

- Branch: `feature_mannan`, ahead of its remote by three commits when inspected.
- The worktree contains existing M2 implementation/test/context changes. They
  are preserved and are not part of this planning edit.
- There is no existing `backend/platform/analysis/ir/` package or M3 handler.
- `AnalysisStageName.IR_CONSTRUCTION` and `IR_SCHEMA_VERSION = "1.0.0"`
  already exist in frozen M1.
- Production worker composition currently registers only the four M2 handlers.
- The frozen `ExecutionContext` supplies `AnalysisInput`, lifecycle ports,
  diagnostics, events, progress, and cancellation; it does not carry arbitrary
  stage output.
- F2 is an immutable, canonical, attempt-scoped `RepositoryInspectionResult`
  exposed by `M2AttemptHandoff`/`M2ExecutionCoordinator`. M1 orchestration
  owns recovery-only rebuilding of a lost F2 handoff. M3 must never invoke M2.

## 2. Global Constraints and Approved Architecture

1. Do not modify `master.txt`, frozen F1, or frozen F2 without explicit
   versioned change control and owner approval.
2. Python/FastAPI implements M1–M4. PostgreSQL is the Python analysis plane's
   persistence authority. Express/MongoDB ownership remains unchanged.
3. Neither backend may directly read the other's database. Artifact access and
   platform authorization use approved authenticated internal APIs.
4. M1 owns analysis/job/stage/event lifecycle, durable diagnostics, execution
   orchestration, lifecycle APIs, and recovery.
5. M2 owns inventory, eligibility, detection, parsing, framework enrichment,
   F2 production, and deterministic F2 reconstruction.
6. M3 owns parser-neutral IR construction, supported normalization, bounded
   semantic analysis, IR validation, and the immutable versioned F3 result.
7. M4 owns cross-file architectural identity resolution, canonical architecture
   logical IDs, Architecture Model construction/validation/persistence,
   publication, findings projections, and result-query APIs.
8. M1's `AnalysisDiagnostic` is the one shared diagnostic/finding-source
   contract. M3 emits it; M3 must not define a competing diagnostic domain.
9. IR is an intermediate, non-canonical analysis artifact. The validated
   Architecture Model is the architectural source of truth.
10. IR is not persisted by default. It may be canonically serialized and held
    in an attempt-scoped handoff; persistence would require owner approval.
11. No repository code execution, network access during analysis, AI/LLM
    interpretation, secret propagation, absolute-host-path identity, or global
    mutable analyzer state is permitted.
12. Determinism must be independent of worker scheduling, input iteration
    order, hash randomization, and analyzer completion order.
13. No silent truncation. Resource caps fail explicitly with safe diagnostics.
14. Analysis lifecycle retains Section 9 semantics, including `PARTIAL` and
    `TIMEOUT`; M3 cannot redefine lifecycle transitions or terminal states.
15. No new public event vocabulary is introduced by M3 without separate
    approval.

## 3. Phase Index

| Phase/module | Status | Retained context |
|---|---|---|
| Phase 1 | Complete | Original Python repository platform foundation remains retained. |
| Phase 2 | Complete | Python reference implementation and completed MERN platform plane coexist. |
| Phase 3 M1 | **FROZEN / COMPLETE — F1 v1.0.0** | Analysis lifecycle, execution, persistence, diagnostics, recovery, APIs, PostgreSQL and Celery/RabbitMQ integration. |
| Phase 3 M2 | **FROZEN / COMPLETE — F2 v1.0.0** | Deterministic inspection, detection, isolated parsing, framework enrichment, canonical F2, recovery-only rebuilding. |
| Phase 3 M3 | **DRAFT PLAN — NOT APPROVED / NOT STARTED** | IR, normalization, bounded semantic analysis, validation, and F3. |
| Phase 3 M4 | Planned / blocked on F3 | Architectural identity and canonical Architecture Model persistence/publication/results. |
| Phase 3 M5 | Planned / blocked on M4 APIs | Analysis UX and Architecture Model exploration. |
| Phase 3 M6 | Planned / blocked on M4/M5 | Integration, evaluation, determinism, security, and performance closure. |
| Later phases | Deferred | Projections, diagram engine, search, AI-assisted explanation, and later roadmap capabilities remain outside M3. |

## 4. Current Phase Plan — Phase 3, Module 3

**Status:** draft implementation plan; owner approval required.
**Implementation:** not started.
**Batch count:** exactly three.

### 4.1 Objective

M3 transforms one immutable F2 `RepositoryInspectionResult` into one immutable,
parser-neutral, versioned `IRDocument` (F3). It normalizes F2 inventory and
syntax evidence, performs only deterministic semantics supported by that
evidence, preserves provenance/incompleteness/conflict, validates the result,
and supplies F3 to M4 without constructing canonical architecture identity or
an Architecture Model.

### 4.2 Verified inputs and reusable implementation

M3 reuses these verified contracts and conventions:

- `backend/platform/analysis/inspection/model.py`
  - `RepositoryInspectionResult`, inventory role/outcome, coverage, language,
    runtime, and framework detections.
- `backend/platform/analysis/syntax/model.py`
  - `SyntaxDocument`; declaration, import, export, reference, framework, and
    manifest facts; canonical UTF-8 `SourceRange`; deterministic fact keys and
    ordering.
- `backend/platform/analysis/domain/input.py`
  - immutable F1 IDs, versions, effective configuration, and artifact boundary.
- `backend/platform/analysis/domain/diagnostic.py`
  - the shared immutable `AnalysisDiagnostic`.
- `backend/platform/analysis/application/execution.py` and
  `application/registry.py`
  - stage handler/result protocol and registration.
- `backend/platform/analysis/inspection/handlers.py`
  - attempt-scoped handoff/coordinator and exact-signature F2 recovery behavior;
    this is a reference for orchestration integration, not an API M3 may call.
- `backend/worker/tasks.py`
  - current production composition root.
- Existing dataclass immutability, canonical JSON, UUID, structured diagnostic,
  cancellation, progress, strict typing, and deterministic-test conventions.

No new third-party dependency is required by the proposed M3 design.

### 4.3 Ownership boundaries and non-goals

M3 owns:

- F2 contract validation at its consumer boundary;
- repository/snapshot/artifact coverage in IR;
- normalization of declarations, references, imports, exports, manifest facts,
  detections, and framework evidence;
- deterministic snapshot-scoped IR keys;
- exact intra-document scope/container resolution;
- evidence-supported relationship/dependency candidates;
- unresolved, ambiguous, dynamic, conflicting, and partial representations;
- canonical serialization, validation, diagnostics, caps, and production of the
  immutable F3 value.

M3 does not own:

- inventory, eligibility, language/framework detection, parsing, framework
  extraction, or F2 recovery;
- pipeline orchestration, attempt lifecycle, stage-output storage, handoff
  recovery, or replay scheduling;
- invocation or import of M2 producer/parser services;
- cross-file canonical identity resolution, entity merging across analyzers or
  versions, fuzzy name matching, rename/move continuity, or collision policy
  for Architecture entities;
- Architecture logical IDs, Architecture Versions, model construction,
  PostgreSQL Architecture persistence, publication, findings/result APIs, graph
  projection, diagrams, or frontend work;
- executing package managers, resolving dependencies over a network, importing
  repository code, or AI-based interpretation.

M3 may normalize an import/export or dependency into a relationship candidate
and attach deterministic textual/path candidate references. It resolves only
document-local lexical, declaration, container, and reference identity. It must
not claim a resolved cross-file target. Consistent with master Section 11's
IR-to-Identity-Resolution-to-Architecture-Builder flow, M4 exclusively owns
cross-file identity resolution, cross-analyzer merging, canonical logical IDs,
historical continuity, collision handling for Architecture entities, and
Architecture Model construction.

### 4.4 Data flow and recovery boundary

```text
Frozen F1 AnalysisInput
        |
        v
M2 stages -> immutable RepositoryInspectionResult (F2)
        |
        | supplied by M1-owned attempt orchestration
        v
M3 F2 consumer boundary
        |
        v
normalize -> local semantics -> validate -> immutable IRDocument (F3)
        |
        | attempt-scoped handoff
        v
M4 consumer (later)
```

The internal handoff interfaces are:

- **F2 -> M3:** an M1-owned `F2ResultReader` exposes only
  `require_for_attempt(analysis_id, job_id, expected_signature) ->
  RepositoryInspectionResult`. M1's adapter obtains the existing attempt-scoped
  F2, performs M1-owned recovery before entry when it is absent, and verifies
  the immutable input/configuration/parser/analyzer signature. M3 receives only
  the returned F2 value. It cannot request or invoke reconstruction.
- **F3 -> M4:** an M1-owned `F3ResultWriter` accepts the validated immutable
  `IRDocument` for the attempt, and an M1-owned `F3ResultReader` supplies that
  exact value to M4. M3 writes once after successful validation; M4 reads only
  and has no M3 invocation/replay API.

`M3AttemptHandoff` and `M3ExecutionCoordinator` are therefore unnecessary and
must not be introduced. M3 is one construction stage, so it needs only the
stateless `IRConstructionService` and a thin `IRConstructionStageHandler`.
Attempt lifecycle, physical handoff storage, release, recovery, and replay stay
in M1's application/composition layer.

F3 remains non-persisted and attempt-scoped. If its handoff is lost, M1 replays
the stateless M3 constructor using byte-equivalent F2 and the identical effective
configuration, M3 analyzer version, and IR schema version. Recovery only
repopulates the handoff: it does not reopen or rewrite a completed Stage, alter
Analysis/Job/Stage lifecycle state, or emit new public event vocabulary. A
signature mismatch or non-equivalent replay fails explicitly. M4 only consumes
the supplied F3 value.

### 4.5 Proposed F3 contract

F3/IR v1 is proposed, not frozen. The implementation must record the normative
contract in proposed
`docs/architecture/contracts/f3-intermediate-representation-v1.md` and freeze
it only after M4 consumer review and owner approval.

F3 has one canonical compatibility version: the `ir_schema_version` field. Its
initial value is the existing frozen M1 `IR_SCHEMA_VERSION = "1.0.0"`. There is
no separate `f3_version` field, because two independently changing version
numbers for the same payload would be ambiguous. “F3 v1.0.0” means the F3
handoff whose `ir_schema_version` is `1.0.0`. The root also records the consumed
`f2_version` as input provenance, not as F3's version. Any incompatible future
F3 change requires a new IR schema version and coordinated, owner-approved
versioned change control; M3 does not silently change the frozen M1 constant.
At execution, the stage adapter takes the expected value from the frozen
`AnalysisInput.ir_schema_version`, requires it to equal the supported
`IR_SCHEMA_VERSION`, and passes it into the stateless constructor alongside F2.
Replay uses the identical value. F2 does not need, and must not receive, a new
field for this purpose.

#### 4.5.1 Root `IRDocument`

Proposed immutable fields:

- canonical `ir_schema_version` and consumed `f2_version` provenance;
- `analysis_id`, `project_id`, `repository_id`, and `snapshot_id`;
- M3 `analyzer_version` and effective `configuration_fingerprint`;
- ordered tuples of `entities`, `relationships`, `evidence`,
  `unresolved_references`, and `conflicts`;
- `IRCompleteness` coverage/counter summary;
- ordered shared `diagnostic_ids`;
- canonical `to_dict()` and UTF-8 `to_canonical_json()`.

The root validates exact F2 version support, ID consistency, configuration and
version signatures, uniqueness, references, ordering, and cap compliance.

#### 4.5.2 Proposed schema vocabulary

- `IREntityKind`: `repository`, `snapshot`, `artifact`, `application`,
  `module`, `symbol`, `component`, `endpoint`, `external_system`,
  `database`, `message_infrastructure`, and `configuration`.
- `IRRelationshipKind`: `contains`, `declares`, `imports`, `exports`,
  `static_call_reference`, `inherits`, `composes`, `declares_route`,
  `uses_framework`, `declares_dependency`, and
  `source_references_dependency`.
- `IRFactStatus`: `confirmed`, `inferred`, `unresolved`, and
  `conflicting`.
- `IREvidenceStrength`: named ordered levels `direct_source`,
  `framework_structural`, `configuration`, `dependency`, and
  `documentation`; arbitrary floating confidence is prohibited.
- `IRUnresolvedReason`: `not_found`, `ambiguous`, `dynamic`,
  `unsupported`, and `incomplete_input`.

The exact enum set is an owner approval item. New values after freeze require
F3 compatibility review.

#### 4.5.3 Proposed record shapes

- `IREntity`: F3-local `ir_key`, kind, name, optional qualified name,
  artifact/module/container references, language/framework metadata, status,
  ordered evidence keys, and safe typed metadata.
- `IRRelationship`: F3-local key, relationship kind, source IR key, optional
  exact document-local target IR key, optional unresolved-reference key, status,
  ordered evidence keys, and safe typed metadata.
- `IREvidence`: deterministic evidence key, artifact ID and repository-relative
  path, required source F2 record type, optional source F2 fact key, optional
  unchanged `SourceRange`, exact upstream producer provenance, M3 transformation
  version, named strength, polarity, and allowlisted safe metadata. The fact key
  is present only when the evidence originated from a `SyntaxFact`; inventory,
  detection, coverage, and other F2 record evidence leaves it `None`. M3 never
  manufactures a fact key or any missing provenance field.
- `IRUnresolvedReference`: source key, relationship kind, original normalized
  target text, reason, ordered candidate references, and evidence keys.
- `IRConflict`: deterministic key, conflict type, subject key, competing
  evidence keys, and safe structured details.
- `IRCompleteness`: inventory/document/fact/entity/relationship/unresolved/
  conflict/failed-artifact counts plus an explicit partial flag.

`IRFactStatus` has these exact static-analysis meanings:

- `confirmed`: directly established by deterministic evidence;
- `inferred`: derived through a documented explicit deterministic rule;
- `unresolved`: available evidence is insufficient to establish the finding or
  its target;
- `conflicting`: competing evidence remains unreconciled.

These statuses describe only the state of a static IR finding. They never claim
runtime truth, observed execution, or authoritative Architecture Model status.
Only M4 can resolve and publish authoritative architectural facts.

IR keys are snapshot-scoped deterministic identifiers, not persistence UUIDs or
Architecture logical IDs. They derive from immutable upstream IDs, normalized
repository-relative paths, F2 fact keys, entity/relationship kind, and required
local disambiguators. They must never use `hash()`, random UUIDs, database row
IDs, absolute paths, display name alone, or iteration order.

#### 4.5.4 Evidence provenance and conflict rules

M3 copies provenance; it does not invent analyzer identities:

- For parser-produced facts, provenance comes from the owning
  `SyntaxDocument`: `parser_adapter_id`, `parser_adapter_version`, and optional
  `grammar_abi_version`, plus the document artifact/path and fact key/range.
- For framework facts, F3 records `framework_name`, the framework fact key, and
  ordered `supporting_fact_keys`. Because frozen F2 exposes no separate
  framework-analyzer ID/version, M3 must not manufacture one. The root F2
  `analyzer_version` remains available as producer-bundle provenance.
- For manifest, inventory, and detection-derived evidence, F3 records the F2
  record/fact type, available artifact/path/range or evidence signals, and the
  root F2 `analyzer_version`; absent producer fields remain absent.
- M3 transformation provenance records the frozen/configured M3 analyzer
  version and `ir_schema_version` separately from upstream producer provenance.

Strength mapping is deterministic: parser declaration/import/export/reference
facts are `direct_source`; typed framework facts are `framework_structural`;
configuration facts are `configuration`; package/manifest dependency
declarations are `dependency`; and documentation-derived facts are
`documentation`. Inventory/detection evidence uses the class of its actual
supporting signal and is not upgraded merely because a detector emitted it.

Evidence strength is a strict strongest-to-weakest ordering:

`direct_source > framework_structural > configuration > dependency > documentation`.

Strength classifies the basis of evidence; it is not runtime confidence and is
not proof of execution. Precedence may choose a preferred interpretation only
where the F3 contract defines an explicit deterministic rule. All competing
evidence remains referenced. Contradictory evidence creates a `conflicting`
status and `IRConflict` containing every competing evidence key; ties,
unhandled contradictions, and unsafe resolutions remain unresolved rather than
being silently discarded.

### 4.6 F2-to-IR normalization

| F2 input | M3 output |
|---|---|
| Root IDs/versions/configuration | F3 root identity/signature and validation boundary |
| Every inventory entry | Artifact coverage/entity with role, outcome, language, content hash, and safe classification metadata |
| Repository/snapshot identity | Repository and snapshot IR roots linked by containment |
| Module/package declaration | Module candidate and local declaration containment |
| Class/function/method/interface/type/component declaration | Symbol or evidence-backed component candidate; exact local container retained |
| Import fact | Import relationship candidate; alias/source text retained; cross-file target unresolved for M4 |
| Export fact | Export relationship candidate with local exact declaration target when provable |
| Call/name/attribute/inheritance/decorator/composition reference | Exact document-local relationship if lexical evidence proves it; otherwise unresolved with candidates. A call is a static call-site reference, never observed execution. |
| Framework fact | Evidence-backed component/endpoint/application candidate or static relationship only when its typed F2 fact supports it |
| Manifest fact | `declares_dependency` or configuration evidence; never source use or runtime observation by itself |
| Source import/reference to a dependency | `source_references_dependency`; distinct from manifest declaration and never runtime observation |
| Language/runtime/framework detections | Root/artifact metadata and evidence; detection alone does not invent architecture nodes |
| Parse failures and F2 diagnostics | Completeness/partial coverage and shared diagnostic references |

All source locations are copied without coordinate conversion from F2's
canonical UTF-8 coordinate space. Literal secret values, raw source, absolute
paths, and prohibited-sensitive content are not admitted to F3 metadata.

Duplicate records with identical deterministic key and content merge ordered
evidence. A repeated key with different semantic content becomes an explicit
conflict/diagnostic or validation failure; it is never last-write-wins.

Application, component, endpoint, database, external-system, message-
infrastructure, and configuration records in F3 are explicitly
evidence-backed **IR candidates**. Their kind describes what M3 evidence
suggests; it does not make them authoritative Architecture Model entities.
Only M4 may resolve, merge, promote, assign canonical logical identity, and
publish them into an Architecture Model.

### 4.7 Semantic rules and limits

1. Semantic state is analysis-scoped and immutable at publication; no global
   registry exists.
2. M3 builds per-document scope/container/declaration/export/alias indexes from
   F2 only.
3. It resolves local references through exact lexical/container rules and exact
   aliases. No fuzzy, probabilistic, or display-name-only matching is allowed.
4. Imports, re-exports, package paths, and manifest dependencies are normalized
   into textual/path target references and candidates. M3 does not resolve
   declarations across documents; all cross-file identity remains for M4.
5. Dynamic imports, computed member access, indirect calls, wildcard ambiguity,
   missing exports, and unsupported syntax remain unresolved with reason and
   candidate evidence.
6. Cycles are valid and preserved; processing order cannot change output.
7. Manifest `declares_dependency`, source `imports`,
   `source_references_dependency`, and `static_call_reference` remain distinct.
   None means a dependency or call was observed at runtime.
8. Framework enrichment may strengthen or type generic evidence but cannot
   erase the generic fact or bypass common normalization.
9. Architecture-like candidate types are produced only from explicit F2
   evidence and always remain non-authoritative IR candidates. A dependency
   name alone does not create a confirmed application, endpoint, external
   system, database, or message-infrastructure entity.
10. Evidence conflicts are retained. Deterministic precedence may set a status
    only when the F3 contract explicitly defines the rule; it does not delete
    losing evidence.
11. Incomplete F2 normally produces a valid partial IR with completeness and
    diagnostics. Unsupported F2 versions, root-ID/signature mismatch, broken
    internal references, key collisions, or cap violations fail the mandatory
    IR stage explicitly.
12. M3 reports through `AnalysisDiagnostic` and existing stage outcomes. It
    does not introduce a second findings model or redefine analysis lifecycle.

### 4.8 Resource, security, and determinism policy

- M3 reads only the supplied immutable F2 value. It does not reopen artifacts,
  execute source, import packages, spawn language runtimes, or access networks.
- Metadata is allowlisted and recursively checked to prevent secrets, unsafe
  objects, host paths, and unbounded values from crossing F3.
- Cancellation/progress checkpoints occur at bounded document/fact phases.
- Canonical sorting is defined for every record type and nested mapping.
- Fact/result caps are not guessed. The first implementation batch benchmarks
  worst-case legal F2 (including the frozen 250,000-fact/50 MiB F2 limits) and
  representative mixed-language repositories. Evidence must record wall time,
  peak RSS, entity/relationship/evidence counts, and canonical F3 size.
- Numeric M3 caps require owner approval before the second batch. Exceeding an
  approved atomic cap produces a safe diagnostic and fails explicitly; M3 never
  silently truncates or emits an apparently complete result.

### 4.9 Exactly three implementation batches

#### Batch 1 — F3 foundation and deterministic normalization

**Objective:** establish the draft F3 schema, immutable model, key rules,
canonical serialization, F2 consumer boundary, basic normalization, and
benchmark evidence.

**Create (proposed):**

- `backend/platform/analysis/ir/__init__.py`: intentional public M3 exports.
- `backend/platform/analysis/ir/model.py`: enums, immutable F3 records,
  deterministic key builders, ordering, safe metadata, canonical JSON.
- `backend/platform/analysis/ir/service.py`: `IRConstructionService` and
  first-pass F2 normalization into repository/snapshot/artifact/module/symbol
  records, evidence, relationship candidates, completeness, and diagnostics.
- `tests/p3/analysis/test_m3_contracts.py`: immutability, version, enum, key,
  ordering, canonical serialization, malformed/collision, and metadata safety.
- `tests/p3/analysis/test_m3_normalization.py`: complete F2 mapping, source
  producer provenance/ranges, role/outcome, partial F2, framework support-key,
  manifest/source-reference, and candidate-authority distinctions.
- `tests/p3/analysis/test_m3_benchmarks.py`: bounded representative and
  worst-case legal F2 measurements; it records evidence, not flaky timing gates.
- `tests/fixtures/p3/m3/`: minimal Python/JS/TS/JSX/TSX, mixed, Unicode,
  partial, conflict, and cap fixtures with expected canonical fragments.

**Modify:**

- `PROJECT_CONTEXT.md`: record actual implementation evidence and cap decision.

**Input/output:** frozen F2 v1.0.0 in; draft immutable F3 with canonical
`ir_schema_version = "1.0.0"` out. No separate `f3_version`, stage handler, or
M4 integration yet.

**Dependencies:** frozen F1/F2 only.

**Acceptance criteria:**

1. Every F2 inventory record has explicit IR coverage.
2. Supported F2 facts normalize without parser-specific AST values.
3. Keys and canonical JSON are byte-equivalent under shuffled input.
4. Source ranges/evidence/diagnostic references survive unchanged.
5. Parser/framework/root producer provenance maps exactly from available F2
   fields; absent analyzer IDs remain absent rather than being invented.
6. Malformed versions, collisions, unsafe metadata, and signature mismatch fail
   explicitly.
7. Benchmark evidence is reviewed and numeric caps are presented for approval.

**Verification:**

```bash
venv/bin/python -m pytest -q tests/p3/analysis/test_m3_contracts.py tests/p3/analysis/test_m3_normalization.py tests/p3/analysis/test_m3_benchmarks.py
venv/bin/ruff check backend/platform/analysis/ir tests/p3/analysis/test_m3_*.py
venv/bin/mypy backend
```

**Definition of Done:** model and normalizer are reviewable, deterministic, and
safe; benchmark/cap evidence and enum/key vocabulary await or receive explicit
owner approval; no orchestration or semantic overreach is present.

#### Batch 2 — Bounded semantic enrichment and IR validation

**Objective:** implement exact document-local semantic resolution,
unresolved/conflict representation, complete validation, and approved resource
enforcement.

**Create (proposed):**

- `backend/platform/analysis/ir/validator.py`: `IRValidator` for schema,
  uniqueness, references, provenance, ordering, metadata, completeness, and cap
  invariants.
- `tests/p3/analysis/test_m3_semantics.py`: scope/container, alias, export,
  static call reference, inheritance, composition, dynamic/ambiguous/unresolved,
  cycles, manifest-declared-vs-source-referenced dependency, and framework/
  generic evidence tests.
- `tests/p3/analysis/test_m3_validation.py`: malformed graphs, unsupported
  values, collisions, missing evidence, cap failure, secrets/absolute paths,
  deterministic duplicate/conflict behavior.
- `tests/p3/analysis/test_m3_goldens.py`: canonical complete/partial/conflicting
  F3 goldens and shuffled/concurrent-order equivalence.

**Modify:**

- `backend/platform/analysis/ir/service.py`: analysis-scoped indexes, exact
  local resolver, unresolved/candidate/conflict aggregation, cancellation and
  progress checkpoints.
- `backend/platform/analysis/ir/model.py`: only owner-approved vocabulary or
  compatibility corrections discovered before F3 freeze.
- `backend/platform/config.py`: add the owner-approved atomic M3 caps.
- `tests/fixtures/p3/m3/`: add ambiguous, dynamic, re-export, cycle,
  framework, malformed, adversarial, and golden cases.
- `PROJECT_CONTEXT.md`: record cap approval, deviations, and actual evidence.

**Input/output:** Batch 1 draft F3 model in; validated deterministic F3 candidate
out. Cross-file Architecture identity remains unresolved for M4.

**Dependencies:** Batch 1 complete; owner approval of F3 vocabulary/key rules
and benchmark-derived numeric caps.

**Acceptance criteria:**

1. Exact local references resolve reproducibly; ambiguous/dynamic/cross-file
   targets remain explicit and evidence-backed.
2. Manifest-declared, imported, and source-referenced dependencies remain
   distinguishable; no static relationship claims runtime observation.
3. Conflicts/cycles are preserved and duplicate evidence is deterministic.
4. Validator rejects unsupported versions, dangling local references, missing
   provenance, collisions, unsafe metadata, and cap violations.
5. Complete, partial, conflict, and shuffled-input golden tests are stable.
6. No M4 identity/model/persistence logic appears in M3.

**Verification:**

```bash
venv/bin/python -m pytest -q tests/p3/analysis/test_m3_*.py
venv/bin/ruff check backend/platform/analysis/ir tests/p3/analysis/test_m3_*.py
venv/bin/mypy backend
```

**Definition of Done:** the standalone service converts frozen F2 to validated,
bounded, deterministic F3 candidates and expresses all uncertainty without
fabrication or scope leakage.

#### Batch 3 — Orchestration integration, F3 handoff, M4 consumer compatibility, and freeze

**Objective:** register the IR construction stage through M1-owned orchestration,
connect the M1-owned F2-reader and F3-reader/writer handoffs, verify M1-owned
replay, complete regression and M4 consumer review, and freeze F3 only after
approval.

**Create (proposed):**

- `backend/platform/analysis/ir/handlers.py`: thin
  `IRConstructionStageHandler` and registration helper. The handler receives
  M1-owned `F2ResultReader` and `F3ResultWriter` ports, calls the stateless M3
  service once, and publishes only a validated immutable result. It contains no
  coordinator, attempt lifecycle, physical handoff, or recovery behavior.
- `backend/platform/analysis/application/handoff.py`: proposed M1-owned internal
  `F2ResultReader`, `F3ResultWriter`, and `F3ResultReader` protocols plus the
  attempt-scoped output adapter/store. This is internal orchestration support,
  not a change to frozen F1 or public lifecycle/event contracts.
- `tests/p3/analysis/test_m3_integration.py`: real registry/handler ordering,
  supplied/missing/mismatched F2, attempt isolation/release, progress,
  cancellation, diagnostics, retries, duplicate delivery, M1-owned F3 replay,
  deterministic handoff, and M4 consumer stub.
- `docs/architecture/contracts/f3-intermediate-representation-v1.md`:
  normative F3 producer/consumer/version/change-control contract after owner
  approval and M4 consumer sign-off.

**Modify:**

- `backend/worker/tasks.py`: instantiate M3 composition, register only the
  existing `IR_CONSTRUCTION` stage, and connect M1-owned F2/F3 handoff and
  replay adapters without changing F1 or giving M3 an M2 invocation path.
- `backend/platform/analysis/ir/__init__.py`: finalized supported exports.
- `PROJECT_CONTEXT.md`: record actual diff, verification, consumer sign-off,
  approval, and status; mark frozen only if every gate passes.

**Input/output:** supplied frozen F2 plus approved M3 configuration in; validated
F3 placed in an attempt-scoped handoff for M4.

**Dependencies:** Batches 1–2 complete; M4 consumer review of the proposed F3
contract. F3 replay ownership/invariants are fixed by this corrected plan.

**Acceptance criteria:**

1. Production registry executes M3 after the frozen M2 stages and supplies the
   validated F3 result without changing F1/F2 or stage vocabulary.
2. M3 contains no M2 producer/parser/rebuild import or call.
3. Attempt isolation, release, retry/duplicate behavior, cancellation, progress,
   partial diagnostics, and failure classification are tested at the M1-owned
   handoff boundary.
4. Lost-F3 recovery is M1-owned and replays the stateless M3 constructor with
   identical F2/configuration/M3-analyzer/IR-schema versions; it cannot reopen
   completed stages, mutate lifecycle state, or add public events.
5. M4 consumer stub uses only F3 and requires no F2/parser/M3 internals.
6. Focused M3, full Python regression, M1/M2 regressions, formatting, lint,
   typing, dependency, and diff checks pass.
7. F3 is marked frozen only after owner approval; otherwise M3 remains
   implemented but not frozen.

**Verification:**

```bash
venv/bin/python -m pytest -q tests/p3/analysis/test_m3_*.py
venv/bin/python -m pytest -q tests/p3/analysis/test_m1_*.py tests/p3/analysis/test_m2_*.py
venv/bin/python -m pytest -q
venv/bin/ruff check .
venv/bin/mypy backend
for f in $(rg --files -g '*.py'); do venv/bin/black --check --quiet "$f" || exit 1; done
venv/bin/python -m pip check
git diff --check
```

The full TestClient suite may require execution outside the managed sandbox
because that sandbox has previously denied AnyIO's AF_UNIX wakeup. Such an
environmental restriction must be reported, never represented as a pass.

**Definition of Done:** M3 is production-wired, bounded, deterministic,
regression-safe, accepted by an M4 consumer, documented, and owner-approved;
only then may F3/M3 be marked frozen and complete.

### 4.10 Consolidated file specification

| Path | State/action | Responsibility |
|---|---|---|
| `backend/platform/analysis/inspection/model.py` | Existing / reuse only | Frozen F2 root and inventory/detection input. |
| `backend/platform/analysis/syntax/model.py` | Existing / reuse only | Frozen parser-neutral facts and source coordinates. |
| `backend/platform/analysis/domain/diagnostic.py` | Existing / reuse only | Shared diagnostic contract. |
| `backend/platform/analysis/application/execution.py` | Existing / reuse only | Frozen execution context and stage result. |
| `backend/platform/analysis/application/registry.py` | Existing / reuse only | Handler registration protocol. |
| `backend/platform/analysis/inspection/handlers.py` | Existing / no M3 modification planned | M2 handoff/rebuild implementation; M1 composition accesses it, not M3. |
| `backend/platform/analysis/ir/__init__.py` | Proposed create | Minimal supported M3 exports. |
| `backend/platform/analysis/ir/model.py` | Proposed create | F3 schema, enums, keys, immutability, ordering, serialization. |
| `backend/platform/analysis/ir/service.py` | Proposed create | F2 normalization and bounded local semantic analysis. |
| `backend/platform/analysis/ir/validator.py` | Proposed create | Whole-document F3 validation. |
| `backend/platform/analysis/ir/handlers.py` | Proposed create | Thin M3 stage adapter/registration using M1-owned handoff ports; no coordinator or recovery. |
| `backend/platform/analysis/application/handoff.py` | Proposed create (M1-owned internal integration) | F2 reader and F3 reader/writer attempt-output ports/store plus M1-owned replay boundary; no F1/public contract change. |
| `backend/platform/config.py` | Existing / proposed modify | Owner-approved M3 caps only. |
| `backend/worker/tasks.py` | Existing / proposed modify | Production M1-owned composition and M3 registration. |
| `docs/architecture/contracts/f3-intermediate-representation-v1.md` | Proposed create in implementation | Normative F3 after consumer/owner approval. |
| `tests/p3/analysis/test_m3_contracts.py` | Proposed create | Schema/key/serialization/security contract tests. |
| `tests/p3/analysis/test_m3_normalization.py` | Proposed create | F2 mapping and evidence preservation. |
| `tests/p3/analysis/test_m3_benchmarks.py` | Proposed create | Cap evidence and size/memory/count measurements. |
| `tests/p3/analysis/test_m3_semantics.py` | Proposed create | Local semantics and uncertainty tests. |
| `tests/p3/analysis/test_m3_validation.py` | Proposed create | Validation/adversarial/cap tests. |
| `tests/p3/analysis/test_m3_goldens.py` | Proposed create | Canonical determinism and regression goldens. |
| `tests/p3/analysis/test_m3_integration.py` | Proposed create | Registry, lifecycle-facing behavior, handoff, recovery boundary. |
| `tests/fixtures/p3/m3/` | Proposed create | Representative mixed-language and adversarial fixtures. |

No migration, REST API, frontend, Express, package dependency, F1, or F2 file is
planned for M3.

### 4.11 Testing strategy and phase gates

- **Contract/unit:** immutable records, enum/version compatibility, canonical
  keys/JSON, metadata safety, duplicate/conflict rules.
- **Transformation:** every F2 fact family, complete/partial/failed artifacts,
  source ranges, evidence provenance, detections, manifest facts, framework
  facts, and manifest-declared-versus-source-referenced distinctions.
- **Semantics:** document-local lexical scope, containers, aliases, exports,
  local references, dynamic/ambiguous/unresolved cases, cycles, static call and
  dependency distinctions, and order independence.
- **Validation/security:** malformed graphs, dangling local references,
  unsupported versions, collision, cap failure, secret/path rejection, no
  source/network/runtime access.
- **Determinism/golden:** repeated, shuffled, and concurrency-varied runs produce
  byte-equivalent canonical F3.
- **Integration:** real handler registry and M1-owned F2/F3 handoff ports;
  attempt isolation, cancellation, progress, diagnostics, retry/duplicate
  delivery, release/replay, and M4 consumer stub.
- **Regression:** all M1/M2 and full Python tests plus Ruff, strict Mypy, Black,
  `pip check`, and `git diff --check`.

### 4.12 M3 acceptance criteria

M3 is complete only when:

1. Frozen F2 v1 is consumed without mutation or producer invocation.
2. The approved F3 schema is explicit, versioned, immutable, canonical, and
   accepted by an M4 consumer.
3. All supported F2 records are covered or explicitly represented as incomplete.
4. Source locations, analyzer provenance, evidence strength, diagnostic
   references, conflicts, and uncertainty survive normalization.
5. Exact document-local semantics are deterministic; cross-file resolution,
   cross-analyzer merging, canonical IDs, and historical continuity stay in M4.
6. No display-name merge, random/host/database identity, silent overwrite, or
   silent truncation occurs.
7. Partial inputs yield truthful completeness; systemic contract/validation/cap
   failures fail explicitly through existing lifecycle semantics.
8. Producer provenance maps only from actual F2 fields, evidence strength uses
   the defined ordering, and competing evidence is preserved.
9. Static call/dependency references never claim runtime observation, and every
   architecture-like IR record remains a non-authoritative candidate.
10. M3 uses the shared diagnostic contract and adds no competing findings/event
    vocabulary.
11. Resource caps are benchmarked and owner-approved.
12. Attempt handoff, recovery ownership, isolation, cancellation, retries, and
    duplicate delivery are verified.
13. No M2, M4, frontend, persistence, projection, or AI responsibility leaks
    into M3.
14. Focused and full regression/quality gates pass with exact results recorded.

## 5. Execution Ledger

| Module | Status | Verified evidence | Remaining |
|---|---|---|---|
| M1 | **FROZEN / COMPLETE — F1 v1.0.0** | Full closure included Python regression, PostgreSQL migrations/constraints/concurrency, RabbitMQ/Celery dispatch/retry/recovery, Ruff, Mypy, and Black. | None; versioned change control only. |
| M2 | **FROZEN / COMPLETE — F2 v1.0.0** | Focused M2: `71 passed, 3` platform-only skips. Full Python: `568 passed, 3` platform-only skips. Ruff, strict Mypy over 171 backend files, sequential full-project Black, `pip check`, and `git diff --check` passed on 2026-11-06. | None; M3 consumes supplied F2 only. |
| M3 | **DRAFT PLAN — NOT APPROVED / NOT STARTED** | Architecture, frozen contracts, M2 handoff, source models, worker registration, tests, and tooling inspected. No IR package exists. | Approve decisions below, then implement the three batches in order. |
| M4 | Planned / not started | Ownership boundary approved at phase level. | Requires frozen F3 and consumer sign-off. |
| M5 | Planned / not started | Express is frontend/platform authority. | Requires M4 result contracts. |
| M6 | Planned / not started | Existing quality tooling verified. | Requires integrated M3–M5. |

## 6. Preserved Decisions and Risks

### 6.1 Frozen M1/F1 summary

- Section 9 lifecycle is exact: `PARTIAL` is nonterminal/incomplete and
  `TIMEOUT` is persisted before failure; Analysis/Job/Stage states remain
  distinct and terminal records immutable.
- `AnalysisInput` is immutable, snapshot-bound, versioned, and uses lazy
  authorized artifact content access.
- PostgreSQL owns Python lifecycle records; Celery/RabbitMQ delivery is
  at-least-once with identifier-only payloads and duplicate-delivery guards.
- One shared `AnalysisDiagnostic` is emitted by M2–M4.
- ADR-0001 prohibits cross-database access and fixes authenticated platform/
  analysis integration.

### 6.2 Frozen M2/F2 summary

- F2 v1.0.0 contains deterministic inventory role/outcome, detections,
  parser-neutral syntax/framework/manifest facts, canonical UTF-8 ranges,
  coverage, and diagnostic references.
- Python `ast` and pinned Tree-sitter adapters run in fail-closed OS child
  isolation with bounded resources, no network, minimal environment, and no
  unnecessary inherited credentials/handles.
- Exactly one generic parse feeds framework enrichment; enrichment never
  reparses or erases generic evidence.
- Approved caps are 25,000 facts/artifact, 250,000 facts/analysis, and 50 MiB
  canonical F2; cap failures are explicit.
- F2 is attempt-scoped and non-persisted. M1 owns recovery-only rebuilding with
  identical immutable input/config/parser/analyzer versions; completed stages
  and frozen lifecycle state remain unchanged.
- M3 only consumes supplied F2 and never invokes M2.

### 6.3 Principal M3 risks and mitigations

- **Boundary ambiguity:** master Section 11 discusses IR and identity together.
  Mitigation: M3 uses snapshot-scoped IR keys/local semantics; M4 alone owns
  cross-file canonical architectural identity and model merging.
- **Handoff gap:** frozen ExecutionContext carries no arbitrary outputs.
  Mitigation: M1-owned F2-reader and F3-reader/writer ports isolate M3 from
  attempt storage/recovery; do not change F1 or expose M2 rebuild to M3.
- **IR explosion:** legal F2 may contain 250,000 facts. Mitigation: benchmark
  before approving atomic F3 caps; fail explicitly, never truncate.
- **False semantics:** dynamic languages and incomplete imports can tempt
  speculative links. Mitigation: exact document-local rules only; use explicit
  static relationship names and preserve candidates, ambiguity, and unresolved
  cross-file states for M4.
- **Nondeterminism/collision:** concurrent ordering or weak keys can alter F3.
  Mitigation: immutable analysis-scoped indexes, canonical sorting, strong
  snapshot/fact-based keys, collision tests, and byte-equivalent goldens.
- **Secret/path leakage:** generic metadata can smuggle unsafe values.
  Mitigation: allowlisted typed metadata, recursive safety validation, source
  references rather than source literals, repository-relative paths only.
- **Schema churn:** an early F3 freeze could block M4. Mitigation: M4 consumer
  review and owner approval before F3 freeze; incompatible changes are versioned.

## 7. Outstanding Approval Decisions and Current Handoff

### 7.1 Owner decisions required before implementation

1. **Approve the final F3 vocabulary:**
   - entity kinds: `repository`, `snapshot`, `artifact`, `application`,
     `module`, `symbol`, `component`, `endpoint`, `external_system`, `database`,
     `message_infrastructure`, and `configuration`;
   - relationship kinds: `contains`, `declares`, `imports`, `exports`,
     `static_call_reference`, `inherits`, `composes`, `declares_route`,
     `uses_framework`, `declares_dependency`, and
     `source_references_dependency`;
   - fact statuses: `confirmed`, `inferred`, `unresolved`, and `conflicting`,
     with the exact static-only meanings in §4.5.3;
   - evidence strengths, strongest to weakest: `direct_source`,
     `framework_structural`, `configuration`, `dependency`, `documentation`;
   - unresolved reasons: `not_found`, `ambiguous`, `dynamic`, `unsupported`,
     and `incomplete_input`;
   - record set: `IRDocument`, `IREntity`, `IRRelationship`, `IREvidence`,
     `IRUnresolvedReference`, `IRConflict`, and `IRCompleteness`;
   - `IREvidence.source_record_type` is required, while
     `IREvidence.source_fact_key` is optional and is populated only from an
     actual F2 `SyntaxFact` key. Missing producer fields are never invented.
2. **Approve the final F3 key rules:** keys are deterministic and scoped to the
   repository snapshot/analysis result; they derive only from immutable
   upstream IDs, normalized repository-relative paths, actual F2 fact keys when
   present, record kind, and required document-local disambiguators. They never
   use random UUIDs, Python `hash()`, database row IDs, absolute paths, display
   names alone, iteration order, or fabricated provenance. IR keys are
   intermediate keys, not M4 canonical logical IDs. Identical key/content
   duplicates merge ordered evidence; same-key/different-content collisions are
   preserved as conflicts or fail validation and never overwrite silently.
3. **Later cap approval:** numeric M3 limits are approved only after Batch 1
   benchmark evidence. Batch 2 is gated on that later decision.

The single canonical compatibility version is already reconciled to frozen
`IR_SCHEMA_VERSION = "1.0.0"`; no separate `f3_version` decision remains.

Recovery ownership is no longer unresolved: M1 owns F2/F3 handoff recovery and
M3 replay; M3 owns only deterministic construction/validation/result production;
M4 only consumes F3. The internal port/store placement is an implementation
detail constrained by that approved ownership, not a new owner decision.

The proposed F3 contract is not frozen until Batch 3 M4 consumer review and
explicit owner approval.

### 7.2 Current handoff

- Current module: M3 planning.
- Status: complete draft plan, not approved, implementation not started.
- Frozen dependencies: M1/F1 v1.0.0 and M2/F2 v1.0.0 remain unchanged.
- Existing dirty M2 worktree changes are preserved.
- No application source, dependency, test, contract, ADR, or `master.txt`
  file was changed by this planning task.
- Recommended next action: owner explicitly approves or revises the final F3
  vocabulary and key rules above. Only after that approval should a separate
  implementation task begin Batch 1; numeric caps remain a Batch 1 exit gate.
