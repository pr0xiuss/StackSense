# PROJECT_CONTEXT.md — StackSense Engineering Context

> Repository handoff maintained through the planning and implementing skills.
> Last updated: 2026-11-05 on branch `feature_mannan`.

---

## 1. Project Overview

StackSense is a software repository intelligence and architecture analysis platform. The current milestone is **Phase 3: Analysis Engine & Architecture Model**. Phase 3 builds the deterministic Python analysis core on top of immutable repository revisions and artifacts delivered by Phase 2. Express remains the platform authority and delegates authenticated analysis operations to Python through a trusted service-to-service boundary; Python remains the analysis authority.

### 1.1 Authoritative sources

- `master.txt` §0: superseding Project-first hierarchy and security boundary.
- `master.txt` §§5–7: supported languages/frameworks, repository snapshots, artifact policy, safety, and resource limits.
- `master.txt` §§8–12: system boundaries, analysis/job lifecycle, analysis engine, IR/identity system, and canonical Architecture Model.
- `master.txt` §25.13: Phase 3 roadmap responsibilities and vertical slice.
- `master.txt` Appendices D, E, G, I, and K: events, API conventions, artifact classification, failure taxonomy, and architecture-change control.
- Existing Python implementation under `backend/` and tests under `tests/` are the concrete Phase 1/2 conventions to extend.
- Express/MongoDB under `express/` is the completed MERN Phase 2 platform implementation. Phase 3 backend work must not be added there.

### 1.2 Verified repository state

- The active branch is `feature_mannan`; the working tree contains the reviewed M1 closure changes recorded in §5.
- Python uses FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, repository interfaces, dependency injection, immutable domain dataclasses, and structured `StackSenseError` responses.
- Express/MongoDB owns immutable repository revisions, artifact metadata, and artifact storage access. Production M1 consumes only the authenticated manifest/content API in ADR-0001; the retained Python Phase 2 implementation is reference/regression code, not the production platform-data authority.
- Phase 3 M1 now provides the Analysis domain, lifecycle persistence, internal REST/SSE API, Celery/RabbitMQ worker wiring, orchestration, and recovery. M2 parsing, M3 IR, and M4 Architecture Model implementation remain absent.
- `requirements.txt` includes the Celery/RabbitMQ client stack and `infra/docker/compose.yml` includes RabbitMQ. The M2 plan approves exact Tree-sitter bindings, but they are not yet declared or installed because implementation has not started.
- The React frontend has a repository detail route with ingestion, revisions, and artifacts. It currently proxies all `/api` traffic to Express on port 5000.
- Python and Express use intentionally separate persistence systems. ADR-0001 freezes the two-way authenticated API boundary and forbids synchronization or cross-database access.
- Verified existing Python extension points include `backend/platform/config.py`, `backend/platform/errors.py`, `backend/platform/dependency_injection.py`, `backend/api/v1/router.py`, `backend/api/error_handlers.py`, `backend/infra/migrations/env.py`, and the Phase 2 capability packages under `backend/platform/`.
- `backend/platform/analysis/`, `backend/worker/`, and `tests/p3/analysis/` are verified existing M1 implementation paths. Empty top-level placeholders such as `backend/analysis/`, `backend/application/`, and `backend/domain/` are not treated as implemented Phase 3 architecture.
- Historical pre-M1 baseline evidence retained for context (current closure evidence is in §5 and §7.4):
  - `python -m pytest --collect-only -q` collected 330 Python tests.
  - `cd frontend && npm test` passed all four configured scripts.
  - `cd frontend && npm run build` passed with 63 transformed modules.
  - An accidental root-level `npm test` failed because the repository root intentionally has no `package.json`; the correct frontend command above passed.

---

## 2. Global Constraints and Approved Architecture

1. **Project-first isolation:** `User -> Project -> Repository`. No Organization entity or organization-scoped authorization may be introduced. Analysis, jobs, results, architecture versions, events, and findings must carry and enforce `project_id`.
2. **Python-only Phase 3 backend:** Modules 1–4 remain under `backend/`. Express may implement only the approved internal transport/proxy adapters; no analysis domain, lifecycle persistence, jobs, or analyzers belong there.
3. **Phase 2 boundary:** An Express-owned `RepositoryRevision` is the immutable snapshot identity. Express supplies verified manifests and bounded artifact content through ADR-0001 APIs. Phase 3 does not clone repositories, extract uploads, rewrite artifacts, or read MongoDB directly.
4. **Static, untrusted-source analysis:** Normal analysis must not execute repository code, installation scripts, build scripts, or unrestricted network requests. All paths remain repository-relative and storage reads remain sandboxed.
5. **Deterministic source of truth:** Deterministic analyzers produce IR; validated IR produces the Architecture Model. AI, frontend state, diagrams, search, and graphs cannot create canonical architecture facts.
6. **IR and Architecture Model are separate:** Parser-specific syntax never leaks into the canonical model. IR can reference shared diagnostics and contain lower-level semantic facts; only validated, identity-resolved architectural concepts enter a published Architecture Version.
7. **Identity:** Persistence IDs remain RFC 4122 UUID v4. Stable logical IDs are separate deterministic strings. Display names, absolute paths, parser order, UI IDs, and AI output never define identity.
8. **Versioning and reproducibility:** Every analysis records the revision/snapshot, effective configuration, analyzer version, IR schema version, and Architecture schema version. Equivalent inputs must produce semantically equivalent serialized results.
9. **Durable lifecycle:** PostgreSQL is authoritative analysis/job state; RabbitMQ transports work; Celery executes it. Celery result state and queue messages are not domain truth.
10. **REST/SSE boundary:** REST returns authoritative state. SSE only notifies progress and supports reconnect/reconciliation using durable event sequence IDs.
11. **Atomic publication:** Draft Architecture Models remain internal. A version becomes visible only after IR, identity, model, schema, and referential validation succeed in one publication transaction. Published versions are immutable.
12. **Evidence and uncertainty:** Entities, relationships, and findings preserve source provenance and deterministic evidence strength. Unresolved, ambiguous, and conflicting facts remain explicit; they are not guessed away.
13. **Security:** Express-owned user authentication and Project RBAC remain platform-authoritative. Python's internal analysis APIs additionally require the owner-approved service credential and delegated actor/Project context defined by the integration ADR. Every boundary must reject cross-project identifier substitution, redact secrets, avoid returning raw source by default, and bound pagination/resource use.
14. **Structured errors:** Phase 3 extends the existing `{ "error": { "code", "message", "details" } }` contract and existing FastAPI error mapping.
15. **Deferred responsibilities:** Neo4j projection, Elasticsearch, knowledge/RAG, AI explanation, reports, and the full React Flow + ELK Diagram Engine belong to later phases. Phase 3 may expose a basic read-only architecture explorer, but must not implement those later systems.
16. **Approved platform/analysis split:** Express is the platform authority for authentication, users, Projects, Project membership/RBAC, and repository registration. The frontend communicates through Express. Python is the authority for analysis lifecycle/execution, repository inspection, IR, identity resolution, and Architecture Model construction. Express delegates analysis operations to Python through a trusted service-to-service boundary.
17. **Integration ADR accepted:** `docs/architecture/adr/0001-express-python-integration.md` is authoritative. Separate service credentials protect both directions; resource chains are verified by Express; Python stores opaque platform UUIDs without cross-database foreign keys; no synchronization or direct database access is permitted.
18. **Project-first conflict rule:** `master.txt` §0 and the current code establish `User -> Project -> Repository`, with no Organization domain. Any remaining Organization wording is historical unless an approved ACR/ADR explicitly restores it.
19. **Change control:** Material deviations from `master.txt`, the Phase 3 contracts below, or the approved Express/Python authority split require explicit approval/ACR treatment before implementation.

---

## 3. Phase Index

| Phase | Status | Concise retained context |
|---|---|---|
| Phase 1 — Engineering Foundation | Completed | Python/FastAPI bootstrap, PostgreSQL/Alembic, DI, error/logging foundation, CI, Black/Ruff/Mypy/Pytest, and React foundation. |
| Phase 2 — Project & Repository Platform (Python) | Completed | Identity/JWT, Project-scoped RBAC, projects, repositories, ingestion, immutable revisions/artifacts, safe acquisition, classification, and storage abstraction. This is Phase 3's backend input contract. |
| Phase 2 — MERN migration | Completed, retained separately | Express/MongoDB platform and the current React integration satisfy the college MERN requirement. It is not the Phase 3 implementation target. Verified historical work includes active-user auth, refresh rotation, RBAC, repository ingestion, username collaborator lookup, self-management prevention, and frontend API coverage. |
| **Phase 3 — Analysis Engine & Architecture Model** | **In progress; M1 FROZEN and COMPLETE; M2 Batches 1 & 2 Complete & Verified** | Six-module plan in §4. F1 v1.0.0 and ADR-0001 are frozen; all M1 closure gates passed. M2 Batches 1 & 2 complete & verified; M3–M6 remain planned. |
| Phase 4 — Architecture Graph & Exploration | Upcoming | Projects published Architecture Versions into Neo4j and adds graph traversal/exploration. Depends on stable Phase 3 identity and model contracts. |
| Phase 5 — Knowledge, Search & Diagram Intelligence | Upcoming | Elasticsearch/retrieval and the canonical Diagram Specification + ELK + React Flow pipeline. Depends on published Architecture Versions and graph projection. |
| Phase 6 — AI Architecture Intelligence | Upcoming | Evidence-grounded explanation behind provider abstractions; never replaces deterministic findings. |
| Phase 7 — Product & Hardening | Upcoming | Production UX, observability, deployment, scale, security, and final evaluation hardening. |

---

## 4. Current Phase Plan — Phase 3

### 4.1 Objectives

Phase 3 accepts a specific immutable repository revision, executes a durable asynchronous deterministic analysis, extracts supported source structures, normalizes them into versioned IR, resolves stable identities, publishes a validated Architecture Version with evidence-backed findings, and exposes status/results to the frontend.

The Phase 3 vertical slice is:

```text
Authenticated user
  -> POST /api/v1/analyses (project/repository/revision)
  -> PostgreSQL Analysis + Job
  -> RabbitMQ
  -> Celery worker
  -> AnalysisInput from Phase 2 artifacts/storage
  -> inventory/detection/parsers/analyzers
  -> validated IR
  -> identity resolution
  -> validated Architecture Model
  -> atomic Architecture Version publication
  -> REST state/results + SSE notifications
  -> frontend analysis status, findings, and basic architecture explorer
```

### 4.2 Explicit non-goals

- No Express Phase 3 implementation or MongoDB analysis persistence.
- No new repository acquisition, upload, archive extraction, or ingestion contract.
- No repository code execution, dependency installation, dynamic runtime introspection, or unrestricted network access.
- No Neo4j/Elasticsearch projection, RAG, LLM analysis, recommendations, report generation, or canonical diagram generation.
- No architecture comparison/rename tracking beyond stable logical identities needed for future versions.
- No user-editable architecture facts. Phase 3 results are deterministic and immutable once published.
- No arbitrary source browser returning entire files; evidence responses expose bounded metadata/snippets only if separately security-approved.

### 4.3 Existing implementation assessment

The Python platform already provides the layering Phase 3 should follow:

```text
FastAPI DTO/router
  -> application service + ProjectAuthorization
  -> abstract repository/storage/queue contracts
  -> immutable domain objects
  -> SQLAlchemy/local storage/Celery adapters
```

Reusable boundaries:

- `ProjectAuthorization.require_access` for read APIs and `require_create_access` for starting/cancelling analysis.
- `PlatformRepositoryGateway` for authenticated Express manifest and bounded content access; production M1 does not compose Python Phase 2 repositories/storage.
- `backend.platform.config.Settings`, `backend.platform.errors`, and API exception mapping.
- `Base` and Alembic conventions for PostgreSQL persistence.
- `apiClient` and existing frontend repository route/components.

Gaps to close:

- no AnalysisInput contract or revision-to-analysis adapter;
- no analysis/job/stage/event persistence or state machine;
- no RabbitMQ/Celery dependencies or worker bootstrap;
- no scanner/detectors/parser adapters/analyzers;
- no IR, identity registry, Architecture Model, or publication repository;
- no analysis REST/SSE API;
- no frontend analysis service/pages/components;
- no Phase 3 fixtures, golden outputs, E2E, determinism, or performance checks.

### 4.4 Shared contracts

#### 4.4.1 `AnalysisInput`

Proposed immutable application boundary:

```text
AnalysisInput
  analysis_id: UUID v4
  project_id: UUID v4
  repository_id: UUID v4
  snapshot_id: UUID v4           # RepositoryRevision.id
  revision_identifier: str
  source_hash: str
  artifacts: tuple[AnalysisArtifact, ...]  # sorted by normalized path
  effective_configuration: AnalysisConfiguration
  analyzer_version: str
  ir_schema_version: str
  architecture_schema_version: str
  content_reader: ArtifactContentReader   # lazy, bounded platform API adapter
```

`AnalysisArtifact` carries artifact ID, revision ID, normalized repository-relative path, content hash, size, and Phase 2 category/support level. Storage keys and absolute paths are excluded. The production factory verifies the complete Express-owned resource chain and manifest totals, sorts deterministically, and reads content lazily through the authenticated bounded API.

#### 4.4.2 Lifecycle and execution contract

- The Analysis state vocabulary is the Section 9 vocabulary: `CREATED`, `QUEUED`, `RUNNING`, `PARTIAL`, `COMPLETED`, `COMPLETED_WITH_WARNINGS`, `FAILED`, `CANCEL_REQUESTED`, and `CANCELLED`, with `TIMEOUT` preserved as the explicit timeout transition shown in §9.7/§9.38.
- Approved golden paths are `CREATED -> QUEUED -> RUNNING -> COMPLETED`, `CREATED -> FAILED`, `QUEUED -> CANCELLED`, `RUNNING -> CANCEL_REQUESTED -> CANCELLED`, `RUNNING -> TIMEOUT -> FAILED`, and `RUNNING -> PARTIAL -> COMPLETED_WITH_WARNINGS`. Additional transitions must be justified against Section 9 and added to the frozen transition matrix before implementation.
- `PARTIAL` means a usable but incomplete result exists. It is not listed as a primary terminal state in §9.9 and must never be presented as complete. The persisted completeness record must say what was analyzed, failed, unsupported, excluded, and potentially incomplete. Finalization may reach `COMPLETED_WITH_WARNINGS` only when the Architecture Model is valid; otherwise the analysis reaches `FAILED`.
- `TIMEOUT` is not a successful or terminal result. It records the explicit timeout step required by §9.7/§9.38 and must deterministically finalize as `FAILED`, retaining timeout category, stage, configured limit, and safe diagnostic metadata.
- Primary terminal states remain exactly `COMPLETED`, `COMPLETED_WITH_WARNINGS`, `FAILED`, and `CANCELLED`. They cannot silently return to `RUNNING`.
- Frozen Job states are `PENDING`, `QUEUED`, `RUNNING`, `RETRYING`, `COMPLETED`, `FAILED`, and `CANCELLED`; they remain execution detail and never replace Analysis states.
- Frozen Stage states are `PENDING`, `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `SKIPPED`, and `CANCELLED`. `QUEUED`/`CANCELLED` preserve the Appendix C execution detail while Section 9 remains authoritative for Analysis lifecycle semantics.
- Mandatory stages: input validation, inventory, language/framework detection, syntax extraction for eligible supported source, IR normalization/validation, identity resolution, architecture build/validation/publication.
- Optional/degradable stages: unsupported artifact analysis and framework enrichment when generic analysis succeeds. Failure becomes a diagnostic/warning, never fabricated output.
- State transitions use repository methods with expected-current-state predicates to prevent stale workers and duplicate messages from regressing state.
- The initial MVP uses one orchestration Celery task per analysis while persisting individual stage states. This keeps IR analysis-local/in-memory and preserves the future ability to split stages into jobs.
- Retry ownership belongs to Celery for declared transient infrastructure failures only. Domain/validation/parser failures are classified in the analysis state and are not blindly retried.
- Queue messages contain identifiers and routing/version metadata only: `analysis_id`, `job_id`, task type, contract version, and an approved correlation identifier. Workers reload all authoritative state; messages never carry source, artifact catalogs, credentials, or full configuration.
- Cancellation is cooperative at stage and batch boundaries. A published Architecture Version is never rolled back by a late cancellation race.
- Durable `AnalysisEvent` rows use monotonically increasing per-analysis sequence numbers for SSE replay/reconciliation.

#### 4.4.3 Shared finding/diagnostic contract

- Phase 3 has one cross-module immutable `AnalysisDiagnostic` contract, owned and versioned by M1. It carries diagnostic ID, analysis/stage, code, category, severity, safe message/details, status, evidence references, affected artifact/entity logical IDs where known, and timestamps.
- M2 emits parser/detection diagnostics, M3 emits normalization/resolution/IR-validation diagnostics, and M4 emits identity/model/publication diagnostics using this same contract. These modules must not define competing parser, IR, finding, or architecture diagnostic domain types.
- M1 owns lifecycle-safe recording of diagnostics so failures before Architecture publication remain observable. M4 owns the result-query service/API that filters and presents those records as findings; a “finding” response is a DTO projection of `AnalysisDiagnostic`, not a second domain contract.
- Diagnostic evidence references use stable repository-relative artifact identity and bounded source ranges. They never contain storage keys, absolute paths, secrets, raw tracebacks, or unrestricted source content.

#### 4.4.4 Version and identity contract

- Initial constants are named, not inferred: `ANALYZER_VERSION`, `IR_SCHEMA_VERSION`, and `ARCHITECTURE_SCHEMA_VERSION`. Their initial values require approval before implementation.
- Artifact identity = snapshot ID + normalized relative path.
- Symbol identity includes snapshot, module/artifact, qualified symbol name, and symbol kind; source location disambiguates only where language semantics require it.
- Architecture logical identity is project/repository scoped and excludes snapshot for concepts intended to match across versions; evidence remains snapshot-specific.
- Persistence IDs are UUID v4. Logical identities are separately unique and deterministic.
- Relationship logical identity = source logical ID + semantic relationship type + target logical ID (or deterministic unresolved-target key).
- Same logical identity merges evidence; same display name alone never merges entities. Irreconcilable collisions produce an explicit finding and fail the affected publication if uniqueness cannot be preserved.

#### 4.4.5 Proposed REST and SSE contract

These are conceptual internal Python FastAPI `/api/v1` routes. They are top-level Analysis resources as permitted by `master.txt` Appendix E, but Express remains the user-facing platform boundary. Express authenticates the user and enforces platform RBAC, then calls Python using the integration-ADR-approved service credential and delegated actor/role/Project context. Python independently validates the delegated context and supplied resource chain; it must not accept a browser token or trust resource IDs without that contract.

| Method and internal route | Purpose | Delegated authorization / behavior |
|---|---|---|
| `POST /analyses` | Create and enqueue an analysis for `project_id`, `repository_id`, `revision_id`, optional configuration/idempotency key. | Delegated Developer/Admin/Owner; return `202` with authoritative Analysis representation. |
| `GET /analyses` | Paginated history filtered by project/repository/revision/status. | Delegated Project member; mandatory Project scope; bounded `limit/offset`. |
| `GET /analyses/{analysis_id}` | Authoritative lifecycle, stages, progress, warnings, errors, and result version ID. | Delegated member of the owning Project. |
| `POST /analyses/{analysis_id}/cancel` | Request cooperative cancellation. | Delegated Developer/Admin/Owner; `409` for invalid/terminal transitions. |
| `GET /analyses/{analysis_id}/events` | SSE notification/replay stream. | Delegated Project member; supports `Last-Event-ID`, heartbeat, and REST reconciliation through the approved Express relay. |
| `GET /analyses/{analysis_id}/findings` | Paginated deterministic findings/diagnostics. | Delegated Project member; filters by category/severity/status. |
| `GET /analyses/{analysis_id}/architecture` | Published Architecture Version summary and completeness. | Delegated Project member; `409 result_not_ready` until published. |
| `GET /analyses/{analysis_id}/architecture/entities` | Paginated/filterable entities for exploration. | Delegated Project member; bounded filters for type/application/module. |
| `GET /analyses/{analysis_id}/architecture/entities/{entity_id}` | Entity metadata, hierarchy, relationships, and evidence references. | Delegated Project member; enforce Analysis/Version/Project ownership. |
| `GET /analyses/{analysis_id}/architecture/relationships` | Paginated relationships/unresolved relationships. | Delegated Project member; source/target/type filters. |

Ownership is explicit: M1 owns `POST /analyses`, lifecycle history/detail, cancellation, and event streaming. M4 owns findings and all Architecture result-query endpoints. M1 may include only the published Architecture Version ID/readiness flag in lifecycle state; it does not persist or query Architecture entities, relationships, or evidence.

DTOs must remain separate from domain types. Public responses expose UUID IDs, versions, timestamps, state, counts, safe metadata, and evidence references; they do not expose storage keys, absolute paths, raw secret values, queue payloads, or internal tracebacks.

Phase 3 error codes include at minimum: `analysis_not_found`, `analysis_state_conflict`, `analysis_already_exists`, `analysis_input_invalid`, `analysis_queue_unavailable`, `analysis_cancel_not_allowed`, `analysis_failed`, `architecture_not_ready`, `architecture_validation_failed`, `artifact_content_unavailable`, `parser_unavailable`, and `resource_limit_exceeded`.

### 4.5 Module dependency graph and sequence

```text
M1 contracts/lifecycle/AnalysisInput/API/worker skeleton
  -> M2 inventory/detection/parsers/source extraction
      -> M3 IR/semantic resolution/evidence/validation
          -> M4 identity + Architecture Model + publication/query APIs
              -> M5 frontend status/results/explorer
                  -> M6 complete integration/evaluation
```

#### Contract freeze points

| Freeze | Owner and consumers | Contract to freeze | Approval prerequisites | Parallel work unlocked |
|---|---|---|---|---|
| **F1 — M1 -> M2 execution/input boundary (FROZEN v1.0.0)** | M1 owns; M2 consumes | `AnalysisInput`, `AnalysisArtifact`, bounded `ArtifactContentReader`, effective configuration/resource limits, stage reporting, `AnalysisDiagnostic`, cancellation checkpoint, deterministic artifact ordering, and identifier-only queue payload. | Approved and recorded in `docs/architecture/contracts/f1-analysis-execution-input-v1.md`; Section 9 `PARTIAL`/`TIMEOUT`, Job/Stage states, revision-as-snapshot, diagnostic ownership, and ADR-0001 source access are fixed. | M2 may begin against v1.0.0; incompatible changes require contract versioning and approval. |
| **F2 — M2 -> M3 syntax/evidence boundary (design baseline approved)** | M2 owns production/rebuild; M3 only consumes and signs off; M1 orchestration owns recovery-only rebuilding | `RepositoryInspectionResult`, separate artifact role/outcome, `SyntaxDocument`, tagged declarations/imports/exports/references/framework facts, canonical UTF-8 source ranges, detection/enrichment evidence, safe manifest facts, deterministic ordering, and parser failure references to `AnalysisDiagnostic`. | F1 remains frozen; parser packages and recovery invariants are approved; role/outcome, encoding/range, sensitive-literal, one-pass parsing, benchmarked-cap, and recovery contracts are reviewed; fixtures cover Python/JS/TS/JSX/TSX and approved frameworks. | M2 Batch 1 may implement the approved design under a separate implementation task. M3 receives an immutable supplied F2 result, never invokes M2, and cannot merge until the implemented F2 contract tests and consumer review pass. |
| **F3 — M3 -> M4 IR boundary** | M3 owns; M4 consumes and signs off | `IRDocument` v1, entity/relationship kinds, stable IR keys, unresolved/conflicting facts, completeness, evidence/provenance, canonical serialization, diagnostic mapping. | F2 frozen; IR schema/version approved; logical-ID input semantics and architectural promotion rules reviewed; invalid/unresolved behavior and golden IR accepted. | M4 persistence schema and repository contract tests may proceed against frozen fixtures; builder, identity resolution, validation, and publication integrate only after F3 acceptance. |

Contract changes after a freeze require the owning module to version the contract, update consumer fixtures/goldens, document migration impact, and obtain the same reviewers' approval. A downstream module must not silently reinterpret an upstream contract.

Safe parallel work after contracts freeze:

- M1 persistence/queue infrastructure can proceed alongside the M2 parser-compatibility spike.
- M2 generic language adapters can be split by Python and JS/TS; framework analyzers can be split only after syntax/evidence contracts are frozen.
- M3 IR schema tests and M4 persistence model design can proceed in parallel after F3 fixtures are approved, but M4 builder implementation waits for the accepted IR boundary.
- M5 can build against frozen DTO fixtures after the Express/Python integration and API decisions, without waiting for the worker engine to be complete.
- M6 golden fixtures and deterministic expected outputs should be authored alongside Modules 2–4, not postponed to the end.

Do not parallelize edits to schema/version/identity contracts without a single owner; those are cross-module freeze points.

---

### 4.6 Module 1 — Analysis Foundation & Execution Infrastructure

#### Responsibilities

1. Define immutable AnalysisInput, analysis, job, stage, event, configuration, and shared `AnalysisDiagnostic` contracts.
2. Add PostgreSQL models/repositories and an Alembic migration only for authoritative analysis/job/stage/event lifecycle state and lifecycle-safe diagnostic recording.
3. Build AnalysisInput from an authorized Phase 2 revision/artifact set and lazy storage reader.
4. Implement explicit state transitions, progress, idempotency, retries, cancellation, timeout metadata, and failure classification.
5. Add RabbitMQ transport and Celery worker adapters without using Celery results as truth.
6. Add lifecycle-only create/list/get/cancel/events APIs, configuration, DI, structured errors, logging context, and version constants. Architecture persistence, publication, findings queries, and result-query APIs belong exclusively to M4.

#### Key behavior

- Creation validates the ADR-defined delegated actor/Project context, repository/revision mapping, and immutable/complete snapshot before one transaction creates Analysis, initial Job, and Stage rows.
- An optional idempotency key is unique per project/user/operation; replay returns the existing analysis rather than duplicate work.
- Queue dispatch occurs after the lifecycle transaction. Dispatch failure is persisted and recoverable; no orphan queue task may exist without database state.
- Worker acquisition performs conditional `QUEUED -> RUNNING`; duplicate/stale tasks safely return.
- Stage progress uses real counts where measurable and stage labels otherwise; no fabricated percentage.
- Events are appended only after corresponding state changes and contain no source/secrets.

#### Tests

- the complete Section 9 transition matrix, including `PARTIAL`, `TIMEOUT -> FAILED`, invalid transitions, terminal immutability, and cancellation races;
- AnalysisInput chain validation, deterministic ordering, lazy bounded reads, missing/tampered artifact failures;
- repository concurrency/conditional updates, idempotency uniqueness, event sequence, project isolation;
- queue publish failure/recovery, duplicate task, retryable vs non-retryable failure, worker crash recovery metadata;
- API auth/RBAC, validation, pagination, 202 semantics, cancel conflicts, SSE replay/reconnect and REST reconciliation.

#### Acceptance criteria

- A valid Express-owned immutable revision can create one durable queued analysis and job.
- A duplicate delivery cannot execute/publish the same stage twice.
- PostgreSQL alone can reconstruct lifecycle state after API/worker restart.
- Cross-project access is rejected for every M1 lifecycle surface.
- Cancellation, retry, error, and progress behavior is explicit and test-covered.

#### 4.6.1 Verified M1 repository and architecture findings

- Existing Python extension points are `backend/platform/config.py`, `backend/platform/dependency_injection.py`, `backend/platform/errors.py`, `backend/api/v1/router.py`, `backend/api/error_handlers.py`, `backend/infra/migrations/env.py`, the shared SQLAlchemy `Base`, and the established domain/application/repository/infra layering under `backend/platform/`.
- Express revision/artifact documents are the platform authority. The authenticated manifest returns IDs, ownership chain, revision identifier, source hash, totals, relative path, size, content hash, category, and support level; it strips storage keys.
- `PlatformRepositoryGateway` is the only production M1 source adapter. It retrieves manifests and bounded content through Express and never copies, mutates, synchronizes, or directly queries platform persistence.
- M1 implementation now exists under `backend/platform/analysis/`, `backend/worker/`, and `tests/p3/analysis/`; Celery/RabbitMQ, lifecycle tables, internal analysis APIs, and SSE are implemented and frozen. The remainder of this M1 subsection is retained as the approved historical batch plan and is superseded by the verified ledger for current status.
- ADR-0001 now records the accepted Express/Python integration and database-ownership decision.
- Express and Python maintain separate persistence. ADR-0001 now defines which immutable Express snapshot Python reads, authenticated resource mapping/content access, and the no-synchronization/no-cross-database rule.
- `master.txt` §9 and the explicit M1 requirements govern the Analysis vocabulary. Appendix C contains an older conflicting Analysis vocabulary and a different Stage vocabulary; the unresolved Stage conflict is an F1 owner decision.

#### 4.6.2 M1 exact boundary

M1 owns AnalysisInput, Analysis/Job/Stage/Event lifecycle contracts, shared diagnostics, lifecycle persistence, creation/status/history/cancellation operations, execution orchestration, queue/worker integration, timeout/retry/heartbeat/orphan recovery, configuration/version metadata, and lifecycle REST/SSE interfaces behind the approved service boundary.

M1 does not own file discovery/parsing/language detection (M2), IR (M3), identity or Architecture persistence/publication/results (M4), frontend work (M5), Express application implementation, or later graph/search/RAG/AI/report/diagram capabilities.

M2–M4 may report progress, diagnostics, cancellation checkpoints, and stage outcomes only through M1 ports. They must not mutate lifecycle repositories directly or invent lifecycle states.

#### 4.6.3 Canonical lifecycle requiring F1 approval

The Section 9 paths to freeze are:

```text
CREATED -> QUEUED -> RUNNING -> COMPLETED
CREATED -> FAILED
QUEUED -> CANCELLED
RUNNING -> CANCEL_REQUESTED -> CANCELLED
RUNNING -> TIMEOUT -> FAILED
RUNNING -> PARTIAL -> COMPLETED_WITH_WARNINGS
RUNNING -> FAILED
```

Primary terminal states remain `COMPLETED`, `COMPLETED_WITH_WARNINGS`, `FAILED`, and `CANCELLED`. `PARTIAL` is usable but explicitly incomplete and is not listed as a primary terminal state. `TIMEOUT` cannot be successful; whether it is a persisted transient status or a transition-history/failure-classification step is unresolved because §9.7/§9.38 show it in the path while §9.8 omits it from the state list.

Invalid transitions include any terminal state returning to `QUEUED`/`RUNNING`, cancellation becoming completion, and stale/concurrent writes that do not match the expected state/version. Additional transitions such as `QUEUED -> FAILED`, cancellation from `PARTIAL`, or retry from a terminal Analysis must not be introduced without F1 approval.

Section 9 lists Stage states `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, and `SKIPPED`; Appendix C also adds `QUEUED` and `CANCELLED`. The implementation must not freeze a Stage enum until the owner resolves this conflict. Job states are likewise an M1 proposal requiring approval and must remain distinct from Analysis state.

#### 4.6.4 M1 dependency and batch sequence

```text
Owner decisions + integration ADR
  -> Batch 1: domain, AnalysisInput, F1 contracts
      -> F1 frozen
          -> Batch 2: PostgreSQL lifecycle persistence/services
              -> migration/concurrency contract verified
                  -> Batch 3: RabbitMQ/Celery orchestration, internal API/SSE
                      -> M1 complete and M2 handoff available
```

M1 is divided into exactly three sequential implementation batches. Batch 2 may not begin before F1 is approved. Batch 3 may not expose or authenticate internal APIs before the integration ADR is approved.

#### 4.6.5 Batch 1 — Analysis Domain & Input Foundation

**Objective:** establish pure-Python contracts for the complete M1 implementation and the M2 handoff, then freeze F1 before persistence or worker code is added.

**Responsibilities:**

1. Freeze Analysis/Job/Stage vocabularies and the transition matrix.
2. Define immutable Analysis, Job, Stage, Event, configuration/version, completeness/progress, and shared `AnalysisDiagnostic` contracts.
3. Define immutable `AnalysisInput`, `AnalysisArtifact`, `ArtifactCatalog`, and `ArtifactContentReader` boundaries.
4. Implement a read-only Phase 2 adapter validating Project/Repository/Revision/Artifact identity and lazy storage access.
5. Define repository ports and `AnalysisStageHandler`/`ExecutionContext`/`StageExecutionResult` contracts without implementing M2–M4.
6. Add absolute-import, pure-domain, ownership, transition, input, and shared-contract tests.

**Proposed AnalysisInput contract:**

```text
analysis_id
project_id
repository_id
revision_id
revision_identifier
source_hash
total_files
total_bytes
effective_configuration
analyzer_version
artifact_catalog
content_reader
```

`AnalysisArtifact` exposes artifact ID, revision ID, relative path, size, content hash, category, and support level. `storage_key` stays adapter-internal. Input construction validates the ownership chain, deterministic path ordering, bounded paging, total metadata consistency, safe relative paths, and accessibility without eagerly loading all content.

**Single shared diagnostic contract:**

`AnalysisDiagnostic` carries diagnostic ID, Analysis/Job/Stage correlation, stable code, Appendix I category/scope/severity/retryability, safe message/details, optional artifact reference, source/cause reference when safe, and timestamp. It is bounded/aggregatable to prevent diagnostic floods. M2–M4 use this contract rather than defining parser-, IR-, or Architecture-specific diagnostic domains.

**Files:**

| Path | Action/status | Responsibility and dependencies |
|---|---|---|
| `backend/platform/analysis/__init__.py` | Create, proposed | Capability package and approved contract-version exports. |
| `backend/platform/analysis/domain/constants.py` | Create, proposed | Frozen Analysis/Job/Stage, diagnostic, retryability, and stage-requirement enums. |
| `backend/platform/analysis/domain/analysis.py` | Create, proposed | Immutable Analysis/configuration/progress/completeness and transition rules. Pure Python. |
| `backend/platform/analysis/domain/job.py` | Create, proposed | Immutable AnalysisJob/AnalysisStage, attempts, heartbeat, cancellation metadata. |
| `backend/platform/analysis/domain/input.py` | Create, proposed | AnalysisInput, AnalysisArtifact, ArtifactCatalog, ArtifactContentReader. |
| `backend/platform/analysis/domain/diagnostic.py` | Create, proposed | One M1-owned cross-module diagnostic contract. |
| `backend/platform/analysis/domain/event.py` | Create, proposed | Durable lifecycle event semantics and safe payload contract. |
| `backend/platform/analysis/application/input_factory.py` | Create, proposed | Phase 2 repositories/storage -> validated read-only AnalysisInput. |
| `backend/platform/analysis/application/execution.py` | Create, proposed | Stage handler/context/result, progress, diagnostic, event, and cancellation ports. |
| `backend/platform/analysis/repositories/{analysis_repo,job_repo,event_repo,diagnostic_repo}.py` | Create, proposed | Abstract persistence contracts consumed by application services, implemented in Batch 2. |
| `backend/platform/errors.py` | Modify, verified existing | Add M1 input/state/integrity/configuration exceptions using the canonical taxonomy. |
| `tests/p3/analysis/test_m1_domain.py` | Create, proposed | Lifecycle and immutable-domain tests. |
| `tests/p3/analysis/test_m1_input.py` | Create, proposed | Phase 2 chain, paging, lazy content, missing/tampered input tests. |
| `tests/p3/analysis/test_m1_contracts.py` | Create, proposed | Execution/event/diagnostic/F1 contract tests. |
| `tests/p3/analysis/test_m1_architecture.py` | Create, proposed | Absolute imports, pure domain, and no M2–M4 ownership leakage. |

**Error behavior:** missing revision is a Repository/Input failure; ownership-chain mismatch is Integrity/Security; unavailable content is Artifact/Storage; invalid configuration is Configuration; invalid transition is Conflict/Integrity; unsupported downstream capability is `UNSUPPORTED_CAPABILITY`, not an internal error.

**Acceptance criteria:** F1 is owner-approved; domain/input/contract tests pass; input construction is lazy and immutable; storage keys do not cross into M2; fake M2 handlers compile against only the frozen execution contract; domain code imports no FastAPI/Pydantic/SQLAlchemy/Celery/M2–M4.

**Exact order:** resolve F1 decisions; add architecture tests; implement constants/transition matrix; implement Analysis/Job/Stage; implement diagnostics/events; implement AnalysisInput; implement Phase 2 adapter; implement ports; add tests; run Black/Ruff/Mypy/targeted Pytest; record F1 freeze.

**Handoff to Batch 2:** frozen domain objects, state machine, AnalysisInput, diagnostic/event contracts, execution ports, repository interfaces, and persistence invariants.

#### 4.6.6 Batch 2 — Persistence & Lifecycle Infrastructure

**Objective:** make PostgreSQL authoritative for M1 lifecycle state and expose transactional lifecycle application services without adding RabbitMQ/Celery yet.

**Responsibilities:**

1. Persist Analysis, Job, Stage, Event, and Diagnostic state only; never Architecture entities/versions/evidence.
2. Add an Alembic migration, SQLAlchemy models, and repository implementations.
3. Create Analysis and initial Job metadata transactionally.
4. Enforce compare-and-set/optimistic transitions and terminal immutability.
5. Implement bounded create/list/get/status/cancel/timeout lifecycle services and DTOs.
6. Persist attempts, heartbeat, stale-job/orphan-recovery primitives, ordered events, and bounded diagnostics.
7. Verify cancellation/completion, timeout, concurrent acquisition, event sequencing, rollback, migration, and Project isolation.

**Proposed tables:** `analyses`, `analysis_jobs`, `analysis_stages`, `analysis_events`, and `analysis_diagnostics`. Required constraints include UUID primary keys, Analysis-owned child rows, frozen status checks, unique per-Analysis event sequence, unique stable stage identity, non-negative attempts, timestamp/state consistency, terminal immutability through repository methods, expected-state/version predicates, and bounded Project-scoped collection queries.

The migration's Project/Repository/Revision foreign/reference strategy is blocked until the integration ADR defines whether Python reads its existing Phase 2 PostgreSQL snapshot records, receives an explicitly registered snapshot reference, or uses another approved mapping. UUID format alone is insufficient.

**Files:**

| Path | Action/status | Responsibility and dependencies |
|---|---|---|
| `backend/platform/analysis/infra/lifecycle_model.py` | Create, proposed | M1-only SQLAlchemy lifecycle/diagnostic models. |
| `backend/platform/analysis/infra/{analysis_repository,job_repository,event_repository,diagnostic_repository}.py` | Create, proposed | SQLAlchemy implementations with scoped, conditional operations. |
| `backend/platform/analysis/application/lifecycle_service.py` | Create, proposed | Create/list/get/cancel/timeout use cases; no result queries. |
| `backend/platform/analysis/application/dto.py` | Create, proposed | Lifecycle request/response DTOs only. |
| `backend/platform/analysis/application/dependencies.py` | Create, proposed | Lifecycle repository/service providers. |
| `backend/platform/config.py` | Modify, verified existing | Pagination, diagnostic, heartbeat, stale-job and persistence limits. |
| `backend/infra/migrations/env.py` | Modify, verified existing | Register only M1 lifecycle models at this batch. |
| `backend/infra/migrations/versions/<revision>_create_analysis_lifecycle_tables.py` | Create, proposed | Five M1 table groups and approved references/constraints/indexes. |
| `tests/p3/analysis/test_m1_persistence.py` | Create, proposed | Repositories, constraints, scope, events, diagnostics. |
| `tests/p3/analysis/test_m1_lifecycle_service.py` | Create, proposed | Use cases, validation, cancellation, timeout. |
| `tests/p3/analysis/test_m1_concurrency.py` | Create, proposed | Competing transitions/acquisition/cancellation/sequences. |
| `tests/p3/analysis/test_m1_migration.py` | Create, proposed | Upgrade/downgrade and metadata-drift checks. |

**Consistency contract:** lifecycle creation is one transaction containing Analysis `CREATED`, initial Job metadata, applicable initial Stage metadata, and `analysis.created`. Transitions use expected state plus a concurrency version; a zero-row update is a conflict, never an overwrite. Queued cancellation is direct `QUEUED -> CANCELLED`; running cancellation is cooperative through `CANCEL_REQUESTED`. Timeout records safe diagnostic/event evidence and follows the approved `TIMEOUT -> FAILED` representation.

**Error behavior:** state conflict is HTTP 409/non-retryable for the caller; missing Analysis is 404; database connectivity is retryable infrastructure failure; deadlock is conditionally retryable; invalid cancellation is conflict; constraint/integrity inconsistency is high-severity; diagnostic limits aggregate rather than silently presenting incomplete evidence as complete.

**Acceptance criteria:** PostgreSQL reconstructs all M1 lifecycle state after restart; concurrent transitions cannot corrupt it; migration upgrade/downgrade passes on an isolated database; collections are scoped/bounded; cancellation and timeout are deterministic; no Architecture table exists; Batch 1 and Batch 2 checks pass.

**Exact order:** approve reference strategy; design tables from F1; add migration/models; implement repositories; implement conditional transitions; implement event/diagnostic persistence; implement DTO/service; implement cancellation/timeout/recovery persistence; add integration/concurrency tests; run migrations and quality gates.

**Handoff to Batch 3:** verified schema/repositories, lifecycle services, atomic transitions, Job acquisition/heartbeat, event/diagnostic persistence, and approved delegated-resource references.

#### 4.6.7 Batch 3 — Execution Orchestration & Integration

**Objective:** connect lifecycle persistence to RabbitMQ/Celery and expose approved internal lifecycle REST/SSE interfaces to Express, validating M1 through injected fake handlers without implementing M2–M4.

**Responsibilities:**

1. Add pinned Celery/RabbitMQ dependencies, validated configuration, and RabbitMQ Compose service.
2. Publish identifier-only messages and reload authoritative PostgreSQL state in workers.
3. Implement deterministic handler registry/orchestrator, retry/backoff, heartbeat, orphan recovery, backpressure, concurrency limits, cooperative cancellation, and 30-minute Analysis timeout.
4. Recover persisted-but-undispatched jobs and tolerate duplicate messages through conditional Job acquisition.
5. Add internal create/list/get/cancel/events APIs using the ADR-approved service authentication/delegated context.
6. Add durable SSE sequence/replay; REST remains authoritative.
7. Validate the complete M1 path with fake handlers; production must not report completion when required M2–M4 handlers are absent.

**Queue payload:** `analysis_id`, `job_id`, `task_type`, contract version, and an approved correlation identifier only. It must not contain source bytes, artifact lists, credentials/tokens, complete configuration blobs, or AnalysisInput.

**Files:**

| Path | Action/status | Responsibility and dependencies |
|---|---|---|
| `requirements.txt` | Modify, verified existing | Add only approved pinned Celery/RabbitMQ dependencies. |
| `.env.example` | Modify, verified existing | Broker, queue, retry/backoff, heartbeat, timeout, concurrency, dispatch recovery. |
| `infra/docker/compose.yml` | Modify, verified existing | RabbitMQ service/healthcheck; preserve PostgreSQL. |
| `backend/platform/config.py` | Modify, verified existing | Bounded orchestration settings and safe defaults. |
| `backend/platform/analysis/application/orchestrator.py` | Create, proposed | Acquisition, ordered handler execution, lifecycle/result propagation. |
| `backend/platform/analysis/application/registry.py` | Create, proposed | Deterministic handler registration without importing M2–M4. |
| `backend/platform/analysis/application/events.py` | Create, proposed | Sanitized durable lifecycle event helper. |
| `backend/platform/analysis/application/recovery.py` | Create, proposed | Undispatched and stale/orphan Job recovery. |
| `backend/platform/analysis/infra/queue.py` | Create, proposed | Celery/RabbitMQ queue adapter with identifier-only payload. |
| `backend/worker/{__init__,celery_app,tasks}.py` | Create, proposed | Worker package, Celery setup, idempotent Analysis task. |
| `backend/api/v1/analyses.py` | Create, proposed | Internal lifecycle REST/SSE endpoints; no Architecture result endpoints. |
| `backend/api/v1/router.py` | Modify, verified existing | Mount M1 internal lifecycle router. |
| `backend/api/error_handlers.py` | Modify, verified existing | Stable M1 HTTP/error mappings. |
| `backend/platform/analysis/application/dependencies.py` | Modify from Batch 2 | Add queue/orchestrator/registry/delegated-context providers. |
| `tests/p3/analysis/test_m1_orchestrator.py` | Create, proposed | Ordering, progress, failure, cancellation, timeout. |
| `tests/p3/analysis/test_m1_jobs.py` | Create, proposed | Celery eager, duplicates, retries, heartbeat/orphans. |
| `tests/p3/analysis/test_m1_queue.py` | Create, proposed | Payload, broker failure, dispatch recovery/backpressure. |
| `tests/p3/analysis/test_m1_api.py` | Create, proposed | Service auth, delegated scoping, 202/status/cancel/errors. |
| `tests/p3/analysis/test_m1_sse.py` | Create, proposed | Sequence/replay/reconnect/terminal stream. |
| `tests/p3/analysis/test_m1_e2e.py` | Create, proposed | Create -> queue -> worker -> fake handlers -> terminal state. |

**Dispatch consistency proposal:** persist lifecycle/Job state before publishing; retain dispatch metadata so an undispatched Job is recoverable. Publication is at-least-once, not falsely described as exactly-once. Duplicate delivery is safe because worker acquisition is conditional and stages are idempotent. The exact Job dispatch states, idempotency-key ownership, and API response when persistence succeeds but publication fails require F1/ADR approval.

**Failure/recovery:** broker outage is retryable orchestration failure; retry exhaustion becomes explicit Job/Analysis failure; worker crashes are detected from stale heartbeat; non-retryable failures are not retried; queue saturation is explicitly rejected/delayed; timeout triggers cleanup and failure; unknown/missing handlers are configuration failures, never successful completion.

**Internal lifecycle API:** conceptual routes are `POST /api/v1/analyses`, `GET /api/v1/analyses`, `GET /api/v1/analyses/{id}`, `POST /api/v1/analyses/{id}/cancel`, and `GET /api/v1/analyses/{id}/events`. Express remains the frontend/platform boundary. The integration ADR must define service credentials, delegated actor/role/Project scope, replay protection, internal exposure, idempotency propagation, error mapping, audit/request correlation, and SSE proxy/relay.

**Acceptance criteria:** delegated authenticated creation returns 202; RabbitMQ messages contain identifiers only; workers reload PostgreSQL state; duplicate tasks do not repeat completed effects; retry/cancellation/timeout/worker-loss paths are explicit; REST reconstructs state after restart; SSE replays durable events; M1 E2E passes with fake handlers; no M2–M4 implementation is present; Phase 1/2 regressions remain green.

**Exact order:** approve integration ADR; add dependencies/settings/Compose; implement queue/dispatch recovery; implement Celery app/task; implement registry/orchestrator; add heartbeat/retry/cancellation/timeout/orphan recovery; add internal REST; add SSE; add focused tests; perform a real RabbitMQ smoke run; run all quality/regression gates.

**Handoff to M2:** frozen AnalysisInput, ExecutionContext, handler/result protocol, diagnostic/event/progress ports, cancellation checkpoints, configuration/version metadata, and lifecycle behavior that downstream modules cannot bypass.

#### 4.6.8 F1 contract freeze specification

| Contract | Owner | Consumers | Required approval/freeze evidence |
|---|---|---|---|
| Analysis lifecycle | M1 | API, persistence, worker, M2–M5 | Resolve TIMEOUT representation, Stage conflict, Job states, and any additional failure transitions; full valid/invalid matrix and terminal tests. |
| AnalysisInput | M1 | M2; M3/M4 indirectly | Approve immutable snapshot source under Express authority; chain, paging, lazy read, missing storage, immutability tests. |
| Phase 2 resource reference | Phase 2 + M1 adapter; integration ADR governs cross-service form | Express/Python boundary | Approve Express UUID -> Python snapshot/artifact mapping and content availability; substitution/mismatch tests. |
| Analysis/Job domain | M1 | persistence/orchestrator/API | Approve Job states, attempts, heartbeat, dispatch metadata, idempotency ownership; invariant/history tests. |
| Stage/execution | M1 | M2–M4 handlers | Resolve Stage states and outcome semantics; fake-handler/order/cancellation/retry tests. |
| Shared diagnostic | M1 | M2–M4 emitters; M4 result projection | Approve Appendix I field subset, caps, redaction, aggregation, version; safety/determinism/volume tests. |
| Event | M1 | SSE, Express relay, operations | Approve vocabulary, sequence, retention, payload; replay/order/redaction tests. |
| Configuration/version | M1 | all analysis modules | Approve initial contract/analyzer versions and bounded defaults; invalid/missing/version-mismatch tests. |
| Delegated request context | Integration ADR; M1 consumer | Express/Python APIs | Approve service authentication, actor/role/Project claims, replay protection, audit correlation; mechanism-specific security tests. |

F1 v1.0.0 is frozen after owner approval and passing contract/integration gates. Future incompatible changes require versioning, updated consumer fixtures, impact documentation, and renewed approval.

#### 4.6.9 M1 risks, blockers, and owner decisions

**Before Batch 1/F1:** decide which immutable snapshot Python analyzes under Express platform authority; confirm Project replaces stale Organization wording; resolve persisted-vs-event TIMEOUT; resolve Section 9 vs Appendix C Stage states; approve Job states.

**Before Batch 2:** approve Project/Repository/Revision FK/reference/mapping strategy; approve idempotency ownership; resolve the stale per-Organization quota against Project-first architecture.

**Before Batch 3:** approve the integration ADR's service authentication, delegated authorization, resource mapping, artifact access, SSE relay, error propagation, request/audit correlation, internal exposure, dispatch-failure semantics, and concrete retry/heartbeat/queue/concurrency limits.

Principal risks are cross-database identity drift, trusting unverified client/resource IDs, database/queue dual-write gaps, worker crashes leaving stale RUNNING work, lifecycle ambiguity, diagnostic floods, hidden partial results, and downstream modules bypassing M1. Mitigations are the integration ADR, F1 contract tests, conditional transitions, durable dispatch metadata, heartbeat recovery, bounded diagnostics, explicit completeness, and architecture fitness tests.

#### 4.6.10 M1 definition of done and quality gates

M1 is done only when all three batches are implemented sequentially; F1 and the integration ADR are approved; PostgreSQL is authoritative; RabbitMQ carries identifier-only messages; Celery reloads authoritative state; retry/cancellation/timeout/orphan/duplicate paths are explicit; internal APIs enforce delegated Project scope; SSE replays durable events; AnalysisInput is immutable/read-only; no Architecture persistence or M2–M5 functionality appears; and all migrations, M1 checks, Phase 1/2 regressions, and the real-broker smoke validation pass.

```text
black --check backend tests
ruff check backend tests
mypy backend
alembic upgrade head
pytest tests/p3/analysis
pytest
```

The existing CI workflow remains an M6-owned file under the phase plan. Batch 3 must still record a real RabbitMQ/Celery smoke result; default unit tests use fakes or Celery eager execution until M6 adds the real-broker CI service.

#### 4.6.11 Coding-agent handoff prompts

**Batch 1 prompt:**

> Implement Phase 3 M1 Batch 1 only after the listed F1 owner decisions are approved. Read `master.txt` §0, §7, §9, Appendices C/I, this M1 plan, and actual Phase 2 revision/artifact/storage contracts. Create the proposed pure-Python Analysis domain, AnalysisInput adapter, shared diagnostic/event contracts, execution ports, repository interfaces, and focused tests. Use absolute imports. Do not add persistence models/migrations, Celery/RabbitMQ, APIs, Express/frontend changes, M2 parsing, M3 IR, or M4 Architecture work. Preserve existing changes, run targeted Pytest plus Black/Ruff/Mypy, update only verified execution evidence, and stop after Batch 1.

**Batch 2 prompt:**

> Implement Phase 3 M1 Batch 2 only after Batch 1/F1 and the resource-reference strategy are approved. Add M1-only PostgreSQL lifecycle models, repositories, migration, conditional transitions, lifecycle services/DTOs, cancellation, timeout, heartbeat/orphan persistence primitives, ordered events, bounded diagnostics, and focused persistence/concurrency tests. Persist no Architecture data and add no worker/broker/API integration beyond approved lifecycle application services. Use absolute imports, run migration/targeted/full regression checks and Black/Ruff/Mypy, record exact evidence, and stop after Batch 2.

**Batch 3 prompt:**

> Implement Phase 3 M1 Batch 3 only after Batches 1–2 and the Express/Python integration ADR are approved. Add approved Celery/RabbitMQ dependencies/settings/Compose service, identifier-only queue/task integration, orchestration registry, dispatch/orphan recovery, heartbeat, bounded retry/backoff, cancellation/timeout propagation, delegated internal lifecycle REST/SSE, and tests using fake handlers. Apply the approved service authentication/resource context exactly. Do not implement M2 parsing, M3 IR, M4 Architecture persistence/results, Express application changes, frontend work, or later phases. Run all M1/full regression/migration/quality checks and the real-broker smoke validation, update verified evidence, and stop.

---

### 4.7 Module 2 — Repository Inspection & Language Analysis

**Planning status: PLAN APPROVED / FROZEN — BATCHES 1 & 2 IMPLEMENTED & VERIFIED.** F1 v1.0.0 and M1 remain frozen. Batches 1 and 2 of M2 are complete; Batches 3 and 4 remain.

#### 4.7.1 Objective, ownership, and non-goals

M2 deterministically turns the frozen `AnalysisInput` artifact catalog and lazy content reader into a complete repository inspection result for M3. It owns artifact analysis roles and eligibility, language/runtime/framework detection, parser adapters, generic syntax extraction, framework enrichment, evidence provenance, source locations, per-artifact processing outcomes, and M2 diagnostics. It emits the proposed F2 parser-neutral contract; it does not emit IR or Architecture entities.

M2 must:

1. Inventory every F1 artifact in normalized path order and assign exactly one analysis role: `semantic`, `configuration`, `documentation`, `metadata_only`, `ignored`, or `unsupported`; track processing outcome separately, with `failed` only as an outcome.
2. Preserve Phase 2 `category` and `support_level` as immutable upstream facts while applying separate Phase 3 eligibility, user exclusions, generated/test/binary/secret policy, resource limits, and failure reasons.
3. Detect Python, JavaScript, TypeScript, JSX, and TSX; distinguish Python, Node.js, and browser runtimes; and detect Django, Flask, FastAPI, Express, NestJS, and Next.js from deterministic evidence.
4. Parse Python with the built-in `ast` module and JS/TS/JSX/TSX behind a replaceable Tree-sitter adapter using the approved exact pins below.
5. Extract modules/packages, imports/exports, classes, functions/methods, interfaces, type aliases, decorators, inheritance, calls/references, and React component declarations/composition with source evidence.
6. Enrich generic facts with the six approved framework analyzers. Generic extraction must survive framework detection/enrichment failure.
7. Record safe `AnalysisDiagnostic` instances and explicit per-artifact outcomes so malformed, unsupported, excluded, oversized, inaccessible, or sensitive artifacts are never represented as successfully analyzed.

Explicit non-goals are M3 symbol/import/call resolution, common IR, dependency relationship resolution, M4 logical identity or Architecture entities, PostgreSQL Architecture/result persistence, new APIs/UI, AI analysis, code execution, dependency installation, builds, or external network access. React is generic JSX/TSX component evidence in M2, not a newly approved framework target.

#### 4.7.2 Verified reuse and missing capabilities

**Reuse without redesign:**

- Frozen `backend/platform/analysis/domain/input.py`: `AnalysisInput`, deterministic `ArtifactCatalog`, `AnalysisArtifact`, and lazy bounded `ArtifactContentReader`.
- Frozen `backend/platform/analysis/application/execution.py`: `ExecutionContext`, progress/diagnostic/cancellation ports, `AnalysisStageHandler`, and `StageExecutionResult`.
- Frozen stage vocabulary in `backend/platform/analysis/domain/constants.py`: `inventory`, `language_detection`, `framework_detection`, and `syntax_extraction` are the M2 lifecycle stages.
- Frozen M1 `AnalysisDiagnostic`; M2 emits it and introduces no competing finding/diagnostic contract.
- Express/Mongo Phase 2 manifest/content boundary in ADR-0001. The production manifest contains immutable artifact ID, revision ID, path, size, content hash, category, and support level, but no storage key or source bytes.
- Express `express/src/services/ingestion/artifactClassifier.js` categories/support levels and limits. The retained Python classifier is a reference/regression equivalent, not the production source authority.
- Existing `AnalysisConfiguration` include/exclude paths, maximum file size, timeout, and versioned custom rules.

**Important distinctions and gaps:**

- Phase 2 classifies ingestion artifacts broadly (for example Java is `source_code/full`); M2 alone decides whether that artifact is supported for Phase 3 semantic analysis.
- Phase 2 metadata does not include detected language, generated/test/sensitive classification, M2 role/outcome, runtime/framework evidence, parse facts, source ranges, or completeness statistics.
- No M2 package, parser dependency, F2 contract, production M2 handlers, parser sandbox/executor, framework detector, fixture corpus, or M2 tests currently exists.
- M1 persists lifecycle state but intentionally does not persist arbitrary stage output. M2 produces the immutable F2 result and M3 consumes that supplied result; M3 never invokes M2 or owns F2 reconstruction. During one live execution attempt, orchestration composition holds the immutable result in an attempt-scoped handoff. If recovery loses that handoff, M1 orchestration invokes the registered M2 producer through an internal recovery-only rebuild path before M3 runs. Rebuild uses the same immutable `AnalysisInput`, effective configuration, and parser/analyzer versions. Completed Stage records remain terminal and unchanged; no frozen F1 lifecycle state, transition, type, or public event vocabulary changes.

#### 4.7.3 Data flow and component responsibilities

```text
AnalysisInput / ArtifactCatalog (F1)
  -> InventoryBuilder
       preserve Phase 2 facts; apply safety, limits, exclusions, M2 roles
  -> LanguageDetection + PreliminaryFrameworkDetection
       extension/manifest/config/path evidence only; no source parsing
  -> bounded ArtifactContentReader reads for eligible text only
  -> ParserExecutor (OS-isolated child, hard resource/network/environment boundary)
       PythonAstAdapter | TreeSitterJsTsAdapter
  -> generic extractor
       parser-neutral declarations/imports/exports/references/components
  -> FrameworkDetectionFinalizer
       combine preliminary evidence with generic syntax facts
  -> framework enrichers (no reparsing)
       Django | Flask | FastAPI | Express | NestJS | Next.js
  -> canonical RepositoryInspectionResult (F2)
       inventory + detections + SyntaxDocuments + diagnostic references + coverage
  -> attempt-scoped immutable handoff supplied by M1 orchestration
  -> M3 normalization/resolution consumes F2 (outside M2)
```

The inventory is metadata-first and must not read ignored, binary, prohibited-sensitive, unsupported, or oversized content. Language detection and preliminary framework detection run before parsing. The `framework_detection` lifecycle stage reads only permitted manifests/configuration plus path/metadata signals and produces ordered candidates; it does not parse source or claim source-confirmed framework structures. `syntax_extraction` parses each eligible artifact exactly once, emits generic facts, finalizes framework state by combining candidate evidence with syntax-level imports/decorators/constructs, and then runs enrichment over those same facts without reparsing. Detection answers whether framework evidence exists and records `confirmed`, `supported`, or `unknown`; enrichment extracts framework-specific facts only for supported/confirmed candidates. A dependency name alone cannot confirm a framework, and enrichment failure preserves generic facts plus an explicit diagnostic.

M1 stage adapters are thin orchestration wrappers around stateless M2 services. The `syntax_extraction` handler produces the complete immutable F2 value into an execution-attempt-scoped handoff owned by orchestration composition. M3 receives that value as input and never calls M2. Correctness does not depend on a process-global cache: after handoff loss, M1 recovery invokes M2 in rebuild mode using the original immutable `AnalysisInput`, effective configuration fingerprint, and exact parser/grammar/analyzer versions; M3 is scheduled only after byte-equivalent canonical F2 is rebuilt. Recovery does not reset, reopen, replace, or append completed Stage records and does not change Analysis/Job/Stage state. It introduces no new public event type: approved existing lifecycle events may be emitted only when their defined semantics apply; otherwise replay observability is limited to internal structured logs/metrics and safe existing diagnostics. A version/configuration mismatch or rebuild failure fails the active job explicitly without running M3. Until M3 exists, production analyses still cannot complete the full pipeline, and M2 must not install fake M3/M4 handlers.

#### 4.7.4 Proposed F2 — Repository Inspection and Syntax Evidence v1.0.0

**Owner:** M2. **Consumer/sign-off:** M3. **Status:** design baseline approved and frozen; contract artifact not yet implemented or runtime-frozen. Proposed contract document: `docs/architecture/contracts/f2-repository-inspection-syntax-v1.md`. Batch 1 must encode this baseline without reinterpretation; runtime F2 v1 freezes only after contract tests and M3 consumer review.

Top-level `RepositoryInspectionResult` contains `f2_version`, analysis/project/repository/snapshot IDs, analyzer version, effective-configuration fingerprint, ordered inventory entries, language/runtime/framework detections, ordered `SyntaxDocument` values, coverage counts, and referenced M1 diagnostic IDs. It contains no raw AST nodes, source bytes, secrets, absolute/storage paths, resolved cross-file relationships, IR, or Architecture entities.

`ArtifactInventoryEntry` contains artifact/revision IDs, normalized relative path, content hash, size, original Phase 2 category/support level, detected language when known, test/generated/sensitive flags, one stable analysis role, one separate processing outcome, and stable reason codes. `ArtifactAnalysisRole` is one of `semantic`, `configuration`, `documentation`, `metadata_only`, `ignored`, or `unsupported`. `ArtifactProcessingOutcome` is one of `not_processed`, `analyzed`, `analyzed_with_warnings`, `excluded`, `unsupported`, or `failed`. Role describes intended pipeline participation; outcome describes what actually happened. Thus parser/read failure leaves a semantic role with a failed outcome, an ignored role normally has an excluded outcome, and an unsupported role has an unsupported outcome. `failed` is never a role.

Role precedence is: mandatory safety/resource policy; explicit user exclusion; upstream ignored/generated/build-cache; prohibited-sensitive/binary; supported source/test semantic eligibility; safe configuration/manifest; documentation; metadata-only; unsupported. The proposed exclusion grammar is normalized repository-relative POSIX `gitwildmatch` syntax through the already-declared `pathspec` package: an empty include set means all otherwise eligible artifacts, a non-empty include set narrows eligibility, explicit excludes win over includes, and neither can override secret/safety/resource policy. `.gitignore` remains advisory evidence and is not silently applied as an absolute exclusion list.

Sensitive classification first uses only permitted immutable metadata and path signals: Phase 2 category/support level, normalized relative path, basename/extension, size, and known generated/secret conventions. Files classified by policy as environment secrets, keys/certificates, credential stores, binaries, or otherwise prohibited are assigned `metadata_only` or `ignored` as policy dictates and their content reader is never called. Permitted source/configuration artifacts may be parsed for structural evidence, but F2 may retain only allowlisted architecture literals such as module specifiers, dependency names/declared versions, decorator names, HTTP methods, and route templates. It never emits arbitrary configuration values, environment values, string literal arguments, tokens, connection strings, key material, or a literal value that triggered sensitive detection. Diagnostics record stable reason/signal codes and locations, never the secret value.

`SyntaxDocument` contains the F2 version, artifact ID/path/content hash, language and language version/dialect where known, parser adapter ID/version/grammar ABI, parse status (`parsed`, `parsed_with_errors`, or `failed`), canonically ordered facts, and diagnostic references. A failed supported artifact remains represented without fabricated facts.

`SyntaxFact` is a tagged immutable union rather than an untyped parser-node dump:

- `DeclarationFact`: module, package, class, function, method, interface, type alias, variable/constant, or React component; name, optional qualified/local container key, modifiers, decorators, signature/type text only where safely bounded, and declaration/name ranges.
- `ImportFact`: source module specifier, relative level, imported name, local alias, side-effect/type-only/CommonJS flags, and range.
- `ExportFact`: local/exported name, source module when re-exported, default/type-only/CommonJS flags, and range.
- `ReferenceFact`: call, name/attribute reference, inheritance, decorator use, or React composition; source declaration key when local, unresolved target text, and range. M2 never resolves a cross-file target.
- `FrameworkFact`: framework-specific route/router/module/provider/model/middleware/component/config evidence linked to supporting generic fact keys and detection evidence.
- `ManifestFact`: redacted dependency/configuration key/value structure; dependency names and declared versions may be retained, but secret values and arbitrary environment values may not.

Every fact has a deterministic `fact_key` derived from snapshot/artifact identity, tagged kind, normalized local discriminator, and source range; keys are not persistence UUIDs and are not M4 logical IDs. Parent/child references are document-local fact keys only. Facts and documents sort by `(artifact.path, range.start_byte, range.end_byte, kind, fact_key)`; mappings serialize with sorted keys and no timestamps. Duplicate evidence is deduplicated by canonical provenance key.

`SourceRange` uses one canonical coordinate space across adapters: the decoded logical source re-encoded as UTF-8, with zero-based absolute byte offsets, one-based lines, zero-based UTF-8 byte columns, and end-exclusive boundaries. Ranges never mix original-file byte offsets with canonical UTF-8 offsets.

The source decoder records the original encoding as document metadata. Python encoding is determined from the raw bounded bytes using the PEP 263/UTF-8-BOM rules (`tokenize.detect_encoding`); permitted non-UTF-8 Python is decoded strictly and then re-encoded to canonical UTF-8. JS/TS/JSX/TSX accepts strict UTF-8 with an optional UTF-8 BOM. The BOM is excluded from canonical coordinates. Newline bytes are otherwise preserved, including CRLF, so absolute offsets are computed from the exact canonical UTF-8 buffer supplied to the parser. Python `ast` one-based lines and UTF-8 byte columns are converted using canonical line-start offsets; Tree-sitter zero-based rows are incremented by one while its UTF-8 byte columns/offsets map directly. Decode failures produce a failed processing outcome plus a diagnostic; no lossy replacement decoding is allowed. F2 evidence exposes canonical coordinates and original-encoding metadata, not original byte offsets. Invalid or unavailable ranges are omitted only when the fact remains safe and a diagnostic explains the limitation.

`DetectionEvidence` identifies artifact ID/path, optional `SourceRange`, a stable signal code, safe observed token/manifest key, analyzer ID/version, and polarity (`supporting` or `conflicting`). Language detections are artifact-scoped; runtime/framework detections are repository- or application-boundary scoped. Evidence uses named states, never floating-point confidence.

Parser failures use the shared M1 `AnalysisDiagnostic` (`category=parsing`, file/artifact scope, artifact ID/path and safe location). F2 holds diagnostic IDs and coverage state; it does not duplicate diagnostic messages as another domain type. Incompatible F2 changes require a major contract version, updated producer/consumer fixtures, and M2/M3 owner approval; additive optional fields require a minor version and contract tests.

#### 4.7.5 Parser compatibility and security spike

Verified locally on 2026-11-05 with the repository runtime `CPython 3.14.6` in isolated temporary virtual environments; no repository dependency was changed:

- Python built-in `ast` parsed representative Python and is the recommended Python adapter. It exactly matches the active interpreter grammar and provides one-based lines plus UTF-8 byte columns. It can raise `SyntaxError`, `ValueError`, `MemoryError`, or `RecursionError`, and sufficiently complex untrusted input can crash the interpreter; it must therefore run behind process isolation and the per-file resource boundary.
- `tree-sitter==0.25.2` installed from a CPython 3.14 wheel. `tree-sitter-javascript==0.25.0` and `tree-sitter-typescript==0.23.2` installed from stable-ABI wheels. The combination parsed ESM, CommonJS/Express, JavaScript JSX, TypeScript interfaces/classes/decorators, TSX/React composition, and reported recoverable malformed syntax through `root_node.has_error`.
- The JavaScript grammar covers JavaScript + JSX. The TypeScript package supplies separate TypeScript and TSX grammars. All are maintained under the official Tree-sitter organization and MIT licensed.
- `tree-sitter==0.26.0` also installed and parsed the sample corpus, but removes timeout attributes and contains newer breaking API changes. The current recommendation is the narrower 0.25.2 core with the latest compatible official grammars, wrapped behind `ParserAdapter`, until a controlled upgrade is separately tested.
- Tree-sitter's direct bytes parsing does not provide a reliable hard wall-clock stop through the Python progress callback, and Python `ast` has no safe in-process kill boundary. Both adapters therefore require an actual OS process boundary with a 5 MiB pre-read cap, the master-defined 30-second per-file deadline, forced termination, hard CPU/memory/open-file/process/file-size limits, and bounded IPC/result size. Production must fail closed if the isolation boundary cannot be established. The child receives source bytes and the minimum parser request over explicit IPC, not repository paths; runs with dropped privileges where supported, a minimal allowlisted environment, no network access, no shell/package-manager/code-execution path, no host/workspace traversal, and no inherited database, broker, storage, cloud, credential, socket, or unrelated file handles (`close_fds` or platform-equivalent). Any bounded temporary directory is private and disposable.
- The packages publish wheels but their inspected PyPI releases do not provide provenance attestations. Implementation must pin exact versions, review wheel availability for CI/deployment architectures, record dependency hashes where the project's dependency workflow permits, and run dependency/security scanning.

**Approved parser baseline:** pin `tree-sitter==0.25.2`, `tree-sitter-javascript==0.25.0`, and `tree-sitter-typescript==0.23.2`; keep Python on built-in `ast`; use iterative tree traversal (not recursive visitor depth) and adapter-owned node mappings rather than Tree-sitter query APIs for the initial implementation.

#### 4.7.6 Practical implementation batches

**Batch 1 — F2 contract and safe parser foundation**

- Implement the approved parser pins, role/outcome model, canonical UTF-8 range semantics, exclusion matching, sensitive-artifact policy, and M1-owned recovery/rebuild semantics without reopening the plan.
- Add the F2 contract document and immutable model/protocols; add approved dependencies/settings.
- Implement the fail-closed OS-isolated parser executor, Python and JS/TS adapter bootstraps, encoding policy, timeout/crash/error translation, hard resource/network/environment/handle isolation, and adapter contract tests.
- Add a benchmark harness before full extraction. Measure fact count, canonical serialized bytes, peak child/parent RSS, and parse/extraction time for each representative framework fixture plus deterministic synthetic files at small, median, and the 5 MiB boundary. Record per-artifact and whole-fixture maxima and proposed headroom; owner approval of per-artifact fact, per-analysis fact, and serialized-F2 byte caps is required before Batch 3 extraction expands beyond the spike corpus.
- Exit gate: exact versions install on Python 3.14 CI; Unicode, CRLF, UTF-8 BOM, PEP 263 non-UTF-8 Python, invalid encoding, valid/malformed/timeout/oversized fixtures return contract-valid results or shared diagnostics; network/credential/descriptor/host-path isolation and hard resource termination are proven in the production execution mode; benchmark evidence and proposed caps are recorded for approval; no generic/framework extraction yet.

**Batch 2 — Deterministic inventory and detection**

- Implement separate role/outcome mapping from all Phase 2 categories/support levels, include/exclude policy, test/generated/sensitive handling, and coverage counts.
- Implement permitted metadata/path-only sensitive classification and prove prohibited-sensitive content is never opened. Safe manifest/config readers expose only allowlisted structural values.
- Implement language/runtime detection and preliminary framework candidate detection from metadata/path/permitted manifest signals, with positive, negative, multi-language, multi-framework, and conflicting evidence; do not parse source in this stage.
- Exit gate: every artifact has one role and reason; no ineligible content is read; shuffled catalog order produces byte-equivalent inventory/detection serialization.

**Batch 3 — Generic syntax extraction**

- Complete Python and JS/TS/JSX/TSX parser-neutral extraction for all required declarations, import/export forms, decorators, inheritance, calls/references, and React composition.
- Parse each eligible artifact once; reuse the resulting generic facts to finalize framework detection and supply later enrichment. Canonicalize fact keys, UTF-8 ranges, provenance, ordering, parse-recovery behavior, and per-artifact diagnostics.
- Enforce the owner-approved caps atomically. Crossing a cap emits `resource_limit_exceeded`, marks the affected artifact/result explicitly, and discards or rejects the incomplete fact set according to the approved failure policy; it never returns an apparently complete truncated document.
- Exit gate: F2 contract/golden fixtures pass for all five syntax variants and all encoding/newline fixtures; one file failure cannot abort independent files; approved caps are enforced without silent truncation; no parser-specific object escapes.

**Batch 4 — Framework enrichment, M1 integration, and freeze**

- Implement Django/Flask/FastAPI and Express/NestJS/Next.js enrichment over generic facts, including negative fixtures that prevent name/dependency-only false positives.
- Add thin M1 stage handlers, attempt-scoped immutable F2 handoff, and production registry wiring without changing frozen F1 types or lifecycle semantics. M3 is only a consumer. Add progress/cancellation checkpoints between artifacts and before enrichment.
- Implement only the owner-approved M1 recovery-only rebuild mechanism: when the non-persisted handoff is lost, orchestration re-executes M2 with the same immutable input/configuration/version tuple before scheduling M3; completed stages and frozen lifecycle states remain unchanged, M3 cannot trigger reconstruction, and no new public event vocabulary is introduced.
- Run M2 integration, determinism, limits, security, full Python regression, Black, Ruff, Mypy, and dependency checks. Freeze F2 only after M3 consumer review.
- Exit gate: all six enrichers reuse the single generic parse and preserve facts/evidence; full `RepositoryInspectionResult` is canonical and byte-equivalently rebuildable by M2 under M1 recovery; completed Stage rows and F1 remain unchanged, no public event enum/type is added, and regressions stay green.

#### 4.7.7 File-level implementation specification

All paths below were rechecked on 2026-11-05. **Modify** paths exist; **Create (proposed)** paths do not. No deletion is planned.

| Path | Action | Components and responsibility | Dependencies / tests / rationale |
|---|---|---|---|
| `docs/architecture/contracts/f2-repository-inspection-syntax-v1.md` | Create (proposed) | Normative F2 schema, ordering, range, evidence, diagnostic, compatibility, and change-control rules. | Owned by M2; M3 sign-off; contract/golden tests. |
| `requirements.txt` | Modify in Batch 1 | Pin the three approved Tree-sitter packages only. | Python 3.14 wheel/install/import audit, `pip check`, dependency scan. |
| `backend/platform/config.py` | Modify | Add M2 parser deadline and approved bounded extraction settings; retain existing analysis/file limits. | Settings validation/default/production tests; no M1 setting reinterpretation. |
| `backend/platform/analysis/inspection/__init__.py` | Create (proposed) | Public M2 inspection exports only. | Import-boundary test prevents adapter leakage. |
| `backend/platform/analysis/inspection/model.py` | Create (proposed) | Separate `ArtifactAnalysisRole` and `ArtifactProcessingOutcome`, reason enums, inventory entry, detection/evidence models, coverage, `RepositoryInspectionResult`. | Frozen F1 types + F2 version; role/outcome invariants, immutability/schema/order tests. |
| `backend/platform/analysis/inspection/inventory.py` | Create (proposed) | `InventoryBuilder`; Phase 2-to-M2 role matrix, include/exclude and safety/resource eligibility. | Metadata-only operation; exhaustive category/support/path tests. |
| `backend/platform/analysis/inspection/detection.py` | Create (proposed) | Language/runtime detection, preliminary framework candidates, syntax-backed finalization, and safe allowlisted manifest/config signals. | Inventory + bounded reader + generic facts; stage-order/no-duplicate-parse/corroboration/redaction tests. |
| `backend/platform/analysis/inspection/service.py` | Create (proposed) | Stateless `RepositoryInspectionService` coordinating inventory, detection, parsing, extraction, enrichment, canonicalization, progress, diagnostics, and cancellation. | F1 context ports; full F2 determinism/partial-failure tests. |
| `backend/platform/analysis/syntax/__init__.py` | Create (proposed) | Public F2 syntax exports. | No parser library types in exports. |
| `backend/platform/analysis/syntax/model.py` | Create (proposed) | Canonical UTF-8 `SourceRange`, original-encoding metadata, provenance, tagged `SyntaxFact` union, `SyntaxDocument`, parser/detection enums, canonical serializer/key builders. | Unicode/CRLF/BOM/non-UTF-8/end-exclusive/order/round-trip tests. |
| `backend/platform/analysis/syntax/base.py` | Create (proposed) | `ParserAdapter` and generic/framework extractor protocols; typed success/failure result. | Fake-adapter contract and exception containment tests. |
| `backend/platform/analysis/syntax/executor.py` | Create (proposed) | Fail-closed OS-isolated parser child execution with bounded IPC, byte/deadline/result bounds, hard process resources, no network, minimal environment, closed unrelated descriptors, termination, and safe error mapping. | 5 MiB/30 s defaults; crash/timeout/cancel/resource/network/environment/credential/descriptor/host-path isolation tests in the production execution mode. |
| `backend/platform/analysis/syntax/python.py` | Create (proposed) | Built-in `ast` adapter and generic Python fact extraction. | Python 3.14 syntax, imports/decorators/inheritance/calls, Unicode ranges, malformed/deep fixtures. |
| `backend/platform/analysis/syntax/javascript.py` | Create (proposed) | Tree-sitter adapter plus JS/JSX/TS/TSX generic extraction; grammar-specific nodes remain private. | ESM/CommonJS, interfaces/types/decorators, JSX/TSX components, malformed recovery. |
| `backend/platform/analysis/frameworks/__init__.py` | Create (proposed) | Framework analyzer registry/export boundary. | Deterministic registration/selection tests. |
| `backend/platform/analysis/frameworks/base.py` | Create (proposed) | Common enrichment protocol and evidence helper. | Generic facts in, framework facts out; no IR import allowed. |
| `backend/platform/analysis/frameworks/python.py` | Create (proposed) | Django, Flask, FastAPI detectors/enrichers. | Routes/apps/models/routers/dependencies plus false-positive fixtures. |
| `backend/platform/analysis/frameworks/javascript.py` | Create (proposed) | Express, NestJS, Next.js detectors/enrichers. | Routers/middleware, modules/controllers/providers, app/pages/API/server-client context and negatives. |
| `backend/platform/analysis/application/inspection_handlers.py` | Create (proposed) | Thin handlers for the four existing M2 stage names plus the execution-attempt-scoped immutable F2 handoff; M2 produces/rebuilds and M3 only consumes the supplied value. | M1 execution contracts; handoff-loss/rebuild, identical input/config/version enforcement, cancellation, diagnostics, progress, unchanged completed stages, and no-M3-recompute tests. |
| `backend/worker/tasks.py` | Modify | Register real M2 handlers and the internal M1 recovery-only rebuild hook in production composition; retain absence of fake M3/M4 handlers. | Registry and M1 worker regression tests; no lifecycle/F1/public-event vocabulary changes. |
| `tests/p3/analysis/test_m2_contracts.py` | Create (proposed) | F2 immutability, separate role/outcome invariants, tagged schema, canonical UTF-8 ranges, keys, ordering, serialization, compatibility rejection. | Batch 1/3 freeze gate. |
| `tests/p3/analysis/test_m2_inventory_detection.py` | Create (proposed) | Exhaustive role/outcome matrix, exclusions, languages/runtimes/framework candidate/final states, conflicts, safe literal policy, prohibited-content read avoidance. | Batch 2 gate. |
| `tests/p3/analysis/test_m2_parsers.py` | Create (proposed) | Adapter/executor and one-pass generic extraction across five syntaxes; Unicode, CRLF, BOM, PEP 263 non-UTF-8, invalid encoding, malformed, timeout/crash/resource cases; production-mode OS isolation, no network, environment/credential stripping, descriptor closure, and fail-closed startup. | Batch 1/3 gate. |
| `tests/p3/analysis/test_m2_frameworks.py` | Create (proposed) | All six framework enrichers and negative/mixed-framework evidence. | Batch 4 gate. |
| `tests/p3/analysis/test_m2_integration.py` | Create (proposed) | F1 input -> ordered M2 stages -> canonical F2 handoff -> consumer stub; diagnostics/progress/cancellation, handoff-loss/M1 recovery rebuild using the same input/config/version tuple, byte-equivalence, unchanged completed stages/lifecycle/events, no M3 recomputation, shuffled/concurrent rebuilds, M1 regressions. | Batch 4 freeze gate. |
| `tests/p3/analysis/test_m2_benchmarks.py` | Create (proposed) | Deterministic fact/serialized-byte/RSS/time measurements and cap enforcement at representative and 5 MiB boundaries. | Owner reviews recorded benchmark evidence before Batch 3 full extraction. |
| `tests/fixtures/p3/m2/{python,js,ts,jsx,tsx,django,flask,fastapi,express,nestjs,nextjs,mixed,malformed,encoding,security,limits}/` | Create (proposed) | Small repositories covering positive/negative/ambiguous/monorepo, Unicode, CRLF, BOM, PEP 263 non-UTF-8, invalid encoding, malformed, secret, and resource cases. | No fixture executes; paired canonical expected F2 JSON. |
| `tests/fixtures/p3/m2/expected/*.f2.json` | Create (proposed) | Versioned canonical inspection/syntax outputs. | Byte-stability and compatibility regression. |

#### 4.7.8 Testing, security, determinism, and failure policy

- Unit tests cover every Phase 2 category/support-level combination, independent role/outcome invariant, path rule, detector signal, fact type, canonical range normalization, serializer, and framework detection/enrichment rule.
- Adapter integration tests run the real pinned parsers on Python 3.14 and verify ABI/version metadata, error nodes, malformed syntax, Unicode, CRLF, UTF-8 BOM, PEP 263 non-UTF-8 Python, invalid encodings, modern language features, and no deprecation warnings (`pytest.ini` promotes warnings to errors).
- Security tests prove prohibited-sensitive/ignored/binary/oversized artifacts are classified from permitted metadata/path signals and never read; permitted source/config parsing emits no non-allowlisted literal values. Production-mode parser tests prove a real OS process boundary, hard resource termination, denied network access, minimal allowlisted environment, absent service/cloud/database/broker/storage credentials, closed unrelated file descriptors/sockets, no host/workspace path access, bounded IPC, and fail-closed startup. No repository code, imports, package manager, shell, or build path is invoked; diagnostic/event/F2 payloads expose no source bytes, storage keys, secrets, tracebacks, or absolute paths.
- Resource tests enforce the existing 5 MiB analyzable-file limit and master 30-second per-file deadline before expensive processing. Before full extraction, deterministic benchmarks record per-fixture fact counts, serialized F2 bytes, peak RSS, and execution time at representative and boundary sizes; proposed caps and headroom require owner approval. Exceeding an approved cap emits a diagnostic and explicit failed/partial outcome, and never publishes a silently truncated `SyntaxDocument` or complete F2 result.
- Determinism tests shuffle artifact and analyzer registration order, rerun in separate processes, and compare canonical F2 bytes. Parser/grammar/analyzer versions and configuration fingerprints are part of output metadata.
- One parser/read failure preserves the artifact role but sets its processing outcome to failed where safe, records a shared diagnostic, and continues independent artifacts. Framework enrichment failure yields generic facts with `analyzed_with_warnings`. Systemic contract/configuration/cap failures follow the approved mandatory-stage policy.
- Stage-order tests prove preliminary framework detection performs no source parse, each eligible source is parsed once during syntax extraction, final detection incorporates generic facts, and enrichment reuses those facts without reparsing.
- Recovery tests prove M2 produces F2, M3 only consumes the supplied immutable value, and handoff loss causes M1-orchestrated M2 rebuilding before M3 using the same immutable `AnalysisInput`, configuration fingerprint, and parser/grammar/analyzer versions. Canonical bytes match the original result; completed Stage records and frozen Analysis/Job/Stage states remain unchanged; no new public event type is emitted; mismatch or rebuild failure fails explicitly without scheduling M3. No M3 code imports or invokes an M2 builder/service.
- M2 itself does not transition the overall Analysis to `PARTIAL`; it reports accurate stage outcome/diagnostics/coverage and lets the frozen M1 lifecycle plus later valid-model publication determine final status.
- Quality gates: targeted M2 Pytest; full `pytest`; `black --check .`; `ruff check .`; `mypy backend`; `python -m pip check`; dependency/security audit; `git diff --check`. No claim is recorded without execution.

#### 4.7.9 Acceptance criteria and Definition of Done

M2 is complete only when:

1. Every F1 artifact appears exactly once in a canonically ordered inventory with preserved Phase 2 metadata, exactly one analysis role, exactly one separate processing outcome, and explainable reason codes; `failed` never appears in the role vocabulary.
2. Python/JS/TS/JSX/TSX and Python/Node/browser runtime results are deterministic; unsupported/mixed ecosystems remain explicit.
3. Django, Flask, FastAPI, Express, NestJS, and Next.js require corroborated evidence, support multi-framework repositories, and cannot be confirmed by a similarly named file or dependency alone.
4. Approved source variants produce parser-neutral generic facts and canonical UTF-8 source ranges, or explicit per-artifact diagnostics; Unicode, CRLF, BOM and permitted non-UTF-8 Python map deterministically, invalid encodings fail explicitly, and raw AST/CST nodes never cross F2.
5. All required declaration/reference/import/export/React-composition fact types and safe manifest facts are represented without M3 resolution or M4 entities.
6. Preliminary framework detection, syntax-backed finalization, and framework enrichment are distinct; each eligible artifact is parsed once, enrichment preserves generic facts/provenance, and enrichment failure does not erase successful generic analysis.
7. Prohibited-sensitive content is never opened, extracted facts never expose unapproved literal values, and parser crashes/timeouts, malformed input, unreadable content, approved caps, exclusions, and unsupported languages are reflected in outcomes/coverage without fabricated success or silent truncation. Parser children run behind a verified fail-closed OS isolation boundary with bounded resources/IPC, no network, a minimal credential-free environment, and no unrelated inherited descriptors or host paths.
8. Equivalent snapshot/configuration/parser/analyzer versions produce byte-stable F2 output across artifact-order and process reruns.
9. M2 produces immutable F2 and M3 only consumes the supplied result. Handoff loss causes M1 orchestration to rebuild F2 with the exact original immutable input/configuration/parser/analyzer version tuple before M3; canonical output is byte-equivalent, completed Stage rows and frozen lifecycle states remain unchanged, mismatches fail explicitly, and no persistence, F1 contract, or public event-vocabulary change is introduced.
10. F2 v1 is documented, contract-tested, reviewed by M3, owner-approved, and frozen; incompatible changes require versioning/change control.
11. Production composition registers only real M2 handlers plus the internal recovery hook; frozen F1 remains unchanged, no M3 symbol resolution/IR or M4 identity/Architecture persistence/query work appears, all M1/full regressions and quality gates pass, and `PROJECT_CONTEXT.md` records exact evidence.

Estimated complexity is **High**: five syntax variants, six framework enrichers, untrusted native parsers, canonical evidence/ranges, and deterministic partial-failure semantics. The highest risks are parser sandbox escape/resource exhaustion, credential or descriptor inheritance, grammar-version drift, false-positive framework detection, encoding/range inconsistency, F2 overfitting to parser nodes, and correct orchestration rebuilding of non-persisted F2 without changing frozen F1. Mitigations and acceptance tests above are mandatory Definition-of-Done gates, not optional hardening.

---

### 4.8 Module 3 — Intermediate Representation & Semantic Analysis

#### Responsibilities

1. Define versioned immutable `IRDocument`, `IREntity`, `IRRelationship`, `IREvidence`, unresolved/conflicting facts, and completeness statistics; represent IR problems through the shared `AnalysisDiagnostic` contract rather than a separate `IRDiagnostic` type.
2. Normalize parser/analyzer facts into common Repository, Snapshot, Artifact, Application, Module, Symbol, Component, Endpoint, Database, External System, Message Infrastructure, and Configuration concepts.
3. Build analysis-scoped symbol/module tables and resolve imports, exports, inheritance, calls, endpoint-handler links, component composition, and declared-vs-observed dependencies where deterministic evidence permits.
4. Preserve unresolved targets and ambiguity; never invent a match.
5. Merge duplicate facts only by deterministic identity keys and combine evidence in canonical order.
6. Validate schema version, required fields, allowed types, references, provenance, duplicate/collision rules, and serialization.

#### Semantic rules

- Resolution precedence is explicit: exact qualified name/module path, explicit alias/export, framework binding, then unresolved. Fuzzy display-name matching does not create confirmed relationships.
- Declared dependencies and observed imports/calls are distinct relationship/fact types.
- Evidence strength uses named deterministic levels, not arbitrary floating confidence.
- Cycles are preserved, not removed. Unknown targets and conflicts remain first-class diagnostics.
- IR serialization sorts by stable keys and never regenerates identity during load.

#### Tests

- schema round-trip/version rejection, reference integrity, duplicate merge, conflicting evidence, and canonical ordering;
- symbol/import/export resolution across files/packages and unresolved/ambiguous cases;
- dependency/call/inheritance/component/endpoint relationship extraction;
- provenance survival through normalization;
- cross-language equivalent concepts converge without losing framework/language metadata;
- IR golden fixtures and order-independence/property-style determinism checks.

#### Acceptance criteria

- Valid source evidence becomes schema-valid IR without parser-specific objects.
- Every resolved relationship references existing IR entities and evidence.
- Ambiguity/collisions are explicit and deterministic.
- Invalid IR cannot reach the Architecture Builder.

---

### 4.9 Module 4 — Identity Resolution & Architecture Model

#### Responsibilities

1. Implement analysis-scoped logical identity generation, registry, duplicate resolution, collision diagnostics, and deterministic merge ordering.
2. Define versioned immutable Architecture Model domain contracts: version, entities, hierarchy, relationships, evidence, unresolved relationships, metadata, and completeness. Findings use the shared `AnalysisDiagnostic` contract.
3. Map normalized IR into architecturally meaningful applications, services, modules, components, controllers, endpoints, workers, databases, brokers/queues, external services, frontend applications, and libraries.
4. Keep hierarchy (`CONTAINS`) distinct from dependencies/calls/produces/consumes/data-access relationships.
5. Validate IDs, entity/relationship types, hierarchy, references, cycles, evidence, schema/version inputs, and project/snapshot ownership.
6. Own Architecture Version/entity/relationship/evidence PostgreSQL models, repositories, migration, model construction, validation, atomic publication, canonical serialization, and authorized result-query APIs.
7. Emit basic deterministic `AnalysisDiagnostic` records for unsupported/failed coverage, circular dependencies, unresolved/ambiguous relationships, evidence conflicts, and completeness warnings. Recommendations remain out of scope.

#### Persistence/publication rules

- Architecture Version rows progress `BUILDING -> VALIDATING -> PUBLISHED` or `VALIDATION_FAILED`.
- Entity/relationship/evidence rows are scoped by Architecture Version. Unique constraints prevent duplicate logical IDs within a version.
- A published version is immutable; retries detect/reuse the already published version for the same analysis rather than append duplicates.
- API serialization is stable and sorted but remains a DTO projection, not the domain model itself.
- M4 result services expose findings, Architecture summary, entities, entity details, relationships, and evidence. M1 exposes only lifecycle state plus the published version ID/readiness flag written during idempotent finalization.
- No Neo4j/search/diagram projection is triggered in Phase 3.

#### Tests

- same logical fact from multiple analyzers merges evidence; same display name in different modules remains separate;
- identity collisions, unresolved targets, ambiguous entities, retry/idempotency, and analyzer-order independence;
- hierarchy vs dependency, relationship deduplication, referential integrity, allowed cycles, orphan entities, and unknown external entities;
- atomic publication rollback, published immutability, historical version isolation, and deterministic serialization;
- golden Architecture Models for representative framework fixtures.

#### Acceptance criteria

- Valid IR produces one validated, published, immutable Architecture Version.
- Invalid or colliding architecture is never exposed as published.
- Every architecture fact traces to snapshot evidence and analyzer/schema versions.
- Re-running equivalent input yields semantically identical logical IDs, entities, relationships, findings, and serialization.

---

### 4.10 Module 5 — Frontend Integration & Architecture Visualization

#### Preconditions

Module 5 follows ADR-0001: the frontend calls Express, and Express delegates analysis operations to Python with the accepted service credential and delegated Project context. Live result integration still waits for M4 API DTOs and proxy/result/SSE transport contracts; MongoDB resource IDs remain opaque references rather than permission by format alone.

#### Responsibilities

1. Add analysis initiation from a selected repository revision, preventing duplicate submission while pending.
2. Add repository-scoped analysis history, filters, loading/empty/error/retry states, and permission-aware start/cancel actions.
3. Add an Analysis detail route showing lifecycle state, durable stages, measurable progress, warnings/errors, versions, and timestamps.
4. Subscribe to SSE while active; reconcile with `GET /analyses/{id}` on open, reconnect, sequence gap, visibility return, and terminal event. Stop streams/polling at terminal state.
5. Add paginated findings and architecture results with filters and evidence details.
6. Provide the Phase 3 visualization boundary: summary metrics, application/module hierarchy, entity browser, relationship table, and selected-entity relationship/evidence panel. This is a read-only projection of the canonical model.
7. Preserve existing `apiClient`, auth expiry behavior, dark theme, accessibility, responsive layout, and service-layer API ownership.

#### Visualization boundary

The planned P3 UI does **not** implement the later Diagram Engine, saved views, custom graph layouts, Neo4j traversal, or full React Flow + ELK diagram workflow. If “visualization” is intended to require a node-edge diagram now, that is a roadmap expansion and needs explicit approval; see §7.3. The default plan treats hierarchy, relationships, counts, status, and evidence panels as the P3 architecture visualization.

#### Tests

- service paths/payloads/error preservation and auth attachment;
- start/cancel/history/detail and permission visibility;
- SSE open/reconnect/sequence-gap reconciliation, no overlapping fallback requests, terminal cleanup;
- loading/empty/partial/warnings/timeout-then-failed/cancelled/result-not-ready states;
- findings/entity/relationship pagination/filtering and evidence navigation;
- route parsing, keyboard/focus semantics, reduced-motion/readability, responsive overflow, and existing Phase 2 regressions.

#### Acceptance criteria

- An authorized user can start an analysis and reach results without a page reload.
- The UI never treats SSE as state authority and recovers after disconnect.
- Viewers can inspect permitted results but cannot start/cancel when backend RBAC disallows it.
- Partial/unsupported/failed coverage is visible and never presented as complete.
- Frontend representations cannot mutate or invent Architecture Model facts.

---

### 4.11 Module 6 — Integration, Testing & Phase 3 Evaluation

#### Responsibilities

1. Build representative fixture repositories for Python/FastAPI, Django, Flask, JavaScript/Express, TypeScript/NestJS, and TypeScript/Next.js/TSX, plus mixed-language, monorepo, malformed, unsupported, malicious, and resource-limit fixtures.
2. Validate the complete API -> PostgreSQL -> RabbitMQ -> Celery -> engine -> Architecture Version -> REST/SSE -> frontend flow.
3. Add determinism regression: repeated runs and randomized artifact/analyzer scheduling produce equivalent normalized IR/model serializations.
4. Add security testing: cross-project access, malicious paths/symlinks, secrets, oversized files/count/depth, parser bombs/timeouts, no code execution/network, safe errors/logs/events.
5. Add failure/recovery testing: queue unavailable, duplicate delivery, worker crash, transient storage/database failure, cancellation races, retry exhaustion, parser degradation, atomic publication rollback, and SSE reconnect.
6. Establish measured performance baselines for supported fixture sizes, per-stage timing/memory/count metrics, and configurable timeouts. Do not claim hard budgets until measured and approved.
7. Run all Python, frontend, migration, format, lint, type, build, and architecture checks; verify OpenAPI and backward compatibility for Phase 1/2 routes.
8. Produce evaluation evidence mapping every Phase 3 acceptance criterion to an automated test or documented manual check.

#### Quality gates

```text
black --check .
ruff check .
mypy backend
alembic upgrade head
pytest
cd frontend && npm test
cd frontend && npm run build
```

Additional Phase 3 gates include Celery eager unit tests, real RabbitMQ worker integration tests in CI, golden IR/model comparisons, deterministic reruns, OpenAPI contract snapshots, and bounded performance/security fixture runs. CI must add RabbitMQ only when real worker integration begins; unit tests must not require a live broker.

#### Acceptance criteria

- The full supported vertical slice completes through a real worker and publishes a queryable model.
- Failure, cancellation, retry, replay, and restart behavior preserve authoritative state.
- Golden outputs are stable and explain every architecture fact through evidence.
- No cross-project leakage, secret leakage, arbitrary execution, or unbounded collection endpoint is observed.
- Phase 1/2 Python APIs and frontend regressions remain green.
- All phase acceptance criteria in §4.14 have evidence before Phase 3 is marked complete.

---

### 4.12 File-by-file implementation specifications

Path status was rechecked against the repository on 2026-11-05. In the tables, **Modify** means the file is verified to exist; **Create (proposed)** means the path does not exist and is a planning proposal. M1 paths under `backend/platform/analysis/`, `backend/worker/`, and `tests/p3/analysis/` now exist and are frozen/complete as recorded in §5. M2-specific `inspection/`, `syntax/`, `frameworks/`, handlers, contract, tests, and fixtures remain absent. Existing frontend paths remain planned for M5. Planning created no application file.

#### Module 1 files

The authoritative, implementation-ready M1 file plan is organized by batch in §§4.6.5–4.6.7. Those tables distinguish verified existing files from proposed paths and define responsibilities, dependencies, tests, acceptance criteria, exact implementation order, and handoffs. They supersede the earlier phase-level M1 file summary so there is only one M1 implementation source of truth.

#### Module 2 files

The authoritative M2 file plan is in §4.7.7. It consolidates generic extraction by language family and framework enrichment by ecosystem to avoid the earlier over-fragmented `engine/` and one-file-per-framework proposal. That table identifies every verified existing modification point and every proposed path, with responsibilities and tests.

#### Module 3 files

| Path | Action | Components / responsibility | Dependencies and verification |
|---|---|---|---|
| `backend/platform/analysis/ir/model.py` | Create (proposed) | Versioned immutable IR entities, relationships, evidence, unresolved/conflicting facts, and statistics; no duplicate diagnostic type. | F3 invariant/schema/shared-diagnostic tests. |
| `backend/platform/analysis/ir/normalizer.py` | Create | Parser/analyzer fact normalization and deterministic deduplication. | Cross-analyzer/order tests. |
| `backend/platform/analysis/ir/symbols.py` | Create | Analysis-scoped module/symbol tables and exact resolution. | alias/qualified/ambiguous tests. |
| `backend/platform/analysis/ir/relationships.py` | Create | Imports/calls/inheritance/routes/components/dependency resolution. | Resolved/unresolved/cycle tests. |
| `backend/platform/analysis/ir/evidence.py` | Create | Evidence identity, strength, conflict, provenance merge rules. | provenance/conflict/redaction tests. |
| `backend/platform/analysis/ir/validator.py` | Create | Schema/reference/type/duplicate/provenance validation. | invalid fixture matrix. |
| `backend/platform/analysis/ir/serializer.py` | Create | Stable JSON-compatible serialization and schema-version load. | round-trip/golden byte stability. |

#### Module 4 files

| Path | Action | Components / responsibility | Dependencies and verification |
|---|---|---|---|
| `backend/platform/analysis/identity/logical_ids.py` | Create | Canonical namespace-safe logical ID builders; UUID remains separate. | collision/path/version tests. |
| `backend/platform/analysis/identity/registry.py` | Create | Analysis-scoped identity registry and deterministic merge/collision handling. | order/concurrency/isolation tests. |
| `backend/platform/analysis/identity/resolver.py` | Create | IR entity/fact -> logical Architecture identity resolution. | duplicate/ambiguous/unresolved tests. |
| `backend/platform/analysis/architecture/model.py` | Create | Architecture Version, entity, relationship, evidence, hierarchy, completeness domain. | invariant tests. |
| `backend/platform/analysis/architecture/builder.py` | Create | Valid IR -> architecture semantics and basic findings. | fixture/golden tests. |
| `backend/platform/analysis/architecture/validator.py` | Create | Schema, references, hierarchy, identity, evidence, publication validation. | invalid model matrix. |
| `backend/platform/analysis/architecture/serializer.py` | Create | Stable canonical model/API projection serialization. | round-trip/determinism tests. |
| `backend/platform/analysis/repositories/architecture_repo.py` | Create | Build/persist/publish/query contract for immutable versions. | fake/SQLAlchemy contract tests. |
| `backend/platform/analysis/infra/architecture_model.py` | Create (proposed) | SQLAlchemy Architecture Version/entity/relationship/evidence models owned solely by M4. | Constraints/FKs/indexes/version isolation. |
| `backend/platform/analysis/infra/architecture_repository.py` | Create | SQLAlchemy normalized persistence and atomic publication. | transaction/immutability/query tests. |
| `backend/platform/analysis/application/result_dto.py` | Create (proposed) | Finding projection plus Architecture summary/entity/relationship/evidence response DTOs. | Stable OpenAPI, pagination, safe evidence fields. |
| `backend/platform/analysis/application/result_service.py` | Create | Authorized diagnostic-as-finding and Architecture entity/relationship/evidence query service. | RBAC/pagination/not-ready tests. |
| `backend/platform/analysis/application/result_dependencies.py` | Create (proposed) | DI providers for M4 repositories, publication, and result-query services without expanding M1 lifecycle providers. | Dependency override and ownership tests. |
| `backend/platform/analysis/application/publication_service.py` | Create (proposed) | Idempotent build/validate/persist/publish transaction and lifecycle completion handoff to M1. | rollback, retry, state-race, immutable publication tests. |
| `backend/api/v1/analysis_results.py` | Create (proposed) | M4-owned findings and Architecture result-query endpoints. | API/RBAC/pagination/not-ready/ownership tests. |
| `backend/api/v1/router.py` | Modify | Mount the M4 result router separately from the M1 lifecycle router. | OpenAPI ownership and route-regression tests. |
| `backend/api/error_handlers.py` | Modify | Map M4 result-readiness and Architecture validation/publication errors through the existing structured contract. | Error status/shape and no-internal-detail tests. |
| `backend/infra/migrations/env.py` | Modify | Register M4 Architecture models in Alembic metadata without moving them into M1 lifecycle models. | Autogenerate drift and import-order checks. |
| `backend/infra/migrations/versions/<revision>_create_architecture_model_tables.py` | Create (proposed) | Add Architecture Version/entity/relationship/evidence tables separately from M1 lifecycle tables. | Upgrade/downgrade, constraints, publication tests. |

#### Module 5 files

| Path | Action | Components / responsibility | Dependencies and verification |
|---|---|---|---|
| `frontend/src/services/analysisService.js` | Create | Analysis CRUD/status/cancel/findings/architecture query methods and SSE URL/event adapter. | Contract tests against frozen routes. |
| `frontend/src/App.jsx` | Modify | Parse/render protected analysis detail route without breaking current routes. | Route regression tests. |
| `frontend/src/pages/RepositoryDetailPage.jsx` | Modify | Add Analysis tab/history/start entry using selected revision and RBAC. | Existing ingestion/revision regressions. |
| `frontend/src/pages/AnalysisDetailPage.jsx` | Create | Own status/results lifecycle, REST reconciliation, SSE subscription, terminal cleanup. | State/reconnect tests. |
| `frontend/src/components/analysis/StartAnalysisModal.jsx` | Create | Revision/config selection, validation, duplicate-submit prevention. | Accessibility/error tests. |
| `frontend/src/components/analysis/AnalysisHistory.jsx` | Create | Paginated repository analysis history and states. | Loading/empty/filter/pagination tests. |
| `frontend/src/components/analysis/AnalysisProgress.jsx` | Create | Stage/progress/cancel/warning/error representation. | State matrix tests. |
| `frontend/src/components/analysis/AnalysisSummary.jsx` | Create | Result versions, completeness, language/framework/entity/relationship metrics. | Partial/empty/result-not-ready tests. |
| `frontend/src/components/analysis/FindingsPanel.jsx` | Create | Paginated/filterable deterministic findings and evidence links. | Filters/retry/accessibility. |
| `frontend/src/components/analysis/ArchitectureExplorer.jsx` | Create | Read-only hierarchy/entity/relationship explorer; no canonical diagram semantics. | Selection/pagination/keyboard tests. |
| `frontend/src/components/analysis/EntityDetails.jsx` | Create | Safe metadata, inbound/outbound relationships, provenance/evidence references. | Missing/unknown/evidence tests. |
| `frontend/src/styles/analysis.css` | Create | Existing dark-theme-compatible responsive analysis UI/focus/overflow states. | Visual/manual and contract checks. |
| `frontend/package.json` | Modify | Add Phase 3 frontend test script entry; add no graph dependency under default plan. | `npm test`, `npm run build`. |
| `frontend/tests/phase3Analysis.test.js` | Create | Service, route, lifecycle, SSE, RBAC, pagination, and UI-state contracts. | Node test harness. |

#### Module 6 files and fixtures

| Path | Action | Components / responsibility | Dependencies and verification |
|---|---|---|---|
| `tests/p3/conftest.py` | Create | Phase 3 users/projects/repositories/revisions/artifacts/storage/queue fixtures. | Isolation and cleanup. |
| `tests/p3/test_analysis_domain.py` | Create | Section 9 Analysis/Job/Stage states, versions, configuration, shared diagnostics. | Unit gate. |
| `tests/p3/test_analysis_input.py` | Create | Phase 2 boundary/lazy reads/tampering/order. | Integration gate. |
| `tests/p3/test_analysis_persistence.py` | Create | M1 lifecycle models/repos/constraints/transitions/events/diagnostic recording only. | PostgreSQL gate. |
| `tests/p3/test_analysis_api.py` | Create | M1 lifecycle REST/SSE auth/RBAC/errors/pagination/OpenAPI. | API gate. |
| `tests/p3/test_analysis_jobs.py` | Create | Queue/task/retry/duplicate/crash/cancel behavior. | eager + RabbitMQ integration. |
| `tests/p3/test_analysis_sse.py` | Create | sequence/replay/reconnect/terminal events. | Streaming gate. |
| `tests/p3/test_detection_and_parsers.py` | Create | languages/runtimes/frameworks/parser failure. | Module 2 gate. |
| `tests/p3/test_ir.py` | Create | normalization/resolution/evidence/validation/golden output. | Module 3 gate. |
| `tests/p3/test_identity_architecture.py` | Create | M4 identity/build/persistence/validation/serialization/publication. | Module 4 gate. |
| `tests/p3/test_architecture_api.py` | Create (proposed) | M4 findings and Architecture result-query RBAC, pagination, evidence safety, and readiness. | Module 4 API gate. |
| `tests/p3/test_phase3_e2e.py` | Create | Full real-worker analysis vertical slice. | Phase gate. |
| `tests/p3/test_determinism.py` | Create | repeated/shuffled/concurrent semantic equivalence. | Phase gate. |
| `tests/p3/test_security_limits.py` | Create | isolation, secrets, traversal, code/network denial, limits. | Security gate. |
| `tests/p3/test_performance.py` | Create | measured stage/time/memory/count baselines with approved thresholds. | Performance gate. |
| `tests/fixtures/p3/<framework>/` | Create | Six supported framework repositories plus mixed/malformed/malicious fixtures. | Analyzer/golden tests. |
| `tests/fixtures/p3/expected/<fixture>.ir.json` | Create | Versioned expected canonical IR. | Golden regression. |
| `tests/fixtures/p3/expected/<fixture>.architecture.json` | Create | Versioned expected canonical Architecture Model. | Golden regression. |

### 4.13 Testing strategy by layer

| Layer | Primary focus |
|---|---|
| Domain unit | States, invariants, identities, schema/version rules, evidence and merge semantics. |
| Adapter unit | Parsers, detectors, framework extraction, queue/storage adapters with fakes. |
| Persistence integration | PostgreSQL constraints, transitions, concurrency, publication, migration. |
| Contract/API | DTOs, OpenAPI, structured errors, RBAC, pagination, 202/cancel/SSE semantics. |
| Worker integration | Real RabbitMQ/Celery delivery, duplicate/retry/crash/cancellation and DB authority. |
| Golden repository | Expected IR/Architecture output for supported ecosystems and regressions. |
| Frontend contract | Services, routing, status/reconnect, RBAC, loading/error/empty/partial states. |
| End to end | Auth -> revision -> analysis -> worker -> published model -> frontend-compatible API. |
| Security/performance | Isolation, secret redaction, untrusted source, limits, stage metrics and approved budgets. |

### 4.14 Phase-level acceptance criteria

Phase 3 is complete only when all are verified:

1. A user with permitted Project access can asynchronously analyze a specific immutable Express-owned revision; a Viewer cannot start/cancel but can read permitted results.
2. PostgreSQL is authoritative for analysis/job/stage/event/model state; RabbitMQ/Celery outages or duplicate delivery cannot corrupt lifecycle state.
3. AnalysisInput validates the full project/repository/revision/artifact chain and lazily reads immutable content through the authenticated Express platform API.
4. Python, JavaScript, TypeScript, JSX, and TSX are classified and parsed through common adapters; all six approved frameworks have evidence-backed enrichment.
5. Malformed/unsupported files degrade explicitly without fabricating facts or unnecessarily failing independent files.
6. IR is versioned, schema-valid, parser-neutral, deterministic, evidence-preserving, and contains explicit unresolved/conflicting facts.
7. Identity resolution is deterministic and order-independent; duplicate/ambiguous/collision behavior is explicit.
8. A valid Architecture Version is atomically published, immutable, complete with safe metadata/evidence, and traceable to analysis/snapshot/config/analyzer/schema versions.
9. Findings are deterministic diagnostics/facts, not AI-generated recommendations.
10. REST returns authoritative state/results; SSE reconnect/replay reconciles with REST and stops at terminal state.
11. The frontend supports start/history/status/progress/cancel/findings and basic architecture exploration with complete loading/error/empty/partial states.
12. No source code execution, secret leakage, cross-project leakage, absolute-path identity, unbounded endpoint, or unsafe parser behavior is present.
13. Repeated and shuffled executions of the same inputs produce semantically equivalent golden IR and Architecture outputs.
14. Phase 1/2 Python tests, frontend regressions, migrations, Black, Ruff, Mypy, Pytest, and production build remain green.
15. The backend-authority/parser/visualization decisions in §7.3 are approved and reflected without silent architectural drift.

---

## 5. Execution Ledger

| Module | Status | Evidence | Remaining work |
|---|---|---|---|
| M1 — Analysis Foundation & Execution | **FROZEN and COMPLETE (F1 v1.0.0)** | All three batches and hardening fixes are complete. ADR-0001 enforces separate MongoDB/PostgreSQL ownership and authenticated APIs in both directions. Python 3.14 uses AnyIO 4.15.1 and Starlette 1.10.0. The full repository suite passes with every warning treated as an error: `497` tests. PostgreSQL migration/constraint/concurrency and live RabbitMQ/Celery dispatch, recovery, failure, and retry smoke passed. `392` Express tests pass; Ruff, strict Mypy (on Linux CI; on Windows, mypy backend reports 14 pre-existing POSIX signal attribute errors in orchestrator.py guarded by hasattr), and full-project Black pass. | None for M1. Any incompatible F1/ADR change requires versioning and owner approval. Do not fold M2 work into M1. |
| M2 — Inspection & Language Analysis | **APPROVED WITH FOLLOW-UPS (Batches 1 & 2 Remediated, Hardened & Finalized)** | **Batch 1 (Verified & Hardened):** Normative F2 contract (`docs/architecture/contracts/f2-repository-inspection-syntax-v1.md`); pinned `tree-sitter==0.25.2`, `tree-sitter-javascript==0.25.0`, `tree-sitter-typescript==0.23.2`; M2 config settings wired via `ParserExecutor.from_settings()` (`parser_per_file_timeout_seconds=30.0`, `parser_max_file_size_bytes=5242880`, `parser_max_memory_mb=512`, `parser_max_stderr_bytes=1048576`); syntax models, `PythonAstAdapter` (Python `ast`), `TreeSitterJsTsAdapter` (JS, TS, JSX, TSX); diagnostic secret/credential redaction in `create_parsing_diagnostic`. Hardened `ParserExecutor` (REV-001/016/017): mandatory Win32 Job Object configuration with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (0x2000) and strict Win32 return checks; mandatory POSIX `RLIMIT_AS` resource-limit propagation; fail-closed isolation availability probe (REV-022); truly bounded streaming reader (`_communicate_bounded`) with early child termination on stdout/stderr overflow; and unified `_cleanup_process` on all termination/timeout paths. Benchmarks measured on representative & boundary fixtures (max fact density: 18,301 facts/MB; tracemalloc peak heap: 133.7MB; max serialized F2: 6,870 KB for 1MB Python; proposed caps: 25,000 facts/artifact, 250,000 facts/analysis, 50 MiB F2 bytes). **Batch 2 (Verified & Remediated):** `InventoryBuilder` with `pathspec` gitignore matching, exhaustive role/outcome mapping across all 16 `ArtifactCategory` values (`failed` is outcome-only), generated/minified code exclusion policy (`GENERATED_ARTIFACTS` & `is_generated` assigned `IGNORED`), metadata-only sensitive file classification with zero content reads, coverage calculation. `DetectionService` with safe manifest parsing (`package.json`, `requirements.txt`) strictly gated by inventory eligibility (zero reads for ignored/excluded manifests like `node_modules`), strict UTF-8 decoding with `AnalysisDiagnostic` emission, language/runtime detection, preliminary framework candidate detection (Django, Flask, FastAPI, Express, NestJS, Next.js), and verified shuffled-order canonical JSON byte determinism for both inventory and full framework/evidence detection. **Checks Passed:** Sequential Pytest: 45 M2 tests across 4 suites passed (`test_m2_contracts.py`: 6, `test_m2_parsers.py`: 26 passed [1 skipped on Windows per REV-020], `test_m2_benchmarks.py`: 2, `test_m2_inventory_detection.py`: 11) + `test_m1_architecture.py`: 7 passed (total 52 passed, 1 skipped); `mypy --follow-imports=silent backend/platform/analysis/inspection backend/platform/analysis/syntax`: 0 issues in 11 files; `ruff check`: 0 errors; `black --check`: passed (0 reformats needed across repo). Full suite: 541 passed, 1 skipped, 1 pre-existing environmental symlink failure. | Execute Batch 3 (Generic syntax extraction across all 5 syntax variants, single-pass parsing, canonical UTF-8 coordinates, atomic cap enforcement) and Batch 4 (Framework enrichment, M1 stage adapters, attempt-scoped F2 handoff, and recovery rebuild). Owner approval of proposed benchmark caps (25,000 facts/artifact, 250,000 facts/analysis, 50 MiB serialized F2) is required before full Batch 3 extraction. |
| M3 — IR & Semantic Analysis | Planned; not implemented | Master IR/identity rules inspected; no current IR code exists. | Approve F3 IR v1; implement/validate/golden-test. |
| M4 — Identity & Architecture Model | Planned; not implemented | Master canonical model/publication rules inspected; no current model code exists. | Approve F3 and M4 persistence; implement model persistence/publication/result APIs. |
| M5 — Frontend Integration | Planned; blocked on M4 result contracts | Express is the approved frontend/platform boundary and ADR-0001 is accepted. | Freeze lifecycle/result proxy DTOs, delegated errors, and SSE relay after M4 result APIs are defined. |
| M6 — Integration & Evaluation | Planned; frontend E2E waits for M4/M5 | CI quality commands and current test organization verified. | Build backend fixtures/goldens throughout; browser-to-worker E2E follows the accepted service boundary once result/proxy contracts exist. |

Phase 3 M1 is formally frozen. No M2 parsing, M3 IR, M4 Architecture persistence/results, or frontend analysis work was started, preserving strict module boundaries.

---

## 6. Decisions Preserved from Earlier Phases

- Project is the authorization/isolation boundary; no Organization domain.
- Resource persistence IDs are UUID v4; API serialization hides infrastructure IDs.
- Repository access derives from Project access and the Owner/Admin/Developer/Viewer matrix.
- Production authentication uses Bearer JWTs; the canonical user claim is `sub`; inactive/deleted users are rejected.
- Refresh tokens are stateful, hashed, rotated atomically, and single-use.
- Bcrypt input beyond 72 UTF-8 bytes is rejected rather than silently truncated.
- Canonical ingestion is Project/Repository scoped and produces immutable revisions/artifacts with content-addressed storage.
- Active ingestion concurrency, source validation, archive/path safety, storage abstraction, and structured error responses remain intact.
- The MERN implementation is retained as a completed parallel platform deliverable; it is not deleted or extended for Phase 3.
- ADR-0001 fixes Express as the frontend/platform authority and Python/PostgreSQL as the analysis authority, with authenticated internal APIs and no cross-database access.

---

## 7. Decisions, Risks, Assumptions, and Handoff

### 7.1 Frozen M1 decisions and later-phase decisions

1. **Frozen:** Express `RepositoryRevision.id` is `snapshot_id`; no duplicate snapshot entity exists in M1.
2. **Frozen:** F1 implements Section 9 exactly: `PARTIAL` is nonterminal/incomplete, `TIMEOUT` is persisted then transitions to `FAILED`, and Job/Stage state remains distinct from Analysis state.
3. Use one Celery orchestration task per analysis in the first implementation while persisting stage records; split stages into separate jobs later without changing frozen domain contracts.
4. Approve one shared `AnalysisDiagnostic` contract, owned/versioned and lifecycle-recorded by M1, emitted by M2–M4, and exposed as finding DTOs only through M4 result-query APIs.
5. Persist Architecture Versions in M4-owned normalized PostgreSQL tables with stable logical IDs and UUID v4 row IDs; keep IR in-memory/serializable but not persist it by default.
6. Use durable PostgreSQL AnalysisEvent rows for SSE replay and sequence; SSE polls/subscribes to that durable stream rather than treating an in-memory broadcaster as truth.
7. Interpret P3 “visualization” as summary/hierarchy/entity/relationship/evidence exploration. Defer canonical node-edge Diagram Specification + ELK + React Flow to Phase 5.
8. **Frozen for M2:** use Python built-in `ast` plus `tree-sitter==0.25.2`, `tree-sitter-javascript==0.25.0`, and `tree-sitter-typescript==0.23.2` behind replaceable adapters and the approved OS isolation boundary.

### 7.2 Principal risks and mitigations

- **Backend split:** Express/Mongo and Python/PostgreSQL intentionally own separate state. ADR-0001 fixes authenticated delegation, opaque resource mapping, and bounded artifact access. Mitigation: preserve that contract; never bridge by trusting client IDs, directly reading the other database, or inventing synchronization.
- **Parser compatibility/safety:** The approved Tree-sitter pins install and parse representative syntax on CPython 3.14.6, but native parsers and Python `ast` still face crash/resource risks, grammar lag, non-attested package artifacts, and future API churn. Mitigation: exact pins, fail-closed OS child isolation with hard bounds/no network/minimal environment/closed unrelated handles, version/ABI metadata, malformed/deep/timeout/isolation tests, dependency scanning, and replaceable adapters.
- **Scope size:** Six frameworks plus lifecycle/IR/model/frontend is large. Mitigation: freeze contracts first, implement generic analyzers before framework enrichment, use fixtures/goldens, parallelize only behind stable interfaces.
- **Nondeterminism:** concurrent analyzers, set/dict order, or evidence arrival can change output. Mitigation: canonical keys/sorting, analysis-scoped registries, shuffled-order tests, stable serialization.
- **Queue/database dual-write:** DB commit can succeed while publish fails. Mitigation: persist dispatch state, identifier-only idempotent messages, publish-failure state/recovery, duplicate worker guards.
- **Partial failures:** one parser/framework failure could either hide coverage or fail too much. Mitigation: explicit artifact roles/outcomes, shared per-artifact diagnostics, coverage metrics, generic fallback after enrichment failure, and `COMPLETED_WITH_WARNINGS` only with a later valid model.
- **Non-persisted F2 handoff:** frozen F1 does not persist arbitrary stage outputs. M2 owns deterministic production/reconstruction, M3 only consumes the attempt-scoped immutable result, and M1 orchestration owns recovery after handoff loss. The approved internal recovery-only path runs the registered M2 producer with the same immutable input/configuration/version tuple without reopening completed stages, changing lifecycle state, or adding public event vocabulary; mismatch or failure stops before M3.
- **Resource exhaustion/malicious source:** parser bombs, native-parser compromise, huge repositories, secrets, descriptor/credential inheritance, or path tricks. Mitigation: reuse Phase 2 limits, lazy/batched reads, fail-closed OS isolation and hard termination, bounded IPC, no network, minimal environment, closed unrelated handles, redaction, no execution, and adversarial security fixtures.
- **Architecture over-granularity:** every symbol could become a visible node. Mitigation: keep symbols in IR/evidence and promote only architecturally meaningful entities.
- **Schema/version churn:** premature v1 changes can invalidate goldens and consumers. Mitigation: freeze version constants and contracts before module implementation; incompatible changes require version bump/change control.

### 7.3 Frozen M2 approval record

The owner approved the following as the frozen M2 planning baseline. No M2 implementation has started:

1. **Parser pins:** built-in Python `ast` plus `tree-sitter==0.25.2`, `tree-sitter-javascript==0.25.0`, and `tree-sitter-typescript==0.23.2` on CPython 3.14.
2. **Corrected F2 model:** `RepositoryInspectionResult`, separate `ArtifactAnalysisRole` and `ArtifactProcessingOutcome` (`failed` is outcome-only), tagged `SyntaxFact`, document-local fact keys, diagnostic references, and canonical ordering.
3. **Canonical source coordinates:** decoded logical source re-encoded to UTF-8; zero-based absolute bytes, one-based lines, zero-based UTF-8 byte columns, end-exclusive ranges; original encoding retained as metadata, BOM excluded, CRLF preserved, PEP 263 non-UTF-8 Python decoded strictly, and invalid encodings fail explicitly.
4. **Eligibility and sensitive policy:** repository-relative POSIX `gitwildmatch`; excludes cannot bypass safety; `.gitignore` is advisory; prohibited-sensitive files are classified from permitted metadata/path signals without content reads; permitted parsing exposes only allowlisted structural literals.
5. **Cap approval gate:** Batch 1 records deterministic fact count, serialized-byte, peak-RSS, and timing benchmarks on representative and 5 MiB boundary fixtures. The owner approves explicit per-artifact, per-analysis, and serialized-F2 caps before full Batch 3 extraction. Cap failures are diagnostic and explicit, never silently truncated.
6. **Detection/enrichment order:** metadata/manifest/path framework candidates before parsing; exactly one generic parse per eligible artifact; syntax facts finalize detection; enrichment reuses facts and never reparses.
7. **Handoff and recovery ownership:** M2 produces immutable F2 and M3 only consumes the supplied result. If the non-persisted handoff is lost, M1 orchestration invokes the registered M2 producer through an internal recovery-only rebuild path using the same immutable `AnalysisInput`, effective configuration, and exact parser/grammar/analyzer versions. M3 neither imports nor invokes M2 reconstruction.
8. **Recovery invariants:** recovery repopulates only the attempt-scoped handoff. Already-completed Stage rows and frozen Analysis/Job/Stage states and transitions remain unchanged. Rebuilt canonical F2 must be byte-equivalent; a version/configuration mismatch or rebuild failure fails the active job before M3. F2 is not newly persisted, terminal stages are not reset, and frozen F1 is not modified.
9. **Event compatibility:** recovery adds no public `AnalysisEventType`, event payload, or other public event vocabulary. An existing event may be used only when its already-approved semantics apply; otherwise observability uses internal structured logs/metrics and safe existing diagnostics. Any new public event requires separate owner approval and contract versioning.
10. **Parser isolation:** every parser runs in an actual OS child process with hard bounded resources and IPC, forced deadline termination, no network, a minimal allowlisted environment, no inherited service/cloud/database/broker/storage credentials, sockets, or unrelated file handles, and no repository/host filesystem access beyond explicitly supplied source bytes. Production fails closed when this boundary cannot be established.

The design baseline for F2 is frozen here, while the runtime F2 v1 contract remains an implementation deliverable: Batch 1 authors the contract artifact and tests, and Batch 4 freezes runtime F2 only after M3 consumer review. Numeric fact/result caps are intentionally determined from Batch 1 benchmarks and require owner approval before Batch 3 full extraction; this is the frozen evidence-based gate, not an unresolved architectural choice. Persisting F2, resetting terminal stages, making M3 call M2, weakening parser isolation, or adding recovery event vocabulary are rejected alternatives.

Later Phase 3 gates remain and do not block the frozen M2 plan:

1. **F3 IR/Architecture freeze:** Approve IR v1, canonical ordering, unresolved/conflict behavior, promotion rules, logical-ID inputs, and golden fixtures before M3/M4 parallel implementation.
2. **Visualization scope:** Confirm that hierarchy/relationship/evidence exploration satisfies P3. If an interactive node-edge graph is required now, approve the roadmap expansion without duplicating the Phase 5 Diagram Engine.
3. **M4 persistence proposal:** Approve normalized PostgreSQL Architecture tables and non-persisted IR. A JSON-blob-only Architecture Model or persisted IR would materially change query, migration, and reproducibility trade-offs.

### 7.4 Current handoff

- **Current phase:** Phase 3 in progress; Module 1 is **FROZEN and COMPLETE** and Module 2 is **PLAN APPROVED / FROZEN — IMPLEMENTATION NOT STARTED**. Modules 3–6 remain planned.
- **Closure evidence:** The complete Python suite passes against PostgreSQL with `497 passed` and no skips or warnings, including all API/SSE/E2E and real-PostgreSQL persistence/concurrency tests. `392` Express tests pass. Alembic is at `c4b1897a0f12`; verified M1 foreign keys are internal only. Live RabbitMQ/Celery worker ping, recovery-task success, explicit failure, and transient-database retry/exhaustion passed. Ruff, strict Mypy, and full-project Black pass.
- **Python 3.14/TestClient resolution:** AnyIO is pinned to `4.15.1`, which contains the Python 3.14 blocking-portal context fix. Starlette is pinned to `1.10.0`, removing its deprecated AnyIO alias. SQLite test engines are explicitly disposed, so the full suite also passes with all resource warnings promoted to errors. Compatible `cryptography==49.0.0` and `python-dateutil==2.9.0.post0` pins satisfy the shared environment, and `pip check` reports no broken requirements. The managed sandbox still rejects the event loop's AF_UNIX cross-thread wakeup with `EPERM`, so TestClient suites must run outside that sandbox restriction.
- **Frozen M1 Interfaces for M2:**
  - `AnalysisInput` & `AnalysisArtifact` (`backend.platform.analysis.domain.input`): immutable snapshot boundary with lazy `ArtifactContentReader`.
  - `AnalysisExecutionContext` (`backend.platform.analysis.application.orchestrator`): context passed to stage handlers providing access to input, progress reporting, diagnostic recording, and cooperative cancellation checking (`is_cancellation_requested()`).
  - `AnalysisStageHandler` & `StageHandlerRegistry` (`backend.platform.analysis.application.registry`): stage execution contract and registration container.
  - `AnalysisDiagnostic` (`backend.platform.analysis.domain.diagnostic`): shared cross-module diagnostic model with severity, categorization, code, and bounded source location.
  - Lifecycle state machine: Section 9 states, optimistic concurrency control, terminal immutability, and 30m timeout enforcement.
- **Branch:** `feature_mannan` verified.
- **Last verified baseline (2026-11-05):** `pytest.ini` promotes all warnings to errors, and the normal `pytest -q` command passed all `497` tests on branch `feature_mannan`; PostgreSQL and RabbitMQ containers were healthy after verification.
- **M2 planning evidence:** CPython 3.14.6 is the active/CI runtime and no Tree-sitter dependency is currently installed. Temporary isolated installs verified `tree-sitter` 0.25.2 and 0.26.0 with official JavaScript 0.25.0 and TypeScript/TSX 0.23.2 grammars. The approved 0.25.2 combination parsed representative ESM, CommonJS/Express, JSX, TypeScript decorators/interfaces, TSX/React composition, and recoverable malformed input. Temporary environments were outside the repository and no application file/dependency changed.
- **Recommended next action:** Stop planning. Begin M2 Batch 1 only under a separate implementing task; do not change frozen F1, start Batch 1 from this planning task, or begin M3. Before Batch 3 full extraction, review and approve the numeric caps produced by the Batch 1 benchmark gate.
