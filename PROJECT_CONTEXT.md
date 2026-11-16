# PROJECT_CONTEXT.md — StackSense Engineering Handoff

Last reconciled: 2026-11-17. Branch inspected: `p5-knowledge-search`.

## 1. Project, Authority and Documentation Policy

StackSense is a software repository intelligence and architecture analysis platform. P1–P4 are owner-confirmed complete and frozen. P5 — Knowledge, Search & Diagram Intelligence — is the current phase, planning only.

Authority: `master.txt` governs frozen overall architecture and its accepted ADR/contracts; `docs/PHASE_5_IMPLEMENTATION_PLAN.md` governs P5-specific scope/design subordinate to master; `PROJECT_CONTEXT.md` records detailed execution/decisions consistently with both. A requirement absent from master is not unapproved merely because the P5 baseline adds it. Documentation is not proof of implementation.

- `docs/architecture/adr/0001-express-python-integration.md`: accepted platform/analysis ownership and authenticated service integration.
- `docs/architecture/contracts/f1-analysis-execution-input-v1.md`, `f2-repository-inspection-syntax-v1.md`, `f3-intermediate-representation-v1.md`, `architecture-model-v1.md`: frozen contracts; actual enums/DTOs/source remain authoritative implementation evidence.
- `docs/PHASE_5_IMPLEMENTATION_PLAN.md`: retained approved seven-module phase baseline. Its original draft header predates owner approval; this ledger records the later approval without rewriting that snapshot.
- **This file now contains ongoing P5 module plans, implementation/review records and handoff.** Do not create another M1 planning document or duplicate future detailed module execution records elsewhere unless the owner asks.
- Owner-authorized compaction removes completed P4 planning/batch detail while retaining its reusable boundaries, decisions, verification summary and limitations below. Historical detail remains in Git where committed; no history was rewritten. Uncommitted status corrections from the preceding task are incorporated, not discarded.
- The complete detailed M1 plan was moved here and refined; its separate file was removed. Internal numbered “Section” references within the detailed M1 block refer to that block's own numbered subsections.

## 2. Global Frozen Constraints

1. **Express/MongoDB** owns users/JWT, projects, membership/RBAC, repository registration, immutable revisions/artifact metadata and repository storage access. **Python/FastAPI/PostgreSQL** owns analysis/jobs/stages/events/diagnostics, canonical architecture and Python-owned derived-work metadata. PostgreSQL is intentional authority, not temporary infrastructure.
2. Neither backend reads the other's database. Cross-service UUIDs are opaque references, not permission for direct MongoDB/legacy-platform-table reads or synchronization. Python reads manifests/content only through approved authorized Express APIs.
3. React calls Express only. Existing trusted service/actor/role/project/correlation delegation is validated independently by Python. No browser service secrets, new public system role, auth/JWT/RBAC redesign or database authority change.
4. P1–P4 contracts/domain implementations are frozen. Public read-only ports are reused; private repository/table imports and editing frozen providers are not shortcuts. Any necessary source change requires explicit narrow change control.
5. No unrelated new Express implementation. The P4 M5 minimum graph transport exception was authorized and completed; it is not blanket authorization. P5's approved module direction includes M6 transport responsibility, but detailed scoped transport/composition/continuation contracts still require their recorded approval gates. **P5 M1 changes no Express/frontend code.**
6. Canonical published Architecture Model v1 in PostgreSQL is immutable and authoritative. Neo4j/Elasticsearch and diagrams/reports are derived, disposable/rebuildable outputs; failure cannot invalidate analysis/model publication.
7. No new canonical kinds, AI architecture inference, source execution, new analysis stages or reopening completed stages/public lifecycle vocabulary. F2/F3 recovery remains frozen M1 ownership with identical inputs/configuration/versions; downstream consumers never invoke upstream recomputation.
8. Project is the current isolation boundary; Organization remains deferred despite historical master language. Exact project/repository/analysis/snapshot/Architecture Version and candidate generation scopes cannot be mixed.
9. Python 3.14, absolute imports, SQLAlchemy/Alembic, existing Celery/RabbitMQ and configured quality tools. No new diagram queue/service/broker or arbitrary task/Cypher/search-DSL execution.
10. Structured safe errors; no credentials, literal secrets, storage keys/host paths/raw source in public output/logs. Preserve static uncertainty/provenance, not invented runtime truth or severity.
11. Preserve existing dark UI/navigation/action patterns, protected routes and API-client auth behavior. User-visible layout is presentation, never an editable canonical architecture.

## 3. Phase Index and Completed Baseline

| Phase | Status | Retained outcome |
|---|---|---|
| P1 — Engineering Foundation | FROZEN / COMPLETE | Persistence, API/frontend, migrations, queue/security/testing foundations |
| P2 — Project & Repository Platform | FROZEN / COMPLETE | Express JWT/platform RBAC, projects/repos, ingestion, immutable revisions/artifacts; Python Phase 2 retained as reference |
| P3 — Analysis Engine & Architecture Model | FROZEN / COMPLETE | Lifecycle/F1; isolated deterministic inspection/F2; IR/F3; identity/model publication; gateway/model UI and performance closeout |
| P4 — Architecture Graph & Exploration | FROZEN / COMPLETE — OWNER CONFIRMED | All six roadmap modules M1–M6 accepted, including final evaluation; owner closure reconfirmed 2026-11-17. There is no P4 M7 |
| P5 — Knowledge, Search & Diagram Intelligence | OVERALL SEVEN-MODULE PLAN APPROVED; IMPLEMENTATION NOT STARTED | Current phase; detailed M1/operational contract review pending |
| P6 — AI Architecture Intelligence | UPCOMING | Grounded explanation/assistant, executive summary and documentation comparison after deterministic P5 ports |
| P7 — Final Product & Hardening | UPCOMING | Productization/deployment/final hardening after preceding capability acceptance |

### 3.1 P3 contracts, performance and retained limitations

- F1 preserves master Analysis states, including nonterminal PARTIAL and TIMEOUT; success requires COMPLETED or COMPLETED_WITH_WARNINGS with publication. Stage/job/analysis states are not P5 work states.
- F2 separates artifact role from outcome; facts/evidence are parser-neutral and source-safe. Canonical UTF-8 ranges are zero-based/end-exclusive bytes/columns, one-based lines, BOM excluded, LF/CRLF preserved, original Python encodings handled explicitly.
- F3 normalizes deterministic evidence; M4 owns cross-file/canonical identity and Architecture Model persistence/query. No P5 parsing or semantic reconstruction.
- Canonical limits: 25,000 entities, 50,000 relationships, 75,000 evidence, 10,000 unresolved, 5,000 conflicts, 128 MiB payload; fail closed, no silent truncation.
- Model statuses retain confirmed/supported/inferred/unresolved/conflicting. Evidence strength: direct source > framework structural > configuration > dependency > documentation; competing evidence preserved. Canonical logical IDs and persistence UUIDs are separate.
- Owner-accepted live extraction optimization processed 469 items in about 20 seconds; this is a historical live observation, not a universal timing guarantee.
- **Narrow owner-approved memory change control, 2026-11-14:** corrected benchmark measurement of parent pytest lifetime RSS versus parser-child safety; isolated child VmHWM/functional-equivalence and exact RLIMIT_AS allocation tests. M3 drains mutable indexes before immutable validation and counts canonical bytes in bounded 256-record batches without changing F3 bytes/IDs. Existing Celery child recycling default is two completed tasks.
- Production parser memory isolation remains **512 MiB RLIMIT_AS**. Linux procfs/seccomp are intentional platform requirements; three Windows Job Object tests skipped on Linux are retained, not removed. Parent-process lifetime peak and tracemalloc overhead are not per-workload current RSS.
- Historical remediation evidence: P1–P3 755 passed/3 skipped; then complete repository 1,031 passed/16 skipped. Optimized unprofiled 250k-fact IR peak about 695 MiB with identical 364,101,337-byte payload; parser limit is a different process guarantee. Real worker recycling verified. These historical checks were not rerun by this documentation task.

## 4. Frozen P4 Handoff — Relevant Decisions, Contracts and Evidence

### 4.1 Architecture baseline retained

The 17-decision baseline was owner-approved 2026-11-11; this compact summary preserves its semantics:

1. Python/FastAPI/Celery owns graph projection/query execution; Express is browser auth/transport boundary.
2. Projection has independent PostgreSQL lifecycle, never a mandatory P3 stage.
3. Durable scheduling/recovery is reconciliation-driven.
4. Verified Neo4j Community **5.26.33**, official Python driver **6.4.1**, Python 3.14.
5. Shared Neo4j database isolates project/version/generation.
6. Only semantic node label ArchitectureEntity, relationship type ARCH_RELATIONSHIP and operational label ProjectionManifest; canonical kinds are properties.
7. Storage keys are generation-scoped deterministic SHA-256, canonical IDs/P3 UUIDs separate.
8. Candidate completeness independently verified by readback before visibility.
9. PostgreSQL attempts/leases/fencing and three-execution retry govern rebuilds.
10. Historical published versions retained/projected and exactly readable as STALE.
11. Controlled query hard caps: depth 5, 500 nodes, 1,000 edges, 25 paths, **5 seconds across execution/iteration/mapping/final-pointer verification** with underlying database cancellation.
12. OWNER/ADMIN rebuild; all project roles read; audited internal automatic scheduling.
13. Unresolved/conflicting records do not become synthetic graph entities.
14. Separate React Flow/ELK Explorer has 300-node/600-edge canvas cap and structured alternative.
15. Layered health, observability, reconciliation and rebuild recovery.
16. Public projection lifecycle exactly PENDING/RUNNING/COMPLETED/FAILED/STALE; QUEUED/RETRYING are internal attempts.
17. Old verified active generation stays readable while new candidate builds; rebuild failure never invalidates it, including historical STALE state.

Node/edge key = SHA-256(project UUID || NUL || version UUID || NUL || generation UUID || NUL || canonical entity/relationship logical ID). G1/G2 coexist without overwriting. No Neo4j internal ID becomes product identity.

The narrowly authorized manifest correction removed ArchitectureProjectionGeneration in favor of **ProjectionManifest.generation_key**, without dual-label alias or schema-version bump; GRAPH_SCHEMA_VERSION stays 1.0.0. Additive composite RANGE indexes on entity/relationship/manifest project/version/generation were explicitly approved and real-Neo4j compatibility checked.

M2 writes and independently verifies exact keys/counts/digests/endpoint scope/direction/schema; M1 alone validates current attempt and transactionally switches the PostgreSQL active-generation pointer. M3 is read-only query execution; M4 composes lifecycle/query FastAPI routes. Never move activation into the projector/query layer.

### 4.2 Frozen public integration points

| Contract | Owner / retained boundary |
|---|---|
| P4-L1 | M1 resource/attempt/lease/activation lifecycle |
| P4-S1 | Exported PublishedArchitectureSource / SqlAlchemyPublishedArchitectureSource in backend/platform/graph/source.py; list published headers and load exact published document read-only |
| P4-W1 | Identifier-only projection/attempt/project/version/generation/contract/correlation worker payload |
| P4-P1 | M2 deterministic projection and independent verification receipt; no activation |
| P4-Q1 | M3 bounded query DTOs/vocabulary, generation-bound HMAC cursors and errors |
| P4-H1 | Layered health and expiring real worker/reconciler capability |
| P4-D1 | Frozen v1.0.0 Python graph API composition, delegated scope/auth/status/validation contract |
| P4-U1 | Exact-version Explorer loaded-window/selection/layout/navigation state; owner phase acceptance includes UI closure |

All paginated graph operations bind active generation and query/scope; drift rejects continuation, never silently restarts. Historical COMPLETED **or STALE** resources with verified active generation are readable. Dependency traversal includes all twelve approved non-containment kinds (depends_on/imports/calls/exposes/consumes/produces/connects_to/persists_to/uses/extends/implements/routes_to); contains is separate hierarchy.

Relevant existing modules: backend/platform/graph/{source,model,lifecycle,persistence,queue,runtime,projection,verification,query_contracts,query_service,api_service,dependencies,api_dependencies}.py; backend/api/v1/graph.py; backend/worker/graph_tasks.py. Do not edit frozen internals for P5; use public ports.

React → existing Express graph routes/controller/gateway → FastAPI → PostgreSQL/Neo4j. Preserve repeated query parameters, delegated auth/RBAC, 202/403/404/409/410/422/upstream failures. Gateway JSON/SSE support is not an established binary PDF relay. Exact-version route: #/projects/:p/repositories/:r/analyses/:a/architecture/:v/graph.

Existing frontend graph canvas/list/inspector/layout worker and useGraphLayout/useArchitectureGraph implement compact layout, evidence paging, stable selection, exact-node focus and Neighbors navigation. Preserve these fixes; P5 diagrams are distinct views/specs, not permission to enlarge P4 caps or replace its worker protocol.

### 4.3 Retained verification, operational corrections and limitations

- M1–M4 code-reviewed remediation and real PostgreSQL 16/Neo4j pipeline results retained. At M4 closure: full repository **1,087 passed, 16 intentional environment/platform skips**; P4 suite 332 passed/13 environment skips; Black 344 unchanged, strict Mypy 216 files and Ruff passed. A real multi-store pipeline was separately executed; skips are not passed infrastructure checks.
- Final frontend navigation correction: all four legacy suites plus **128 tests/19 Vitest files**, production build and diff checks passed; focused navigation/layout/Explorer 16 tests. Real React Flow/ELK browser fixture verified exact node centering, neighbor expansion and stable ordinary selection. These are UI checks, not fabricated live backend E2E.
- Initial graph status 404 can be a publication/discovery race, not absent analysis output. Existing bounded context-safe polling recovers it; no rerun of analysis. Readiness/worker scheduling remains real-state gated.
- Existing example/local graph reconciliation interval was tuned to **5s**; code fallback stays 60s. Historical Beat cadence and scans of 34 publications in 0.430–0.842s were observed. Existing dispatch recovery 60s/lease 120s/heartbeat 30s/backoff 15s are P4 settings, not approved P5 defaults. Task registration alone is not runtime capability.
- Owner accepted/froze P4 after live use; M6 closure reconfirmed 2026-11-17. No separate P4 M7 or new consolidated M6 test run is invented. Historical verification counts are not claims about this documentation-only task.
- Operational caveats retained: explicit real-service test environment gates, Windows tests intentionally skipped on Linux, deterministic static analysis is not runtime observation, initial graph discovery is eventual, and deployment secrets/resource settings must match actual services. Source master/ADRs/contracts, implementation/tests and Git history retain detailed evidence; no frozen threshold weakened.

## 5. Approved P5 Baseline and Execution Ledger

The overall seven-module plan is owner-approved. Detailed M1 three-batch purposes are accepted as the planning baseline, **not** detailed contract freeze or implementation authorization.

| Module | Responsibility | Execution status |
|---|---|---|
| M1 | Delivery contracts, durable work/attempts/dispatch/fencing/recovery and report prerequisites | APPROVED FOR IMPLEMENTATION — owner approval 2026-11-17; no batch started; existing batch/acceptance gates retained |
| M2 | Deterministic knowledge projection, verified Elasticsearch generations, scoped search | Overall direction approved; detailed module planning/implementation not started |
| M3 | Controlled retrieval, evidence/context and existing graph-query reuse | Same |
| M4 | Four independent diagrams, DiagramSpec/layout/export and presentation workspace | Same |
| M5 | One deterministic Architecture Analysis Report/PDF, prepared ReportSpec and private artifacts | Same |
| M6 | Minimal approved Express transport and unified React output workspace; separately gated ingestion→analysis continuation | Same |
| M7 | Real integration/recovery/security/performance/evaluation and final closure | Same |

Mandatory product flow: successful published exact version → independent search and overview work → four diagram READY artifacts → M1's strict same-version/digest report barrier → one report operation → prepared/validated PDF. Overview is prioritized; retryable overview failures hold siblings, terminal FAILED releases siblings, and a valid successor may satisfy the barrier; no text-only automatic fallback is introduced. These policies are incorporated for joint detailed-plan review, not implementation authorization.

P5 preserves published-model authority and evidence; reports/diagrams do not parse source or invent findings/severity. The renderer consumes prepared ReportSpec/assets and queries no backend. P6 owns executive summary, documentation comparison, natural-language/AI explanation. New shared-queue limits, handler profiles, runtime layout/PDF/ES choices and narrowly scoped composition remain their explicit gates; the requested OWNER/ADMIN retry policy is now incorporated for detailed review; global phase approval is not a claim of measured operational compatibility.

Current planning-task evidence: repository/contract/deployment-unit inspection only; documentation consistency/diff checks are recorded at handoff. No application tests, migrations, infrastructure runs or dependency installation by this refinement.

## 6. Detailed P5 M1 Plan — Delivery Contracts and Durable Orchestration

The following complete plan supersedes the removed standalone M1 file. Numbered subsections/references within this block are local to M1; exactly three batches are retained.

### 1. Document Status and Planning Scope

**Detailed M1 plan: APPROVED FOR IMPLEMENTATION — OWNER APPROVED 2026-11-17. M1 is not implemented, complete or frozen.**

**C0 approval status: DESIGN APPROVED WITH THE M1 PLAN; CONTRACT NOT FROZEN.** Owner approval authorizes implementation beginning with B1. B1 consumer fixtures, producer/consumer sign-off and independent review must still support an explicit C0 freeze before B2; passing tests alone cannot grant freeze approval. All existing composition, measured-default and runtime acceptance gates remain in force.

**Implementation: NOT STARTED. Exactly three implementation batches are specified in Section 26.**

Inspected branch: `p5-knowledge-search`, 2026-11-17. The owner approved the overall P5 seven-module plan before this task. That approval establishes module direction; it does not establish approval of this new detailed C0 contract, unmeasured operational defaults, migrations or implementation commencement.

Authority: frozen `master.txt` and accepted ADR/contracts → governing P5 baseline `docs/PHASE_5_IMPLEMENTATION_PLAN.md` → detailed execution/decision record in `PROJECT_CONTEXT.md`. The phase document's original “proposed” header predates the latest owner approval; it is not edited by this task. This document does not supersede frozen interfaces or broaden M1 into output generation.

The current owner instruction consolidates this entire detailed plan into PROJECT_CONTEXT.md and removes the separate M1 plan. It overrides the attachment's old file-location instruction, not its planning-only boundary. The seven-module structure and exactly three M1 batches remain accepted baselines; detailed C0/policy approvals remain pending. Application code, tests, configuration, dependencies, migrations, ADRs, master and the phase-level plan remain untouched.

### 2. Executive Summary

M1 supplies P5-specific durable execution records and dependency coordination on existing PostgreSQL/Celery/RabbitMQ infrastructure. It does not introduce a second workflow product, orchestration service, generic DAG framework or message broker. The frozen AnalysisJob and GraphProjection implementations are domain-specific and cannot safely hold diagram/report/search jobs.

Use the existing public published-source port and public analysis read service to discover exact eligible versions. Persist one version/policy delivery bundle, bounded search/diagram work, append-only execution attempts and accepted output-reference receipts. Reconcile publication discovery, durable dispatch intent, expired leases and report eligibility after failures. No browser event or broker message is authoritative.

All output activation and work completion share one fenced physical PostgreSQL transaction through M1's explicit UoW and enlisted producer-owned public publication ports. Expensive indexing/layout/rendering occurs outside that transaction in attempt-scoped candidates. M1 owns the outer SQLAlchemy transaction, final live-fence authorization and commit; M2/M4/M5 lock/validate/write their own resource data through enlisted public adapters without independent commits. M1 never edits those modules' tables itself.

All four committed READY diagram references must match one project/repository/analysis/snapshot/Architecture Version and canonical digest before a unique automatic report operation is created. A ready notification is only a hint. Reconciliation can recover a missed hint or broker outage without rerunning successful upstream work.

### 3. Repository Reconnaissance and Verified Existing Infrastructure

| Verified existing path | Actual capability | M1 implication |
|---|---|---|
| `backend/platform/graph/source.py` | Exported `PublishedArchitectureSource`, `PublishedArchitectureHeader/Page/Cursor`, `SqlAlchemyPublishedArchitectureSource`; exact published-model load | Reuse read-only public adapter; do not create a private P3 query |
| Same source port | `list_published(limit, after)` accepts 1–500; ordering project UUID/repository UUID/sequence/version UUID | Cursor is not chronological/append-only; periodic completed sweeps must restart |
| `backend/platform/analysis/application/lifecycle_service.py` | `AnalysisLifecycleService.get_analysis(analysis_id, project_id)` returns authoritative status/identity | Read-only success eligibility check; no mutation/recovery invocation |
| `backend/platform/analysis/application/dependencies.py` | Public `get_analysis_lifecycle_service`, delegated context, project equality and operator-role dependencies | Reuse provider/read method and trusted auth; do not import private analysis repositories |
| `backend/platform/analysis/application/dto.py` | Analysis response includes project/repository/snapshot identity and status; creation is revision-scoped/idempotent | Validate header/analysis ownership; never choose a different revision/version |
| `backend/platform/analysis/domain/job.py` and `infra/lifecycle_model.py` | Analysis-specific job/stage/diagnostic persistence | Frozen, not a generic P5 execution store |
| `backend/platform/graph/lifecycle.py`, `persistence.py`, `queue.py` | P4 reconciliation, conditional lease, durable dispatch, strict identifier payload and verified activation | Reliability patterns are informative, not an M1 implementation to subclass/extend |
| `backend/platform/graph/runtime.py`, `backend/worker/graph_tasks.py` | Expiring capability heartbeat, worker/task composition and queue registration | Task registration alone is not proof that the intended worker/Beat path is live |
| `backend/worker/celery_app.py` | JSON tasks/results, late acknowledgements, reject-on-worker-lost, prefetch, concurrency, beat and existing routes | Reuse same app/broker; additive task/beat routes require scoped composition approval |
| `backend/platform/config.py` | `analysis.jobs` default queue, analysis concurrency 2/prefetch 1; distinct graph execution/maintenance settings | Existing values are facts, not approved P5 throughput/memory/lease defaults |
| `ops/systemd/stacksense-celery-worker.service`, `stacksense-celery-beat.service` | Existing worker/Beat services load .env on restart; analysis worker has no explicit queue selector, while graph units select configured queues | Existing service files are not proof of the full deployed consumer fleet; no new worker service is proposed |
| `backend/platform/dependency_injection.py` | Cached engine/settings and request Session; session dependency commits/rolls back | P5 DI owns its own services; publication protocol must account for transaction commit, not just flush |
| `backend/platform/projects/infra/base.py` | Shared SQLAlchemy `Base` | Reuse declarative infrastructure only, not legacy project authority |
| `backend/infra/migrations/env.py` | Explicit imports register models in Base.metadata | Add only P5 registrations/new migration; preserve existing migrations |
| `backend/infra/migrations/versions/c5d2e3f4a5b6_add_graph_runtime_capabilities.py` | Latest leaf in inspected migration chain, after `f4c1b2d3e4a5` | Recheck actual head before generating an additive revision; do not hard-code a stale down_revision |
| `backend/api/v1/router.py`, `backend/api/error_handlers.py` | Router composition, structured errors; existing code-specific mappings | Add P5 router only; map new P5 errors locally rather than edit frozen global mappings |
| `docs/architecture/adr/0001-express-python-integration.md` | Express/Mongo platform; Python/PostgreSQL analysis; trusted headers; no cross-database access | Reuse accepted delegation; no Mongo access/system impersonation |
| `tests/conftest.py` | Existing Python 3.14 HTTPX/TestClient compatibility shim | Reuse for buffered API tests; it does not prove real concurrent ASGI/worker correctness |
| `tests/p4/integration/test_graph_lifecycle_postgres.py` | Real PostgreSQL races/constraints | Follow isolation/testing patterns; its fallback to `.env` is not permission to test against user data |
| `tests/p4/integration/test_graph_dispatch_rabbitmq.py` | `RABBITMQ_TEST_URL`, isolated temporary queue routing/redelivery/failure checks | Reuse declared dependency and test pattern; transport-only tests must be supplemented by actual P5 worker execution |
| `pyproject.toml`, `.github/workflows/ci.yml` | Python 3.14, Black/Ruff/strict Mypy/pytest commands | Read-only reference for quality gates; no CI changes in planning |

No delivery package, P5 work tables, publication hook, P5 worker capability protocol or ready-reference reader is currently established. Names specified below are proposed new interfaces, not claims about existing code. No infrastructure was started and no tests were rerun during planning.

P4 has six modules in its actual roadmap. The latest owner instruction confirms final acceptance/freeze, including M6; a P4 M7 does not exist and is not invented. Existing verification records are retained as recorded, not relabeled as newly executed tests.

### 4. Relevant Architecture and ADR Constraints

- Master Section 9 separates PostgreSQL job truth, RabbitMQ transport and Celery execution. P5 work remains independent of frozen analysis lifecycle; PARTIAL/TIMEOUT are not successful terminal analysis states.
- Sections 13 and 18 keep derived systems disposable, failures isolated and module internals private. Use exported/public interfaces; no P5 imports of P3/P4 private repositories or SQL tables.
- Section 16 describes diagram generation/cache/versioning; M1 schedules it, M4 owns meaning/spec/layout/storage readiness.
- Sections 17.47–17.49 require explicit asynchronous report state/idempotency; Section 17.90 forbids discovering facts or querying through renderers.
- Section 17.80 and rule 17.90.38 allow a general text-only report path. The owner requires the P5 automatic product to wait for all four READY diagrams. M1 enforces that product scheduling policy without removing the general renderer capability or editing master.
- ADR-0001 uses opaque cross-service UUIDs and trusted `X-Service-Token`, `X-Actor-Id`, `X-Actor-Role`, `X-Project-Id`, optional correlation. Python independently validates delegated scope. No retained user token or invented system role.
- Frozen P4 automatic scheduling/rebuild/query semantics remain untouched. P5 private work messages are not new public analysis/graph lifecycle events.
- Existing Express transport authorization is scoped, not blanket permission for M1 to implement a new gateway. P5 M6 owns approved transport work after its contract gate.

### 5. M1 Goals and Non-Goals

**Goals:** exact-version discovery/eligibility; durable idempotent work; at-least-once dispatch; claims, leases, heartbeat, fencing; crash/restart/broker recovery; fixed dependency coordination; automatic report barrier; authorized status/retry; downstream-usable immutable C0 contracts and operational evidence.

**Non-goals:** analysis jobs/stages/recovery; graph projection/activation/query semantics; source scanning; Elasticsearch/indexing; retrieval/context; DiagramSpec/builders/layout/export; ReportSpec/PDF; generated-file implementation; platform metadata retrieval; ingestion→analysis chaining; frontend; canonical identity/model changes.

The shared `ArtifactReference` shape belongs to M1, but immutable storage/sealing, exact-generation reads, integrity/size validation, safe cleanup exclusion and READY publication belong to the producer. The phase-level shared artifact-store implementation is deferred to its first M4/M5 consumer, not smuggled into M1.

### 6. Responsibility Ownership and Dependency Boundaries

| Owner | Responsibility | Consumer boundary |
|---|---|---|
| Frozen P3 | Successful analysis and published canonical model | Existing public reads only |
| Frozen P4 | Published source adapter and graph infrastructure/query/lifecycle | M1 reuses exported read-only source port, no graph dependency for delivery |
| P5 M1 | Work/attempt/dispatch/discovery, prerequisite receipts, report scheduling and fencing | C0 contracts/DI; no output module repository imports |
| P5 M2 | Search validation, independent verification and output resource publication | WorkHandler + publication hook + output receipt |
| P5 M3 | Request-scoped retrieval/context | Status/scope contracts; not necessarily background work |
| P5 M4 | Validated diagram generation, local/store integrity, READY state and artifact history | WorkHandler + atomic publication hook + committed ArtifactReference |
| P5 M5 | Prepared report, render/storage validation and report READY | WorkHandler + same publication boundary; never polls four diagrams |
| P5 M6 | Express/React transport/UX and any separately approved platform preparation | Delivery DTOs/status/retry, no private database access |

| P5 M7 | Cross-module integration, evaluation and closure | Public contracts and real acceptance evidence |

M1 owns a fixed set of work kinds (`search_projection`, `diagram`, `report`), not a user-programmable workflow graph. Diagram template IDs are fixed: `system_overview`, `component_architecture`, `dependency_map`, `data_flow`. Report type is `architecture_analysis`. M3 has no invented background job simply to fill the registry.

### 7. Existing Functionality to Reuse

Reuse `PublishedArchitectureSource`/concrete exported adapter, `AnalysisLifecycleService.get_analysis`, `get_analysis_lifecycle_service`, delegated authorization dependencies, engine/Session/Base, Settings patterns, existing Celery app and Kombu transport already declared through Celery, structured logging/error envelopes and existing test tooling.

Use P5-owned adapters and composition. Do not import `SqlAlchemyArchitectureRepository`, `ArchitectureVersionModel`, `SqlAlchemyAnalysisRepository`, graph lifecycle repositories or graph lease implementations into delivery. The exported P4 source adapter may internally depend on P3; P5 does not reproduce those imports.

No new Python third-party dependency is expected for M1. Standard hashlib/json/UUID, existing Pydantic/SQLAlchemy/Celery cover requirements. No new queue/service/workflow library is proposed.

### 8. Proposed Architecture and Component Interactions

```text
Existing public published source + public analysis read
                       |
                PublishedVersionReader
                       |
       Discovery sweep / pending-eligibility revisit
                       |
           DeliveryCoordinator + PostgreSQL
           bundle / work / attempts / receipts
             |                       ^
       durable dispatch intent       | fenced atomic completion
             v                       |
       existing Celery/RabbitMQ -> P5 task -> WorkHandler registry
                                           |
                         owner-module candidate build/validation
                                           |
                          owner-module publication hook (same SQL transaction)
                                           |
                       accepted READY reference -> report barrier
                                           |
                              durable report work -> same dispatch path
```

`DeliveryCoordinator` is application coordination, not a new daemon. Celery tasks/Beat invoke bounded services. A registry binds allowlisted work kinds and pinned handler profiles to module-owned implementations. M1 production can be installed with downstream handlers absent: durable work remains pending with `handler_unavailable`; it must not report fabricated output success or consume execution attempts.

Read APIs use a P5 projection of durable state. READY hints invoke the same reconciliation check as periodic recovery; no separate authoritative completion-event consumer is needed.

### 9. Domain Model and Lifecycle State Machines

#### 9.1 Bundle and logical operations

`DeliveryBundle`: immutable VersionScope/source digest, delivery-policy version, effective configuration/profile snapshot and source-eligibility state. Unique `(project_id, architecture_version_id, delivery_policy_fingerprint)`.

Eligibility is `WAITING_FOR_ANALYSIS`, `ELIGIBLE` or `INELIGIBLE`; temporary read/infrastructure errors are separate retry metadata, not fabricated analysis failure. An eligible bundle has logical work slots for search and four diagrams. Report slot is absent until the barrier succeeds. Aggregate delivery status is derived from slots/prerequisites; do not store an independent workflow state that can contradict individual outputs.

A logical slot identifies `(bundle, work_kind, template_or_report_type)`. A `DerivedWork` is one immutable-input **run** of that operation, not an output artifact or canonical fact. Its identity includes input fingerprint and `run_number`. Only one run is current per slot.

#### 9.2 Work and attempts

Proposed work transitions, separate from frozen F1:

```text
PENDING -> QUEUED -> RUNNING -> COMPLETED
                    |   |
                    |   +-> FAILED (final nonretryable/exhausted)
                    +-> RETRYING -> QUEUED
PENDING/QUEUED/RETRYING -> CANCELLED (internal safe cancellation only)
RUNNING -> CANCELLED only after fencing ownership is invalidated
```

PENDING can remain blocked by dependencies, capability or admission with an explicit reason. First dispatch preparation commits QUEUED before send. Redispatch of QUEUED does not change state or consume an execution attempt. RETRYING has `next_eligible_at`; expiration creates a fresh delivery epoch and requeues the same run.

`WorkAttempt` is created only on a successful execution claim: RUNNING → COMPLETED / FAILED / EXPIRED / CANCELLED. Terminal attempt records never reopen. Each new attempt increments the monotonic run fence, execution ordinal and attempt identity. Heartbeat/progress are bounded mutable fields only while RUNNING.

Terminal work runs never reopen. An authenticated OWNER/ADMIN retry of an eligible current FAILED run creates a new current run (`retry_of_work_id`, next run number), preserves the failed run/attempts and pins the same input/profile. This distinguishes user retries from automatic attempts and makes terminal-history guarantees explicit. A completed run is not “retried” to overwrite published bytes; changed-input regeneration belongs to the output module and a separately authorized operation.

#### 9.3 Internal cancellation semantics

CANCELLED terminates a logical run for a classified internal policy action. **No public cancellation API, extra task or operator service is added.** Cause vocabulary: ADMINISTRATIVE_WITHDRAWAL (explicit owner-authorized withdrawal of an unpublished operation) and POLICY_SUPERSEDED (durably authorized replacement policy for the same unpublished slot, with replacement identity recorded). These are plan decisions incorporated for joint C0 review, not implemented capabilities. A newer Architecture Version alone never cancels historical work.

M1 alone applies internal cancellation with validated cause/actor/operation identity, expected current work/fence and policy epoch. Initiators are the coordinator consuming an approved durable policy decision or an owner-authorized operator via a controlled in-process maintenance procedure; no producer/browser/broker payload independently cancels work. An operator uses an approved internal maintenance procedure, not a claimed existing endpoint. Producers may report an execution-stop/checkpoint result, but cannot cancel logical runs or revoke another attempt. Shutdown, dispatch disablement, broker failure and heartbeat loss are not logical cancellation.

| State | Serialized cancellation behavior |
|---|---|
| PENDING | Lock bundle/work, validate cause; invalidate dispatch epoch and advance fence; mark CANCELLED without inventing an attempt |
| QUEUED | Same; outstanding messages become stale no-ops and cannot claim |
| RETRYING | Cancel pending retry; preserve prior FAILED/EXPIRED attempts |
| RUNNING, live lease | Lock bundle/work/attempt; invalidate fence/epoch/lease and record attempt/run CANCELLED atomically; cooperative execution stop follows commit |
| RUNNING, expired lease | Preserve or classify attempt EXPIRED, never rewrite terminal history CANCELLED; authorized logical-run cancellation prevents a new retry |
| Candidate already exists | Apply the same database cancellation; candidate remains private; producer owns bounded cleanup |
| COMPLETED / FAILED / CANCELLED run | Terminal state unchanged; no unpublish or completed-output deletion. FAILED recovery requires a successor run; cancelled-run resumption is not implicitly supported |

Cancellation/retry serialize on the bundle/current-run lock: cancellation first makes retry of the now-CANCELLED predecessor ineligible; successor creation first means a cancellation targeting the old work/fence cannot affect it. A heartbeat first extends a live lease but does not prevent subsequent authorized cancellation; cancellation first makes heartbeat fail. Persisted CANCELLED state/fence suppresses redispatch after restart.

Cancellation and publication use the same lock order. If cancellation commits first, late renewal/publication fails. If publication commits first, cancellation sees COMPLETED and is refused. A stale callback cannot cancel the newer current run. Persist safe cause, actor type/ID, cancellation time and invalidated fence; no cleanup inside this transaction.

Expiration ends an attempt due to lost liveness and may permit automatic retry; failure ends an attempt for a classified error; cancellation ends the logical run for authorized policy. Manual retry creates a successor after FAILED, not a reopened terminal run. M1 never deletes producer artifacts or changes completed analysis/graph state.

#### 9.4 Execution budget

Automatic budget counts acquired executions, not message publications, lease renewals or unavailable-handler checks. A crashed execution counts once and ends EXPIRED. No implicit Celery retry budget exists alongside the database budget. Manual retry rounds require approved rate/maximum-round policy; absent approval, expose a clear conflict rather than unlimited restarts. Numeric values await measurement/owner approval. Independently configure acquired executions per run, backoff/jitter bounds, per-project/actor manual-retry admission window and successor-round cap. Missing production policies keep execution/manual retry disabled rather than copying test values or allowing unlimited rounds.

#### 9.5 Manual retry policy and deduplication

OWNER/ADMIN alone may manually retry; DEVELOPER/VIEWER inspect status and receive 403 for retry. Automatic retry is internal. Do not reuse the P3 operator dependency, which admits DEVELOPER.

Eligible target is the current FAILED run, unchanged exact scope/profile/input, same-input retry explicitly permitted by failure policy, approved round/admission budget, matching capabilities and satisfied prerequisites. Exhausted transient infrastructure work may recover; deterministic invalid scope/schema/provenance/capacity cannot be bypassed. Reject with 409 delivery_retry_requires_new_input or delivery_prerequisite_conflict until separately authorized changed-input work exists.

Create a successor DerivedWork with fresh UUID, incremented slot run_number, retry_of_work_id, identical semantic input fingerprint, fresh dispatch epoch/attempt namespace and zero acquired executions. Preserve terminal history. Run identity fingerprint is SHA-256 over tagged canonical [slot identity, input fingerprint, run_number]; random lease/attempt IDs are not semantic inputs.

Under bundle/current-run lock, deduplicate actor/project/action/idempotency key and request fingerprint. Same key/body returns its original durable response even after the successor completes; same key/different body →409. Different keys/actors racing for one FAILED predecessor create one successor; later callers receive 409 delivery_retry_conflict with the authorized current-work ID, not another successor.

PENDING/QUEUED/RUNNING/RETRYING are not manual targets. COMPLETED/CANCELLED/superseded FAILED never reopen. Wrong scope/missing resource follows current 403/404 disclosure rules; admission uses defined safe 429/409 responses. Report retry revalidates its four pinned prerequisites and never substitutes latest diagrams.

Audit actor UUID/role, project/version/bundle/slot, predecessor/successor work IDs, input/policy fingerprint, request/key digest, reason/failure code, correlation ID, UTC timestamp and budget decision. Persist no credentials.

### 10. Shared Contracts and Schemas

All records below are **proposed C0 v1.0.0**, not already implemented/frozen. Immutable dataclasses or Pydantic frozen models; nested collections immutable, unknown message/request fields forbidden. UUIDs validated, aware UTC instants, explicit byte units, bounded safe strings and canonical finite JSON only.

| Contract / owner | Essential fields and rules | Persistence/consumer |
|---|---|---|
| `VersionScope`, M1 | project/repository/analysis/snapshot/version UUIDs; sequence; publication time; canonical digest; source contract/analyzer/IR/architecture schema and source configuration fingerprint | Immutable bundle/work input; all modules |
| `DeliveryPolicy`, M1 with producer approval | policy version; required template set; overview policy; pinned handler/output schema/generator/config profiles; report type/template profile | Immutable snapshot/fingerprint; never read changed global defaults mid-run |
| `PublishedVersionReader`, M1 adapter | `list_published(limit, cursor)`, `inspect_eligibility(header)`; `load_exact` only when canonical scope/digest validation requires it | Transient adapter; persisted eligible/pending header; wraps public frozen ports |
| `WorkExecutionContext`, M1 | immutable scope/bundle/work/run/input/profile/attempt/fence/dispatch epoch/candidate/deadline plus read-only ExecutionControl; no logical cancellation callable, credentials or raw source | Transient handler input; no Session/engine/Connection/transaction/lease secret exposed |
| `ExecutionControl`, M1 | checkpoint() checks deadline/current ownership; should_stop() reports cooperative-stop condition; no mutation methods | M2/M4/M5 may stop only their own execution; M1 alone records lifecycle and invalidates ownership |
| `PreparedOutput`, producer | mandatory exact VersionScope, bundle/work/run, attempt UUID, fence and dispatch epoch, candidate UUID, all pinned producer/generator/schema/config profiles, bundle/work input fingerprints and applicable producer fingerprints/output content/spec/layout digests, validated size/sealing descriptor | Immutable transient result; cross-attempt/fence/profile reuse rejected even for identical content; not a source/spec blob in M1 tables |
| `ArtifactReference`, M1 shape/producer content | producer/kind/template, exact immutable resource/generation/artifact UUIDs, VersionScope, canonical/input/schema/producer versions, content/spec/layout digests and size/media where applicable; no mutable latest alias/shared final key | Committed exact-generation reference backed by producer sealing/immutable contents, not merely a stable string; diagrams require C2 spec/layout/server artifacts |
| `AcceptedOutput`, producer + M1 | validated ready reference and safe summary; no READY claim based only on a broker result | Stored M1 receipt in same transaction as producer READY and work completion |
| `WorkHandler`, M1 port/producer implementation | `execute(context) -> PreparedOutput`; separate enlisted `ProducerPublicationPort.publish_prepared(candidate, publication_context) -> AcceptedOutput` | Registry pairs execution handler with a public publication factory; execution has no publication Session; bounded publication occurs inside UoW |
| `PublicationContext` / `ProducerPublicationFactory`, M1 shape / producer implementation | Immutable transaction/scope/work/attempt/fence/candidate/deadline context; public factory binds the owner adapter to a UoW-enlisted Session on M1's physical Connection | Only public producer ports exposed to M1; no producer outer-commit authority; enlisted Session closes on UoW exit |
| `OutputReadinessReader`, producer | `validate_ready(reference, publication_context) -> ReadyValidation` on the factory-enlisted port | Public module-owned local validation, no raw transaction handle or private-table reads by M1 |
| `DeliveryWorkPayload`, M1 | work_id, bundle_id, project_id, architecture_version_id, dispatch_epoch UUID, C0 version, correlation_id | Identifier-only broker kwargs; reload authoritative input; no lease token/source/spec/role |
| `DeliveryFailure`, M1 shape/producer classification | stable code, safe message, retry class, bounded details, source capability | Durable attempt failure; never another AnalysisDiagnostic contract |

**Fingerprint algorithm:** lowercase canonical UUID strings; copy canonical logical IDs/digests without renormalizing them; canonical JSON with sorted keys, UTF-8, compact separators, finite numbers, stable sorted set-like lists and no volatile timestamps. Include contract/type tags to prevent key-space ambiguity. SHA-256 lowercase hex over that byte encoding. Reject invalid Unicode rather than replace. Never concatenate unescaped free text with delimiters.

Bundle fingerprint binds exact scope, canonical digest, delivery policy and all pinned producer profiles. Initial search/diagram work binds bundle, kind/template and generator/schema/config versions. Report input additionally binds an ordered list of all four exact accepted diagram reference identities/digests plus report profile. Correlation ID/lease/task ID/current timestamps are not semantic fingerprints. Artifact content digest uses actual bytes and is distinct from input fingerprint.

C0 freezes common shape/ownership, not the internal DiagramSpec/ReportSpec/knowledge schema. C1/C2/C4 later fill producer-specific required reference validation without silently changing C0 required fields; incompatible changes require producer/consumer review and version change. Unknown required producer profile/version blocks dispatch, never uses “latest”.

#### 10.0 Execution control and candidate/reference invariants

ExecutionControl is an M1-owned producer-facing Protocol with exactly checkpoint() -> None and should_stop() -> bool. checkpoint raises a typed execution-stop/lost-ownership/deadline signal when continuation is invalid; should_stop only reports the stop condition. A true stop condition is latched for that execution. Neither method grants mutation authority or performs producer-requested logical cancellation. M1's independent liveness/clock observations drive it; no producer method can change work state, invalidate a fence, cancel another attempt or revive ownership.

A cooperative producer observes the signal and stops candidate work. Ignoring a checkpoint does not grant publication authority: M1 independently rechecks exact current ownership/deadline/fence in final publication. M1 alone classifies and records FAILED/EXPIRED/CANCELLED and any retry transition under the existing policy; a producer stop is not automatically a logical cancellation. Preserve the internal classified/audited cancellation rules in §9.3.

PreparedOutput binding is mandatory, not inferred from the broker payload: compare exact VersionScope and bundle identity, work UUID/run number, attempt UUID, fence, dispatch epoch, candidate UUID, every pinned producer/generator/schema/config profile and the bundle/work input fingerprints against durable current execution before invoking the publication port, then revalidate within the locked transaction. Output content/spec/layout digests and producer-specific fingerprints must match the sealed candidate and the applicable pinned producer contract; an inapplicable field is explicitly absent under that schema, never an unchecked wildcard. A successor attempt must reject an earlier attempt's prepared candidate even if its content digest is equal. This does not change legitimate historical report reuse of an already accepted immutable artifact: reuse is reference consumption, never pretending an old candidate was created by a new attempt.

ArtifactReference immutability requires both exact generation identity and immutable/sealed underlying bytes/index records with verified digests/size; a stable URI or UUID by itself proves neither. Readers resolve the committed project/version/generation reference, never a mutable filename, alias or latest selector. Producer acceptance must reject a reference without the required immutable-storage/readiness proof; M1 must not infer sealing from file existence.

#### 10.1 Shared contract ownership, consumers and rejection

Every row inherits C0 v1.0.0 negotiation, deep-immutable serialized values, strict unknown-field/schema/scope checks and safe mismatch rejection. Durable lifecycle fields change only through legal transitions/CAS; input/receipt contents and terminal history do not. Additive optional fields need producer/consumer compatibility review; incompatible scope/fingerprint/state/receipt semantics require major version and owner change control. Never select a different generator/schema silently.

| Contract | Owner / producer | Consumers | Invariant and failure behavior |
|---|---|---|---|
| VersionScope / DeliveryPolicy / BundleIdentity | M1 shape; public source adapter/coordinator produce | M2/M4/M5 execution, M3/M6 context/status, M7 tests | Exact scope/digest/pinned profiles; mismatch rejects creation |
| WorkIdentity / AttemptIdentity / successor | M1 coordinator | M2/M4/M5 handlers; M6 safe DTO | Unique current slot/run and attempt/fence; stale epoch cannot claim/publish |
| ExecutionControl | M1 owns observations/control; producers only consume | M2/M4/M5 execute; M1 lifecycle | checkpoint/should_stop cannot mutate logical state/fences; stop/deadline/lost ownership blocks publication |
| WorkExecutionContext / DeliveryFailure | M1 context; producers classify bounded failure | M2/M4/M5; M1 completion | Immutable input plus read-only ExecutionControl; no private ORM/task; ownership/deadline blocks publication; M1 alone records transitions |
| Fixed registry / handler profile | M1 port; producer public factories register | M1 worker/M7 fixtures | Fixed kind/template/type/version; duplicate/unknown profile blocks capability |
| DeliveryWorkPayload | M1 dispatcher | Registered P5 worker | Identifier-only/version/scope/epoch strict; poison rejected without execution |
| RetryCommand / CancellationDecision | M1 public retry/internal coordinator | M1 lifecycle/M6 retry DTO | OWNER/ADMIN retry; classified internal cancellation; state/cause/key conflict rejected |
| PreparedOutput | M2/M4/M5 producer, M1 envelope | Producer publication port/M1 | Sealed validated candidate, not READY; exact scope/bundle/work/run/attempt/fence/dispatch epoch/candidate, all pinned profiles and applicable input/output fingerprints/digests mandatory; successor reuse rejected |
| ArtifactReference | M1 common shape; producer content | M1 barrier, M5 report, M6 status | Exact immutable committed generation/artifact/digest/size backed by sealed storage, not path/latest/stable-name assumption; unready/mutable/mismatched reference blocks |
| AcceptedOutput / PublicationReceipt | Producer validated output; M1 accepted receipt | M1 recovery/barrier, producer idempotent replay, M6 summary | Binds work/attempt/fence/input/candidate/reference digest; durable only after commit |
| PublicationContext / ProducerPublicationFactory | M1 transaction contract; producer adapter | M2/M4/M5 publishers | Same physical transaction; M1 never imports private tables/repositories; separate publication commit violates contract |
| OutputReadinessReader / ReadyValidation | Producer public port | M1 barrier/publication/retry | Bounded local exact-reference READY check; missing/incompatible/conflicting match blocks |
| DependencyReceipt | M1 coordinator | M1 dispatch/recovery; M6 wait reason | Immutable prerequisite IDs/digests or final-overview release decision/policy; never client READY |
| BarrierReceipt | M1 after all-four validation | M5 execution/M1 retry/M6 status | Four exact template refs/digest/report profile/fingerprint; stale/mixed/missing refs reject |
| DeliverySummary / RetryAcceptedResponse | M1 read/API service | M6 transport/React; M7 tests | Safe authorized scope/status/identity; no secrets or canonical mutation |

PublicationReceipt is the existing proposed delivery_outputs record, not a new table. DependencyReceipt is typed prerequisite/release evidence in existing work/bundle fields. BarrierReceipt is immutable bundle prerequisite JSON/fingerprint and report-work binding. Add these fields to the proposed P5 migration without expanding the seven-table structure or inventing another workflow engine. Receipt semantic hashes exclude storage timestamps/correlation.

Joint producer confirmation: M2 knowledge-generation reference/readiness; M4 spec/layout/server-artifact identity, sealing and publication; M5 pinned report prerequisites/readiness; M6 exact status/retry/errors/role forwarding. M3 consumes context identities without an invented background job; M7 tests these boundaries. Interfaces are finalized as this review proposal, not declared implemented or frozen downstream contracts.

### 11. Persistence Model and Database Constraints

#### 11.1 Proposed P5-owned tables

Use shared Base/engine, P5-specific tables, UUID PKs, timezone-aware timestamps, indexed scope, constrained enums and version/CAS columns. Cross-service project/repository/snapshot/actor UUIDs have **no foreign key to legacy Python platform tables**. M1 also avoids a new FK into frozen architecture/analysis tables; eligibility/ownership is established through public reads and immutable receipts. Local P5 relations use restrictive foreign keys.

| Table | Important columns | Database guarantees |
|---|---|---|
| `delivery_bundles` | id; VersionScope fields; source/policy/profile JSON+digests; eligibility; eligibility-check retry; automatic_report_fingerprint/work-slot; version/timestamps | Unique project/version/policy fingerprint; immutable scope/input; conditional report slot creation under lock |
| `delivery_work` | id,bundle_id,kind,template,logical_slot_key,run_number,is_current,retry_of_work_id; input fingerprint/profile; state; current attempt/fence; dispatch epoch/version/claim; next eligible; safe reason; dispatch/execution counters; cancellation cause/actor/time/prior fence | Unique slot/run; partial unique current run per slot; allowed kind/template and state; nonnegative counters; terminal run state immutable through repository operations |
| `delivery_attempts` | id,work_id,ordinal,fence,candidate_id,worker_id; lease secret digest/owner/heartbeat/expiry; state/start/end/error | Unique work/ordinal and work/fence; at most one RUNNING per work; terminal/end and running/lease consistency checks |
| `delivery_outputs` | id,bundle_id,work_id,attempt_id,fence,kind/template; exact scope; accepted reference JSON/digest; committed_at | One accepted output per completed work; unique receipt identity; local FK ownership chain and mandatory scope/fingerprint checks |
| `delivery_discovery_state` | policy/sweep key, cursor JSON/schema, sweep generation, scan lease/fence, last_completed_at and next pass | One concurrent owner per sweep partition; fenced checkpoint; reset at end; no source-table mutation |
| `delivery_runtime_capabilities` | capability/profile,worker_id,observed_at,ready,contract/deployment version, queue/deployment epoch | Expiring evidence for matching handlers/queue/reconciler; no source data; heartbeat does not imply infinite liveness |
| `delivery_retry_requests` | actor/project/action/key digest, request fingerprint, prior/new work IDs, response identity,created_at | Unique actor/project/action/idempotency key; same key/different request →409; repeat old request never creates another round |

`delivery_work` contains durable dispatch intent and next-send metadata; a separate generic outbox table is unnecessary. Every due QUEUED row is replayable intent. A bounded dispatch claim with expiry prevents concurrent reconcilers flooding the broker. This claim is not an execution lease and does not consume execution budget.

No separate inbox is needed for duplicate READY hints: accepted output identity and bundle/report-slot uniqueness deduplicate transactionally. If later transport requires an event inbox, that is new evidence/change control, not speculative M1 infrastructure.

#### 11.2 Migration implications

One additive Alembic revision creates the P5 tables, local FKs/checks/unique/partial indexes and claim/recovery indexes. Recheck migration head; the inspected chain ends at `c5d2e3f4a5b6`, but revision ID/filename is generated at implementation, not invented now. Add model imports to migration metadata registration only. Do not alter P3/P4 tables, historical migrations or source contracts.

Index due-dispatch `(state,next_eligible_at,dispatch_retry_at)`, active lease expiry, bundle/version scope, pending eligibility and retry-request uniqueness. Bundle policy audit also records the monotonic sibling-release reason/time; work cancellation fields record validated cause/actor/time/invalidated fence. These are P5-only additions in the proposed migration. Use database-enforced partial unique indexes rather than a SELECT-only singleton check. SQLite may cover pure mapping smoke tests but cannot replace PostgreSQL locking/index/constraint verification.

Downgrade requires stopping P5 workers/dispatch and preserving/exporting P5 records as approved; never cascade into P3/P4. Operational rollback normally disables P5 dispatch and leaves additive tables/data intact. No destructive migration or cleanup is run by this task.

### 12. Idempotency, Transactions and Concurrency Strategy

Use short explicit transactions and an injected clock backed by PostgreSQL time for production expiry predicates. Never hold row locks while calling broker, source API, layout/index/render/storage or doing a large model load.

Lock order whenever multiple P5 rows participate: **bundle → work rows in UUID order → attempt → producer publication rows**. Discovery scan/dispatch reservations are separately short, never held while acquiring bundle locks. Select candidate IDs first; recheck all predicates after acquiring locks. Retry serialization/deadlock errors only with bounded safe replay; never blindly replay an external side effect.

| Transaction | Atomic contents | After commit / crash rule |
|---|---|---|
| T1 discover | Bundle or pending-eligibility upsert; immutable scope/profile validation; eligible initial work creation; fenced scan checkpoint | Cursor advances only after durable decision. Duplicate observes same fingerprint; mismatch fails integrity |
| T2 prepare dispatch | Eligible dependency/capability/admission check; PENDING/RETRYING→QUEUED; dispatch epoch; short dispatcher reservation | Commit before send. Lost process leaves replayable due intent |
| T3 publish bookkeeping | Conditional last-send/error/backoff update for same current epoch | Broker success before bookkeeping crash may duplicate send; claim makes it harmless |
| T4 claim | Require locally available exact handler/profile before acquiring; verify payload/current run/epoch/scope and pinned profile under lock; atomic QUEUED→RUNNING; new attempt/fence/candidate/lease; execution count | Exactly one contender claims; duplicate returns no-op; missing/mismatched local handler consumes no execution |
| T5 heartbeat | Conditional attempt/current fence/unexpired lease renewal using DB clock | Invalid/expired lease cannot be revived |
| T6 success/publication | M1 fresh Connection/outer begin plus enlisted rollback_only Sessions; owner adapter locks/validates/stages READY; M1 receipt/completion/barrier; final live-fence CAS; one commit | All SQL effects commit or roll back; no distributed atomicity with external bytes; success only after commit |
| T7 failure/recovery | Conditional current-attempt failure/expiry, lease invalidation; retryability/budget/next-eligible; work RETRYING or FAILED; safe error | New attempt only after fresh dispatch epoch; stale worker cannot finish |
| T9 internal cancellation | Validated cause; lock bundle/work/attempt, invalidate epoch/fence/lease, preserve expired/terminal history, record audit | Late execution cannot publish; producer cleans isolated candidates; no public cancel endpoint |
| T8 manual retry | Authorize; lock bundle/current FAILED run; replay request key or insert new current successor run; durable retry response | Existing failed run/history retained; duplicate key yields same run/response |

#### 12.1 Atomic output publication and transaction ownership

| Distinct step | Owner / boundary | Visibility |
|---|---|---|
| Candidate creation | Producer execute phase writes unique attempt/fence/candidate namespace | Private staged bytes/ES generation only |
| Candidate validation | Producer independently verifies content/spec/layout/counts/digests/version/size outside locks; seals candidate writers | No READY acceptance |
| Producer resource publication | Enlisted producer repository locks its own rows, validates candidate and stages local SQL | Uncommitted, not externally visible |
| Active pointer / READY activation | Producer stages pointer/READY in the same PostgreSQL transaction | Visible only after outer commit |
| Accepted receipt | M1 validates exact returned scope/profile/candidate/reference and inserts receipt | Same transaction |
| Work/attempt completion and dependency release | M1 flushes receipt/dependency intent, then final conditional authorize-and-complete writes terminal records and revokes lease | Same single commit or rollback |
| Notification / dispatch | M1 after successful commit; durable intent remains authoritative | Hints only; no prerequisite truth |

**M1 owns the physical outer transaction.** Replace the unproven generic restricted-ORM facade with an explicit SQLAlchemy publication enlistment. After separate read/candidate sessions close, PublicationUnitOfWork opens one fresh engine Connection, calls Connection.begin before ORM work, and owns the transaction handle through one final commit/rollback. Bind the M1 Session and producer-enlisted Sessions to that same Connection using explicit join_transaction_mode="rollback_only". They operate sequentially in one thread/transaction; they are never threaded/shared or constructed from an independent engine.

The mode prevents Session.commit from committing the outer Connection, but does not forbid invoking the Session's own commit lifecycle or its events. Session.rollback may propagate rollback and invalidate the whole operation. Therefore rollback_only is secondary transaction protection, not the primary lifecycle guard. UoW commits only its private outer transaction after all guards/flushes succeed, and closes enlisted Sessions/Connection in finally. Do not reuse the request dependency's autobegun/teardown-committed Session or nest a new application transaction inside it.

**Public producer interface.** Immutable PublicationContext contains scope/input/profile/work/attempt/fence/candidate/deadline and transaction identity, no engine/Connection/private repository. A registered public ProducerPublicationFactory receives its borrowed enlisted Session at the trusted composition boundary and constructs its own repository, returning only its publication/readiness port. Producer owns its table locks and local validation; M1 sees no private repository/table. The ORM Session is an explicit trusted integration dependency, not falsely described as a complete capability sandbox.

**Dedicated lifecycle guard.** Proposed GuardedEnlistedSession (or an equivalently enforceable Session wrapper in publication.py) permits owner-table queries, add/update/delete and explicit flush, but rejects producer commit(), rollback(), close() and transaction-control access before executing those lifecycle operations. Each attempted violation first marks an M1-owned monotonic poison flag, then raises PublicationContractViolation. Catching the exception cannot clear the flag: M1 checks it after every producer call/flush, before final authorization and again before outer commit. A poisoned UoW must roll back, never continue toward success.

Only M1's private UoW completion/cleanup path may operate the outer commit/rollback and close enlisted Sessions/Connection. The guard must not obstruct that exclusive cleanup or treat it as a producer action. Retain rollback_only as a second defense, not a substitute for the guard. Producer independent Session/Connection creation, raw Connection/engine access and transaction-control SQL remain forbidden by composition/architecture tests and trusted-code review; this is not a Python security sandbox. Neither PublicationContext nor WorkExecutionContext exposes those handles.

**Producer Session event restriction.** No producer after_commit, after_transaction_end or equivalent lifecycle callback may notify external clients, activate storage/search, dispatch downstream tasks or claim the outer transaction committed. Session-level commit events are not proof of physical outer commit in rollback_only mode. Do not attach success side effects to producer Session events, including cleanup events after M1 closes a participant. Public factory/repository integration is local SQL only. External notifications/dispatch are M1-owned post-commit actions after confirmed outer commit; failed/rolled-back/poisoned UoW emits no success hint. Durable intent/reconciliation recovers post-commit notification or broker failure.

[SQLAlchemy 2.0 Session documentation](https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.params.join_transaction_mode) defines this mode's commit/rollback behavior. The pinned 2.0.52 source was inspected locally; this supports the design, not a completed real-PostgreSQL proof. Independent Session.commit cannot publish the coordinated transaction, while any rollback/connection loss aborts it. Savepoints and default conditional join behavior are not used to hide producer failures.

**Repository evidence and implementation gap.** backend/infra/postgres.py provides a shared engine/sessionmaker with autoflush=False; backend/platform/dependency_injection.py commits request sessions after yield. Existing graph repositories flush and use caller-owned commit boundaries, showing the pattern but not this new cross-module UoW. Existing local storage put overwrites bytes and has no sealing guarantee; it cannot be claimed to implement P5 candidate isolation. PublicationUnitOfWork, enlistment guards and downstream sealed stores are still NEW implementation/integration prerequisites.

**Ordered transaction — mandatory and testable:**

1. M1 locks the bundle.
2. M1 locks all participating work rows in deterministic UUID order.
3. M1 locks the current attempt.
4. M1 validates exact scope/work/run, dispatch epoch, current fence, live lease/deadline and required bounded publication budget.
5. The producer locks its own resource records in its documented deterministic order, through its public enlisted port.
6. The producer revalidates sealed candidate binding/digests/size/profile and stages READY metadata/active pointer.
7. The producer returns AcceptedOutput, still uncommitted.
8. M1 validates and inserts the exact publication receipt.
9. M1 stages dependency/report-barrier intent, retaining work/attempt ORM state RUNNING.
10. Final conditional live-fence authorization and terminal completion execute using PostgreSQL clock_timestamp(); only this operation sets terminal state/clears lease.
11. M1 confirms healthy/unpoisoned UoW and commits the single physical outer transaction.
12. Only after confirmed successful commit may M1 issue notifications/dispatch.

No producer hook may commit, perform external side effects or reverse lock order. Failed ordering/binding/guard checks poison or abort the transaction, never partially complete it.

Enlisted Sessions use explicit autoflush=False and are explicitly flushed for producer metadata/receipts/intents before final authorization; no pending ORM terminal-state change exists. Terminal completion uses only the final conditional database operation. No post-CAS ORM flush is permitted, and stale identity-map state is discarded on UoW close. Validate the outer transaction is still active after each participant and at final authorization. Never let a later Session flush commit unvalidated changes.

Any hook exception, invalid receipt, stale/cancelled ownership, expired lease/deadline before final authorization, zero-row CAS, SQL/commit failure rolls back all producer metadata/pointer, receipt, completion and downstream intent together. No success notification or successful completion result precedes commit. Ambiguous connection loss at commit is resolved by reading durable identities in a new transaction, not blindly rerunning side effects.

Completion ordering must not invalidate its own final guard: do not flush work/attempt terminal states or clear the lease before the final authorization. The repository's final authorize-and-complete operation checks the still-RUNNING current work/attempt and live lease, then conditionally updates both terminal records and clears lease ownership as one PostgreSQL statement (for example a guarded CTE), verifying the expected affected identities. Failure rolls back the whole transaction. No hook or substantial query runs after that final operation. When evaluating a barrier inside this same T6, only the coordinator may temporarily count its validated in-transaction candidate receipt alongside already committed sibling completions; the report intent remains invisible and rolls back unless final completion succeeds. Recovery outside T6 counts committed COMPLETED work/receipts only.

The final conditional live-fence CAS is the authorization linearization point. Row locks exclude takeover/cancellation until transaction exit. Expiry after that last authorization but before physical WAL commit cannot be tested atomically by application code; the already-authorized bounded transaction may commit. Do not claim a wall-clock lease predicate at the physical commit instant. Competing recovery waits/rechecks and cannot concurrently establish another owner.

**Heartbeat interaction.** Renew independently before entering publication if necessary; quiesce/join that attempt's heartbeat loop before acquiring publication locks, with no Session/lock held while joining. No self-heartbeat competes with the locked attempt during the short publication phase. Recovery observes approved lock wait limits. Rollback permits renewal only if ownership is still current/live; never revive an expired lease to accept the candidate.

**Bounded hooks.** Approved transaction-local lock_timeout/statement_timeout plus a monotonic whole-publication deadline/remaining-time SQL budgets prevent unbounded database waits. PostgreSQL 16 transaction-timeout support must not be assumed. Statement timeout cannot interrupt arbitrary CPU/network callback work, so such work is forbidden in publication adapters and exercised by separation/timeout tests. No numeric production limits are invented.

#### 12.2 External candidates and PostgreSQL-gated visibility

**External artifacts are prepared privately; PostgreSQL determines when their references become visible.** PostgreSQL cannot atomically commit filesystem renames, object uploads or Elasticsearch writes. External preparation, closure/sealing and integrity validation finish before the bounded SQL publication transaction. No distributed atomicity/durability is claimed.

**Candidate isolation/sealing:** keys bind exact project/version/work/run/attempt/fence/dispatch epoch/candidate scope. No cross-attempt reuse, shared mutable final filename/key or stale overwrite of a newer accepted object. Producer validates exact content, version, profile, digest and byte size and seals against later mutation before PreparedOutput. Old candidates cannot be relabeled for a successor attempt. A seal means the producer's actual store/index operations prevent continued writes to that generation, not that a boolean was set or a stable filename exists. Namespace isolation and sealing are both required; a database fence alone cannot block arbitrary external overwrites.

**Authorized exact-generation readers:** resolve the committed PostgreSQL READY/active record under project/version authorization and fetch precisely its immutable generation/artifact reference, checking expected digest/size/version as the producer contract requires. Never inspect the newest external generation as fallback, read an uncommitted candidate, use mutable alias/latest, silently substitute another version, or treat physical existence as publication. Apply equally to files/object storage, diagrams/PDFs and knowledge/search outputs. Missing/corrupt accepted bytes produce explicit producer availability/integrity failure and repair, not alternate data.

For M2, preserve the approved isolated Elasticsearch candidate generations and PostgreSQL accepted-generation pointer. Mutable alias swaps are not authoritative activation. Search readers bind the accepted physical index identity/generation and scope; they never fall back to an uncommitted or merely newest ES generation. Generation-changing pagination rejects continuation under existing C1 requirements. ES remains rebuildable derived data, never canonical architecture.

**Producer-owned orphan cleanup:** before deletion the producer must establish (1) no accepted reference anywhere points to the candidate, including historical reports; (2) no active attempt owns it; (3) no in-progress publication can still accept it; and (4) the approved grace period elapsed. A single unlocked absence check or wall-clock lease expiry is insufficient. Use producer-owned candidate-row serialization/cleanup marking with public M1 ownership information, preserving the publication lock order and module boundaries; publication must reject a cleanup-marked candidate. Require durable attempt retirement/fencing, not an attempt that might still finish its already-authorized transaction. Recheck under the producer's cleanup/publication exclusion before deletion.

This cleanup decision is a producer implementation gate, not permission for M1 to query producer tables/delete bytes or invent a cleanup queue. Check references/liveness through their owning modules' public contracts, not another module's private tables. Serialize against accepted-reference creation and hold/record deletion authority across the external deletion boundary; crashed/partially completed cleanup retries idempotently and can never delete accepted/active/in-publication candidates. Tombstone/deleting metadata, if chosen by the producer, is private candidate metadata, not a new canonical/public lifecycle. The reference/grace/ownership checks require producer-specific joint review and proof.

Failed SQL publication may leave a private orphan but no READY output; cleanup/recovery belongs to the producer. Committed metadata followed by external loss is a producer failure; SQL atomicity does not guarantee external durability. If candidate sealing, exact-generation readers, cleanup exclusion or same-transaction publication cannot be implemented, production integration remains blocked until an equivalent independently reviewed fenced protocol exists.

### 13. Worker Dispatch and Handler Registration

Use new `backend/worker/delivery_tasks.py` registered in the existing Celery app. Proposed allowlisted tasks: `stacksense.execute_delivery_work`, `stacksense.reconcile_delivery`, `stacksense.delivery_runtime_heartbeat`. No per-template task names from user input, arbitrary dotted imports or new diagram queue.

Initial routing recommendation remains existing `settings.analysis_queue_name` (`analysis.jobs`). Add only P5 include/routes/beat entries; preserve all frozen task routes, priorities, serializer, retry and acknowledgement settings. Approval must cover new composition and measured sharing behavior before Batch 2. Do not alter graph maintenance routing to make P5 work run.

On a shared queue, one compatible heartbeat does not guarantee which consumer receives a message. Dispatch enablement therefore requires the supported consumer fleet to have the new fixed P5 task registration and agreed handler-profile support; rolling deployment must disable P5 dispatch until incompatible consumers are drained/upgraded. An old worker rejecting an unknown task can otherwise discard a delivery, which durable redispatch recovers but cannot make timely. Test this deployment case explicitly. Do not claim task-specific consumer targeting or priority isolation that the current queue does not provide.

Worker steps: validate strict payload → read pinned config/profile and resolve matching local handler → acquire current epoch atomically while rechecking that profile → execute with bounded deadline/checkpoints → fenced publish/complete transaction → safe acknowledgement/result. Celery `max_retries=0` for this entrypoint: database policy alone controls automatic retry. Broker redelivery does not imply duplicate execution. A worker missing the profile records a bounded capability mismatch and leaves execution unclaimed; admission/reconciliation must stop repeated incompatible deliveries until a matching consumer is available.

**Identifier-only payload and compatibility invariant:** retain exactly the DeliveryWorkPayload fields in §10; its C0 version/correlation tags do not authorize embedded profiles, configuration, fingerprints, candidate contents or credentials. Reload pinned producer/generator/schema/config profiles and fingerprints from the exact durable bundle/work run. Validate supported C0 and local profile compatibility before claim, and recheck durable scope/run/epoch/profile under the claim lock; create attempt/fence/candidate identity only through M1's claim. A mismatch must not consume an execution or substitute newer/default code. Execute and publish against that same pinned profile; unknown broker fields are rejected, not trusted overrides. This adds no producer lifecycle authority or new broker contract fields.

`WorkHandlerRegistry` has an explicit allowlist and exact profile/version matching. Startup rejects duplicate/contradictory registrations. Missing downstream implementations remain pending with safe status and no attempt consumed; integration tests use controlled fixture handlers. Capability registration includes execution contract/producer profile and observed time. A worker with older/missing code must not consume an attempt executing a different generator version.

Publisher bounded connection/write timeout and optional RabbitMQ confirms use the existing Kombu/Celery connection APIs after verification. Confirms improve observability but cannot make database/broker exactly-once. Persisted due intent and idempotent claims remain necessary. Never record “dispatched” before attempting publication as proof that work exists in RabbitMQ.

Malformed/unknown-version payload: reject/no execution, safe code/correlation log, no sensitive payload dump; acknowledge or reject without requeue according to explicitly tested poison policy. Do not requeue forever or introduce a DLQ without approval. A genuine transient DB failure before claim remains recoverable from durable intent regardless of broker ack/redelivery outcome.

#### 13.1 Shared-queue deployment, capability and rollback protocol

The inspected ops/systemd analysis worker/Beat units provide existing processes, not proof of every deployed RabbitMQ consumer. No new production queue, broker or worker service is proposed.

1. **Preflight with P5 dispatch disabled:** inventory actual consumers of the selected queue, worker names, code/contract revisions, handlers/profiles, bindings and possible manual/remote consumers. Compare with an owner-reviewed rollout manifest. A single Celery inspect response or generic heartbeat is insufficient.
2. **Deploy registration before messages:** ship additive schema/task registration and profile-aware code with dispatch still disabled. Gracefully drain/restart every shared-queue consumer after its existing analysis work; do not kill analyses or change graph queues. Restart compatible Beat. Existing units reload .env on restart; imported task code is not hot-reloaded.
3. **Verify each consumer:** fixed task names, exact C0 contract, pinned producer/generator/schema/config profiles, deployment epoch and queue binding. Missing downstream handlers remain honestly unavailable; do not dispatch those kinds.
4. **Prove runtime capability per worker:** record worker identity/epoch/queue/contract/exact supported profile and observed-at after successful handler initialization. Refresh via hooks/timer on the existing worker process, not a new service. A capability task processed by any one worker cannot prove all peers. Verify actual reconciler/Beat execution separately.
5. **Enable only the compatible fleet:** every supported consumer able to receive enabled P5 work must understand the envelope and enabled profiles. Fresh required capabilities + complete approved fleet inventory + schema and approved admission limits gate dispatch. One matching consumer cannot steer tasks away from an incompatible peer on the same queue.
6. **Rolling deployment:** disable new P5 dispatch before a mixed-version window, drain existing P5 messages on compatible workers and settle/safely fence active attempts before downgrading peers. Preserve normal existing workload progress. Old Celery workers may reject/acknowledge/discard unknown tasks: recover QUEUED intent by redispatch or RUNNING work by lease expiry once compatibility is restored. This guarantees durable recoverability, not absence of transport delay.
7. **Mismatch/unknown consumers:** disable affected P5 dispatch, expose capability mismatch and alert. Heartbeats cannot prove an unidentified worker cannot connect later. Where fleet inventory/admission and graceful draining cannot be guaranteed, dispatch enablement is blocked pending owner-approved deployment control; do not quietly create another queue/service or claim targeting/priority isolation.
8. **Rollback:** disable P5 scheduling/dispatch first, drain compatible envelopes and resolve active attempts; retain additive schema, accepted receipts and published output. Revert code only when no envelope needs unavailable registration/profile. Re-enable solely on a compatible fleet; replay missing messages from durable state, never purge the shared queue.

The smallest compatible rollout is an owner-controlled maintenance window with the existing units: reconcile every broker consumer to a known worker/process and profile, stop/drain unknown or incompatible consumers, prohibit unmanaged shared-queue peers during enablement, then reopen dispatch. This requires fleet/consumer mapping and an enforceable operator admission process; another worker's heartbeat cannot supply either. If mapping or admission cannot be established, keep dispatch off. Do not introduce a new broker/queue/service or silently change credentials/network controls to claim the gap solved.

Actual fleet admission is not currently enforced by a verified repository subsystem. The runbook/owner-controlled deployment window is an approval gate; new infrastructure enforcement, if needed, requires its own authorization. Test unknown-task discard, incompatible profile, expired capability, dispatch-off rollout/drain, rollback and resumed durable delivery alongside existing analysis/graph work.

### 14. Lease, Heartbeat and Fencing Design

Claim identifies work/current run/dispatch epoch, then creates a new attempt UUID, monotonic fence and unpredictable lease secret. Store only secret digest if feasible; never send it through broker/log/API. Worker keeps secret transiently; publication/renewal validates attempt ID, worker, token digest, fence, current run, state and `expires_at > DB_now`.

Lease renewal uses a separate short Session/transaction, never the handler's long-running Session. Independent bounded heartbeat loop is appropriate for blocking handler work; it cannot share a SQLAlchemy Session across threads. A failed renewal sets an execution-stop/lost-ownership signal and prevents publication; it does not itself cancel the logical run. Checkpoints and hard per-handler process/deadline controls belong to execution integration; M1 cannot claim to interrupt arbitrary Python code instantly.

Quiesce the heartbeat before entering the bounded publication transaction as specified in Section 12.1. Final live-fence authorization controls publication; no heartbeat is assumed while the attempt row is locked. Internal cancellation serializes on the same locks and invalidates fence/epoch, distinct from expiry/failure.

Once expired, renewal must fail even if no reconciler has claimed recovery yet. Recovery locks and rechecks: either a timely heartbeat already extended expiry, or the attempt becomes EXPIRED and is fenced out. A race cannot both renew and recover successfully. No machine-local wall clock determines lease validity; monotonic clocks enforce local deadlines while PostgreSQL timestamps govern distributed ownership.

No M2/M4/M5 producer can bypass T6 with its own stale `activate` call. Contract tests explicitly pause an old worker, expire/retry/complete a newer attempt, then allow the old worker to return; old output and dependency release must both be rejected.

### 15. Reconciliation and Recovery Strategy

#### 15.1 Discovery and eligibility

The public source enumerates all published headers, not only successful analyses. Validate header project/repository/analysis/snapshot/version against the public analysis representation and exact canonical read/digest as needed. Eligible status is only COMPLETED or COMPLETED_WITH_WARNINGS. PARTIAL/TIMEOUT/RUNNING are not eligible; persist WAITING_FOR_ANALYSIS and revisit. Terminal failure/cancellation is INELIGIBLE, without modifying the analysis or pretending a delivery error caused it.

Already accepted immutable bundle/header fingerprints can be compared without repeatedly loading the entire canonical payload during every sweep. Perform necessary initial exact-load validation outside locks, one bounded version at a time; producers later load their exact immutable input through public ports. No unbounded cache of complete ArchitectureDocuments is needed for discovery.

Do not insist the analysis's convenience latest-version pointer equals every historical published header: multiple published versions may be associated with an analysis. Validate the requested header/document's own identity and publication, retaining every exact version. If an ownership field cannot be checked through the public DTO, treat it as an unresolved source contract gate, not a private SQL shortcut.

Persist a leased/fenced bounded scan cursor. When a pass reaches the end, reset to None and record completion; new publications can sort before a previously saved cursor. Resume after crash, deduplicate existing bundles, revisit pending eligibility independently, and measure oldest incomplete sweep/pending age. Advance checkpoint only after a durable per-header decision; a malformed header is durably quarantined with safe error so unrelated versions can progress without silent omission.

Bound pages/time per reconciliation invocation; no copied P4 all-history while loop without a work budget. Fairness between pending eligibility, live discovery, backfill, dispatch and expired-lease recovery is explicit. No fast chronological discovery interface currently exists; if repeated sweeps cannot meet approved latency at measured scale, seek change control for a public source enhancement rather than modifying P3/P4 during M1.

#### 15.2 Recovery passes

Each bounded pass performs: due pending eligibility → limited discovery pages → expire/recover leases → unblock dependencies/capabilities → reserve/send due durable intent → reconcile completed receipts/report barrier → emit safe summary. A failed broker or source call cannot roll back previously committed work for other versions.

Recovery handles restart after bundle insert, after QUEUED before send, after send before bookkeeping, after claim, during heartbeat, after external candidate creation, during publication SQL, after SQL success before ack, and after report creation before send. Database state determines the next action; no “Celery result SUCCESS” overrides it.

Checkpoint leases, dispatcher reservations and capability rows themselves expire/recover. Reconciliation task registration or import success is not runtime readiness; expiring heartbeats prove actual queue execution. A missing Beat/consumer yields unavailable/degraded delivery status and operator action, not indefinite unexplained queued work.

### 16. Retry and Failure Classification

| Failure | Proposed handling | Execution budget / visibility |
|---|---|---|
| Broker connection/publish timeout | Backoff durable dispatch; replay same epoch safely | No execution consumed; work remains queued with dispatch error |
| Source/public read unavailable | Revisit eligibility with bounded backoff | No output execution consumed; no analysis mutation |
| Matching handler/worker capability absent | Block pending dispatch and expose reason | No execution consumed; no fake FAILED output |
| Worker loss/lease expiry | End attempt EXPIRED; fresh epoch/attempt if budget remains | One acquired execution consumed; stale return rejected |
| Producer transient dependency/I/O | FAILED attempt, RETRYING work until approved budget exhausted | Independent sibling work continues |
| Invalid scope/schema/fingerprint/provenance | Nonretryable integrity failure/quarantine | No publication or downstream release; safe operator evidence |
| Producer deterministic invalid/capacity output | Nonretryable failure until authorized changed input/config | No silent truncation, cap increase or automatic retry loop |
| Unknown handler exception | Safe internal failure; default nonretryable unless explicitly classified | No traceback/source in API; preserve private correlation |
| Stale epoch/token/current-run mismatch | No-op rejection/fenced result | Does not consume another execution or alter newer state |
| SQL deadlock/serialization before committed result | Bounded local transaction retry if side-effect safe | No duplicated external side effect or reset of attempt budget |

Backoff parameters, jitter, total budget, per-project admission, manual retry rounds and retention are pending measured defaults. Jitter is deterministic under an injected test RNG, not part of output identity. Retryable classification is an allowlist, not any exception with a string containing “timeout”.

Cancellation is not a retryable failure: apply Section 9.3's authorized run policy and fencing; do not turn heartbeat loss, deployment drain or final overview failure into logical cancellation. A producer execution-stop result without current ownership cannot mutate a newer run.

Existing terminal runs/attempts and published outputs are preserved. Failed-candidate bytes belong to output-module cleanup; M1 does not delete artifacts or determine historical report retention. New policy/profile is a new versioned input, not a stealth retry using changed global defaults.

### 17. Automatic Report Prerequisite Barrier

Required templates are exactly system_overview/component_architecture/dependency_map/data_flow. A count of four arbitrary diagram records is insufficient.

Under the bundle lock, the barrier must:

1. Require ELIGIBLE exact published-successful VersionScope and pinned policy/report profile.
2. Read the accepted output receipt for each required logical template slot; ensure producing work completed under current accepted fencing rules, or is this T6's sole coordinator-validated tentative completion subject to its final authorize-and-complete guard. READY signals/client data alone are insufficient. No other unfinished candidate counts.
3. Invoke producer public readiness validation in the same transaction, checking immutable generation/resource/artifact IDs, same project/repository/analysis/snapshot/version/canonical digest, required spec/layout/server artifact digests and durable READY metadata.
4. Pin the exact four validated references, ordered by stable template ID, and compute report prerequisite fingerprint. No mixing versions, foreign templates, old candidate refs or latest-pointer substitutions.
5. If absent, create the single automatic report logical slot/current run with pinned inputs and durable dispatch intent; record its identity/fingerprint on the bundle. A uniqueness conflict reloads/verifies the same identity, not an unexplained success.
6. Commit with upstream acceptance/work completion. Sending a report message occurs afterward via normal dispatch recovery.

Concurrent completions serialize briefly on the bundle. First three commits create no report; the fourth creates one. Duplicate notifications/reconciliations return the existing report identity. Rollback of producer publication leaves no READY receipt and cannot satisfy the barrier. If the completion hint is lost, periodic receipt reconciliation produces the same result.

Initial report eligibility pins historical immutable diagram generations, not mutable active pointers. A later diagram regeneration does not alter a queued/published report, auto-create another report, or overwrite prior bytes. New report generation policy remains M5/owner controlled. Manual retry of a failed report preserves its four pinned references; if integrity/readability validation fails, block it rather than substitute different diagrams.

Overview has priority: siblings wait for overview READY on the normal path or for its durable terminal FAILED state on the failure path. Retryable attempt failure keeps them waiting. Terminal failure releases the other three independently, with an explicit priority-failed note, but automatic report creation remains blocked. This requested product policy is incorporated into the joint-review proposal; it is not permission for a text-only automatic report.

#### 17.1 Overview failure, recovery and report pinning

An overview attempt failure is not necessarily a final logical-run failure. While a classified retryable attempt is FAILED/EXPIRED and the run is RETRYING/QUEUED with budget remaining, the proposed priority policy holds unreleased sibling diagrams with waiting_on=overview_retry. Overview final failure means the current logical run has durably reached FAILED for a nonretryable cause or exhausted automatic executions; a broker outage, unavailable handler, missing heartbeat or mere queue delay is not by itself that terminal condition.

Under the bundle lock, a durable final FAILED overview run sets a monotonic sibling-release DependencyReceipt and enables only still-pending siblings through normal durable intent. Already running/completed siblings are unchanged; repeated recovery creates no duplicate work. Persist reason, failed work identity, policy version and release time, never a fabricated overview READY. Cancellation alone does not meet final-failure release; it is a distinct authorized policy state requiring explicit reevaluation, not an implicit fallback.

Status reports the failed overview run/error/attempt budget, authorized retry availability, each sibling's independent state, and report waiting_on=system_overview (plus any other missing/invalid template). No text-only report is scheduled.

An authorized retry creates a new current overview run with identical pinned source/input/profile and a stable retry-request key; failed history stays immutable. No public cancellation operation is needed. Producer owns candidate build/publication through the fenced transaction. On its successful READY acceptance, reevaluate the barrier transactionally; retain previously accepted valid sibling references rather than rerunning them. The monotonic sibling-release decision is not reversed during overview retry.

If the automatic report was never eligible, the first complete valid four-reference set creates its one automatic report logical operation; this is not a second report caused by “recovery.” If report work already exists (queued/running/completed/failed), keep its original four references and input fingerprint; new/regenerated overview refs cannot rewrite it or automatically create another operation. Changed-input/manual report regeneration is separately controlled by M5/owner policy.

Successful siblings are reusable only when their committed READY reference matches bundle project/repository/analysis/snapshot/exact version/canonical digest, required template and pinned generator/schema/config profile, with valid immutable spec/layout/server-artifact refs; do not require sibling regeneration simply because the overview acquired a new attempt/run. A regenerated overview may replace the selected reference for the first not-yet-created report only through an authorized same-input/profile current-run acceptance. A changed generator/config profile requires an explicit new policy/operation, not silent reuse of the original bundle. Receipt selection binds accepted work/run identity and exact scope; reports never choose an arbitrary latest artifact. Duplicate recovery notifications return the existing acceptance/report identity. Mixed scope/digest/version still fails closed.

#### 17.2 Barrier identity, history and general renderer boundary

The BarrierReceipt fingerprint is SHA-256 of tagged canonical JSON containing C0/barrier-policy version, exact VersionScope identity/canonical digest, report type/template/schema/generator/config profile, and the four required template entries sorted by stable template ID. Each entry contains accepted receipt/work identity, producer resource/generation/artifact IDs, input profile fingerprint and content/spec/layout digests. No volatile timestamp, event/correlation ID or active/latest alias participates.

Bundle lock plus unique automatic-report slot/bundle constraint admits one automatic report operation. Replaying an identical complete set returns it; a different set after that operation exists cannot replace its pinned BarrierReceipt or create another automatic operation. Manual report retry creates a successor run for the same immutable input; published reports and prior terminal runs remain historical. Search failure is unrelated and cannot block an otherwise valid barrier.

Three READY diagrams, wrong templates, failed/missing references, mismatched scope/digest/profile, or stale/incompatible candidate validation all block. Here stale means invalid for the requested pinned bundle/input, **not** merely a valid historical Architecture Version or non-latest immutable generation. Producer readiness validates the exact reference; it must not require a historical artifact to become current globally.

Master 17.80 and 17.90.38 preserve the broader renderer/engine ability to produce permitted text-only reports. P5 baseline Sections 9.2–9.4 specify prepared ReportSpec and the strict all-four automatic product gate. These coexist: M1 creates only this gated product and has no text-only fallback branch; the general renderer contract must not globally require all four diagrams for every future/manual template. Any manual/future text-only product is outside M1 and cannot bypass this automatic endpoint. No master/ADR/baseline edit is required for that separation; any later proposal to remove general capability is a separate joint-review conflict.

M1 Batch 3 uses controlled producer stubs and immutable ready references. That validates concurrency and contracts, not actual M4/M5 layout/PDF behavior; real all-module integration remains later P5 acceptance.

### 18. API and Authorization Requirements

New FastAPI routes are proposed under existing `/api/v1`; Express exposure belongs to P5 M6. No M1 Express changes. Reuse existing delegated auth/project checks and safe error shape.

| Endpoint | Request | Response and rules |
|---|---|---|
| GET `/architecture-versions/{versionId}/delivery?project_id=...` | Exact UUIDs and trusted actor/project context | 200 `{scope,bundle_id,policy_version,eligibility,diagrams:[...],search,report,waiting_on,capabilities,updated_at}`; all authorized project roles |
| POST `/architecture-versions/{versionId}/delivery/retry?project_id=...` | `{resource_type,resource_id,idempotency_key}`; strict allowlist and bounded key | 202 `{scope,operation_id,work_id,retry_of_work_id,state}` after durable creation; only an existing eligible failed logical operation, no arbitrary task/profile |

Status distinguishes not-yet-discovered/pending eligibility, pending dependency/handler/worker, dispatch error, running, terminal failure and retained ready output. Each diagram summary includes stable template, safe state/reason, work/reference IDs and attempt progress—not lease tokens. Include overview final/retryable failure, monotonic sibling-release reason, report prerequisite wait and safe internal-cancellation cause where applicable. No public cancellation endpoint is added. Report waiting_on lists exact missing/invalid prerequisites. If published scope exists but bundle not yet exists, return a nonmutating not-scheduled status, not a fake missing architecture 404.

Role policy incorporated for review: OWNER/ADMIN may retry eligible failed P5 work; all four roles read status; DEVELOPER/VIEWER retry receives 403. Frozen P3 create/cancel admits DEVELOPER, so reuse trusted delegation/project validation but implement the P5-specific role check separately. Automatic derived execution is internal code over approved published scope, not a forged actor request; audit `actor_type=system` without accepting that as a new delegated public role.

Statuses: 401 missing/invalid service auth; 403 scope/role failure; 404 exact inaccessible/missing resource under existing disclosure policy; 409 not-retryable/active run/idempotency conflict/prerequisite mismatch; 422 malformed/unsupported request; 503 delivery persistence/capability unavailable when operation cannot be accepted. A temporarily unavailable broker may still yield 202 if intent is durably recorded and runtime policy permits recovery; acceptance is not a claim that the task ran.

New errors live in P5 `api_contracts.py`/local router translation, preserving `{error:{code,message,details}}`. Existing global error map does not know new delivery codes; do not silently let all conflicts become 422/500, or modify frozen error mappings without approval. Auth exceptions continue through existing handlers. Standard FastAPI validation shape is preserved/documented as currently established, not globally rewritten.

### 19. Dependency Injection and Composition

`delivery/dependencies.py` composes request-scoped coordinator/read models, P5 repository and source adapter from existing settings/Session/public services. Workers construct the same application services with short independent Sessions, explicit transaction boundaries and clocks/publisher/registry supplied through DI. Publication alone uses M1's fresh Connection-owned PublicationUnitOfWork; producer public factories receive explicit transaction-enlisted rollback_only Sessions and build their private repositories internally. No request teardown or producer method independently commits accepted output. No process-global ORM Session or mutable registry of caller-supplied classes.

`PublishedVersionReader` wraps exported `SqlAlchemyPublishedArchitectureSource` and a public analysis-read callable supplied from `get_analysis_lifecycle_service`/its service construction. Verify that constructing this service does not perform unnecessary source/network reads for `get_analysis`; if composition needs a lightweight public read provider not currently available, flag the exact gap instead of importing private repositories.

Composition additions are narrowly scoped: P5 router include, Celery task/beat entries, P5 model registration, additive P5 settings/env examples. Batch 2 requires explicit approval of those existing-file edits; the phase module approval is not assumed to authorize all frozen composition/config defaults. M1 changes no Express file or ADR.

Downstream registration occurs at the composition root through public handler factories. M1 imports its protocols, not output-module internals. A fake/fixture handler can satisfy the full lifecycle/publication protocol before M2/M4/M5 implementations exist. Unregistered work stays safely pending; no stub returns success in production.

### 20. Observability and Operational Controls

Required safe identifiers: project/version/bundle/work/attempt/dispatch epoch/candidate/profile/correlation and worker identity. Do not log lease secret, broker URL credentials, source bytes, arbitrary upstream messages or unbounded config/query/spec data.

Metrics: publication-to-discovery, sweep age/pages/pending eligibility age, queued age and dependency wait, dispatch connection/send/backoff/failure, claims/duplicate no-ops, heartbeat/lease expiry/stale rejection, per-kind execution/retry/final failure, report barrier rejection reason and duplicate creation avoidance, worker capability age and reconciliation backlog.

Health separately reports configured task registration, actual recent reconciler/worker capability, database readiness, broker reachability and producer readiness. Missing downstream handler is an honest pending capability, not canonical-platform failure. Existing analysis/graph health behavior remains unchanged.

Operational controls to measure and approve before production wiring: scan page/time budgets, discovery/reconcile interval and fairness, dispatcher reservation/replay time, DB statement/lock timeouts, lease/heartbeat/capability TTL, per-handler hard deadline, automatic executions/backoff/jitter, per-kind/project admission, bounded payload/config/error lengths and record retention.

Invariants rather than invented defaults: heartbeat interval < lease duration; capability TTL > heartbeat interval; recovery age accounts for valid in-flight send/claim; per-task work is bounded; counters cannot overflow; publication requires live ownership at the final fenced authorization point with bounded commit, as precisely defined in Section 12.1. Test with small injected values but do not promote them to production defaults.

Benchmark queue-sharing interference against existing analysis latency and worker RSS on named hardware. This is an M1 scheduling benchmark with fixture handlers, not an M4 layout/index/PDF performance claim. No new queue or raised global worker concurrency is silently introduced.

### 21. Security and Tenant-Isolation Requirements

All database selectors include authorized project and exact scope; payload IDs are untrusted until matched to durable rows. No cross-project work lookup followed by post-filtering. Public retry cannot change work kind/template, requested source/schema/profile or reference scope.

Production trusted delegation is reused and independently checked by Python. Test current-user shortcuts never authenticate delivery routes. No raw source, user bearer/refresh token, service token or absolute artifact path in bundle/work/broker/API data. P5 persistence is Python-owned; no MongoDB connection or FK to historical Python users/projects.

Worker execution is fixed registry code, never imported from request strings. Typed candidates and opaque references have bounded serialization. Secret lease tokens stay out of messages/logs/status; expiry/revocation prevents stale publication. Authorized internal cancellation invalidates epoch/fence without deleting outputs; external candidates are private/sealed and cannot overwrite another attempt's namespace. Per-project admission/retry limits prevent an authorized user exhausting the shared analysis queue.

Platform names/revision display metadata are not required to create M1's scope or barrier. The phase plan's D11 metadata interface belongs to later approved transport/report preparation; this module neither adds that Express route nor pretends the manifest already returns project/repository names.

### 22. File-by-File Implementation Inventory

Every NEW path is proposed. Braced test names below expand to the explicitly named files; no path is claimed to exist merely because listed. No deletion or frozen module refactor is proposed.

| Action/path | Components and reason | Batch / dependencies / primary tests |
|---|---|---|
| NEW `backend/platform/delivery/__init__.py` | Limited public contract exports, no side-effectful initialization | B1; import/namespace tests |
| NEW `backend/platform/delivery/contracts.py` | VersionScope, policy/profiles, payload, work/candidate/reference/failure/publication protocols | B1; schema/version/deep immutability/scope/fingerprint tests |
| NEW `backend/platform/delivery/model.py` | Bundle/work/attempt/run state transitions, logical slot and eligibility rules | B1; allowed/forbidden transitions and terminal history |
| NEW `backend/platform/delivery/source.py` | Public-port PublishedVersionReader and eligibility adapter | B1; frozen source/analysis read fixture contracts, no private imports |
| NEW `backend/platform/delivery/repository.py` | P5 persistence protocol + SqlAlchemyDeliveryRepository: upsert, current runs, claims, heartbeats, fence, receipts, retry keys, cursor and report uniqueness | B2/B3; real PostgreSQL concurrency/rollback tests |
| NEW `backend/platform/delivery/persistence.py` | Seven P5 ORM tables and database constraints only | B2; metadata/migration/unique/partial index tests |
| NEW `backend/platform/delivery/service.py` | DeliveryCoordinator, bounded discovery/dispatch/recovery; completion/report barrier/status/retry coordination | B2/B3; transaction boundary/failure matrices |
| NEW `backend/platform/delivery/publication.py` | PublicationUnitOfWork, immutable PublicationContext, Connection-owned UoW, GuardedEnlistedSession/monotonic poison, rollback_only secondary defense, callback restrictions and public producer factory/port; owns outer transaction/final fence and invalidates borrowed views on exit | B1 protocols/fixtures, B2 real SQL atomicity/timeout/heartbeat tests |
| NEW `backend/platform/delivery/registry.py` | WorkHandlerRegistry, exact supported profiles and controlled publication invocation | B1 contract/B2 execution; unknown/duplicate/stale producer tests |
| NEW `backend/platform/delivery/queue.py` | Strict payload publisher, existing Celery/Kombu adapter, bounded send and no-op test publisher | B2; identifier-only/duplicate/connection failure tests |
| NEW `backend/platform/delivery/dependencies.py` | P5 request/worker factories around existing public engine/auth/source/read providers | B2/B3; wiring, Session/Connection lifetime, forbidden producer commit/rollback, outer transaction and rollback tests |
| NEW `backend/platform/delivery/api_contracts.py` | Delivery summary/retry/accepted/error DTOs and local status translation | B3; response schema/status and safe details |
| NEW `backend/api/v1/delivery.py` | Two authorized status/retry endpoints with local P5 errors | B3; auth/project/resource/idempotency API tests |
| NEW `backend/worker/delivery_tasks.py` | Three fixed tasks, runtime heartbeat, execution/ack/lease loop orchestration, no business output algorithms | B2; registry/capability/redelivery/crash tests |
| NEW migration under `backend/infra/migrations/versions/` (generated revision name) | Add only P5 tables/indexes/FKs; exact head rechecked | B2; isolated PostgreSQL upgrade/constraint/rollback compatibility |
| MODIFY `backend/infra/migrations/env.py` | Register new P5 models in shared metadata | B2; scoped additive-only approval |
| MODIFY `backend/worker/celery_app.py` | Add delivery include, task routes and bounded beat entry on existing queue | B2; explicit composition/queue approval, existing-route regression |
| MODIFY `backend/platform/config.py` | Add independently approved P5 settings/invariants; preserve existing defaults | B2/B3; validation and unchanged P3/P4 config tests |
| MODIFY `.env.example`, `.env` (later approved values only) | Match new setting names; local secrets preserved, no production secret defaults | B2/B3; no env change authorized by this planning task |
| MODIFY `backend/api/v1/router.py` | Include delivery router only | B3; OpenAPI and existing route regression |
| NEW `tests/p5/__init__.py`, `tests/p5/delivery/__init__.py`, `tests/p5/integration/__init__.py` | Match repository test-package conventions | B1/B2; no shared global TestClient change |
| NEW `tests/p5/delivery/test_contracts.py`, `test_model.py`, `test_source.py`, `test_registry.py`, `test_execution_control.py` | C0 schemas/state/source/profile behavior | B1 |
| NEW `tests/p5/delivery/test_dispatch.py`, `test_recovery.py`, `test_fencing.py`, `test_cancellation.py`, `test_publication.py`, `test_rollout.py` | Durable intent, restart/epoch/claim/heartbeat behavior with controlled fakes | B2 |
| NEW `tests/p5/delivery/test_barrier.py`, `test_api.py` | Exact four-template scope, concurrency/idempotency, role/status/retry | B3 |
| NEW `tests/p5/integration/test_delivery_postgres.py` | Real locks, unique constraints, DB time, multi-connection races, publication rollback | B2/B3 |
| NEW `tests/p5/integration/test_delivery_rabbitmq.py` | Real routing/ack/redelivery and actual worker fixture execution/restart | B2/B3 |
| NEW `tests/p5/integration/test_delivery_acceptance.py` | Source success→four fixture outputs→one fixture report; all crash boundaries and scope attacks | B3 |
| NEW `tests/p5/benchmarks/test_delivery_capacity.py` | Bounded sweeps/dispatch/fairness/RSS, namespaced fake handlers | B2 evidence; no new production defaults by fiat |
| REUSE existing public source/auth/analysis service/engine/Base/test tooling listed in Section 3 | Dependency injection and read-only contracts | All batches; no edits |

Not M1 targets: `delivery/platform_metadata.py`, `delivery/artifacts.py` storage implementation, output packages, Express, frontend, P3/P4 repositories, global error handler, frozen contract files, ADRs and master. No new dependency file change anticipated.

### 23. Testing and Verification Strategy

#### 23.1 Required evidence

| Test group | Required cases |
|---|---|
| C0/domain | Unknown fields/versions, forged UUID scope, invalid Unicode/NaN, immutability, fingerprints/transitions/terminal history; ExecutionControl cannot mutate work/fences; expired deadline/lost ownership blocks publication; mismatched prepared attempt/fence/epoch/profile and mutable/non-exact references rejected |
| Source | Published but RUNNING analysis, terminal warnings, PARTIAL/TIMEOUT rejection, pending later succeeds, historical version not latest pointer, new publication before scan cursor, crash before checkpoint, duplicate/invalid headers |
| SQL races | Two creators one bundle/slot; two messages one claim; two heartbeat/recovery contenders; expired renew rejected; stale completion; current-run uniqueness; duplicate retry keys and concurrent manual retry |
| Dispatch | Before-send crash, publish success before SQL bookkeeping, publish timeout with unknown broker outcome, duplicate old epoch, old terminal run message; identifier-only envelope rejects embedded profile/config/credential overrides; unsupported C0 or durable pinned-profile mismatch consumes no execution and cannot substitute latest/default code; capability missing/mismatched, poisoned payload |
| Atomic publication | Real shared physical PostgreSQL transaction; guarded commit/rollback/close rejected before producer lifecycle; caught violation poisons UoW/prevents commit; M1-only outer lifecycle; no external producer Session-event side effects; independent Connection/Session forbidden by architecture tests; hook/receipt/barrier/CAS failure rolls back all; heartbeat/expiry/budget/ambiguous commit retained |
| Candidate visibility/cleanup | Old worker fenced after successor claim; attempts cannot overwrite/reuse candidates; sealing prevents mutation; uncommitted candidates invisible to authorized readers; exact committed generation/digest/size; no latest/uncommitted-ES fallback; failed publication leaves private orphan; accepted/active/in-publication cleanup rejected; repeated/crashed cleanup safe |
| Cancellation | PENDING/QUEUED/RETRYING/live RUNNING/expired RUNNING/candidate-existing/terminal matrix; cancel-vs-publication race; immutable EXPIRED history; stale producer cannot cancel successor; producer-owned cleanup; no public endpoint |
| Report barrier | 0/1/2/3 correct diagrams no report; four wrong/duplicate templates no report; mixed scope/digest/schema invalid; concurrent completions one report slot; retryable versus final overview failure; monotonic sibling release; authorized overview successor reuses siblings and first report; duplicate recovery; already queued/completed report pinned; dropped hint/send failure recovered |
| Failure isolation | Diagram failure preserves siblings; overview normal/final-failure policy; failed report cannot alter diagrams; newer generation cannot replace pinned report input |
| Security/API | Real delegated headers, missing/bad credential, Viewer retry denied, cross-project IDs, idempotency conflict, no lease/raw source/private paths; local 404/409/422/503 mappings |
| Runtime | Exact per-consumer contract/profile/epoch heartbeat versus generic registration; old unknown-task rejection/discard; mixed-fleet dispatch gate/drain/rollback; lost worker/lease expiry, heartbeat pause during publication and process restart; no new queue/consumer targeting assumption |
| Capacity | Named hardware, cold/warm bounded sweeps and backfill; queue wait/execution separately; injected workload under analysis traffic; per-process current and peak RSS, no lifetime-pytest benchmark contamination |

Use fake clock/seeded jitter/barriers in unit tests, actual PostgreSQL clock/independent connections for integration, actual RabbitMQ and Celery child process for execution. Existing TestClient shim is fine for buffered API contract tests but not evidence of real concurrent request/worker behavior; use real HTTP/subprocess integration where that matters.

All integration fixtures require an explicitly supplied isolated database/broker environment. Do not silently fall back to user `.env` database or purge shared queues. Temporary **test** queue names are acceptable test isolation, not a production new-queue decision. Clean only fixture-created rows/queues. Required real-service skips block that batch's verification gate.

#### 23.2 Future commands, not executed now

Run from root after approved files exist; use a dedicated test database and `RABBITMQ_TEST_URL`, never production credentials. Fixtures must fail/skip explicitly if isolation prerequisites are absent.

```sh
./venv/bin/python -m pytest tests/p5/delivery/test_contracts.py tests/p5/delivery/test_model.py tests/p5/delivery/test_source.py tests/p5/delivery/test_registry.py tests/p5/delivery/test_execution_control.py
./venv/bin/python -m pytest tests/p5/delivery
./venv/bin/python -m pytest tests/p5/integration/test_delivery_postgres.py tests/p5/integration/test_delivery_rabbitmq.py
./venv/bin/python -m pytest tests/p5/integration/test_delivery_acceptance.py
./venv/bin/python -m pytest tests/p5/benchmarks/test_delivery_capacity.py
./venv/bin/python -m pytest tests/p1 tests/p2 tests/p3 tests/p4
./venv/bin/python -m pytest
./venv/bin/python -m black --check .
./venv/bin/python -m ruff check .
./venv/bin/python -m mypy backend
./venv/bin/python -m pip check
git diff --check
git status --short
```

Future migration verification: `./venv/bin/alembic heads` then `./venv/bin/alembic upgrade head` on an explicitly isolated existing-baseline test database, followed by schema/constraints checks and an isolated downgrade/upgrade test. No migration runs now. Exact fixture environment routing must be reviewed before executing commands that import the global app/settings.

Also retain `(cd express && npm test)`, `(cd frontend && npm test)` and `(cd frontend && npm run build)` for final composition regression where practical; M1 changes neither package. No invented npm lint/type/format script. Record exact actual results and unrun/blocked checks, not expected pass counts.

### 24. Risks, Unresolved Decisions and Approval Gates

The overall seven-module plan is owner-approved. The following are detailed M1 contract/operational approvals, not a request to redesign that architecture.

**M1 plan and C0 design are owner-approved for implementation as of 2026-11-17; C0 is not frozen.** Plan/start approval is now satisfied. B1 contract/fixture review, producer/consumer sign-off and explicit C0 freeze before B2 remain outstanding, as do real runtime/producer integration acceptance and the operational gates below. This status update records authorization, not implementation or acceptance evidence.

| Gate/classification | Decision/evidence required | Blocking scope |
|---|---|---|
| C0 — DESIGN APPROVED; CONTRACT NOT FROZEN | VersionScope, work/run/attempt states, exact prepared binding/fingerprints, identifier-only payload and pinned profiles, cooperative ExecutionControl, M1-owned guarded/poisoned publication transaction, sealed ArtifactReference/committed visibility and barrier receipts; M1/M2/M4/M5/M6 sign-off | B1 implementation authorized; explicit freeze after B1 review, never automatic; B2 cannot begin with a draft C0 |
| G1 — Design approved; joint C0 freeze review pending | OWNER/ADMIN-only eligible manual retry; internal classified cancellation; retryable overview holds siblings, final FAILED releases siblings, report still needs four READY | No policy choice is left ambiguous; C0 freeze and numerical round/admission defaults still required |
| G2 — Architecture/composition authorization | Exact additive edits to Celery app/router/migration metadata/settings, same queue, no frozen lifecycle changes | B2 wiring/migration; module approval is not assumed blanket infrastructure authorization |
| G3 — Technical investigation + owner numerical approval | Complete consumer-fleet inventory/admission/drain evidence, exact-profile capability, rollout/rollback proof; measured shared-queue fairness, heartbeat/lease/replay/reconcile/publication/byte/admission/retry budgets | Production dispatch/defaults; use clearly test-only values in fixtures |
| G4 — Implementation prerequisite + runtime verification | Connection-owned UoW with GuardedEnlistedSession/poison/event restrictions and rollback_only secondary defense; exact candidate/reference/readers/cleanup, producer locks and real live-fence/expiry/heartbeat/rollback proofs | Production output activation/report barrier; M1 B3 may use honest fixtures |
| G5 — Design reconciliation recorded | Strict P5 automatic barrier and broader permitted text-only renderer remain distinct; no M1 fallback or global renderer weakening | Joint review confirms contract separation, not a new master change or unresolved four-diagram policy |
| G6 — Repository-verified boundary; implementation/runtime evidence required | Public header and analysis DTO expose exact identity/success status; bounded sweep/reset/pending-eligibility correctness and historical-scale latency remain tests/measurements | Adapter acceptance/performance, not an unresolved authority choice; no private source-query shortcut |
| G7 — Owner operational decision | Audit/work/receipt retention, manual retry rate/round policy and failed-candidate responsibility | Destructive cleanup/manual retry policy; default no published-history deletion |
| Implementation detail within module | SQL index names, generated Alembic revision ID, safe local helper factoring, clock/RNG injection and fixed logger event names | Implement after contract approval without new architecture decision |

Highest risks: stale publication across module boundaries; source discovery cursor losing earlier-sort insertions; database/broker crash windows; queued work without a matching live consumer; and hidden shared-queue interference. Address these in B1/B2 contracts and real tests, not defer infrastructure correctness to B3.

No platform metadata approval is needed to complete M1 UUID/digest-based coordination. Names and the D11 interface stay with later transport/report work. No new Express implementation, third-party dependency or public lifecycle event is required by this module.

### 25. Definition of Done and Acceptance Criteria

M1 is complete only when:

1. C0 is independently reviewed/frozen with exact downstream interfaces, and all authorized existing-file edits remain additive/composition-only.
2. All eligible exact published versions are eventually discovered, including pre-deployment history, earlier-sort insertions and publication-before-analysis-success; bounded sweep latency measured.
3. Duplicate discovery/messages create one bundle/current logical run, one acquired execution per claim and no budget consumption for pure redispatch.
4. Leases use distributed DB time, expiry cannot be revived, and stale/old-epoch/manual-predecessor workers cannot publish or release dependencies.
5. Fresh M1-owned UoW and enlisted owner adapters atomically commit all PostgreSQL READY/pointer/receipt/completion/dependency changes; external candidates remain isolated/sealed, with no distributed atomicity claim. Final live-fence and cancellation/expiry races are tested; enlisted Session.commit cannot commit the physical outer transaction and illegal lifecycle use poisons the UoW.
6. Exactly four distinct required same-scope/digest/version READY references create one automatic report logical operation; all other combinations create none. Broker loss/restart recovers its dispatch.
7. Automatic and manual retry retain terminal history/pinned inputs, enforce approved budget/roles/idempotency and never overwrite completed outputs.
8. Missing downstream handlers remain honestly pending, not falsely complete; fixture consumer proofs do not masquerade as production diagram/PDF verification.
9. Status/retry APIs enforce delegated auth/project/role/ownership, preserve structured errors and reveal no credentials/tokens/source/private paths.
10. Real PostgreSQL and RabbitMQ/Celery concurrency/redelivery/restart tests, focused/frozen regressions and configured quality gates actually pass; blocked/skipped checks are disclosed.
11. Exact per-consumer/profile rollout/drain/rollback evidence and operational budgets/fairness are approved; no dispatch into an unproven mixed fleet, unbounded scan/retry/new queue or relaxed frozen memory limit. Internal cancellation semantics and overview recovery preserve terminal and report history.
12. Source, tests and final diff confirm no P3/P4 state/schema/private module modification, Express work or M2–M5 output implementation. Owner explicitly accepts M1 before freezing it.
13. ExecutionControl cannot mutate logical lifecycle/fences; M1 alone records stop/deadline/ownership outcomes. PreparedOutput mismatches in scope/bundle/work/run/attempt/fence/epoch/candidate/any pinned profile or applicable fingerprint/digest and mutable/non-exact ArtifactReference fail closed. Identifier-only payloads cannot override durable profiles; incompatible workers consume no execution and cannot select latest/default versions.
14. Guarded enlisted producer commit/rollback/close is rejected before Session lifecycle, violations irreversibly poison UoW even when caught, M1 alone controls outer cleanup/commit, and no producer Session callback emits external success. Real PostgreSQL rollback/concurrency proves shared physical transaction semantics; mocks/SQLite do not substitute.
15. Sealed candidates cannot cross-attempt overwrite/mutate; readers resolve committed exact generation without latest/ES fallback. Producer cleanup cannot remove accepted, active or still-publishable candidates, honors approved grace and remains safe after repetition/crash.

The runbook/evidence later recorded in this document must name runtime versions, commands, test resource isolation, measured times/RSS, failure injections, limitations and rollback switch. Current status remains planning-only; none of these acceptance checks is claimed executed by this task.

### 26. Three-Batch Implementation Roadmap

#### Batch 1 — Shared Contracts, Domain Models and Source Boundary

**Objective/deliverables:** deliver the C0 contract candidate, pure lifecycle model and read-only source adapter; prove downstream consumer compatibility using fixtures before persistence wiring and seek explicit owner/consumer freeze approval. B1 cannot self-authorize or self-freeze C0.

**Scope/exclusions:** contracts, run/attempt transitions, identity/fingerprints, fixed handler registry contract, exact published/successful eligibility. No migration, production worker wiring, output algorithms, Express or API implementation.

**Prerequisites:** approved overall phase/M1 direction; authoritative source/ADR review. C0 review must confirm read-only execution control, exact prepared/reference binding, guarded Session/event rules, sealing/readers/cleanup and incorporated lifecycle/report policies before contract freeze; numerical production defaults and implementation authorization remain distinct gates.

**Ordered tasks:**

1. Reconfirm branch/worktree and read-only frozen interfaces; capture verified source/analysis DTO fields and supported source contract version.
2. Implement contracts/model schemas and pure canonical fingerprints; distinguish logical slot, immutable work run, automatic attempts and manual successor run.
3. Define payload/profile matching, read-only ExecutionControl, exact PreparedOutput/reference binding, cancellation matrix, PublicationContext/guarded enlistment/public factory and outer-UoW/final-CAS/event rules with consumer fixtures; no producer-specific spec knowledge.
4. Implement PublishedVersionReader over public ports; pending eligibility, exact identity/digest, historical version and cursor-reset semantics.
5. Add pure tests and consumer examples for search receipt, each diagram reference and report pinned inputs; exercise optional/unavailable handlers without false success.
6. Obtain producer/consumer and owner review; freeze C0 document/evidence in this module plan through explicit approval, not auto-marked by tests.

**Files:** NEW delivery `__init__.py`, `contracts.py`, `model.py`, `source.py`, `registry.py`, `publication.py` contract surface; NEW `tests/p5/__init__.py`, delivery package initializer, `test_contracts.py`, `test_model.py`, `test_source.py`, `test_registry.py`, `test_execution_control.py`. REUSE public source/analysis read/auth types and existing test utilities. No MODIFY source files in B1 and no database changes.

**Tests/quality:** Section 23 first command; deterministic ordering/immutability/schema failures, state transitions, source before-success/earlier-sort/multiple versions, publication-hook consumer fixtures; changed-file Black/Ruff/strict Mypy and diff check. No fake DB concurrency claims.

**Acceptance:** C0 producers/consumers can implement against fixtures without private imports; no ambiguous scope/version/fence/publication semantics; source adapter cannot choose latest or modify P3/P4. Missing checks are explicit gates.

**Risks/rollback:** wrong C0 would propagate into every output module; prevent B2 before review. B1 rollback is removal/reversion of only new unused P5 files, not frozen source; no database state exists.

**Evidence to start B2:** exact file diff, focused tests/quality output, exported source boundary trace, C0 owner/producer approval and explicit G2/G3 infrastructure/default decisions. B1 completion alone is not B2 authorization.

#### Batch 2 — Durable Persistence, Dispatch and Recovery Foundation

**Objective/deliverables:** real P5 persistence, transactional work creation, durable dispatch, atomic execution claims/heartbeat/fencing, bounded sweep/recovery and actual worker/runtime readiness.

**Scope/exclusions:** infrastructure correctness belongs here, including success-publication transaction primitive tested with fixtures. No real search/diagram/report output implementation or report barrier/API product completion.

**Prerequisites:** C0 frozen, G2 exact composition/queue approval, approved test infrastructure and measured runtime budgets before production defaults. No new queue.

**Ordered tasks:**

1. Recheck migration head; implement seven P5 models/local constraints and repository transactional operations; generate additive migration and metadata registration.
2. Implement T1–T7 and T9, current-run uniqueness, durable pending eligibility, bounded leased sweep with reset, dispatch reservations/epochs and independent heartbeat Sessions.
3. Implement PublicationUnitOfWork with fresh Connection.begin, guarded enlisted Sessions and irreversible poison; reject producer commit/rollback/close before execution and forbid Session-event external side effects, retaining rollback_only as secondary defense. Add owner locks, heartbeat quiescence, final fenced CAS/clock/cancellation and sealed-candidate fixtures; inject exception/expiry at each READY/receipt/completion step.
4. Add identifier-only publisher/tasks on existing app/queue, no Celery retries; implement per-consumer exact-profile capability and dispatch-off rollout/drain/rollback gate, poison/unknown-task recovery and bounded broker behavior without assuming targeting/priority.
5. Add bounded reconciliation and failure classification; preserve existing Celery settings/routes/beat entries and frozen source contracts.
6. Run real isolated PostgreSQL migration/constraint/race tests and RabbitMQ/Celery redelivery/crash/restart tests; benchmark scan/dispatch/queue fairness with fixture producers.
7. Submit measured settings for explicit approval; wire only approved values and matching env names, preserving secrets and existing defaults.

**Files:** NEW `persistence.py`, `repository.py`, `service.py`, `queue.py`, `dependencies.py`; complete B1 `publication.py`, `backend/worker/delivery_tasks.py`, additive migration, integration package initializer, `test_dispatch.py`, `test_recovery.py`, `test_fencing.py`, `test_cancellation.py`, `test_publication.py`, `test_rollout.py`, `test_delivery_postgres.py`, `test_delivery_rabbitmq.py`, `tests/p5/benchmarks/test_delivery_capacity.py` and necessary benchmark package initializer. MODIFY only approved `backend/infra/migrations/env.py`, `backend/worker/celery_app.py`, `backend/platform/config.py` and env files. Extend B1 registry/contracts only compatibly through C0 review. REUSE existing engine/Base/Celery/source/read/auth; no frozen domain tables.

**Database/contract gates:** one additive migration; exact partial indexes/checks validated on PostgreSQL, no direct legacy platform FK. Any incompatible C0 discovery requires review/version change before downstream merge. No implementation silently changes maximum attempts or frozen analysis/graph settings.

**Tests/quality:** B2 unit suites plus real SQL and RabbitMQ commands, migration upgrade/downgrade on isolated DB, runtime process kill at send/claim/publish boundaries; full Python regression and Black/Ruff/Mypy/pip/diff checks before batch closure. Queue-only message test is insufficient without worker execution.

**Acceptance:** committed intent survives every tested DB/broker window; one claim per run; stale/cancelled worker cannot activate sealed fixture result; SQL publication rollback/lease-expiry/heartbeat races safe; exact-profile fleet rollout gate proven; restarted scan finds pending/new earlier-sort publications; missing handler/consumer visible; defaults measured/approved.

**Risks/rollback:** additive schema/composition and shared queue can affect startup/latency; disable P5 dispatch/beat entries first, keep safe P5 rows for diagnosis, preserve all existing routes/queues. Rollback migration only on isolated fixtures unless owner approves operational data handling.

**Evidence to start B3:** real migration/DB/worker results, exact crash matrix, accepted numerical/configuration evidence, C0-compatible publication proof, frozen dependency regression and reviewed additive diff. Unavailable real infrastructure blocks closure, not “passed with skips”.

#### Batch 3 — Dependency Coordination, Report Barrier and Operational Acceptance

**Objective/deliverables:** exact four-diagram automatic report barrier, duplicate-safe scheduling/recovery, status/retry APIs, operational visibility and M1 consumer acceptance. Fixture outputs stand in for downstream implementations honestly.

**Scope/exclusions:** fixed dependencies/overview policy/report slot and authorized retry/status. No DiagramSpec/layout/search/ReportSpec/PDF/storage engine, Express gateway or new analysis/graph event vocabulary.

**Prerequisites:** B2 accepted and real services available; C0/producer readiness/publication contracts reviewed and frozen, incorporated policy cases tested, and runtime defaults approved. M4/M5 production integration may remain future; fixtures must implement the same public protocol.

**Ordered tasks:**

1. Implement overview eligibility/final-failure sibling policy and safe per-slot dependency checks, without creating a generic DAG engine.
2. Implement T6 barrier under bundle lock; pin four refs/fingerprint/report slot atomically. Public readiness/exact-generation fixture readers reject mutable/latest/uncommitted/stale-attempt refs. Producer Session callbacks cannot dispatch that report or announce success.
3. Reconcile missed hints/dispatch failure; distinguish overview retryable/final failure and owner-approved monotonic sibling release; recover overview through an authorized successor, reuse siblings for the first eligible report, retain existing queued/completed report pins, deduplicate recovery hints.
4. Implement strict delivery summary/retry DTOs, local safe error translation and delegated scope/approved role enforcement; idempotent manual successor runs retain terminal history.
5. Register FastAPI router additively; expose capability/wait reasons and safe counters/logs. No Express route change in M1.
6. Execute fixture end-to-end source→four READY→one report work through real PostgreSQL/RabbitMQ; kill/restart at barrier/report-dispatch boundaries and validate cross-scope rejection.
7. Run full regression/quality/composition checks, review interfaces with M2/M4/M5/M6 consumers and record operational runbook/remaining integration limitations for owner acceptance.

**Files:** extend NEW `service.py`, `repository.py`, `dependencies.py` and worker entrypoints; NEW `api_contracts.py`, `backend/api/v1/delivery.py`, `test_barrier.py`, `test_api.py`, `test_delivery_acceptance.py`; extend real B2 integration tests. MODIFY only approved router include and approved additional P5 settings/env names. REUSE delegated auth/read interfaces; no further migration expected unless reviewed B2 model gap requires a separate additive migration, never rewriting applied B2 history.

**Contracts/freezes:** final C0 consumer review for receipt/readiness/publication/API schemas; original phase C1/C2/C4 remain producer-owned, not frozen on their behalf. API forwarding belongs to M6 after its own integration contract freeze.

**Tests/quality:** 0–4 and mixed-template/version barrier matrix, four concurrent completion transactions, lost/duplicate hints, stale publication, revoked/Viewer mutation, repeated/different-body retry keys, missing handler and broker backlog states; real acceptance suite, full Python regression/quality and practical unchanged Express/frontend test/build regression.

**Acceptance:** exactly one automatic report logical operation after four committed same-version READY refs, none otherwise; original diagnostics/data ownership untouched; status/retry secure and helpful; all crash recovery gates and consumer stubs pass; real output-generation gaps explicitly deferred rather than claimed complete.

**Risks/rollback:** violation of the specified OWNER/ADMIN policy or readiness semantics would leak/release work incorrectly; fail closed, keep report scheduling disabled until tests/approval. Disabling P5 dispatch must leave historical ready artifacts and frozen analysis/graph unaffected. No destructive output cleanup belongs here.

**Closure evidence:** reviewed final diff, exact command/environment/results, real infrastructure/race/recovery evidence, approved operational settings/role/policy decisions, downstream consumer compatibility, safe rollback/runbook and explicit owner acceptance. Only then propose M1 freeze; this planning task does not approve, implement or freeze it.


#### Refinement Record — 2026-11-17

- Consolidated the entire detailed M1 plan here; removed its separate file only after content transfer. P4 historical plans/logs were compacted into frozen decisions/contracts/evidence/limitations, not treated as unimplemented work.
- A: executive summary, contracts, persistence, transactions, heartbeat/DI, inventory, tests, acceptance and B1/B2 now define outer-UoW ownership, explicit producer transaction enlistment, exact visibility/rollback and external-candidate isolation; added proposed publication.py responsibility.
- B: domain, T9, failure/security/status, inventory/tests and B1/B2 now define internal cancellation for every work state and publication race; no public cancellation endpoint or producer artifact deletion.
- C: reconnaissance, dispatch, capabilities, gates/tests and B2 now define per-consumer/profile rollout/drain/rollback; existing services reused, unknown-task loss recovered durably, no targeting or fleet-control capability invented.
- D: barrier, status, policy/gates/tests and B3 now distinguish retryable/final overview failure, proposed monotonic sibling release, authorized recovery, first-report creation and immutable queued/completed report pins.
- New/refined C0 proposals: PublicationContext/ProducerPublicationFactory/Connection-owned enlisted-UoW lifetime, cancellation audit/cause semantics, exact fleet/profile/epoch capability, and reference selection/release policy. C0 remains unfrozen.
- Additional planned tests: publication ownership/premature commit/expiry/heartbeat/rollback, cancellation state/race matrix, old/mixed-fleet rollout recovery, overview final/retry/recovered/pinned report cases. No tests executed.
- Superseded by the later five-area decision-resolution record: retry roles, internal cancellation causes and final-overview release are now specified policies for joint review. Remaining approval/technical gates are detailed C0 acceptance, scoped composition, numerical retry/admission/retention budgets, actual fleet mapping/admission and producer transaction/sealing proofs with real-service evidence.
- Seven phase modules, M1 scope and exactly three accepted batch purposes are unchanged. At this refinement, the detailed plan was PROPOSED — AWAITING OWNER REVIEW; later owner implementation approval is recorded below. No implementation had begun.




#### Decision Resolution and Joint-Review Record — 2026-11-17

**Historical status at decision resolution: planning complete for review; M1 was PROPOSED — AWAITING OWNER REVIEW, without implementation authorization. Superseded by the owner approval recorded below.**

| Area | Resolution incorporated | Evidence category / what remains |
|---|---|---|
| 1. Retry/cancellation/overview | OWNER/ADMIN eligible FAILED successor retry, audited/deduplicated/limited; internal classified cancellation with no endpoint; live fencing and immutable terminal history; retryable overview holds siblings, final FAILED releases them, successor reuses valid siblings | Design decisions for joint review; numerical caps/admission and actual lifecycle tests remain implementation/runtime prerequisites |
| 2. Shared contracts | Exact source/work/attempt/profile identity; immutable C0; ownership/producer/consumer/rejection/version matrix; publication/dependency/barrier receipts and fixed task/template types | Stable interface proposal complete; M2/M4/M5/M6 producer-consumer sign-off and later C1/C2/C4 details not fabricated |
| 3. Publication | M1 Connection-owned outer transaction; rollback_only enlisted Sessions/public producer factories, owner-specific locks, guard/poison lifecycle misuse, final live-fence CAS and one commit; immutable sealed external candidates/private readers | SQLAlchemy 2.0.52 source and existing engine/flush boundaries verified; new UoW/candidate stores unimplemented, real PostgreSQL rollback/concurrency proofs required |
| 4. Worker fleet | Existing app/broker/queues/services only; dispatch off until every consumer maps to approved exact contract/profile/epoch; per-worker capability, controlled drain/rollout/rollback and durable replay after unknown-task loss | Config/unit files verified; complete live topology is NOT verified; enforceable fleet inventory/admission remains deployment prerequisite |
| 5. Report barrier | Four required committed matching diagram refs; fingerprint/unique automatic operation, immutable report inputs, search independence; no automatic text-only path, general permitted renderer ability unchanged | Master 17.80/17.90.38 and P5 baseline 9.2–9.4 reconciled as product gate versus general renderer; no reference document changed |

**Repository/operational checks in this task:** inspected shared engine/request transaction, frozen source/read DTOs, graph lease/activation/runtime patterns, existing local storage overwrite behavior, migration registration, delegated role validation, Celery/queue configuration and existing systemd worker/Beat units. A read-only systemctl --user show of the four existing services failed with “Operation not permitted” connecting to the user scope bus; this is an environment access limitation, not evidence workers are stopped. No RabbitMQ consumer inventory, restart, live DB publication test or fleet compatibility proof was claimed. The next operator must provide actual consumer-to-worker/profile mapping through permitted service/broker inspection before dispatch enablement.

**Cross-reference reconciliation:** master 18.76 assigns transactions to application use cases and keeps external consistency asynchronous; 18.44/18.43 preserve module-owned tables despite shared PostgreSQL. Coordinated delivery is one application use case through public producer ports, not M1 SQL over producer tables. General text-only support is not removed by a strict automatic product. Historical source scope and stale/readable artifact terminology remain exact-version aware. The baseline's generic mutation-role proposal is refined here to the task's explicit P5 retry restriction, not a change to frozen P3 create/cancel or P4 rebuild roles.

**Remaining joint review items:** accept detailed C0 and physical-transaction integration/sign-off, exact additive composition scope, consumer-fleet admission procedure and approved measured numerical policies/retention. Confirm downstream sealed-generation/readiness references and the distinction between historical valid refs and incompatible stale candidates. These are not unresolved choices about retry roles, public cancellation or whether three diagrams suffice.

**Runtime acceptance still required:** real PostgreSQL stale/two-worker/duplicate-publication/independent-commit/rollback/cancel races; sealed candidate visibility/orphan cleanup; RabbitMQ restart, worker kill after claim, rejected/discarded/unknown task, mixed fleet, graceful drain/rollback and redispatch; concurrent four-reference barrier and recovered overview without report repinning. Required skips do not satisfy gates.

**Updated sections:** M1 §§2/6/9–14/16–19/21–26, shared receipt/persistence/API/test/inventory rows, and current handoff. Exactly three batch purposes remain: B1 contracts/domain/source; B2 persistence/physical publication/dispatch/fencing/rollout/recovery; B3 dependency/barrier/status/retry/operational acceptance. M1 performs no downstream generation. Only this rolling context is edited.



#### Final C0 and Publication Joint-Review Amendments — 2026-11-17

- **A / M1 §10:** ExecutionControl exposes only checkpoint/should_stop and cannot cancel logical work or mutate fences/states. PreparedOutput binds exact scope/work/run/attempt/fence/epoch/candidate/profile/input/output digests; ArtifactReference requires sealed immutable underlying generation, not merely a stable URI.
- **B / M1 §12.1:** retained Connection-owned outer transaction and rollback_only enlistment, clarified Session lifecycle/events still need a dedicated GuardedEnlistedSession and monotonic UoW poison. Producer query/add/update/delete/flush permitted; commit/rollback/close/independent connection and transaction control prohibited. M1 alone commits/cleans up; producer Session callbacks never notify, activate or dispatch. Ordered 12-step protocol, final fenced linearization, heartbeat/deadline and ambiguous-commit handling retained.
- **C / M1 §12.2:** isolated sealed candidates, PostgreSQL-gated exact-generation readers including ES, no latest/alias fallback, and producer-owned serialized/grace/ownership/reference-safe idempotent cleanup. External corruption/loss remains a producer integrity/availability failure; no distributed durability claim.
- **Final consistency review:** §10/§10.1 bind PreparedOutput explicitly to bundle/run and every applicable profile/fingerprint; §13 keeps the broker envelope identifier-only and reloads/rechecks compatible pinned versions from durable state without consuming an attempt on mismatch. §23 tests, §24 gates, §25 acceptance and B1 wording align with the same requirements. The existing cooperative-stop, guarded/poisoned M1 outer transaction and committed-reference-only visibility rules remain mandatory; none is runtime-verified by this review.
- **Propagation:** ownership matrix, proposed publication.py/ExecutionControl test inventory, §23 acceptance matrix, §24 integration gate, §25 DoD and all three §26 batches updated. Added planned ExecutionControl/binding/immutability, guarded-lifecycle/poison/events, real physical-transaction, sealing/reader/cleanup and stale-worker tests; no test file created or test executed.
- **Preserved:** seven P5 modules, exactly three M1 batches, C0 freeze before B2, OWNER/ADMIN retry, classified internal-only cancellation, worker-fleet dispatch admission, strict all-four same-version automatic report barrier, broader permitted text-only renderer and unchanged P1–P4 ownership/ADRs.
- **Remaining approvals/evidence:** joint detailed-plan/C0 and producer-specific sign-off, exact scoped composition, measured budgets and owner-approved limits; actual guard/UoW implementation, real PostgreSQL/RabbitMQ races/recovery, sealed/exact-reader/cleanup producer proofs and compatible fleet inventory/admission. Prior user-bus permission limitation remains; no runtime gate is promoted by documentation.
- **Unresolved architecture conflict:** none newly identified in these amendments; exact storage enforcement and guarded-session integration are implementation/producer-review prerequisites, not proven capabilities. Any producer unable to meet them remains blocked pending an equivalent reviewed protocol.
- **Status at amendment review:** PROPOSED — AWAITING OWNER REVIEW; no batch was authorized by that documentation refinement. **Subsequent owner decision, 2026-11-17:** M1 plan/C0 design APPROVED FOR IMPLEMENTATION, beginning with B1 under the existing three-batch gates. C0 contract freeze remains pending B1 evidence/sign-off and explicit approval. Implementation has not started; M1 is not complete or frozen. This task changes status only.

## 7. Current Handoff and Refinement Ledger

- **P1–P4:** FROZEN / COMPLETE by owner acceptance; compact frozen handoffs retained above, no implementation reopened.
- **P5:** overall seven-module architecture/module structure approved; implementation not started. This context is the shared destination for subsequent module plans, implementations and reviews; the phase document remains a retained baseline.
- **M1:** detailed plan **APPROVED FOR IMPLEMENTATION — OWNER APPROVED 2026-11-17**; exactly three batches and all reviewed decisions retained. Implementation not started; M1 is not complete or frozen.
- **Policies incorporated for joint review:** OWNER/ADMIN-only eligible retry, classified internal cancellation, terminal-overview sibling release, strict same-version four-diagram automatic report with general text-only capability preserved. **Remaining approvals/prerequisites:** C0 and producer contracts, precise additive composition, measured retry/admission/timeout/retention values; producer transaction/candidate-sealing proof and fleet mapping/admission/real-service evidence. No policy is presented as implemented.
- **Final C0 amendments:** read-only execution control, exact prepared/reference binding, guarded Session/poison/event restrictions and sealed exact-generation/read/cleanup rules incorporated; they remain unimplemented/unverified.
- **C0 approval:** design approved with the M1 plan; contract NOT FROZEN. Identifier-only worker payloads retain durable pinned-profile compatibility. Plan/start approval is satisfied; post-B1 contract freeze, producer/consumer sign-off, scoped composition, measured defaults and later runtime acceptance remain required.
- **Next action:** implement Batch 1 under the approved plan when work resumes; no implementation is performed by this status-only task. B2/B3 remain subject to their documented prerequisites. No source/test/config/master/ADR change is part of this task.
- **Documentation relocation:** removed docs/PHASE_5_M1_IMPLEMENTATION_PLAN.md only after preserving/refining its complete content here. It was untracked; its content is recoverable in this context, not through an assumed Git commit.
