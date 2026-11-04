# PROJECT_CONTEXT.md — StackSense Engineering Context

> Repository handoff maintained through the planning and implementing skills.
> Last updated: 2026-11-04 on branch `feature_mannan`.

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

- The working tree was clean and the active branch was `feature_mannan` when this plan was produced.
- Python uses FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, repository interfaces, dependency injection, immutable domain dataclasses, and structured `StackSenseError` responses.
- Phase 2 already persists immutable `RepositoryRevision` records and per-revision `RepositoryArtifact` metadata. Artifact bytes are read through `StorageService.get(storage_key)`; Phase 3 must consume that boundary rather than reacquire or mutate repositories.
- Phase 2 ingestion is currently synchronous. There is no analysis domain, worker process, Celery/RabbitMQ wiring, analysis persistence, IR, Architecture Model, or Phase 3 API.
- `requirements.txt` contains no Celery/RabbitMQ client or JavaScript/TypeScript parser binding. `infra/docker/compose.yml` currently starts PostgreSQL only.
- The React frontend has a repository detail route with ingestion, revisions, and artifacts. It currently proxies all `/api` traffic to Express on port 5000.
- Python and Express use separate persistence systems. Their users, Projects, repositories, revisions, artifacts, and sessions are not synchronized. The authority split is approved, but the service-authentication, resource-reference, artifact-availability, and delegated-authorization contract remains an M1/M5/M6 integration blocker; see §4.6.9 and §7.3.
- Verified existing Python extension points include `backend/platform/config.py`, `backend/platform/errors.py`, `backend/platform/dependency_injection.py`, `backend/api/v1/router.py`, `backend/api/error_handlers.py`, `backend/infra/migrations/env.py`, and the Phase 2 capability packages under `backend/platform/`.
- `backend/platform/analysis/`, `backend/worker/`, and `tests/p3/` do not exist. They are proposed locations following the active `backend/platform/<capability>/{domain,application,repositories,infra}` and `tests/p<phase>/` conventions. Empty top-level placeholders such as `backend/analysis/`, `backend/application/`, and `backend/domain/` are not treated as implemented Phase 3 architecture.
- Baseline evidence gathered during planning:
  - `python -m pytest --collect-only -q` collected 330 Python tests.
  - `cd frontend && npm test` passed all four configured scripts.
  - `cd frontend && npm run build` passed with 63 transformed modules.
  - An accidental root-level `npm test` failed because the repository root intentionally has no `package.json`; the correct frontend command above passed.

---

## 2. Global Constraints and Approved Architecture

1. **Project-first isolation:** `User -> Project -> Repository`. No Organization entity or organization-scoped authorization may be introduced. Analysis, jobs, results, architecture versions, events, and findings must carry and enforce `project_id`.
2. **Python-only Phase 3 backend:** Modules 1–4 are implemented under `backend/`; no Phase 3 routes, models, jobs, or analysis logic are added to Express.
3. **Phase 2 boundary:** A `RepositoryRevision` is the immutable snapshot identity. `RepositoryArtifact` plus `StorageService` is the Phase 3 source boundary. Phase 3 does not clone repositories, extract uploads, or rewrite artifacts.
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
17. **Integration ADR required:** The approved authority split does not define service authentication, delegated identity/authorization context, resource-reference mapping, artifact availability, error propagation, request/audit correlation, or SSE relay. These security and data contracts require owner-approved ADR detail before the affected M1 work is implemented; no synchronization or trust mechanism may be invented.
18. **Project-first conflict rule:** `master.txt` §0 and the current code establish `User -> Project -> Repository`, with no Organization domain. Any remaining Organization wording is historical unless an approved ACR/ADR explicitly restores it.
19. **Change control:** Material deviations from `master.txt`, the Phase 3 contracts below, or the approved Express/Python authority split require explicit approval/ACR treatment before implementation.

---

## 3. Phase Index

| Phase | Status | Concise retained context |
|---|---|---|
| Phase 1 — Engineering Foundation | Completed | Python/FastAPI bootstrap, PostgreSQL/Alembic, DI, error/logging foundation, CI, Black/Ruff/Mypy/Pytest, and React foundation. |
| Phase 2 — Project & Repository Platform (Python) | Completed | Identity/JWT, Project-scoped RBAC, projects, repositories, ingestion, immutable revisions/artifacts, safe acquisition, classification, and storage abstraction. This is Phase 3's backend input contract. |
| Phase 2 — MERN migration | Completed, retained separately | Express/MongoDB platform and the current React integration satisfy the college MERN requirement. It is not the Phase 3 implementation target. Verified historical work includes active-user auth, refresh rotation, RBAC, repository ingestion, username collaborator lookup, self-management prevention, and frontend API coverage. |
| **Phase 3 — Analysis Engine & Architecture Model** | **Planned; not implemented** | Six-module plan in §4. Backend Modules 1–4 are Python-only. Express remains the frontend/platform boundary and delegates analysis to Python. Module 6 validates the complete vertical slice. |
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
- `RevisionRepository` and `ArtifactRepository` for snapshot metadata; both require additional exact lookup/count/streaming methods rather than unbounded list calls.
- `StorageService.get` for lazy artifact bytes.
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
  content_reader: ArtifactContentReader   # lazy, bounded StorageService adapter
```

`AnalysisArtifact` carries artifact ID, normalized repository-relative path, content hash, size, Phase 2 category/support level, and storage key. The factory must verify that project, repository, revision, and every artifact agree; reject mutable/missing snapshots; sort deterministically; never expose absolute storage paths; and never preload the whole repository.

#### 4.4.2 Lifecycle and execution contract

- The Analysis state vocabulary is the Section 9 vocabulary: `CREATED`, `QUEUED`, `RUNNING`, `PARTIAL`, `COMPLETED`, `COMPLETED_WITH_WARNINGS`, `FAILED`, `CANCEL_REQUESTED`, and `CANCELLED`, with `TIMEOUT` preserved as the explicit timeout transition shown in §9.7/§9.38.
- Approved golden paths are `CREATED -> QUEUED -> RUNNING -> COMPLETED`, `CREATED -> FAILED`, `QUEUED -> CANCELLED`, `RUNNING -> CANCEL_REQUESTED -> CANCELLED`, `RUNNING -> TIMEOUT -> FAILED`, and `RUNNING -> PARTIAL -> COMPLETED_WITH_WARNINGS`. Additional transitions must be justified against Section 9 and added to the frozen transition matrix before implementation.
- `PARTIAL` means a usable but incomplete result exists. It is not listed as a primary terminal state in §9.9 and must never be presented as complete. The persisted completeness record must say what was analyzed, failed, unsupported, excluded, and potentially incomplete. Finalization may reach `COMPLETED_WITH_WARNINGS` only when the Architecture Model is valid; otherwise the analysis reaches `FAILED`.
- `TIMEOUT` is not a successful or terminal result. It records the explicit timeout step required by §9.7/§9.38 and must deterministically finalize as `FAILED`, retaining timeout category, stage, configured limit, and safe diagnostic metadata.
- Primary terminal states remain exactly `COMPLETED`, `COMPLETED_WITH_WARNINGS`, `FAILED`, and `CANCELLED`. They cannot silently return to `RUNNING`.
- Job states are a **proposed execution detail**, not an approved replacement for Analysis states: `PENDING`, `QUEUED`, `RUNNING`, `RETRYING`, `COMPLETED`, `FAILED`, `CANCELLED`. They require approval with the M1 persistence contract.
- Stage state is an F1 freeze decision: Section 9 lists `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `SKIPPED`, while Appendix C also includes `QUEUED` and `CANCELLED`. No enum is implemented until the owner resolves the conflict; cancellation/timeout metadata must remain distinct from Analysis-state semantics.
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
| **F1 — M1 -> M2 execution/input boundary** | M1 owns; M2 consumes | `AnalysisInput`, `AnalysisArtifact`, bounded `ArtifactContentReader`, effective configuration/resource limits, stage reporting, `AnalysisDiagnostic`, evidence reference, cancellation checkpoint, deterministic artifact ordering. | Approve Section 9 transition matrix including `PARTIAL`/`TIMEOUT`; approve revision-as-snapshot boundary, M1 job states, diagnostic schema/version, queue message identity, and Phase 2 repository/storage lookup additions. | M1 persistence/worker/API work and M2 parser spike/inventory implementation may proceed independently behind contract tests. |
| **F2 — M2 -> M3 syntax/evidence boundary** | M2 owns; M3 consumes and signs off | `SyntaxDocument`, declarations/references/source ranges, language/framework detection result, manifest facts, evidence ordering, parser failure representation through `AnalysisDiagnostic`. | F1 frozen; parser adapter/package approved; supported syntax fact inventory and source-range semantics reviewed; fixtures cover Python/JS/TS/JSX/TSX and approved frameworks. | Language/framework adapters can proceed in parallel with M3 schema/golden-fixture work; M3 normalization cannot merge until F2 contract tests pass. |
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

- A valid Python Phase 2 revision can create one durable queued analysis and job.
- A duplicate delivery cannot execute/publish the same stage twice.
- PostgreSQL alone can reconstruct lifecycle state after API/worker restart.
- Cross-project access is rejected for every M1 lifecycle surface.
- Cancellation, retry, error, and progress behavior is explicit and test-covered.

#### 4.6.1 Verified M1 repository and architecture findings

- Existing Python extension points are `backend/platform/config.py`, `backend/platform/dependency_injection.py`, `backend/platform/errors.py`, `backend/api/v1/router.py`, `backend/api/error_handlers.py`, `backend/infra/migrations/env.py`, the shared SQLAlchemy `Base`, and the established domain/application/repository/infra layering under `backend/platform/`.
- Phase 2's immutable input records are the frozen dataclasses `RepositoryRevision` and `RepositoryArtifact`. `RevisionRepository.get_by_id`, deterministic paginated `ArtifactRepository.list_by_revision`, `RepositoryRepository.get_by_id`, and `StorageService.get/exists` are reusable read boundaries.
- `RepositoryRevision` already carries ID, Project/Repository/ingestion IDs, revision identifier, source hash, file/byte totals, and creation time. `RepositoryArtifact` already carries ID, full ownership chain, relative path, size, content hash, category, support level, internal storage key, and creation time.
- The M1 adapter must not copy or mutate Phase 2 persistence. It may page through artifact metadata and open content lazily through `StorageService`; the M2-facing contract must not expose storage keys or absolute paths.
- `backend/platform/analysis/`, `backend/worker/`, and `tests/p3/` are absent and remain proposed paths. Celery/RabbitMQ packages are absent, Compose contains PostgreSQL only, and no analysis lifecycle tables, workers, internal analysis APIs, or SSE exist.
- No ADR directory or individual ADR was found. `master.txt` describes `docs/architecture/adr/` as the intended location, but the required Express-to-Python integration ADR is not present.
- Express and Python currently maintain separate Project/Repository/Revision/Artifact persistence. Their IDs are UUID-formatted, but identity format alone is not a synchronization or authorization contract. The integration ADR must define which immutable snapshot Python reads and how Express-owned resource references map to it.
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

F1 is frozen only after owner approval and passing contract tests. Creating Python types alone does not freeze it. Contract changes after freeze require versioning, updated consumer fixtures, impact documentation, and renewed approval.

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

#### Responsibilities

1. Convert AnalysisInput artifact metadata into a deterministic analysis inventory with analysis roles (`semantic`, `configuration`, `documentation`, `metadata_only`, `ignored`, `unsupported`, `failed`).
2. Reuse Phase 2 category/support metadata while applying Phase 3 eligibility, generated/test/binary/secret policy and configured exclusions.
3. Detect Python, JavaScript, TypeScript, JSX, TSX, Python/Node/browser runtimes, and approved frameworks using weighted deterministic evidence.
4. Define parser-neutral syntax contracts and parser adapters: Python built-in `ast`; proposed Python Tree-sitter bindings for JS/TS/JSX/TSX, subject to the compatibility gate in §7.3.
5. Extract modules, packages, imports/exports, classes, functions/methods, interfaces/types, decorators, inheritance, calls/references, React components/composition, and source locations.
6. Add framework enrichment for Django, Flask, FastAPI, Express, NestJS, and Next.js without bypassing generic language extraction.
7. Capture manifests/configuration safely, redact secret values, and emit parser/detection diagnostics rather than fail the entire repository for one artifact.

#### Detector and analyzer rules

- Extension is one signal; parser compatibility, manifests, imports, entry points, and framework constructs corroborate classification.
- Framework confidence is deterministic (`confirmed`, `supported`, `unknown`) with evidence references; a package name alone is insufficient.
- Tests remain identified separately but may contribute evidence. Generated/build/cache/binary artifacts do not dominate semantic analysis.
- Parser adapters return parser-neutral `SyntaxDocument`/`SyntaxFact` objects; raw AST nodes remain adapter-internal.
- Framework analyzers enrich generic facts and preserve all supporting evidence. They do not directly create Architecture entities.
- Unsupported languages remain inventoried and contribute completeness warnings.

#### Tests

- per-language valid/invalid syntax, encoding, very large file, imports/exports, overload/disambiguation, and stable source ranges;
- deterministic language/runtime/framework detection with positive, negative, and conflicting signals;
- framework fixtures for all six approved targets;
- generated/test/secret/binary/unsupported classification and safe redaction;
- parser failure isolation, no repository code execution, no network access, and resource-limit enforcement;
- shuffled artifact order produces identical syntax/evidence output.

#### Acceptance criteria

- All approved source variants produce parser-neutral evidence or explicit diagnostics.
- One malformed file does not abort independent supported files.
- Framework facts always include generic source facts and evidence.
- The same snapshot/config/version produces byte-stable normalized extraction output.

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

Module 5 follows the approved authority split: the frontend calls Express, and Express delegates analysis operations to Python. Live integration starts only after the integration ADR details in §7.3 and M1/M4 API DTOs are frozen. The current Express token and MongoDB resource IDs cannot be sent to Python as trusted Python identity merely because their formats match. Until the ADR is approved, M5 may refine framework-neutral wireframes and DTO fixtures only; it may not wire proxy authentication, live mutations, SSE relay, or result calls. The frontend portion of M6 end-to-end validation is blocked by the same ADR details.

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

Path status was rechecked against the repository on 2026-11-04. In the tables, **Modify** means the file is verified to exist; **Create (proposed)** means the path does not exist and is a planning proposal. Existing files include `requirements.txt`, `.env.example`, `infra/docker/compose.yml`, `.github/workflows/ci.yml`, the listed Python platform/API/migration extension points, `frontend/src/App.jsx`, `frontend/src/pages/RepositoryDetailPage.jsx`, and `frontend/package.json`. The proposed `backend/platform/analysis/`, `backend/worker/`, `tests/p3/`, and Phase 3 frontend paths are absent. No application file has been created by planning.

#### Module 1 files

The authoritative, implementation-ready M1 file plan is organized by batch in §§4.6.5–4.6.7. Those tables distinguish verified existing files from proposed paths and define responsibilities, dependencies, tests, acceptance criteria, exact implementation order, and handoffs. They supersede the earlier phase-level M1 file summary so there is only one M1 implementation source of truth.

#### Module 2 files

| Path | Action | Components / responsibility | Dependencies and verification |
|---|---|---|---|
| `requirements.txt` | Modify | Add the approved Python parser bindings/grammars only after the F2 parser decision. | Python 3.14 compatibility/security spike and pinned-version review. |
| `backend/platform/analysis/engine/context.py` | Create | Per-analysis context, versions/configuration/registry/metrics; no global mutable state. | Isolation/concurrency tests. |
| `backend/platform/analysis/engine/inventory.py` | Create | Deterministic artifact inventory, roles, exclusions, counts. | Classification/limit/order tests. |
| `backend/platform/analysis/engine/detection.py` | Create | Language/runtime/framework evidence and deterministic confidence rules. | Positive/negative/conflict fixtures. |
| `backend/platform/analysis/engine/registry.py` | Create | Analyzer selection by supported language/framework and capability. | Selection/order/plugin tests. |
| `backend/platform/analysis/syntax/model.py` | Create (proposed) | Parser-neutral `SyntaxDocument`, declarations, references, ranges, and evidence; failures reference shared `AnalysisDiagnostic`. | F2 schema/serialization/diagnostic contract tests. |
| `backend/platform/analysis/syntax/base.py` | Create | `ParserAdapter` protocol and safe parse result contract. | Adapter contract tests. |
| `backend/platform/analysis/syntax/python.py` | Create | Built-in `ast` adapter for Python. | Python syntax fixtures. |
| `backend/platform/analysis/syntax/tree_sitter.py` | Create, proposed | JS/TS/JSX/TSX adapter behind parser protocol. | Grammar/version/error fixtures. |
| `backend/platform/analysis/analyzers/base.py` | Create | Language/framework analyzer protocols and evidence emitter. | Contract tests. |
| `backend/platform/analysis/analyzers/python.py` | Create | Generic Python structure extraction. | modules/imports/classes/functions/calls. |
| `backend/platform/analysis/analyzers/javascript.py` | Create | Generic JS/JSX extraction. | ESM/CommonJS/React fixtures. |
| `backend/platform/analysis/analyzers/typescript.py` | Create | TS/TSX types/interfaces/decorators/components. | TS/Nest/React fixtures. |
| `backend/platform/analysis/analyzers/manifests.py` | Create | Safe package/config/dependency evidence and secret redaction. | manifest/config/security tests. |
| `backend/platform/analysis/analyzers/frameworks/{django,flask,fastapi,express,nestjs,nextjs}.py` | Create (six files) | Framework-specific enrichment over generic syntax facts. | One focused fixture/test suite per framework. |

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

1. A user with permitted Project access can asynchronously analyze a specific immutable Python Phase 2 revision; a Viewer cannot start/cancel but can read permitted results.
2. PostgreSQL is authoritative for analysis/job/stage/event/model state; RabbitMQ/Celery outages or duplicate delivery cannot corrupt lifecycle state.
3. AnalysisInput validates the full project/repository/revision/artifact chain and lazily reads immutable content through `StorageService`.
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
| M1 — Analysis Foundation & Execution | Planned in three batches; not implemented | Complete three-batch implementation plan, file map, F1 freeze, DoD, and handoff prompts recorded in §4.6. Verified Phase 2 boundaries, Section 9, Appendix I, API/persistence conventions, and missing broker/ADR infrastructure. | Resolve F1 and integration-ADR decisions; approve Batch 1; implement sequentially. |
| M2 — Inspection & Language Analysis | Planned; not implemented | Supported languages/frameworks and current Phase 2 artifact classifier verified. | Complete parser spike; approve F2; implement analyzers. |
| M3 — IR & Semantic Analysis | Planned; not implemented | Master IR/identity rules inspected; no current IR code exists. | Approve F3 IR v1; implement/validate/golden-test. |
| M4 — Identity & Architecture Model | Planned; not implemented | Master canonical model/publication rules inspected; no current model code exists. | Approve F3 and M4 persistence; implement model persistence/publication/result APIs. |
| M5 — Frontend Integration | Planned; blocked on integration ADR details | Express is the approved frontend/platform boundary. | Freeze Express-to-Python lifecycle/result proxy contracts, delegated errors, and SSE relay after M1/M4 DTOs and the integration ADR are approved. |
| M6 — Integration & Evaluation | Planned; frontend E2E blocked on ADR details | CI quality commands and current test organization verified. | Build backend fixtures/goldens throughout; browser-to-worker E2E waits for the approved service boundary. |

No application behavior was implemented during this planning pass. Only this handoff document was restructured.

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
- The owner-approved integration direction is Express as the frontend/platform authority and Python as the Phase 3 analysis authority, with authenticated delegation through a trusted service-to-service boundary. This fixes the authority split but not the still-required integration ADR details.

---

## 7. Decisions, Risks, Assumptions, and Handoff

### 7.1 Proposed Phase 3 decisions requiring plan approval

1. Treat `RepositoryRevision.id` as `snapshot_id`; do not create a duplicate snapshot entity unless implementation evidence shows missing immutable-snapshot semantics.
2. Approve the F1 lifecycle contract exactly against Section 9: `PARTIAL` is nonterminal/incomplete, `TIMEOUT` follows the explicit path to `FAILED`, primary terminal states remain unchanged, and Job state remains distinct from Analysis state. Resolve whether `TIMEOUT` is persisted and whether the Section 9 or Appendix C Stage vocabulary governs M1 before freezing enums.
3. Use one Celery orchestration task per analysis in the first implementation while persisting stage records; split stages into separate jobs later without changing frozen domain contracts.
4. Approve one shared `AnalysisDiagnostic` contract, owned/versioned and lifecycle-recorded by M1, emitted by M2–M4, and exposed as finding DTOs only through M4 result-query APIs.
5. Persist Architecture Versions in M4-owned normalized PostgreSQL tables with stable logical IDs and UUID v4 row IDs; keep IR in-memory/serializable but not persist it by default.
6. Use durable PostgreSQL AnalysisEvent rows for SSE replay and sequence; SSE polls/subscribes to that durable stream rather than treating an in-memory broadcaster as truth.
7. Interpret P3 “visualization” as summary/hierarchy/entity/relationship/evidence exploration. Defer canonical node-edge Diagram Specification + ELK + React Flow to Phase 5.
8. Evaluate Python built-in `ast` plus Python Tree-sitter language packages for JS/TS/JSX/TSX through a Python 3.14 compatibility/security spike; package selection remains an approval decision.

### 7.2 Principal risks and mitigations

- **Backend split:** Express/Mongo and Python/PostgreSQL have no shared identity, authorization, Project, repository, revision, or artifact state. The authority split is fixed, but its contract is not. Mitigation: approve the integration ADR's trust, resource mapping, and artifact-access rules before affected M1/M5 work; never bridge by trusting client IDs, accepting an unverified token, or inventing synchronization.
- **Parser compatibility/safety:** Tree-sitter package/grammar versions may not support Python 3.14 or all syntax variants consistently. Mitigation: isolated adapter spike, pinned grammar versions, malformed/deep input tests, time/size limits, replaceable protocol.
- **Scope size:** Six frameworks plus lifecycle/IR/model/frontend is large. Mitigation: freeze contracts first, implement generic analyzers before framework enrichment, use fixtures/goldens, parallelize only behind stable interfaces.
- **Nondeterminism:** concurrent analyzers, set/dict order, or evidence arrival can change output. Mitigation: canonical keys/sorting, analysis-scoped registries, shuffled-order tests, stable serialization.
- **Queue/database dual-write:** DB commit can succeed while publish fails. Mitigation: persist dispatch state, identifier-only idempotent messages, publish-failure state/recovery, duplicate worker guards.
- **Partial failures:** one parser/framework failure could either hide coverage or fail too much. Mitigation: mandatory/optional stage policy, per-artifact diagnostics, completeness metrics, `COMPLETED_WITH_WARNINGS` only with a valid model.
- **Resource exhaustion/malicious source:** parser bombs, huge repositories, secrets, or path tricks. Mitigation: reuse Phase 2 limits, lazy/batched reads, timeouts, redaction, no execution/network, security fixtures.
- **Architecture over-granularity:** every symbol could become a visible node. Mitigation: keep symbols in IR/evidence and promote only architecturally meaningful entities.
- **Schema/version churn:** premature v1 changes can invalidate goldens and consumers. Mitigation: freeze version constants and contracts before module implementation; incompatible changes require version bump/change control.

### 7.3 Outstanding decisions / approval gates

1. **Express/Python integration ADR details:** The authority direction is already approved and must not be reopened: Express is the platform/frontend boundary and Python is the analysis authority. Before Batch 2 reference constraints and Batch 3 APIs, the owner must approve service authentication/rotation, delegated actor/role/Project scope, replay protection, request/audit correlation, resource-reference mapping, which immutable snapshot/artifacts Python reads, artifact-content availability, idempotency ownership, cross-service error mapping, internal route exposure, and SSE proxy/relay.
2. **F1 lifecycle/input freeze:** Approve the Section 9 transition interpretation, persisted-vs-event `TIMEOUT`, authoritative Stage states, proposed Job states, snapshot/input boundary, shared diagnostic contract, queue identity, resource limits, and Phase 2 lookup/reference behavior before M1/M2 implementation.
3. **F2 parser/syntax freeze:** Approve Tree-sitter or another Python-native JS/TS parser after the compatibility spike, then approve the parser-neutral syntax/evidence/source-range contract before M2/M3 parallel implementation.
4. **F3 IR/Architecture freeze:** Approve IR v1, canonical ordering, unresolved/conflict behavior, promotion rules, logical-ID inputs, and golden fixtures before M3/M4 parallel implementation.
5. **Visualization scope:** Confirm that hierarchy/relationship/evidence exploration satisfies P3. If an interactive node-edge graph is required now, approve the roadmap expansion and define how React Flow + ELK is introduced without duplicating the Phase 5 Diagram Engine.
6. **Version constants and retry/time limits:** Approve initial analyzer/IR/Architecture schema versions and measured/configured retry, heartbeat, stage timeout, 30-minute analysis limit enforcement, and performance thresholds before freezing public/golden contracts.
7. **M4 persistence proposal:** Approve normalized PostgreSQL Architecture tables and non-persisted IR. A JSON-blob-only Architecture Model or persisted IR would materially change query, migration, and reproducibility trade-offs.

### 7.4 Current handoff

- **Current phase:** Phase 3 planning complete; implementation has not begun.
- **Plan status:** Phase plan revised; detailed M1 three-batch draft ready for project-owner review and explicit Batch 1/F1 approval.
- **Branch:** `feature_mannan` verified before planning.
- **Last verified baseline:** 330 Python tests collected; frontend tests and production build passed; working tree was clean before this document edit.
- **Blockers:** M1 Batch 1 waits for the F1 lifecycle/snapshot decisions in §4.6.9; Batch 2 reference constraints and Batch 3 API/security work wait for the integration ADR. M2/M3 parallel work waits for F2; M3/M4 integration waits for F3. M5 live proxy/SSE work and the frontend/E2E portion of M6 also wait for the ADR details. All implementation statuses remain planned.
- **Recommended next action:** Review §4.6, resolve the five F1 owner decisions and the immutable snapshot mapping, then explicitly approve **M1 Batch 1 only**. Complete the integration ADR before Batch 2 reference constraints are frozen and before any Batch 3 internal API is implemented.
