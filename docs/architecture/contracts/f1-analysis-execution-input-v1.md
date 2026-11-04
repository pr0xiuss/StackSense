# F1 — Analysis Execution and Input Contract v1.0.0

Status: **FROZEN**  
Owner: Phase 3 Module 1  
Consumer: Phase 3 Module 2  
Frozen: 2026-11-04

## Scope

F1 freezes the M1-to-M2 execution boundary. It does not assign parsing,
intermediate representation, identity resolution, Architecture Model persistence,
publication, or result-query ownership to M1.

## Immutable input

`AnalysisInput` is a frozen dataclass containing the analysis, project,
repository, and immutable snapshot UUIDs; revision identifier and source hash;
verified file/byte totals; effective configuration; deterministic
`ArtifactCatalog`; lazy bounded `ArtifactContentReader`; and analyzer, IR, and
Architecture schema versions. `AnalysisArtifact` contains only artifact UUID,
revision UUID, normalized relative path, size, content hash, category, and support
level. Storage keys, absolute paths, credentials, and source bytes are excluded.

The production factory obtains the manifest and content only through the
authenticated Express internal API defined by ADR-0001. It verifies the complete
project/repository/revision/artifact ownership chain, safe paths, counts, and
sizes. Reads are lazy and bounded to 50 MiB per call. The catalog is ordered by
normalized relative path.

## Execution lifecycle

Analysis states and transitions implement `master.txt` Section 9 exactly:

- `CREATED -> QUEUED | FAILED`
- `QUEUED -> RUNNING | CANCELLED`
- `RUNNING -> COMPLETED | PARTIAL | CANCEL_REQUESTED | TIMEOUT | FAILED`
- `CANCEL_REQUESTED -> CANCELLED`
- `TIMEOUT -> FAILED`
- `PARTIAL -> COMPLETED_WITH_WARNINGS | FAILED`

Only `COMPLETED`, `COMPLETED_WITH_WARNINGS`, `FAILED`, and `CANCELLED` are
terminal. `PARTIAL` and `TIMEOUT` are explicit nonterminal states and cannot be
silently collapsed or treated as successful results.

Job states are `PENDING`, `QUEUED`, `RUNNING`, `RETRYING`, `COMPLETED`, `FAILED`,
and `CANCELLED`. Stage states are `PENDING`, `QUEUED`, `RUNNING`, `COMPLETED`,
`FAILED`, `SKIPPED`, and `CANCELLED`. Domain transitions are optimistic and
terminal states are immutable.

Queue payload v1.0.0 is identifier-only: `analysis_id`, `job_id`, `project_id`,
`task_type`, `contract_version`, and `correlation_id`. Workers reload durable
state. Delivery is at-least-once; conditional acquisition and version checks
provide duplicate-delivery safety.

## Shared diagnostic contract

M1 owns the single immutable `AnalysisDiagnostic` contract and durable recording.
M2–M4 emit this type; they must not introduce competing finding or diagnostic
domain contracts. It contains analysis/job/stage identifiers, code, category,
severity, scope, safe message/details, retryability, optional artifact-relative
source location, and timestamp. Recording is bounded. M4 owns finding projections
and result-query APIs.

## Change control

Any incompatible change requires a new contract version, updated producer and
consumer fixtures, migration impact, and owner approval. M2 must not reinterpret
this contract or access M1 repositories directly.
