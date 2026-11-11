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

Last reconciled: 2026-11-11
Current branch: `feature_mannan`

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
high-level discussion of all six modules is complete. Detailed M1 planning is
owner-approved, and all three M1 batches are implemented and verified. The
earlier detailed roadmap remains a preserved proposal for comparison. M1 now
awaits independent review and explicit owner freeze approval; all later modules
remain unstarted.

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
| P4 — Architecture Graph & Exploration | **M1 FROZEN / M2 DETAILED PLAN AWAITING REVIEW** | Neo4j infrastructure, PostgreSQL lifecycle, activation, durable reconciliation, RabbitMQ routing and operational supervision are frozen; deterministic projection/verification is planned but not implemented. |
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
6. Nodes are `ArchitectureEntity`; edges are `ARCH_RELATIONSHIP`; canonical
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
validates the conceptual six-module structure. M1 is now frozen and complete;
the repository-grounded detailed M2 proposal is recorded separately in Section
7C and awaits owner approval. The preserved roadmap in Section 7B remains the
high-level reference for modules that have not yet received detailed planning.

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

**Status: FROZEN / COMPLETE.** All three batches, the independent review and its
remediation are verified. On 2026-11-11 the owner explicitly accepted M1 and
froze P4-L1, P4-S1 and P4-W1. This section remains the implementation record;
M2 must consume these contracts without reopening M1 or changing P4 Baseline
v1.

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

Owner approval of this corrected detailed plan remains required. Three
conditional owner gates remain: exact driver pin after the compatibility spike;
any fallback if Community constraints or the P4-owned source adapter cannot meet
approved guarantees; and the later browser-transport decision if the completed
Express surface cannot carry P4 graph calls. The last gate is outside P4 M1–M4:
it cannot authorize an Express change by implication, and React cannot bypass it
by calling Python directly. None may be silently decided during implementation.

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
verification result. Manifest READY is written only after success; M1 validates
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

**Status: DETAILED PLAN COMPLETE — AWAITING OWNER REVIEW / IMPLEMENTATION NOT
STARTED.** This plan was prepared from the current `feature_mannan` worktree,
the approved P4 Baseline v1, frozen M1/P4-L1/P4-S1/P4-W1 implementation and the
actual frozen P3 Architecture Model. It does not authorize implementation or
freeze P4-P1.

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
5. `Neo4jInfrastructure` currently owns driver creation, connectivity and the
   three required uniqueness constraints for generation, node and relationship
   keys. It intentionally has no projection write/read API. No scope indexes or
   candidate data exist yet.
6. Celery already routes `stacksense.execute_graph_projection` to
   `graph.projections`, but no task is registered and dispatch remains disabled.
   The current systemd graph worker consumes only `graph.maintenance`; M2 needs
   a separate execution-queue consumer before capability heartbeats can become
   ready.
7. The M1 source, lifecycle and worker contracts are version `1.0.0`; Neo4j
   Community `5.26.33` with Python driver `6.4.1` is verified. M2 must emit these
   exact versions in P4-P1 and may not silently bump them.
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
5. The Neo4j adapter claims the candidate manifest with a lease-derived fence,
   resets only an interrupted inactive `BUILDING` generation when ownership has
   changed, then writes nodes and relationships in bounded transactions. Each
   query requires the current manifest fence and `BUILDING` state.
6. Between batches, the executor renews the M1 lease in a fresh PostgreSQL
   transaction. Lease loss stops further work; it never manufactures a failure
   result using a stale token.
7. The verifier opens a new Neo4j read session and derives actual records from
   Neo4j rather than writer counters. Only an exact match conditionally changes
   the internal manifest from `BUILDING` to `READY` and removes its fence.
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

One `ArchitectureProjectionGeneration` node holds only projection control and
summary data: generation key; project/version/generation IDs; resource/attempt
IDs for audit; source content and architecture-schema versions; graph schema,
contract and projector versions; `BUILDING|READY`; complete source counts;
expected and verified key-set/endpoint/payload digests; evidence-association,
unresolved and conflict summary digests; and the temporary lease-fence hash.
Operational timestamps may be recorded but are excluded from semantic digests.
No raw lease token, credential, source text, unresolved descriptor or conflict
detail is stored.

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
- **Summary digests:** SHA-256 of the frozen canonical P3 representations for
  evidence associations, unresolved relationships and conflicts. They prove
  intentional treatment without creating synthetic graph elements or storing
  potentially sensitive literal details.

Expected digests come only from the immutable plan. Actual key, endpoint and
payload digests are rebuilt only from a new Neo4j read session plus the manifest
summary properties. The algorithms are pure and golden-vector tested across
processes, input permutations, Unicode and empty collections.

### E. Neo4j storage, writes and concurrency

M2 adds a narrow projection store; no caller supplies Cypher. Every statement is
a fixed `LiteralString` with parameters, an explicit transaction timeout and
exact project/version/generation predicates.

The candidate claim stores `SHA-256(lease_token)` as an ephemeral fence; the raw
unpredictable token never enters Neo4j, logs or task payloads. Every reset/write/
finalize query first matches the generation manifest in `BUILDING` state and the
current fence. A replacement lease atomically replaces the manifest fence before
bounded cleanup/rebuild, causing all stale-worker write queries to affect zero
rows. `READY` is immutable: later writes cannot match it. A new rebuild uses a
new generation and never mutates the prior verified generation.

Write order is manifest, nodes, then relationships. Node batches use
`UNWIND` plus `MERGE` on `projection_key` and replace the complete allowlisted
property map. Relationship batches first match both endpoint keys in the exact
scope, then `MERGE` the directed relationship and replace its properties. Every
batch returns matched/written counts; zero-fence, missing endpoint or count
mismatch aborts. Retrying the same deterministic generation creates no
duplicates. A replacement execution first fences the old worker, then deletes
the interrupted candidate's relationships and nodes in bounded pages before
rebuilding; it never uses unbounded `DETACH DELETE`.

The existing uniqueness constraints remain mandatory. Efficient exact-scope
enumeration also requires additive composite RANGE indexes on
`ArchitectureEntity(project_id, architecture_version_id, generation_id)`,
`ARCH_RELATIONSHIP(project_id, architecture_version_id, generation_id)` and
`ArchitectureProjectionGeneration(project_id, architecture_version_id,
generation_id)`. M2 verifies their exact shape at executor startup. These are
physical access-path additions only: labels, relationship type, graph contract
and `GRAPH_SCHEMA_VERSION = 1.0.0` remain unchanged. Because M1 is frozen, this
additive-index treatment is an explicit owner approval gate; otherwise it must
follow formal graph-schema change control rather than being silently applied.

### F. Independent verification and P4-P1

Verification never trusts `MERGE` summaries. In a fresh read session it:

1. finds exactly one manifest by generation key and checks exact project,
   version, generation, source, contract, schema and projector fields;
2. enumerates all scoped nodes and relationships in deterministic key pages;
3. checks actual counts and `count == count(DISTINCT projection_key)` in addition
   to relying on constraints;
4. compares exact sorted key sets, detecting missing and extra records;
5. proves every relationship endpoint exists, is an expected node in the same
   generation, has the expected source-to-target direction and canonical kind;
6. rejects unexpected labels/types, scope leakage, duplicate P3 UUID/logical ID,
   unsupported properties and manifest/source-summary mismatch;
7. reconstructs actual records from Neo4j and independently recomputes all
   three P4-P1 digests; and
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

Batch 1 benchmarks the existing roadmap candidates of 500 nodes and 1,000
relationships per transaction against small, dense and maximum representative
fixtures. Recommended initial per-query timeout is 30 seconds, cleanup page is
1,000 records and cleanup grace is 24 hours. Proposed safe metadata limits are
64 UTF-8 bytes per key, 2 KiB per string, 64 values per list, 16 KiB total
allowlisted metadata and 1 MiB total projected properties per node/relationship.
These values are candidate defaults, not silently approved limits. The measured
results and canonical metadata inventory must receive owner approval before
Batch 2 writer freeze; reducing source content is not an allowed optimization.

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
| MODIFY | `backend/platform/graph/neo4j.py` | Add only a safe shared session/driver boundary needed by the M2 store; retain existing M1 initialization, constraints and graph schema version unchanged. No projection semantics enter this infrastructure file. |
| MODIFY | `backend/platform/graph/dependencies.py` | Compose M2 mapper/store/verifier/executor through P4-owned DI without touching frozen analysis DI. |
| MODIFY | `backend/platform/graph/__init__.py` | Export only reviewed M2 public ports/contracts. |
| MODIFY | `backend/worker/graph_tasks.py` | Register exact `execute_graph_projection`, lease-checkpoint execution, safe summaries and identifier-only cleanup task. |
| MODIFY | `backend/worker/celery_app.py` | Route cleanup to `graph.maintenance`; execution routing already exists and is preserved. |
| MODIFY | `backend/platform/config.py`, `.env.example` | Typed bounded batch/timeout/metadata/cleanup settings; dispatch default remains fail-closed until the execution worker is deployed. Local `.env` is not a planning artifact. |
| CREATE | `ops/systemd/stacksense-celery-graph-projection-worker.service` | Dedicated `graph.projections` consumer with existing concurrency/prefetch settings; the frozen M1 maintenance worker remains separate. |
| CREATE | `tests/p4/graph/test_projection.py` | Golden keys/digests, order/Unicode/empty determinism, mapping, allowlist, limits and no-synthetic-element tests. |
| CREATE | `tests/p4/graph/test_projection_store.py` | Fixed-query, batching, idempotency, fencing, endpoint and bounded cleanup adapter tests. |
| CREATE | `tests/p4/graph/test_verification.py` | Independent missing/extra/duplicate/scope/direction/endpoint/version/digest corruption matrix. |
| CREATE | `tests/p4/graph/test_projection_worker.py` | Payload/acquire/source/heartbeat/retry/receipt/stale/concurrent/cleanup task behavior and queue isolation. |
| CREATE | `tests/p4/integration/test_graph_projection_neo4j.py` | Real Community candidate coexistence, indexes, writes, verification, corruption, retry and cleanup. |
| CREATE | `tests/p4/integration/test_graph_projection_pipeline.py` | Real PostgreSQL/RabbitMQ/Celery/Neo4j execution through M1 activation and failed-rebuild preservation. |
| CREATE | `tests/fixtures/p4/graph/` | Small, no-edge, dense, Unicode, maximal-metadata, unresolved/conflict, historical and deliberate-corruption fixtures. |

No Express, frontend, P1-P3, frozen M1 model/lifecycle/persistence/source/queue
contract, `master.txt`, GitHub workflow or Python analysis pipeline file is
modified. No new Python dependency or PostgreSQL/Alembic migration is planned.
Neo4j's additive indexes are the only physical schema addition and require the
approval stated above.

### J. Three implementation batches

#### Batch 1 — Deterministic P4-P1 foundation

Implement immutable records, strict mapper, exact keys, P3 public UUID reuse,
metadata allowlist, canonical serializers/digests, config validation and
fixtures. Benchmark candidate batch/timeout/property caps and validate additive
index support on Neo4j Community. Freeze the measured limits and physical-index
treatment before writer work.

Acceptance: permutation and cross-process runs produce byte-identical records
and digests; G1/G2 keys differ while canonical IDs match; all existing entity/
relationship kinds map without semantic invention; unresolved/conflict inputs
produce summaries only; unknown/unsafe/oversized metadata fails without
truncation; golden vectors cover Unicode and empty sets; no frozen contract/file
changes occur.

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
generations.

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
6. a replaced lease fences the expired worker before reset/write and READY is
   immutable;
7. independent read-back detects every required omission, duplicate, extra,
   endpoint, scope, version, count and digest corruption;
8. failed/partial candidates never become active or query-visible, while a
   failed rebuild preserves the prior verified generation and public state;
9. P4-P1 exactly satisfies frozen M1 receipt/activation checks and M1 alone
   switches the pointer;
10. retry exhaustion, duplicate delivery, broker/Neo4j loss and cleanup follow
    frozen M1 semantics without new public states/events;
11. no raw source, secrets, credentials, lease token, unsafe metadata or host
    path enters Neo4j/logs/errors;
12. focused, corruption, concurrency, real-infrastructure, full regression,
    formatting, lint, typing and service-unit checks pass with recorded results;
13. P1-P3 and frozen M1 files/contracts remain unchanged except the explicitly
    approved additive Neo4j infrastructure surface/index treatment; and
14. P4-P1, measured limits and the M2 execution record receive independent
    review and explicit owner freeze approval before M3 begins.

### M. Risks and owner decisions required before implementation

1. **Additive Neo4j indexes (required):** approve the three exact scope indexes
   as compatible physical additions under graph schema `1.0.0`, with no frozen
   M1 semantic change. If not approved, formal graph-schema change control is
   required before M2 can meet bounded exact read-back at scale.
2. **Candidate operational limits (required before Batch 2):** approve or revise
   the benchmarked node/edge batch sizes, 30-second per-query timeout, metadata/
   record caps, 1,000-record cleanup page and 24-hour cleanup grace. The plan
   proposes starting values; evidence, not convenience, freezes them.
3. **P4-P1 vocabulary (required at Batch 2 freeze):** approve the manifest
   `BUILDING|READY` states, generation-key formula, strict metadata allowlist,
   three canonical digest definitions and safe failure-code set. These are M2
   contract choices, not changes to M1's receipt envelope.

No unresolved contradiction with `master.txt`, the 17 approved P4 decisions or
frozen P1-P3/M1 contracts was found. The only pre-implementation approval needed
for Batch 1 itself is the additive-index treatment; measured operational values
and the full P4-P1 vocabulary have explicit later freeze gates and cannot be
silently assumed.

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
4. **Detailed M2 planning — COMPLETE / AWAITING OWNER REVIEW.** Section 7C is
   the proposed implementation baseline. Detailed M3–M6 planning is not started.
5. **Implementation — M1 FROZEN / COMPLETE.** The owner explicitly accepted M1
   and P4-L1/P4-S1/P4-W1 after independent review/remediation. No instruction
   has authorized M2–M6 implementation.

| Work item | Status |
|---|---|
| P1–P3 | **FROZEN / COMPLETE** |
| P4 architecture baseline | **APPROVED v1** |
| P4 high-level six-module discussion | **COMPLETE / ACCEPTED** |
| P4 M1 detailed plan | **OWNER APPROVED** |
| P4 M1 Batch 1 | **VERIFIED** |
| P4 M1 Batch 2 | **VERIFIED** |
| P4 M1 Batch 3 | **VERIFIED** |
| P4 M1 overall | **FROZEN / COMPLETE** |
| P4-L1 / P4-S1 / P4-W1 | **FROZEN v1.0.0** |
| P4 M2 detailed plan | **COMPLETE — AWAITING OWNER REVIEW** |
| P4 M2 implementation | **NOT STARTED** |
| Preserved detailed roadmap | **REFERENCE PROPOSAL / NOT APPROVED AS DETAILED MODULE PLANS** |
| Detailed M3–M6 planning | **NOT STARTED** |
| M2–M6 implementation | **NOT STARTED** |

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
  plan in Section 7C are complete. M2 implementation has not started and P4-P1
  is not frozen. Plan approval, the additive Neo4j scope-index decision and the
  recorded Batch 1 measurement gate precede writer implementation.
- **Frozen boundaries:** no P1-P3 or M1 lifecycle/source/queue/persistence
  contract is reopened. M2 consumes exact P4-W1/P4-S1, returns the frozen M1
  receipt envelope and never activates a generation.
- **Next action:** owner reviews Section 7C and its three explicit approval
  groups. Do not begin M2 Batch 1 without approval.

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

## 13. Current Handoff

The approved architecture, frozen M1 and contracts, detailed M2 proposal,
preserved roadmap, phase DoD, risks and verified execution records are recorded
in this sole rolling handoff.

**Next action:** review and approve or revise Section 7C, including its additive
scope indexes, provisional measured-limit gate and P4-P1 vocabulary. Do not
begin M2 implementation, P4-P1 freeze or detailed M3–M6 planning without
separate explicit instruction.
