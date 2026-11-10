# PROJECT_CONTEXT.md — StackSense Engineering Context

Last reconciled: 2026-11-10
Current branch: `feature_mannan`

## 1. Project Overview

StackSense is a software repository intelligence and architecture analysis
platform. Express/MongoDB owns the platform plane: users, JWT authentication,
projects, project RBAC, repository registration, immutable revisions and
artifact metadata. Python/FastAPI/PostgreSQL owns the analysis plane: lifecycle,
execution, deterministic inspection/IR, canonical Architecture Models and
published analysis results. The services communicate only through authenticated
internal APIs and never read each other's databases.

Phase 3 M1/F1 through M4/Architecture Model v1 and M5 frontend integration are
implemented, independently reviewed, corrected, verified and frozen. M6
cross-service validation, security checks, performance verification and phase
closeout are complete. Phase 3 is **FROZEN / COMPLETE**.

### 1.1 Authoritative sources

- `master.txt`, especially Sections 9–12, 25.13, Appendices C/E/F/H.
- `docs/architecture/adr/0001-express-python-integration.md`.
- Frozen F1, F2, F3 and Architecture Model v1 contracts under
  `docs/architecture/contracts/`.
- Actual Express, FastAPI and React source and tests.

### 1.2 Verified repository state

- Branch: `feature_mannan`.
- The worktree contains the verified Phase 3 implementation and final remediation
  awaiting its completion commit. All existing changes must be preserved.
- React 18/Vite uses JavaScript/JSX, a small hash/path router in `App.jsx`, the
  central `apiClient.js`, `AuthContext`, feature services, and focused Vitest /
  React Testing Library coverage. There is no React Router, global state
  library, visualization dependency, ESLint or TypeScript configuration.
- Existing route pages are Landing, Auth, Projects Dashboard and Repository
  Detail. Repository Detail already exposes Ingestion, Revisions and Artifacts.
- The existing design is a responsive dark interface using tokens in
  `styles/index.css`, a 1200–1240px content width, `DashboardHeader`, dark
  elevated cards, cyan/indigo accents, status pills, tables, tabs, modals and
  shared accessible action menus.
- Vite sends `/api` only to Express on port 5000. Browser JWTs are Express
  credentials and cannot authenticate directly to FastAPI.
- FastAPI analysis and Architecture Model routes require `X-Service-Token` plus
  delegated actor, role and project headers. ADR-0001 requires Express to
  authenticate/RBAC-check users and relay those calls; browsers must never see
  the service credential.

## 2. Global Constraints

1. Preserve frozen `master.txt`, F1, F2, F3 and Architecture Model semantics.
2. Express remains the only browser-facing API and JWT/RBAC authority. FastAPI
   remains analysis authority. M5 may add the ADR-approved proxy/relay, not move
   analysis persistence or logic into Express.
3. Never expose internal service tokens, storage keys, raw source, tracebacks,
   credentials or unrestricted diagnostic details to the browser.
4. OWNER, ADMIN and DEVELOPER may create/cancel analyses; VIEWER is read-only.
   UI visibility is convenience only; Express and FastAPI both enforce access.
5. Frontend lifecycle state is derived from canonical backend states. It must
   retain `partial`, `timeout`, `cancel_requested` and
   `completed_with_warnings`; it must not invent backend state.
6. M5 displays the canonical relational Architecture Model. It must not create
   a graph projection, traversal API, Neo4j model, editable architecture truth,
   AI interpretation or Phase 4 dependency explorer.
7. Preserve the existing UI language and CSS system. Extend existing cards,
   tabs, tables, buttons, feedback, loading, empty and error patterns; do not
   redesign Landing, Auth, Dashboard or Repository workflows.
8. Reuse `apiClient.js`; add streaming capability without regressing its JWT
   refresh concurrency, 401 retry or session-invalidity behavior.
9. Collections use backend `limit`/`offset`; never fetch all Architecture Model
   rows to simulate pagination or a complete graph in browser memory.
10. M5 is JavaScript/JSX with centralized JSDoc contracts. A repository-wide
    TypeScript migration is out of scope.

## 3. Phase Index

| Module | Status | Concise retained outcome |
|---|---|---|
| M1/F1 | **FROZEN / COMPLETE v1.0.0** | PostgreSQL analysis/job/stage/event/diagnostic lifecycle, Celery execution, REST/SSE, cancellation and M1-owned recovery. |
| M2/F2 | **FROZEN / COMPLETE v1.0.0** | Deterministic inventory, detection, isolated Python/JS/TS/JSX/TSX parsing, framework enrichment and immutable non-persisted F2. |
| M3/F3 | **FROZEN / COMPLETE v1.0.0** | Deterministic parser-neutral IR, document-local lexical semantics, diagnostics, validation and immutable non-persisted F3. |
| M4 | **FROZEN / COMPLETE v1.0.0** | Canonical identity/model construction, validation, approved capacity limits, atomic publication and published-only query APIs. |
| M5 | **FROZEN / COMPLETE** | Express analysis gateway plus React initiation, lifecycle, findings, result exploration and bounded Architecture Model visualization; final UI remediation is verified. |
| M6 | **FROZEN / COMPLETE** | Cross-service/E2E, regression, security, production-build and performance validation completed; Phase 3 closed on 2026-11-10. |

### 3.1 M1–M4 verification retained

The 2026-11-09 independent review corrected artifact integrity, manifest
credential sanitization, static route semantics, retry timeout accounting, M3
lexical resolution and bounded M4 result queries. Verification: full non-slow
repository `731 passed, 3 skipped, 2 deselected`; real PostgreSQL integration
`3 passed`; M3/M4 capacity benchmarks `6 passed in 366.88s`; focused Ruff,
Black, Mypy, pip integrity and diff whitespace passed. The three skips are
Windows-only parser isolation checks on Linux. Frozen public vocabularies did
not change. Detailed normative behavior remains in the frozen contracts and
tests rather than being duplicated here.

## 4. Current Phase Plan — Phase 3 Module 5

**Status: FROZEN / COMPLETE.**

The owner approved the complete four-batch plan and all four decisions in §6.1
on 2026-11-09. The plan is now the implementation baseline. Material scope,
contract, page-count or batch changes require explicit change control; routine
execution evidence belongs in the ledger.

### 4.1 Objective and exact scope

M5 completes the Phase 3 user-visible vertical slice:

```text
Authenticated user
  -> repository revision
  -> start analysis
  -> lifecycle/status/progress/history
  -> deterministic diagnostics and completeness
  -> published Architecture Model summary
  -> bounded entity/relationship/evidence/conflict exploration
```

M5 owns the browser-facing Express-to-FastAPI delegation adapter, frontend API
contracts/services, analysis UI, basic canonical-model visualization and M5
tests. It does not own analysis execution, F2/F3 persistence, architecture
identity, graph projection, arbitrary graph traversal, diagrams, AI, reports or
editing published results.

### 4.2 Verified reuse and gaps

Reusable frontend:

- `App.jsx` route parsing/protected views.
- `DashboardHeader`, repository breadcrumb/header, tab and table patterns.
- `apiClient.js` token attachment, refresh rotation and structured `ApiError`.
- `useProjectRole` for role-derived visibility.
- `repositoryService`, `ingestionService.listRevisions/getRevision`, existing
  pagination, skeleton, retry, empty-state, feedback and modal styling.
- Global design tokens and responsive patterns in existing CSS.

Reusable backend:

- Express JWT authentication and `projectAuthorization` policy methods.
- FastAPI create/list/get/cancel/SSE lifecycle routes and frozen DTOs.
- M4 published version/entity/relationship/evidence/unresolved/conflict APIs.
- Structured `{error:{code,message,details}}` contract on both services.

Verified missing integration:

1. Express has no user-facing analysis proxy or SSE relay.
2. React has no analysis or architecture services, routes or pages.
3. FastAPI analysis history is project-scoped but cannot filter by repository,
   which makes correct repository history pagination impossible.
4. Diagnostics are persisted but have no public paginated query endpoint.
5. Architecture evidence is pageable, but selected-entity evidence cannot be
   queried directly without scanning evidence pages. The owner-approved
   additive `entity_id` filter closes this gap in B1.

### 4.3 Route/page inventory and page count

M5 creates **exactly two new route-level pages**, modifies one existing page,
and retains four existing pages. After M5 the application has **six route-level
pages total**.

| Route | Page | Action |
|---|---|---|
| `#/` | `LandingPage` | Retain. |
| `#/login`, `#/signup` | `AuthPage` | Retain. |
| `#/projects` | `ProjectsDashboardPage` | Retain; no M5 redesign. |
| `#/projects/:projectId/repositories/:repositoryId` | `RepositoryDetailPage` | Modify: add Analyses tab. |
| `#/projects/:projectId/repositories/:repositoryId/analyses/:analysisId` | `AnalysisDetailPage` | **Create.** |
| `#/projects/:projectId/repositories/:repositoryId/analyses/:analysisId/architecture` | `ArchitectureModelPage` | **Create.** |

`App.jsx` must match architecture and analysis routes before the existing broad
repository route so nested URLs are not swallowed by the repository match.
Start Analysis is a modal, not a third page.

### 4.4 Page layouts

All layouts reuse `DashboardHeader`, `.container`, repository breadcrumbs,
existing typography, cards, pills, buttons, tabs, tables and responsive rules.

#### A. Existing Repository Detail — new Analyses tab

```text
DashboardHeader
Projects > Project > Repository                         repository actions
Repository title / description / repository status
--------------------------------------------------------------------------
Ingestion | Revisions | Artifacts | Analyses

[ Analysis runs                                      (Start Analysis) ]
[ latest status ] [ revision ] [ architecture available ] [ last run ]

Filters: status                    Search analysis/revision
--------------------------------------------------------------------------
Status | Revision | Progress | Started | Completed | Architecture | Action
... paginated history rows ...                                  View ->
--------------------------------------------------------------------------
Previous                                                        Next
```

- Start button appears only for OWNER/ADMIN/DEVELOPER after role resolution.
- Start modal loads revisions, defaults to the latest revision, shows revision
  identifier/hash/file count, and has an optional collapsed Advanced section
  for include paths, exclude paths, max file size and timeout.
- VIEWER sees history and an explanatory read-only badge, never mutation UI.
- Empty state links users back to Revisions/Ingestion when no revision exists.

#### B. New Analysis Detail page

```text
DashboardHeader
Projects > Project > Repository > Analysis

[ status icon ] Analysis run <short id> [canonical status pill]   [Cancel]
Revision / created / elapsed / attempt                [View Architecture]

[ overall progress ] [ files analyzed ] [ warnings ] [ model version ]

Stage progress rail (8 ordered cards)
Input -> Inventory -> Language -> Framework -> Syntax -> IR -> Identity -> Model

Overview | Findings | Execution
Overview: configuration, completeness, timestamps, failure/partial explanation
Findings: diagnostics + published unresolved/conflict summaries with pagination
Execution: active job/attempt details and stage table
```

- REST is authoritative. SSE invalidates/refetches state; serialized polling is
  the fallback when streaming disconnects. Both stop at terminal state.
- Cancel is enabled only while queued/running and only for operator roles.
  `cancel_requested` shows a disabled "Cancellation requested" state, so a
  duplicate cancel request cannot be submitted.
- `timeout` and `partial` are shown as transitional canonical states, not
  terminal aliases. Completed-with-warnings remains visually distinct.
- Architecture CTA appears only when `published_version_id` exists; a completed
  analysis without a published pointer is displayed as an integrity error.

#### C. New Architecture Model page

```text
DashboardHeader
Projects > Project > Repository > Analysis > Architecture

Architecture Model v<sequence> [published]       digest / schema / published at
[ entities ] [ relationships ] [ evidence ] [ unresolved ] [ conflicts ]

Overview | Entities | Relationships | Evidence | Unresolved | Conflicts

Overview:
  Kind/status filters
  +-----------------------------------+-------------------------------+
  | bounded deterministic SVG map    | selected entity inspector     |
  | loaded entities/relationships    | name/kind/status/namespace    |
  | explicit "partial window" label  | metadata/evidence/source keys |
  +-----------------------------------+-------------------------------+

Data tabs:
Search/filter controls
paginated dark table
loading / empty / error / retry
Previous                                                     Next
```

- The SVG overview loads at most 100 entities and 100 relationships at once,
  draws only relationships whose endpoints are in the loaded entity window,
  and prominently labels the view as a bounded model window. It must never
  imply that omitted rows do not exist.
- Layout is deterministic: architectural tiers by kind, stable logical-ID
  ordering within each tier, static connectors, keyboard-selectable nodes and
  no force simulation. This is a direct visualization of canonical API rows,
  not a graph projection or Phase 4 traversal engine.
- Tables remain the complete paginated exploration surface. Unknown metadata is
  rendered only through a safe allowlist/structured key-value component; no
  `dangerouslySetInnerHTML`.
- On narrow screens the inspector stacks below the canvas and tables remain in
  an existing horizontal overflow wrapper.

### 4.5 Cross-service request flow and security

```text
React apiClient + Express JWT
  -> Express authenticate
  -> projectAuthorization.requireAccess/requireCreateAccess
  -> analysisGatewayService
       X-Service-Token      (server secret only)
       X-Actor-Id           (req.user.id)
       X-Actor-Role         (authoritative membership record)
       X-Project-Id         (validated request project)
       X-Correlation-Id     (generated/forwarded safe request ID)
  -> FastAPI delegated endpoint
  -> PostgreSQL analysis/model authority
```

Express must construct delegated headers; it never accepts them from the
browser. It validates UUIDs, repository/revision ownership for create, request
body size, pagination and supported filter values. Upstream structured 4xx
errors pass through after safe parsing. Network/timeout/invalid-upstream errors
become structured `502 analysis_service_error`, `503
analysis_service_unavailable`, or `504 analysis_service_timeout`; upstream HTML,
stack traces and secrets are never relayed.

The JSON gateway uses Node's existing runtime `fetch`/`AbortController` with a
bounded configurable timeout, so no HTTP-client package is required. SSE has a
separate connection timeout/idle policy, forwards only `text/event-stream`,
honors backpressure, and aborts the Python request when the browser disconnects.

### 4.6 Browser-facing API matrix

Express exposes the same resource shapes as FastAPI under the existing
`/api/v1` prefix. The browser never calls port 8000.

| Method and endpoint | Permission | Request/query | Response |
|---|---|---|---|
| `POST /analyses` | OWNER/ADMIN/DEVELOPER | `CreateAnalysisRequest` | `202 AnalysisResponse` |
| `GET /analyses` | Any member | `project_id`, approved `repository_id`, `limit`, `offset`, optional `status` | `AnalysisListResponse` |
| `GET /analyses/:analysisId` | Any member | `project_id` | `AnalysisResponse` |
| `POST /analyses/:analysisId/cancel` | OWNER/ADMIN/DEVELOPER | `project_id`; `CancelAnalysisRequest` | `AnalysisResponse` |
| `GET /analyses/:analysisId/events` | Any member | `project_id`, `after_sequence`; optional `Last-Event-ID` | SSE stream |
| `GET /analyses/:analysisId/diagnostics` | Any member | `project_id`, `limit`, `offset`, optional `severity`, `stage` | approved `AnalysisDiagnosticListResponse` |
| `GET /analyses/:analysisId/architecture` | Any member | `project_id` | `ArchitectureVersionResponse` |
| `GET /architecture-versions/:versionId` | Any member | `project_id` | `ArchitectureVersionResponse` |
| `GET /architecture-versions/:versionId/entities` | Any member | `project_id`, `limit`, `offset`, optional `kind`, `status` | `ArchitectureCollectionResponse<Entity>` |
| `GET /architecture-versions/:versionId/entities/:entityId` | Any member | `project_id` | `ArchitectureEntityResponse` |
| `GET /architecture-versions/:versionId/relationships` | Any member | `project_id`, `limit`, `offset`, optional `kind`, `status` | `ArchitectureCollectionResponse<Relationship>` |
| `GET /architecture-versions/:versionId/evidence` | Any member | `project_id`, `limit`, `offset`; approved optional `entity_id` | `ArchitectureCollectionResponse<Evidence>` |
| `GET /architecture-versions/:versionId/unresolved` | Any member | `project_id`, `limit`, `offset` | `ArchitectureCollectionResponse<Unresolved>` |
| `GET /architecture-versions/:versionId/conflicts` | Any member | `project_id`, `limit`, `offset` | `ArchitectureCollectionResponse<Conflict>` |

Existing supporting calls are reused unchanged:

- `GET /projects/:projectId`
- `GET /projects/:projectId/access`
- `GET /projects/:projectId/repositories/:repositoryId`
- `GET /projects/:projectId/repositories/:repositoryId/revisions?limit&offset`
- `GET /projects/:projectId/repositories/:repositoryId/revisions/:revisionId`

### 4.7 Request and response contracts

Contracts remain snake_case on the wire and are declared once with JSDoc in
`frontend/src/contracts/`. UUIDs and datetimes are JSON strings.

#### Analysis requests

```text
CreateAnalysisRequest {
  project_id: UUID
  repository_id: UUID
  revision_id: UUID
  include_paths?: string[]          // max 1000; each 1..4096 chars
  exclude_paths?: string[]          // max 1000; each 1..4096 chars
  max_file_size_bytes?: integer     // 1..50 MiB; default 5 MiB
  timeout_seconds?: integer         // 1..1800; default 1800
  idempotency_key?: string          // nonblank, max 255
}

CancelAnalysisRequest { reason?: string | null } // max 1000
```

The modal generates one UUID idempotency key per user submission and reuses it
for transport retries. A deliberate second analysis creates a new key.

#### Analysis responses

```text
AnalysisListResponse {
  items: AnalysisResponse[]; total: integer; limit: integer; offset: integer
}

AnalysisResponse {
  id; project_id; repository_id; snapshot_id: UUID
  status: created|queued|running|partial|completed|
          completed_with_warnings|failed|cancel_requested|cancelled|timeout
  configuration: object
  version: integer
  created_at; updated_at; started_at?; completed_at?: datetime
  completeness?: AnalysisCompletenessResponse
  published_version_id?: UUID
  error_code?: string; error_message?: string
  stages: AnalysisStageResponse[]
  active_job?: AnalysisJobResponse
}

AnalysisCompletenessResponse {
  analyzed_files_count; unsupported_files_count; failed_files_count;
  excluded_files_count: integer
  is_partial: boolean
  details: Record<string,string>
}

AnalysisStageResponse {
  id; analysis_id: UUID
  stage_name: input_validation|inventory|language_detection|
              framework_detection|syntax_extraction|ir_construction|
              identity_resolution|architecture_build
  status: pending|queued|running|completed|failed|skipped|cancelled
  order; processed_items; total_items; version: integer
  is_mandatory: boolean
  created_at; updated_at; started_at?; completed_at?: datetime
  error_code?: string; error_message?: string
}

AnalysisJobResponse {
  id; analysis_id: UUID
  status: pending|queued|running|retrying|completed|failed|cancelled
  attempt; max_attempts; version: integer
  worker_id?; heartbeat_at?; started_at?; completed_at?: string
  created_at; updated_at: datetime
  error_code?: string; error_message?: string
}

AnalysisDiagnosticResponse {
  id; analysis_id: UUID
  code; category; severity; scope; message; retryability: string
  created_at: datetime; stage?: string
  details: safe object
  artifact_id?: UUID; artifact_path?: string
  source_line?: integer; source_column?: integer
}

AnalysisDiagnosticListResponse {
  items: AnalysisDiagnosticResponse[]; total; limit; offset: integer
}
```

`AnalysisDiagnosticListResponse` is approved but does not yet exist. Express
must pass only the safe FastAPI DTO and must not expose internal exceptions.

#### SSE contract

```text
id: <monotonic sequence number>
event: analysis.created | analysis.queued | analysis.started |
       analysis.stage.started | analysis.stage.progress |
       analysis.stage.completed | analysis.stage.failed |
       analysis.stage.skipped | analysis.partial |
       analysis.cancel_requested | analysis.cancelled | analysis.timeout |
       analysis.completed | analysis.completed_with_warnings | analysis.failed
data: <sanitized JSON object>
```

The UI treats SSE as a notification and refetches `AnalysisResponse`; it never
derives canonical state solely by replaying event payloads.

#### Architecture responses

```text
ArchitectureVersionResponse {
  id; analysis_id; project_id; repository_id; snapshot_id: UUID
  sequence_number: integer
  architecture_schema_version; ir_schema_version; content_digest: string
  entity_count; relationship_count; evidence_count;
  unresolved_relationship_count; conflict_count: integer
  completeness: safe object
  published_at: datetime
}

ArchitectureEntityResponse {
  id: UUID; logical_id; kind; name; status: string
  namespace; evidence_ids; source_ir_keys: string[]
  metadata: safe object
}

ArchitectureRelationshipResponse {
  id: UUID; logical_id; kind; source_logical_id; target_logical_id; status: string
  evidence_ids; source_ir_keys: string[]; metadata: safe object
}

ArchitectureEvidenceResponse {
  id: UUID; logical_id; source_record_type; path: string
  artifact_id?: UUID; source_fact_key?: string; source_range?: safe object
  producer_id?; producer_version?; strength; polarity: string
  metadata: safe object
}

ArchitectureUnresolvedResponse {
  id: UUID; logical_id; kind; source_logical_id; target_descriptor;
  reason; status: string; evidence_ids; candidate_references: string[];
  metadata: safe object
}

ArchitectureConflictResponse {
  id: UUID; logical_id; conflict_type; subject_key: string
  evidence_ids: string[]; details: safe object
}

ArchitectureCollectionResponse<T> {
  items: T[]; total; limit; offset: integer
}
```

Entity kinds and relationship kinds come directly from Architecture Model v1;
the frontend maps them to labels/icons but preserves raw values. Findings are
not a new domain object: the Findings tab presents existing
`AnalysisDiagnosticResponse`, `ArchitectureUnresolvedResponse` and
`ArchitectureConflictResponse` in separate sections.

#### Error response

```text
ErrorResponse {
  error: { code: string; message: string; details: safe object }
}
```

401 follows the existing refresh flow. 403 preserves the session and shows a
permission message. 404 shows scoped not-found UI. 409 shows conflict/retry
guidance. 422 maps field details inline. Network/5xx errors preserve credentials
and expose retry without destructive state resets.

### 4.8 Frontend state and behavior

- `useAnalysisLiveStatus` owns one stream, one fallback timer and one in-flight
  REST request. It uses `AbortController`, exponential reconnect capped at 15s,
  serialized 3s polling fallback, terminal-state stop and unmount cleanup.
- History/filter offsets reset when project/repository/status changes.
- Analysis progress is derived from stage rows: completed terminal stages plus
  bounded `processed_items/total_items` for the active stage. Unknown totals
  show indeterminate progress rather than fabricated percentages.
- Architecture collections maintain independent offsets and errors per tab.
- Canvas selection uses logical IDs; data tables use stable resource UUIDs for
  route/API identity. Persistence IDs never replace logical IDs in semantics.
- Search is only client-side within the currently loaded page unless a backend
  search/filter parameter exists; the UI labels that scope.
- Every async region has loading, empty, structured error and retry states.
- Mutations prevent duplicate submissions and announce result through existing
  status/alert patterns.

### 4.9 Implementation batches

#### Batch 1 — Secure analysis gateway and contract completion

Objective: establish the browser-safe Express delegation boundary and the two
minimum FastAPI read-query additions.

- Add Express configuration, gateway, validation, routes/controllers and SSE
  relay for every endpoint in §4.6.
- Use authoritative project membership to construct delegated role headers.
- Verify project/repository/revision chain for create and exact project scope for
  every read/mutation.
- Add the owner-approved optional `repository_id` to FastAPI analysis listing
  and repository query.
- Add the owner-approved paginated/filterable diagnostic listing owned by M1.
- Add the owner-approved M4 `entity_id` evidence collection filter.

Acceptance: browser JWT succeeds without exposing the service token; outsider
and cross-project access fails; Viewer reads but cannot create/cancel; upstream
failures remain structured/sanitized; SSE disconnect aborts upstream; JSON calls
time out; existing Python/Express contracts remain green.

#### Batch 2 — Frontend contracts, services and repository analysis history

- Add contract modules, `analysisService`, `architectureService` and the minimal
  streaming extension to `apiClient`.
- Add Analyses tab, history/status filters, pagination and Start Analysis modal.
- Reuse revision APIs, `useProjectRole`, existing form/dialog/table patterns and
  unchanged repository metadata/ingestion workflows.

Acceptance: operator can create one analysis for an immutable revision with a
stable idempotency key; Viewer cannot see mutation controls; history is correctly
repository-filtered/paginated; the run appears without page reload; validation,
403, 409, 422, network and 5xx feedback are handled.

#### Batch 3 — Analysis lifecycle, progress and findings page

- Add route parsing, `AnalysisDetailPage`, live-status hook, status/progress,
  stage rail, completeness, execution and findings components.
- Integrate SSE invalidation with bounded polling fallback and cancellation.
- Load published unresolved/conflicts only when an Architecture Version exists.

Acceptance: every canonical state has an intentional mapping; reconnect never
creates duplicate timers/requests; terminal state stops background work;
findings paginate independently; a published run links to its exact model.

#### Batch 4 — Architecture Model page, visualization and M5 closure

- Add Architecture page, model summary, deterministic SVG window, inspector and
  five paginated data tabs.
- Add supported filters, safe metadata, keyboard selection, responsive behavior
  and accessible status/error feedback.
- Complete cross-service/frontend regression and E2E verification.

Acceptance: only published scoped models render; the canvas identifies its
bounded window; tables provide complete offset navigation; no graph projection,
traversal, AI or editing is introduced; build/tests/vertical slice pass.

### 4.10 File-level implementation specification

Paths labeled **proposed** do not currently exist.

#### Express

| Path | Action and responsibility |
|---|---|
| `express/src/config/analysisConfig.js` | **Create.** Validate analysis base URL, service secret, JSON timeout and SSE policy; fail closed outside test. |
| `express/src/services/analysisGatewayService.js` | **Create.** Construct delegated headers, bounded JSON requests, safe errors and upstream SSE connection. |
| `express/src/middleware/analysisValidate.js` | **Create.** UUID, body, pagination/filter and project/repository validation. |
| `express/src/controllers/analysisController.js` | **Create.** Thin lifecycle/history/diagnostics/SSE handlers; no persistence. |
| `express/src/controllers/architectureController.js` | **Create.** Thin published-result handlers. |
| `express/src/routes/analysisRoutes.js` | **Create.** Authenticated lifecycle routes. |
| `express/src/routes/architectureRoutes.js` | **Create.** Authenticated published-model routes. |
| `express/src/routes/index.js` | Modify; register both routers. |
| `express/.env.example` | Modify; document approved `ANALYSIS_API_BASE_URL`, `ANALYSIS_INTERNAL_API_SECRET_KEY`, timeouts. |
| `express/tests/unit/analysisGatewayService.test.js` | **Create.** Headers, timeout, sanitization, abort, safe errors. |
| `express/tests/integration/analysisProxyApi.test.js` | **Create.** JWT, RBAC, isolation, request/response/SSE contract. |

#### FastAPI/PostgreSQL — narrow M1/M4 query change control only

| Path | Action and responsibility |
|---|---|
| `backend/api/v1/analyses.py` | Modify after approval; accept `repository_id`, expose diagnostics list. |
| `backend/platform/analysis/application/dto.py` | Modify; add immutable diagnostic collection DTO. |
| `backend/platform/analysis/application/lifecycle_service.py` | Modify; scoped history and diagnostic reads. |
| `backend/platform/analysis/repositories/analysis_repo.py` | Modify; optional repository filter on list port. |
| `backend/platform/analysis/infra/analysis_repository.py` | Modify; bounded PostgreSQL predicate/count. |
| Diagnostic repository port/adapter | Modify; bounded list/count with severity/stage filters. |
| `backend/api/v1/architecture.py` and M4 query repository/service | Optional only if entity-scoped evidence filtering is approved. |
| M1 API/lifecycle/repository tests | Modify; filters, pagination, RBAC, isolation. |
| `tests/p3/api/test_m4_architecture_api.py` | Optional evidence-filter coverage. |

No lifecycle transition, F1 field, event vocabulary, worker, M2, M3, model
builder, publication or database migration change is planned.

#### Frontend

| Path | Action and responsibility |
|---|---|
| `frontend/src/App.jsx` | Modify; exact ordered analysis/architecture routes. |
| `frontend/src/contracts/analysisContracts.js` | **Create.** Shared JSDoc lifecycle/diagnostic/SSE contracts/constants. |
| `frontend/src/contracts/architectureContracts.js` | **Create.** Shared JSDoc model contracts/vocabulary labels. |
| `frontend/src/services/apiClient.js` | Modify minimally; authenticated streaming path sharing refresh rules. |
| `frontend/src/services/analysisService.js` | **Create.** Lifecycle/history/cancel/diagnostic/event operations. |
| `frontend/src/services/architectureService.js` | **Create.** Published version/collection operations. |
| `frontend/src/hooks/useAnalysisLiveStatus.js` | **Create.** Single SSE/reconnect/poll lifecycle. |
| `frontend/src/pages/RepositoryDetailPage.jsx` | Modify; add Analyses tab. |
| `frontend/src/pages/AnalysisDetailPage.jsx` | **Create.** Lifecycle/findings/execution composition. |
| `frontend/src/pages/ArchitectureModelPage.jsx` | **Create.** Summary, bounded overview and collections. |
| `frontend/src/components/analysis/AnalysesTab.jsx` | **Create.** History/filter/pagination/start entry. |
| `frontend/src/components/analysis/StartAnalysisModal.jsx` | **Create.** Revision/configuration/validation/idempotency. |
| `frontend/src/components/analysis/AnalysisHeader.jsx` | **Create.** Breadcrumb/status/actions. |
| `frontend/src/components/analysis/AnalysisProgress.jsx` | **Create.** Overall/ordered stage progress. |
| `frontend/src/components/analysis/AnalysisFindings.jsx` | **Create.** Diagnostics/unresolved/conflicts. |
| `frontend/src/components/analysis/AnalysisExecution.jsx` | **Create.** Job/attempt/stage details. |
| `frontend/src/components/architecture/ArchitectureCanvas.jsx` | **Create.** Bounded deterministic SVG/keyboard selection. |
| `frontend/src/components/architecture/ArchitectureInspector.jsx` | **Create.** Selected entity/safe metadata. |
| `frontend/src/components/architecture/ArchitectureCollectionTable.jsx` | **Create.** Typed table/pagination shell. |
| `frontend/src/styles/analysis.css` | **Create.** Existing-token analysis styling. |
| `frontend/src/styles/architecture.css` | **Create.** Existing-token model styling. |
| `frontend/package.json`, lockfile | Modify; add Vitest, jsdom and React Testing Library; retain Node regressions. |
| Frontend service/UI test files | **Create.** Exact contracts, roles, lifecycle, timers, pagination and accessibility. |

Do not split each card, row or icon into a separate component without proven
reuse.

### 4.11 Testing and quality gates

Express tests cover delegated-header origin, role matrix, cross-project denial,
validation/defaults/idempotency, safe upstream errors, secret non-exposure,
timeouts, SSE forwarding/backpressure and disconnect abort.

Python tests cover repository-filtered count/order/pagination, diagnostic
severity/stage filters, deterministic ordering/bounds, project isolation and
frozen lifecycle/event/M4 regressions.

Frontend tests cover exact service requests, route precedence, unresolved-role
safety, start/cancel duplicate prevention, every lifecycle state, progress,
SSE/poll cleanup, findings/model pagination, bounded canvas labeling,
deterministic keyboard selection, loading/empty/error/retry states, and existing
auth/project/repository/ingestion regressions.

Planned commands, verified where scripts already exist:

```text
cd express && npm test
cd frontend && npm test
cd frontend && npm run build
./venv/bin/pytest -q tests/p3/analysis/test_m1_*.py tests/p3/api/test_m4_architecture_api.py
./venv/bin/ruff check backend tests
./venv/bin/mypy --strict backend
./venv/bin/black --check backend tests
git diff --check
```

Frontend `npm test` must retain the four existing Node suites and add the new
Vitest/RTL suite. No frontend lint/typecheck command is claimed until configured.

### 4.12 Definition of Done and acceptance criteria

M5 is complete only when:

1. An authenticated operator can select an immutable revision, start an analysis
   and reach its detail page.
2. Any member can view correctly repository-scoped, paginated history.
3. Lifecycle, stages, attempts, completeness, errors and cancellation reflect
   canonical backend state; live updates stop reliably.
4. Diagnostics, unresolved relationships and conflicts are distinct,
   evidence-backed finding categories; no new finding model is invented.
5. A published Architecture Version exposes summary, entities, relationships,
   evidence, unresolved items and conflicts with server pagination.
6. The bounded overview is accessible, deterministic and explicitly partial;
   no graph projection or full-model browser load occurs.
7. Express enforces JWT/RBAC, safely delegates, hides credentials and preserves
   structured errors.
8. Viewer and unresolved-role UI never exposes mutations; backend authorization
   remains decisive.
9. Existing design, responsive behavior, auth/dashboard/repository flows and
   `apiClient` refresh semantics remain intact.
10. Executed tests/build/static checks are recorded before completion.

## 5. Execution Ledger

| Module | Status | Evidence / remaining |
|---|---|---|
| M1 | **FROZEN / COMPLETE** | Verified, including the implemented additive repository-history filter and diagnostic query boundary required by M5. Frozen F1 lifecycle semantics remain unchanged. |
| M2 | **FROZEN / COMPLETE** | F2 contract and extraction coverage remain unchanged. Production performance hardening now reuses bounded OS-isolated parser children, parallelizes authorized artifact reads through a pooled HTTP client, preserves deterministic ordering/integrity checks, and emits phase timing telemetry. |
| M3 | **FROZEN / COMPLETE** | No M5 change planned. |
| M4 | **FROZEN / COMPLETE** | Architecture Model construction/publication and the implemented bounded entity-evidence query filter are verified. Frozen schema v1 semantics remain unchanged. |
| M5 B1 | **COMPLETE / VERIFIED** | Implemented Express analysisConfig, analysisGatewayService, analysisValidate, analysisController, architectureController, analysisRoutes, architectureRoutes. Implemented FastAPI optional repository_id filter, diagnostics list endpoint, and M4 entity_id evidence filter. 29 Express tests passed (11 unit, 18 integration). 15 FastAPI M1/M4 API tests passed. |
| M5 B2 | **COMPLETE / VERIFIED** | Implemented frontend contracts (analysisContracts, architectureContracts), API services (analysisService, architectureService), apiClient streaming extension (apiStream), dark theme styling (analysis.css), AnalysesTab with pagination/status filtering, StartAnalysisModal with revision inspection, idempotency key generation and advanced options, RepositoryDetailPage tab integration, and App route precedence. Verified with clean `npm run build` (vite v8.3.1), 100% existing frontend Node test suites, 29 Express tests, 15 Python API tests, and clean static checks (black, ruff, mypy --strict). |
| M5 B3 | **COMPLETE / VERIFIED** | Implemented `useAnalysisLiveStatus` hook (authoritative REST polling with SSE invalidation, 15s reconnect backoff, 3s serialized polling fallback, terminal state teardown), `AnalysisDetailPage`, `AnalysisHeader` (breadcrumbs, cancellation modal, architecture link, streaming indicator), `AnalysisProgress` (8-stage progress rail, metrics cards, indeterminate/percentage progress), `AnalysisFindings` (diagnostics, unresolved relationships, architecture conflicts with independent pagination and severity filters), `AnalysisExecution` (active worker job telemetry and stage execution table), App route mounting, and dark theme CSS. Verified with clean `npm run build` (75 modules, 2.15s), 100% existing frontend Node test suites, 29 Express tests, 15 Python API tests, and static checks (black, ruff, mypy --strict). |
| M5 B4 | **COMPLETE / VERIFIED** | Implemented `ArchitectureModelPage`, `ArchitectureCanvas` (bounded partial window of max 100 entities, deterministic tier layout by kind, stable logical-ID ordering, static SVG connectors with arrowheads, keyboard selection), `ArchitectureInspector` (safe structured metadata key-values, evidence counts, namespace, IR tags), `ArchitectureCollectionTable` (typed paginated table shell for Entities, Relationships, Evidence with entity filtering, Unresolved, Conflicts), `architecture.css` dark theme design token styling, and App route integration. Verified with clean `npm run build` (81 modules, 3.96s), 100% existing frontend Node test suites, 29 Express tests, 15 Python API tests, and static checks (black, ruff, mypy --strict). |
| M5 remediation | **FROZEN / COMPLETE** | Corrected the Express gateway prefix to `/api/v1`, documented/configured both internal service credentials, registered the mandatory production `input_validation` stage, removed the API-to-worker queue-state race, preserved authorization-before-resource-lookup ordering, and repaired live-status lifecycle handling. Corrected multi-application M4 scope promotion, internal module resolution, static Express router mount composition, and the M4 boundary so lower-level frontend calls/imports are not mislabeled as unresolved architecture. Added conservative, evidence-backed backend boundary promotion for Django, FastAPI, Flask, Express and NestJS controllers, services, data repositories and workers without changing F3; added static endpoint-to-controller routing and indexed cross-file relationship resolution. Test/spec/migration evidence no longer expands or destroys production framework roots, FastAPI route modules are promoted as controllers, and ordinary Python `.get()`/`.delete()` calls are not published as HTTP endpoints. The bounded overview now selects entities round-robin by application namespace and loads bounded relationship candidates by semantic kind, preventing Express logical-ID ordering from hiding FastAPI endpoints and Python services. Modules, libraries and the full frontend inventory remain available in collection tabs. Aligned frontend entity/relationship/evidence vocabulary with the canonical M4 contract and replaced the single-row canvas with a wrapped, tiered, zoomable bounded view. Canvas selection remains fixed during selection/focus changes and the analysis SVG node class is isolated from landing-page hover transforms. Node content is now clipped inside its SVG card, and connector-focus controls are grouped responsively so `Show all` cannot overlap the connector summary. Long pipeline-stage labels now wrap in a stable two-line title area instead of truncating Identity Resolution and Architecture Build. A real optimized run processed 469 extraction items in about 20 seconds and completed the downstream pipeline. The final repository smoke model validated with 2 applications, 19 controllers, 25 services, 26 data repositories, 4 workers, 79 endpoints and 78 static `routes_to` relationships. Latest architecture verification: 42 focused M4 tests passed; the 10,000-entity capacity benchmark passed in 27.38s; Python regression excluding the pre-existing pathological M3 stress benchmark passed 746 tests with 3 platform skips; frontend legacy suites plus 8 Vitest tests and the production build passed. Earlier Express 422-test and zero-vulnerability npm audit gates remain unchanged. Focused Ruff, changed-file Black, strict mypy and diff checks passed. |
| Local analysis operations | **VERIFIED** | Added and installed user-level systemd worker and Beat services from `ops/systemd/`. Exactly one named worker consumes `analysis.jobs`; Beat executes the 60-second M1 dispatch-recovery schedule. Both services are enabled with automatic restart, user lingering is enabled for boot-time startup, and the PostgreSQL/RabbitMQ containers already use `unless-stopped`. A previously orphaned queued analysis was republished once and verified `RUNNING` under `stacksense-worker@pr0xius`. M2 throughput hardening replaces per-artifact parser startup with four reusable sandboxed children (recycled after 64 requests), reuses Express HTTP connections, and performs eight bounded concurrent artifact reads. Benchmarks measured 12 representative isolated parses falling from 18.014s to 3.056s (5.89x), 100 small Python parses completing in 3.193s, and 300 actual StackSense source files (1.71 MB, 59,053 facts) completing isolated extraction in 6.810s; 105 focused M1-input/M2 tests passed with 3 platform skips. |
| M5 | **FROZEN / COMPLETE** | Analysis initiation, live lifecycle, findings, model exploration, visualization and final stage-rail presentation are verified. |
| M6 | **FROZEN / COMPLETE** | Final cross-service regression, real execution, performance, build, static and dependency-security gates passed. On 2026-11-10 the owner additionally accepted the phase after live testing complete analysis runs and Architecture Model exploration on multiple projects. |

## 6. Decisions, Risks and Required Approvals

### 6.1 Approved owner decisions

1. **M1 query change control — approved:** add optional `repository_id` on
   `GET /analyses` and paginated `GET /analyses/:id/diagnostics`. These are
   additive read-only changes; F1 input/lifecycle/event contracts remain frozen.
2. **Evidence drill-down — approved:** add optional `entity_id` filtering to the
   existing evidence collection so selected-entity evidence is retrieved with
   bounded server pagination.
3. **Basic visualization boundary — approved:** implement the bounded,
   deterministic SVG in §4.4 as M5 presentation of canonical rows; full graph
   projection and traversal remain Phase 4.
4. **Frontend test tooling — approved:** add Vitest, jsdom and React Testing
   Library while retaining the existing source-inspection Node regressions.

These approvals authorize only the plan recorded here. They do not mark any
implementation batch, API change, dependency addition or test as completed.

### 6.2 Principal risks and mitigations

- Secret leakage: server-only config, header allowlist, sanitized errors/logs and
  negative tests.
- RBAC drift: authoritative Express membership then independent FastAPI checks.
- SSE leaks: one hook/controller, abort on disconnect/unmount, bounded reconnect,
  REST-authoritative state.
- Large models: page <=100, independent offsets, bounded canvas, no aggregation.
- Misleading visualization: loaded/total counts and explicit partial label.
- Dynamic metadata/XSS: React text rendering/safe structure; no raw HTML.
- Route regression: most-specific matching and tests.
- Dirty worktree: status inspection before/after and no unrelated overwrite.

No architectural decision or unresolved acceptance gate blocks Phase 3 closure.

## 7. Current Handoff

M1–M5 contracts and implementation are frozen and verified. Corrective changes
preserve F1/F2/F3 and Architecture Model schema versions. The analysis-start
flow, production-only backend scope resolution, backend boundary promotion,
relationship resolution, application-balanced backend-first map, map stability,
parser throughput and pipeline-stage presentation are resolved.
M6 closeout is complete, and the owner accepted the end-to-end product behavior
after live project testing on 2026-11-10. Phase 3 is formally **FROZEN /
COMPLETE**; subsequent changes require explicit change control.
The user-level Celery worker and Beat services were restarted, verified active,
and remain enabled for login/boot startup. Existing published Architecture
Versions remain immutable; run a new analysis to observe the final model changes.
The user-level Celery worker was restarted after the final scope/sampling fix and
confirmed ready on `analysis.jobs`. Previously published models will never change
in place; that immutability is intentional.

M2 performance hardening preserves the frozen F2 contract, source coverage,
security sandbox and capacity behavior. New timing logs split artifact-read,
parse, enrichment and serialization time so future bottlenecks are measurable.
Any long-running Celery worker must be restarted after deploying this code;
Celery does not hot-reload imported parser modules.

**Next action:** Create and push the Phase 3 completion commit on
`feature_mannan`, then begin Phase 4 planning from the frozen Phase 3 output
boundary. Do not reopen frozen Phase 3 contracts without explicit change
control.
