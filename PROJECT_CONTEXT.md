# GLOBAL IMPLEMENTATION BOUNDARY — NO NEW EXPRESS IMPLEMENTATION

- No remaining StackSense work may add or change Express implementation without
  explicit project-owner approval. Existing Express/MongoDB authentication,
  projects, RBAC, repositories and platform integration are completed work.
- Do not rewrite, refactor, replace, migrate, duplicate or remove completed
  Express behavior, and do not add Express routes, controllers, services,
  models, middleware, authentication flows or gateways for P4 M1–M4.
- P4 M1–M4 backend implementation is Python/FastAPI only. React continues to use
  the existing Express-facing platform/security boundary and must never call
  Python directly or bypass, break or remove existing Express functionality.
- Preserve all approved Express/Python integration contracts and all frozen
  P1–P3 work. If a future requirement appears to require an Express change,
  stop and obtain explicit owner approval through change control first.

# PROJECT_CONTEXT.md — StackSense Engineering Context

Last reconciled: 2026-11-13
Current branch: `feature_shreya`

## 1. Project Overview

StackSense is a software repository intelligence and architecture analysis
platform. Express/MongoDB owns users, JWT authentication, projects, project
RBAC, repository registration, immutable revisions and artifact metadata.
Python/FastAPI/PostgreSQL owns analysis lifecycle, deterministic source
inspection and IR, canonical Architecture Models and published results. The
services communicate only through authenticated internal APIs and never read
each other's databases.

P1–P3 are implemented and frozen. P4, **Architecture Graph & Exploration**, is
the current implementation phase. Its Architecture Baseline v1 is approved; the P4
high-level discussion of all six modules is complete. M1 and its corrected graph
schema are verified, owner-accepted and frozen. M2 (Batches 1, 2, and 3) is fully
implemented and verified against real Neo4j Community and PostgreSQL. M3 (Batches 1,
2, and 3: P4-Q1 contracts, closed vocabularies, limits, DTOs, HMAC-SHA256 Base64URL cursor
codec, SqlAlchemyGraphGenerationReader, Neo4jGraphQueryRepository with 7 Cypher operations,
GraphQueryService with monotonic deadline and generation-drift double-read, P4-owned DI
providers, query health probe, structured observer telemetry, and real PostgreSQL 16 +
Neo4j Community 5.26.33 pipeline integration) is fully implemented and verified.
M4–M6 remain.

### 1.1 Authority and documentation policy

- `master.txt` is the authoritative frozen architecture specification,
  especially Sections 13, 25.14 and Evaluation 2 for P4.
- `docs/architecture/adr/0001-express-python-integration.md` preserves the
  Express/MongoDB and Python/PostgreSQL boundary. Its accepted integration
  contract remains valid, but any historical allowance for later Express work
  is superseded for current/future implementation by the owner boundary at the
  top of this file; the ADR is not edited or treated as implementation approval.
- Frozen F1, F2, F3 and Architecture Model v1 contracts remain authoritative.
- Source and tests establish actual implementation state; documentation alone
  is not proof.
- This file is the sole rolling planning/status handoff. Temporary agent reports
  are consolidated here and removed unless a compelling permanent-document
  reason exists. Do not duplicate `master.txt`.

## 2. Global Frozen Constraints

1. P1–P3 contracts and implementation remain frozen without explicit change
   control.
2. PostgreSQL Architecture Model v1 is canonical, immutable after publication
   and the only legal P4 projection source.
3. Neo4j is a derived, disposable and rebuildable projection, never authority.
4. P4 consumes a complete validated `PUBLISHED` project-scoped Architecture
   Version; it never consumes draft/partial data.
5. P4 never reopens the P3 analysis pipeline, revives the legacy projection
   stage, reruns M2/M3/M4, or changes F1/F2/F3.
6. Express remains the completed browser-facing JWT/RBAC authority. React calls
   Express only; it never calls FastAPI/Neo4j or receives internal credentials.
   P4 M1–M4 add Python/FastAPI backend functionality only and may not modify
   Express without separate explicit owner change control.
7. Neither backend reads the other's database. Neo4j is behind Python ports.
8. Projection resources, nodes, edges and queries are isolated by project,
   Architecture Version and generation. Neo4j internal IDs are never product
   identity.
9. Graph APIs are controlled, parameterized and bounded. Raw Cypher is forbidden.
10. The P3 Architecture Model page remains the canonical relational fallback.
11. Graph failure cannot invalidate analysis completion, publication or the
    canonical model.
12. P4 adds no P5 search/knowledge/diagram-intelligence behavior, P6 AI,
    canonical kinds, or editable architecture truth.

## 3. Phase Index and Frozen Baseline

| Phase | Status | Retained outcome / dependency |
|---|---|---|
| P1 — Engineering Foundation | **FROZEN / COMPLETE** | Backend/frontend, persistence, queue, security, migration, testing and operational foundations. |
| P2 — Project & Repository Platform | **FROZEN / COMPLETE** | JWT identity, projects/RBAC, repositories, immutable revisions, artifacts and ingestion. |
| P3 — Analysis Engine & Architecture Model | **FROZEN / COMPLETE** | M1/F1 lifecycle; M2/F2 inspection; M3/F3 IR; Architecture Model v1; gateway/UI; integration/performance closeout. |
| P4 — Architecture Graph & Exploration | **M1–M3 FROZEN; M4 PLAN APPROVED / IMPLEMENTATION AUTHORIZED** | M1 and M2 are frozen. The owner confirmed M3 complete and froze P4-Q1/P4-H1 after verified review remediation. The corrected three-batch M4 Python/FastAPI integration plan in Section 7E passed Master Agent review and is approved as one sequential implementation unit; implementation has not started. M5–M6 remain upcoming. |
| P5 — Knowledge, Search & Diagram Intelligence | **UPCOMING** | Depends on verified P4 graph; owns retrieval, search, knowledge and diagram intelligence. |
| P6 — AI Architecture Intelligence | **UPCOMING** | Owns grounded AI explanation after deterministic retrieval. |
| P7 — Final Product & Hardening | **UPCOMING** | Productization, deployment hardening and final acceptance. |

### 3.1 Frozen P3 outcomes reused by P4

| Module | Frozen outcome |
|---|---|
| M1/F1 v1.0.0 | PostgreSQL analysis/job/stage/event/diagnostic lifecycle, Celery, REST/SSE, cancellation and recovery. |
| M2/F2 v1.0.0 | Deterministic inventory/detection, isolated parsers, framework enrichment and immutable non-persisted F2. |
| M3/F3 v1.0.0 | Deterministic IR, document-local semantics, diagnostics and validation. |
| M4 / Architecture Model v1.0.0 | Canonical identity/model, validation/caps, atomic publication and published-only bounded queries. |
| M5 | Express analysis gateway and React analysis/model exploration with bounded canonical-model overview. |
| M6 | Cross-service/E2E, security, regression, build and performance closeout; owner accepted live behavior on 2026-11-10. |

Latest retained verification: Python regression excluding the known pathological
M3 stress benchmark was 746 passed with 3 platform skips; focused M4 tests were
42 passed; 10,000-entity benchmark passed in 27.38s. Frontend legacy and focused
Vitest suites, production build, Express regression/audit, Ruff, changed-file
Black, strict Mypy and diff checks passed. A live optimized run processed 469
extraction items in about 20 seconds and completed publication.

## 4. Approved P4 Architecture Baseline v1

**Status: APPROVED by owner on 2026-11-11.** These decisions are immutable for
implementation unless change control is explicitly approved.

1. Python/FastAPI/Celery owns projection and graph queries; the completed
   Express platform remains the browser gateway/security boundary.
2. Projection has an independent PostgreSQL lifecycle; P3 stages stay frozen.
3. Durable scheduling/recovery is reconciliation-driven.
4. Baseline is Neo4j Community 5.26.33 LTS and official Python driver 6.4.x,
   with exact patch/Python 3.14 verification before pinning.
5. One shared Neo4j database enforces project/version/generation isolation.
6. Nodes are `ArchitectureEntity`; edges are `ARCH_RELATIONSHIP`; the sole
   operational generation-manifest label is `ProjectionManifest`; canonical
   kinds remain properties.
7. Node/edge storage keys are deterministic, generation-scoped SHA-256 values;
   canonical IDs remain separate properties.
8. Candidate generations require independent Neo4j read-back verification
   before PostgreSQL pointer-gated visibility.
9. PostgreSQL attempts/leases govern concurrency, three-attempt retry and
   rebuild-as-new-generation.
10. Every published version is projected and initially retained; older verified
    versions become exactly queryable `STALE` resources.
11. Queries use controlled semantics and hard caps: depth 5, 500 nodes, 1,000
    edges, 25 paths and 5 seconds.
12. OWNER/ADMIN may rebuild; an audited system actor schedules automatically;
    all project roles may read.
13. Unresolved relationships/conflicts are not synthetic graph nodes/edges.
14. A separate React Flow + ELK Explorer has a 300-node/600-edge canvas cap and
    accessible structured alternative.
15. Layered health/degradation, observability, reconciliation and rebuild-based
    recovery are mandatory.
16. Public states are exactly `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`,
    `STALE`; `QUEUED`/`RETRYING` are internal attempt states.
17. Rebuild serves the last verified active generation until a candidate passes
    verification; failure cannot invalidate the active generation.

Storage keys are:

```text
node_key = SHA-256(project_id || NUL || architecture_version_id || NUL ||
                  generation_id || NUL || logical_id)
edge_key = SHA-256(project_id || NUL || architecture_version_id || NUL ||
                  generation_id || NUL || relationship_logical_id)
```

Canonical logical/P3 IDs and all scope IDs remain separate properties, so active
G1 and candidate G2 coexist without matching or overwriting one another.

## 5. P4 Objective, Scope and Existing Integration Points

P4 delivers:

```text
Repository -> Analysis -> Published Architecture Model
           -> Graph Projection -> Graph Query -> Existing Express Gateway
           -> React Architecture Explorer
```

It reuses `ArchitecturePublicationRepository.load_published_document`, atomic
published versions, Express delegation/RBAC, FastAPI delegated context, Celery
recovery conventions, the central frontend `apiClient.js`, current hash/path
routing and the dark UI system. No Neo4j driver/service, graph lifecycle,
projector, query API, graph-specific browser route or explorer currently exists.
P4 M1–M4 may implement only the Python side. The absence of a compatible
existing Express graph transport is an explicit downstream integration blocker,
not permission to add one or to call Python directly from React.

P4 does not modify the frozen Architecture Model repository port or persistence
implementation. Exact document loading reuses the existing read-only
`ArchitecturePublicationRepository.load_published_document(version_id,
project_id)`. Published-version enumeration is owned by a new P4
`PublishedArchitectureSource` adapter: its SQLAlchemy implementation performs a
read-only, deterministic query over the existing frozen
`ArchitectureVersionModel` for `PUBLISHED` headers, then delegates exact document
rehydration to the existing repository. It cannot write Architecture Model rows
or alter publication behavior.

No P3 contract change is approved. If implementation evidence proves the
P4-owned adapter insufficient, the only contemplated fallback is an additive
read method on `ArchitecturePublicationRepository`,
`list_published_version_headers(*, after_published_at, after_id, limit)`, with a
matching `SqlAlchemyArchitectureRepository` implementation. That exact change
would require explicit P3 change-control approval before either frozen file is
edited; it is not part of the current roadmap.

## 6. Cross-Module Contracts and Freeze Points

| Contract | Owner | Consumers | Required semantics / freeze point |
|---|---|---|---|
| P4-L1 Projection Lifecycle | M1 | M2, M3, M4, M6 | Resource/attempt records, public/internal mapping, leases, active/candidate generations, system/user audit and automatic-scheduling eligibility. Freeze after M1 B2. |
| P4-S1 Published Source | M1 P4-owned adapter over frozen Architecture Model reads | M2 | P4 adapter enumerates read-only `PUBLISHED` headers; exact document loading delegates to frozen `load_published_document`; no P3 port/persistence change. Freeze after M1 B2. |
| P4-W1 Worker Payload | M1 | M2, M6 | Identifier-only `{projection_id, attempt_id, project_id, architecture_version_id, generation_id, contract_version, correlation_id}`. Freeze before M2 worker. |
| P4-P1 Projection/Verification | M2 | M1 activation, M3 status, M6 | Immutable verification result containing candidate identity, expected/actual counts/digests/key sets and safe failure; M2 never activates. Freeze after M2 B2. |
| P4-Q1 Graph Query | M3 | M4, M5, M6 | Status, node, bounded subgraph, approved non-containment dependency-kind traversal, separate containment and path DTOs, signed cursors, errors and degradation. Freeze after M3 B1. |
| P4-D1 Python Graph API Integration | M4 | M3, M5, M6 | Python/FastAPI route composition, delegated-context enforcement, DTO/error/OpenAPI completion and reuse of the existing trusted service/actor/role/project/correlation contract. It adds no Express implementation. Freeze after M4 B1. |
| P4-U1 Explorer State | M5 | M6 | Explicit Architecture Version ID from the route, validated analysis/project/repository context, loaded IDs, expansion cursors, selected node, layout state and explicit partial/stale/degraded state. The version ID is immutable for the page lifetime. Freeze after M5 B1. |
| P4-H1 Graph Health | M1/M3 | M4, M5, M6 | Core liveness independent; graph `ready/degraded/unavailable`; no silent fallback. Freeze after M3 B3. |

### 6.1 Lifecycle contract

- One projection resource per `(architecture_version_id, projection_type)` with
  source digest/schema, project/repository IDs, public state, version,
  `active_generation_id`, timestamps and safe last failure.
- Attempts are immutable/auditable records with attempt/generation IDs, internal
  state, actor type/ID, correlation ID, lease owner/heartbeat, expected/actual
  verification data, safe error and timestamps. A partial unique constraint
  allows at most one `QUEUED`/`RUNNING`/`RETRYING` attempt per resource.
- Initial `QUEUED` maps to `PENDING`; acquired/retrying/requeued-after-start maps
  to `RUNNING`; verified activation maps to `COMPLETED`; terminal failure with no
  active generation maps to `FAILED`; superseded verified resource maps to
  `STALE`. Rebuild attempts never change an already readable public state.
- M1 alone owns activation. Given an immutable M2 verification result, M1 locks
  and validates the current resource/attempt, confirms the attempt is still
  active and lease-valid, confirms its `candidate_generation_id` and expected
  source/schema/projector versions match, then performs the PostgreSQL
  active-generation compare-and-swap transactionally. M2 cannot update the
  resource pointer or public state.
- The M1 activation port accepts the attempt/resource/generation identities and
  the immutable expected/actual verification summary. Its single transaction
  locks the resource and attempt, rechecks current-attempt and lease ownership,
  persists verification outcome/audit data, and switches
  `active_generation_id` only for a successful current result.
- A stale/lease-lost/superseded attempt result is rejected without changing the
  resource; its candidate becomes cleanup-eligible. Failed verification is
  recorded on the attempt and moves the resource to `FAILED` only when no
  verified active generation exists. A concurrent rebuild cannot be displaced
  by a late result from an older attempt. Cleanup never selects
  `active_generation_id`.
- If a rebuild fails for a resource already in public `STALE` state with a
  verified `active_generation_id`, the resource remains `STALE`, that active
  historical generation remains readable through exact-version queries, and
  only the failed attempt/candidate records the failure. The failure must never
  change the resource to `FAILED`, clear or invalidate its active generation,
  or make the historical version unavailable.

### 6.2 Graph/query DTO contract

- `GraphProjectionStatus`: version/project/repository, public state, active
  generation, in-progress attempt summary, source/projector/schema versions,
  counts, timestamps, stale reason and graph capability status.
- `GraphNode`: P3 entity UUID/logical ID, kind/name/namespace/status, safe
  metadata and evidence references; never Neo4j element ID.
- `GraphEdge`: P3 relationship UUID/logical ID, kind, canonical source/target
  entity IDs, status, safe metadata/evidence; direction is unchanged.
- `GraphSubgraph`: exact version/generation, deterministic nodes/edges,
  requested depth/direction/relationship kinds, loaded/available counts,
  `truncated` and signed `next_cursor`. Truncation is always explicit. Dependency
  traversal preserves the selected canonical relationship kinds; it never
  rewrites them to `depends_on`.
- `GraphDependencyQuery`: entity UUID, incoming/outgoing semantic mode,
  optional `relationship_kinds` constrained to the approved non-containment
  allowlist, page/limit and cursor. Its `GraphSubgraph` response retains each
  edge's actual kind and canonical direction. `contains` is invalid for this DTO
  and uses the containment request/response contract instead.
- `GraphPathResult`: at most 25 deterministically ordered paths with nodes and
  directed edges; no runtime/impact claims.
- Cursor: HMAC-SHA256/Base64URL payload bound to project, exact version, active
  generation, query fingerprint, last stable key, expiry and contract version.
  A dedicated production secret is required; cursors fail closed after pointer
  changes or tampering.

### 6.3 Proposed FastAPI capability surface

All routes require existing delegated authentication and exact project match:

| Method/path under `/api/v1/architecture-versions/{version_id}` | Purpose |
|---|---|
| `GET /graph/status?project_id=` | Public lifecycle, active generation and degradation. |
| `POST /graph/rebuild?project_id=` | OWNER/ADMIN only; idempotently creates/coalesces attempt; `202`. |
| `GET /graph?project_id=&node_limit=50&edge_limit=100&cursor=` | Deterministic initial/continued bounded window. |
| `GET /graph/nodes/{entity_id}?project_id=` | Node detail in active exact-version generation. |
| `GET /graph/neighborhood/{entity_id}` | Bounded direction/kind/depth expansion. |
| `GET /graph/dependencies/{entity_id}` | Outgoing traversal over the approved non-containment relationship-kind allowlist, optionally narrowed by `relationship_kinds`. |
| `GET /graph/dependents/{entity_id}` | Incoming traversal over the same approved non-containment relationship-kind allowlist. |
| `GET /graph/containment/{entity_id}` | Explicit parent/children canonical `contains` navigation. |
| `GET /graph/paths` | Bounded directed path search between two entity UUIDs. |

Defaults are depth 1, 100 nodes, 200 edges, 5 paths, 2 seconds and page 50;
hard limits are the approved 5/500/1,000/25/5s and page 100. Request validation
rejects larger values. Actual limit termination returns `truncated=true` and a
cursor where continuation is meaningful.

The approved dependency traversal allowlist preserves every canonical
non-containment relationship kind without collapsing semantics:
`depends_on`, `imports`, `calls`, `exposes`, `consumes`, `produces`,
`connects_to`, `persists_to`, `uses`, `extends`, `implements`, and `routes_to`.
Responses retain each edge's actual kind and direction. `contains` is excluded
from dependency/dependent traversal and is available only through the explicit
containment capability unless the caller separately requests a generic
neighborhood containing it.

## 7. P4 High-Level Module Discussion

**Status: COMPLETE / ACCEPTED AS THE P4 MODULE FOUNDATION.** This section
validates the conceptual six-module structure. M1, including its corrected graph
schema, is frozen and complete. The repository-grounded detailed M2 plan is
recorded separately in Section 7C; its three batches are implemented, reviewed
and accepted complete. Detailed M3 planning is recorded in Section 7D and is
owner-approved; implementation has not started. The preserved roadmap in
Section 7B remains the high-level reference for modules that have not yet
received detailed planning.

### M1 — Graph Infrastructure and Projection Lifecycle

**Purpose:** M1 exists to give the derived graph an independent, durable control
plane. Projection work must continue, recover and report honest state without
reopening or coupling itself to the frozen P3 analysis lifecycle.

**Core Responsibilities:** It owns Neo4j connectivity and infrastructure
health, PostgreSQL projection resources and attempts, published Architecture
Version discovery, reconciliation, Celery/RabbitMQ scheduling and recovery,
leases and heartbeats, public-state mapping, candidate/active generation
coordination and verified-generation activation.

**Ownership Boundaries:** M1 owns lifecycle persistence and the transactional
active-generation pointer switch. It does not transform Architecture Models,
write candidate graph content, independently verify Neo4j completeness, define
graph-query semantics, or serve browser-facing APIs.

**Inputs and Outputs:** It consumes published-version headers, automatic or
manual projection intent, worker progress and immutable M2 verification
results. It produces durable lifecycle/attempt records, identifier-only worker
payloads, public projection status and an active-generation decision. Failed or
stale verification results never become activation instructions.

**Interactions and Dependencies:** It reads the frozen P3 publication boundary
through the approved P4-owned source adapter, dispatches M2, supplies active
generation/status information to M3 and exposes health/degradation consumed by
M3–M6. M2 cannot bypass M1 to activate a candidate.

**Architectural Considerations:** PostgreSQL remains lifecycle authority rather
than RabbitMQ or Neo4j. Reconciliation must tolerate duplicate schedulers,
dispatch loss, expired leases and late results. A rebuild keeps the previous
verified generation readable; this includes a historical `STALE` resource,
which remains `STALE` after rebuild failure. Core service health must remain
independent from graph availability.

**Expected Outcome:** A recoverable, auditable projection lifecycle that can
discover every published version, coordinate one valid attempt, activate only a
currently valid verified candidate and report honest public state.

### M2 — Deterministic Graph Projection and Verification

**Purpose:** M2 turns one exact canonical Architecture Version into a faithful
Neo4j candidate and proves that the candidate actually matches the source before
it can become readable.

**Core Responsibilities:** It owns deterministic node/edge representation,
generation-scoped storage identity, safe property projection, bounded writes,
candidate construction, independent Neo4j read-back, completeness/digest/
endpoint verification, immutable verification-result production and candidate
cleanup eligibility.

**Ownership Boundaries:** M2 owns construction and verification, not projection
lifecycle persistence, public-state transitions or activation. It must not
change canonical architecture semantics, invent entities/relationships, expose
partially written generations or silently omit unsupported data.

**Inputs and Outputs:** It consumes an identifier-only M1 attempt payload and
the exact frozen published Architecture Model. It produces an isolated candidate
generation plus a success/failure verification result containing sufficient
evidence for M1 to make the activation decision.

**Interactions and Dependencies:** M1 schedules and supervises it; the frozen P3
read boundary supplies canonical data; Neo4j stores the candidate; M1 alone
accepts or rejects its result. M3 never queries the candidate directly and sees
it only after M1 activation.

**Architectural Considerations:** Deterministic ordering, identities and digests
must make retries idempotent. Verification must independently detect omissions,
duplicates, wrong endpoints, count/digest mismatch and scope/version mismatch.
Metadata must be allowlisted and bounded so source, secrets and unsafe values do
not leak. G1 and G2 must coexist without overwriting each other.

**Expected Outcome:** A complete, deterministic and independently verified graph
candidate whose correctness is demonstrated rather than inferred from a
successful write operation.

### M3 — Graph Query and Exploration API

**Purpose:** M3 converts verified graph data into a controlled application
capability instead of exposing Neo4j or arbitrary graph execution directly.

**Core Responsibilities:** It owns projection status, bounded graph windows,
node detail, neighborhoods, dependency/dependent traversal, separate containment
navigation, bounded paths, deterministic pagination, signed cursors, FastAPI
integration, graph errors and query-layer health/degradation.

**Ownership Boundaries:** M3 defines graph-query meaning and DTOs over M1-selected
verified generations. It does not project data, activate generations, perform
browser JWT/RBAC, expose raw Cypher, implement search/AI semantics or let callers
turn graph traversal into canonical architecture truth.

**Inputs and Outputs:** It consumes exact project/version/generation scope,
delegated authorized context and controlled query parameters. It produces
bounded deterministic graph DTOs, explicit truncation/cursors, lifecycle status
and graph-specific safe errors.

**Interactions and Dependencies:** M1 supplies authoritative lifecycle and
active-generation selection; Neo4j supplies verified graph records; M4 completes
the Python/FastAPI integration; M5 consumes the frozen P4-Q1/P4-D1 DTOs only
through an approved existing browser transport. M6 validates isolation, limits,
semantics and degradation.

**Architectural Considerations:** Every query must include project, exact
Architecture Version and active generation. Dependency traversal preserves the
approved non-containment relationship kinds and their direction; `contains`
remains separate. Exact-version `COMPLETED` and `STALE` resources with an active
generation are readable. Limits, timeouts, cursor binding and parameterized
queries must fail closed.

**Expected Outcome:** A stable, version-aware and safe graph capability surface
that supports architecture exploration without leaking infrastructure or
allowing unbounded traversal.

### M4 — Python/FastAPI Graph API Completion and Backend Integration

**Purpose:** M4 completes the Python/FastAPI graph capability surface around the
M1 lifecycle and M3 query contracts while preserving the already implemented
Express browser security boundary.

**Core Responsibilities:** It owns Python route composition, delegated-context
validation, exact project/version scoping, OWNER/ADMIN rebuild enforcement in
FastAPI, DTO/error/OpenAPI completion, health integration and backend contract
tests across M1–M3.

**Ownership Boundaries:** M4 is Python-only. It must not add or modify Express
routes, controllers, services, models, middleware or gateway behavior; access
MongoDB; redefine M3 query semantics; activate projections; or create a second
browser authentication boundary. Existing Express behavior remains completed
and authoritative for browser JWT/RBAC.

**Inputs and Outputs:** It consumes P4-L1 and stable P4-Q1 contracts plus the
existing trusted delegated service/actor/role/project/correlation headers. It
produces a composed, documented and safely error-mapped FastAPI graph surface
for authorized internal delegation; it does not expose Python directly to React.

**Interactions and Dependencies:** M4 depends on stable M1/M3 contracts, reuses
the accepted ADR-0001 delegated-auth contract and freezes P4-D1 for downstream
consumers. Any browser-facing graph route absent from the completed Express
surface is outside P4 M1–M4 and requires a separate owner decision; it must not
be silently assigned to M4.

**Architectural Considerations:** FastAPI must independently validate delegated
scope and rebuild authority before graph retrieval. Query limits, correlation
and safe errors remain consistent with M3. Infrastructure readiness and API
composition cannot imply that an unapproved Express route exists.

**Expected Outcome:** A testable Python/FastAPI backend integration that exposes
the approved graph functionality through the existing delegated-service model
without changing completed Express implementation or weakening either security
boundary.

### M5 — React Architecture Explorer

**Purpose:** M5 turns the controlled graph API into an understandable,
interactive architecture exploration experience while retaining the canonical
P3 Architecture Model page as the relational fallback.

**Core Responsibilities:** It owns explicit-version routing, lazy graph loading
and expansion, React Flow visualization, deterministic ELK worker layout, node
selection/inspection, dependency and containment navigation, accessible
structured alternatives and honest loading/stale/partial/degraded/rebuild UI.

**Ownership Boundaries:** The Explorer is read-only and calls Express only. It
must not infer new architecture, edit graph truth, perform authorization, call
FastAPI/Neo4j directly, silently substitute a latest version, redefine M3 DTOs
or introduce P5 diagram/search and P6 AI behavior.

**Inputs and Outputs:** It consumes an explicit Architecture Version ID plus the
frozen graph DTOs and lifecycle state through the approved browser boundary. It produces bounded visual and
structured views, local selection/layout/expansion state and clear capability
feedback; it does not produce authoritative architecture data.

**Interactions and Dependencies:** Its package compatibility spike,
route/component shell and independent layout-worker work may proceed after the
relevant M3 DTOs stabilize. Live service/hook/page integration requires frozen
P4-D1 plus a verified compatible route through the already completed Express
boundary. If that route is absent, integration pauses for an owner decision; M5
must not add Express work or call Python directly. Navigation begins from an
exact loaded P3 Architecture Version and remains bound to that ID throughout
refresh and exploration.

**Architectural Considerations:** Large graphs require explicit lazy loading,
deduplication and render caps. Layout must stay off the main thread and selection
must not trigger jitter. Keyboard/focus behavior and a structured alternative
are product requirements, not optional polish. Partial or unavailable graph
capability must never be presented as complete architecture.

**Expected Outcome:** An accessible, stable and bounded exact-version Explorer
that helps users navigate graph structure without weakening backend authority or
misrepresenting projection completeness.

### M6 — Integration, Testing, Performance and Evaluation 2

**Purpose:** M6 provides evidence that the complete P4 vertical slice works
correctly under real infrastructure, concurrency, failure and user interaction,
not merely in isolated unit tests.

**Core Responsibilities:** It owns real PostgreSQL/Neo4j/RabbitMQ/Celery
integration, projection and verification correctness, lifecycle/recovery and
historical-version tests, query isolation/limits, FastAPI delegated
authorization plus regression of the completed Express boundary,
frontend/accessibility validation where an approved browser transport exists,
performance/capacity evidence, outage/remove-rebuild evaluation and P1–P3
regression protection.

**Ownership Boundaries:** M6 validates and closes the approved phase. It must not
become a seventh feature module, relax limits to make tests pass, introduce
search/AI/product scope or retroactively redefine contracts without change
control.

**Inputs and Outputs:** It consumes the frozen P4 contracts, completed module
implementations and representative/corrupt/multi-project/historical fixtures. It
produces reproducible acceptance evidence, measured performance results,
documented operational outcomes and any scoped defect corrections required for
freeze.

**Interactions and Dependencies:** It spans M1–M5 and the retained P1–P3
regression surface. Test harnesses and fixtures may grow alongside modules, but
final evaluation waits for all cross-module contracts and implementation.

**Architectural Considerations:** Happy-path completion is insufficient. M6
must prove late-result rejection, failed rebuild preservation for `COMPLETED`
and `STALE`, corruption detection, graph loss/rebuild, cross-scope denial,
bounded traversal, graph API degradation, accessibility and canonical P3
availability during graph failure. Performance evidence must identify hardware
and preserve hard safety limits.

**Expected Outcome:** Defensible Evaluation 2 evidence that StackSense can
rebuild, query and explore architecture graphs safely while canonical P3 data
and earlier product behavior remain intact.

### 7.1 Cross-Module Architectural Review

The six-module division is coherent and collectively covers the approved P4
vertical slice from canonical publication through projection, controlled Python
API integration, exploration and operational proof, subject to the explicit
browser-transport owner gate.

- **M1/M2 boundary:** clean when M1 remains lifecycle/activation authority and
  M2 returns only an immutable independently established verification result.
  Candidate construction success alone can never imply activation.
- **M2/M3 boundary:** clean because M3 receives no writer or candidate access;
  it queries only the active generation selected by M1.
- **M3/M4 boundary:** graph-query semantics remain in M3; M4 composes and
  completes their Python/FastAPI delegated API, error and OpenAPI integration
  without duplicating traversal logic or adding Express work.
- **M4/M5 boundary:** Express remains the completed security authority and React
  continues to call Express only. M5 consumes rather than defines DTOs. Only
  independent M5 shell/layout work can overlap M4 before P4-D1 freezes; live
  browser integration is blocked if the existing Express surface cannot carry
  the graph calls, pending a separate owner decision outside P4 M1–M4.
- **M6 coverage:** includes the operational lifecycle—discovery, dispatch,
  concurrency, verification, activation, history, failure, recovery, rebuild,
  query, authorization, degradation and accessibility—not just happy-path E2E.
- **Shared concerns without duplicate ownership:** M1 owns infrastructure and
  lifecycle health; M3 owns query-capability health; M4 composes it into the
  Python API; M5 presents it only through the existing Express boundary.
  Rebuild requests enter through the M3/M4 Python API, but M1 owns lifecycle
  execution and M2 owns candidate construction.

No missing P4 responsibility or unnecessary seventh module is identified. The
principal boundary risks are P3 coupling during published-version discovery,
M1/M2 activation drift, M3 DTO duplication in React or any future approved
gateway work, cross-scope graph
queries and UI claims of completeness. The existing contracts and freeze points
address each risk if enforced during detailed planning.

No approved P4 baseline decision is changed. The owner has accepted this
discussion as the shared foundation and authorized detailed M1 planning. Driver
compatibility, operational thresholds and other recorded items remain detailed
module-planning or implementation verification work. The no-new-Express
boundary exposes one separate downstream approval question—how M5 reaches the
new graph API if the completed Express surface is insufficient—which must be
resolved without silently changing P4 M1–M4 or the approved baseline.

## 7A. Detailed M1 Plan — Graph Infrastructure and Projection Lifecycle

**Status: FROZEN / COMPLETE.** All three batches, the independent review, its
remediation and the narrowly authorized manifest-schema correction are verified
and owner-accepted. P4-L1, P4-S1, P4-W1 and the corrected
`ProjectionManifest` graph-schema surface remain frozen at `1.0.0`. Section
12.7 records the amendment and its acceptance. This section remains the
implementation record; M2 must consume the contracts without reopening any
other M1 surface or changing P4 Baseline v1.

### A. Module overview

**Objective and outcome:** M1 establishes an independent PostgreSQL control
plane and Neo4j infrastructure boundary for graph projections. At completion,
every published Architecture Version can be discovered idempotently, represented
by a durable projection resource, scheduled through recoverable identifier-only
messages, supervised through leases, and activated only by M1 after an
independent M2 verification result passes current-attempt checks.

**Responsibilities:** Neo4j connectivity/schema bootstrap; projection resources
and attempts; source discovery; reconciliation; queue dispatch/recovery; leases,
heartbeats and retry accounting; public/internal state mapping; transactional
active-generation switching; graph component health; safe operational logging.

**Exclusions:** M1 does not construct graph nodes/relationships, verify candidate
contents, query/traverse graphs, expose graph product APIs, authorize browser
users, render React UI, alter canonical Architecture Model semantics, or add
P5/P6 functionality.

**Dependencies and consumers:** M1 consumes frozen P3 `PUBLISHED` Architecture
Version headers and the exact `load_published_document` read boundary, although
full document loading is used by M2. It reuses PostgreSQL, SQLAlchemy, Alembic,
Celery/RabbitMQ, Pydantic settings, logging, systemd and Docker Compose
conventions. M2 consumes P4-L1/P4-S1/P4-W1 and returns P4-P1; M3 later consumes
lifecycle/active-generation state; M6 validates the real operational path.

**Frozen P3 relationship:** P3 analysis/jobs/stages/events and Architecture
Model publication remain unchanged. M1 adds separate P4 tables, services, tasks
and adapters. No P3 lifecycle event or state is emitted or modified by graph
projection work.

### B. Existing repository assessment

| Verified existing repository evidence | M1 implication |
|---|---|
| Python is 3.14.6; `requirements.txt` has no Neo4j driver installed. | Driver 6.4.x patch selection is evidence-gated in Batch 1. |
| `Settings` in `backend/platform/config.py` centralizes typed environment configuration and production secret checks. | Additive graph settings and production validation belong here; `.env` remains local and untouched. |
| `backend/infra/postgres.py` provides SQLAlchemy 2 sessions over the shared PostgreSQL authority. | Reuse the engine/session boundary; graph lifecycle gets separate tables and repositories. |
| `Base` is shared, migrations explicitly import models in `backend/infra/migrations/env.py`, and Alembic head is `a71f0e4b92c3`. | The P4 migration follows existing explicit DDL/import conventions and revises the actual head at implementation time. |
| P3 repositories use domain records plus abstract ports, SQLAlchemy adapters, optimistic versions, explicit `flush`, and caller-owned commits. | P4 follows the same transaction ownership and concurrency style, adding row locks where activation requires atomic multi-row decisions. |
| `ArchitectureVersionModel` stores project/repository/sequence/state/digests/counts and has project/state plus project/repository/sequence indexes. | A P4 adapter can enumerate `PUBLISHED` headers read-only without adding a P3 repository method or changing the frozen table. |
| `ArchitecturePublicationRepository.load_published_document(version_id, project_id)` already rehydrates only complete published documents. | P4-S1 delegates exact loading to this frozen method; no duplicate document loader is created. |
| Celery currently includes only `backend.worker.tasks`, defaults to `analysis.jobs`, uses JSON, late ack, worker-lost rejection, prefetch 1 and Beat recovery. | Add graph task registration and explicit task routing without changing existing analysis task semantics. |
| Analysis recovery persists work before broker dispatch, republishes undispatched/stale work, and relies on optimistic concurrency. | Reuse the durable-intent/at-least-once pattern, but use lease tokens and a partial unique index for graph attempts. |
| Existing systemd units run one analysis worker and one Beat scheduler. | Add a dedicated graph worker unit; retain a single Beat process and route graph work to its own queue. |
| `/api/v1/health` currently returns exactly `{status: ready}` and P1 tests freeze that behavior. | Preserve it; add a separate graph component health route/service without making core readiness depend on Neo4j. |
| Compose currently contains PostgreSQL 16 and RabbitMQ 3.13 with named volumes/health checks; no Neo4j service exists. | Add Neo4j 5.26.33 Community, a named volume, environment-based credentials and localhost-only development ports. |
| No `backend/platform/graph/` package or `tests/p4/` tree exists. | All graph domain/control-plane code and focused tests are new P4-owned paths. |

**Missing capabilities:** Neo4j driver/configuration/schema checks; graph
lifecycle tables; graph repository/source/queue ports; reconciliation; graph
leases; activation CAS; graph task routing/worker; graph-specific health and
observability; P4 tests and fixtures.

**Files that remain untouched:** `master.txt`, frozen F1/F2/F3 and Architecture
Model contracts, `backend/platform/analysis/architecture/repository.py`,
`backend/platform/analysis/architecture/persistence.py`, P3 migrations and
analysis lifecycle/domain/orchestrator code. P4 uses a new dependency module
rather than adding graph composition to
`backend/platform/analysis/application/dependencies.py`.

**Roadmap correction from repository evidence:** the preserved M1 proposal
listed additive published-header methods in the frozen P3 repository/persistence
files and P3 analysis DI changes. Neither is necessary. The detailed plan uses a
P4-owned adapter over the existing model/exact loader and P4-owned DI. Any later
evidence that requires a P3 change is an unapproved change-control request, not
an M1 implementation detail.

### C. Architecture and component responsibilities

#### C1. Neo4j infrastructure and driver lifecycle

A P4 Neo4j adapter owns driver creation, connectivity verification, session
scoping, close/disposal and idempotent schema bootstrap. Configuration keeps URI,
user, password and database separate; credentials are `SecretStr` and never
logged. Batch 1 verifies Community support for the required node and relationship
key constraints before the schema contract is accepted. M1 creates no canonical
graph data; M2 later uses this adapter's bounded execution/session boundary.

#### C2. PostgreSQL projection lifecycle

`GraphProjectionResource` represents one `(architecture_version_id,
projection_type)` and owns public state plus the nullable active-generation
pointer. `GraphProjectionAttempt` represents one candidate generation/execution,
its immutable source/version expectations, retry/dispatch data, actor audit,
lease and terminal outcome. PostgreSQL is authoritative for both; Neo4j and
RabbitMQ never decide lifecycle truth.

The repository port exposes narrow transactional operations rather than generic
CRUD: ensure resource, create/coalesce attempt, mark dispatch, acquire/heartbeat
lease, record retry/failure, list recovery candidates, mark superseded resources
STALE and activate a verified result. The SQLAlchemy adapter owns row locks and
database constraint translation; the application service owns transaction
boundaries through injected commit/rollback callbacks or session units of work,
matching existing conventions.

#### C3. Published Architecture Version source adapter

`PublishedArchitectureSource` is a P4-owned read port. Its SQLAlchemy adapter:

- reads only `ArchitectureVersionModel` rows whose frozen state is `PUBLISHED`;
- returns a safe immutable header containing IDs, repository sequence,
  publication time, source/content digest, architecture schema/analyzer versions
  and canonical counts;
- performs deterministic bounded keyset pages ordered by
  `(project_id, repository_id, sequence_number, id)`;
- begins each reconciliation pass from the start and idempotently ensures
  resources, avoiding a fragile persisted high-water mark that could miss
  backfilled or same-time publications;
- delegates exact document loading to
  `SqlAlchemyArchitectureRepository.load_published_document` for M2 use.

The initial approach uses existing indexes and benchmarks header enumeration.
It does not add an index or method to frozen P3 storage. If measured performance
is insufficient, the exact P3 physical/port change must be proposed separately
for owner-controlled change approval.

#### C4. Reconciliation, scheduling and queue publishing

The reconciler is idempotent and separates discovery, resource creation,
initial-attempt creation, dispatch, interrupted-work recovery and explicit
rebuild. It scans published headers, ensures exactly one resource and marks
older verified repository versions STALE. Automatic scheduling then follows the
resource condition, not merely the absence of an active attempt:

- a newly created resource receives exactly one initial automatic attempt;
- a PENDING resource with eligible undispatched work dispatches or recovers that
  existing attempt and never creates a replacement merely because it is not
  currently leased;
- a RUNNING resource with a valid active attempt is left alone;
- a RUNNING resource with an expired lease or recoverable interruption recovers
  the same eligible attempt/generation under the approved retry policy;
- COMPLETED and STALE resources with verified active generations are no-ops;
- a terminally FAILED resource is a no-op after retry exhaustion; and
- only an explicit OWNER/ADMIN rebuild intent may create a later attempt and new
  candidate generation for a terminal or already projected resource.

A manual rebuild enters the same lifecycle service with a user actor/correlation;
automatic initial work uses an explicit system actor. Concurrent initial or
rebuild requests lock/coalesce onto the existing eligible active attempt. A
repeated reconciliation pass therefore cannot create duplicate resources,
attempts or unnecessary generations.

The proposed P4-W1 freeze target is an identifier-only JSON payload:
`projection_id`, `attempt_id`, `project_id`, `architecture_version_id`,
`generation_id`, `contract_version`, `correlation_id`. It contains no model,
source, credentials, configuration or lease token. The publisher uses
at-least-once delivery: commit intent, publish, then mark dispatch. A crash after
publish but before the mark can duplicate a message, so acquisition must remain
idempotent.

#### C5. Lease, heartbeat and retry ownership

Worker acquisition atomically moves an eligible QUEUED/RETRYING attempt to
RUNNING and returns a new unpredictable lease token plus expiry. The token is not
in RabbitMQ; it is obtained from PostgreSQL after message receipt. Heartbeats
must match attempt, generation, worker and lease token and extend an unexpired
lease. Old workers cannot heartbeat or complete after lease replacement.

Transient execution/Neo4j failures use at most three total execution tries for
one attempt/generation (the initial try plus at most two retries), with persisted
execution/retry count and bounded backoff. Replay of the same attempt keeps the
same generation so M2 writes are idempotent. Exhaustion terminally fails the
attempt. Broker redelivery that loses the lease race is a no-op and does not
consume an execution try. A later rebuild creates a new attempt and generation.

#### C6. Public/internal lifecycle mapping

Public states remain exactly `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`,
`STALE`. Internal attempt states are `QUEUED`, `RUNNING`, `RETRYING`,
`COMPLETED`, `FAILED`, `SUPERSEDED`; they are never exposed as new public
vocabulary.

| Resource condition | Public state |
|---|---|
| No active generation; attempt QUEUED | `PENDING` |
| No active generation; attempt RUNNING/RETRYING | `RUNNING` |
| No active generation; terminal failure/retries exhausted | `FAILED` |
| Verified active generation for current repository version | `COMPLETED` |
| Verified active generation for an older published repository version | `STALE` |
| Rebuild in progress/fails while an active generation exists | Preserve existing `COMPLETED` or `STALE` |

Discovery of a newer published sequence marks older verified resources STALE
without clearing their pointer. Activation also rechecks sequence ordering so an
older out-of-order completion cannot become current.

#### C7. Activation coordination

M2 returns an immutable P4-P1 result; M1 owns the acceptance operation. In one
PostgreSQL transaction M1 locks the resource and attempt and verifies:

1. resource/attempt/project/version identities match;
2. the attempt is the resource's current active attempt;
3. internal state is RUNNING and lease token/owner are current and unexpired;
4. candidate generation matches the attempt;
5. source digest, architecture schema, graph schema, projector version and
   contract version equal the immutable attempt expectations;
6. verification succeeded and expected/actual counts, key-set digest, endpoint
   digest and canonical payload digest are present and equal as required by
   P4-P1.

Success records the safe verification summary, terminally completes the
attempt, switches `active_generation_id`, copies active schema/projector/digest
metadata and sets `COMPLETED` or `STALE` according to canonical sequence. Failure
records only the attempt/candidate outcome; it sets resource `FAILED` solely when
no active generation exists. Stale, expired, superseded or late results are
rejected and become cleanup-eligible without touching the pointer or public
state. M1 does not re-run M2 verification or inspect graph content itself.

#### C8. Health and observability

The existing core health route remains unchanged. A graph component health
service/route reports only `ready`, `degraded` or `unavailable` with safe
component summaries. It reports Neo4j infrastructure/connectivity, PostgreSQL
lifecycle persistence, reconciliation/scheduling and projection-execution
capability separately. Infrastructure `ready` proves connectivity/configuration;
it does not assert that dispatch is enabled or that an M2 executor exists.
Projection execution is ready only after the M2 task/executor is registered,
the dedicated consumer is enabled and its capability check passes. Loss of
Neo4j or RabbitMQ degrades graph capability while canonical P3 APIs remain
healthy; invalid/incompatible graph configuration is unavailable/fail-closed.

Structured logs include correlation, resource, attempt, version, generation,
state transition, lease/retry and duration fields, never secrets, source or full
model payloads. M1 records reconciliation counts, undispatched age, expired
leases, activation rejection reasons and health latency through existing logging
instead of adding an unapproved metrics platform.

### D. Lifecycle and operational flows

1. **Published-version discovery:** Beat schedules reconciliation; the graph
   reconciliation task scans deterministic published-header pages. Discovery
   identifies canonical publications only and does not itself imply attempt
   creation or dispatch.
2. **Resource creation:** inside PostgreSQL, insert one PENDING resource keyed by
   version/type with immutable source scope/digest/schema/count expectations.
   Unique conflict resolves by loading the existing identical resource; a scope
   or digest mismatch fails closed. Resource creation and its first system
   attempt commit atomically, so a crash cannot leave a newly discovered
   resource permanently without its initial durable work.
3. **Initial-attempt creation:** lock the new resource and create exactly one
   QUEUED system attempt with a fresh generation and actor audit. A unique/lock
   race loads the already-created attempt. Reconciliation of COMPLETED, STALE or
   terminally FAILED resources creates no automatic attempt.
4. **Existing-attempt dispatch:** commit durable intent before publishing P4-W1,
   then persist dispatch metadata. A PENDING resource with eligible undispatched
   work republishes that existing attempt. Publish failure leaves the same
   recoverable durable intent; it does not cause attempt replacement.
5. **Worker acquisition:** a duplicated delivery can acquire only an eligible
   attempt. Atomic acquisition assigns worker/lease token/expiry and changes the
   attempt to RUNNING. Other deliveries acknowledge as coalesced/no-op.
6. **Progress/heartbeat:** the future M2 worker periodically calls M1 with the
   lease token. M1 extends expiry only for the current owner/generation and emits
   safe structured progress logs; P3 events are untouched.
7. **Successful M2 handoff:** M2 submits its immutable verification result with
   lease identity. Receipt does not itself imply success until activation
   validation runs.
8. **Activation:** M1 performs the C7 checks and pointer switch in one PostgreSQL
   transaction. Readers become able to select the generation only after commit.
9. **Initial failure/retry:** transient failure moves the same attempt/generation
   to RETRYING, increments persisted retry count and republishes after backoff.
   Exhaustion marks attempt and pointerless resource FAILED.
10. **RabbitMQ dispatch failure:** the committed QUEUED attempt retains null/old
   dispatch metadata. Reconciliation republishes it. Duplicate sends are safe
   because lease acquisition is authoritative.
11. **Worker crash/expired lease:** reconciliation locks the expired RUNNING
    attempt. If retry budget remains it invalidates the old token, records
    RETRYING and republishes; otherwise it records terminal failure. Old worker
    results are rejected.
12. **Terminal automatic failure:** after the third execution fails, the attempt
    and pointerless resource become FAILED. Later reconciliation records the
    terminal state but never creates or dispatches another automatic attempt.
13. **Explicit rebuild:** an OWNER/ADMIN request entering through later M3/M4
    Python API work deliberately creates a new attempt and candidate generation
    after locking/coalescing. This remains possible after terminal failure and
    for COMPLETED/STALE resources; it is distinct from automatic reconciliation.
14. **Concurrent rebuilds:** row locking plus a partial unique active-attempt
    index yields one attempt/generation. Losing requests return the existing
    attempt; their safe actor/correlation is logged without mutating its creator
    audit.
15. **Late/stale/superseded result:** attempt/lease/generation mismatch returns a
    deterministic rejection, marks only eligible terminal audit state and never
    switches the resource pointer.
16. **Failed rebuild with COMPLETED active generation:** resource stays
    COMPLETED and G1 remains readable; failed G2 is cleanup-eligible.
17. **Failed rebuild with STALE historical active generation:** resource stays
    STALE and G1 remains exact-version readable; it never becomes FAILED.
18. **Neo4j outage/recovery:** new graph execution cannot succeed, retries remain
    bounded, graph health degrades and canonical P3 remains ready. After Neo4j
    returns, reconciliation republishes eligible work; complete loss is repaired
    by later rebuilds from published Architecture Models, not reanalysis.

### E. Persistence and contracts

#### E1. Projection resource

Planned `graph_projection_resources` fields: UUID id; Architecture Version,
project and repository IDs; architecture sequence; fixed projection type;
source content digest and schema version; public state; nullable active
generation; active projector/graph-schema/digest/count summary; safe last
failure; optimistic version; created/updated/activated timestamps.

Required guarantees:

- unique `(architecture_version_id, projection_type)`;
- FK to `architecture_versions.id` with restrictive deletion;
- positive architecture sequence and optimistic version;
- public-state check vocabulary;
- `COMPLETED`/`STALE` require an active generation;
- `PENDING`/`RUNNING`/`FAILED` require no active generation;
- indexes for project/version lookup, repository sequence/current selection and
  public-state reconciliation.

#### E2. Projection attempt

Planned `graph_projection_attempts` fields: UUID id/resource/generation;
monotonic attempt number; internal state; actor type/id/role and correlation ID;
payload contract, source digest/schema, graph schema and projector versions;
execution/retry counts with a maximum of three executions, dispatch data; lease
owner/token/heartbeat/expiry; safe
expected/actual verification summary; safe failure; optimistic version and
timestamps.

Required guarantees:

- FK to resource and unique `(resource_id, generation_id)` plus
  `(resource_id, attempt_number)`;
- globally unique generation UUID;
- partial unique index allowing at most one QUEUED/RUNNING/RETRYING attempt per
  resource;
- active-state/lease field consistency checks;
- non-negative retry/dispatch counts and bounded safe text;
- indexes for undispatched work, expired leases, resource history and
  correlation/audit lookup;
- a deferred composite FK from `(resource.id, active_generation_id)` to the same
  resource's attempt generation, preventing cross-resource pointer assignment.

No separate public-event table or P3 event vocabulary is introduced. Attempt
history is the durable P4 audit record.

#### E3. P4-S1 source contract

The immutable header includes version/analysis/project/repository/snapshot IDs,
sequence, published time, content/configuration digest, analyzer/IR/architecture
schema versions and all canonical counts. Enumeration returns deterministic
bounded pages. Exact loading is project-scoped and returns only PUBLISHED data.

#### E4. P4-W1 worker contract

The payload fields are exactly those listed in C4. Deserialization rejects
missing/extra keys, invalid UUIDs, unsupported task/contract versions and scope
mismatch. Correlation ID is opaque bounded text. Lease credentials are never
serialized.

#### E5. M1 activation port toward P4-P1

M1 freezes the identity/version/lease fields it requires, but M2 owns the final
verification-result vocabulary in P4-P1. The port accepts immutable success or
failure and never accepts a bare `verified=true` without independent summaries.
The activation result is one of activated, already-activated idempotent replay,
rejected-stale/superseded, or recorded-failure; none creates a new public state.

#### E6. Transaction boundaries

- new-resource and initial-attempt creation commit atomically before broker
  publish; existing-resource reconciliation never backfills a new attempt based
  only on the absence of an active attempt;
- dispatch marking is a later idempotent transaction;
- lease acquire/heartbeat/retry each uses conditional update or row lock;
- activation locks resource and attempt and commits pointer, public state,
  active metadata and terminal attempt together;
- marking older repository resources STALE locks affected resources and never
  clears active pointers;
- no transaction spans PostgreSQL and Neo4j; Neo4j candidate readiness plus the
  PostgreSQL pointer gate provides atomic visibility.

### F. Infrastructure and compatibility

1. Start Neo4j Community `5.26.33` in an isolated development container with a
   named volume and localhost-bound Bolt/HTTP ports.
2. Test available official Python driver `6.4.x` patches under the repository's
   Python `3.14.6`; record install, import, sync driver, TLS/URI parsing,
   connectivity, session/transaction timeout and clean shutdown results.
3. Verify the exact Community constraint/index syntax required for
   `ArchitectureEntity.projection_key`, `ARCH_RELATIONSHIP.projection_key` and
   generation manifest identity. Test idempotent bootstrap and incompatible
   pre-existing schema failure.
4. Pin the exact driver only after the spike passes; no speculative requirement
   entry is approved.
5. Add typed settings for Neo4j URI/user/password/database, connection/pool/
   health timeouts; graph queue, concurrency/prefetch; reconciliation/dispatch
   intervals; lease/heartbeat; three-total-execution retry/backoff. Contract,
   graph-schema and projector versions are code-owned constants persisted with
   attempts, not arbitrary environment overrides. Validate heartbeat is safely
   shorter than lease and reject empty/default Neo4j secrets in production.
6. Compose credentials come from environment interpolation, not committed
   literals; health checks must not print them. `.env.example` documents safe
   placeholders while `.env` remains untracked/local.
7. Separate M1 control-plane work from future projection execution. Beat routes
   reconciliation and its liveness heartbeat to `graph.maintenance`; the M1
   systemd worker consumes only that queue. `graph.projections` remains the
   P4-W1 execution queue and has no deployed consumer until M2 registers the
   exact executor. Retain one Beat process while database constraints make an
   accidental duplicate scheduler safe.
8. The maintenance worker/reconciliation schedule and future projection
   consumer must not be enabled as one undifferentiated switch. Neo4j infrastructure, graph
   health, lifecycle persistence and direct reconciliation tests may be enabled
   first. Reconciliation may discover publications and create durable initial
   intent while execution dispatch is disabled; the attempt remains eligible
   and undispatched rather than being acknowledged, discarded or replaced.
9. Execution dispatch has an explicit fail-closed readiness gate backed by M2
   executor registration/capability. If unavailable, M1 reports execution as
   not ready and leaves durable work recoverable. It does not publish executable
   jobs to a consumer that cannot execute them.
10. The graph-maintenance worker is enabled with M1 so reconciliation cannot
    accumulate on an unconsumed queue. The projection queue consumer and
    projection-execution dispatch are enabled only after M2 registers the exact
    P4-W1 task/executor and a fresh execution heartbeat succeeds. Expiring
    PostgreSQL capability evidence proves that Beat delivery reached the
    appropriate queue worker; local task registration alone is never treated as
    runtime readiness.

**Deployment/activation sequence:** (1) deploy Neo4j infrastructure and prove
connectivity; (2) expose graph infrastructure health without claiming execution
readiness; (3) migrate and verify PostgreSQL lifecycle persistence; (4) enable
published-version discovery/reconciliation by enabling the maintenance worker
with execution dispatch disabled, so new work is durable; (5) verify queue
publishing/routing and recovery without a deployed projection consumer; and (6)
only after M2 registers the executor and its live execution heartbeat passes,
enable the projection consumer and dispatch. Failure at any step leaves
canonical P3 available and cannot silently discard queued work.

### G. File-by-file change plan

Paths marked CREATE are proposed P4 paths verified not to exist; the Alembic
revision filename receives its generated revision ID during implementation.

| Action | Exact path | Responsibility and integration reason |
|---|---|---|
| CREATE | `backend/platform/graph/__init__.py` | P4 graph package boundary and deliberately small exports. |
| CREATE | `backend/platform/graph/model.py` | Resource/attempt records, public/internal enums, invariants, transition results and M1-owned contract constants. |
| CREATE | `backend/platform/graph/repository.py` | Persistence port for ensure/coalesce, leases, recovery, failure, history, STALE marking and transactional activation. |
| CREATE | `backend/platform/graph/persistence.py` | SQLAlchemy models/mappers/repository using shared `Base`, PostgreSQL locks, optimistic versions and constraint translation. |
| CREATE | `backend/platform/graph/source.py` | P4-S1 header/read port and SQLAlchemy adapter over frozen `ArchitectureVersionModel` plus exact loader delegation. |
| CREATE | `backend/platform/graph/queue.py` | Strict P4-W1 payload, publisher port, in-memory test adapter and Celery publisher. |
| CREATE | `backend/platform/graph/lifecycle.py` | Lifecycle service, reconciler, scheduling/coalescing, lease/retry/recovery and activation orchestration. |
| CREATE | `backend/platform/graph/neo4j.py` | Official-driver lifecycle, connectivity/capability checks and idempotent schema bootstrap; M2 later extends bounded graph operations. |
| CREATE | `backend/platform/graph/health.py` | Layered graph health model/service and safe component summaries. |
| CREATE | `backend/platform/graph/dependencies.py` | P4-owned composition providers for repositories, source, lifecycle, driver and health; avoids P3 analysis DI changes. |
| CREATE | `backend/platform/graph/runtime.py` | Expiring PostgreSQL-backed evidence that scheduled heartbeats reached the maintenance or execution queue worker. |
| CREATE | `backend/worker/graph_tasks.py` | M1 reconciliation/recovery task adapters and explicit execution-capability gate; M2 later adds the registered projection executor. No deployed consumer acknowledges projection work before that registration. |
| CREATE | `backend/infra/migrations/versions/<generated_revision>_create_graph_projection_lifecycle.py` | P4 resource/attempt tables, checks, FKs and indexes; `down_revision` is actual head `a71f0e4b92c3` unless changed before implementation. |
| CREATE | `backend/infra/migrations/versions/<generated_revision>_add_graph_runtime_capabilities.py` | Expiring per-worker scheduling/execution capability evidence. |
| CREATE | `ops/systemd/stacksense-celery-graph-worker.service` | M1 `graph.maintenance` consumer with existing restart/shutdown conventions; M2 separately enables execution-queue consumption. |
| MODIFY | `backend/platform/config.py` | Add typed graph/Neo4j/lease/queue settings and production validation. |
| MODIFY | `.env.example` | Document graph settings and secret placeholders; do not modify `.env`. |
| MODIFY after passing spike | `requirements.txt` | Pin the proven official Neo4j 6.4.x patch only. |
| MODIFY | `infra/docker/compose.yml` | Add Neo4j Community 5.26.33, named volume, environment auth, health check and localhost-only dev ports. |
| MODIFY | `backend/infra/migrations/env.py` | Import new P4 persistence models into shared metadata. |
| MODIFY | `backend/worker/celery_app.py` | Include graph tasks, explicit analysis/graph task routes and graph reconciliation Beat entry while preserving analysis defaults. |
| REUSE | `ops/systemd/stacksense-celery-beat.service` | Existing single Beat authority already loads `celery_app` schedules; no unit-file change is currently required. |
| MODIFY | `backend/platform/health.py` | Preserve `/health` response exactly and add separate safe graph component health reporting. |
| REUSE | `backend/platform/dependency_injection.py`, `backend/infra/postgres.py`, `backend/platform/logging.py` | Existing engine/session/logging foundations; no change is currently required. |
| REUSE / DO NOT MODIFY | `backend/platform/analysis/architecture/repository.py`, `backend/platform/analysis/architecture/persistence.py` | Frozen exact loader and model only; no P4 methods or fields added. |
| DO NOT MODIFY | `backend/platform/analysis/application/dependencies.py` and all P3 domain/orchestrator/stage/event files | Graph composition is P4-owned; analysis behavior remains frozen. |
| CREATE | `tests/p4/__init__.py`, `tests/p4/graph/__init__.py` | P4 test package boundaries. |
| CREATE | `tests/p4/graph/test_model.py` | State/invariant/public mapping and payload-version rules. |
| CREATE | `tests/p4/graph/test_persistence.py` | Repository mapping, constraints, optimistic/locking behavior and activation semantics. |
| CREATE | `tests/p4/graph/test_source.py` | Deterministic complete header enumeration, publication filtering and exact loader delegation. |
| CREATE | `tests/p4/graph/test_queue.py` | Exact identifier-only payload, strict parsing, routing and broker failure behavior. |
| CREATE | `tests/p4/graph/test_lifecycle.py` | All state, lease, three-execution retry, explicit rebuild/coalescing, activation and rebuild-preservation flows, including rebuild after terminal failure. |
| CREATE | `tests/p4/graph/test_reconciliation.py` | Discovery/resource/initial-attempt separation; repeated-scan idempotency; no automatic attempt for COMPLETED, STALE-with-active-generation or terminal FAILED; existing undispatched and expired-lease recovery without duplicate attempts; missing-M2 execution gate. |
| CREATE | `tests/p4/graph/test_health.py` | Core readiness regression and graph ready/degraded/unavailable behavior. |
| CREATE | `tests/p4/integration/test_graph_lifecycle_postgres.py` | Real PostgreSQL migration, constraints, concurrent attempts and activation CAS. |
| CREATE | `tests/p4/integration/test_graph_neo4j_compatibility.py` | Real Neo4j/Python 3.14 driver and Community schema evidence. |
| CREATE | `tests/p4/integration/test_graph_dispatch_rabbitmq.py` | Real RabbitMQ routing, duplicate delivery and dispatch recovery evidence. |

No M1 graph product route, Express file, frontend file, M2 projector or M3 query
implementation is planned.

### H. Three implementation batches

#### Batch 1 — Compatibility and Infrastructure

**Objective:** prove the selected runtime combination and establish safe Neo4j
configuration/connectivity/schema/health foundations.

**Scope/files:** `config.py`, `.env.example`, Compose, `requirements.txt` only
after evidence, `graph/{neo4j,health,dependencies}.py`, package init, graph health
extension and compatibility/health tests.

**Dependencies:** approved Neo4j 5.26.33/driver 6.4.x direction, Python 3.14.6,
existing Compose/settings/health patterns. No lifecycle tables are needed yet.

**Expected output:** recorded exact driver patch, reproducible Neo4j container,
validated Community constraints, idempotent bootstrap, safe driver lifecycle and
layered graph health that cannot break core readiness.

**Verification:** real container connectivity and schema tests plus unit tests
for config production failure, secret redaction, health degradation, driver
close and unsupported schema. Run Ruff, Black, strict Mypy and P1 health
regression.

**Exit criteria:** exact driver patch proven/pinned; Python 3.14 and Community
capabilities pass; credentials are externalized; `/health` remains unchanged;
Neo4j outage reports only graph degradation.

**Freeze point:** infrastructure selections and internal schema-bootstrap
capabilities become the M2 dependency; P4-L1/S1/W1 are not frozen yet.

#### Batch 2 — Lifecycle Persistence and Contracts

**Objective:** implement the complete PostgreSQL control-plane model, source
adapter, lifecycle rules and M1 activation boundary.

**Scope/files:** `graph/{model,repository,persistence,source,queue,lifecycle}.py`,
P4 dependencies, Alembic migration/env import and unit/real-PostgreSQL tests.
The queue payload and in-memory publisher are defined here; Celery scheduling is
Batch 3.

**Dependencies:** Batch 1 configuration/constants; frozen Architecture Version
model/loader; existing SQLAlchemy/Alembic/session conventions.

**Expected output:** durable resources/attempts, deterministic source discovery,
strict payload contract, coalescing/leases/retries, public-state mapping and
transactional activation with COMPLETED/STALE preservation.

**Verification:** migration upgrade/downgrade; PostgreSQL constraints/indexes;
parallel request/activation tests; late lease/result rejection; initial failure;
COMPLETED and STALE failed rebuilds; terminal FAILED explicit rebuild; repeated
reconciliation with no new attempt for COMPLETED/STALE/terminal FAILED;
interrupted-work recovery reusing the existing attempt; source pages with
concurrent publications; exact loader delegation and P3 immutability checks.

**Exit criteria:** every D/E invariant is executable and tested on PostgreSQL;
no source/pointer race can expose a candidate; M2 cannot activate; no P3 file or
contract changed.

**Contract freeze:** after Batch 2 implementation and verification, independent
review plus explicit owner approval freezes P4-L1, P4-S1 and P4-W1 before M2
worker implementation. P4-P1's full verification vocabulary remains M2-owned,
while M1's required activation envelope becomes frozen at that gate. Approval of
this planning draft alone does not freeze an unimplemented contract.

#### Batch 3 — Scheduling and Operations

**Objective:** connect durable intent to RabbitMQ/Celery recovery and complete
operational supervision without implementing M2 projection.

**Scope/files:** Celery publisher, `worker/graph_tasks.py`, Celery include/routes/
Beat schedule, graph worker systemd unit, reconciler/recovery composition,
operational logs/health and RabbitMQ/reconciliation tests.

**Dependencies:** frozen Batch 2 contracts and Batch 1 driver/health. M2's task
implementation is not added; deployment enablement waits for M2 registration.

**Expected output:** dedicated queue routing, resource discovery schedule,
recoverable durable intent, duplicate-safe dispatch/acquisition once enabled,
stale lease recovery, system/user audit, separate infrastructure/execution
readiness and operator-visible degradation. With M2 absent, execution dispatch
is disabled and queued intent remains durable and undiscarded.

**Verification:** real RabbitMQ publish/routing and broker interruption;
crash-after-publish duplicate; two reconcilers; worker lease loss; retry
exhaustion; absent-M2 executor leaves work undispatched/unacknowledged; later
executor enablement recovers the same attempt; service unit syntax/manual smoke;
Neo4j/RabbitMQ outages; full M1 and P1–P3 regression/static checks.

**Exit criteria:** durable work survives broker/worker interruption; one active
attempt invariant holds; graph queue cannot starve analysis jobs; operational
health/logging is safe; infrastructure can be deployed/tested independently;
rollout cannot dispatch to or consume an unregistered M2 task; enabling the M2
executor later recovers the existing eligible intent without a duplicate
attempt.

**Freeze point:** M1 is ready for independent review/freeze. Detailed M2 planning
may consume the frozen contracts only after owner acceptance; implementation is
never implied by plan approval.

### I. Testing and verification strategy

**Unit/SQLite-compatible tests:** pure domain transitions, state mapping, strict
payload, source-header mapping, service decisions, retry classification, health
aggregation and fake publisher/driver behavior. SQLite tests do not claim proof
of PostgreSQL locks, partial indexes or concurrency.

**Real PostgreSQL tests:** migration upgrade/downgrade from actual Alembic head;
partial active-attempt uniqueness; composite active-generation FK; `FOR UPDATE`
coalescing; optimistic version conflicts; activation transaction rollback;
concurrent rebuild/activation order; exact COMPLETED/STALE preservation;
deterministic full source enumeration.

**Real Neo4j tests:** 5.26.33 Community connectivity from Python 3.14, exact
driver patch, auth failure, named database behavior available in Community,
transaction timeout, node/relationship constraint support, bootstrap replay,
schema mismatch and outage/reconnect/close.

**Real RabbitMQ/Celery tests:** queue routing, JSON payload contents, late-ack/
worker-loss behavior where practical, broker publish failure, undispatched
recovery, duplicate delivery, Beat/reconciler idempotency and analysis-queue
isolation. Mocked Celery tests supplement but do not replace these.

**Lifecycle scenario matrix:** all 18 flows in Section D, especially lease-token
replacement, late P4-P1 results, initial failure, explicit rebuild coalescing,
out-of-order repository versions, failed rebuilds for both COMPLETED and
historical STALE resources, and reconciliation of each terminal public state.
It explicitly proves that repeated reconciliation creates no attempt for
COMPLETED, STALE-with-active-generation or terminal FAILED resources; eligible
interrupted work recovers the existing attempt; explicit rebuild remains
possible after failure; and absent M2 capability leaves work durable and
undispatched.

**Regression and quality:** existing P1 `/health`, P3 Architecture Model reads,
analysis Celery routing/recovery and full frozen test suites; `black --check`,
`ruff check`, strict `mypy`, Alembic head/upgrade/downgrade and `git diff
--check`. Commands must be recorded when implementation occurs; this planning
task claims no test execution.

Planned verification commands, using explicit test service URLs/secrets from the
implementation environment rather than committed credentials:

```text
docker compose -f infra/docker/compose.yml config
docker compose -f infra/docker/compose.yml up -d postgres rabbitmq neo4j
./venv/bin/alembic upgrade head
./venv/bin/pytest tests/p4/graph
./venv/bin/pytest tests/p4/integration/test_graph_lifecycle_postgres.py
./venv/bin/pytest tests/p4/integration/test_graph_neo4j_compatibility.py
./venv/bin/pytest tests/p4/integration/test_graph_dispatch_rabbitmq.py
./venv/bin/pytest
./venv/bin/black --check backend tests
./venv/bin/ruff check backend tests
./venv/bin/mypy backend
systemd-analyze --user verify ops/systemd/stacksense-celery-graph-worker.service
git diff --check
```

Downgrade/upgrade migration verification uses the generated M1 revision ID and
must restore `head`; it is not expressed with a guessed revision identifier in
this plan.

### J. Risks, unresolved decisions and approval gates

| Risk/uncertainty | Planned mitigation / approval gate |
|---|---|
| No Neo4j driver is installed; exact 6.4.x Python 3.14 behavior is unverified. | Batch 1 evidence gate. Owner approves the exact pin only after recorded compatibility results. |
| Neo4j Community relationship uniqueness/schema capability may differ from the proposal. | Spike exact DDL. If required guarantees cannot be met without changing the approved storage/schema direction, stop for owner decision rather than weakening verification. |
| P4 source enumeration imports a frozen persistence model and may become slow at high version counts. | Keep it read-only/P4-owned, full deterministic pages and benchmark. Any P3 port/table/index change requires separate explicit change control. |
| PostgreSQL cannot atomically commit Neo4j data. | Preserve candidate invisibility and use independently verified READY candidate plus PostgreSQL pointer-gated visibility; never claim distributed atomicity. |
| Broker publish/mark-dispatched crash window duplicates messages. | At-least-once design, strict attempt identity and idempotent lease acquisition. |
| Expired worker may continue after a new lease. | Unpredictable lease token on every acquisition; token required for heartbeat/result/activation. |
| Concurrent version discovery and out-of-order completion can mislabel current/history. | Persist architecture sequence, lock repository resources during STALE/current decision and recheck during activation. |
| Intermediate M1 deployment could strand reconciliation or acknowledge execution work before M2 task registration. | Run M1 reconciliation on `graph.maintenance`; keep `graph.projections` dispatch and its consumer disabled until M2 registers and passes an expiring live-worker capability check. Retain eligible durable intent for later recovery. |
| Reconciliation could recreate work for a completed, stale or terminally failed resource. | Eligibility is state-specific: only a newly created resource gets an automatic initial attempt; PENDING/RUNNING recover existing work; COMPLETED/STALE/terminal FAILED are automatic no-ops. Explicit rebuild is a separate authorized command. |
| Health checks could make canonical APIs unavailable. | Separate graph health from unchanged core `/health`; graph failure only degrades graph capability. |
| Actor/correlation data or error text could leak sensitive input. | Bounded safe fields, allowlisted failure codes, sanitized messages and negative logging tests. |

This corrected detailed M1 plan was subsequently owner-approved, implemented
and frozen. Its driver, Community-schema and P4-owned source-adapter gates were
resolved by the verified M1 execution record. The later browser-transport
decision remains outside P4 M1–M4: it cannot authorize an Express change by
implication, and React cannot bypass the completed platform boundary by calling
Python directly.

### K. M1 Definition of Done

M1 is complete only when all of the following are evidenced:

1. Neo4j Community 5.26.33 and one exact official 6.4.x driver patch work on
   Python 3.14 with recorded connectivity, timeout, constraint and shutdown
   evidence.
2. Production-safe typed configuration rejects invalid/default secrets and
   never logs credentials; Compose uses a persistent volume and localhost-only
   development exposure.
3. PostgreSQL migrations upgrade/downgrade and enforce resource uniqueness,
   active-attempt uniqueness, lease/state checks and same-resource active
   generation references.
4. Every PUBLISHED Architecture Version is discovered through complete,
   deterministic, bounded P4-owned enumeration; exact loading delegates to the
   frozen P3 loader.
5. Only a newly created resource receives an automatic initial attempt;
   PENDING/RUNNING reconciliation dispatches or recovers the existing eligible
   attempt; COMPLETED, STALE-with-active-generation and terminal FAILED
   resources create no automatic attempts or generations.
6. RabbitMQ loss, crash-after-publish, duplicate delivery, expired lease and
   retry exhaustion recover or terminate exactly as planned without duplicate
   activation.
7. Only the current lease-valid attempt and matching generation/source/schema/
   projector/contract verification result can activate.
8. Pointer switch, active metadata, attempt completion and public state commit
   transactionally; no Neo4j candidate is selected before that commit.
9. Late/stale/superseded results cannot switch a pointer. Initial terminal
   failure becomes FAILED, while failed rebuild preserves active generation and
   existing COMPLETED or historical STALE state/readability.
10. Older verified versions remain exact-query eligible as STALE and
    out-of-order completion cannot silently become current.
11. Explicit OWNER/ADMIN rebuild remains possible after terminal failure and
    creates one deliberate new attempt/generation; repeated reconciliation and
    eligible interrupted-work recovery remain idempotent.
12. Dedicated graph queue/worker/reconciliation cannot starve or alter analysis
    work; P3 states, events, contracts and files remain frozen.
13. Infrastructure, lifecycle and reconciliation are independently testable
    before M2. Dispatch/consumer activation fails closed while the M2 executor is
    absent, preserves durable undispatched work and reports the missing
    capability without silently acknowledging or discarding jobs.
14. Core health stays ready during graph outage; graph health honestly reports
    ready/degraded/unavailable, distinguishes execution readiness and contains
    safe correlation/lifecycle evidence.
15. Real PostgreSQL, Neo4j and RabbitMQ checks plus focused unit/concurrency/
    recovery tests, full P1–P3 regressions and Black/Ruff/Mypy/diff gates pass
    with exact results recorded.
16. P4-L1, P4-S1 and P4-W1 are reviewed, versioned and frozen; M1 is independently
    reviewed with no unresolved acceptance blocker.

## 7B. Preserved Detailed Six-Module Roadmap

### M1 — Graph Infrastructure and Projection Lifecycle

**Objective:** establish Neo4j connectivity/schema, independent PostgreSQL
lifecycle, durable reconciliation/dispatch and layered health without changing
the analysis pipeline.

**Boundary:** owns P4-L1, P4-S1 and P4-W1, config, migration, projection queue,
leases, status transitions, verified-generation activation and scheduling. It
excludes graph transformation, verification, traversal APIs, Express and UI.

**Inputs/outputs:** consumes published version headers and system/manual intent;
emits durable resources/attempts and identifier-only worker payloads. New
infrastructure: Neo4j Community, official driver, an M1 `graph.maintenance`
worker and the isolated future `graph.projections` execution queue.

**Design:** `GraphProjectionRepository` is lifecycle authority; RabbitMQ is not.
The P4-owned `PublishedArchitectureSource` deterministically discovers published
version headers without changing the frozen P3 port or implementation.
Reconciliation creates missing PENDING resources, marks older verified
repository versions STALE, creates one initial system attempt only with a newly
created resource, dispatches existing eligible undispatched attempts and
recovers expired leases without replacement attempts. COMPLETED,
STALE-with-active-generation and terminal FAILED resources are automatic
no-ops; only explicit OWNER/ADMIN rebuild creates a later attempt/generation.
Manual actor identity is retained. M1 alone consumes a successful immutable M2 verification result,
rejects stale or superseded attempts, and atomically switches the active
generation pointer. Liveness never depends on Neo4j; graph health is separately
ready/degraded/unavailable.

**Files:**

| Action/path | Responsibility |
|---|---|
| CREATE `backend/platform/graph/{__init__,model,repository,persistence,queue,lifecycle,neo4j,health,runtime}.py` | P4 domain records/ports, SQLAlchemy adapter, queue payload/publisher, reconciler/lifecycle service, driver/schema/health and expiring runtime-capability adapters. |
| CREATE `backend/platform/graph/source.py` | P4-owned read-only published-header enumeration over the frozen Architecture Version model and delegation to the frozen exact-document loader. |
| CREATE `backend/worker/graph_tasks.py` | Reconcile/recover tasks now; M2 adds execution task. |
| CREATE two P4 Alembic revisions | Resources/attempts plus expiring runtime-capability evidence, FKs/checks/indexes, active-attempt uniqueness and active-generation safety. |
| CREATE `ops/systemd/stacksense-celery-graph-worker.service` | Dedicated M1 maintenance-queue consumer; do not starve analysis jobs or consume execution work before M2. |
| MODIFY `backend/platform/config.py`, `.env.example`, `requirements.txt` | Neo4j URI/user/secret/database, graph queue/retry/lease/cursor settings; exact driver pin after spike. |
| MODIFY `infra/docker/compose.yml` | Neo4j 5.26.33, auth, health check, named volume, localhost-only development ports. |
| MODIFY `backend/worker/celery_app.py` | Include graph tasks, task routing and reconciliation schedule. |
| REUSE `backend/platform/analysis/architecture/repository.py` and `persistence.py` | Frozen exact `load_published_document` behavior and existing persistence model; no modification is planned. Any additive published-header port method is a fallback requiring explicit P3 change control. |
| CREATE `backend/platform/graph/dependencies.py`; MODIFY `backend/platform/health.py` | P4-owned DI and layered graph component health. Frozen P3 analysis DI is not modified. |
| CREATE `tests/p4/graph/test_{lifecycle,persistence,reconciliation,queue,source,neo4j_compatibility}.py` | State, lease, source enumeration, failed verification, STALE-resource rebuild preservation/exact readability, stale/late result rejection, concurrent activation, migration, dispatch recovery and real connectivity. |

**Batches:**

1. **Compatibility/infrastructure:** prove an exact 6.4.x driver on Python 3.14
   against 5.26.33; pin it; add config/Compose/driver/schema bootstrap and
   Community constraint-capability check.
2. **Lifecycle persistence:** implement migration, domain transitions,
   repository/CAS/leases, the P4-owned source adapter, transactional verified
   activation and P4-L1/P4-S1/P4-W1 tests; freeze those contracts.
3. **Scheduling/operations:** queue publisher, reconciler, dispatch/stale-lease
   recovery, system audit and health/logs. Infrastructure and durable lifecycle
   use a live maintenance heartbeat with execution disabled; the projection
   queue consumer is not enabled until M2 registers and proves its executor
   capability.

**Acceptance / DoD:** migrations upgrade/downgrade on real PostgreSQL; Python
3.14 connects to real Neo4j; public/internal state mapping is exact; duplicate
schedulers create one active attempt; repeated reconciliation of
COMPLETED/STALE/terminal FAILED creates none; queue failure recovers the existing
attempt; every published version eventually gets a resource; no P3 stage/event changes; outage
reports graph degradation while core health and canonical reads remain ready.
Failed verification cannot activate; stale/lease-lost results and late results
from concurrent rebuilds cannot replace the current active generation. No
frozen P3 file changes without separately approved change control.

### M2 — Deterministic Graph Projection and Verification

**Objective:** transform one frozen ArchitectureDocument into an isolated
candidate graph and independently prove its completeness before activation.

**Boundary:** owns P4-P1, key generation, property normalization, write batches,
read-back verification, immutable verification-result production and candidate
cleanup eligibility. It does not own lifecycle persistence, active-generation
selection or switching, query UX, RBAC/gateway or canonical semantics. M2 must
never activate a generation.

**Design:** load through frozen `load_published_document`; sort by canonical
logical ID; allowlist safe scalar/list properties with per-property/record caps;
write `ArchitectureEntity` nodes and `ARCH_RELATIONSHIP` edges scoped to exact
project/version/generation. The verifier independently queries all candidate
keys/endpoints/records, checks exact expected sets/counts/uniqueness/direction,
reconstructs canonical sorted records and digest, then returns an immutable
verification result. `ProjectionManifest` READY is written only after success;
M1 validates
that the result still belongs to the current lease-valid attempt and candidate,
then alone performs the PostgreSQL pointer switch. Failed generations remain
invisible and cleanup is bounded. A stale or superseded result is merely
cleanup-eligible and cannot affect the active generation.

**Files:**

| Action/path | Responsibility |
|---|---|
| CREATE `backend/platform/graph/projection.py` | Projection records, deterministic keys, normalization, expected digest and orchestration. |
| CREATE `backend/platform/graph/verification.py` | Independent read-back verifier and P4-P1 result/failure contract. |
| MODIFY `backend/platform/graph/neo4j.py` | Bounded MERGE/write, scoped enumeration, duplicate/endpoint/digest verification and generation deletion. |
| REUSE M1 `backend/platform/graph/lifecycle.py` and `persistence.py` activation port | Submit immutable verification results to M1; M2 performs no resource-state or active-pointer write. |
| MODIFY `backend/worker/graph_tasks.py` | `execute_graph_projection`, heartbeat, retry classification and cleanup tasks. |
| MODIFY `backend/platform/config.py` | Configurable node/edge batch sizes, metadata caps and cleanup grace. |
| CREATE `tests/p4/graph/test_{projection,verification,projection_worker,cleanup}.py` | Determinism, corruption, immutable verification handoff, retry/rebuild, stale/concurrent result behavior and active-generation preservation. |
| CREATE `tests/fixtures/p4/graph/` | Small, dense, Unicode, empty-relationship and historical ArchitectureDocument fixtures. |

**Batches:**

1. **Deterministic contract:** key/record/digest algorithms, metadata allowlist
   and configurable batches; benchmark initial 500-node/1,000-edge transactions
   and adjust only with recorded evidence.
2. **Writer/verifier:** candidate writes, manifest, exact read-back verifier,
   deliberate corruption tests and P4-P1 freeze.
3. **Worker/rebuild:** heartbeat/retry integration, verification-result handoff
   to M1, failed rebuild preservation, idempotent replay and reader-safe cleanup;
   boundary tests cover stale attempts and concurrent rebuild completion order.

**Acceptance / DoD:** identical input/version/config/projector produces identical
semantic records/digest; G1/G2 coexist; retries create no duplicates; missing or
extra keys, duplicate keys, missing/wrong endpoints, count/digest/scope/version
mismatch all fail closed; no candidate is query-visible; failed rebuild leaves
old active generation readable and preserves its existing `COMPLETED` or
`STALE` public state; cleanup cannot delete active; no unresolved or conflict
synthetic elements and no unsafe metadata/source/secrets enter Neo4j.
M2 cannot switch the active pointer or public lifecycle state; failed, stale or
late verification results are rejected by M1 without displacing the verified
generation.

### M3 — Graph Query and Exploration API

**Objective:** expose bounded deterministic graph capabilities and lifecycle
operations through delegated FastAPI APIs.

**Boundary:** owns P4-Q1, graph query ports/adapters/services, signed cursors,
FastAPI DTOs/routes/errors and API-level health. It consumes only verified active
generations selected by M1 and never queries candidates.

**Design:** authorize/project-match before PostgreSQL/Neo4j retrieval; accept
COMPLETED or exact-version STALE resources with active generation. Query templates
are fixed and parameters/kinds/directions allowlisted. Every Cypher predicate
includes project/version/generation. Stable ordering uses canonical entity/
relationship UUID then logical ID. Timeout/record limits are enforced both in
validation and driver transaction configuration. Dependency/dependent queries
traverse the approved non-containment relationship-kind allowlist, optionally
narrowed by the caller, and return every edge with its actual canonical kind and
direction; they never collapse results into `depends_on`. Canonical `contains`
navigation remains a separate capability. Rebuild delegates to M1 and requires
OWNER/ADMIN in FastAPI even after Express enforcement.

**Files:**

| Action/path | Responsibility |
|---|---|
| CREATE `backend/platform/graph/{dto,query,cursor,service}.py` | API records, query port/Neo4j adapter, HMAC cursor and application service. |
| CREATE `backend/api/v1/graph.py` | Status/rebuild/node/window/neighborhood/dependency/containment/path routes. |
| MODIFY `backend/api/v1/router.py` | Register graph routes. |
| MODIFY P4-owned `backend/platform/graph/dependencies.py` | Add graph query/service/driver/repository providers and delegated OWNER/ADMIN enforcement without modifying frozen P3 analysis DI. |
| MODIFY `backend/platform/config.py` | Query defaults/hard caps, timeout and cursor secret/TTL with production validation. |
| MODIFY `backend/platform/errors.py`, `backend/api/error_handlers.py` | Safe graph unavailable/not-ready/stale-cursor/limit/not-found errors. |
| CREATE `tests/p4/api/test_graph_api.py` | Delegation, role, validation, dependency-kind allowlist, containment separation and response/error contracts. |
| CREATE `tests/p4/graph/test_{query,cursor,query_isolation}.py` | Every approved dependency kind, actual-kind preservation, direction, containment exclusion, ordering, limits, cursor binding and scope isolation. |

**Batches:**

1. **Contract/limits:** DTOs, endpoint requests/responses, error taxonomy,
   cursor binding and P4-Q1 freeze.
2. **Query engine:** parameterized Neo4j templates, stable pagination,
   multi-kind dependency/dependent semantics, separate containment,
   neighborhood/path semantics and hard time/result caps.
3. **FastAPI integration:** routes, DI, status/rebuild, layered health, OpenAPI
   and negative authorization/isolation tests.

**Acceptance / DoD:** no raw Cypher input/path; unauthorized/project-mismatch is
rejected before retrieval; all scopes appear in every query; COMPLETED and exact
STALE active generations read; candidate/FAILED/PENDING do not; direction matches
canonical semantics; dependency traversal preserves the selected approved kinds
and excludes `contains`; hard limits and 5-second timeout cannot be bypassed;
truncation is explicit; cursors reject tampering, expiry or generation change;
Neo4j outage returns graph-specific degradation without breaking P3 APIs.

### M4 — Python/FastAPI Graph API Completion and Backend Integration

**Objective:** complete the Python/FastAPI graph API composition over frozen M1
and M3 contracts while preserving the completed Express browser security
boundary and ADR-0001 delegation model.

**Boundary:** Python-only. It owns FastAPI route assembly, delegated-context and
project/version validation, OWNER/ADMIN rebuild enforcement, DTO/error/OpenAPI
completion, graph health integration and backend contract tests. It adds no
Express implementation, browser authentication boundary, graph semantics,
Neo4j write logic or lifecycle authority.

**Design:** reuse the existing Python delegated-auth dependencies and exact
trusted service/actor/role/project/correlation headers. FastAPI authorizes scope
before retrieval, applies M3 limits and returns sanitized structured errors.
Rebuild audit remains authoritative in PostgreSQL attempts. React still calls
Express only; Python is never exposed directly to the browser.

**Proposed files (detailed M4 planning must verify exact existing paths):**

| Action/path | Responsibility |
|---|---|
| MODIFY `backend/api/v1/graph.py` | Complete status/read/rebuild route composition over M1/M3 services; no query semantics in the route layer. |
| MODIFY `backend/api/v1/router.py` | Register the Python graph API only. |
| CREATE or MODIFY P4-owned `backend/platform/graph/dependencies.py` | Compose graph lifecycle/query services using existing delegated auth and P4-owned DI; do not modify frozen P3 DI. |
| MODIFY `backend/platform/errors.py`, `backend/api/error_handlers.py` | Complete safe graph-specific error mapping without exposing infrastructure details. |
| CREATE `tests/p4/api/test_graph_integration.py` | Delegated-context, RBAC, scope, DTO/error/OpenAPI and M1–M3 integration tests. |
| REUSE / DO NOT MODIFY `express/**` | Existing Express platform/security/gateway implementation remains completed. Any missing browser-facing graph transport is outside P4 M1–M4 and requires explicit owner change control. |

**Batches:**

1. **Python API contract integration:** verify M1/M3 DTOs, route composition,
   delegated context and P4-D1 contract tests.
2. **Mutation/degradation:** OWNER/ADMIN rebuild, read-role behavior,
   correlation/audit inputs and safe graph error/degradation mapping.
3. **Backend integration freeze:** FastAPI OpenAPI/contract, health and M1–M3
   integration tests plus frozen P1–P3 and existing Express regression checks.

**Acceptance / DoD:** delegated requests fail closed on missing/invalid service,
actor, role, project or exact-version scope; all authorized project roles may
read; only OWNER/ADMIN rebuild; query caps and canonical kind/direction semantics
remain those of M3; `contains` remains separate; no credentials, stack traces or
infrastructure IDs leak; no Express file changes; existing platform/gateway
regressions remain green. A missing browser transport is reported as a separate
owner decision rather than bypassed with direct React-to-Python calls.

### M5 — React Architecture Explorer

**Objective:** deliver exact-version, lazy, accessible graph exploration while
preserving the existing Architecture Model page and design system.

**Boundary:** owns P4-U1, browser graph contracts/service, route/page, state,
ELK worker layout, React Flow canvas, inspector/list alternative and UI states.
It never edits graphs, performs architecture inference, sends Cypher, searches,
calls AI, or treats frontend visibility as authorization.

**Design:** new route (matched before the existing architecture route):
`#/projects/:projectId/repositories/:repositoryId/analyses/:analysisId/architecture/:versionId/graph`.
`ArchitectureModelPage` constructs this link from the exact loaded Architecture
Version `id`. The explorer retains that route `versionId` as immutable page
identity, loads that exact version, and validates its returned analysis, project
and repository IDs against the route before requesting graph status or data. It
must never resolve or substitute a current/latest version, including when newer
published versions exist for the same repository. Expansion requests are
serialized/deduplicated by entity/query cursor; state deduplicates canonical IDs
and refuses additions above 300/600 with explicit feedback. Dependency controls
use the approved non-containment relationship kinds and display actual returned
edge kinds; containment is a separate control. ELK runs only in a Web Worker on
sorted DTOs. Node selection never relayouts existing nodes unless the dataset
changes. A structured list mirrors loaded nodes/edges and supports keyboard
navigation, focus and inspector selection.

**Files:**

| Action/path | Responsibility |
|---|---|
| CREATE `frontend/src/pages/ArchitectureExplorerPage.jsx` | Explicit route-version orchestration, route-context validation, status/degraded/rebuild states and no current-version substitution. |
| CREATE `frontend/src/contracts/graphContracts.js` | Lifecycle, canonical dependency-kind allowlist, separate containment, direction, DTO guards/labels and approved limits. |
| CREATE `frontend/src/services/graphService.js` | Central `apiClient` calls carrying the explicit route `versionId`; never call a current/latest graph alias. |
| CREATE `frontend/src/hooks/useArchitectureGraph.js` | Exact immutable version-bound load/expand/dedup/cursor/selection/retry state; reject mismatched-version responses. |
| CREATE `frontend/src/workers/graphLayout.worker.js` | Deterministic ELK layout off main thread. |
| CREATE `frontend/src/components/graph/{GraphCanvas,GraphControls,GraphInspector,GraphStatusBanner,GraphListView}.jsx` | React Flow view, navigation/filter controls, details, status and accessible alternative. |
| CREATE `frontend/src/styles/graph.css` | Existing-token dark responsive styles and focus states. |
| MODIFY `frontend/src/App.jsx` | Most-specific route carrying `versionId` and stylesheet. |
| MODIFY `frontend/src/pages/ArchitectureModelPage.jsx` | Add “Explore Graph” entry containing the loaded version's explicit ID; preserve all P3 views/fallbacks. |
| MODIFY `frontend/package.json` | Pin verified compatible `@xyflow/react` and `elkjs` patches after M5 B1 spike. |
| CREATE `frontend/tests/component/{ArchitectureExplorerPage,GraphCanvas,useArchitectureGraph}.test.jsx` | Explicit-version routing/context checks, older-version retention, dependency kinds, state, caps, keyboard, layout stability, errors and interactions. |
| MODIFY `frontend/tests/coverageCompletion.test.js` | Route/service static regression only where current convention requires. |

**Batches:**

1. **Compatibility/contracts/shell:** verify React 18/Vite 8-compatible package
   patches, define P4-U1 as a consumer mapping of stable P4-Q1 DTOs, and define
   the dependency-kind UI contract, worker protocol, route and empty component
   shell. Once the relevant P4-Q1 query DTOs are stable, only package
   compatibility, route/component shell and independent layout-worker work may
   proceed before P4-D1 freezes. Service/hook API integration waits for P4-D1;
   M5 must not invent or independently redefine API request/response contracts.
2. **Explorer workflow:** canvas/layout, inspector, controls, lazy expansion,
   exact-version stale/current handling and accessible list.
3. **Hardening:** loading/empty/partial/failed/degraded/retry/rebuild UX,
   keyboard/focus/responsive tests, production build and P3 page regression.

**Acceptance / DoD:** initial 50/100 query; no more than 300/600 rendered;
explicit expansion and partial counts; exact version never silently changes;
deep links and refresh retain the explicit `versionId`; an older explicitly
selected version remains selected when a newer repository version exists; route
context mismatch fails closed rather than substituting another version;
COMPLETED/STALE distinctions visible; failed/PENDING/RUNNING/degraded states are
honest; last active graph remains usable during rebuild; no selection jitter or
main-thread ELK; keyboard-accessible nodes/controls/list with visible focus;
dependency filters preserve approved kinds and labels while containment remains
separate; P3 Architecture Model page remains functional; no direct
FastAPI/Neo4j calls.

### M6 — Integration, Testing, Performance and Evaluation 2

**Objective:** prove the complete vertical slice, failure/recovery behavior,
limits, accessibility and frozen-regression safety using real infrastructure.

**Boundary:** owns phase-level fixtures, integration/E2E/performance/security/
operational evaluation and final evidence. It fixes only defects found within
approved P4 scope and does not add product capability.

**Files:**

| Action/path | Responsibility |
|---|---|
| CREATE `tests/p4/integration/test_{postgres_neo4j_projection,celery_projection,graph_query_api,rebuild_recovery}.py` | Real infrastructure integration. |
| CREATE `tests/p4/e2e/test_p4_vertical_slice.py` | Published model through verified graph/query. |
| CREATE `tests/p4/performance/test_p4_capacity.py` | Projection/query/cursor/canvas-size benchmark evidence. |
| CREATE/EXTEND `tests/fixtures/p4/graph/` | Multi-project, two-version, dense, cyclic, disconnected and corrupted candidates. |
| REUSE existing Express regression/integration suites | Verify completed JWT/RBAC/delegation behavior remains unchanged; do not add graph gateway implementation or tests that assume unapproved Express routes. |
| CREATE `frontend/tests/component/ArchitectureExplorerAccessibility.test.jsx` | Keyboard/focus/list/degraded-state accessibility. |
| MODIFY `.github/workflows/ci.yml` | Add Neo4j/RabbitMQ services and Python P4 integration plus Express/frontend jobs; retain existing gates. |
| MODIFY `PROJECT_CONTEXT.md` during implementation | Record actual evidence/status only; no separate report by default. |

**Batches:**

1. **Automated integration:** real PostgreSQL/Neo4j lifecycle, worker/RabbitMQ,
   projection corruption/idempotency/concurrency/isolation/history/query tests.
2. **Product/security/performance:** existing Express boundary regression,
   FastAPI delegated RBAC, frontend interactions only through an approved
   existing browser transport, accessibility, hard caps/timeouts and
   reference-hardware benchmarks.
3. **Operational Evaluation 2:** outage, lease loss, failed rebuild, remove and
   rebuild Neo4j, full vertical slice, P1–P3 regressions and freeze evidence.

#### M6 evaluation matrix

| Scenario | Expected result | Required evidence |
|---|---|---|
| Publish two versions | Both eventually verified; older becomes STALE and exact-readable. | PostgreSQL/Neo4j assertions and API output. |
| Open older explicit version while newer repository version exists | Explorer route, status, queries and refresh remain bound to the requested Architecture Version ID; no current-version substitution. | Approved browser-transport/component/E2E route and response assertions. |
| Mixed canonical relationship kinds | Dependency/dependent queries preserve every selected non-containment kind and direction; `contains` appears only in containment or separately requested generic neighborhood. | Query, Python API, approved browser-transport and component assertions. |
| Replay same attempt/task | No duplicate semantic nodes/edges; deterministic digest. | Repeated real projection and counts/digest. |
| Concurrent auto/manual requests and out-of-order completion | One active attempt; requests coalesce/idempotently respond; M1 rejects stale/late verification results and only the current verified candidate can switch the pointer. | Transaction/concurrency test. |
| Corrupt/delete/add candidate data | Independent verifier fails; pointer never switches. | Parameterized corruption tests. |
| Failed rebuild with active G1 in `COMPLETED` or historical `STALE` state | G1 remains exact-version readable, the public state is unchanged, and failed G2 cannot clear the pointer or turn a STALE resource into FAILED. | Lifecycle assertions plus API reads during/after failed G2 for both public states. |
| Cross-project/version/generation IDs | No traversal or timing-visible retrieval across scope. | Negative query/API tests. |
| Oversized/deep/slow query | 422 for invalid request or bounded explicit truncation/timeout <=5s. | API and Neo4j transaction timeout tests. |
| OWNER/ADMIN vs other roles | Only OWNER/ADMIN rebuild; all members read; outsiders denied first. | FastAPI delegated-RBAC tests plus regression of the completed Express authorization boundary; no new Express graph route is assumed. |
| RabbitMQ/worker interruption | Durable attempt is republished/recovered without duplicate activation. | Worker/reconciler logs and DB assertions. |
| Neo4j unavailable | Graph reports degraded/unavailable; canonical P3 page/API remain available. | Health/API/E2E evidence. |
| Delete Neo4j volume/projection | Reconcile/rebuild restores equivalent verified graph from PostgreSQL only. | Before/after digest/count/API comparison. |
| Explorer 50/100 then expansion | Lazy loading, deterministic layout, caps 300/600, explicit partial state. | Component/E2E assertions and screenshots if manually reviewed. |
| Keyboard/accessibility | Complete selection/navigation/list alternative and visible focus. | RTL automated checks plus manual keyboard review. |
| Frozen regression | P1–P3, Express, frontend and builds remain green. | Exact command results recorded here. |

**Performance gates:** every graph transaction obeys the 5-second hard timeout;
initial API defaults remain 100 nodes/200 edges or smaller and frontend starts
at 50/100. M6 records projection throughput and p50/p95 query/layout timings on
identified reference hardware for small, representative and capacity fixtures.
No unapproved absolute projection-time promise is invented; phase freeze
requires no superlinear regression or resource-limit failure at approved P3
model caps, with any practical capacity limitation explicitly approved.

**Acceptance / DoD:** all matrix scenarios pass with recorded evidence; real
Neo4j/PostgreSQL/RabbitMQ paths are exercised; no mocked-only closure; automated
security/isolation/corruption tests pass; manual outage/remove-rebuild and
accessibility checks pass; full existing suites/static checks/builds pass; P4
can be frozen without accepted hidden blocker.

## 7C. Detailed M2 Plan — Deterministic Graph Projection and Verification

**Status: COMPLETE THREE-BATCH PLAN — OWNER APPROVED; IMPLEMENTATION NOT
STARTED.** This plan was prepared from the current `feature_mannan` worktree,
the approved P4 Baseline v1, frozen M1/P4-L1/P4-S1/P4-W1 implementation and the
actual frozen P3 Architecture Model. Approval establishes all three batches as
the implementation baseline, but the owner's current instruction is to perform
no implementation until a separate start instruction. P4-P1 and measured
operational limits retain their recorded post-Batch-1 approval gate.

### A. Verified repository findings

1. Frozen M1 already provides the complete control-plane boundary M2 needs:
   PostgreSQL resources and attempts, identifier-only `ProjectionWorkPayload`,
   exclusive leases, heartbeats, three-execution retry accounting, stale-result
   rejection, immutable `VerificationReceipt`, and transactional activation in
   `GraphProjectionLifecycle.activate`. M2 must not add a second lifecycle or
   write `active_generation_id` itself.
2. `SqlAlchemyPublishedArchitectureSource.load_exact(version_id, project_id)`
   is a P4-owned adapter that delegates to the frozen P3 exact published-document
   loader. It returns the immutable `ArchitectureDocument`; no P3 repository,
   persistence or API modification is necessary.
3. The frozen model already guarantees deterministic ordering, unique scoped
   logical IDs, referential integrity, legal relationship directions, complete
   evidence coverage, bounded counts and a 128 MiB canonical payload cap. M2
   revalidates its projection boundary but does not reinterpret those semantics.
4. Stable public P3 entity and relationship UUIDs are not fields on
   `ArchitectureDocument`; P3 derives them with the existing pure
   `architecture_resource_id(version_id, record_type, logical_id)` function.
   M2 may reuse that function read-only and stores the derived UUID separately
   from the canonical logical ID and the generation-scoped Neo4j key.
5. `Neo4jInfrastructure` owns driver creation, connectivity and the three
   required uniqueness constraints for generation, node and relationship keys.
   Repository inspection found that frozen M1 used
   `ArchitectureProjectionGeneration` instead of the approved sole
   `ProjectionManifest` label. The owner authorized a narrow change-control
   amendment; live inspection proved zero manifest/entity/relationship data,
   and the implementation now fails closed if legacy manifest data exists,
   removes the obsolete empty constraint, creates/verifies
   `projection_manifest_generation_key_unique` on
   `ProjectionManifest.generation_key`, and supports no alias label. The
   corrected schema awaits owner re-freeze acceptance. No scope indexes or
   candidate data exist yet.
6. Celery already routes `stacksense.execute_graph_projection` to
   `graph.projections`, but no task is registered and dispatch remains disabled.
   The current systemd graph worker consumes only `graph.maintenance`; M2 needs
   a separate execution-queue consumer before capability heartbeats can become
   ready.
7. The owner retained M1 source, lifecycle, worker, projector and graph-schema
   version `1.0.0`; Neo4j Community `5.26.33` with Python driver `6.4.1` is
   verified. The manifest correction is an implementation repair to that
   approved physical schema, not a logical schema-version bump. M2 must emit
   these exact values and may not silently change them.
8. No PostgreSQL schema change is required for M2. The current M1 attempt rows
   already persist expected/actual counts and all three expected/actual digest
   pairs needed for activation and audit.

### B. Objective, ownership and exclusions

M2 converts one exact published `ArchitectureDocument` into one isolated Neo4j
candidate generation, independently reads that generation back, and returns a
P4-P1 `VerificationReceipt` to M1. Construction success is never activation.

M2 owns deterministic projection records and digests; generation-scoped graph
keys; safe property normalization; bounded idempotent writes; write fencing;
exact endpoint resolution; independent read-back verification; safe failure
classification; and bounded cleanup of terminal, inactive candidates.

M1 remains the sole owner of public/internal lifecycle state, attempt and lease
validity, retry eligibility, actor audit, current-attempt validation and the
transactional PostgreSQL active-generation pointer switch. M2 does not modify
P1-P3, invent canonical entities or relationships, expose candidates, perform
query/traversal work, add Express code, or implement M3-M6 behavior. Unresolved
relationships and conflicts are summarized for completeness but never become
synthetic graph nodes or edges.

### C. Contracts and end-to-end data flow

The executor follows this exact boundary:

1. Celery validates an exact P4-W1 payload with `extra=forbid`; malformed or
   version-incompatible deliveries are safely rejected without graph access.
2. A short PostgreSQL transaction calls frozen M1 `acquire`. A duplicate or
   ineligible delivery receiving no lease is an acknowledged no-op and consumes
   no additional execution.
3. A second short read transaction obtains the current resource/attempt and
   exact P4-S1 document. M2 verifies payload, resource, attempt, document IDs,
   source digest, schema version, projector version, contract version and all
   five source counts before transformation.
4. The deterministic mapper produces an immutable `ProjectionPlan`. No
   PostgreSQL transaction remains open while Neo4j work runs.
5. The Neo4j adapter claims `ProjectionManifest` with a lease-derived fence and
   resets only an interrupted inactive `BUILDING` generation when ownership has
   changed. Every bounded mutation transaction first obtains the manifest node
   write lock and revalidates current fence/state under that same held lock as
   specified in E; a predicate-only query is forbidden.
6. Between batches, the executor renews the M1 lease in a fresh PostgreSQL
   transaction. Lease loss stops further work; it never manufactures a failure
   result using a stale token.
7. The verifier opens a new Neo4j read session and derives actual records from
   Neo4j rather than writer counters. Only an exact match conditionally changes
   `ProjectionManifest` from `BUILDING` to `READY` and removes its fence, inside
   the same manifest-locked transaction that revalidates ownership.
8. M2 translates the immutable verification result into the already frozen M1
   `VerificationReceipt`. A fresh PostgreSQL transaction calls M1 `activate`;
   M1 alone accepts or rejects it and switches the active pointer.
9. A stale/superseded receipt or failed candidate never affects the previous
   active generation. Later bounded cleanup is allowed only after PostgreSQL
   proves the generation terminal and inactive.

`BUILDING` and `READY` are private Neo4j manifest states, not new public
projection lifecycle values. The public vocabulary remains exactly PENDING,
RUNNING, COMPLETED, FAILED and STALE; M2 emits no public event vocabulary.

### D. Deterministic projection contract

#### D1. Identity and encoding

All UUIDs are lower-case canonical strings. All text is NFC-normalized UTF-8.
NUL is forbidden in every key component. The approved formulas remain exact:

```text
node_key = SHA-256(project_id || NUL || architecture_version_id || NUL ||
                  generation_id || NUL || entity_logical_id)
edge_key = SHA-256(project_id || NUL || architecture_version_id || NUL ||
                  generation_id || NUL || relationship_logical_id)
```

The candidate manifest uses the same unambiguous framing without a record ID:

```text
generation_key = SHA-256(project_id || NUL || architecture_version_id || NUL ||
                        generation_id)
```

Keys are 64 lower-case hexadecimal characters. G1 and G2 therefore coexist
without overwriting or modifying each other. Each node separately stores
`architecture_entity_id` (the stable P3 UUID), `logical_id` and
`projection_key`; each relationship similarly stores
`architecture_relationship_id`, `logical_id` and `projection_key`. Neo4j
element IDs are never application identifiers.

#### D2. Generation manifest

One `ProjectionManifest` node per generation holds only projection control and
summary data: generation key; project/version/generation IDs; resource/attempt
IDs for audit; source content and architecture-schema versions; graph schema,
contract and projector versions; `BUILDING|READY`; the five expected and
verified source counts defined in D6; expected and verified
key-set/endpoint/payload digests; independently derived expected and asserted
actual evidence-association, unresolved and conflict summary digests; a
monotonic operational lock epoch; and the temporary lease-fence hash.
Operational lock/timestamp properties are excluded from semantic digests. No
raw lease token, credential, source text, evidence payload, unresolved
descriptor or conflict detail is stored. `ProjectionManifest` is the only
manifest label; `ArchitectureProjectionGeneration` is not an alias or an
additional label.

#### D3. ArchitectureEntity nodes

Every canonical entity maps one-to-one to label `ArchitectureEntity` with this
fixed core property set: scope IDs, generation key, projection key, stable P3
UUID, logical ID, semantic signature, canonical kind, name, namespace list,
fact status and sorted evidence logical IDs. Source-IR keys remain in the
canonical PostgreSQL model and are not duplicated into Neo4j. The mapper does
not add kind-specific labels.

The initial versioned metadata allowlist is derived from actual P3 outputs:

- string: `application_namespace`, `runtime_role`, `source_root`, `framework`,
  `architectural_role`, `qualified_name`, `method`, `path`, `handler`,
  `mount_path`, `declared_path`, `database_engine`, `external_kind`,
  `unresolved_reason`, `infrastructure_kind`, `dependency_name`,
  `identity_anchor`, `promotion_rule_id`;
- boolean: `manifest_declared`, `source_referenced`, `usage_evidence`;
- list of strings: `role_inference_signals`, `transformation_rule_ids`.

Each accepted value becomes a flat Neo4j property named `meta__<canonical_key>`;
Neo4j map-valued properties are never attempted. Unknown keys, wrong types,
NUL/control characters, non-finite numbers, nested structures or values above
the approved caps fail closed with a metadata-contract diagnostic. Nothing is
silently truncated, stringified or copied wholesale.

Value validation is field-semantic and rechecks the frozen P3 representation.
`source_root` is the only filesystem/repository path in this allowlist: P3
derives it from normalized evidence paths as a forward-slash,
repository-relative application root. M2 accepts only non-empty NFC UTF-8
relative components; it rejects a leading `/`, Windows drive prefix, `\\` or
`//` UNC/network prefix, URI/file scheme, backslash, empty or `.`/`..`
component, NUL, C0/C1 control character and any value matching P3's host-path
guards. It does not rewrite an unsafe value into a safe-looking one.

Actual frozen P3 output uses `path`, `mount_path` and `declared_path` for
canonical HTTP route paths, not filesystem paths: `normalize_route_path`
produces a leading `/`, forward slashes and optional meaningful trailing slash.
For these three fields M2 therefore accepts only that exact static-route shape;
the leading `/` is route syntax and is not treated as a POSIX filesystem root.
It rejects drive/UNC prefixes, backslashes, URI/file schemes, NUL/control
characters, `.` or `..` segments and host-root signatures such as `/home/`,
`/Users/`, `/var/`, `/tmp/`, `/etc/`, `/root/`, `/usr/` and `/opt/`. No
percent-decoding or normalization is performed to rescue a rejected value.
Violations use the stable safe code `projection_metadata_invalid`; logs/errors
identify only the field and rule, never the rejected value.

#### D4. ARCH_RELATIONSHIP relationships

Every resolved canonical relationship maps one-to-one to a directed
`ARCH_RELATIONSHIP` from the exact canonical source node to the exact target
node. Properties are the scope IDs, generation key, projection key, stable P3
UUID, logical ID, canonical relationship kind, status, source/target logical
IDs, source/target projection keys, sorted evidence IDs and allowlisted
`transformation_rule_ids`. Source-IR keys remain in PostgreSQL. Relationship
type and direction are never inferred from display names and never reversed for
query convenience.

The mapper resolves endpoints from the expected entity logical-ID map before
writing. A missing endpoint, duplicate logical ID, key collision, illegal kind
or direction mismatch is a permanent projection-contract failure. Unresolved
relationships and conflicts produce no node or edge. Their exact canonical
record digests, counts and evidence-association digest remain in the manifest so
verification can prove that the intentional exclusion contract was applied to
the complete source document.

#### D5. Canonical serialization and digests

Digest input uses recursive NFC normalization, lower-case UUIDs, JSON objects
with lexicographically sorted keys, arrays already sorted by canonical record
key, UTF-8, `ensure_ascii=false` and separators `(',', ':')`. No timestamps,
Neo4j element IDs, fence values or map iteration order participate.

- **Key-set digest:** SHA-256 of
  `{node_keys:[sorted], relationship_keys:[sorted]}`.
- **Endpoint digest:** SHA-256 of sorted records
  `{relationship_key, kind, source_key, target_key}`. Source precedes target, so
  reversing an edge changes the digest.
- **Payload digest:** SHA-256 of the semantic generation header, full sorted
  projected node records, full sorted projected relationship records, source
  counts and the evidence-association/unresolved/conflict summary digests.
- **Summary digests:** SHA-256 of canonical records independently derived from
  the exact immutable `ArchitectureDocument`: evidence logical ID plus sorted
  owning entity/relationship logical IDs; each unresolved-relationship logical
  ID plus kind/status and its sorted evidence IDs; and each conflict logical ID
  plus conflict type/subject key and sorted evidence IDs. Sensitive evidence
  payloads, target descriptors, conflict details and source text are excluded.

Expected summary records, counts and digests come only from the immutable
document/plan and are computed before Neo4j access. The writer stores only the
resulting assertions on `ProjectionManifest`. A fresh verifier session reads
those assertions but never uses them to construct expected values. It
independently reconstructs every actual projected node and relationship record,
recomputes graph key/endpoint/payload digests, and compares the manifest claims
against both independently derived expected summaries and independently read
actual graph data. Missing, extra or mismatched summary fields fail
verification. Because evidence/unresolved/conflict detail is intentionally not
projected, their manifest properties remain assertions under verification, not
an authoritative source or substitute for node/edge read-back. The algorithms
are pure and golden-vector tested across processes, input permutations, Unicode
and empty collections.

#### D6. Frozen five-count boundary

The exact M1 `ProjectionCounts` fields and their P3 sources are:

| M1 field | Frozen P3 header field | Measure |
|---|---|---|
| `entities` | `ArchitectureVersionRecord.entity_count` / `ArchitectureVersionModel.entity_count` | Number of canonical `ArchitectureDocument.entities`; each becomes one `ArchitectureEntity`. |
| `relationships` | `ArchitectureVersionRecord.relationship_count` / `ArchitectureVersionModel.relationship_count` | Number of resolved canonical `ArchitectureDocument.relationships`; each becomes one `ARCH_RELATIONSHIP`. |
| `evidence` | `ArchitectureVersionRecord.evidence_count` / `ArchitectureVersionModel.evidence_count` | Number of canonical `ArchitectureDocument.evidence` records; evidence is summarized, not projected as nodes/edges. |
| `unresolved` | `ArchitectureVersionRecord.unresolved_relationship_count` / `ArchitectureVersionModel.unresolved_relationship_count` | Number of `ArchitectureDocument.unresolved_relationships`; these are excluded from graph edges and summarized. |
| `conflicts` | `ArchitectureVersionRecord.conflict_count` / `ArchitectureVersionModel.conflict_count` | Number of `ArchitectureDocument.conflicts`; these are excluded from graph elements and summarized. |

`PublishedArchitectureHeader.counts` maps those five persisted P3 fields into
`ProjectionCounts`; M1 copies them into the attempt's five
`expected_*_count` columns. Before planning or writing, M2 loads the exact
document and requires each header value to equal the corresponding tuple
length, with unresolved relationships and conflicts counted one canonical
record each. It also rechecks the frozen P3 maxima and content digest.

`ProjectionManifest` stores explicit expected and asserted-actual values for all
five fields. The verifier derives expected values from the exact document, then
enumerates actual entity/relationship graph records. For evidence, unresolved
and conflicts—whose raw records are deliberately absent from Neo4j—it verifies
the manifest's asserted count and summary digest against the independently
derived canonical source records; only after all checks succeed may those three
verified values populate `actual_counts`. `VerificationReceipt` carries the
unchanged frozen `expected_counts` and all-or-none `actual_counts`; it adds no
count fields and represents a failed/incomplete verification with
`actual_counts=None` unless a complete safe set is available.

### E. Neo4j storage, writes and concurrency

M2 adds a narrow projection store; no caller supplies Cypher. Every statement is
a fixed `LiteralString` with parameters, an explicit transaction timeout and
exact project/version/generation predicates.

The candidate claim stores `SHA-256(lease_token)` as an ephemeral fence; the raw
unpredictable token never enters Neo4j, logs or task payloads. A predicate match
alone is insufficient under Neo4j's default read-committed isolation. Every
claim/fence-replacement, reset, write, delete and finalize transaction must first
obtain the exclusive node write lock on the exact `ProjectionManifest`, then
read and validate `BUILDING`, generation scope and fence while that lock remains
held, perform its one bounded candidate mutation, and commit or roll back as one
explicit transaction.

The fixed lock query uses supported Neo4j Community semantics: after matching
the unique `generation_key`, it updates a manifest-owned monotonic
`lock_epoch = lock_epoch + 1`. The right-hand side directly depends on the
property being read, which makes Neo4j acquire the manifest node write lock
before that read; node-property write locks are held until transaction end. The
adapter then reads state/fence and performs the bounded mutation in the same
explicit driver transaction. All competing mutation and fence-replacement
paths acquire this same manifest lock first and use the same lock ordering.
Temporary/dummy lock properties are not relied upon, no APOC/Enterprise lock
primitive is assumed, and `lock_epoch` is operational and excluded from every
semantic digest.

Consequently, if a replacement transaction locks first, it commits the new
fence and the old worker later observes a mismatch under lock and rolls back
without mutation or receipt. If the old transaction locks first, replacement
blocks; the old mutation may legitimately commit before replacement, after
which replacement acquires the lock, installs its fence and boundedly resets/
rebuilds the still-inactive candidate. There is no ordering in which a stale
mutation commits after a completed fence replacement. Lease loss/fence mismatch
stops without submitting either stale success or stale failure. `READY` is
immutable and never reset; every rebuild of a verified generation uses a new
generation.

Write order is manifest, nodes, then relationships. Node batches use
`UNWIND` plus `MERGE` on `projection_key` and replace the complete allowlisted
property map. Relationship batches first match both endpoint keys in the exact
scope, then `MERGE` the directed relationship and replace its properties. Every
batch returns matched/written counts; zero-fence, missing endpoint or count
mismatch aborts. Retrying the same deterministic generation creates no
duplicates. A replacement execution first fences the old worker, then deletes
the interrupted candidate's relationships and nodes in bounded pages before
rebuilding; it never uses unbounded `DETACH DELETE`.

The corrected target uniqueness constraints are mandatory for
`ArchitectureEntity.projection_key`, `ARCH_RELATIONSHIP.projection_key` and
`ProjectionManifest.generation_key`. Efficient exact-scope enumeration also
requires additive composite RANGE indexes on
`ArchitectureEntity(project_id, architecture_version_id, generation_id)`,
`ARCH_RELATIONSHIP(project_id, architecture_version_id, generation_id)` and
`ProjectionManifest(project_id, architecture_version_id,
generation_id)`. M2 verifies their exact shape at executor startup. These are
fixed labels/type and access paths; no other manifest label is permitted.
The owner-approved M1 amendment corrected the manifest uniqueness constraint
while retaining `GRAPH_SCHEMA_VERSION = 1.0.0`; real Neo4j verification passed.
The owner also approved these three composite RANGE indexes as additive physical
access paths, subject to exact Neo4j Community compatibility verification during
Batch 1. They do not change labels, relationship types or graph semantics.

### F. Independent verification and P4-P1

Verification never trusts `MERGE` summaries. In a fresh read session it:

1. finds exactly one `ProjectionManifest` by generation key and checks exact project,
   version, generation, source, contract, schema and projector fields;
2. enumerates all scoped nodes and relationships in deterministic key pages;
3. checks actual counts and `count == count(DISTINCT projection_key)` in addition
   to relying on constraints;
4. compares exact sorted key sets, detecting missing and extra records;
5. proves every relationship endpoint exists, is an expected node in the same
   generation, has the expected source-to-target direction and canonical kind;
6. rejects unexpected labels/types, scope leakage, duplicate P3 UUID/logical ID,
   unsupported properties and missing/extra/mismatched manifest summary fields;
7. independently re-derives expected evidence-association, unresolved and
   conflict records/counts/digests from the exact source plan, reconstructs
   actual node/edge records from Neo4j, and recomputes all three P4-P1 digests
   without using manifest assertions as expected inputs; and
8. conditionally changes the still-fenced manifest from `BUILDING` to `READY`,
   stores the verified summaries and removes the fence only if every check
   passes.

Missing entities, missing endpoints, duplicate keys, extra records, count,
direction, schema/projector/source/scope or digest mismatch always fails
projection. There is no partial success and no silent omission. A failed check
returns `verified=false` with safe canonical failure code/message and all
available expected/actual summaries. M1 records the result and preserves any
previous active generation; M2 never converts the result into lifecycle state.

The frozen `VerificationReceipt` is P4-P1's external envelope. M2-owned internal
records may be richer, but their translation must populate every frozen field
exactly, include the current lease owner/token only at the M1 call boundary, and
never expose that token elsewhere. P4-P1 freezes after Batch 2 corruption and
activation-boundary review.

### G. Failure, retry, cleanup and observability

Failure classes are deterministic:

- **permanent source/contract:** source missing, scope/digest/count/version
  mismatch, unsupported schema/projector, key collision, metadata/cap violation;
- **verification failure:** missing/extra/duplicate record, endpoint/direction/
  scope/count/digest/manifest mismatch;
- **transient infrastructure:** Neo4j connectivity, acquisition, transaction
  timeout, broker/process interruption or retryable PostgreSQL error; and
- **stale ownership:** lease/fence loss or superseded attempt, which stops as a
  safe no-op and cannot submit a stale success.

Stable safe codes are `projection_source_missing`,
`projection_source_mismatch`, `projection_contract_mismatch`,
`projection_capacity_exceeded`, `projection_metadata_invalid`,
`graph_schema_incompatible`, `graph_write_unavailable`,
`graph_write_incomplete`, `graph_verification_scope_mismatch`,
`graph_verification_count_mismatch`, `graph_verification_key_mismatch`,
`graph_verification_endpoint_mismatch`, `graph_verification_payload_mismatch`
and `graph_internal_error`. Messages are bounded and sanitized; driver text,
Cypher, credentials, tokens, metadata values, logical IDs and source paths are
not logged as failure detail.

Pre-verification execution failures use frozen M1 `record_failure`; completed
verification (success or failure) uses `activate(receipt)` so M1 performs its
authoritative current-attempt check. M2 does not invoke Celery autoretry:
reconciliation redispatches the persisted RETRYING attempt after M1's approved
backoff, retaining the same generation. The initial try plus two retries remains
unchanged.

An internal identifier-only cleanup task may delete only a known generation
whose PostgreSQL attempt is terminal/superseded, grace has elapsed and resource
active generation differs. It rechecks eligibility before each bounded edge,
node and manifest deletion page. It cannot discover or delete by unconstrained
Neo4j scan, cannot delete a COMPLETED/STALE active generation and treats any
state race as a no-op. Global retention policy remains M1/P4 baseline; M2 only
implements the safe primitive and eligibility enforcement.

Metrics/logs are aggregate and correlation-safe: transform/write/verify
duration, batch count, retry/execution number, expected/actual record counts,
failure code, generation outcome and cleanup count. No high-cardinality logical
IDs or sensitive values are metric labels. Candidate readiness remains separate
from core health.

### H. Resource limits and security

The frozen P3 maxima remain hard upper bounds: 25,000 entities, 50,000
relationships, 75,000 evidence records, 10,000 unresolved relationships, 5,000
conflicts and 128 MiB canonical source payload. M2 rechecks them and never
truncates.

The following are measurement candidates only and are **not approved production
defaults**: 500 nodes and 1,000 relationships per transaction; a 30-second
per-query timeout; 1,000-record cleanup pages; 24-hour cleanup grace; metadata
caps of 64 UTF-8 bytes per key, 2 KiB per string, 64 list values, 16 KiB per
metadata record and 1 MiB total projected properties per node/relationship; and
any worker-memory or throughput threshold derived from them. Batch 1 benchmarks
all candidates against small, dense and maximum representative fixtures and
reports raw evidence plus a recommendation. It does not freeze those values.
The coding agent may not treat them as configuration defaults, and Batch 2
writer implementation may not begin/freeze operational limits until the owner
explicitly approves or revises the measured set. Performance optimization may
change batching/streaming only; it cannot weaken canonical P3 source maxima,
truncate metadata, skip records or silently omit evidence.

Neo4j receives no raw source code, evidence literal payload, credential, secret,
absolute host path, lease token or arbitrary nested metadata. The worker has no
arbitrary Cypher API. Values are parameters; labels/types are constants. Scope
is present in every record and query. Driver credentials remain `SecretStr` and
the execution worker uses the existing isolated queue/prefetch model.

### I. Exact file-change inventory

| Action | Path | M2-owned reason |
|---|---|---|
| CREATE | `backend/platform/graph/projection.py` | Immutable projection records/plan, generation/node/edge keys, P3 UUID derivation, strict metadata normalization and canonical digest algorithms. |
| CREATE | `backend/platform/graph/projection_store.py` | Narrow Neo4j port and official-driver adapter with fixed bounded claim/reset/write/enumerate/finalize/delete operations and additive scope-index verification. |
| CREATE | `backend/platform/graph/verification.py` | Independent read-back verifier, corruption taxonomy and internal result-to-frozen-`VerificationReceipt` translation. |
| CREATE | `backend/platform/graph/executor.py` | P4-W1 execution coordinator, short PG units of work, source validation, lease checkpoints, failure classification, activation handoff and cleanup eligibility. It orchestrates M2 only; lifecycle remains M1. |
| MODIFY | `backend/platform/graph/neo4j.py` | The owner-approved M1 amendment already corrected the sole manifest label/constraint at graph schema `1.0.0`. M2 may add only the narrow reviewed driver/session and approved composite-index bootstrap/verification surface; projection semantics remain M2-owned. |
| MODIFY | `backend/platform/graph/dependencies.py` | Compose M2 mapper/store/verifier/executor through P4-owned DI without touching frozen analysis DI. |
| MODIFY | `backend/platform/graph/__init__.py` | Export only reviewed M2 public ports/contracts. |
| MODIFY | `backend/worker/graph_tasks.py` | Register exact `execute_graph_projection`, lease-checkpoint execution, safe summaries and identifier-only cleanup task. |
| MODIFY | `backend/worker/celery_app.py` | Route cleanup to `graph.maintenance`; execution routing already exists and is preserved. |
| MODIFY | `backend/platform/config.py`, `.env.example` | Typed bounded batch/timeout/metadata/cleanup settings; dispatch default remains fail-closed until the execution worker is deployed. Local `.env` is not a planning artifact. |
| CREATE | `ops/systemd/stacksense-celery-graph-projection-worker.service` | Dedicated `graph.projections` consumer with existing concurrency/prefetch settings; the frozen M1 maintenance worker remains separate. |
| CREATE | `tests/p4/graph/test_projection.py` | Golden keys/digests, order/Unicode/empty determinism, mapping, allowlist, limits and no-synthetic-element tests. |
| CREATE | `tests/p4/graph/test_projection_store.py` | Fixed-query/label/index shape, batching, idempotency, manifest-lock serialization, stale fencing, endpoint and bounded cleanup adapter tests. |
| CREATE | `tests/p4/graph/test_verification.py` | Independent missing/extra/duplicate/scope/direction/endpoint/version/digest corruption matrix. |
| CREATE | `tests/p4/graph/test_projection_worker.py` | Payload/acquire/source/heartbeat/retry/receipt/stale/concurrent/cleanup task behavior and queue isolation. |
| CREATE | `tests/p4/integration/test_graph_projection_neo4j.py` | Real Community `ProjectionManifest` constraint/index compatibility, candidate coexistence, transactional lock/fence races, writes, verification, corruption, retry and cleanup. |
| CREATE | `tests/p4/integration/test_graph_projection_pipeline.py` | Real PostgreSQL/RabbitMQ/Celery/Neo4j execution through M1 activation and failed-rebuild preservation. |
| CREATE | `tests/fixtures/p4/graph/` | Small, no-edge, dense, Unicode, maximal-metadata, unresolved/conflict, historical and deliberate-corruption fixtures. |

No Express, frontend, P1-P3, frozen M1 model/lifecycle/persistence/source/queue
contract, `master.txt`, GitHub workflow or Python analysis pipeline file is
modified. No new Python dependency or PostgreSQL/Alembic migration is planned.
The owner-approved manifest-label amendment was accepted and re-frozen without
reopening any other M1 surface. The three Neo4j composite scope indexes are
approved physical additions but remain unimplemented until M2; exact Community
compatibility must be demonstrated before their use.

### J. Three implementation batches

#### Batch 1 — Deterministic P4-P1 foundation

Implement immutable records, strict mapper, exact keys, P3 public UUID reuse,
metadata allowlist, canonical serializers/digests, config validation and
fixtures. Benchmark candidate batch/timeout/property caps and validate additive
index support on Neo4j Community. Report measurements and recommended limits;
only the owner may approve/freeze them before writer work. The corrected M1
graph schema is accepted/re-frozen and this detailed M2 plan is owner-approved;
Batch 1 remains deliberately unstarted until the owner gives a separate start
instruction.

Acceptance: permutation and cross-process runs produce byte-identical records
and digests; G1/G2 keys differ while canonical IDs match; all existing entity/
relationship kinds map without semantic invention; unresolved/conflict inputs
produce summaries only; unknown/unsafe/oversized metadata fails without
truncation; repository-relative `source_root` and HTTP-route fields enforce their
distinct value contracts; golden vectors cover Unicode and empty sets; no frozen
contract/file changes occur.

#### Batch 2 — Bounded writer and independent verifier

Implement the projection store, additive indexes, fenced manifest, bounded
reset/write/delete, new-session verifier, complete corruption matrix and exact
translation to frozen `VerificationReceipt`. Review and freeze P4-P1 after real
Neo4j evidence.

Acceptance: retries are idempotent; stale fence writes affect zero records; G1
and G2 coexist; exact nodes/edges/endpoint direction are written; missing,
extra, duplicate, cross-scope, wrong endpoint/direction/count/version/schema or
digest corruption fails; READY is set only after successful independent read;
failed verification remains invisible; cleanup is bounded and refuses active
generations. Every candidate mutation re-establishes ownership while holding the
manifest node write lock in its own transaction; race tests prove both
replacement-first rejection and old-commit-first reset/rebuild orderings.

#### Batch 3 — M1 integration and operational closure

Implement executor/task/DI, short PG units of work, lease checkpoints, safe
failure mapping, reconciliation-driven retry, cleanup scheduling, dedicated
execution worker, live capability transition and complete real-infrastructure
pipeline tests. Update the execution ledger only with observed results.

Acceptance: durable P4-W1 work progresses only with a live execution consumer;
duplicate delivery is a no-op; lease replacement fences the old worker; source
mismatch cannot write; transient failures retry the same generation at most
three total executions; M1 alone activates; stale/out-of-order result cannot
switch the pointer; failed rebuild preserves the prior COMPLETED or STALE active
generation; graph loss can rebuild from P3 without analysis; analysis and
maintenance queues remain isolated.

### K. Test and verification strategy

Unit/property tests cover every pure algorithm, enum kind, status, metadata
type, cap and failure code. Adapter tests use a fake driver only for query
contract isolation; real Neo4j tests are mandatory for constraints, composite
indexes, transaction behavior, relationship direction, fencing and corruption.
Real PostgreSQL/RabbitMQ/Celery tests prove M1 integration rather than replacing
it with mocks. Regression includes all frozen P1-P3 and M1 suites.

The real-Neo4j concurrency suite uses deterministic barriers. In the
replacement-first case, an old worker pauses after non-authoritative preflight
ownership validation but before its mutation transaction; the replacement
transaction acquires the manifest lock and commits the new fence; the old worker
then resumes, must re-establish ownership inside its mutation transaction,
observes the mismatch and commits no candidate change or receipt. In the reverse
case, the old worker acquires the manifest lock, validates and pauses; the
replacement is proven blocked, the old bounded mutation commits, then the
replacement acquires the lock, replaces the fence and resets/rebuilds the
inactive candidate. The test asserts that no old-fence mutation can commit after
replacement commit, and that READY is never reset.

Planned commands (implementation must record exact outcomes):

```text
docker compose -f infra/docker/compose.yml up -d postgres rabbitmq neo4j
./venv/bin/alembic upgrade head
./venv/bin/pytest tests/p4/graph/test_projection.py
./venv/bin/pytest tests/p4/graph/test_projection_store.py
./venv/bin/pytest tests/p4/graph/test_verification.py
./venv/bin/pytest tests/p4/graph/test_projection_worker.py
./venv/bin/pytest tests/p4/integration/test_graph_projection_neo4j.py
./venv/bin/pytest tests/p4/integration/test_graph_projection_pipeline.py
./venv/bin/pytest tests/p4
./venv/bin/pytest
./venv/bin/black --check backend tests
./venv/bin/ruff check backend tests
./venv/bin/mypy backend
systemd-analyze --user verify ops/systemd/stacksense-celery-graph-projection-worker.service
git diff --check
```

Performance evidence records hardware, source counts, canonical bytes, batch
sizes, transform/write/verify/cleanup durations, peak worker memory and Neo4j
query plans. It never weakens hard source limits or silently drops records.

### L. Module acceptance criteria and Definition of Done

M2 is complete only when:

1. identical exact source/scope/config/schema/projector produces identical
   semantic records and all expected digests;
2. generation-scoped keys permit simultaneous old active and new candidate
   generations without mutation or collision;
3. every canonical entity and resolved relationship is represented once with
   exact IDs, properties, direction and endpoints;
4. unresolved relationships/conflicts are never synthetic graph elements and
   their complete treatment is represented by deterministic summaries;
5. all writes, reads and deletes are bounded, parameterized, scoped and
   idempotent; no arbitrary Cypher surface exists;
6. every candidate mutation serializes on the exact `ProjectionManifest` node,
   revalidates ownership under that held lock, and a completed replacement fence
   makes every old-fence mutation/receipt impossible; READY is immutable;
7. independent read-back detects every required omission, duplicate, extra,
   endpoint, scope, version, count and digest corruption;
8. failed/partial candidates never become active or query-visible, while a
   failed rebuild preserves the prior verified generation and public state;
9. P4-P1 exactly satisfies frozen M1 receipt/activation checks and M1 alone
   switches the pointer;
10. retry exhaustion, duplicate delivery, broker/Neo4j loss and cleanup follow
    frozen M1 semantics without new public states/events;
11. no raw source, secrets, credentials, lease token, unsafe metadata or host
    filesystem path enters Neo4j/logs/errors; repository-relative source roots
    and canonical HTTP route paths remain semantically distinct;
12. focused, corruption, concurrency, real-infrastructure, full regression,
    formatting, lint, typing and service-unit checks pass with recorded results;
13. P1-P3 and frozen M1 files/contracts remain unchanged except only changes
    separately authorized through the manifest-label/version change-control
    gate and additive-index approval; and
14. P4-P1, measured limits and the M2 execution record receive independent
    review and explicit owner freeze approval before M3 begins.

### M. Risks and owner decisions required before implementation

1. **Manifest label/version — RESOLVED / RE-FROZEN:** the owner authorized and
   accepted the narrow M1 correction to sole label `ProjectionManifest` while
   retaining `GRAPH_SCHEMA_VERSION = 1.0.0`. The empty live schema was corrected
   and verified without alias/data migration; this M1 surface is frozen again.
2. **Additive Neo4j indexes — APPROVED FOR BATCH 1 VERIFICATION:** the owner
   approved the exact `ProjectionManifest`/entity/relationship composite RANGE
   indexes as physical access paths. Batch 1 must still prove their exact shape
   and compatibility on installed Neo4j Community before writer implementation.
3. **Candidate operational limits — UNAPPROVED, REQUIRED BEFORE BATCH 2:** approve or revise
   the benchmarked node/edge batch sizes, 30-second per-query timeout, metadata/
   record caps, 1,000-record cleanup page and 24-hour cleanup grace. The plan
   proposes measurement candidates only; Batch 1 evidence and explicit owner
   approval, not convenience or coding-agent choice, freezes them. Worker memory
   and throughput thresholds are included in this gate.
4. **P4-P1 vocabulary — UNAPPROVED, REQUIRED BEFORE BATCH 2:** approve the manifest
   `BUILDING|READY` states, generation-key formula, strict metadata allowlist,
   three canonical digest definitions and safe failure-code set. These are M2
   contract choices, not changes to M1's receipt envelope.

No unresolved architectural contradiction remains. Frozen P1-P3, M1 lifecycle/
receipt ownership, the no-new-Express boundary and all other approved P4
decisions remain consistent. This section preserves M2's approved planning
baseline; actual implementation, review and completion evidence is recorded in
Section 12. The 2026-11-12 owner M3-planning directive accepts M2 as complete
and authorizes the planning transition, without reopening its implementation.

## 7D. Detailed M3 Plan — Graph Query and Exploration API

**Planning status (2026-11-12): OWNER APPROVED — IMPLEMENTATION NOT STARTED.**
No M3 batch is authorized to start by this approval record alone. This detailed
plan supersedes only the provisional M3 file/batch sketch in Section 7B; it does
not alter the approved 17-decision P4 baseline, frozen P1-P3, frozen M1 or
completed M2 contracts.

### A. Verified repository findings and boundaries

1. Frozen M1 persists one `GraphProjectionResourceModel` per exact Architecture
   Version and projection type. It carries project/repository/version scope,
   public `PENDING|RUNNING|COMPLETED|FAILED|STALE` state and the sole
   `active_generation_id` pointer. `GraphProjectionRepository.get_resource`
   requires the resource UUID; the only version lookup is the private
   `_resource_for_version`. M1 therefore does **not** expose a suitable public
   exact-version read port for M3.
2. M3 will add a P4-owned, read-only generation-resolution port and SQLAlchemy
   adapter over the already frozen M1 tables. It will not add a method to the
   M1 lifecycle repository, mutate lifecycle state, acquire locks or create a
   second active-generation authority.
3. M2 writes fixed `ArchitectureEntity` nodes and `ARCH_RELATIONSHIP` edges.
   Every record contains `project_id`, `architecture_version_id`,
   `generation_id`, `generation_key` and its generation-scoped SHA-256
   `projection_key`. Nodes also contain the stable P3
   `architecture_entity_id`, logical ID, semantic signature, canonical kind,
   name, namespace, fact status, evidence logical IDs and allowlisted metadata.
   Edges contain the stable P3 `architecture_relationship_id`, logical ID,
   canonical kind/status, canonical source/target logical IDs and projection
   keys, evidence logical IDs and allowlisted metadata.
4. M2 independently verifies and finalizes a `ProjectionManifest` as `READY`
   before M1 can activate it. PostgreSQL's active-generation pointer remains the
   authority; the READY manifest is an additional read-side integrity preflight,
   never an activation signal.
5. Neo4j has uniqueness constraints on node, edge and manifest keys and
   composite RANGE indexes on `(project_id, architecture_version_id,
   generation_id)` for all three. There is no separate index on
   `architecture_entity_id` or canonical kind. Node anchoring can still use the
   scope index and exact stable-ID predicate within the frozen maximum of 25,000
   nodes, but Batch 2 must inspect real query plans and latency. Any additional
   index requires separate M1/M2 schema change control; M3 will not add one.
6. The official driver is pinned to `neo4j==6.4.1`; M1 verified Community
   5.26.33 and exposes an initialized driver through P4-owned dependency
   composition. M3 reuses that infrastructure and fixed database selection.
7. Existing Python APIs use synchronous FastAPI, Pydantic response models,
   request-scoped SQLAlchemy sessions, `StackSenseError`'s structured
   `{error:{code,message,details}}` envelope, and the trusted delegated
   service/actor/role/project/correlation headers. Existing list APIs use
   offset pagination; no reusable signed-cursor contract exists.
8. Ownership is explicit and non-overlapping: M1 owns projection lifecycle,
   status, attempts, rebuild orchestration and active-generation activation; M3
   owns only read-only P4-Q1 graph-query contracts and execution over M1-selected
   verified generations; M4 owns FastAPI routes that compose M1 lifecycle/
   rebuild services with M3 read services, delegated-context/RBAC integration,
   OpenAPI and final HTTP error mapping (P4-D1). This detailed ownership rule
   controls over provisional high-level wording in Sections 7/7B. M3 does not
   create/register public routes, expose a rebuild operation, mutate lifecycle
   state or modify frozen P3 delegated-auth code. React continues to call only
   the existing Express-facing boundary; no Express work is authorized here.

### B. Objective, ownership and non-goals

M3 exposes a transport-neutral, deterministic application capability over one
verified exact Architecture Version generation. It owns request/response DTOs,
generation resolution, safe cursor encoding, controlled graph reads, result
mapping, traversal semantics, query limits, query-layer errors and observability.

M1 remains the sole owner of lifecycle/status resources, attempts, automatic or
manual rebuild execution, leases, verification handoff and activation. M4 later
owns the FastAPI transport and composes M1 status/rebuild capabilities with M3
read-only queries; it must not move either responsibility into the other module.
M3 does not write Neo4j, schedule or rebuild projections, project or verify
candidates, activate generations, change projection state, query unverified
generations, modify P3 Architecture Models, expose arbitrary Cypher, implement
browser authentication, add Express/FastAPI routes, provide search/impact/AI
semantics, or plan M4-M6. Neo4j remains a rebuildable projection; PostgreSQL and
the published Architecture Model remain authoritative.

### C. P4-Q1 contracts

#### C1. Common scope and DTO vocabulary

- `GraphReadScope`: exact `project_id`, `architecture_version_id`, captured
  `generation_id`, resource state (`COMPLETED` or `STALE`), graph/projector
  versions and verified counts. A caller never supplies `generation_id` for an
  initial read; M3 resolves it from PostgreSQL. A continuation cursor must match
  the currently active generation exactly.
- **Pagination invariant:** every operation that emits or accepts a cursor
  (`graph window`, `neighborhood`, `dependencies`, `dependents` and
  `containment`) binds that cursor to the exact captured `generation_id`.
  Continuation always re-resolves the active generation first; a mismatch is
  `graph_generation_changed`. M3 never silently restarts, rebases a cursor or
  returns page one from another generation.
- `GraphNode`: P3 `architecture_entity_id`, logical ID, canonical kind, name,
  namespace, fact status, semantic signature, evidence logical IDs and only the
  already-projected safe metadata. Neo4j element IDs and projection keys are
  internal ordering/lookup values and are not public identities.
- `GraphEdge`: P3 `architecture_relationship_id`, logical ID, actual canonical
  kind/status, source/target `architecture_entity_id`, evidence logical IDs and
  safe metadata. Direction always remains canonical source to target.
- `GraphSubgraph`: exact version/generation, deterministic node/edge tuples,
  requested depth/direction/kinds, loaded counts, `truncated`, and opaque
  `next_cursor` when meaningful. Nodes are unique by stable entity UUID and
  edges by stable relationship UUID.
- `GraphPath`/`GraphPathResult`: ordered node and directed-edge sequences plus
  exact scope; maximum 25 paths. They describe static canonical relationships,
  not runtime execution or impact certainty.
- Ordering is byte-deterministic by lowercase generation-scoped projection key;
  ties are impossible under M2 uniqueness constraints. Public output is then
  mapped to stable P3 UUIDs without exposing the key.
- Canonical relationship kinds remain exactly `contains` plus the approved
  dependency set: `depends_on`, `imports`, `calls`, `exposes`, `consumes`,
  `produces`, `connects_to`, `persists_to`, `uses`, `extends`, `implements`,
  and `routes_to`. M3 creates no vocabulary.

#### C2. Common validation and limits

- Defaults: depth 1, nodes 100, edges 200, paths 5, timeout 2 seconds and page
  size 50. Hard maxima: depth 5, nodes 500, edges 1,000, paths 25, timeout 5
  seconds and page size 100. Requests outside these bounds fail before Neo4j.
- Directions are closed enums (`incoming`, `outgoing`, `both`) and relationship
  kinds are enum values, never Cypher fragments. Entity/version/project IDs are
  UUIDs. Duplicate kinds are normalized into canonical enum order.
- Every query uses fixed label/type names and parameters for all data values.
  Where Cypher cannot parameterize a bounded depth, the adapter selects one of
  five audited literal templates after enum/integer validation; it never
  interpolates caller text.
- One monotonic operation deadline starts before initial PostgreSQL generation
  resolution and is capped at five seconds. It covers cursor validation,
  PostgreSQL reads, connection acquisition, every Neo4j query, result streaming/
  iteration, deduplication, mapping/serialization preparation and the final
  PostgreSQL pointer verification. Every database call receives only the
  remaining budget. Neo4j uses both a server-side transaction/query timeout and
  a deadline cancellation guard that cancels/closes the active session and
  rolls back server work when time expires; PostgreSQL reads use a remaining-
  budget statement timeout and rollback on expiry. An application timer alone
  is insufficient. Mapping/iteration checks the same deadline, and expiration
  at any point—including final pointer verification—returns
  `graph_query_timeout` with no partial response. Limit termination remains
  explicit; it never silently drops records while claiming completeness.

#### C3. Generation resolution and consistency

1. M4 will authorize the delegated project before invoking M3. M3 independently
   looks up the exact `(project_id, architecture_version_id, projection_type)`
   resource through its read-only adapter.
2. Only `COMPLETED` or exact-version `STALE` resources with a non-null active
   generation and complete activation summary are readable. `PENDING`,
   `RUNNING`, `FAILED`, missing resources and candidates are not queryable.
3. The Neo4j adapter requires the matching `ProjectionManifest` to be `READY`
   and to match project/version/generation/schema/projector scope. Every node,
   edge and both relationship endpoints repeat the same three scope predicates.
4. The service captures one generation at request start. A concurrent rebuild
   continues serving the captured, immutable verified generation while G2 is
   being built. After query materialization it re-reads the PostgreSQL pointer;
   if it changed, the result is discarded with `graph_generation_changed` so
   the caller retries against the new generation. It never combines G1 and G2.
5. Every paginated operation validates the cursor's signed generation against
   a fresh PostgreSQL resolution before Neo4j access and rechecks the pointer
   before returning. If either check differs, it rejects continuation with
   `graph_generation_changed`; it never restarts at the new generation or
   converts the request into an initial page. Exact-version `STALE` reads are
   allowed when that resource retains a verified active generation; M3 never
   substitutes a newer/current version.

### D. Seven operation designs

#### D1. Graph window

- **Purpose:** deterministic bounded initial overview, not a complete export.
- **Input:** exact version/project scope; node/edge limits, page size, optional
  canonical-kind filters and cursor.
- **Semantics:** keyset-page nodes by projection key, then return the induced
  canonical edges whose endpoints are in that node window. If the edge cap is
  reached, the cursor retains the immutable node-window bounds plus the last
  edge key; after those edges finish it advances the node key. Endpoints are
  therefore never dangling and repeated nodes across an edge continuation are
  intentional/deduplicable.
- **Output:** `GraphSubgraph`, manifest total counts, loaded counts and explicit
  truncation. A verified zero-node graph returns `200` with empty tuples.
- **Tests:** empty/isolated/dense graphs, node and edge continuation, stable
  repeat reads, endpoint closure, kind filtering, hard limits and scope leaks.

#### D2. Node detail

- **Purpose:** retrieve one exact projected entity for inspector/detail use.
- **Input:** version/project and stable P3 `architecture_entity_id` UUID.
- **Semantics:** match within all three scope predicates; return projected safe
  properties only. No traversal and no pagination.
- **Output:** `GraphNode` with exact scope; missing/out-of-scope is the same safe
  `graph_node_not_found` result to avoid existence disclosure.
- **Tests:** every projected field, metadata allowlist, wrong scope/generation,
  absent node and refusal to expose projection/internal IDs.

#### D3. Neighborhood

- **Purpose:** generic bounded structural expansion around a node.
- **Input:** entity UUID, `incoming|outgoing|both`, depth, node/edge limits,
  optional relationship kinds and cursor.
- **Semantics:** default kinds are the 12 non-containment dependency kinds.
  `contains` participates only when the caller explicitly requests it; this is
  the only generic operation allowed to opt into it. Results retain actual kind
  and canonical edge direction even for incoming/both traversal. Reachable edge
  candidates are deduplicated and keyset-ordered by `(minimum_depth,
  relationship_projection_key, neighbor_projection_key)`.
- **Output:** start node plus bounded discovered nodes/edges and continuation.
  An existing node with no matches returns the start node and no edges.
- **Tests:** three directions, depths 1-5, cycles/self-edges, duplicate paths,
  explicit/implicit containment, deterministic pagination and dense fan-out.

#### D4. Dependencies

- **Purpose:** answer what the selected entity statically depends on.
- **Input:** entity UUID, depth, optional subset of the approved 12 dependency
  kinds, node/edge limits and cursor.
- **Semantics:** outgoing canonical traversal only. `contains` is rejected.
  Edge kinds are not collapsed to `depends_on`.
- **Output/tests:** neighborhood-shaped `GraphSubgraph`; test all 12 kinds,
  mixed kinds, direction, multi-hop cycles, empty results and containment
  rejection.

#### D5. Dependents

- **Purpose:** answer what statically depends on the selected entity.
- **Input/output:** same bounded contract as dependencies.
- **Semantics:** incoming traversal over the same 12-kind allowlist while each
  returned edge remains serialized source-to-target. `contains` is rejected.
- **Tests:** mirror dependencies plus proof that incoming traversal never swaps
  endpoint identities or edge direction.

#### D6. Containment

- **Purpose:** navigate canonical architecture hierarchy independently from
  dependency semantics.
- **Input:** entity UUID, `parents|children|both`, depth, node/edge limits and
  cursor.
- **Semantics:** only `contains`; parent-to-child is canonical outgoing
  direction, so parents traverse incoming and children outgoing. It shares the
  bounded traversal engine but not the dependency-kind API.
- **Output/tests:** bounded subgraph; direct/deep parent/child, multiple parents,
  cycles as corrupt-but-bounded data, empty hierarchy, direction and proof that
  non-containment edges never appear.

#### D7. Bounded paths

- **Purpose:** find deterministic directed static paths between two stable
  entity UUIDs in one generation.
- **Input:** source/target UUID, max depth, path limit, optional subset of the
  12 non-containment kinds and timeout.
- **Semantics:** directed source-to-target simple paths only; `contains` is
  excluded so containment remains a distinct capability. Fixed depth-selected
  controlled templates scope every node and edge. Results order by hop count,
  then the byte sequence of edge projection keys and node projection keys.
  Source equal to target returns one deterministic zero-edge path.
- **Output:** at most 25 paths with all nodes/edges materialized once per path;
  no path is a successful empty result. Timeout never returns an implied
  complete result.
- **Tests:** no/one/multiple paths, cycles, ordering, kind filters, equal
  endpoints, max depth/path cap, dense alternatives, timeout and cross-scope
  decoys.

### E. Cursor security and stable pagination

- Generation binding is a mandatory invariant for every paginated operation,
  not an operation-specific option. A valid signature does not make a cursor
  reusable after M1 changes the active pointer. M3 compares the signed
  `generation_id` with the freshly resolved active generation before retrieval
  and again after materialization; any mismatch rejects the continuation. No
  adapter or service may silently discard the cursor and restart pagination.
- The opaque format is `base64url(canonical-json-payload).base64url(hmac)` with
  padding omitted. The signature is HMAC-SHA256 over the encoded payload using
  a dedicated `graph_query_cursor_secret_key`, never the JWT, service-token or
  Neo4j credential. Verification uses `hmac.compare_digest` before trusting any
  field; encoded cursor size is capped.
- Payload v1 contains cursor contract version, issued/expiry timestamps,
  project/version/generation UUIDs, operation name, SHA-256 query fingerprint
  and operation-specific last stable position. Window positions may contain
  node-window bounds and last edge key; traversal positions contain depth/edge/
  neighbor keys. These are internal opaque ordering keys, not public graph IDs.
- The fingerprint is SHA-256 over canonical JSON of all semantics affecting
  results: operation, direction, normalized kinds, depth, limits/page size and
  endpoint IDs. Project/version/generation are also explicit payload fields for
  fail-closed diagnostics.
- Invalid encoding/version/signature is `graph_cursor_invalid`; expiry is
  `graph_cursor_expired`; project/version/operation/fingerprint mismatch is
  `graph_cursor_scope_mismatch`; inactive generation is
  `graph_generation_changed`. None reveals the decoded attacker payload.
- Recommended v1 TTL is 15 minutes and the production secret must contain at
  least 32 bytes. Rotating the one active secret intentionally invalidates
  short-lived outstanding cursors; multi-key grace rotation is deferred unless
  operations demonstrate a need. TTL and rotation behavior require owner
  approval at the Batch 1 P4-Q1 freeze.

### F. Internal architecture and data flow

```text
authorized exact project/version request (M4 later)
  -> GraphQueryService starts the single monotonic operation deadline
  -> GraphQueryService validates P4-Q1 request
  -> GraphGenerationReader resolves PostgreSQL active generation
  -> CursorCodec validates/binds continuation, if present
  -> GraphQueryRepository runs fixed, scoped Neo4j templates under the
     remaining server-side timeout and cancellation guard
  -> result iteration/mapper validates scope/properties and builds immutable
     DTOs while checking the same deadline
  -> generation pointer is re-read under the remaining PostgreSQL timeout
  -> bounded P4-Q1 result or typed safe failure
```

- `GraphQueryService` owns validation, deadline, generation double-read,
  cursor/fingerprint coordination, materialization caps and telemetry. Its one
  deadline budget is passed through every layer; nested repositories do not
  start independent timeout windows.
- `GraphGenerationReader` is a read-only port; its SQLAlchemy adapter is the
  only M3 component aware of M1 tables.
- `GraphQueryRepository` is a read-only port. `Neo4jGraphQueryRepository` owns
  fixed queries, remaining-budget connection/query/transaction timeout,
  deadline-triggered session cancellation/rollback, manifest preflight and
  strict record mapping. Application code never handles raw Cypher. A timed-out
  operation must terminate database work rather than merely stop awaiting it.
- Shared one-hop/dedup/keyset primitives support neighborhood, dependency,
  dependent and containment operations, but each public operation has a
  separate service method and allowlist/direction policy. Window and paths use
  dedicated implementations because their pagination and complexity differ.
- M3 emits structured query-start/completion/failure logs with operation,
  correlation ID, scope IDs, generation, duration, returned counts,
  truncation and safe code. It never logs cursor contents, Cypher, credentials,
  metadata values or Neo4j records. The repository currently has no metrics
  exporter; M3 exposes a small observer callback/default logging observer so a
  later operational integration can record duration/count/timeout/error metrics
  without changing query semantics or adding a dependency now.

### G. Error taxonomy and degradation

| M3 code | Meaning | Proposed M4 HTTP mapping |
|---|---|---|
| `graph_projection_not_found` | No exact project/version projection resource | 404 |
| `graph_projection_not_ready` | Exact resource has no readable active generation | 409 |
| `graph_node_not_found` | Anchor/node absent in authorized exact scope | 404 |
| `graph_cursor_invalid` / `graph_cursor_scope_mismatch` | Malformed, tampered or mismatched cursor | 422 |
| `graph_cursor_expired` | Valid cursor exceeded TTL | 410 |
| `graph_generation_changed` | Pointer changed during read or since cursor | 409 |
| `graph_query_limit_exceeded` | Request exceeds approved bounds | 422 |
| `graph_query_timeout` | Whole-operation deadline exhausted; database work cancelled/rolled back | 504 |
| `graph_unavailable` | Neo4j/driver unavailable | 503 |
| `graph_schema_incompatible` | READY manifest/record violates frozen schema | 503 |
| `graph_query_integrity_error` | Same-generation/scope/referential invariant failed | 500 |

M3 owns these safe typed meanings; M4 owns final `StackSenseError`/HTTP mapping
and the existing error envelope. Driver messages, stack traces, query text,
credentials and record contents never enter public details. A Neo4j failure
degrades graph capability only and does not make canonical P3 APIs unavailable.

### H. Exact file-change plan

All paths below are proposed P4-owned changes verified against the current tree.
No migration, dependency, Neo4j schema or frozen M1/M2/P1-P3 file change is
planned.

| Action/path | Ownership and responsibility |
|---|---|
| CREATE `backend/platform/graph/query_contracts.py` | M3 immutable request/result DTOs, closed direction/kind enums, approved defaults/hard limits and safe P4-Q1 serialization. |
| CREATE `backend/platform/graph/cursor.py` | M3 canonical payload, HMAC-SHA256 Base64URL codec, fingerprinting, expiry/size/scope validation and typed cursor failures. |
| CREATE `backend/platform/graph/query_repository.py` | M3 generation-read and graph-query ports, SQLAlchemy exact-version read adapter, fixed controlled Cypher adapter, manifest preflight and strict row mapping. |
| CREATE `backend/platform/graph/query_service.py` | M3 seven-operation application service, deadline/cap enforcement, generation double-read, cursor coordination and structured observer hook. |
| CREATE `backend/platform/graph/query_health.py` | M3 query capability probe/result independent of frozen M1 health DTO; M4 may compose it later. |
| MODIFY `backend/platform/graph/dependencies.py` | Add P4-owned M3 read repository/cursor/query-service providers while reusing the initialized M1 Neo4j infrastructure. No P3 DI change. |
| MODIFY `backend/platform/config.py` | Add approved query defaults/hard-cap validation, dedicated cursor secret and TTL; no lifecycle/projection setting changes. |
| MODIFY `.env.example` | Document only the new M3 query/cursor variables with a safe development placeholder and production rotation warning. |
| CREATE `tests/p4/graph/test_query_contracts.py` | DTO/enums/defaults/maxima, canonical output and invalid input. |
| CREATE `tests/p4/graph/test_cursor.py` | Determinism, tamper/expiry/scope/generation/fingerprint/size rejection and secret separation. |
| CREATE `tests/p4/graph/test_query_service.py` | All seven semantics, generation double-read, caps, errors, truncation, empty behavior and telemetry using fakes. |
| CREATE `tests/p4/graph/test_query_isolation.py` | Adversarial project/version/generation decoys and result-mapper fail-closed checks. |
| CREATE `tests/p4/integration/test_graph_query_neo4j.py` | Real Community 5.26.33 schema/query plans, all operations, cursors, dense/cyclic graphs, timeouts and concurrent G1/G2 visibility. |
| CREATE `tests/p4/integration/test_graph_query_postgres.py` | Real PostgreSQL COMPLETED/STALE resolution, unreadable states, pointer changes and exact-version behavior. |
| CREATE `tests/p4/graph/test_query_performance.py` | Reproducible named fixtures and recorded duration/materialization/concurrency measurements; never a substitute for real-Neo4j evidence. |
| DO NOT MODIFY `backend/api/**`, `express/**`, `frontend/**` | P4-D1 FastAPI transport belongs to M4; Express/frontend are outside M3 and the no-new-Express rule remains binding. |
| DO NOT MODIFY M1/M2/P1-P3 graph, analysis, persistence, migration or schema files | M3 consumes their frozen records/contracts read-only. |

### I. Three implementation batches and approval gates

#### Batch 1 — P4-Q1 foundation, generation reads and secure cursors

**Scope:** create contracts/errors, limit validation, exact-version generation
reader, cursor codec/fingerprints, settings and fakes. Freeze exact DTO fields,
operation semantics, cursor TTL/rotation and error vocabulary.

**Tests:** contract/cursor/service-generation unit tests; real PostgreSQL state
resolution for COMPLETED, STALE and unreadable states; production-secret
validation; formatting, Ruff and MyPy on changed files.

**Acceptance:** no M1 port/schema change; exact version/project required; only a
verified active generation resolves; every cursor-bearing operation rejects an
inactive generation without restarting; cursor tampering/expiry/scope changes
fail closed; all defaults/maxima match the approved baseline.

**Owner gate:** independently review and freeze P4-Q1 DTO names, 15-minute TTL,
rotation behavior, neighborhood explicit-containment behavior, path
non-containment policy and error codes before Batch 2.

**Batch 1 Execution Record (2026-11-13 — Verified):**
- **Files created/modified:**
  - `backend/platform/graph/query_contracts.py`: P4-Q1 contract version `1.0.0`, closed vocabularies (`TraversalDirection`, `ContainmentDirection`, `GraphRelationshipKind`), 12 approved dependency kinds (`contains` strictly excluded), hard limits (depth 5, nodes 500, edges 1,000, paths 25, page size 100, timeout 5.0s, cursor bytes 2048), safe typed exceptions with error taxonomy codes, immutable Pydantic request/response DTOs (`GraphReadScope`, `GraphNode`, `GraphEdge`, `GraphSubgraph`, `GraphPath`, `GraphPathResult`, `GraphWindowRequest`, `NodeDetailRequest`, `NeighborhoodRequest`, `DependenciesRequest`, `DependentsRequest`, `ContainmentRequest`, `BoundedPathsRequest`).
  - `backend/platform/graph/cursor.py`: HMAC-SHA256 Base64URL opaque cursor codec without padding, canonical JSON serialization, parameter normalization fingerprinting, fail-closed validation for tampering, expiration, project/version scope mismatch, operation mismatch, and active generation drift (`GraphGenerationChangedError`).
  - `backend/platform/graph/query_repository.py`: `GraphGenerationReader` protocol and read-only `SqlAlchemyGraphGenerationReader` adapter over frozen M1 tables (`GraphProjectionResourceModel`), resolving COMPLETED/STALE active generations without locks or M1 schema changes; `GraphQueryRepository` protocol and `FakeGraphGenerationReader`.
  - `backend/platform/graph/query_health.py`: independent `GraphQueryHealthProbe` and `GraphQueryHealthResponse` evaluating Neo4j query capability without mutating database or lifecycle state.
  - `backend/platform/config.py`: query defaults and hard-cap bounds, dedicated `graph_query_cursor_secret_key` and 15-minute `graph_query_cursor_ttl_seconds`, with production validation.
  - `.env.example`: documented M3 query and cursor settings with rotation warning.
- **Verification Evidence:**
  - `tests/p4/graph/test_query_contracts.py`: 13/13 passed (DTO immutability, vocabulary constraints, kind normalization, containment rejection in dependencies/dependents/paths, explicit containment in neighborhood, error codes).
  - `tests/p4/graph/test_cursor.py`: 8/8 passed (encoding, decoding round-trip, tampering rejection, secret separation, expiration, scope mismatch, generation changed fail-closed).
  - `tests/p4/graph/test_query_repository.py`: 10/10 passed (COMPLETED/STALE resolution, PENDING/RUNNING/FAILED rejection, missing resource, wrong project ID, missing metadata invariant check, active generation verification, fake reader).
  - `tests/p4/graph/test_query_health.py`: 5/5 passed (ready, schema incompatible, configuration invalid, storage unavailable, degraded probe).
  - `tests/p4/graph/test_config.py`: 29/29 passed (M3 query bounds validation, cursor secret production enforcement).
  - `tests/p4/integration/test_graph_query_postgres.py`: 1/1 passed against real PostgreSQL (PENDING rejected, lease/activation verified, COMPLETED resolved, STALE resolved, decoy project isolated).
  - Full P4 suite: 214/214 passed in 3.25s.
  - `black --check .`: 328 files passed.
  - `ruff check .`: 0 errors.
  - `mypy backend`: 0 issues found in 211 source files.
  - `git diff --check`: 0 errors.

#### Batch 2 — Controlled query engine and independent real-Neo4j proof

**Scope:** implement manifest preflight, node/window queries, shared bounded
traversal, dependencies/dependents, containment, paths, strict mapping,
whole-operation deadline/result caps, actual Neo4j cancellation/rollback and
deterministic generation-bound keyset continuation.

**Tests:** repository/service/isolation suites and real Neo4j for all kinds,
directions, cycles, density, pagination, same-scope endpoints, READY-only
visibility, cursor rejection after every operation's generation switch, timeout
during execution/iteration/mapping/final pointer verification, proof that timed-
out database work is cancelled, server outage and G1/G2 coexistence. Use
`EXPLAIN` and representative `PROFILE` only in controlled test infrastructure
to record scope-index use and anchor/traversal costs.

**Acceptance:** all Cypher is fixed and parameterized; every match scopes
project/version/generation and both endpoints; candidate/corrupt data cannot
leak; node/edge/path limits and the single five-second end-to-end deadline
cannot be bypassed; timed-out Neo4j/PostgreSQL work is terminated/rolled back;
results are deterministic across repeats; no internal IDs are exposed.

**Owner gate:** review real Community 5.26.33 query plans and named-hardware
measurements (p50/p95/max duration, materialized records, memory and concurrent
load). If stable-ID anchoring cannot meet the hard timeout, stop for explicit
schema/index change control rather than modifying frozen M1/M2.

**Batch 2 Execution Record (2026-11-13 — Verified):**
- **Files created/modified:**
  - `backend/platform/graph/query_repository.py`: implemented `Neo4jGraphQueryRepository` executing fixed, parameterized Cypher templates over composite scope indexes `(project_id, architecture_version_id, generation_id)` for nodes, relationships, and manifests; implemented manifest preflight (`verify_manifest_ready`), exact node inspection (`get_node_detail`), keyset-paginated window (`query_window`), bounded BFS traversal engine (`_execute_traversal`) supporting neighborhood (with explicit containment opt-in), outgoing dependencies (12 approved kinds, containment excluded), incoming dependents (12 approved kinds, containment excluded, edge source-to-target direction preserved), containment hierarchy (`contains` only); implemented directed simple paths (`query_bounded_paths`) up to depth 5 with 5 fixed templates; implemented `_map_node` and `_map_edge` stripping internal projection properties (`_INTERNAL_PROJECTION_PROPERTIES`); updated `FakeGraphQueryRepository` double.
  - `backend/platform/graph/query_service.py`: implemented `GraphQueryService` orchestrating all 7 operations with single monotonic operation deadline (5.0s budget), keyset cursor decoding/validation/issuance, manifest preflight, query execution, and PostgreSQL active-generation double-read verification preventing cross-generation leakage (`GraphGenerationChangedError`); implemented `GraphQueryObserver` protocol and `DefaultLoggingGraphQueryObserver`.
  - `tests/p4/graph/test_query_service.py`: 13/13 unit tests passed (all 7 operations with fakes, cursor pagination and tamper rejection, double-read generation change detection, deadline timeout handling, manifest unready rejection, observer lifecycle event tracking).
  - `tests/p4/graph/test_query_isolation.py`: 6/6 tests passed (internal projection properties stripped from node/edge metadata, composite scope predicates enforced across all Cypher templates, traversal queries, and path templates).
  - `tests/p4/graph/test_query_performance.py`: 4/4 tests passed (hard cap validation on node/edge/path/depth/timeout bounds, dense workload materialization benchmark for 500 nodes and 1,000 edges completed in < 500ms).
  - `tests/p4/integration/test_graph_query_neo4j.py`: 11/11 tests passed against real Neo4j Community 5.26.33 (READY manifest preflight, BUILDING/missing/schema-mismatch rejection, exact-scope node detail, window pagination with keyset advancement, neighborhood with direction and explicit containment, outgoing dependencies excluding containment, incoming dependents preserving source->target direction, containment navigation, depth 1-5 bounded paths with cycle handling, G1/G2 generation coexistence without leakage, server-side transaction timeout mapping).
- **Verification Evidence:**
  - `tests/p4/graph/`: 234/234 passed in 2.17s.
  - `tests/p4/integration/` (real Neo4j 5.26.33 + real PostgreSQL 16): 12/12 passed in 3.29s (11 Neo4j + 1 PostgreSQL).
  - Full P4 suite: 246/246 passed.
  - Regression: P1 (20/20 passed), P2 (309/309 passed), P3 M3 (90/90 passed).
  - `black --check .`: 333 files passed.
  - `ruff check .`: 0 errors.
  - `mypy backend`: 0 issues found in 212 source files.
  - `git diff --check`: 0 errors.

#### Batch 3 — Composition, degradation and M3 freeze

**Scope:** add P4-owned DI, query health, observer/logging, full generation
double-read behavior, cross-module regression and final P4-Q1 handoff for M4.
Do not register FastAPI routes; M4 consumes the frozen service/DTO/error
contract.

**Tests:** dependency lifecycle/driver closure, health degradation, correlation
logging without sensitive fields, pointer switch during query, cursor after
switch for every paginated operation, historical STALE read, deadline expiry at
each operation phase, real PostgreSQL+Neo4j integration, full P4 and repository
regression plus Black/Ruff/MyPy.

**Acceptance:** Neo4j loss is explicit and isolated; G1 remains readable during
G2 construction; a pointer switch never produces mixed output; M4 can compose
all seven operations without redefining DTOs; no Express/frontend/API route or
frozen source changes; execution evidence and deviations are recorded.

**Owner gate — SATISFIED 2026-11-13:** independent M3 review remediation was
verified and the owner explicitly froze P4-Q1/P4-H1. Section 12.13 records the
status approval; M3 is not reopened by M4.

**Batch 3 Execution Record (2026-11-13 — Verified):**
- **Files created/modified:**
  - `backend/platform/graph/dependencies.py`: implemented P4-owned DI providers:
    - `get_graph_generation_reader(session)`: creates request-scoped `SqlAlchemyGraphGenerationReader` wrapping SQLAlchemy session.
    - `get_graph_query_repository(settings)`: constructs `Neo4jGraphQueryRepository` reusing initialized `Neo4jInfrastructure.driver`.
    - `get_graph_query_service(settings, generation_reader, query_repository)`: constructs request-scoped `GraphQueryService` with validated `cursor_secret_key` and single monotonic operation deadline manager.
    - `get_graph_query_health_probe(settings)`: constructs independent `GraphQueryHealthProbe`.
  - `backend/platform/graph/__init__.py`: exported full P4-Q1 contract symbols (`APPROVED_DEPENDENCY_RELATIONSHIP_KINDS`, `P4_Q1_CONTRACT_VERSION`, DTOs, vocabularies, errors), repository protocols and implementations, service, observer, cursor functions, error types, and DI providers with strict `__all__`.
  - `tests/p4/graph/test_dependencies.py`: 6/6 unit tests passed for all DI providers (session wrapping, driver reuse, service construction with secret injection, and health probe lifecycle).
  - `tests/p4/graph/test_query_pipeline.py`: 15/15 unit tests passed covering historical STALE reads across all 7 operations, active generation pointer drift detection mid-query across all 7 operations, cursor invalidation across all paginated operations following active generation shift, deadline exhaustion at each of the 4 query phases (preflight, data query, post-query pointer re-read, mapping), and structured logging observer telemetry without leaking sensitive credentials.
  - `tests/p4/integration/test_graph_query_pipeline.py`: 1/1 end-to-end integration test passed against real PostgreSQL 16 and Neo4j Community 5.26.33, proving:
    1. Exact-version generation resolution from PostgreSQL authority.
    2. Neo4j manifest preflight and controlled query execution.
    3. Candidate G2 build coexistence in Neo4j while G1 actively serves traffic.
    4. Active pointer switch from G1 to G2 in PostgreSQL immediately and atomically shifts subsequent reads to G2.
    5. Invalidation of G1 cursors following pointer switch to G2 (`GraphGenerationChangedError`).
    6. Historical STALE resource queryability.
    7. Clean database isolation and tear-down.
- **Verification Evidence:**
  - Full P4 suite: `pytest tests/p4` -> 278 passed, 3 skipped in 36.64s.
  - P4 Graph Unit tests: `pytest tests/p4/graph/` -> 253 passed.
  - P4 Integration tests: `pytest tests/p4/integration/` -> 25 passed against real PostgreSQL 16 and Neo4j Community 5.26.33.
  - Regression suites:
    - P1: 20 passed in 0.32s (`pytest tests/p1/`).
    - P2: 309 passed, 1 skipped in 9.68s (`pytest tests/p2/`).
    - P3 M3: 91 passed in 0.19s (`pytest tests/p3/analysis/...`).
  - Code Quality Gates:
    - `black --check .`: 335 files unchanged (clean).
    - `ruff check .`: 0 errors (clean).
    - `mypy backend`: 0 issues found in 212 source files (clean).
    - `git diff --check`: 0 whitespace errors (clean).
- **Boundaries Preserved:**
  - No FastAPI routes registered (`backend/api/**` left strictly to M4).
  - Zero Express / frontend modifications (`express/**` and `frontend/**` untouched).
  - Zero P1, P2, P3 frozen contract modifications.
  - M1 lifecycle tables remain strictly read-only for M3 query engine via `SqlAlchemyGraphGenerationReader`.

### J. Test, performance and security strategy

- Fakes prove service decisions, cursor cryptography and failure mapping; they
  cannot close Neo4j semantics, query plans, timeout or isolation gates.
- Real PostgreSQL proves exact lifecycle resolution and pointer races. Real
  Neo4j 5.26.33 proves labels/types, indexes, relationship direction, endpoint
  scope, deterministic pages, dense/cyclic traversal and driver timeout.
- Fixtures cover empty, isolated, mixed-kind, deep containment, cyclic, dense,
  Unicode, multiple projects, multiple versions, coexisting G1/G2, corrupt
  endpoints/scope and READY/BUILDING manifests.
- Performance runs report rather than invent capacity claims. They exercise
  default and maximum request bounds, dense fan-out, depth 5, 25 paths, many
  concurrent readers and pointer switches. The immutable safety acceptance is
  that one deadline stops the entire M3 operation by 5 seconds—including final
  pointer verification—and server-side timeout plus cancellation/rollback ends
  database work. No response exceeds 500 nodes, 1,000 edges or 25 paths;
  tighter latency/SLO claims require owner approval from measured evidence.
- Query plans must begin from exact scope/anchor predicates and never scan
  unrelated projects/versions. Expensive risks are depth-5 variable paths,
  high-degree `both` traversal, induced edges in dense windows, distinct/dedup
  work and stable-ID anchor filtering without a dedicated index.
- Cursor input size, filter cardinality, enum values and repeated parameters are
  bounded before persistence access. Authorization occurs in M4 before M3, but
  M3 still requires exact project/version and filters every retrieval, providing
  defense in depth without duplicating RBAC authority.

### K. Critical-question resolutions

1. **Suitable M1 active-generation interface?** No. Evidence: public
   `GraphProjectionRepository` has only resource-ID lookup; version lookup is
   private. Use the M3 read-only adapter over frozen tables, not an M1 change.
2. **Does M2 schema support all queries?** Functionally yes: scope properties,
   endpoint keys, canonical kinds and scope indexes exist. Stable-ID anchoring
   lacks its own index, so performance is a measured Batch 2 risk, not grounds
   for an unapproved schema change.
3. **Are fields projected?** Yes for public node/edge identity, kind, direction,
   status, evidence references and safe metadata. Literal evidence/source text
   is intentionally absent; M3 must not reconstruct or invent it.
4. **Can cursors avoid M1/M2 changes?** Yes. All required binding inputs come
   from the M3 generation read and request, and projection keys already provide
   immutable keyset order.
5. **Stable pagination?** Signed operation-specific positions over immutable
   projection keys; no offset or Neo4j element ID. Window uses node bounds plus
   edge position; traversals use depth/edge/neighbor position. Every paginated
   operation signs the captured generation and rejects continuation after an
   active-pointer change; none silently restarts.
6. **Same verified generation guarantee?** PostgreSQL pointer capture, READY
   manifest preflight, full scope predicates on nodes/edges/endpoints, strict
   mapper validation and a PostgreSQL pointer re-read before return.
7. **Pointer changes during execution?** Discard the captured result and return
   `graph_generation_changed`; the caller restarts. G1 remains physically safe
   during the request under the approved generation coexistence/cleanup model.
8. **Shared versus separate queries?** Neighborhood/dependency/dependent/
   containment share bounded traversal mechanics but retain separate policies;
   window, node detail and paths require dedicated algorithms.
9. **Expensive patterns?** Dense fan-out, bidirectional depth 5, path
   enumeration, induced dense-window edges and unindexed stable-ID anchors.
   Fixed templates, deadlines, caps, keyset ordering and real benchmarks bound
   but do not erase those costs.
10. **M4 dependency?** M4 must map P4-Q1 services/errors to delegated FastAPI
    routes and freeze P4-D1 without redefining DTOs. No M3 dependency on new
    Express functionality exists; browser transport remains the already-recorded
    later owner gate.

### L. M3 Definition of Done, risks and decisions

M3 is complete only when all seven operations meet the frozen P4-Q1 contract;
COMPLETED and exact-version STALE resources are readable; candidates and
unreadable states are not; every returned record is from one READY active
generation; scope isolation, direction and containment separation are proven;
cursors and hard limits fail closed; real infrastructure/performance/concurrency
evidence proves the single five-second deadline covers execution, iteration,
mapping and final pointer verification and actually cancels/rolls back timed-out
database work; no frozen/Express/API-route code changed; and independent review
plus owner freeze approval is recorded.

The owner approved the implementation baseline choices for: (a) exact P4-Q1
DTO field names, (b) the 15-minute cursor TTL and invalidate-on-secret-rotation
policy, (c) explicit-only `contains` in generic neighborhoods, (d)
non-containment-only bounded paths, and (e) the safe error vocabulary/mappings.
The implementation and review evidence is recorded, and the owner subsequently
froze P4-Q1/P4-H1 in Section 12.13. No other architectural decision blocks M4
implementation. The dedicated stable-ID index is
**not** proposed; it becomes a change-control question only if real Batch 2
evidence proves the frozen schema inadequate.

## 7E. Detailed M4 Plan — Python/FastAPI Graph API Completion and Backend Integration

**Planning status (2026-11-13): PLANNING COMPLETE — MASTER AGENT REVIEW
COMPLETED / OWNER APPROVED; ALL THREE BATCHES AUTHORIZED AS ONE SEQUENTIAL UNIT;
IMPLEMENTATION NOT STARTED.** Implementation proceeds Batch 1 -> Batch 2 ->
Batch 3 without separate planning approval between batches. Batch acceptance
evidence remains mandatory, followed by one consolidated M4 review. This
section supersedes only the provisional M4 sketch in Sections 7/7B; it does not
alter the 17 approved P4 decisions or frozen P1-P3/M1-M3 contracts.

### A. Verified repository findings and prerequisite discrepancy

1. FastAPI is assembled in `backend/api/app.py`; `/api/v1` composition lives in
   `backend/api/v1/router.py`. Routers use synchronous functions, Pydantic
   response models and request-scoped SQLAlchemy sessions. The existing
   `StackSenseError` handler returns `{error:{code,message,details}}` and applies
   code/category-based HTTP status mapping.
2. `backend/api/v1/architecture.py` exposes only the canonical P3 Architecture
   Model. No FastAPI graph status/query/rebuild route exists. The planned
   `backend/api/v1/graph.py` path is therefore a verified **new P4 file**, not a
   modification of an existing graph router.
3. The accepted ADR-0001 boundary is implemented by
   `get_delegated_context`: constant-time `X-Service-Token` validation plus
   required actor UUID, closed OWNER/ADMIN/DEVELOPER/VIEWER role, project UUID
   and optional correlation ID. `require_delegated_project` rejects a query/path
   project different from the trusted header. M4 can reuse these frozen
   dependencies without modifying P3 authentication code.
4. M1's `GraphProjectionLifecycle.request_rebuild(resource_id, actor_id,
   actor_role, correlation_id)` owns rebuild-attempt creation, role validation,
   idempotent active-attempt reuse and the strict P4-W1 payload. Its repository
   is caller-transaction-owned. M1 intentionally has no public exact
   `(project_id, architecture_version_id)` status lookup and no HTTP facade.
5. A P4-owned, read-only M4 status adapter can query the frozen M1 tables without
   adding an M1 repository method. It must return the exact public resource state
   and active attempt summary verbatim; it may not infer lifecycle transitions,
   mutate rows or become a second lifecycle authority.
6. A manual rebuild can remain reliable without a new queue dual write: M4
   resolves the exact scoped resource, invokes the frozen M1 lifecycle method
   and commits the queued attempt. The existing M1 reconciler is the sole
   dispatcher/recovery authority and will publish the durable candidate. M4 does
   not publish, mark dispatched, retry, lease, verify or activate it.
7. M3 exposes exactly seven service methods: `get_window`, `get_node_detail`,
   `get_neighborhood`, `get_dependencies`, `get_dependents`, `get_containment`
   and `get_bounded_paths`. Its immutable P4-Q1 request/result DTOs, enums,
   limits, signed cursors, errors and five-second whole-operation deadline are
   directly reusable. M4 must only translate HTTP parameters into those request
   models and return their existing response models.
8. M3 errors are safe typed `GraphQueryError` values but are not
   `StackSenseError`; an additive M4 exception adapter/handler is required to
   preserve their codes and approved HTTP mappings. Driver exceptions and raw
   lifecycle messages must never be forwarded.
9. `/api/v1/health` is the frozen core-ready response and
   `/api/v1/health/graph` is M1's lifecycle/infrastructure health. M3 separately
   provides `GraphQueryHealthProbe/Response`. M4 will add a distinct safe query
   capability endpoint rather than change either existing response contract.
10. Express's current `architectureRoutes.js` and `architectureController.js`
    proxy only P3 version/entity/relationship/evidence/unresolved/conflict
    endpoints. There is **no browser-facing P4 graph status/query/rebuild
    transport**. M4 remains Python-only, so this does not block its internal API
    contract, but it blocks M5 live integration until separately approved
    Express change control supplies a compatible proxy. React must not call
    FastAPI directly.
11. The owner confirmed after remediation verification that M3 is complete and
    P4-Q1/P4-H1 are frozen. Section 12.13 records that status-only approval; it
    does not rewrite M3 implementation details or test evidence. M4 consumes the
    existing frozen contracts directly and has no remaining M3 prerequisite.

### B. Objective, ownership and non-goals

M4 composes the frozen M1 lifecycle and M3 query capabilities into a secure,
version-explicit, documented internal FastAPI API. It owns HTTP routing,
transport parameter mapping, delegated-context enforcement, exact project and
Architecture Version checks, OWNER/ADMIN rebuild authorization, safe HTTP error
mapping, correlation-aware route logging, graph query health exposure, OpenAPI
completion and P4-D1 contract tests.

M4 does **not** own graph semantics, Cypher, cursors, limits, generation
selection, projection writes/verification/activation, attempts/leases/retries,
browser authentication, project membership, Express gateway behavior, MongoDB,
frontend integration, P5 retrieval or P6 AI. It does not alter M1 or M3 frozen
interfaces. Express remains the browser-facing JWT/RBAC boundary; FastAPI
independently validates the delegated service/actor/role/project context.

### C. Proposed P4-D1 contract

P4-D1 v1 consists of the nine internal graph endpoints below, the separate
query-health endpoint, the unchanged delegated headers, direct reuse of P4-Q1
DTOs/vocabularies/limits and the safe error envelope. Every graph endpoint:

- requires `X-Service-Token`, `X-Actor-Id`, `X-Actor-Role` and `X-Project-Id`;
- accepts required `project_id` as a query parameter and rejects a mismatch
  before any graph/lifecycle service invocation;
- retains the explicit path `architecture_version_id` and never resolves or
  substitutes a latest/current version;
- uses the trusted delegated role, never a body/query role;
- accepts optional `X-Correlation-Id`; one M4 request-context dependency
  validates a supplied value as 1..255 characters without rewriting it, or
  generates exactly one UUID when absent. That same value is reused by route
  logs and M1 rebuild/audit persistence;
- documents success and safe error schemas in OpenAPI; and
- never returns service credentials, Neo4j keys/IDs, SQL details, Cypher,
  traceback text, hostnames, storage credentials or raw exception messages.

#### C1. Endpoint inventory and exact mappings

| Method/path | HTTP input -> frozen service request | Response/service/authorization |
|---|---|---|
| `GET /api/v1/architecture-versions/{version_id}/graph/status` | required `project_id`; exact UUID path/query | `ProjectionStatusResponse` from the M4 read-only status adapter; all four authorized roles; exact project/version only. |
| `GET /api/v1/architecture-versions/{version_id}/graph/nodes/{entity_id}` | `project_id`, optional `timeout_seconds` -> `NodeDetailRequest(project_id, version_id, entity_id, timeout_seconds)` | existing `GraphNode`; `GraphQueryService.get_node_detail`; all roles. The actual frozen DTO has no separate scope wrapper. |
| `GET /api/v1/architecture-versions/{version_id}/graph/window` | `project_id`, `node_limit`, `edge_limit`, `page_size`, repeated `canonical_kinds`, optional `cursor`, `timeout_seconds` -> `GraphWindowRequest` | existing `GraphSubgraph`; `get_window`; all roles. |
| `GET /api/v1/architecture-versions/{version_id}/graph/nodes/{entity_id}/neighborhood` | `project_id`, `direction`, `depth`, node/edge limits, repeated `relationship_kinds`, cursor, timeout -> `NeighborhoodRequest` | `GraphSubgraph`; `get_neighborhood`; all roles; explicit `contains` remains permitted only under frozen M3 rules. |
| `GET /api/v1/architecture-versions/{version_id}/graph/nodes/{entity_id}/dependencies` | `project_id`, depth, node/edge limits, repeated dependency kinds, cursor, timeout -> `DependenciesRequest` | `GraphSubgraph`; `get_dependencies`; all roles; `contains` remains rejected. |
| `GET /api/v1/architecture-versions/{version_id}/graph/nodes/{entity_id}/dependents` | same bounded fields -> `DependentsRequest` | `GraphSubgraph`; `get_dependents`; all roles; canonical edge direction is unchanged. |
| `GET /api/v1/architecture-versions/{version_id}/graph/nodes/{entity_id}/containment` | `project_id`, `direction=parents|children|both`, depth, node/edge limits, cursor, timeout -> `ContainmentRequest` | `GraphSubgraph`; `get_containment`; all roles; only `contains`. |
| `GET /api/v1/architecture-versions/{version_id}/graph/paths` | `project_id`, required `source_entity_id`, `target_entity_id`, `max_depth`, `path_limit`, repeated relationship kinds, timeout -> `BoundedPathsRequest` | `GraphPathResult`; `get_bounded_paths`; all roles; non-containment directed paths only. |
| `POST /api/v1/architecture-versions/{version_id}/graph/rebuild` | required `project_id`; no caller-supplied actor/role/generation/resource ID | `202 ProjectionRebuildAcceptedResponse`; OWNER/ADMIN only; M4 adapter resolves exact resource then invokes `GraphProjectionLifecycle.request_rebuild`, commits the durable attempt and leaves dispatch to M1 reconciliation. |
| `GET /api/v1/health/graph/query` | no delegated/user scope; no caller-controlled graph query | existing `GraphQueryHealthResponse`; additive P4-H1 query capability probe. It never alters core `/health` or M1 `/health/graph`. |

All request defaults and hard maxima are imported from P4-Q1, not copied as new
constants. Repeated enum query values map to tuples and Pydantic performs the
final frozen validation. Cursor strings remain opaque. FastAPI's syntactic
path/query validation remains a documented 422; intentional graph failures use
the StackSense error envelope.

#### C2. M4 lifecycle transport DTOs

- `ProjectionAttemptSummary`: `attempt_id`, `attempt_number`, frozen attempt
  state and created/updated/completed timestamps. It excludes actor identity,
  lease tokens/owners, correlation IDs, failure messages and dispatch internals.
- `ProjectionStatusResponse`: resource UUID, exact project/version UUIDs,
  frozen public state, optional active generation/schema/projector versions,
  optional verified `ProjectionCounts`, safe `last_failure_code`, timestamps and
  optional active-attempt summary. An in-progress rebuild may coexist with a
  readable COMPLETED/STALE active generation; M4 must not rewrite that state.
- `ProjectionRebuildAcceptedResponse`: resource/version IDs, public resource
  state, queued/reused attempt UUID/number/state and `accepted_at` from the
  attempt record. `202` means a durable M1 attempt exists, not that projection
  completed or dispatch succeeded.
- `GraphErrorResponse`: OpenAPI model of the existing
  `{error:{code,message,details}}` shape; it changes no global envelope.

#### C3. Authorization and scope matrix

| Capability | OWNER | ADMIN | DEVELOPER | VIEWER | Scope enforcement |
|---|---:|---:|---:|---:|---|
| Projection status | read | read | read | read | trusted header project must equal `project_id`; adapter requires exact version/project pair. |
| Seven P4-Q1 reads | read | read | read | read | delegated project check precedes M3; M3 independently scopes project/version/generation. |
| Manual rebuild | allow | allow | deny | deny | role denial occurs before resource lookup; actor UUID/role/correlation come only from delegated context. |
| Query health | safe operational read | safe operational read | safe operational read | safe operational read | no tenant data or graph records are returned; endpoint follows the existing public health convention. |

Missing/invalid service credentials are 401. Missing/malformed delegated
actor/project or correlation input is 422. Unknown role, project mismatch and
rebuild role denial are 403. Cross-project and wrong-version lookups use the
same safe not-found result and never disclose whether another scope exists.

#### C4. Error and degradation mapping

| Domain condition/code | HTTP | Public behavior |
|---|---:|---|
| `graph_projection_not_found` | 404 | exact scoped projection absent; same response for out-of-scope version. |
| `graph_projection_not_ready` | 409 | exact version has no readable verified generation; no fallback. |
| `graph_node_not_found` | 404 | no node existence disclosure outside exact scope. |
| `graph_cursor_invalid` | 422 | malformed/tampered opaque cursor; decoded attacker content is never returned. |
| `graph_cursor_scope_mismatch` | 422 | cursor operation/project/version/parameters do not match. |
| `graph_cursor_expired` | 410 | caller restarts the operation explicitly. |
| `graph_generation_changed` | 409 | caller retries explicitly; M4 never substitutes another generation/version. |
| `graph_query_limit_exceeded` | 422 | frozen M3 bounds or kind policy rejected the domain request. |
| `graph_query_timeout` | 504 | M3 has cancelled/rolled back database work; no partial payload. |
| `graph_unavailable` | 503 | graph storage/query capability unavailable; canonical P3 routes remain available. |
| `graph_schema_incompatible` | 503 | installed projection/query schema is incompatible; no unsafe fallback. |
| `graph_query_integrity_error` | 500 | stable generic integrity message; no record/driver details. |
| `graph_rebuild_conflict` | 409 | M4-specific lifecycle composition conflict; M1 state remains authoritative. |
| `graph_lifecycle_unavailable` | 503 | PostgreSQL lifecycle persistence/commit unavailable; request is rolled back and never accepted. |
| `graph_api_internal_error` | 500 | sanitized unexpected M4 failure; exception detail stays server-side. |

M4 preserves every M3 code and its approved `safe_details` allowlist.
Lifecycle exceptions are mapped by explicit type/control flow, never by parsing
arbitrary error text. SQLAlchemy failures roll back and become
`graph_lifecycle_unavailable`. Existing delegated authentication remains
`authentication_required|invalid_token` -> 401, malformed delegated context
remains `analysis_input_invalid` -> 422, and role/project denial remains
`analysis_access_denied` -> 403. FastAPI syntactic path/query validation remains
a distinct standard 422 transport response; it is not relabeled as a graph
domain error. The existing global handler gains only additive graph handlers/
mappings and no unrelated status mapping changes.

### D. Internal composition and data flow

```text
trusted Express/service request
  -> FastAPI graph route validates delegated service/actor/role/project
  -> exact project header/query match and rebuild role check
  -> read route builds the frozen P4-Q1 request DTO
       -> frozen GraphQueryService -> PostgreSQL generation + Neo4j query
  -> status/rebuild route invokes M4 GraphApiService
       -> read-only exact-version status adapter
       -> frozen GraphProjectionLifecycle.request_rebuild (mutation only)
       -> caller-owned commit; existing M1 reconciler dispatches/retries
  -> graph error adapter -> existing safe error envelope/OpenAPI response
```

`GraphApiService` is a thin M4 facade, not lifecycle logic. Its status reader is
the sole new component aware of frozen M1 persistence models. For status it
executes one SQLAlchemy `SELECT` that reads the exact project/version/projection
resource and left-joins its active QUEUED/RUNNING/RETRYING attempt. PostgreSQL's
statement-level MVCC snapshot therefore supplies the resource state, active
generation and active-attempt fields from one observed database state. The M1
partial uniqueness invariant permits at most one active attempt. The adapter
maps that single result directly, uses no row locks and never infers a transition.
If lifecycle state changes before or after the statement, the caller receives
the coherent before-or-after snapshot, never fields combined from two reads.

The exact rebuild call/transaction sequence is:

1. the route validates the delegated service, actor, OWNER/ADMIN role and exact
   project match, then obtains the request's one correlation ID;
2. the M4 status reader resolves the exact `(project_id,
   architecture_version_id, projection_type)` resource in the existing
   request-scoped SQLAlchemy session; absence/out-of-scope is the same safe 404;
3. `GraphApiService` invokes the frozen
   `GraphProjectionLifecycle.request_rebuild(resource.id, actor_id, actor_role,
   correlation_id)`; M1 alone locks as required, creates or reuses the active
   attempt and applies lifecycle/role/idempotency semantics;
4. the status reader performs its coherent single-statement read inside that
   same transaction to materialize the accepted resource/attempt DTO;
5. `GraphApiService`, using the injected request-session `commit` callback,
   commits before returning. Only a successful commit permits HTTP 202;
6. any lookup, lifecycle, flush or commit failure invokes the same session's
   `rollback` callback and returns a safe error—never an acceptance response;
7. after commit, the existing M1 reconciler alone discovers and dispatches the
   queued attempt and owns all subsequent recovery.

No second session, transaction manager, publisher or idempotency key is added.
Concurrent rebuild requests continue to reuse M1's active attempt. M4 never
publishes Celery work, marks it dispatched, acquires a lease, retries, verifies
or activates a generation.

One M4 request-context dependency resolves correlation once. A supplied
`X-Correlation-Id` must contain 1..255 characters and is propagated byte-for-
byte; an absent header causes one UUID to be generated. The same resolved value
is used for route-level structured logs and M1 rebuild/audit persistence—no
downstream layer generates another request ID. Logs contain operation,
correlation ID, actor UUID, trusted role, project/version, HTTP outcome and safe
graph code. They exclude service tokens, cursors, query metadata, Cypher, graph
records and database messages. M3's frozen observer remains unchanged.

### E. Exact file-level implementation plan

| Action/path | Components and responsibility | Dependencies/tests/rationale |
|---|---|---|
| CREATE `backend/api/v1/graph.py` | P4-D1 router, nine scoped endpoints, query-health endpoint, parameter-to-P4-Q1 mapping, delegated project/role checks, response declarations and safe route logging. | Depends on frozen delegated dependencies, M1/M3 providers and M4 DTO/facade. API contract/auth/OpenAPI tests. Transport belongs here; no domain logic/Cypher. |
| MODIFY `backend/api/v1/router.py` | Include the new graph router under existing `/api/v1`. | Router-registration/OpenAPI regression. Minimal additive API composition. |
| CREATE `backend/platform/graph/api_contracts.py` | `P4_D1_CONTRACT_VERSION`, lifecycle response DTOs, error-envelope OpenAPI models and safe M4 lifecycle error classes. | Reuses `ProjectionCounts` and frozen state enums. Serialization/extra-field/error-code tests. Keeps M4-owned vocabulary out of frozen M1/M3 files. |
| CREATE `backend/platform/graph/api_service.py` | `GraphProjectionStatusReader` port, one-statement SQLAlchemy exact-scope resource/active-attempt snapshot adapter and thin `GraphApiService` for status/rebuild transaction composition. | Reads frozen M1 models; delegates mutation to `GraphProjectionLifecycle`; receives the same request session's commit/rollback callbacks. Unit + real PostgreSQL snapshot/concurrency/rollback tests. Avoids changing M1 repository contract. |
| CREATE `backend/platform/graph/api_dependencies.py` | Provide the request-scoped M4 status reader/API facade and one correlation-context resolver while depending on existing frozen lifecycle/query/query-health providers. | Tests supplied/missing/empty/overlong correlation, single-ID reuse and session commit/rollback. A separate M4 composition module avoids reopening M3's provider file or package exports. |
| MODIFY `backend/api/error_handlers.py` | Add explicit M3 `GraphQueryError` handling and M4 graph-code HTTP mappings while retaining the existing envelope and unrelated mappings. | Parametrized status/code/sanitization tests. Required because frozen M3 errors are transport-neutral. |
| CREATE `tests/p4/api/__init__.py` | Mark the P4 API test package. | No runtime responsibility. |
| CREATE `tests/p4/api/test_graph_contracts.py` | Endpoint paths/methods, parameter mapping, exact P4-Q1 DTO responses, response/error schemas and OpenAPI assertions. | FastAPI dependency overrides/fakes; all nine endpoints plus query health. |
| CREATE `tests/p4/api/test_graph_authorization.py` | Missing/invalid service token; malformed actor/role/project; header mismatch; all role reads; OWNER/ADMIN rebuild; DEVELOPER/VIEWER denial; cross-project/version isolation. | Proves authorization occurs before service calls. |
| CREATE `tests/p4/api/test_graph_errors_health.py` | Complete M3/M1 error-to-HTTP matrix, sanitized unexpected failures, Neo4j degradation/query health and unchanged core/M1 health. | Fakes plus OpenAPI checks; no secret/stack leakage. |
| CREATE `tests/p4/integration/test_graph_api_pipeline.py` | Real FastAPI + PostgreSQL + Neo4j status and all seven reads, durable rebuild request, concurrent request reuse, pointer/generation behavior and outage isolation. | Reuses P4 infrastructure fixtures; no Express mutation. |
| REUSE / DO NOT MODIFY `backend/platform/analysis/application/dependencies.py` | Existing ADR-0001 service/actor/role/project validation and project matcher. | Frozen P3 boundary; M4 imports it only. |
| REUSE / DO NOT MODIFY M1/M2/M3 files (`model.py`, `lifecycle.py`, `repository.py`, `persistence.py`, `query_contracts.py`, `query_service.py`, `query_repository.py`, `query_health.py`, `dependencies.py`, `__init__.py`) | Frozen lifecycle/query authority and exports. | Any discovered need to alter these is a hard stop and explicit change-control request. |
| REUSE / DO NOT MODIFY `express/**`, `frontend/**`, migrations, dependencies, `master.txt` | Browser transport/UI and schema are outside M4. | Run regressions only. Missing Express P4 transport remains an owner decision. |

No migration, Neo4j schema/index, dependency, environment variable or
configuration change is planned.

### F. Three sequential implementation batches

These three batches are one owner-approved implementation unit. The
implementation agent proceeds sequentially through all three and records each
batch's acceptance evidence without pausing for another planning approval or
owner review. It stops only for a genuine frozen-interface/architecture
conflict, an unresolvable hard acceptance failure, a schema/dependency/migration
change, or another action requiring explicit owner authorization. After Batch 3,
the Master Agent performs one consolidated M4 review.

#### Batch 1 — Python API contract integration

**Scope:** create P4-D1 contracts and thin status reader/facade; implement and
register status plus all seven read routes; reuse P4-Q1 request/result DTOs;
apply delegated service/project validation; declare OpenAPI success/error
responses. Rebuild mutation and final degradation behavior remain for Batch 2.

**Dependencies:** frozen P4-Q1/P4-H1, frozen M1 lifecycle and M3 service
providers, and existing FastAPI session/delegated dependencies. All are
satisfied; there is no remaining pre-implementation contract gate.

**Tests/evidence:** contract serialization; all role read access; every route's
exact service method/request model; defaults, repeated enums, cursor and hard
limit validation; project/version mismatch before service invocation; router
registration and generated OpenAPI paths/schemas; Black/Ruff/MyPy and focused
API suite.

**Acceptance:** all seven operations are reachable only through delegated exact
scope; routes contain no query/lifecycle logic; responses are byte-compatible
with frozen P4-Q1 serialization; status reflects M1 without reinterpretation;
no Express/frozen file is changed; P4-D1 version and endpoint vocabulary are
ready for the consolidated review.

#### Batch 2 — Mutation, authorization and degradation

**Scope:** add OWNER/ADMIN-only `202` rebuild; transactionally persist/reuse the
M1 attempt and rely on M1 reconciliation for dispatch; add correlation/audit
logging; install complete M3/M4 error mapping; expose separate query health;
prove graph outages do not affect core/P3 health or canonical APIs.

**Dependencies:** Batch 1 contracts/facade. No new owner approval between
batches unless a frozen-interface gap appears.

**Tests/evidence:** role matrix; supplied/missing/empty/overlong correlation and
one-ID propagation to logs/persistence; exact-version resource resolution;
single-statement coherent status before/during/after concurrent rebuild;
active-attempt reuse; concurrent rebuild requests; commit failure rollback;
reconciler-visible queued attempt; every M3 code mapping;
PostgreSQL and Neo4j failure mapping; query health ready/degraded/unavailable;
no misleading 200/202 on failure; log-capture tests proving correlation is
present and secrets/cursors/internal messages are absent.

**Acceptance:** DEVELOPER/VIEWER are denied before existence lookup;
OWNER/ADMIN create exactly one durable attempt under concurrency; `202` never
claims completion; M4 never dispatches/leases/activates; all failures use stable
safe envelopes; `/api/v1/health` and `/api/v1/health/graph` remain unchanged.

#### Batch 3 — Backend integration, regression and P4-D1 freeze evidence

**Scope:** complete real FastAPI/PostgreSQL/Neo4j composition tests, OpenAPI and
contract snapshot assertions, isolation/concurrency/outage cases, full relevant
regressions and the M4 execution record. No implementation scope expansion.

**Tests/evidence commands:**

```text
./venv/bin/pytest -q tests/p4/api
./venv/bin/pytest -q tests/p4/integration/test_graph_api_pipeline.py
./venv/bin/pytest -q tests/p4
./venv/bin/pytest -q tests/p1 tests/p2 tests/p3
./venv/bin/black --check backend tests
./venv/bin/ruff check backend tests
./venv/bin/mypy backend
npm --prefix express test
npm --prefix express audit --omit=dev
git diff --check
git diff --name-only -- express frontend master.txt backend/platform/analysis
```

Run against real PostgreSQL 16 and Neo4j Community 5.26.33; use fakes only for
isolated transport/error cases. Record skipped tests and the known frozen P3
process-wide memory benchmark separately rather than claiming a clean run.

**Acceptance:** status, seven reads and rebuild pass real composition; cursor
and generation errors survive HTTP mapping unchanged; cross-project/version
decoys never leak; OpenAPI contains exact request/response/error contracts;
existing P1-P3, P4 M1-M3 and Express behavior has no functional regression;
there are zero Express/frontend/frozen-contract changes; execution evidence is
ready for one consolidated independent M4 review and explicit P4-D1 freeze.

### G. Security, failure cases and edge conditions

- Authorization precedes retrieval. Cross-scope timing/detail is normalized to
  safe denial/not-found behavior; M4 never retrieves broadly then filters.
- Candidate generations, PENDING/RUNNING/FAILED resources without a readable
  active generation and BUILDING manifests remain inaccessible under M3 rules.
  Exact STALE versions with verified active generations remain readable.
- Rebuild failure never invalidates the previous COMPLETED/STALE active
  generation. Status may simultaneously show a readable public resource and an
  active rebuild attempt.
- Duplicate/concurrent rebuild calls reuse M1's active attempt; M4 adds no
  idempotency scheme that conflicts with M1.
- Invalid enum arrays, duplicate kinds, excessive limits, long cursors and
  timeout values are handled by frozen P4-Q1 validation; M4 does not clamp or
  silently rewrite them.
- Error details expose only allowlisted identifiers/codes already approved by
  the contracts. Authentication tokens, actor-supplied cursor payloads and
  storage/driver messages are never logged or returned.
- Query health is safe and isolated. An unavailable Neo4j returns graph
  unavailable/degraded status while core health and canonical P3 architecture
  endpoints stay operational.

### H. Definition of Done

M4 is complete only when all nine scoped endpoints and query health match the
approved P4-D1 contract; direct P4-Q1 DTO reuse is proven; delegated service,
actor, role, project and exact-version checks fail closed; all authorized roles
read and only OWNER/ADMIN rebuild; M1 remains the sole lifecycle/dispatch/
activation owner; M3 remains the sole graph-query owner; safe errors/OpenAPI,
correlation logging and degradation are complete; real PostgreSQL/Neo4j
composition and relevant regressions pass with exact evidence; no Express,
frontend, migration, dependency, `master.txt` or frozen P1-P3/M1-M3 file is
modified; and consolidated independent review plus explicit P4-D1 freeze is
recorded.

### I. Risks, blockers and approval decisions

1. **M4 implementation blockers:** none are currently known. The owner froze
   P4-Q1/P4-H1 and approved this corrected P4-D1 endpoint vocabulary, lifecycle
   status/rebuild DTOs, safe error mappings, query-health route, coherent status
   snapshot and durable-attempt/reconciler-dispatch design. All three batches
   are authorized as one sequential implementation unit.
2. **Browser transport — downstream M5 blocker, not M4 scope:** current Express has
   no P4 graph proxy. Before M5 API integration, the owner must authorize a
   separate Express gateway change or another architecture-compliant transport.
   Direct React-to-FastAPI is forbidden. M4 can be implemented/frozen internally
   while this remains unresolved, but P4 cannot complete without it.
3. **Frozen-interface escape hatch:** if implementation proves that the M4
   read-only adapter cannot expose status or the existing lifecycle cannot
   durably accept a rebuild, stop for explicit M1 change control. No such change
   is currently required by inspected code.
4. **Operational risks:** request-scoped Neo4j initialization cost, health-probe
   load, status/attempt races and correlation-log leakage are mitigated by reuse
   of current DI, bounded safe probes, a one-statement PostgreSQL status snapshot,
   M1 locking/idempotency and negative tests. No new performance/SLO claim is
   introduced.

## 8. Dependency Graph and Implementation Order

```text
M1 lifecycle/infrastructure
  -> P4-L1/S1/W1 freeze
  -> M2 projection/verification
       -> P4-P1 freeze
       -> M3 query/API
            -> P4-Q1/H1 freeze
                 |-> M4 Python/FastAPI integration -> P4-D1 freeze-|
                 |-> M5 compatibility/route/component/layout shell-|
                                                                    -> M5 API-integrated Explorer
                                                                    -> P4-U1 freeze
                                                                    -> M6 final integration/evaluation
```

Critical-path backend sequence: M1 -> M2 -> M3 -> M4. M5 shell/layout work may
overlap as described below, but live browser integration additionally depends on
a compatible already implemented Express transport or a separate owner-approved
decision outside P4 M1–M4. M6 test fixtures and harnesses can grow alongside
every module, but final evaluation waits for every approved dependency.

After the relevant P4-Q1 query DTO contract is stable, M4 Python API integration
and only M5 package compatibility, route shell, component shell and independent
layout-worker work may proceed in parallel. M5 consumes P4-Q1/P4-D1 DTOs as
defined and must not invent, fork or independently redefine them. M5 service,
hook and page integration with live graph APIs waits for P4-D1 and verification
that the completed Express boundary can carry the required calls. If it cannot,
work stops for explicit owner direction; no agent may add Express implementation
or bypass Express. This avoids DTO drift and preserves the security boundary.

## 9. Global Phase 4 Definition of Done

P4 is complete only when:

1. Every published Architecture Version eventually obtains a verified resource
   or an explicit recoverable/terminal projection state.
2. Projection is deterministic, idempotent, isolated and rebuildable from the
   published Architecture Model without repository reanalysis.
3. Independent read-back proves exact entities, relationships, endpoints,
   counts, uniqueness and digest before activation.
4. Partial/corrupt/candidate generations are never readable.
5. Failed rebuild preserves the last verified active generation and its public
   `COMPLETED` or `STALE` state; a historical STALE generation remains readable
   by exact version and never becomes FAILED merely because its rebuild fails.
6. COMPLETED and exact-version STALE reads behave correctly; current selection
   never silently returns history.
7. Queries preserve every selected approved canonical relationship kind and
   direction, keep `contains` separate from dependency traversal, are
   project/version/generation scoped, parameterized and enforce all approved
   limits/timeouts.
8. Express JWT/project RBAC and independent FastAPI delegation checks are both
   enforced; only OWNER/ADMIN rebuild.
9. Explorer route/state retains an explicit Architecture Version ID, never
   substitutes the current version, and supports exact-version initial load,
   lazy expansion, node selection, dependency/containment/path navigation,
   inspector and accessible list within 300/600 caps and the existing design
   system.
10. Neo4j outage/degradation is explicit and canonical P3 functionality remains
    available.
11. Reconciliation, dispatch recovery, stale leases, retries, orphan cleanup,
    metrics/logs and remove-and-rebuild are verified with real infrastructure.
12. Automated unit/integration/E2E/security/performance/accessibility gates and
    manual operational evaluations pass with recorded evidence.
13. Frozen P1–P3 regression suites, formatting, linting, type checks, Express/
    frontend tests, builds and dependency audits remain green.
14. No raw source/secrets/credentials/host paths leak to graph, API, UI or logs.
15. No P5/P6 behavior, new canonical vocabulary or frozen contract modification
    enters P4.
16. Implementation matches approved Baseline v1 and `master.txt`; deviations
    receive explicit change control before freeze.

## 10. Verification Commands Planned

Use actual environment paths and record real results during implementation:

```text
docker compose -f infra/docker/compose.yml up -d postgres rabbitmq neo4j
./venv/bin/alembic upgrade head
./venv/bin/pytest tests/p4
./venv/bin/pytest
./venv/bin/black --check .
./venv/bin/ruff check .
./venv/bin/mypy backend
npm --prefix express test
npm --prefix express audit --omit=dev
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend audit --omit=dev
```

Real worker/reconciler, outage and remove/rebuild scenarios are operational
checks, not replaced by unit tests.

## 11. Remaining Verification Items and Risks

| Item | Owner/resolution point |
|---|---|
| Exact Neo4j Python driver 6.4.x patch and Community constraint support on Python 3.14 | **Resolved by frozen M1:** driver 6.4.1 against Community 5.26.33. |
| Neo4j memory/localhost port/health configuration | **Resolved by frozen M1** and retained as an M6 operational regression. |
| Projection batch sizes and safe metadata key/value/record caps | M2 B1 benchmark and canonical metadata inventory before writer freeze. |
| Cursor secret rotation/TTL and exact endpoint DTO field names | M3 B1 contract freeze; dedicated production secret, no JWT-secret reuse. |
| React Flow/ELK compatible patches and deterministic worker options | M5 B1 before package pin/UI implementation. |
| P4-owned published-header adapter query plan and deterministic pagination/watermark behavior | M1 B2 against real PostgreSQL; any need to alter the frozen P3 port is an explicit, unapproved change-control gate. |
| Browser transport for P4 graph APIs under the no-new-Express boundary | Before M5 live API integration, verify whether the completed Express surface already supports the required transport. If not, stop for an explicit owner decision outside P4 M1–M4; do not add Express work or call Python directly. |
| Cleanup grace, retry jitter and operational alert thresholds | M1/M2 implementation metrics, frozen before M6 outage testing. |
| Capacity/performance baselines on named hardware | M6 B2; results recorded without weakening hard safety limits. |

Principal risks are projection authority drift, lost scheduling, partial graph
visibility, rebuild data loss, cross-scope traversal, Cypher injection, dense
graph resource exhaustion, stale/current confusion, metadata leakage, Neo4j
outage and browser layout overload. The approved architecture and module
acceptance criteria provide explicit mitigations for each.

No genuine conflict with `master.txt` was found. Section 13's Organization
language is interpreted through superseding Section 0: Project is the current
tenant boundary. ADR-0001 governs the implemented dual-backend ownership.

## 12. Approval Gates and Execution Ledger

Approval is sequential and non-transitive:

1. **P4 Architecture Baseline v1 — APPROVED.** All 17 decisions in Section 4.
2. **P4 high-level module discussion — COMPLETE / ACCEPTED AS THE P4 MODULE
   FOUNDATION.** Section 7 remains the shared conceptual boundary.
3. **Detailed M1 planning — OWNER APPROVED.** Section 7A is the implementation
   baseline. The preserved Section 7B roadmap remains reference material, not an
   automatically approved detailed plan for M2–M6.
4. **Detailed M2 planning — OWNER APPROVED.** Section 7C and all three batches
   are the approved implementation baseline and are implemented, reviewed and
   complete.
5. **Detailed M3 planning — OWNER APPROVED.** Section 7D and its three batches
   are the approved implementation baseline. M3 implementation (Batches 1, 2, and 3)
   is complete; independent-review findings are remediated and verified against real
   PostgreSQL and Neo4j Community. The owner confirmed M3 complete and froze
   P4-Q1/P4-H1 on 2026-11-13; M3 is not reopened by M4.
6. **Detailed M4 planning — MASTER AGENT REVIEW COMPLETE / OWNER APPROVED.**
   Section 7E is the approved complete three-batch P4-D1 implementation baseline.
   All batches are authorized as one sequential unit; implementation has not
   started.
7. **Implementation — M1, M2 & M3 FROZEN / COMPLETE; M4 AUTHORIZED / NOT
   STARTED.**
   The owner accepted M1, P4-L1/P4-S1/P4-W1, and M2. M3 Batches 1, 2, and 3 are
   fully implemented; the review remediation is verified against PostgreSQL 16 and
   Neo4j Community 5.26.33, and P4-Q1/P4-H1 are frozen. M4 implementation is
   authorized but no batch has started.

| Work item | Status |
|---|---|
| P1–P3 | **FROZEN / COMPLETE** |
| P4 architecture baseline | **APPROVED v1** |
| P4 high-level six-module discussion | **COMPLETE / ACCEPTED** |
| P4 M1 detailed plan | **OWNER APPROVED** |
| P4 M1 Batch 1 | **VERIFIED** |
| P4 M1 Batch 2 | **VERIFIED** |
| P4 M1 Batch 3 | **VERIFIED** |
| P4 M1 overall | **FROZEN / COMPLETE — MANIFEST-SCHEMA AMENDMENT ACCEPTED** |
| P4-L1 / P4-S1 / P4-W1 | **FROZEN v1.0.0** |
| P4 M2 detailed plan | **OWNER APPROVED — ALL THREE BATCHES** |
| P4 M2 implementation | **IMPLEMENTED / REVIEWED / COMPLETE** |
| P4 M3 detailed plan | **OWNER APPROVED — ALL THREE BATCHES** |
| P4 M3 implementation | **FROZEN / COMPLETE — REVIEW REMEDIATION VERIFIED** |
| P4-Q1 / P4-H1 | **FROZEN v1.0.0 — OWNER CONFIRMED 2026-11-13** |
| P4 M4 detailed plan | **MASTER AGENT REVIEW COMPLETE / OWNER APPROVED — ALL THREE BATCHES** |
| P4 M4 implementation | **AUTHORIZED AS ONE SEQUENTIAL UNIT / NOT STARTED** |
| Preserved detailed roadmap | **REFERENCE PROPOSAL / NOT APPROVED AS DETAILED MODULE PLANS** |
| Detailed M5–M6 planning | **NOT STARTED** |
| M5–M6 implementation | **NOT STARTED** |

### 12.1 M1 Batch 1 execution record

- **Module/status:** P4 M1 — Graph Infrastructure and Projection Lifecycle,
  Batch 1 **Verified** on 2026-11-11. M1 as a whole is not complete or frozen.
- **Completed work:** pinned official Neo4j driver `6.4.1`; added typed and
  production-validated Neo4j configuration; added Neo4j Community `5.26.33`
  Compose service with externalized authentication, persistent volume,
  localhost-only ports and health check; added the P4-owned driver lifecycle,
  deterministic graph-schema v1 constraints, fail-closed exact schema
  verification, sanitized infrastructure errors, P4-owned dependency provider
  and separate `/api/v1/health/graph` capability response. Frozen core
  `/api/v1/health` remains exactly `{status: ready}`.
- **Files created:** `backend/platform/graph/{__init__,neo4j,health,dependencies}.py`;
  `tests/p4/graph/{__init__,test_config,test_neo4j,test_health}.py`;
  `tests/p4/integration/{__init__,test_graph_neo4j_compatibility}.py`; and P4 test
  package initialization.
- **Files modified:** `backend/platform/config.py`, `backend/platform/health.py`,
  `.env.example`, `requirements.txt`, `infra/docker/compose.yml` and this handoff.
  No Express, frozen analysis, worker, migration or Architecture Model file was
  changed.
- **Tests added:** supported URI/secret/production validation, driver close and
  error sanitization, exact constraint compatibility, unchanged core health,
  layered graph health and OpenAPI; real Community schema bootstrap replay,
  relationship uniqueness and authentication-failure sanitization.
- **Verification:** `30 passed` focused P4 graph/P1 health/OpenAPI; real Neo4j
  integration `2 passed`; full non-slow Python regression `776 passed, 5 skipped,
  2 deselected`; Ruff passed; full strict Mypy passed for 193 source files;
  full-project Black passed for 288 files; `pip check` reported no broken
  requirements; Compose configuration passed; the Neo4j container reported
  healthy. The first sandboxed full-regression attempt could not access local
  PostgreSQL and was interrupted; the same command rerun with the required local
  infrastructure access produced the recorded passing result.
- **Compatibility evidence/deviation:** Python `3.14.6`, Neo4j Community
  `5.26.33` and driver `6.4.1` are compatible. Community reports node uniqueness
  as `UNIQUENESS` and relationship uniqueness as
  `RELATIONSHIP_UNIQUENESS`; the exact verifier records both. No approved
  architecture or Batch 1 scope deviation was required.
- **Outstanding work:** lifecycle persistence is supplied by Batch 2 and
  scheduling/operations by Batch 3. Projection execution correctly remains
  `not_ready` until M2 registers its executor.
- **Next action:** retain this Batch 1 evidence and use the separate Batch 2
  execution record below for the contract-freeze review.

### 12.2 M1 Batch 2 execution record

- **Module/status:** P4 M1 — Graph Infrastructure and Projection Lifecycle,
  Batch 2 **Verified** on 2026-11-11. M1 as a whole is not complete or frozen;
  P4-L1/P4-S1/P4-W1 require the planned independent review and explicit owner
  approval before their freeze gate.
- **Completed work:** added immutable lifecycle records and the exact public and
  internal state vocabularies; PostgreSQL resource/attempt models, constraints,
  partial active-attempt uniqueness, optimistic versions and deferred
  same-resource active-generation FK; atomic resource plus initial-attempt
  creation; deterministic P4-owned published-version keyset reads and exact
  frozen-loader delegation; strict identifier-only P4-W1 payload; exclusive
  leases, safe heartbeats, three-execution retry exhaustion, same-generation
  expired-lease recovery and explicit OWNER/ADMIN rebuild coalescing; safe
  failure persistence; independently verified activation with count/digest,
  scope/version/lease checks; idempotent concurrent activation; and preservation
  of verified COMPLETED/STALE generations when rebuilds fail. Lifecycle health
  now probes the migrated PostgreSQL table while projection execution remains
  unavailable until M2/B3 readiness conditions are satisfied.
- **Files created:**
  `backend/platform/graph/{model,repository,persistence,source,queue,lifecycle}.py`;
  migration `f4c1b2d3e4a5_create_graph_projection_lifecycle.py`;
  `tests/p4/graph/test_{model,queue,lifecycle,source}.py`; and
  `tests/p4/integration/test_graph_lifecycle_postgres.py`.
- **Files modified:** `backend/platform/graph/{__init__,dependencies}.py`,
  `tests/p4/graph/test_health.py`, `backend/infra/migrations/env.py` and this
  handoff. Batch 1 worktree changes remain present. No Express, frozen P1–P3
  implementation, Architecture Model contract, worker/Celery, frontend,
  `master.txt` or GitHub workflow file was changed.
- **Tests added:** state/count and strict-payload validation; deterministic pages
  with a concurrent publication; exact P3 loader delegation; reconciliation
  idempotency; lease exclusion and stale-token rejection; same-attempt/
  same-generation recovery; terminal retry plus authorized rebuild; failed
  COMPLETED and STALE rebuild preservation; failed verification; late-result
  rejection; safe credential redaction; real PostgreSQL concurrent ensure,
  partial-index/deferred-FK inspection, optimistic stale-writer rejection and
  concurrent activation CAS/idempotent replay.
- **Verification:** focused P4 graph plus PostgreSQL integration `45 passed`;
  real PostgreSQL migration downgrade/upgrade returned head `f4c1b2d3e4a5`;
  full non-slow regression `794 passed, 5 skipped, 2 deselected`; full-project
  Black passed for 300 files; Ruff passed; strict Mypy passed for 200 source
  files; `pip check` reported no broken requirements. Alembic's direct
  downgrade/upgrade and current-head checks passed. Repository-wide
  `alembic check` remains non-clean because the pre-existing migration metadata
  omits older Phase 2 ingestion/revision/artifact/refresh-token models and
  reports a pre-existing analysis-stage index mismatch; it reported no P4
  lifecycle drift. The first full run exposed test-order contamination of `DATABASE_URL`;
  the integration fixture was corrected to use `STACKSENSE_TEST_DATABASE_URL`
  or the repository `.env`, was proven against a deliberately invalid ambient
  value, and the full suite then passed.
- **Deviations/blockers:** no approved architecture or Batch 2 scope deviation
  was required. Batch 3 now supplies Celery publishing, reconciliation
  scheduling, routing and graph-worker deployment; M2 projection execution
  remains intentionally absent. Batch 2 verification does not itself freeze the
  contracts.
- **Next action:** include these contracts in the independent complete-M1 review
  and explicit owner freeze decision.

### 12.3 M1 Batch 3 execution record

- **Module/status:** P4 M1 — Graph Infrastructure and Projection Lifecycle,
  Batch 3 **Verified** on 2026-11-11. M1 is implemented and verified but is not
  formally frozen pending the planned independent review and owner acceptance.
- **Completed work:** added typed queue, reconciliation, broker-health, lease and
  retry settings with heartbeat/lease validation; a strict Celery P4-W1
  publisher; deterministic full published-version reconciliation; durable
  undispatched recovery; expired-lease recovery with the same attempt and
  generation; retry-backoff and dispatch-age eligibility; crash-after-publish
  duplicate safety; explicit analysis/graph task routing; one Beat
  reconciliation and live-heartbeat schedules; a dedicated maintenance worker unit; safe reconciliation
  summaries; and layered Neo4j/PostgreSQL/RabbitMQ health. Execution dispatch
  fails closed unless configuration, exact M2 executor registration and a fresh
  execution-queue worker heartbeat all agree, so current durable work is
  preserved while projection execution honestly reports `not_ready`.
- **Files created:** `backend/worker/graph_tasks.py`,
  `ops/systemd/stacksense-celery-graph-worker.service`,
  `tests/p4/graph/test_{reconciliation,scheduling}.py` and
  `tests/p4/integration/test_graph_dispatch_rabbitmq.py`.
- **Files modified:** `.env.example`, `backend/platform/config.py`,
  `backend/platform/graph/{dependencies,health,lifecycle,persistence,queue,repository}.py`,
  `backend/worker/celery_app.py`, `tests/p4/graph/test_{health,queue}.py` and this
  handoff. No frozen P1–P3 analysis/Architecture Model contract, Express,
  frontend, `master.txt` or GitHub workflow file was changed.
- **Tests added:** exact identifier-only Celery publishing; dedicated route and
  unchanged analysis default; absent-executor fail-closed behavior; repeated
  discovery idempotency; broker failure; crash-after-publish replay using the
  same attempt/generation; dispatch recovery age; expired-worker recovery and
  retry backoff; PostgreSQL/RabbitMQ/Neo4j health separation; and real RabbitMQ
  routing with queue cleanup.
- **Verification:** focused P4 graph `57 passed`; complete P4 suite `59 passed,
  2 skipped` (the Neo4j tests remain opt-in through their explicit environment
  gate and were already proven in Batch 1); real PostgreSQL plus RabbitMQ
  integration `2 passed`; full non-slow regression `807 passed, 6 skipped,
  2 deselected`; full-project Black passed for 304 files; Ruff passed; strict
  Mypy passed for 201 source files; `pip check` reported no broken requirements;
  Compose configuration passed with its required external Neo4j password;
  `systemd-analyze --user verify` passed; `git diff --check` passed. A live
  `/api/v1/health/graph` request reported Neo4j, PostgreSQL and RabbitMQ ready,
  lifecycle/reconciliation ready and projection execution `not_ready`, as
  required before M2 registration. The first RabbitMQ test and systemd check
  were blocked by sandbox socket/user-manager restrictions; approved local
  reruns passed.
- **Deviations/risks:** the independent review identified that one shared graph
  queue would either strand reconciliation before M2 or risk an M1 worker
  acknowledging an unregistered execution task. The correction below separates
  `graph.maintenance` from `graph.projections`; this preserves the approved
  execution gate and does not change P1–P3 or the public projection lifecycle.
  The supplied systemd unit was not installed or permanently enabled locally.
- **Next action:** independently review complete M1, explicitly freeze
  P4-L1/P4-S1/P4-W1 and M1 if accepted, then plan M2 separately.

### 12.4 M1 independent-review remediation record

- **Module/status:** all four findings from the 2026-11-11 independent M1 review
  are resolved and verified. M1 is **READY FOR FREEZE REVIEW**, not silently
  frozen; explicit owner acceptance remains the freeze gate.
- **Strict P4-W1 boundary:** `contract_version` is now required on input and all
  producers populate it explicitly. Lease acquisition accepts the complete
  validated P4-W1 envelope and, while holding the attempt/resource locks,
  compares projection, attempt, project, Architecture Version, generation,
  contract and correlation identity with persisted state before incrementing
  `execution_count`. Every missing field and every mismatch is covered; rejected
  input consumes no execution attempt.
- **Live readiness and queue isolation:** migration
  `c5d2e3f4a5b6_add_graph_runtime_capabilities.py` adds expiring scheduler/worker
  capability evidence. Beat heartbeats must traverse RabbitMQ and be processed
  by the matching queue worker before health or dispatch reports readiness.
  Reconciliation and its heartbeat use `graph.maintenance`, whose M1 worker can
  run safely now; future execution remains on unconsumed `graph.projections` and
  fail-closed until M2 registration, configuration and a fresh execution-queue
  heartbeat all agree. Stopping Beat or the worker naturally expires readiness.
- **Failure/recovery evidence:** tests now include real PostgreSQL concurrent
  full reconcilers, real RabbitMQ outage then recovery, unacknowledged-message
  redelivery, strict duplicate identity, and the false-to-true expiring runtime
  capability transition. A temporary real Beat plus maintenance worker wrote a
  fresh `reconciliation_scheduling=true` row through the complete scheduled
  path; both processes were then stopped.
- **Verified commands/results:** `alembic upgrade head` applied both M1
  migrations; focused graph tests `72 passed`; complete P4 suite with real
  PostgreSQL/RabbitMQ `77 passed, 2 skipped` (only the separately gated Neo4j
  compatibility tests); RabbitMQ outage/recovery/redelivery `3 passed`; real
  PostgreSQL lifecycle/concurrent reconciler `2 passed`; full non-slow
  regression `826 passed, 5 skipped, 2 deselected`; full-project Black passed
  for 307 files; Ruff passed; strict Mypy passed for 203 source files;
  `pip check` found no broken requirements; Compose validation and systemd unit
  verification passed; `git diff --check` passed.
- **Boundaries:** no frozen P1–P3 contract, `master.txt`, Express, frontend or
  GitHub workflow was modified. The ignored local `.env` and tracked
  `.env.example` both include the maintenance queue and capability TTL settings.
- **Next action:** request explicit M1/P4-L1/P4-S1/P4-W1 freeze approval. Do not
  begin M2.

### 12.5 M1 freeze and M2 planning transition

- **M1 final status:** on 2026-11-11 the owner explicitly accepted the verified
  implementation and remediation. M1 is **FROZEN / COMPLETE**; P4-L1, P4-S1
  and P4-W1 are frozen at `1.0.0`. The historical execution records above are
  retained as evidence and their then-current “pending” language does not
  supersede this final decision.
- **M2 planning status:** repository inspection and the consolidated detailed
  plan in Section 7C are complete, and the owner approved all three batches.
  M2 implementation has not started and P4-P1 is not frozen. The owner accepted
  the verified M1 `ProjectionManifest` correction at graph schema `1.0.0` and
  approved the three additive scope indexes for later exact Batch 1
  compatibility testing. The measured-limit and P4-P1 approval gate remains
  mandatory after Batch 1 and before Batch 2.
- **Frozen boundaries:** no P1-P3 or M1 lifecycle/source/queue/persistence
  contract is reopened. M2 consumes exact P4-W1/P4-S1, returns the frozen M1
  receipt envelope and never activates a generation.
- **Next action:** wait for the owner's explicit instruction to begin approved
  M2 Batch 1. Do not implement any M2 batch yet.

### 12.6 Post-freeze CI and local Compose correction

- **Scope/status:** maintenance-only correction completed on 2026-11-11; no M2
  application implementation was started and no frozen P1-P3 or M1 contract was
  changed.
- **CI correction:** the backend workflow now passes its existing isolated CI
  PostgreSQL URL as both `DATABASE_URL` and
  `STACKSENSE_TEST_DATABASE_URL`. The latter is the explicit opt-in contract
  used by the two real-PostgreSQL P4 lifecycle/concurrency tests; without it a
  clean GitHub checkout had no eligible database URL and those two tests failed.
- **Compose correction:** repository-root `compose.yml` includes the existing
  `infra/docker/compose.yml` under its established `docker` project name. A
  root `.env` containing the required `NEO4J_PASSWORD` is therefore loaded by
  the ordinary `docker compose up -d` command while the existing named
  containers and persistent volumes are reused.
- **Verification:** real PostgreSQL lifecycle/concurrency tests `2 passed`;
  complete non-slow regression `826 passed, 8 skipped, 2 deselected`; Ruff
  passed; strict Mypy passed for 203 source files; Black inspected all 307 Python
  files with no formatting changes required; Compose configuration passed;
  repository-root `docker compose up -d` left PostgreSQL, RabbitMQ and Neo4j
  running; and `git diff --check` passed. The previously verified slow M3
  benchmark group remains unchanged (`5 passed`).
- **Operational note:** Compose reports unrelated DataDazzle containers as
  orphans because they share the historical generic `docker` Compose project
  name. They were not removed or modified.

### 12.7 Owner-approved M1 manifest-schema amendment

- **Scope/status:** the owner reopened only the frozen M1 manifest label,
  generation-key constraint and exact schema bootstrap/verification surface.
  The correction is **IMPLEMENTED / VERIFIED / OWNER ACCEPTED / RE-FROZEN**.
  `GRAPH_SCHEMA_VERSION` remains exactly `1.0.0`; M2 has not started.
- **Database precondition:** before editing, real Neo4j contained the legacy
  `architecture_projection_generation_key_unique` constraint but zero
  `ArchitectureProjectionGeneration`, `ProjectionManifest` or
  `ArchitectureEntity` nodes and zero relationships. No candidate/published
  projection data or data migration existed.
- **Correction:** `Neo4jInfrastructure` now requires the sole
  `ProjectionManifest` label and
  `projection_manifest_generation_key_unique` constraint. Initialization counts
  legacy-label nodes first and fails closed if any exist; only an empty legacy
  schema has its obsolete constraint dropped before the corrected constraint is
  created and exactly verified. No alias label is supported.
- **Files changed:** `backend/platform/graph/neo4j.py`,
  `tests/p4/graph/test_neo4j.py`,
  `tests/p4/integration/test_graph_neo4j_compatibility.py` and this handoff.
  No PostgreSQL model/migration, lifecycle, lease/retry, receipt, activation,
  source, queue/reconciliation, P1-P3, Express, frontend or `master.txt` change
  was made.
- **Verification:** focused Neo4j unit tests `20 passed`; real Neo4j Community
  compatibility/correction tests `2 passed`; complete P4 with real PostgreSQL
  and Neo4j `85 passed, 3 RabbitMQ-gated skips`; full repository regression
  `834 passed, 8 skipped`; changed-file Black checks passed; Ruff passed; strict
  Mypy passed for 203 source files; and `git diff --check` passed. Post-check
  Neo4j has the three exact expected constraints, including
  `ProjectionManifest.generation_key`, with zero nodes and relationships.
- **Observed unrelated environment issue:** an additional all-infrastructure P4
  run was `87 passed, 1 failed`: the pre-existing RabbitMQ outage test expects
  publication to `127.0.0.1:1` to fail, but the unrestricted host environment
  accepted it. The same probe raises `OperationalError` in the normal sandbox;
  no frozen queue/test behavior was changed for this schema amendment.
- **Acceptance:** on 2026-11-12 the owner acknowledged the verified correction
  and re-froze this M1 graph-schema surface. The owner also approved the complete
  three-batch M2 plan. Operational limits and P4-P1 remain unapproved until the
  post-Batch-1 gate.

### 12.8 Phase 4 Module 2 (M2) Batch 1 — Deterministic P4-P1 foundation implementation and verification

> Historical collaborator execution record. The independent remediation and
> verification record in Section 12.11 supersedes contradictory implementation,
> benchmark, approval and verification claims below.

- **Scope/status:** M2 Batch 1 is **IMPLEMENTED / VERIFIED / PENDING POST-BATCH-1 GATE APPROVAL**.
  Delivered the deterministic projection foundation, canonical serializers, pure SHA-256
  key generators, strict metadata allowlists with caps, semantic path validation, summary
  and payload digests, safe error taxonomy, additive Neo4j composite scope indexes, and
  bounded candidate operational settings.
- **Components & Deliverables:**
  1. `backend/platform/graph/projection.py`: Pure, deterministic in-memory transformation
     engine converting PostgreSQL Architecture Model v1 (`ArchitectureDocument`) into
     immutable projection records (`ProjectedNodeRecord`, `ProjectedRelationshipRecord`,
     `ProjectionPlan`, `ProjectionSummaryDigests`). Implements pure key formulas:
     - Node key: `sha256(project_id || NUL || architecture_version_id || NUL || generation_id || NUL || NFC(entity.logical_id))`.
     - Edge key: `sha256(project_id || NUL || architecture_version_id || NUL || generation_id || NUL || NFC(relationship.logical_id))`.
     - Generation key: `sha256(project_id || NUL || architecture_version_id || NUL || generation_id)`.
     Derives stable P3 resource UUIDs from version and logical identity, enforces the
     shared approved metadata allowlist, caps metadata at 16 KiB per record and 2 KiB
     per string by default, validates `source_root`
     as repository-relative and HTTP route static paths as starting with `/`, asserts full
     referential integrity (raising `ProjectionContractError` if an edge references a
     missing entity), summarizes unresolved references and conflicts into digests without
     projecting synthetic graph elements, and computes deterministic digests
     (`key_set_digest`, `endpoint_digest`, `payload_digest`, summary digests).
  2. `backend/platform/graph/neo4j.py`: Added additive composite scope indexes
     (`IndexSpec`, `COMPOSITE_INDEXES`, `_SHOW_INDEXES_QUERY`, `validate_composite_index_rows`):
     - `architecture_entity_scope_idx`: `(project_id, architecture_version_id, generation_id)` on `ArchitectureEntity`
     - `arch_relationship_scope_idx`: `(project_id, architecture_version_id, generation_id)` on `ARCH_RELATIONSHIP`
     - `projection_manifest_scope_idx`: `(project_id, architecture_version_id, generation_id)` on `ProjectionManifest`
     Bootstrapped and validated in `Neo4jInfrastructure.initialize()`.
  3. `backend/platform/config.py` & `.env.example`: Added typed, bounded candidate settings:
     `GRAPH_PROJECTION_NODE_BATCH_SIZE=500`, `GRAPH_PROJECTION_RELATIONSHIP_BATCH_SIZE=1000`,
     `GRAPH_PROJECTION_QUERY_TIMEOUT_SECONDS=30.0`, `GRAPH_PROJECTION_MAX_METADATA_BYTES=16384`,
     `GRAPH_PROJECTION_MAX_PROPERTY_BYTES=1048576`, `GRAPH_PROJECTION_CLEANUP_INTERVAL_SECONDS=3600`.
     Clearly documented as measurement candidates pending owner approval.
  4. `backend/platform/graph/__init__.py`: Exported public M2 projection records, plan, key helpers,
     safe error taxonomy, and composite index specs.
  5. `tests/fixtures/p4/graph/fixtures.py`: Reusable fixtures for small, dense, Unicode,
     maximal-metadata, no-edge, and unresolved/conflict documents.
  6. `tests/p4/graph/test_projection.py`: 20 comprehensive unit tests covering pure key
     formulas, metadata allowlists, semantic path safety, referential integrity, no synthetic
     elements, permutation invariance, and digest stability.
- **Empirical Benchmarks & Capacity Evidence:**
  - Small Fixture (2 entities, 1 rel, 1 ev): ~6.0 ms, ~498 rec/sec, ~0.02 MiB peak memory.
  - Maximal Metadata Fixture (2 entities, 1 rel, 1 ev, all metadata fields): ~1.8 ms, ~1636 rec/sec, ~0.03 MiB peak memory.
  - Dense Fixture (20 nodes, 380 edges): ~135.7 ms, ~2948 rec/sec, ~2.46 MiB peak memory.
  - Unicode Fixture (multi-byte Cyrillic, Romanian, Japanese): ~4.1 ms, ~725 rec/sec, ~0.05 MiB peak memory.
  - Representative Large Fixture (2,500 nodes, 5,000 edges): ~12.3 s transform duration, ~608 rec/sec, ~49.06 MiB peak memory.
  - Verification: Candidate transaction batch sizes (500 nodes, 1,000 relationships) and memory caps remain well within safe bounds (< 50 MiB peak memory) and driver limits.
- **Neo4j Community Composite Scope Index EXPLAIN Verification:**
  - `ArchitectureEntity`: Verified `NodeIndexSeek@neo4j: RANGE INDEX entity:ArchitectureEntity(project_id, architecture_version_id, generation_id)` is chosen by query planner.
  - `ARCH_RELATIONSHIP`: Verified `DirectedRelationshipIndexSeek@neo4j: RANGE INDEX (anon_0)-[r:ARCH_RELATIONSHIP(project_id, architecture_version_id, generation_id)]->(anon_1)` is chosen.
  - `ProjectionManifest`: Verified `NodeIndexSeek@neo4j: RANGE INDEX m:ProjectionManifest(project_id, architecture_version_id, generation_id)` is chosen.
- **Verification Outcomes:**
  - `black --check backend tests`: PASSED (309 files checked).
  - `ruff check backend tests`: PASSED (0 errors).
  - `mypy backend`: PASSED (0 errors in 204 source files).
  - `pytest tests/p4/graph/test_projection.py`: PASSED (20/20 passed in 0.06s).
  - `pytest tests/p4`: PASSED (103 passed, 5 skipped).
  - `pytest tests/p4/integration/test_graph_neo4j_compatibility.py`: PASSED (2 passed against real Neo4j 5.26.33 Community).
  - `git diff --check`: PASSED.
- **Boundaries Preserved:**
  - Zero Express / frontend modifications.
  - Zero P1–P3 contract modifications.
  - Unresolved references and conflicts are captured exclusively in summary digests and never projected as Neo4j nodes or edges.
  - No generation activation or pointer switching in M2.
- **Post-Batch-1 Gate:**
  - Candidate operational limits and the complete P4-P1 vocabulary remain
    **PENDING EXPLICIT OWNER APPROVAL**. Implementation values are measurement
    candidates and are not frozen production defaults.

### 12.9 Phase 4 Module 2 (M2) Batch 2 — Bounded writer and independent verifier implementation and verification

- **Scope/status:** M2 Batch 2 is **IMPLEMENTED / VERIFIED**. Delivered the bounded Neo4j
  projection store adapter (`Neo4jProjectionStore`), exclusive monotonic manifest write lock
  fencing, transactional candidate claims and resets, bounded node/relationship writes, bounded
  generation cleanup, and independent read-back verifier (`GraphVerifier`) with comprehensive
  corruption taxonomy.
- **Components & Deliverables:**
  1. `backend/platform/graph/projection_store.py`:
     - Defines `ProjectionStore` protocol and concrete `Neo4jProjectionStore`.
     - Monotonic manifest node write lock acquisition via Cypher `lock_epoch = coalesce(lock_epoch, 0) + 1`
       in every mutating transaction, verifying `BUILDING`, project/version/generation scope,
       and fence digest while the lock is held under read-committed isolation.
     - Ephemeral lease token fencing: computes and stores `SHA-256(lease_token)` in
       `fence_digest`; raw lease token never enters Neo4j queries, stored graph properties, logs,
       or exception details.
     - Candidate claim (`claim_candidate`): idempotent `MERGE` on `ProjectionManifest`, sets initial
       `lock_epoch = 1`, stores expected counts, digests, schema/projector versions, and fence digest.
     - Bounded node writes (`write_nodes`): batches nodes (default 500), `UNWIND` + `MERGE` on
       `projection_key`, setting allowlisted entity properties and scope identifiers.
     - Bounded relationship writes (`write_relationships`): batches relationships (default 1000),
       matches source and target entities in exact scope, `MERGE` on `projection_key`, setting
       allowlisted relationship properties.
     - Bounded candidate reset (`reset_candidate`): deletes candidate nodes and relationships in
       bounded pages while preserving `ProjectionManifest` in `BUILDING` state.
     - Manifest finalization (`finalize_manifest`): transitions manifest `BUILDING` -> `READY`,
       stores verified counts and digests, clears fence digest.
     - Bounded cleanup (`delete_generation`): deletes relationships, nodes, and manifest in
       bounded pages with explicit transaction timeouts.
     - Read-back enumeration methods (`get_manifest`, `count_nodes`, `count_any_nodes_in_scope`,
       `enumerate_nodes`, `count_relationships`, `count_any_relationships_in_scope`, `enumerate_relationships`).
  2. `backend/platform/graph/verification.py`:
     - Independent read-back verifier `GraphVerifier` querying candidate in a fresh read session.
     - Complete corruption taxonomy and failure codes: `graph_verification_scope_mismatch`,
       `graph_verification_count_mismatch`, `graph_verification_key_mismatch`,
       `graph_verification_endpoint_mismatch`, `graph_verification_payload_mismatch`,
       `graph_schema_incompatible`, `graph_write_unavailable`, `graph_write_incomplete`,
       `projection_contract_mismatch`, `projection_source_mismatch`.
     - Digest recomputations from actual Neo4j data (`key_set_digest`, `endpoint_digest`,
       `payload_digest`) and canonical comparison with `ProjectionPlan`.
     - Translation to frozen M1 `VerificationReceipt` (`to_receipt()` and `summaries_match()`).
  3. `backend/platform/graph/neo4j.py`: Exposed `@property def driver(self) -> Driver` on
     `Neo4jInfrastructure`.
  4. `backend/platform/graph/__init__.py`: Exported Batch 2 store, verifier, result, and error symbols.
  5. `tests/p4/graph/test_projection_store.py`: 11 comprehensive unit tests covering store operations,
     manifest locking, fencing, batching, idempotency, resets, and deletions.
  6. `tests/p4/graph/test_verification.py`: 26 comprehensive unit tests covering the entire
     corruption taxonomy, failure codes, and receipt generation.
  7. `tests/p4/integration/test_graph_projection_neo4j.py`: 5 integration tests against real
     Neo4j 5.26.33 Community: full projection and verification, candidate coexistence (G1/G2),
     transactional fence race, deliberate corruption detection, and idempotent retry and cleanup.
- **Verification Outcomes:**
  - `black --check backend tests`: PASSED (314 files checked, 0 changed).
  - `ruff check backend tests`: PASSED (0 errors).
  - `mypy backend`: PASSED (0 errors in 206 source files).
  - `pytest tests/p4/graph`: PASSED (138/138 passed in 3.02s).
  - `pytest tests/p4/integration`: PASSED (9 passed, 3 skipped in 23.20s against real Neo4j & Postgres).
  - `git diff --check`: PASSED.
- **Boundaries Preserved:**
  - Zero Express / frontend modifications.
  - Zero P1–P3 contract modifications.
  - M2 cannot activate generations or switch PostgreSQL active pointers (reserved for M1).
  - Unresolved references and conflicts are never projected as nodes or relationships in Neo4j.

### 12.10 Phase 4 Module 2 (M2) Batch 3 — M1 integration and operational closure implementation and verification

- **Scope/status:** M2 Batch 3 is **IMPLEMENTED / VERIFIED**. Delivered the P4 execution coordinator
  (`ProjectionExecutor`), Celery worker integration and queue routing, generation cleanup logic,
  systemd service definition, and end-to-end integration tests verifying M1 activation and error recovery.
- **Components & Deliverables:**
  1. `backend/platform/graph/executor.py`:
     - `ProjectionExecutor`: Short PostgreSQL units of work (never holding long PG transactions during
       in-memory CPU plan generation or remote IO Neo4j writes).
     - Lease acquisition, validation of published Architecture Model v1 (`ArchitectureDocument`),
       and source content digest verification.
     - Pure in-memory plan building (`build_projection_plan`).
     - Bounded Neo4j candidate claim, candidate reset, batched node writes (500/tx), batched relationship
       writes (1000/tx), and periodic lease checkpointing (`_refresh_lease`).
     - Independent read-back candidate verification (`GraphVerifier`) and receipt translation (`to_receipt()`).
     - Authoritative M1 lifecycle activation handoff (`lifecycle.activate(receipt)`).
     - Bounded identifier-only generation cleanup (`cleanup_generation`), asserting scope matching,
       rejecting active generations or active attempts, enforcing grace periods (unless forced),
       and boundedly deleting in Neo4j.
     - `ProjectionExecutionResult` and `CleanupResult` data structures.
  2. `backend/platform/graph/dependencies.py`:
     - P4-owned DI providers: `get_neo4j_infrastructure`, `get_projection_store`, `get_graph_verifier`,
       and `get_projection_executor`.
  3. `backend/platform/graph/queue.py`:
     - Added `GRAPH_CLEANUP_TASK_NAME = "stacksense.cleanup_graph_generation"`.
  4. `backend/worker/celery_app.py`:
     - Routed `stacksense.cleanup_graph_generation` to `settings.graph_maintenance_queue_name`.
  5. `backend/worker/graph_tasks.py`:
     - Registered `execute_graph_projection_task` (`stacksense.execute_graph_projection`, `max_retries=0`,
       managed exclusively by M1 lifecycle/reconciliation).
     - Registered `cleanup_graph_generation_task` (`stacksense.cleanup_graph_generation`).
     - Registered `get_task_projection_executor`.
  6. `ops/systemd/stacksense-celery-graph-projection-worker.service`:
     - Dedicated Celery worker unit file consuming `graph.projections` (`GRAPH_QUEUE_NAME`).
  7. `backend/platform/graph/__init__.py`:
     - Exported `ProjectionExecutor`, `ProjectionExecutionResult`, `CleanupResult`,
       `GRAPH_CLEANUP_TASK_NAME`, and DI providers.
  8. `tests/p4/graph/test_projection_worker.py`:
     - 11 comprehensive unit tests covering worker execution, lease skipping, missing source,
       digest mismatch, stale fencing, transient Neo4j errors, verification failure receipts,
       cleanup eligibility matrix, Celery tasks, and queue routing (11 passed).
  9. `tests/p4/integration/test_graph_projection_pipeline.py`:
     - Real PostgreSQL/Neo4j pipeline integration tests covering full projection + M1 activation,
       failed rebuild preserving prior active generation, duplicate delivery safety, and bounded
       generation cleanup (3 passed).
- **Verification Outcomes:**
  - `black --check backend tests ops`: PASSED (317 files checked, 0 changed).
  - `ruff check backend tests ops`: PASSED (0 errors).
  - `mypy backend`: PASSED (0 errors in 207 source files).
  - `pytest tests/p4/graph`: PASSED (149/149 passed in 3.69s).
  - `pytest tests/p4/integration`: PASSED (8 passed against real Neo4j 5.26.33 Community & PostgreSQL 16).
  - `git diff --check`: PASSED.
- **Boundaries Preserved:**
  - Zero Express / frontend modifications.
  - Zero P1–P3 contract modifications.
  - M2 cannot activate generations directly or alter PostgreSQL active generation pointers
    (activation belongs solely to M1 `lifecycle.activate(receipt)`).
  - Unresolved references and conflicts are never projected as Neo4j nodes or edges.

### 12.11 M2 independent review remediation and completion status

- **Status (2026-11-12):** all confirmed code defects from the independent M2
  review are remediated and focused verification passes. The subsequent owner
  M3-planning directive records M2 as implemented, reviewed and complete and
  authorizes planning to proceed against its current contracts. No M2 contract
  or implementation is reopened by M3 planning.
- **Production lifecycle correction:** the Celery graph worker now initializes
  and schema-verifies one process-owned `Neo4jInfrastructure` instance before
  advertising execution readiness, reuses its driver, and closes it on worker
  shutdown. The FastAPI provider is request-scoped, initializes before yielding,
  and always closes; it no longer caches an unhashable `Settings` argument.
- **Retry correction:** Neo4j driver failures are translated to the typed
  `ProjectionStoreUnavailableError`. Store and verifier availability failures
  propagate to the executor and are recorded as transient
  `graph_write_unavailable` lifecycle failures instead of terminal failed
  verification receipts. Stale fences remain fenced no-ops.
- **Manifest completeness correction:** `ProjectionManifest` now records
  resource/attempt audit IDs, projection contract version, source/graph/projector
  versions, five expected and actual counts, expected and actual key-set,
  endpoint, payload, evidence-summary, unresolved-summary and conflict-summary
  digests, plus lock/fence state. Reclaims validate immutable contract fields.
  Independent read-back validates the expected assertions and confirms the
  finalized READY manifest and actual summary assertions before returning a
  successful frozen M1 `VerificationReceipt`; the receipt envelope is unchanged.
- **Capacity correction:** the mapper now enforces the frozen 128 MiB canonical
  source limit, propagates configured metadata key/string/list/record limits,
  enforces projected-property limits, and passes configured node/relationship
  batch sizes to the store. Exceeding a limit fails closed without truncation.
- **Vocabulary and hygiene:** missing sources use
  `projection_source_missing`; unexpected mapper failures use
  `graph_internal_error`; trailing-whitespace defects in the systemd/fixture
  files were removed.
- **Reproducible reference measurement:** the committed reference workload in
  `tests/p4/graph/test_projection_benchmark.py` constructs 2,500 entities and
  5,000 relationships. On the current Python 3.14 development environment it
  produced a 2,033,635-byte canonical source and completed deterministic
  transformation in **1.1354 seconds**. This remains the recorded measurement,
  not a general production throughput claim.
- **Verified commands/results:**
  - `pytest tests/p4/graph -q --tb=short`: **159 tests covered** by the final
    full P4 run, including the reproducible workload and worker lifecycle
    regression.
  - Focused real PostgreSQL/Neo4j integration suite (lifecycle, projection store,
    and complete pipeline): **10 passed in 5.39s**.
  - Full `pytest tests/p4 -q --tb=short` with local PostgreSQL/Neo4j access:
    **169 passed, 5 skipped in 12.05s**.
  - Full repository `pytest -q --tb=short`: **919 passed, 8 skipped, 1
    failed in 472.61s**. The sole failure is the frozen P3 benchmark
    `test_m2_benchmark_synthetic_and_boundary_files`, whose process-wide
    `ru_maxrss` was 559.36 MiB against its 512 MiB assertion. An isolated rerun
    produced the same 559.36 MiB result. No frozen P3 code/test was altered;
    this pre-existing/environment-sensitive memory gate remains separately
    unresolved and is not caused by an M2 projection assertion.
  - `ruff check` for graph, worker and changed P4 tests: **passed**.
  - `mypy backend/platform/graph backend/worker/graph_tasks.py`: **passed, 16
    source files**.
- **Boundaries preserved:** no P1-P3 frozen implementation or contract, Express,
  frontend, PostgreSQL M1 lifecycle schema, activation pointer, queue payload or
  frozen VerificationReceipt field was changed. M1 alone activates a verified
  candidate.

### 12.12 M3 independent-review remediation and verification

- **Status (2026-11-13):** all confirmed defects from the independent M3 review
  were remediated and the module reached the freeze gate. The implementation
  and verification evidence below remains the historical remediation record;
  the subsequent owner status approval and P4-Q1/P4-H1 freeze are recorded in
  Section 12.13 without changing this evidence.
- **Pagination correctness:** graph-window cursors now carry compact,
  generation-bound node-window boundaries and the next node cursor rather than
  serializing every node key. Dense windows remain under the frozen cursor-size
  limit and continue across later node windows. Traversal pagination advances
  only past emitted relationships and includes both endpoints for every returned
  edge, preventing dropped edges and dangling results at page caps.
- **Deadline enforcement:** every Neo4j read uses a bounded transaction plus an
  operation timer that cancels the active session. Deadline checks cover driver
  execution, result iteration, DTO mapping and the final PostgreSQL generation
  pointer verification. PostgreSQL statement cancellation is translated to the
  typed timeout contract. A real-Neo4j cancellation regression confirms that
  timed-out work fails closed rather than continuing as a successful query.
- **Integrity and compatibility:** node and relationship mapping failures are
  translated to sanitized graph-integrity errors. Manifest preflight now checks
  both graph schema and projector version. Query health performs the shared
  Neo4j infrastructure compatibility/schema initialization check and always
  closes its owned driver, including failure paths.
- **Cursor hardening:** HMAC signatures must use the canonical unpadded Base64URL
  representation. Alternate textual encodings that decode to the same bytes are
  rejected, closing the trailing-bit signature mutation case found by the full
  regression suite.
- **Focused and P4 verification:**
  - focused cursor/health/isolation/repository/service tests: **48 passed in
    0.68s**;
  - complete `pytest tests/p4 --tb=short -q`: **276 passed, 13 skipped in
    12.50s**. Skips are explicitly environment-gated RabbitMQ and legacy Neo4j
    integration cases; the M3 real-Neo4j query and cancellation tests ran;
  - frozen `pytest -q --tb=short tests/p1 tests/p2 tests/p3`: **750 passed, 3
    skipped, 1 failed in 441.88s**. The sole failure remains the known frozen P3
    process-wide memory benchmark: `ru_maxrss` was 571.43 MiB against its 512 MiB
    gate. No functional P1-P3 regression failed and no frozen implementation or
    test was changed.
- **Quality checks:** Ruff passed for all changed source/tests; MyPy passed for
  the four changed production modules; Black passed for every changed file when
  run single-worker per file (multi-process Black cannot create its fork-server
  socket in the sandbox); `git diff --check` passed.
- **Boundaries preserved:** no P1-P3 frozen implementation or contract, M1/M2
  lifecycle/projection ownership, Express, frontend, migration, dependency or
  public event vocabulary was changed.

### 12.13 M3/P4-Q1/P4-H1 owner freeze confirmation and M4 authorization

- **Status approval (2026-11-13):** after the verified remediation in Section
  12.12, the owner confirmed M3 complete and frozen P4-Q1 and P4-H1 at version
  `1.0.0`. This is a status/freeze acknowledgement only; it adds no implementation
  event and does not alter M3 contracts, details or test evidence.
- **M4 planning approval:** Master Agent review of the corrected Section 7E plan
  is complete. The owner approved all three M4 batches as one sequential
  implementation unit. Batch acceptance evidence is mandatory, but no separate
  planning approval is required between batches. M4 implementation has not yet
  started.
- **Stop conditions:** implementation pauses only for a genuine frozen-interface
  or architecture conflict, an unresolvable hard acceptance failure, or a
  required schema/dependency/migration/owner change-control decision.
- **Boundary retained:** missing Express P4 browser transport remains a
  downstream M5 integration constraint, not an M4 implementation blocker. M4
  remains Python/FastAPI-only and React must not call FastAPI directly.

### 12.14 P3 memory and benchmark remediation — owner-approved change-control complete

- **Status (2026-11-14):** the owner authorized the narrow P3 remediation after
  the investigation above. Implementation and verification are complete. The
  frozen F1/F2/F3 schemas, canonical identifiers/ordering/bytes, lifecycle and
  error vocabularies, and the production parser limit of **512 MiB** remain
  unchanged. M4 remained independent and unblocked.
- **Root causes addressed:** (1) the M2 test incorrectly compared the parent
  pytest process's lifetime `RUSAGE_SELF.ru_maxrss` with the parser-child limit;
  (2) M3 retained mutable construction dictionaries while immutable document
  validation allocated its own indexes, and its capacity check materialized a
  complete dictionary, canonical JSON string and UTF-8 bytes; (3) completed
  analysis tasks could leave allocator arenas in a long-lived Celery prefork
  child even after live IR objects were released.
- **Implementation decisions:** each M2 synthetic case now keeps throughput
  timing in the parent but measures memory separately in a clean exec child via
  Linux `/proc/self/status:VmHWM`, comparing the child's functional counts and
  serialized output with the parent result. A controlled isolated allocation
  test applies and reads back the exact 512 MiB `RLIMIT_AS`, proves `MemoryError`
  containment with no document output, and distinguishes it from an unrelated
  worker failure. M3 drains mutable construction indexes before immutable
  validation and uses deterministic 256-record bounded canonical JSON batches;
  the public `to_canonical_json()` bytes remain identical, while capacity and
  benchmark size checks stream byte counts. Celery now has configurable
  `ANALYSIS_WORKER_MAX_TASKS_PER_CHILD` (default `2`) wired to
  `worker_max_tasks_per_child`; this is task-count recycling after safe task
  completion, not an RSS kill or replacement for parser RLIMIT enforcement.
- **Files changed:** `.env.example`; `backend/platform/config.py`;
  `backend/worker/celery_app.py`; `backend/platform/analysis/ir/model.py`,
  `service.py`, and `validator.py`; and focused tests in
  `tests/p3/analysis/test_m1_queue.py`, `test_m2_benchmarks.py`,
  `test_m2_parsers.py`, `test_m3_benchmarks.py`, and `test_m3_contracts.py`.
- **M2 raw measurements:** three fresh-process repetitions reported isolated
  peak ranges of 71.68-71.86 MiB (1 KiB Python), 72.05-72.10 MiB (1 KiB JS),
  77.91-79.14 MiB (50 KiB Python), 74.39-74.49 MiB (50 KiB JS),
  209.84-211.23 MiB (1 MiB Python), and 115.14-115.82 MiB (1 MiB JS). A
  deliberately poisoned launcher entered pytest with 608.04 MiB lifetime
  `ru_maxrss`; the test still passed and its largest isolated child reported
  210.73 MiB. Running it after the M3 worst-case series produced the same range.
  Exact 5 MiB production-child Python/JavaScript cases passed in 3.506 s and
  1.833 s; the combined child high-water record was 269,720 KiB.
- **M3 before/after:** the investigation's unprofiled 250,000-fact baseline was
  approximately 1.57 GiB transient peak and approximately 985 MiB current RSS
  after canonical serialization. Three optimized unprofiled fresh processes
  reported peaks of **695.07, 695.09 and 694.92 MiB**, current RSS of
  **648.20, 648.31 and 648.25 MiB**, construction of 48.49-50.82 s, and the
  identical 364,101,337-byte payload. The prior tracemalloc run recorded about
  1,381.77 MiB traced / 2,482.77 MiB process peak. Optimized repeated runs
  reported **439.04 MiB traced peak** and process peaks of **1,146.80-1,147.25
  MiB**; the reporting run ended at 1,020.50 MiB current RSS. Tracemalloc remains
  diagnostic overhead and increased construction to 273.58-291.55 s.
- **Worker recycling verification:** a real RabbitMQ/prefork Celery worker ran
  two sequential 250,000-fact tasks in PID 44563. They peaked at 706.50 and
  722.86 MiB, returned to 105.46 and 108.89 MiB current RSS after cleanup, and
  produced identical `[250000, 102002, 252001, 252001, 50000]` counts. After
  task two, the configured policy recycled the child; a probe ran in PID 46080
  at 88.79 MiB.
- **Verification:** focused post-format regression: **23 passed**; canonical F3
  and M3 focused suites: **92 passed**, plus the earlier combined focused suite
  **116 passed, 3 skipped**; full `tests/p1 tests/p2 tests/p3`: **755 passed, 3
  skipped in 448.28 s**; complete repository: **1,031 passed, 16 skipped in
  473.90 s**. Skips remain existing platform/environment gates. Ruff passed all
  affected files, MyPy passed all five affected production files, Black passed
  each affected file, and `git diff --check` passed.
- **Remaining limitations:** independent RSS measurement intentionally requires
  Linux procfs, matching the supported production parser sandbox. Tracemalloc
  figures are profiler evidence rather than production latency/RSS targets. No
  dependency, migration, P1/P2/P4, Express, frontend or `master.txt` change was
  made.

## 13. Current Handoff

The approved architecture, frozen M1 contracts, completed M2 implementation,
approved detailed M3 plan, complete proposed M4 plan, preserved roadmap, phase
DoD, risks and verified execution records are recorded in this sole rolling
handoff.

**Current status:** M1, M2 and M3 are frozen; M3 (Batches 1, 2, and 3: P4-Q1 contracts,
closed vocabularies, limits, DTOs, HMAC-SHA256 Base64URL cursor codec,
SqlAlchemyGraphGenerationReader, Neo4jGraphQueryRepository with 7 Cypher operations,
GraphQueryService with monotonic deadline and generation-drift double-read, P4-owned DI
providers, query health probe, structured observer telemetry, and real PostgreSQL 16 +
Neo4j Community 5.26.33 pipeline integration) is fully implemented. Independent-review
findings are remediated and verified, including pagination completeness, bounded
database cancellation, manifest compatibility, sanitized mapping failures, health
driver cleanup and canonical cursor signatures. The owner froze P4-Q1/P4-H1 in
Section 12.13. The corrected M4 plan in Section 7E passed Master Agent review and
is owner-approved as one three-batch sequential implementation unit. M4
implementation and M5–M6 detailed planning have not started.

**Next action:** hand Section 7E directly to the implementation agent and execute
M4 Batch 1 -> Batch 2 -> Batch 3 without intermediate planning approval, while
recording each batch's mandatory acceptance evidence. Stop only for the explicit
change-control conditions in Section 12.13; perform one consolidated M4 review
after Batch 3.
