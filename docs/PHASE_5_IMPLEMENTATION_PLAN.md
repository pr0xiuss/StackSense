# Phase 5 — Knowledge, Search & Diagram Intelligence

Status: **PROPOSED — READY FOR OWNER REVIEW; NOT APPROVED OR FROZEN.**

Implementation: **NOT STARTED — all modules and batches are planned only.**

Repository inspected: `p5-knowledge-search`, 2026-11-17.

Location: `docs/PHASE_5_IMPLEMENTATION_PLAN.md` (the owner moved the initial document here).

## 1. Document Purpose and Authority

This is the consolidated P5 planning workspace for StackSense, a software repository intelligence and architecture analysis platform. It is not a PostgreSQL workload-intelligence product.

Authority, in descending order:

1. `master.txt`: authoritative, frozen architecture; particularly Sections 0, 9, 13, 14, 16, 17, 18, and 25.16–25.17.
2. Accepted architecture decisions, including `docs/architecture/adr/0001-express-python-integration.md`, and frozen published contracts under `docs/architecture/contracts/`.
3. `PROJECT_CONTEXT.md`: rolling decisions, execution evidence, status and handoff. Its historical summaries are not proof that a capability works.
4. This document: proposed P5 decomposition, contracts, implementation responsibilities and approval gates; subordinate to the above.

Labels used throughout: **Established** = master/accepted contract; **Owner requirement** = the current P5 brief or explicit prior owner decision; **Verified** = inspected implementation; **Proposed** = recommendation awaiting approval; **Blocked** = the named decision must be resolved before the affected implementation. Unqualified future-tense specifications below describe the proposed baseline, not work already performed or decisions already approved.

Only this document is changed by this task. No application implementation, compatibility installation, migration, benchmark or test execution is claimed. References to changes in other files are future implementation specifications, not authorization to edit frozen code.

## 2. Phase 5 Overview

P5 turns the published, evidence-backed Architecture Model into useful deterministic product outputs: searchable architecture knowledge, controlled retrieval/context, four essential diagrams, and one automatic Architecture Analysis Report. A unified frontend puts these outputs first while retaining analysis and graph details as drill-down tools.

P5 does not rediscover source facts. PostgreSQL Architecture Model v1 is authoritative; Neo4j and Elasticsearch are rebuildable projections. Generated diagrams, search hits, context and PDFs must name the exact project, repository, revision/snapshot and Architecture Version from which they were derived.

Proposed delivery: seven cohesive modules, described in Section 15. Search and diagrams are independent branches after shared contracts; report generation depends on all four diagram artifacts, not on search or Neo4j availability.

## 3. Product Vision and Objectives

The primary journey is repository → useful architecture outputs, not repository → several disconnected technical dashboards. Users should see diagrams as they become available, search their exact architecture, inspect supporting evidence, and download the completed report without manually scheduling each derivative.

Objectives:

- Automatically discover published versions without modifying the frozen analysis pipeline or relying on a browser session.
- Prioritize System Architecture Overview; independently generate Component Architecture, Dependency Map and Data Flow Diagram.
- Make diagram meaning traceable to canonical entities/relationships, including limitations and static uncertainty.
- Offer scoped lexical search, supported semantic capabilities, controlled architecture queries and bounded evidence/context retrieval without an LLM.
- Automatically generate one PDF report only after all four diagrams are READY for the same version.
- Preserve exact historical results, security boundaries and existing dashboard styling/interactions.
- Measure publication-to-availability, queue wait, execution time, memory and failures separately. No arbitrary performance guarantee is inferred from previous extraction improvements.

## 4. Existing Architecture and Phase Dependencies

### 4.1 Verified repository baseline

| Existing path/interface | Verified responsibility | P5 reuse and restriction |
|---|---|---|
| `backend/platform/analysis/application/dto.py` | `CreateAnalysisRequest` requires project/repository/revision UUIDs, supports an idempotency key | Reuse existing analysis initiation; no new analysis lifecycle or stage |
| `backend/platform/analysis/domain/job.py` | Analysis-specific Job and attempt accounting; requires an analysis identity | Not a generic diagram/report job table; do not insert unrelated jobs into it |
| `backend/platform/analysis/domain/diagnostic.py` and `domain/constants.py` | Shared `AnalysisDiagnostic`; severity `info`, `warning`, `error`, `critical` | Read established diagnostics; never invent security findings or recalculate severity |
| `backend/platform/analysis/architecture/model.py` | Immutable ArchitectureDocument, canonical identities, evidence, completeness, validation | Input to deterministic P5 builders; no canonical mutation |
| `backend/platform/analysis/architecture/service.py` | `ArchitectureQueryService` and published result access | Read-only reuse through P5 adapters; no additional P3 persistence responsibilities |
| `backend/platform/analysis/architecture/dto.py` | UUID record IDs separately from canonical logical IDs; paginated result DTOs | Preserve both identities; evidence references are not interchangeable with record UUIDs |
| `backend/platform/graph/source.py` | Public `PublishedArchitectureSource`: `list_published(limit, after)` and `load_exact(version, project)` | Reuse read-only source port in a P5-owned adapter; keyset cursor includes project/repository/sequence/version |
| `backend/platform/graph/query_service.py`, `query_contracts.py` | Bounded exact-version window, node, neighborhood, dependency/dependent, containment and path queries | Reuse for graph-assisted knowledge exploration, not a second Cypher engine |
| `backend/platform/graph/lifecycle.py`, `verification.py`, `persistence.py` | Frozen P4 resources, attempts, verification and active-generation ownership | Patterns inform P5, but P5 must not extend these records or activate P4 generations |
| `backend/worker/celery_app.py` | Celery/RabbitMQ, existing task routes, beat, late acknowledgement, bounded concurrency | Reuse infrastructure; proposed additive task registration requires scoped composition approval |
| `backend/api/v1/router.py` | FastAPI route composition | Proposed additive registration only; frozen handlers remain unchanged |
| `express/src/services/analysisGatewayService.js` | Trusted delegated headers, bounded forwarding, repeated query parameters, graph-mode status/error preservation, SSE relay | Extend this gateway minimally; binary PDF relay is not established by its JSON or SSE modes |
| `express/src/routes/graphRoutes.js`, `routes/index.js` | Authenticated graph transport and registration | Pattern for transport, not permission to add unrelated Express code |
| `express/src/services/internalAnalysisSourceService.js` | Authorized immutable revision manifest and artifact access; manifest includes revision metadata, not project/repository display names | Reuse manifest contract where appropriate; report display-name snapshot requires an approved P5 metadata interface, not a MongoDB read from Python |
| `frontend/src/App.jsx` | Existing hash/path routes, exact-version Model/Graph routes, shared dashboard header | Extend route parser without introducing a second router or losing exact-version links |
| `frontend/src/pages/RepositoryDetailPage.jsx`, `AnalysisDetailPage.jsx`, `ArchitectureModelPage.jsx`, `ArchitectureExplorerPage.jsx` | Repository, execution, canonical model and graph exploration views | Extend current flow; preserve operational drill-downs rather than duplicate them |
| `frontend/src/services/apiClient.js`, `architectureService.js`, `graphService.js`, `analysisService.js`, `ingestionService.js` | Existing Express-facing service layer and auth/session behavior | Reuse; no direct browser → FastAPI calls or replacement auth client |
| `frontend/src/components/graph/`, `hooks/useGraphLayout.js`, `workers/graphLayout.worker.js` | Existing graph canvas, inspector, list, layout and navigation behavior | Reuse safe UI patterns; do not change frozen P4 worker protocol or graph-window caps |
| `frontend/package.json` | React 18; React Flow `12.12.1`, ELK `0.12.1`; Vite/Vitest; no lint/type/format scripts | Existing renderer/layout packages, not evidence of server-side layout availability |
| `infra/docker/compose.yml`, `requirements.txt` | PostgreSQL, RabbitMQ, Neo4j; Python backend dependencies | No Elasticsearch service/client or PDF renderer is currently established here |

The current backend uses Python 3.14; `pyproject.toml` configures Ruff, Black and strict Mypy accordingly. Backend imports must remain absolute. New P5 packages follow the existing cohesive `backend/platform/<domain>/` style rather than inventing a separate service architecture.

### 4.2 Frozen contracts and limits

- F1/F2/F3 and Architecture Model v1 remain unchanged. P5 consumes published Architecture Models, not transient F2/F3 handoffs, and never triggers parser recovery.
- Source ranges are canonical UTF-8 byte coordinates: zero-based, end-exclusive bytes/columns; one-based lines; BOM excluded, original LF/CRLF preserved. Non-UTF-8 Python source requires the existing decoding semantics, not slicing original bytes with canonical offsets.
- Actual Architecture Model statuses include `confirmed`, `supported`, `inferred`, `unresolved`, `conflicting`. Do not replace them with F3's smaller enum or present any as runtime truth.
- Evidence strength remains direct source > framework structural > configuration > dependency > documentation; opposing evidence survives retrieval and presentation.
- Canonical model limits remain 25,000 entities, 50,000 relationships, 75,000 evidence, 10,000 unresolved, 5,000 conflicts, 128 MiB payload. A bounded diagram is a disclosed view, not a truncated canonical model.
- P4 public projection states remain PENDING/RUNNING/COMPLETED/FAILED/STALE; historical STALE versions with verified active generations remain readable. Rebuild failure must preserve the last verified generation.
- Existing P4 exploration limits and its 5-second whole-operation deadline are not enlarged by P5. In particular, P4's React explorer window of 300 nodes/600 edges is separate from the proposed P5 diagram view budget.

### 4.3 P4 status reconciliation

The owner declared P4 frozen after live acceptance. The repository contains working M5 transport/UI and later correction records (Section 12.21 onward of `PROJECT_CONTEXT.md`), but older tables still describe M4/M5 as upcoming, and the final handoff does not establish an independently completed M6 evaluation. These are documentation/evidence inconsistencies, not authorization to reopen implementation.

P5 treats P1–P4 interfaces as frozen dependencies. Before implementation approval, the owner should accept the existing P4 closure evidence or commission only the missing acceptance checks. No new P4 test result or complete M6 verification is asserted by this planning task; no context record is changed here.

### 4.4 Compatibility evidence versus work still required

The [official Elasticsearch Python client release notes](https://www.elastic.co/docs/release-notes/elasticsearch/clients/python) record Python 3.14 CI coverage; the [official client compatibility guidance](https://github.com/elastic/elasticsearch-py#compatibility) still requires a compatible server/client version pairing. This supports an implementation spike, not a claim that a particular StackSense installation has passed it. The [ReportLab graphics documentation](https://docs.reportlab.com/reportlab/userguide/ch2_graphics/) establishes direct PDF drawing primitives; Python 3.14 packaging, selected fonts and StackSense's diagram/pagination workload remain unverified. No new dependency version is frozen here.

## 5. Phase 5 Scope

| Deliverable | Included | Principal acceptance output |
|---|---|---|
| Knowledge/search | Deterministic projection, indexing/rebuild, scoped lexical search, capability-gated semantic/hybrid retrieval, evidence/context planning, controlled knowledge queries | Exact-version results and reproducible provenance; visible freshness and failure states |
| Diagram intelligence | Four automatic diagrams, DiagramSpec, independent layout, React Flow rendering, grouping/focus, safe exports, user presentation preferences | Four independently recoverable READY artifacts, overview prioritized, no invented topology |
| Report | One deterministic Architecture Analysis Report; PDF only; automatic orchestration, local artifact store, history/download | Validated same-version ReportSpec and immutable PDF after all four diagrams READY |
| Frontend | Repository-centered output workspace, search/knowledge/evidence, diagrams and report availability, operational drill-downs | Cohesive navigation preserving project/repository/analysis/version identity |

A one-action ingestion → analysis experience is a previously requested product direction, not an already authorized backend bridge. Section 10 defines it as a separately gated enhancement; automatic post-publication P5 delivery is required independently.

## 6. Explicit Out-of-Scope Responsibilities

No AI/LLM explanation, chatbot, natural-language diagram generation, executive summary, documentation comparison, runtime monitoring, new source-analysis rules, new findings/severity engine, cross-version architecture diff, new canonical entity/relationship types, Neo4j redesign, arbitrary Cypher/Elasticsearch DSL, freeform diagram editor, additional report types, Word/HTML report outputs, or cloud storage implementation.

No direct cross-database access, organization domain, source execution, browser service credentials, migration of PostgreSQL to MongoDB, replacement JWT/RBAC, new diagram queue, or reopening of completed analysis stages. P7 production hardening is not an excuse to defer essential P5 authorization, boundedness or recovery tests.

## 7. Deliverable 1 — Knowledge and Search

### 7.1 Knowledge projection

A P5-owned projector consumes `PublishedArchitectureSource.load_exact`. Its immutable `KnowledgeProjection` contains canonical entity, relationship, evidence, unresolved/conflict and existing diagnostic references, with safe searchable metadata. It is a derived vocabulary, not a second Architecture Model or new architecture identity resolver.

Searchable document kinds: entity, relationship, evidence metadata, and existing analysis diagnostic. Separate unresolved/conflict documents may support explicit filters, but are never promoted to established entities. Every document has project/repository/snapshot/analysis/version, canonical content digest, schema/projector version and generation. A diagnostic is analysis-scoped and must be linked honestly to the selected architecture version; do not claim it is a newly persisted canonical finding.

Allowlist names, kinds, namespaces, static statuses, safe architectural metadata, evidence paths/ranges/producer references, diagnostic codes/severity and safe messages. Do not index repository source bodies, credential-bearing configuration, arbitrary metadata, access tokens, storage keys or generated PDFs. Documentation-derived evidence already in the model may be indexed with its actual strength; broad README/ADR ingestion is not introduced here.

### 7.2 Elasticsearch projection and freshness

Proposed storage: shared versioned physical indexes per schema, with mandatory project/version/generation filters, not one index per repository or version. PostgreSQL owns SearchProjection resources, attempts, verification receipts and active-index/generation pointers. Elasticsearch is disposable. Scope filtering occurs before retrieval/ranking, never after fetching global hits.

`knowledge_key = SHA256(canonical_json([project_id, version_id, document_kind, canonical_reference]))`; `storage_key = SHA256(canonical_json([knowledge_key, generation_id]))`. Canonical logical IDs are copied exactly, never normalized again. Canonical JSON uses explicit schema/version, sorted keys, compact UTF-8 encoding and no volatile timestamps; arrays have defined ordering. No ambiguous delimiter concatenation. Digests include all allowlisted stored properties in deterministic key order, excluding ES engine metadata.

Build candidates with bounded bulk requests; inspect every bulk result; refresh the candidate, then independently read back keys, counts, payload digests, scope and versions. Acknowledged writes or an index count alone do not prove completeness. Activate only after verification and a fenced PostgreSQL transaction. Retain the previous verified generation through rebuild failure. A breaking mapping change builds a new physical index and pointer, not an in-place semantic overwrite.

Incremental work is an optimization, not a relaxed publication rule: unchanged safe record payloads/embeddings may be reused by content-and-producer fingerprint, but every new version/generation receives its own scoped storage keys and complete independently verified key set. A changed/deleted record cannot remain because an old active index was patched incompletely. First implement full deterministic rebuild; enable incremental reuse only after equivalence and deletion tests pass. Do not require cross-version identity continuity beyond the canonical model's existing IDs.

Freshness is a separate DTO dimension: CURRENT, STALE, BUILDING, FAILED, UNAVAILABLE. Include `active_generation`, `attempt_state`, `is_readable`, `is_current_version`, `last_verified_at`, and safe failure code. STALE means a historical/not-current verified projection, not unreadable. During rebuild, BUILDING may coexist with a readable active generation; failure describes the failed attempt without concealing that generation. Exact-version queries never switch versions for freshness.

Search pagination binds project/version, generation, physical index identity, query/filter digest, ordering and cursor expiry. Use PIT/search-after where supported and signed opaque cursors. On generation change or expired PIT, reject continuation explicitly; do not silently restart. Cleanup closes PITs and respects active readers and retained historical artifacts.

### 7.3 Retrieval and controlled knowledge

Lexical baseline: identifiers/names/paths, field-weighted BM25, exact canonical-ID and qualified-name matches before fuzzy text, stable logical-ID tie break. Relevance is not evidence strength or truth. Duplicate hits collapse by canonical reference while preserving all distinct provenance/conflict references.

Semantic search is capability-gated behind `EmbeddingProvider`: model/version/dimensions/tokenization/text-policy are part of the generation fingerprint. Recommendation: ship lexical + existing graph-assisted structured retrieval as the mandatory baseline; enable embeddings only after the owner chooses and approves an offline/local or external provider and validates Python 3.14, licensing, privacy, cost and resource behavior. Disabled semantic mode returns an explicit capability error, never silently labels lexical results semantic. Hybrid fusion, if enabled, uses a documented deterministic rank-fusion rule and stable tie break; provider output reproducibility and numerical tolerance must be recorded.

Controlled query operations: entity lookup, entity relationships, dependencies, dependents, containment, bounded related paths and evidence retrieval. Identifiers and structured filters are supported; arbitrary natural-language interpretation belongs to P6. Graph operations reuse frozen P4 APIs and their full dependency relationship-kind set, not `depends_on` alone; `contains` stays separate. If Neo4j is unavailable, return capability-specific unavailability for graph traversal while lexical search, direct canonical detail and essential diagrams continue. Do not silently implement a second traversal engine.

### 7.4 Evidence planner and context builder

`RetrievalRequest → scoped candidates → exact canonical resolution/ambiguity → retrieval plan → bounded evidence bundle → ContextBundle`.

The planner sets a budget before retrieval; no whole-repository dump. Preserve architecture version, entity/relationship IDs, evidence logical IDs and UUIDs where available, actual producer ID/version, optional source fact key, source record type, relative path/range, static status, strength and opposing evidence. Inventory/detection-derived provenance need not have a SyntaxFact key. Missing values remain absent; no fabricated analyzer ID or percentage confidence.

Default context uses safe canonical evidence metadata. Optional excerpts require an explicit authorized bounded artifact read via ADR-0001, encoding-aware coordinates, path policy, literal/secret redaction and an excerpt budget. Evidence existence does not authorize reading files prohibited by the safety policy. If safe extraction cannot be established, return source references only. P5 does not rerun M2 to recover text or counts.

`ContextBundle v1` contains scope, request/fingerprint, resolved/ambiguous subjects, ordered facts, relationships, evidence, conflicts/unresolved, limits, omissions with reasons, capability/freshness and provenance. It is suitable for P6 consumption but contains no generated answer. Optional excerpt support may be withheld at contract freeze until its safety tests pass; metadata evidence is mandatory.

## 8. Deliverable 2 — Diagram Intelligence

### 8.1 Four essential diagrams

| Stable template ID (proposed v1) | Meaning and selection | Evidence and safeguards |
|---|---|---|
| `system_overview` | Applications/frontend applications, backend services, external interfaces/systems and persistence/messaging boundaries; bounded expansion | Canonical nodes and established interactions; application grouping is presentation, not identity inference |
| `component_architecture` | Backend-first applications → controllers/services/workers/components/modules, with selectable frontend inclusion | Real containment/ownership evidence only; a service filename alone is not a new service detector |
| `dependency_map` | Architectural dependency relationships, with optional module/library expansion | Existing kinds such as depends_on/imports/uses/calls/connects_to retain their exact semantics; containment is a separate overlay |
| `data_flow` | Static interaction/data-flow-relevant slice of endpoints/services/persistence/messaging/external systems | Allowlisted existing routes_to/calls/produces/consumes/persists_to/connects_to relationships only where present; retain canonical direction and label static semantics, not observed traffic |

All four must produce validated artifacts even when their valid content is small. If no established data flow exists, the Data Flow Diagram is an honest empty/limited diagram with a reason and coverage warnings—not fabricated flows. Do not turn every low-level module into an overview entity. Do not use LLM grouping, infer hidden databases or label a static `calls` edge as an executed request.

### 8.2 Three-layer architecture

1. **Canonical architecture truth:** published Architecture Model, read-only, with established semantic identities/relationships/evidence.
2. **Diagram specification:** allowlisted query/view selection and pure template builder produce a validated renderer-independent `DiagramSpec`.
3. **Visual layout and workspace:** DiagramSpec + layout profile/version → ELK adapter → separate `LayoutSpec` → React Flow; user presentation preferences, focus and pan/zoom remain outside canonical truth. Safe server exports consume the same prepared specifications.

The complete flow remains Architecture Model → Diagram Query/View → Diagram Builder → DiagramSpec → ELK Layout → React Flow Model → frontend. LayoutSpec carries bounded coordinates, node dimensions, routed edges, groups and label boxes; it never defines architecture semantics.

DiagramSpec is not React Flow nodes/edges, ELK's internal graph or Mermaid text. Proposed fields: schema/template/builder versions; exact scope and canonical digest; generation/input fingerprint; nodes with canonical references; edges with canonical relationship references/direction; presentation groups; labels/status/evidence references; legend, warnings, selected/omitted counts and view continuation/focus context. Group IDs occupy a separate presentation namespace, cannot be queried as canonical entity IDs, and bundles preserve underlying edge references. Model reference and endpoint validation occurs before layout.

### 8.3 Server availability and layout decisions

Automatic reports cannot wait for a browser layout worker. Recommendation: one bounded headless ELK helper using the same pinned `elkjs` line as the frontend, launched by Python through a narrow stdin/stdout specification protocol. This is a helper process, not an Express service, new graph store or diagram queue. Node is already a frontend/Express runtime but is a **new analysis-worker deployment dependency**; approve this explicitly after a Linux packaging/resource spike.

The helper receives only sanitized DiagramSpec, no credentials, arbitrary paths, URLs or source. Minimal environment, closed unrelated descriptors, process group termination, bounded CPU/RSS/input/output/wall time and network denial are required. Existing M2 parser sandbox must not be weakened or repurposed by modifying frozen code. An independently verified layout fallback may return a visibly flagged deterministic layout; invalid/unbounded layout cannot become READY. Browser worker handles user-driven presentation refinements using a P5 protocol, not a changed P4 protocol.

Layout profiles use compact hierarchical/compound layouts, connected-component packing, edge bundling and collapsed groups—not a single unbounded horizontal rank. Initial diagram budget recommendation: at most approximately 500 visible canonical nodes with an independently approved edge budget; lower responsive defaults after measurement. Large views disclose omitted counts and support filtering/focus/expand, never silently drop canonical facts or enlarge P4 explorer limits.

### 8.4 Readiness, priority, customization and export

A diagram is READY only after DiagramSpec and LayoutSpec validate, the server-renderable artifact is durably stored and verified, and metadata is transactionally committed. Opening React is not part of readiness. Each template has its own fingerprint, attempts, failure and retry; one failure cannot invalidate ready siblings or the published model.

Overview is scheduled first and made available first on the normal successful path. Proposed orchestration: release the other three tasks when overview becomes READY; run them independently subject to existing worker capacity. If overview exhausts retries, release the other templates with a visible overview-failed dependency note rather than blocking all useful outputs forever; report remains blocked until all four READY. This failure-path policy requires explicit approval, not a silent broker-priority assumption.

Generated specs/layouts are immutable. User workspace preferences (positions, collapsed groups, filters) are separate, user/project/version/template scoped, and may not modify canonical names, relationships, evidence or generated report inputs. Reset restores the generated layout. A workspace edit does not regenerate the canonical model or automatically invalidate the report.

Proposed P5 diagram exports: validated DiagramSpec JSON and safe SVG from prepared specs/layout, with scope/version/warnings retained. Escape labels, reject scripts/external resources, and preserve reference mappings. PNG and standalone diagram PDF are optional decisions, not mandatory report features; the unified report remains PDF only. No Mermaid-first conversion or browser screenshot is the source of truth.

## 9. Deliverable 3 — Report Generation

### 9.1 Small deterministic report scope

One report type: **Architecture Analysis Report**, one deterministic ReportSpec pipeline, one PDF output. Approximately 8–12 pages is a readability guideline, not permission to omit required warnings or silently truncate evidence. No report designer, narrative engine, executive summary, source rescan, documentation comparison or new finding severity computation.

Sections are independently prepared and renderer-independent:

1. Project/repository metadata, immutable revision/snapshot, analysis and Architecture Version, schema/template/generator versions, report timestamp and generation identity.
2. Architecture inventory/statistics and major established boundaries.
3. Mandatory same-version System Architecture Overview diagram, with legend and source references; select other diagrams only when useful to the report, not automatically four full-page pictures.
4. Important **existing** findings/diagnostics: original severity, safe message, code and evidence/source references. Existing diagnostic severity includes `critical`; do not remap it to invented high/medium risk scores.
5. Coverage and limitations: canonical completeness, partial analysis, failed files/counts where actually retained, unsupported/skipped/language information only where persisted, unresolved/conflicts and unavailable fields explicitly identified.

Inspection did not establish a separate rich persisted security-finding catalog. Initial report uses the existing analysis diagnostics and canonical uncertainty; it must not imply that no vulnerabilities exist because diagnostics are empty. The report-preparation adapter may expose a future finding port, but no competing AnalysisDiagnostic domain or detection engine is created.

Report display metadata needs a separate honest boundary: existing published headers contain UUIDs, not project/repository names, and the current Express internal source manifest supplies revision metadata but not those names. Proposed D11 is a narrowly scoped authenticated P5 internal metadata read, returning validated project/repository display names and immutable revision metadata. Python captures a safe metadata snapshot once per report input, includes its digest in the fingerprint, and never joins MongoDB. Names describe the capture time, not historical names proven at architecture publication. If that interface is not approved, report labels must explicitly use UUIDs/unavailable values; the plan must not pretend a display-name contract already exists.

### 9.2 ReportSpec and renderer

`ReportSpec v1` includes scope, canonical digest, template/schema versions, immutable section data, diagnostic IDs/original severity, evidence references, completeness/limitations, and exact diagram artifact IDs/digests. The four prerequisite diagram references belong in the report provenance even when only the overview is embedded. Validate all sources are the selected version before rendering.

The renderer takes a prepared ReportSpec and prepared diagram primitives/assets. It cannot query PostgreSQL, Elasticsearch, Neo4j, Express or repository content; no ORM/session/network clients enter the renderer. Sections format independently; content discovery belongs to preparation and orchestration.

Recommendation: a pinned ReportLab-based PDF renderer with bundled licensed Unicode fonts and vector drawing from LayoutSpec; avoid browser automation and HTML execution for this small report. Python 3.14 packaging, font coverage, long labels, pagination, image bounds and PDF metadata determinism require a spike. This recommendation is not a verified installation. Created-at values are captured once per immutable report request; byte reproducibility requires pinned fonts, renderer and metadata settings. Otherwise promise semantic ReportSpec reproducibility, not untested byte-identical PDFs.

### 9.3 Automatic workflow and report gate

`architecture published + successful analysis → P5 durable discovery → four independent DiagramJobs → all four READY, exact version validated → orchestrator creates one ReportJob → prepare/validate ReportSpec → render PDF → verify/store → report READY`.

The **M1 P5 delivery orchestrator**, not ReportEngine, checks prerequisites and creates the report request. ReportEngine never polls four diagram jobs. A ready notification is only a hint; PostgreSQL state and a unique dependency fingerprint decide eligibility transactionally. Concurrent completions and reconciliation must create only one eligible report request.

Pin all four diagram artifact IDs/digests in one consistent read and validate they belong to the same version. A duplicate message cannot duplicate a report. Retrying the same inputs retains the idempotency identity. A genuinely changed diagram/template/renderer input creates a new immutable report generation; it never overwrites a published PDF. Regeneration after a newer diagram generation requires explicit policy/manual request, not an unbounded cascade. Report failure leaves architecture, diagrams and search unchanged.

### 9.4 Storage and architectural reconciliation

P5-owned `GeneratedArtifactStore` writes to configured local private storage, behind a future S3-compatible port. It is distinct from Express-owned repository artifact storage. Stage to a temporary same-filesystem path, enforce byte limits, verify digest/length, then atomic rename; commit READY only with verified metadata. Recovery reconciles staged/orphaned files without exposing partial downloads. Never persist absolute filesystem paths in public DTOs; server-generated opaque keys only.

`master.txt` 17.80 and 17.90 rule 38 allow report generation to survive unavailable diagrams, whereas this P5 product workflow requires all four diagrams READY. Recommended reconciliation: retain the renderer's architectural ability to render a valid prepared text report, but the single P5 automatic report product never schedules one without the strict four-diagram prerequisite. There is **no P5 text-only fallback**. Owner acceptance of this scoped workflow policy is required; if the master requires fallback for this exact product, explicit change control is needed rather than editing master here.

## 10. Deliverable 4 — Frontend Integration

### 10.1 Navigation and page layout

Preserve current dark theme, dashboard header, breadcrumbs, spacing, menus, loading/error/retry patterns and responsive behavior. Extend existing pages rather than add separate search, report and diagram dashboard pages. Proposed new full-page route: **one Repository Intelligence workspace**; existing pages remain operational drill-downs.

Proposed exact route: `#/projects/:projectId/repositories/:repositoryId/analyses/:analysisId/architecture/:versionId/intelligence`. Its tabs/query parameters select `diagrams`, `search`, `knowledge`, `reports`; selected template/entity is URL-addressable. All UUIDs and ownership relationships validate on entry. A repository-level convenience link may resolve a chosen published version once and redirect to this exact route; multiple versions for one analysis require explicit selection. Back/forward/history never silently substitute latest.

| Existing/new view | Layout and behavior |
|---|---|
| Existing repository detail | Keep repository metadata, revisions/ingestions and analysis history. Add prominent Prepare/Analyze entry and latest-selected output card with exact-version link; advanced operations stay accessible |
| Existing analysis detail | Keep pipeline/status/findings. Add compact delivery progress: four diagrams, search availability, report WAITING/BUILDING/READY; direct report download and workspace link. No ninth analysis stage |
| New intelligence workspace | Shared header/breadcrumbs/version selector → availability strip → Diagrams/Search/Knowledge/Reports tabs. Diagrams is primary; no P6 chatbot placeholder claiming availability |
| Diagrams tab | Four template choices with per-template status; overview selected initially; toolbar/filter/focus/export; bounded canvas; collapsible details/evidence drawer with actions before paged evidence. Responsive collapse, fit-once, explicit focus navigation, stable selection and scroll |
| Search tab | Search input, mode/capability/freshness and kind/status filters → paginated result list → bounded detail/evidence drawer. No one-letter table wrapping; full IDs in expandable details |
| Knowledge tab | Selected subject, exact identity, structured dependency/dependent/containment controls reusing graph services, and evidence/conflict panels. Unavailable traversal does not blank canonical details |
| Reports tab | Current report status/prerequisites, PDF download, paginated immutable report history with version/template/generation metadata and retry for authorized users |
| Existing model/graph pages | Remain precise canonical and exploratory drill-downs; add workspace link only. Do not replace P4 graph exploration with the four diagram templates |

No new global user-facing page is required for report preview: browser PDF download/open is sufficient. A focused entity drawer is reused across tabs; don't invent a user directory or identity schema.

### 10.2 Frontend state and usability

Use existing `apiClient.js` and domain services. Abort outdated requests on scope/tab changes; deduplicate polling; no overlapping timer requests. Poll only active P5 resources, suspend hidden views, apply bounded backoff/jitter and stop at terminal state. Server orchestration must not depend on polling. Preserve credentials on authorization failures/network/transient 5xx per current auth contract.

Server pagination and cursors remain authoritative; local filtering states whether it covers loaded records or the whole query. Evidence starts collapsed/limited; traversal actions remain reachable without scrolling hundreds of evidence IDs. Map and structured-list layouts must not retain inappropriate narrow graph inspectors. Fit view is explicit after initial layout; selecting a node must not repeatedly trigger fit/re-layout/scroll oscillation. View-on-map switches tab and focuses the exact node after layout completion; stale callbacks cannot move another version's camera.

### 10.3 Optional one-action preparation bridge — approval gate

Prior owner discussion requested automatic ingestion → analysis. Proposed opt-in Prepare Architecture action composes existing ingestion and analysis APIs; it does not replace them. A browser-only promise chain is simpler but loses work on navigation/restart; a durable Express-owned preparation record can survive those failures but adds a scoped platform workflow and delegated background-actor policy.

Recommendation: durable Express preparation coordinator, **only after explicit approval**. It owns ingestion/request linkage in MongoDB, resolves the exact completed revision and submits existing Python `CreateAnalysisRequest` with a stable idempotency key. It never queries PostgreSQL or starts P5 domain tasks itself. Revalidate initiating actor membership/role at continuation; if authority was revoked, stop visibly. Do not retain bearer/refresh tokens or trust a stale cached role. An approved internal continuation authorization contract is required; ADR-0001 must not be silently extended with an invented system actor.

This bridge is separable from required P5 post-publication automation. If not approved, retain explicit ingestion/analysis initiation with a streamlined UI and deliver automatic outputs after publication; do not claim full one-click workflow completed.

## 11. P5/P6 Responsibility Boundary

| P5 deterministic foundation | P6 extension, not implemented in P5 |
|---|---|
| Canonical knowledge projection, lexical search, configured embedding retrieval | AI provider configuration and architecture explanation/assistant |
| Structured retrieval plans and bounded ContextBundle with provenance | Natural-language interpretation and grounded answer synthesis |
| Predefined templates, filtering/focus, immutable DiagramSpec and presentation customization | Natural-language/custom diagram requests and AI-assisted diagram recommendations |
| Prepared ReportSpec and deterministic PDF | Executive Summary grounded in the final ReportSpec, not a separate rescan |
| Existing evidence and limitation display | Documentation comparison against architecture, initially README/ARCHITECTURE.md/ADR/design Markdown |

Embedding generation, if approved, is representation/retrieval only, never architecture inference. P6 may consume P5 ports but cannot turn an unsupported statement into a canonical fact or change severity. No speculative P6 provider framework, comparison crawler, chatbot page or hidden LLM dependency is added in P5.

## 12. Cross-Cutting Architecture Requirements

- PostgreSQL owns Python P5 work, projection metadata, diagram/report/workspace records. Express/MongoDB remains platform authority. Neither backend accesses the other's database. Local generated output is Python-owned, not a new repository source store.
- React → Express → FastAPI. Trusted service credentials and actor/project context are server-side only; Python validates them and exact resource ownership. P5 graph assistance stays behind existing P4 services.
- Existing P3 analysis lifecycle/stages/events and P4 projection lifecycle/contracts remain unchanged. New P5 resource progress is separate; no new public analysis/projection event vocabulary.
- Reuse Celery/RabbitMQ, SQLAlchemy/Alembic, existing gateway/auth, React Flow/ELK. No new microservice, database, diagram queue or alternate auth client.
- At-least-once messages; durable discovery before dispatch; identifier-only payloads; leased/fenced attempts; bounded work and retry; exact-version idempotency; immutable published outputs; independent candidate verification and atomic visibility.
- Standard structured errors `{error: {code, message, details}}`, safe details and correlation ID; preserve status distinctions through Express. No stack trace, raw source, credentials or private storage location in errors/logs.
- Configuration and input/version fingerprints are recorded with every output. Cache keys include project, exact version, canonical digest, schema/builder/renderer/model versions, selection/layout policy and applicable user scope.

## 13. Proposed Module Breakdown

Seven modules are proposed; the count is not an approved decision. This separates durable orchestration from output builders and avoids a module per diagram or page.

| Module | Purpose | Effort / risk | Primary deliverable |
|---|---|---|---|
| M1 — Delivery Contracts and Durable Orchestration | Discover published versions; own P5 work, fencing, dependencies and recovery | High / High integration | Version-scoped durable delivery foundation and report prerequisite coordinator |
| M2 — Knowledge Projection and Search Index | Deterministic knowledge records and verified ES generations | High / High infrastructure | Rebuildable exact-version search with freshness |
| M3 — Controlled Retrieval and Evidence Context | Scoped search/graph planning, ambiguity and bounded evidence | Medium–High / High security | Stable retrieval/context contract for UI and P6 |
| M4 — Diagram Intelligence | Four template builders, spec validation, server/browser layout, exports and presentation workspaces | High / High layout/performance | Four independent immutable READY diagrams |
| M5 — Deterministic Architecture Report | Preparation, validation, PDF and artifact history | Medium–High / Medium–High rendering | One automatic same-version PDF product |
| M6 — Platform Transport and Unified Frontend | Minimal Express boundary, workspace and existing-page integration; separately gated preparation bridge | High / High cross-service | Cohesive secure product journey |
| M7 — Integration, Evaluation and Closure | Real infrastructure, failure/recovery, regression and live acceptance | High / integration-heavy | Verified acceptance evidence and freeze proposal |

## 14. Module Dependency Graph

```text
Owner gates + compatibility/capacity spikes
                    |
             M1 contracts/foundation
              /                 \
       M2 search                M4 diagrams
          |                         |
       M3 retrieval             M5 report
              \                 /
              M6 integrated experience
                       |
              M7 evaluation/closure
```

M6 shells/layout can proceed after the relevant DTOs freeze, before live services; API integration waits for Python + Express contract approval. M3 graph adapters depend on frozen P4, not M4 diagrams. M5's pure ReportSpec preparation/rendering can begin against fixtures after M1/M4 contracts freeze; production scheduling waits for all four diagram implementations. M7 test fixtures/failure harnesses start early, not only after M6.

Contract freeze points (all proposed and owner-reviewed):

| Freeze | Owner/consumer approval | Required content | Enables |
|---|---|---|---|
| C0 — Scope/work/authority | M1 plus all producers, owner for composition/Express changes | Exact source envelope, P5 work/attempt states, leases/fencing, dispatch/report prerequisite policy, RBAC | Parallel M2/M4 domain work |
| C1 — Knowledge/search | M2 + M3 + M6 | Document vocabulary, index verification, freshness/cursors, embedding capability, errors/budgets | Retrieval and search UI mocks |
| C2 — Diagram | M4 + M1 + M5 + M6 | DiagramSpec/LayoutSpec, four template semantics, READY/storage, pinned artifact references, helper protocol | Report renderer and diagram UI |
| C3 — Context | M3 + M6, future P6 consumer review | ContextBundle, provenance/ranges, omissions, ambiguity, optional excerpts | Stable knowledge UI and future AI integration |
| C4 — Report | M5 + M1 + M6 | ReportSpec, prerequisite fingerprint, history/download/retention, renderer isolation | Automatic report and frontend integration |
| C5 — Transport | Python producers + M6 Express/React | Every route/DTO/status/limit, auth/repeated parameters/binary handling | Live frontend API integration |

No collaborator independently invents DTOs or changes frozen contracts to unblock parallel work. A changed shared contract needs producer/consumer review and owner approval before merge.

## 15. Detailed Module Plans

File inventories below distinguish **NEW (proposed)** from **MODIFY (verified existing, future additive approval)** and **REUSE (verified, read-only)**. New Python packages include conventional `__init__.py`; these are packaging files, not separate abstractions. No deletion is planned. Each batch closes with focused tests, quality checks and evidence before its successor.

### 15.1 M1 — Delivery Contracts and Durable Orchestration

**Purpose/scope:** P5-owned lifecycle and dependency coordination only: discover exact published successful analyses, create per-version work, dispatch/retry, lease/heartbeat/fence, recover lost dispatch and schedule eligible reports. Excludes P3 jobs/stages, P4 activation, diagram/search/report algorithms and source analysis.

**Dependencies/consumers:** read-only `PublishedArchitectureSource`; existing analysis query service for terminal-success check; PostgreSQL, Celery/RabbitMQ. Upstream C0 approvals; downstream M2–M6. P5-owned work tables, not modifications to AnalysisJob or GraphProjection tables.

**Interfaces/models:** `PublishedVersionReader`, `DeliveryCoordinator`, `WorkHandler` registration, `DerivedWork`, `WorkAttempt`, `DeliveryBundle`, immutable `VersionScope`/`ArtifactReference`. The work handler returns a validated domain result; the coordinator owns attempt completion/fencing, while each output module owns its resource publication transaction using the current attempt token. A stale handler cannot publish or release dependencies.

**Lifecycle/background:** see Sections 18–19. Discovery creates a unique `(project, version, delivery-policy-version)` bundle and required work records. Durable report barrier is M1-owned. No report job until all four committed diagram references pass scope validation. Broker loss is recovered by bounded reconciliation, not an in-memory callback or reopening analysis stages.

**API:** internal handler protocol; authenticated read-only delivery summary and authorized retry API in Section 17. No public endpoint can run arbitrary task names. **Failure/security/metrics:** fenced duplicate-safe execution, isolated dependencies, delegated resource checks, safe failures; discovered/queued/running age, attempt/retry/fence counters and dependency wait reason.

| File/action | Components, responsibility, dependencies and verification |
|---|---|
| NEW `backend/platform/delivery/contracts.py` | VersionScope, work/result/envelope schemas; canonical fingerprints; rejects mixed version/type and unsupported contract versions |
| NEW `backend/platform/delivery/model.py` | DerivedWork/WorkAttempt/DeliveryBundle transitions and report-barrier rules; pure deterministic transition/duplicate tests |
| NEW `backend/platform/delivery/persistence.py` | P5 SQLAlchemy tables, unique idempotency constraints, attempt fencing and pinned dependencies; real PostgreSQL race/rollback tests |
| NEW `backend/platform/delivery/repository.py` | Conditional claim/renew/finish, keyset discovery checkpoints and atomic report eligibility; no P3/P4 record mutation |
| NEW `backend/platform/delivery/source.py` | P5 adapter around public published source + existing analysis query port; validates exact scope/digest and successful analysis |
| NEW `backend/platform/delivery/platform_metadata.py` (subject to D11) | P5 HTTP adapter and immutable safe PlatformMetadataSnapshot; authenticated Express metadata only, exact ownership-chain/digest checks and no MongoDB access |
| NEW `backend/platform/delivery/service.py` | Coordinator, bounded reconciliation, retries and report prerequisite scheduling; broker failure, restart and concurrent completion tests |
| NEW `backend/platform/delivery/dependencies.py` | P5 DI/handler registry; receives public frozen ports, no imports from P3 private repositories |
| NEW `backend/api/v1/delivery.py` | Summary/retry transport with existing trusted auth/error conventions; permissions and ownership tests |
| NEW `backend/worker/delivery_tasks.py` | Identifier-only generic P5 dispatch and bounded reconcile entrypoints; never interprets source or stores broker payload as authority |
| NEW `tests/p5/delivery/test_{contracts,lifecycle,recovery}.py` | Scope/fingerprint, transition, lost message, stale attempt and all-four barrier tests |
| NEW `tests/p5/integration/test_delivery_postgres.py` | Real transactions, double dispatch, leases, report creation uniqueness and failed storage commit |

**Batches:** B1 contracts/models + source adapter and benchmark harness; B2 persistence/claims/reconciliation/worker composition; B3 report barrier, delivery APIs, restart/concurrency acceptance. B2 cannot start before C0 and queue/composition authorization. B3 uses fixture artifact readiness until M4 integration.

**Acceptance/DoD:** duplicate publications create one required work set; publication-to-discovery delay is measured; no work is lost after broker outage/restart; stale attempts cannot commit; four concurrent READY notifications create one report; mixed-version/prerequisite failures create none; P1–P4 state/events unchanged. Required unit + real PostgreSQL/RabbitMQ tests pass and operational limits are approved, not assumed.

### 15.2 M2 — Knowledge Projection and Search Index

**Purpose/scope:** canonical-to-knowledge mapping, safe searchable properties, ES storage, candidate verification, freshness/rebuild and optional approved embedding adapter. Excludes semantic architecture inference, arbitrary query execution, P4 lifecycle and report data discovery.

**Dependencies/consumers:** M1 C0, published model source, approved ES server/client compatibility. Produces C1 for M3/M6. PostgreSQL owns search resource/attempt pointers; ES owns derived document generations only.

**Interfaces/models/API:** `KnowledgeProjector`, `SearchIndexWriter`, `SearchVerifier`, `SearchProjectionService`, `EmbeddingProvider`; immutable `KnowledgeProjection`, `SearchVerificationResult`; status/rebuild/search APIs. Search queries are allowlisted methods, never raw DSL. Search resource activation verifies the current P5 attempt token and candidate receipt.

**Lifecycle/background:** Section 7 and Section 19; independent post-publication work. **Failure:** bulk item errors, key/count/digest mismatch, model mismatch, timeout or insufficient capacity prevent activation; previous verified generation remains readable. **Security:** no raw source/secrets, mandatory scope filter, bounded tokens/bytes. **Metrics:** queue/build/verify/activate durations, indexed/expected counts, rejected bulk items, stale age, PIT count, query latency and semantic capability.

| File/action | Components, responsibility, dependencies and verification |
|---|---|
| NEW `backend/platform/knowledge/model.py` | Immutable knowledge records, canonical mapping and versioned fingerprint vocabulary; schema/reference safety tests |
| NEW `backend/platform/knowledge/projection.py` | Pure model-to-record transform, allowlists, deterministic keys/digests; input permutation and adversarial metadata tests |
| NEW `backend/platform/knowledge/persistence.py` | Search resource/attempt/receipt and active generation/index pointer tables; transactional race tests |
| NEW `backend/platform/knowledge/repository.py` | P5 metadata and activation/retention operations; fenced candidate ownership checks |
| NEW `backend/platform/knowledge/elasticsearch.py` | Pinned client, mappings, bounded bulk/readback/PIT operations, cancellation and health; real ES integration tests |
| NEW `backend/platform/knowledge/verification.py` | Independent key/payload/scope/count/version readback; injected missing/duplicate/tampered record tests |
| NEW `backend/platform/knowledge/service.py` | Status/rebuild/search planning and safe generation-bound pagination; M1 WorkHandler adapter |
| NEW `backend/platform/knowledge/contracts.py`, `dependencies.py` | C1 request/response/port types and DI; consumer fixtures and optional disabled embedding implementation |
| NEW `backend/platform/knowledge/embedding.py` (conditional approval) | Provider adapter and text-policy/model fingerprint only if semantic branch approved; no LLM architecture interpretation |
| NEW `backend/api/v1/knowledge.py` | Search/status/rebuild handlers; same module later hosts M3 controlled retrieval handlers |
| NEW `tests/p5/knowledge/test_{projection,search,verification}.py` | Ordering, relevance tie breaks, scope, budgets, continuation rejection and failures |
| NEW `tests/p5/integration/test_search_elasticsearch.py` | Real ES mappings/bulk/PIT/refresh/readback/activation and outage recovery |

**Batches:** B1 projection/C1 + ES/client/embedding capability spike and capacity measurements; B2 durable indexing, independent verification, activation/recovery; B3 bounded search/cursors, freshness, rebuild/history and optional approved semantic branch. C1/limits/provider choices freeze before affected B2/B3 work.

**Acceptance/DoD:** equivalent canonical inputs produce identical record digests; missing/tampered records never activate; no cross-project/version hit; lexical exact identifiers outrank fuzzy ambiguity; every pagination binds generation; rebuild cannot remove readable historical generation; ES unavailable does not block diagrams/report. Real ES and PostgreSQL verification, relevance fixtures, resource evidence and C1 consumer approval complete.

### 15.3 M3 — Controlled Retrieval and Evidence Context

**Purpose/scope:** structured knowledge operations, entity resolution/ambiguity, search/graph retrieval planning, safe evidence projection and bounded ContextBundle. Excludes M3-like source semantics, new graph traversal implementation, AI answer synthesis or canonical identity merging.

**Dependencies/consumers:** M1/C0, M2/C1 for search; frozen P3 query and P4 graph contracts for exact details/traversals. C3 consumed by M6 and future P6. No independent fact database; optional bounded expiring query cache is derivative and keyed by scope/generation/query/schema. No cache is required for correctness.

**Interfaces/API/models:** `KnowledgeQueryService`, `RetrievalPlanner`, `EvidencePlanner`, `ContextBuilder`; `KnowledgeQueryRequest`, `EvidenceBundle`, `ContextBundle v1`. Entity lookup first uses exact canonical/record IDs, then qualified names; multiple candidates produce ambiguity, not forced resolution. API supports controlled operation enums and explicit limits.

**Lifecycle/background:** request-scoped, deadline/cancellation-bound; no background source analysis or new queue. **Failure:** distinguish partial optional capability failure from mandatory scope/evidence-integrity failure; never return an apparently complete context after hidden budget loss. **Security:** scope before retrieval, metadata-first evidence, controlled excerpt policy. **Metrics:** retrieval source latency, evidence considered/selected/omitted, ambiguity, capability failure, output bytes and budget failures; never log query/source content by default.

| File/action | Components, responsibility, dependencies and verification |
|---|---|
| NEW `backend/platform/knowledge/retrieval.py` | Query service/planner, exact resolution and stable fusion; calls existing public graph/query services only |
| NEW `backend/platform/knowledge/evidence.py` | EvidencePlanner, safe canonical source adapter and optional bounded excerpt adapter; range/encoding/path/secret tests |
| NEW `backend/platform/knowledge/context.py` | Immutable ContextBundle construction, dedup, budgets, preserved competing evidence and deterministic ordering |
| EXTEND NEW M2 `knowledge/contracts.py`, `dependencies.py` | C3 DTOs and DI; no redefinition of C1 search response |
| EXTEND NEW M2 `backend/api/v1/knowledge.py` | Knowledge query/context/evidence handlers, authorized scope and existing error envelope |
| NEW `tests/p5/knowledge/test_{retrieval,evidence,context}.py` | Ambiguity, direct-vs-doc strength, opposing evidence, Unicode/CRLF/BOM/non-UTF-8 coordinates, budget disclosure, cancellation |
| NEW `tests/p5/integration/test_knowledge_pipeline.py` | Search + frozen graph/canonical interfaces, unavailable Neo4j, cross-scope and generation change |

**Batches:** B1 C3 + exact resolution and controlled graph/search adapters; B2 evidence/context builders and security budgets; B3 API integration, optional excerpts only after safety approval, P6 consumer stub and failure acceptance.

**Acceptance/DoD:** same request/snapshot/config yields stable semantic context; no invented producer/fact key; unresolved/conflicting facts remain identified; context never exceeds approved budgets; outages preserve honest available capabilities; forbidden files never opened. C3 owner/consumer review and security/integration tests complete.

### 15.4 M4 — Diagram Intelligence

**Purpose/scope:** four semantic builders, DiagramSpec/LayoutSpec, server layout, storage/publication, safe exports and separate user presentation state. Excludes canonical entity creation, P4 graph query/lifecycle changes, new source detection and AI layout meaning.

**Dependencies/consumers:** M1/C0, published model source, approved C2 and layout helper packaging. No ES/Neo4j prerequisite for essential diagrams. Downstream M5/M6. PostgreSQL owns diagram generations/spec metadata/workspaces; local GeneratedArtifactStore owns immutable specs/layout/static assets.

**Interfaces/models/API:** `DiagramBuilder` template registry, `DiagramValidator`, `LayoutEngine`, `DiagramService`, `DiagramExporter`; DiagramSpec/LayoutSpec v1, DiagramResource/Generation, UserDiagramWorkspace. Status/spec/layout/history/export/retry/workspace APIs; see Section 17.

**Lifecycle/background:** independent work per template and fingerprint; M1 schedules/owns attempts and report prerequisite evaluation. M4 owns atomic artifact readiness with current fenced attempt; no report creation inside builders. **Failure/security:** helper timeout/resource/invalid output fails only that diagram, no script/URL fetching, active generation retained. **Metrics:** per-template build/layout/render/storage times, nodes/edges/group counts, omissions, fallback, helper peak RSS and retry/cache hit.

| File/action | Components, responsibility, dependencies and verification |
|---|---|
| NEW `backend/platform/diagrams/contracts.py`, `model.py` | C2 specs/layout/artifact/workspace types and resource transitions; reference/direction/scope/version validation |
| NEW `backend/platform/diagrams/builders.py` | Four cohesive pure builders and registry, shared selection/grouping utilities; avoid file per trivial helper |
| NEW `backend/platform/diagrams/validation.py` | Referential, vocabulary, coverage/omission, label/group and layout geometry checks |
| NEW `backend/platform/diagrams/layout.py` | Bounded headless LayoutEngine adapter, cancellation and allowed deterministic fallback |
| NEW `backend/platform/diagrams/layout_runtime/package.json` and generated lockfile; `layout_runtime/elk_layout.mjs` | Proposed isolated pinned ELK helper and narrow JSON protocol; no HTTP listener or Python/Express domain logic |
| NEW `backend/platform/diagrams/persistence.py`, `repository.py` | Diagram resource/generation/workspace metadata, unique input identity, fenced READY commit and artifact references |
| NEW `backend/platform/diagrams/service.py`, `export.py`, `dependencies.py` | WorkHandler, authorized status/retry/preferences and spec-based SVG/JSON export; uses M1/artifact store |
| NEW `backend/api/v1/diagrams.py` | Exact-version diagram/history/spec/layout/export/workspace routes; bounded DTOs |
| NEW `tests/p5/diagrams/test_{builders,spec,layout,exports}.py` | All templates, empty dataflow, endpoint direction, groups/bundles, deterministic semantics, layout bounds and malicious labels |
| NEW `tests/p5/integration/test_diagram_pipeline.py` | Headless helper kill/timeout/credentials isolation, restart, stored artifact verification, all-four readiness and sibling independence |

**Batches:** B1 C2 and four builders with canonical fixtures; B2 Linux ELK spike, helper/package approval, bounded layout and artifact readiness; B3 independent retries, export/workspaces and API integration. View-cap measurements and helper security gates precede production defaults; no unnecessary extra micro-module is required.

**Acceptance/DoD:** four correctly named independent outputs per version; normal-path overview-first policy verified; no Neo4j/ES dependency; canonical meaning/provenance preserved; groups and omissions explicit; helper cannot fetch network/source; failed candidate leaves previous generation; browser remains usable at approved budgets. C2 review, headless real execution, deterministic spec tests and visual acceptance complete.

### 15.5 M5 — Deterministic Architecture Report

**Purpose/scope:** prepare/validate ReportSpec, render one PDF, persist immutable artifact/history and expose retrieval. Excludes prerequisite polling, report scheduling ownership, new findings, executive summary or alternate report formats.

**Dependencies/consumers:** M1 C0/barrier, M4 C2/ready artifact references, existing canonical/analysis diagnostic query interfaces; approved renderer/fonts and strict report policy. M6 consumes C4. PostgreSQL owns report records/generations; generated artifacts are local/private behind the shared storage port.

**Interfaces/models/API:** `ReportPreparer`, `ReportValidator`, `ReportRenderer`, `ReportService`, `GeneratedArtifactStore`; ReportSpec, ReportResource, ReportGeneration, safe PDF metadata. The renderer is pure relative to prepared inputs and has no backend query capability.

**Lifecycle/background:** M1 schedules only after the strict barrier; preparation → validation → render → verify/store → READY. **Failure:** render/storage/validation failure retries independently and never downgrades diagrams/analysis; same fingerprint idempotent, changed inputs immutable new generation. **Security:** escape strings, no external font/image URLs, PDF no scripts/attachments/source dumps, safe private path and download names. **Metrics:** prerequisite wait (M1), preparation/render/storage bytes/duration, page count, retry, failures and report availability latency.

| File/action | Components, responsibility, dependencies and verification |
|---|---|
| NEW `backend/platform/reports/contracts.py`, `model.py` | C4 ReportSpec/section/reference/output types and immutable generation identity; mixed-version/invalid references rejected |
| NEW `backend/platform/reports/preparation.py` | Reads public canonical/analysis diagnostic ports, approved platform metadata snapshot, original severity, available completeness and exact prepared diagram artifacts; no new detection |
| NEW `backend/platform/reports/validation.py` | Required sections/overview, all-four provenance, scope/input digest/budget checks before render |
| NEW `backend/platform/reports/pdf.py` | ReportLab adapter only over prepared spec/assets; Unicode/fonts/pagination/vector layout; no DB/network DI |
| NEW `backend/platform/reports/persistence.py`, `repository.py` | Report metadata, immutable generations, readiness and safe history/download references |
| NEW `backend/platform/reports/service.py`, `dependencies.py` | Fenced handler, authorized retry/download and DI; calls M1 for scheduling, never polls diagrams |
| NEW `backend/platform/delivery/artifacts.py` | Shared P5 GeneratedArtifactStore port and bounded local implementation; path validation, atomic writes/digest/orphan reconciliation. Owned by M1 foundation, implemented with first M4/M5 storage use |
| NEW `backend/api/v1/reports.py` | Exact-version report list/status/retry/PDF response; scope, caching and safe headers |
| NEW `tests/p5/reports/test_{preparation,validation,pdf,storage}.py` | Missing/mixed diagrams, original severity, missing coverage, long/Unicode labels, path traversal, failed rename and renderer dependency isolation |
| NEW `tests/p5/integration/test_report_pipeline.py` | Concurrent report eligibility, retry after stored file/DB crash window, no partial download, pinned history and regeneration |

**Batches:** B1 C4, preparation/validation and PDF/font compatibility spike; B2 bounded renderer/local store/history with fixtures; B3 real M1/M4 automatic pipeline, download/retry/recovery and PDF visual evaluation. Optional future S3 adapter is not implemented.

**Acceptance/DoD:** automatic report waits for four same-version READY diagrams; overview embedded; original diagnostic severity and limitations intact; duplicate signals do not duplicate outputs; renderer has no data-query dependency; stored PDF verifies, cannot be overwritten, and is downloadable only with project access. C4/policy approval, visual pagination checks and real restart tests complete.

### 15.6 M6 — Platform Transport and Unified Frontend

**Purpose/scope:** minimal approved Express transport and repository-centered React workspace, search/knowledge/evidence, four diagram availability and report history/download. Separately approved durable preparation bridge may compose existing ingestion/analysis calls. Excludes graph/search business logic in Express, JWT redesign and duplicate dashboards.

**Dependencies/consumers:** C0–C5 as applicable; existing authentication/project RBAC/API client; Python output APIs. MongoDB has no P5 analysis/output authority; only optional platform preparation linkage is stored there. Browser state and user presentation settings do not become canonical architecture.

**Interfaces/API:** existing gateway with new bounded P5 route/controller methods and binary relay, domain React services/hooks/contract validators. Exact-version routes in Section 10 and external contracts in Section 17. **Lifecycle/background:** UI observes server state; requests cancel on scope change, terminal polling stops; optional preparation continuation is server durable, not browser lifetime. **Failure/security/metrics:** all status distinctions retained, 403 does not clear auth, no internal secret leaks, accessible keyboard/focus and safe downloads; UI request/poll/layout durations and safe correlation IDs.

| File/action | Components, responsibility, dependencies and verification |
|---|---|
| MODIFY `express/src/services/analysisGatewayService.js` | Reuse trusted forwarding/status contract; add bounded P5 JSON paths and download stream mode with content-type/length/header allowlist, abort/backpressure and client disconnect handling |
| NEW `express/src/routes/intelligenceRoutes.js`, `controllers/intelligenceController.js`, `validators/intelligenceSchemas.js` | Minimal authenticated route/DTO/role/scope transport; no Python domain duplication |
| NEW `express/src/routes/internalIntelligenceRoutes.js`, `services/intelligenceMetadataService.js` (subject to D11) | Reuse existing internal service authentication; validate project→repository→revision ownership and return only approved display/revision fields. No parallel authentication or database authority |
| MODIFY `express/src/routes/index.js` | Add P5 routes after scoped approval; retain existing routes |
| NEW `express/src/services/repositoryPreparationService.js`, `models/repositoryPreparationModel.js` (conditional) | Only approved durable ingestion→analysis linkage; stable idempotency, actor revalidation and continuation policy; not a general replacement ingestion service |
| MODIFY `frontend/src/App.jsx` | Exact intelligence route parsing and workspace registration with shared header/ProtectedRoute |
| MODIFY `frontend/src/pages/RepositoryDetailPage.jsx`, `AnalysisDetailPage.jsx`, `ArchitectureModelPage.jsx`, `ArchitectureExplorerPage.jsx` | Output entrypoints/progress/download and exact-version cross-links; preserve current workflows |
| NEW `frontend/src/pages/RepositoryIntelligencePage.jsx` | One tabbed workspace, explicit version context and output availability |
| NEW `frontend/src/components/intelligence/{DiagramPanel,SearchPanel,KnowledgePanel,ReportPanel,EvidencePanel}.jsx` | Cohesive tab panels, shared bounded evidence drawer and accessible forms; no giant unrelated component |
| NEW `frontend/src/services/{knowledgeService,diagramService,reportService,deliveryService}.js` | Existing apiClient-only domain calls, pagination/cancellation, authenticated binary download adapter |
| NEW `frontend/src/contracts/intelligenceContracts.js` | C1–C5 consumer validation, version and identity guards; no invented DTO fields |
| NEW `frontend/src/hooks/{useIntelligenceDelivery,useDiagramWorkspace}.js` | Abortable nonoverlapping polling, stale-result guards and stable layout/camera/user preferences |
| NEW `frontend/src/workers/diagramLayout.worker.js` | P5 presentation layout protocol with pinned ELK; independent of frozen graph worker |
| NEW `frontend/src/styles/intelligence.css` | Existing dark-theme tokens/layout patterns, responsive tabs/canvas/table/drawer, visible focus and limited wrapping |
| NEW `express/tests/integration/intelligenceRoutes.test.js`, `express/tests/unit/intelligenceGateway.test.js` | Auth/RBAC/scope, repeated filters, 202/403/404/409/410/422/5xx, stream timeout/disconnect and no unsafe upstream detail |
| NEW `frontend/tests/component/{RepositoryIntelligencePage,DiagramPanel,SearchPanel,ReportPanel,IntelligenceNavigation}.test.jsx` | Loading/empty/error/capability, history, exact version, camera/selection, pagination, terminal polling and keyboard behavior |
| NEW `express/tests/integration/repositoryPreparation.test.js` (conditional) | Duplicate ingestion completion, revoked actor, restart and exact revision/idempotency handling |

**Batches:** B1 scoped Express approval + C5 transport/streaming and route/component shells; B2 diagram/search/knowledge panels and existing-page navigation; B3 reports/history/download and optional approved preparation bridge, accessibility and full UI regression. Layout-worker prototyping can run parallel after C2; live integration waits for C5. No React direct Python fallback.

**Acceptance/DoD:** complete output journey through Express; no credential exposure or swallowed status; all four diagrams progressively visible; search/context/pagination version safe; report accessible from analysis and workspace; evidence never buries actions; no horizontal all-node spaghetti default or selection/camera oscillation. Required frontend/Express suites and frontend production build pass; no claim of lint/type commands that do not exist.

### 15.7 M7 — Integration, Evaluation and Closure

**Purpose/scope:** evaluate complete deterministic P5 and frozen dependency regressions under real infrastructure, failures, security and realistic repository sizes. No new product feature or relaxed frozen threshold. **Dependencies:** all module contracts and integrated implementations; test harness starts in parallel. **Consumers:** owner acceptance/future P6.

**Models/API/persistence/lifecycle:** no production domain ownership; uses approved public interfaces, isolated test databases/indexes/artifact directories and exact-version fixtures. No new queue or event vocabulary. **Failure/security/metrics:** exercise malformed upstreams, tenant leaks, broker/ES/Neo4j/storage loss, cancellation and stale attempts; collect reproducible queue/process/end-to-end metrics, current/peak RSS in the correct isolated processes and capacity reports.

| File/action | Responsibility and verification |
|---|---|
| NEW `tests/p5/integration/test_intelligence_e2e.py` | Published successful analysis → four diagrams → automatic report; search failure independence, historical exact version and full auth flow |
| NEW `tests/p5/integration/test_delivery_recovery.py` | Broker downtime, restart at each commit/storage boundary, concurrent retry and retained previous generations |
| NEW `tests/p5/integration/test_intelligence_security.py` | Cross-project/version IDs, forged trusted context, path/label injection, prohibited artifact reads and output leaks |
| NEW `tests/p5/benchmarks/test_intelligence_capacity.py` | Representative/max canonical models, deep/wide/disconnected layouts, bulk indexing/context/PDF budgets; subprocess-isolated measurements |
| NEW `frontend/tests/component/IntelligenceAccessibility.test.jsx` | Keyboard, focus restoration, responsive table/drawer and color-independent state labels |
| NEW `express/tests/integration/intelligenceFlow.test.js` | Real gateway contract to Python fixture/server; safe binary transfer and status fidelity |

**Batches:** B1 acceptance fixtures/harness/baseline budgets; B2 full infrastructure/fault/security/regression/performance evaluation; B3 owner live UX acceptance, runbook/known-limit review and freeze proposal. Future documentation updates are to existing context/plan only after separate authorization; none made now.

**Acceptance/DoD:** Section 27 passes with exact commands/environment/results recorded; failed/skipped infrastructure checks explicitly blocked rather than counted as passed. Owner accepts resource limits, pending policy decisions and known limitations before freeze. M7 does not infer correctness from pass/fail ratio alone.

### 15.8 Future composition/configuration inventory and frozen-boundary control

These existing files were inspected or located and are **future additive changes only, pending D2**. No module may use this list to refactor frozen internals.

| Existing file | Future change and owner | Restriction |
|---|---|---|
| `backend/worker/celery_app.py` | M1 adds P5 task module/beat registration using existing queue | Preserve P3/P4 routes, acknowledgement, lifecycle and recovery behavior; no new queue |
| `backend/api/v1/router.py` | M1/M2/M4/M5 register new routers | Preserve existing routers/DTOs/authentication |
| `backend/infra/migrations/env.py` | M1 registers P5 model metadata | New additive migrations under `backend/infra/migrations/versions/`; exact revision filenames generated later, no edits to frozen migrations |
| `backend/platform/config.py` | Module-owned additive P5 settings | No altered existing defaults/limits; proposed P5 values require measurements and approval |
| `requirements.txt` | M2 ES client; M5 PDF/font-related runtime dependencies if approved | Exact pins only after Python 3.14/Linux compatibility checks; do not claim packages already installed |
| `infra/docker/compose.yml` | M2 local Elasticsearch service, persistent volume and secure health/auth configuration | Existing PostgreSQL/RabbitMQ/Neo4j untouched; ES justified by master, version/resource budget pending D3 |
| `.env.example`, `.env` | Later additive approved P5 settings; synchronize names without publishing secrets | No environment edits in planning; no placeholder default production passwords |
| `frontend/package.json` and lockfile | Only measured dependency changes if required; current React Flow/ELK reused | Do not reinstall/upgrade packages just because a new phase starts |

P3 `analysis/architecture/repository.py`, `persistence.py`, frozen handoff files, P4 lifecycle/query/projection files and ADR-0001 are **RETAIN/READ ONLY**, not implementation targets. A genuinely missing public port is a change-control issue, not permission to import private repositories or edit frozen contracts.

## 16. Data Models and Persistence

### 16.1 Ownership and invariants

| Proposed record | Authority/location | Immutable identity and constraints |
|---|---|---|
| DeliveryBundle | Python PostgreSQL, M1 | Project/version/policy fingerprint unique; exact published source digest and analysis success proof |
| DerivedWork / WorkAttempt | Python PostgreSQL, M1 | Type/resource/input fingerprint unique; current attempt token, lease expiry, monotonic fencing/version; attempts append-only |
| SearchProjection / generation receipt | Python PostgreSQL, M2 | Exact project/version plus index schema/projector/embedding fingerprint; candidate separate from active pointer |
| Knowledge document | Elasticsearch, M2 | Generation-scoped storage key, copied canonical references, scope/digest/schema; no source body |
| DiagramResource / DiagramGeneration | Python PostgreSQL, M4 | Project/version/template/config fingerprint; immutable spec/layout/asset digest references; prior ready generation retained |
| UserDiagramWorkspace | Python PostgreSQL, M4 | Actor/project/version/template and base generation; presentation-only; optimistic updates |
| ReportResource / ReportGeneration | Python PostgreSQL, M5 | Report type/version/template/four-diagram/data/renderer fingerprint; immutable PDF/spec metadata |
| PlatformMetadataSnapshot (subject to D11) | Python P5 input snapshot, not platform authority | Exact project/repository/revision UUIDs, approved safe names/revision fields, captured-at and digest; Express remains authoritative for live platform metadata |
| GeneratedArtifact | Metadata PostgreSQL; private bytes local store | Opaque key, owner scope, media type, byte length/content digest; stage then verify then READY |
| RepositoryPreparation (conditional) | Express MongoDB, M6 | Actor/project/repository/request key, exact ingestion/revision/analysis IDs, durable continuation state; no analysis data duplication |

No derived store assigns canonical logical IDs. UUID persistence IDs, canonical logical IDs, P5 artifact IDs and presentation group IDs remain separate fields/types. Foreign-key/unique constraints enforce local relationships; cross-service ownership is checked through APIs, not database joins.

### 16.2 Retention and consistency

Recommended initial policy: retain published historical diagram/report artifacts and readable search generations until owner approves an explicit retention policy; no destructive automatic deletion of published outputs. Failed candidates/staging/PITs use bounded cleanup after approved grace periods, checking active pointers and leases. Retention changes need audit, reader safety and deletion recovery implications.

Search candidates coexist with active generation. Diagram/report publication is a fenced PostgreSQL state transition after durable blob verification. A storage file and database transaction are not magically atomic: staged/orphan recovery reconciles their crash windows; READY must never reference an unverified/missing file. Download integrity failure returns a safe availability error and repair action, not corrupt bytes.

## 17. API and Service Contracts

### 17.1 Proposed common contract

All new APIs below are **proposed**, not existing endpoints. FastAPI path prefix `/api/v1`; Express exposes the same domain path under its existing API prefix. React uses its existing Express apiClient. `project_id` is required query context even when resource path contains a version; delegated project must match. Responses carry exact `scope: {project_id, repository_id, analysis_id, snapshot_id, architecture_version_id}`, schema and safe correlation metadata.

`Page<T> = {items:T[], next_cursor:string|null, limit:number, total:number|null, scope, generation_id?}`; total is nullable when an exact count is intentionally unavailable, never fabricated. Every mutable-generation pagination operation binds its generation; immutable report/diagram history binds scope/query and a stable high-water snapshot. No silent continuation across a changed generation. Errors preserve 401/403/404/409/410/422/429/503/504 distinctions; asynchronous accepted work returns 202 with durable resource/work IDs, not completed success.

Proposed initial numerical budgets for **measurement and owner approval**, not frozen production defaults: page 50/max 100; query 512 UTF-8 bytes; evidence page 25/max 100; metadata ContextBundle 256 KiB and at most 100 selected evidence records; optional excerpts aggregate 32 KiB; query deadline 5 seconds end-to-end. Index batch bytes/count, helper/PDF CPU/RSS/time/output, diagram edge cap, retention/PIT expiry, polling and worker fairness remain benchmark outputs. Existing P3/P4 approved limits are unchanged. Exceeding a mandatory integrity/capacity budget fails closed; a bounded view/context discloses intentional selection/omissions, never claims completeness.

### 17.2 Endpoint inventory and payloads

Let `V=/architecture-versions/{versionId}`. Every row requires authenticated project membership; mutation role proposal is owner/admin/developer, viewer read-only, subject to existing operation-specific RBAC inspection at C0. Do not assume a new owner-only policy or grant viewers rebuild/retry rights.

| Proposed method/path | Request | Success response / important behavior | Owner |
|---|---|---|---|
| GET `V/delivery` | project_id | 200 `{scope, diagrams:[{template_id,state,artifact_id?,work_id?,error?}], search, report, waiting_on}` | M1 |
| POST `V/delivery/retry` | `{resource_type,resource_id,idempotency_key}` + project | 202 `{work_id,resource_id,state,scope}`; allowlisted exact resource only | M1 |
| GET `V/search/status` | project_id | 200 `{scope,resource_state,freshness,is_readable,active_generation?,attempt?,capabilities}` | M2 |
| POST `V/search/rebuild` | `{idempotency_key}` + project | 202 `{resource_id,work_id,state}`; previous verified remains readable | M2 |
| GET `V/search` | q, mode, repeated kind/status filters, limit, cursor, project_id | Page<SearchHit>; explicit semantic-unavailable, stale generation and expired cursor errors | M2 |
| POST `V/knowledge/query` | `{operation,subject:{entity_id? or logical_id?},filters,limits,cursor?}` + project | 200 `{scope,operation,subjects,items,ambiguity?,capabilities,limits,omissions,next_cursor?}`; unsupported operation 422 | M3 |
| POST `V/knowledge/context` | `{subjects,question_hint?,operations,budget}` + project | 200 ContextBundle v1; question_hint is bounded retrieval text, never an interpreted AI question | M3 |
| GET `V/knowledge/evidence` | repeated entity_id/relationship_id/evidence_id filters, limit,cursor,project_id | Page<EvidenceItem>; canonical metadata by default; explicitly budgeted excerpt capability only | M3 |
| GET `V/diagrams` | project_id | 200 `{scope,items:[DiagramSummary x4]}`; each state independent | M4 |
| GET `V/diagrams/{templateId}` | project_id, optional exact generation_id | 200 `{scope,template_id,state,generation_id?,fingerprint,warnings,artifact_refs}`; absent/pending is not falsely READY | M4 |
| GET `V/diagrams/{templateId}/generations` | project_id,limit,cursor | Page<DiagramSummary>; immutable generation history | M4 |
| GET `V/diagrams/{templateId}/generations/{generationId}/spec` | project_id | 200 DiagramSpec; matching scope/generation required | M4 |
| GET `V/diagrams/{templateId}/generations/{generationId}/layout` | project_id | 200 LayoutSpec; matching spec digest/profile required | M4 |
| GET `V/diagrams/{templateId}/generations/{generationId}/export` | project_id, format=json or svg | 200 bounded validated content with safe media/disposition; not report format selection | M4 |
| POST `V/diagrams/{templateId}/retry` | `{idempotency_key}` + project | 202 work/resource; approved retry policy, does not delete prior ready artifact | M4/M1 |
| GET/PUT `V/diagrams/{templateId}/workspace` | project_id; PUT `{base_generation_id,revision,positions,collapsed_groups,filters}` | 200 presentation preferences; optimistic revision conflict 409; actor scoped and bounded | M4 |
| GET `V/reports` | project_id,limit,cursor | Page<ReportSummary>, report_type fixed architecture_analysis; explicit prerequisite wait | M5 |
| GET `V/reports/{reportId}` | project_id | 200 `{scope,id,state,generation,template_version,prerequisites,created_at,ready_at?,size?,digest?,error?}` | M5 |
| POST `V/reports/{reportId}/retry` | `{idempotency_key}` + project | 202 work/resource only if prerequisites still refer to the pinned valid inputs | M5/M1 |
| GET `V/reports/{reportId}/download` | project_id | 200 `application/pdf`, bounded stream, safe filename/length/digest/cache headers; not READY →409, unavailable bytes→503 | M5/M6 |
| POST `/projects/{projectId}/repositories/{repositoryId}/preparations` (conditional) | existing valid ingestion input or existing revision_id, approved analysis config, idempotency_key | 202 `{preparation_id,state,ingestion_id?,revision_id?,analysis_id?}`; no source-contract changes | M6 |
| GET `/projects/{projectId}/repositories/{repositoryId}/preparations/{id}` (conditional) | authenticated scope | 200 preparation status/linkage; internal continuation not user-callable arbitrary task | M6 |
| GET `/internal/intelligence/projects/{projectId}/repositories/{repositoryId}/revisions/{revisionId}/metadata` (D11 approval required) | Existing internal service authentication, exact identifiers; not exposed through browser routes | 200 `{project_id,project_name,repository_id,repository_name,revision_id,revision_identifier,source_hash}` with unavailable optional values explicit; ownership mismatch rejected | M6 transport / M1 input adapter |

SearchHit fields: record/document kind, canonical reference and record UUID where established, name/path, static status, safe excerpt/summary only if authorized, relevance score/rank metadata, evidence references, source generation/freshness. EvidenceItem preserves actual source record type, optional fact/producer fields and canonical range. DiagramSummary includes counts/coverage/limitations and exact generation. No API promises unsupported language statistics or a synthesized security score.

`KnowledgeQueryRequest.operation` is a closed set: `lookup`, `relationships`, `dependencies`, `dependents`, `containment`, `paths`, `evidence`. Path queries also require `target:{entity_id or logical_id}`. Direction, relationship-kind filters, hop/path/node/edge limits map to existing P4 DTOs: dependencies/dependents retain all twelve approved non-containment kinds; containment uses parents/children/both separately. Every returned continuation binds all participating graph/search generation IDs and query parameters; a changed generation rejects continuation even if another data source is unchanged. One operation deadline covers adapters, database execution/iteration, mapping and final pointer verification; cancellation must terminate underlying work, not just abandon the response future.

### 17.3 Transport and downloads

Express reuses existing trusted service/actor/role/project/correlation forwarding and project authorization. Serialize repeated filters with `append`, not comma joining. Reject unknown/oversized query/body fields and enforce bounded upstream timeout; propagate meaningful upstream status and safe error shape, including 202, 403, 404, 409, 410 and 422. Do not convert all failures to 502.

Download relay must be a bounded/backpressure-aware extension of the gateway, abort on client disconnect/timeout, validate media type/length and safe headers, and never buffer an unbounded PDF with JSON handling. Proposed first version supports full PDF download; Range requests may be explicitly rejected unless end-to-end support is implemented/tested. No public local path, public bucket, unauthenticated URL, browser internal-service token or arbitrary proxy URL.

## 18. Background Processing and Orchestration

### 18.1 Durable flow

1. A P5-owned reconciler pages the existing public published-version reader, checks successful terminal analysis (`COMPLETED`/`COMPLETED_WITH_WARNINGS`) through existing read interfaces, validates exact scope/digest and upserts a delivery bundle/work set transactionally.
2. Commit before broker dispatch. Dispatch messages contain only work/project/version/contract/correlation IDs; handlers reload durable configuration and immutable input references.
3. Search projection and overview work may run independently. Overview normally becomes READY before remaining diagram tasks are released; Section 8's failure-path policy prevents blanket sibling failure.
4. Every handler claims current work, renews bounded leases and publishes only with the matching attempt/fence. Expired/stale completions cannot mutate active outputs or unblock dependents.
5. Diagram READY causes a durable eligibility check. All four exact-version refs are pinned and one unique report request is created; concurrent events/reconciliation cannot duplicate it.
6. Report preparation/render/storage completes independently; frontend observes compact delivery summary. Failed branches expose honest retry/wait reasons.

No new analysis stage or mandatory analysis completion dependency is introduced. Publication discovery also covers versions created before P5 deployment; bounded backfill policy/checkpoint and live discovery are separate so historical work cannot starve new publications.

The existing published-source cursor sorts project/repository/sequence/version; it is **not a globally append-only publication timestamp/change feed**. A newer publication may sort before a saved cursor. Complete bounded reconciliation sweeps must therefore reset at the end and deduplicate by durable version identity, with a measured maximum sweep age; never keep a permanent high-water cursor and assume earlier keys cannot appear. If a publication is observed before the analysis reaches successful terminal state, persist a pending eligibility record and revisit it, rather than advance the scan and lose it. Use the existing source port without adding a P3/P4 hook. If bounded sweeps cannot meet the approved discovery latency at measured scale, request explicit change control for a suitable discovery interface rather than silently modifying frozen source contracts.

### 18.2 Queue reuse, fairness and recovery

Recommendation: reuse the existing Celery/RabbitMQ setup and existing `analysis.jobs` queue for registered P5 tasks after explicit capacity/composition approval; introduce **no diagram-specific queue**. Small bounded tasks, separate work-type concurrency quotas/admission control and staged dispatch prevent unbounded derivative fan-out. Existing worker concurrency is small; do not promise three diagrams execute simultaneously or rely on unconfigured RabbitMQ priorities.

Tradeoff: shared queue simplifies deployment but can delay analysis. Measure new analysis latency under P5 load before approval. If acceptable fairness cannot be achieved, return for approval of another existing-queue/worker allocation; do not quietly add a queue, modify frozen routing or raise global concurrency/memory.

Use bounded reconciliation with backoff, jitter, retry classification and maximum attempts approved after measurements. Recover broker loss, lost worker and file/DB crash windows from durable records. Retry transient I/O/dependency failures, not deterministic invalid specs or capacity failures without changed inputs/configuration. Explicit retry/rebuild keeps previous ready outputs readable and records audit context.

## 19. Lifecycle and State Transitions

These are proposed **new P5 resource contracts**, not changes to F1 or frozen P4 states.

| Layer | Proposed semantics |
|---|---|
| P5 work | PENDING → QUEUED → RUNNING → COMPLETED; RUNNING → RETRYING → QUEUED for retryable failure; final FAILED or CANCELLED. Each retry has an append-only attempt and a new fenced ownership token |
| Diagram generation | PENDING → BUILDING → READY or FAILED; retry uses a new attempt, never mutates a published generation's bytes. Resource can retain last_ready_generation during candidate failure |
| Report eligibility | WAITING_FOR_DIAGRAMS is a delivery-summary prerequisite condition, not an already scheduled ReportJob polling state |
| Report generation | PENDING → PREPARING → RENDERING → STORING → READY or FAILED; phase progress maps to RUNNING work. Retry after failure is explicit; published PDF immutable |
| Search resource | PENDING/RUNNING/COMPLETED/FAILED/STALE as derivative resource vocabulary; readiness/freshness/attempt dimensions in Section 7. No active generation + final failure →FAILED; active historical generation remains STALE/readable after failed rebuild |
| Presentation workspace | Mutable user state with optimistic revision and base generation; not part of canonical lifecycle |

Cancelling derivative work cannot cancel a completed analysis or remove an active artifact. A late success after cancel/lease expiry is rejected. A historical requested version remains exact and readable when its artifact is retained; not-current status is never permission to serve a different version.

## 20. Security and Authorization

Preserve ADR-0001 trusted delegation, constant-time service-token verification, actor UUID/project validation and operation-specific project RBAC. Initial proposal follows existing analysis/graph mutation roles; C0 must inspect each retained backend authorization rule before freezing role-action mapping. Frontend visibility is usability, never the security boundary. Viewers cannot trigger rebuild/retry merely by calling Python directly.

Every source record, index hit, graph operation, artifact download and workspace update is scoped to authorized project and exact version. Historical version access does not bypass current membership. New routes reject ownership-chain mismatch and sanitized query injection; no user-submitted paths, raw DSL/Cypher or client-supplied trusted headers are forwarded unverified.

Allowlist searchable/renderable content. Never open prohibited sensitive artifacts for excerpts. No raw repository content in ES/Neo4j/PDF/logs. Internal URLs, headers, storage keys and secrets stay server-side. Exports escape malicious labels; SVG has no scripts, external references or executable links; PDF/fonts/assets are local approved resources. Layout helper has no unnecessary inherited credentials/descriptors/network.

Request limits, streaming/output ceilings, bounded graph/search deadlines, worker admission and per-project rate limits prevent computational abuse. Dependency/license review includes ES distribution, client, ELK helper, ReportLab and fonts; do not claim an unperformed vulnerability audit or compatibility result.

## 21. Observability and Reliability

Correlate project/version/work/attempt/template/report IDs across Express/Python/worker logs without logging query text, source or auth by default. Distinguish:

- Queue wait = claim/start minus enqueue; processing = stage start-to-finish; delivery end-to-end = publication to READY; diagram/report dependency wait is separate.
- Build/write/verify/activate, layout helper startup/execution/serialization, PDF prepare/render/store and search execution/iteration/mapping times.
- Candidate/active generation, expected/actual counts/digests, stale-attempt rejection, lease expiry, retry/final failure, omitted view/evidence counts, cache hits and cleanup/orphan backlog.

Health distinguishes API availability, ES reachability/schema, queue dispatch and worker heartbeat, artifact storage capacity, layout runtime/font readiness and exact-resource availability. An ES outage must not declare the canonical platform unavailable or block essential diagrams/PDF. Do not expose detailed internal health topology publicly.

Runbook requirements for later implementation: broker outage/reconcile, ES rebuild/reindex, helper timeout/kill, disk full/corrupt artifact, stale lease, failed report prerequisites, historical restore/retention, safe retry and tracing a version. Keep existing successful generation readable during candidate work; never claim “ready” based only on task completion.

## 22. Testing and Evaluation Strategy

### 22.1 Required suites and fixtures

| Level | Required evidence |
|---|---|
| Pure contracts/determinism | Published model fixtures permuted in input order; exact stable keys/spec/context/report semantic digests; unsupported schema fails; no fabricated IDs/provenance/status |
| Canonical semantics | Express/FastAPI/Django/React mixed examples using already established entities; contains distinct from dependency; canonical edge direction; no-runtime-claim data flow; empty valid diagram |
| Evidence/security | Unicode/CRLF/BOM/non-UTF-8 coordinates, optional fact keys, secret paths never read, HTML/SVG/PDF label injection, cross-project/version and forged actor context |
| Real persistence/search | PostgreSQL uniqueness/fencing/rollback; ES missing/tampered/duplicate records, partial bulk, PIT expiry, generation swap during continuation; actual compatibility version recorded |
| Worker/recovery | RabbitMQ interruption, process death before/after each DB/blob/broker boundary, concurrent retry/reconcile, revoked permissions, stale work, overview failure and independent siblings |
| Automatic report | No report for 0–3 READY diagrams or mixed versions; one report for concurrent fourth completion; all refs pinned; report failure preserves upstream; no renderer DB/network access |
| Visual/UX | Deep/wide/disconnected graphs, responsive workspace, long labels, stable camera/selection and exact-node focus; evidence collapsed/paged, keyboard/focus/contrast, readable PDF typography/diagram/pages |
| Performance | Small/medium/near-canonical-limit models, 500-node candidate view, high edge fanout, 75k evidence metadata; separate parent/helper RSS and wall/CPU/I/O; cold/warm cache; shared queue fairness |
| Regression/E2E | Existing auth/session/project/repository/ingestion/analysis/model/graph flows; complete Express-facing output journey; historical version and unavailable dependency branches |

Benchmark in fresh subprocesses and report current RSS and peak RSS separately; parent pytest lifetime `ru_maxrss` is not a per-workload or helper measurement. Preserve production parser isolation/512 MiB guarantee and previously approved memory remediation. Any new limit must name process, unit, workload and rejection behavior; do not raise frozen thresholds to pass.

### 22.2 Exact future verification commands

These are proposed implementation verification commands, **not executed during planning**. New test paths become valid only when their approved batches create them. Run from repository root unless a subshell specifies otherwise.

```sh
./venv/bin/python -m pytest tests/p5/delivery tests/p5/knowledge tests/p5/diagrams tests/p5/reports
./venv/bin/python -m pytest tests/p5/integration
./venv/bin/python -m pytest tests/p5/benchmarks
./venv/bin/python -m pytest tests/p1 tests/p2 tests/p3 tests/p4
./venv/bin/python -m pytest
./venv/bin/python -m black --check .
./venv/bin/python -m ruff check .
./venv/bin/python -m mypy backend
./venv/bin/python -m pip check
(cd express && npm test)
(cd frontend && npm test)
(cd frontend && npm run build)
git diff --check
git status --short
```

The `tests/p1` through `tests/p4` directories and `.github/workflows/ci.yml` Python quality commands were verified; the final full pytest command remains the authoritative broad regression. Infrastructure tests must use explicitly isolated PostgreSQL/ES/RabbitMQ/artifact resources and the repository's actual marker/environment conventions, inspected before execution. Do not run against user data or classify skipped real-service tests as passed. Existing package scripts define no frontend/Express lint/format/type-check commands; report that honestly rather than inventing scripts. New headless helper tests use its approved package scripts, to be specified at its compatibility freeze. CI configuration is read-only in this task.

## 23. Implementation Sequence

1. **Owner review first:** approve module/scope/policy decisions, resolve frozen composition and scoped Express authorization, agree semantic capability and server layout direction; reconcile P4 closure evidence without rewriting history.
2. **Early targeted prototypes within approved B1s:** Python 3.14 + ES exact client/server, headless ELK Linux isolation/packaging/layout quality, ReportLab fonts/PDF vector rendering, shared queue memory/fairness. No prototype runs in this planning task.
3. **M1 contracts/foundation:** freeze C0; real PostgreSQL claims/dispatch and report barrier; integration fixtures. Implement shared artifact storage when first consumer needs it rather than a speculative storage framework.
4. **Parallel:** M2 search and M4 diagram domain; M7 harness and M6 route/component shells after C1/C2. Freeze measured caps before full-scale extraction/indexing/layout.
5. **Consumers:** M3 after C1; M5 after C2/C4 fixtures; complete all four M4 outputs and independent readiness. Express integration after C5, not guessed DTOs.
6. **M6 full integration:** progressive output UX, search/context, reports/download and optional explicitly approved preparation bridge; preserve operational views.
7. **M7 closeout:** real end-to-end/fault/security/performance and regression; exact evidence/limitations; owner live acceptance and explicit freeze approval.

Critical path: approvals → M1/C0 → M4/C2 + server layout → four READY artifacts → M5 automatic PDF → M6/M7 acceptance. Search/retrieval is a parallel mandatory branch that must also finish before P5 closes. Highest effort is diagrams and cross-service UX; highest integration risk is durable scheduling/authority and storage/DB crash windows. No calendar estimate is supplied without measured compatibility and workload evidence.

## 24. Risks and Mitigations

| Risk | Impact | Mitigation / gate |
|---|---|---|
| Frozen composition edited as ordinary implementation | P3/P4 contract regression | D2 explicit additive-only authorization; read-only source ports; regression/diff review |
| Shared queue starves new analyses | User-visible delay despite fast extraction | Bounded fan-out/admission, overview priority policy and measured queue fairness before defaults |
| Layout requires browser or produces unreadable wide ranks | Reports stuck or unusable diagrams | Headless ELK spike; compound packing/focus, bounded visible view and actual visual acceptance |
| ES/embedding package/model unsupported or expensive | Search blocked, privacy/memory exposure | D3/D4 pinned compatibility and capability gating; no hidden external provider |
| Report assumes F2/language/full findings data persisted | Misleading report or illegal parser rerun | Read actual canonical completeness/diagnostics; missing data explicitly unavailable |
| Four-diagram barrier conflicts with global fallback | Unapproved behavior change | D1 scoped product policy acceptance; renderer still decoupled; no text-only P5 scheduling |
| A diagram failure cascades or duplicate signals produce reports | Lost output/duplicate PDF/history | Independent resources, unique fingerprints, transactional prerequisite pinning and recovery tests |
| Truncation/grouping presented as full topology | False architecture | Canonical references, explicit omissions, presentation-only groups and expandable views |
| Source excerpts expose secrets or wrong ranges | Confidentiality/integrity failure | Metadata-only baseline; explicit safe read/encoding/redaction gate; forbidden files never opened |
| Previous P4 records and closure claims disagree | Bad dependency assumption | Distinguish owner freeze from unverified M6 record; accept evidence or narrowly validate dependency |
| Disk full/orphaned bytes or failed rebuild removes good data | Lost historical output | Staging/digest/atomic rename, fenced metadata readiness, conservative retention and crash recovery |
| Convenience latest links mix versions | Search/diagram/report mismatch | Resolve once to explicit version; immutable pinned artifact refs and generation-bound cursors |

## 25. Architecture Decisions and ADR Requirements

### 25.1 Established and verified decisions retained

| Classification | Decision/evidence |
|---|---|
| Established by master | Canonical Architecture Model before derived graph/search/diagram; bounded evidence/context; renderer-independent diagrams; ELK/React Flow direction; report preparation separated from rendering |
| Existing accepted ADR | ADR-0001 Express/Mongo platform, Python/PostgreSQL analysis ownership, trusted internal APIs and no cross-DB access |
| Frozen prior contracts | F1/F2/F3/Architecture Model v1 and P4 lifecycle/query/verification/generation semantics; no reopening analysis pipeline |
| Prior owner product decision | Repository/output-first UX direction, preserve existing dark style and advanced drill-downs |
| Current owner requirement | Four automatic independent diagrams, overview priority, strict all-four-ready automatic report, one PDF type, no P5 executive summary/documentation comparison |
| Verified current implementation | Existing published source port, graph query API, gateway, exact-version React routes, installed frontend React Flow/ELK; analysis Job is not a generic job |

### 25.2 Proposed decisions requiring review

| ID / problem | Viable alternatives and tradeoffs | Recommendation / frozen impact / blocking scope |
|---|---|---|
| D1 — Strict report prerequisites versus master fallback | Enforce all four in P5 orchestration (matches brief, delays report on failed diagram); allow text fallback (more available, violates current brief); seek master change (unnecessarily broad unless interpretation rejected) | Scoped P5 product policy, renderer remains general. Owner acceptance before C0/C4; no unilateral master edit |
| D2 — Frozen infrastructure composition and global no-new-Express restriction | Read-only adapters alone cannot register workers/routes; approved additive composition plus transport is narrow; private imports/parallel gateway violate boundaries | Explicit approval for Section 15.8 additions and M6 P5 transport/streaming, preserve all frozen behavior. Blocks production wiring and Express implementation, not pure fixture contracts |
| D3 — Elasticsearch deployment/client/schema | Self-hosted pinned compatible ES/client (local reproducibility, resource/operations cost); managed ES (operations easier, cost/credentials); alternative search engine (architecture departure) | ES per master; choose exact supported server/client pair after Python 3.14/Linux/TLS/auth/bulk/PIT spike. New ES infrastructure justified, no version silently frozen. Blocks M2 real indexing |
| D4 — Semantic retrieval provider | Lexical+graph first with explicit disabled semantic capability (deterministic/private, no vector similarity); offline pinned embeddings (resource/licensing/model packaging); external provider (privacy/network/cost/reproducibility) | Mandatory lexical/graph baseline; owner chooses whether semantic adapter is required in initial P5 acceptance. Provider/model/dimensions must freeze before semantic implementation; no claim disabled semantic fulfills an approved mandatory semantic feature |
| D5 — Automatic server layout | Bounded Node ELK helper (same layout ecosystem, adds worker Node runtime); separate layout service (extra service/ops, not recommended); Python fallback engine (less dependency, layout divergence and extra implementation) | Approve helper after spike; no new service/queue; preserve P4 worker protocol. Blocks automatic diagram READY/report path |
| D6 — PDF renderer/fonts/export scope | ReportLab vector PDF (small renderer, manual typography); HTML/browser rendering (flexible, heavier/security cost); other Python PDF library (compatibility/layout unknown) | ReportLab proposal + approved fonts; PDF-only report, JSON/SVG diagram exports. Confirm optional PNG/diagram-PDF deferral. Blocks production M5 rendering |
| D7 — Queue/resource limits/priority | Existing shared queue (simple, contention); existing queue allocation with dedicated worker admission (isolation, deployment cost); new queue (outside brief) | Existing queue, bounded staged dispatch and measured admission; approve every operational cap and retry/retention value after B1 measurements. Overview-first normal path plus sibling release after terminal overview failure needs acceptance. Blocks production defaults |
| D8 — One-action preparation continuation | Browser-only chain (no persistent authority contract, fragile); durable Express bridge (reliable, needs Mongo workflow and actor continuation approval); retain explicit ingestion/analysis (least change, partial UX goal) | Durable bridge only with explicit scoped approval/authority policy; otherwise clearly defer and retain existing initiation. Does not block post-publication P5 outputs |
| D9 — Retention/excerpts/report regeneration | Preserve published artifacts + metadata-only evidence (safe storage/privacy default); bounded retention/excerpts/autoregeneration (richer/cheaper but deletion/security/cascade risks) | Preserve histories, conservative staged cleanup, metadata evidence; explicit decisions for excerpt policy and changed-input report regeneration. Blocks destructive cleanup/excerpts, not core builds |
| D10 — P4 closure discrepancy | Accept owner live freeze with available records; run missing focused evaluation evidence; reopen P4 implementation without cause (not recommended) | Owner accepts dependencies or requests missing evidence. Do not silently certify historical tests or modify context in this task |
| D11 — Report display metadata source | UUID-only labels/current revision manifest (no new platform read, weaker display metadata); authenticated P5 internal metadata snapshot (correct names/revision, narrow extra Express scope); direct MongoDB or frozen analysis DTO modification (forbidden/unapproved) | Approve the bounded internal metadata read and capture-time semantics under D2; otherwise explicitly accept UUID/unavailable display fields. Blocks named metadata preparation, not canonical diagram/search builders |

Proposed future ADR titles/content, **not created now**: “P5 Derived Delivery and Four-Diagram Report Prerequisites” (D1/D2/D7); “Knowledge Projection, Search Generations and Embedding Capability” (D3/D4); “DiagramSpec, Headless ELK and Presentation Workspaces” (D5); “Deterministic PDF and Generated Artifact Storage” (D6/D9). If D8 is approved, an explicit continuation authorization decision must explain its relationship to ADR-0001 without rewriting that frozen ADR.

### 25.3 Master/implementation/product reconciliation register

1. Sections 13/14 include organization terminology; frozen Section 0's project-primary/organization-deferred rule controls. P5 adds no organization model.
2. Section 17's text-only report fallback versus the owner-required four-diagram automatic prerequisite remains D1, not silently resolved by declaring the master obsolete.
3. Section 17 describes wider report possibilities; implementing one deterministic PDF is a product subset, not a second report engine. Section 25.16's phase summary does not list report delivery explicitly; Section 17 plus this owner brief supplies its architecture/product scope, not new canonical semantics.
4. Section 14's AI/RAG examples are architecture context, not permission to implement P6 natural-language interpretation. Embedding retrieval and answer generation remain separate.
5. A roughly 500-node P5 diagram view is a separate proposed presentation budget, not a change to frozen P4 frontend/query caps.
6. Actual P3 diagnostic/coverage persistence is narrower than a generic “all findings/language statistics” report description; render available facts and explicit unknowns, never invent or reopen F2.

## 26. Unresolved Questions and Owner Approvals

Before approving the implementation baseline, resolve D1/D2 and accept the seven-module ownership/C0–C5 freezes. Confirm D4 initial semantic acceptance and D8 whether one-action preparation is included or deferred; these affect scope rather than hidden implementation details.

Before affected implementation batches: choose D3 exact ES compatibility, D5 helper deployment/isolation, D6 PDF/font/export scope and D7 measured numerical defaults/queue fairness. D9 historical retention/excerpt/regeneration rules gate those capabilities. D10 requires acceptance of dependency evidence, not a redesign of P4. D11 resolves the missing display-metadata interface or explicitly accepts UUID-only/unavailable labels; no new internal endpoint is assumed approved.

No decision here is represented as already approved merely because its recommendation follows the master. A module can implement approved pure contracts/fixtures while another optional branch is blocked, but the whole phase cannot freeze with an unresolved mandatory acceptance capability. Approval must distinguish “plan accepted in direction”, “contract frozen”, “batch authorized” and “verified complete”.

## 27. Acceptance Criteria

1. **Authority:** no P1–P4 contract/semantic change without explicit change control; no cross-DB access or canonical inference in projections; reviewed diff and contract fixtures prove boundaries.
2. **Delivery:** published successful exact version discovered and scheduled durably; duplicate publication/messages/restarts create one idempotent work set; delays measured against owner-approved discovery/admission budgets.
3. **Search:** complete verified candidate before activation; exact scope and generation for all results/cursors; historical readability/freshness correct; relevance fixtures pass; unsupported semantic capability explicit and approved scope met.
4. **Knowledge/evidence:** structured queries and bounded context preserve actual provenance, original statuses and conflicts; scope/Unicode/encoding/secret/budget/ambiguity tests pass; no fabricated facts or hidden omissions.
5. **Four diagrams:** all required templates produce validated exact-version immutable artifacts, including honest limited/empty views; overview-first normal path, independent retries and approved failure policy; no Neo4j/ES prerequisite.
6. **Diagram UX:** bounded readable layout rather than all-horizontal ranks; pan/zoom/focus/filter/groups/export work; selection/camera stable; every shown semantic node/edge references canonical records; omissions visible.
7. **Report:** zero report jobs before all four READY; exactly one for duplicate fourth-ready notifications; same-version overview embedded and four prerequisites pinned; original diagnostics/limitations; no executive summary/comparison; valid private immutable PDF/history/download.
8. **Renderer isolation:** ReportRenderer consumes only prepared spec/assets, cannot perform data queries; helper cannot read repository/credentials or access network; malicious labels/paths rejected safely.
9. **Transport/UI:** all calls through authenticated Express; role/scope/errors/repeated filters/download cancellation preserved; exact version survives routes/history; outputs prominent, operational details retained; loading/empty/error/retry/permission states accessible.
10. **Failure isolation/recovery:** ES/Neo4j/report/candidate failure never invalidates published architecture or good siblings; stale attempts cannot commit; active generations preserved; crash-window/broker/storage recovery verified with real services.
11. **Performance/security:** measured approved limits enforced with correct process memory/deadlines; source extraction performance and parser sandbox unchanged; fairness under derivative load established; no unbounded task/query/render/download.
12. **Regression/acceptance:** actual Python/Express/frontend tests and build/quality checks recorded, missing infrastructure explicit; owner accepts live UX, scope limitations and final evidence before freeze.

## 28. Definition of Done

Each module closes only after its listed batches, contract/consumer review, meaningful focused tests, applicable real integration checks, measured limits and reviewed diff. No “done” status based solely on test counts. Published artifacts must be traceable and recoverable, not merely visible once in a browser.

P5 closes when all four deliverable areas and mandatory acceptance capabilities pass Section 27; exact commands/environment/results and limitations are recorded; no unresolved mandatory owner gate remains; deployment/health/recovery procedures are accepted; frozen dependencies remain unchanged except explicitly approved additive composition; and the owner explicitly accepts the phase.

Subsequent implementation agents may update this document's execution ledger only with verified evidence and approved deviations. Updating the rolling `PROJECT_CONTEXT.md`, creating ADRs and changing code/configuration require the relevant later task authorization; this planning task does none of them.

## 29. Planning Status and Freeze Readiness

| Area | Current verified status |
|---|---|
| Repository/authority inspection | Completed for planning; no runtime compatibility or test result newly claimed |
| All four deliverables and seven module plans | Proposed in this document; ready for owner review |
| Architecture/contract decisions D1–D11 and C0–C5 | Recommendations/gates recorded; not approved/frozen by this task |
| M1–M7, every batch | PLANNED — IMPLEMENTATION NOT STARTED |
| Dependencies/infrastructure/schema/source/tests | Unchanged |
| P5 implementation authorization | NOT GRANTED |
| P5 plan freeze | NOT FROZEN — owner review and named decisions pending |

Next action: owner/Master Agent reviews scope, module boundaries, D1/D2 policy/authorization and initial semantic/preparation scope, then authorizes the appropriate compatibility/contract B1 work. Do not begin implementation merely because this document now contains a complete proposal.
