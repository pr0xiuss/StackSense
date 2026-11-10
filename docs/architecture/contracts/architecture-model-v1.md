# Architecture Model Contract v1

Status: **Frozen with Phase 3 Module 4**  
Schema version: `1.0.0`

This contract defines the immutable, canonical Architecture Model produced by
M4 from a validated F3 `IRDocument`. M4 never invokes M2 or M3. M1 owns pipeline
orchestration and recovery; M4 owns identity resolution, model construction,
validation, PostgreSQL persistence, publication, and published-result queries.

## Input and handoffs

- `identity_resolution` consumes the attempt's immutable F3 result and produces
  an immutable `ResolvedArchitectureInput`.
- `architecture_build` consumes the same F3 plus that resolved result.
- If either non-persisted handoff is lost, the M1-owned attempt store replays the
  producer with identical AnalysisInput, configuration, analyzer and schema
  versions. Replay does not reopen completed stages or emit new public events.
- M4 output is one immutable `ArchitectureDocument` identified by a stable UUID
  derived from the Analysis identity.

## Canonical model

The supported entity, relationship, evidence, uncertainty, conflict and
completeness vocabularies are the enums and immutable records in
`backend.platform.analysis.architecture.model`. Canonical logical IDs use the
specified project/repository-scoped NFC/UTF-8 encoding rules and are distinct
from PostgreSQL resource UUIDs. Static relationships never claim runtime
observation. Manifest dependencies remain distinct from source references.

Every promoted entity and relationship is evidence-backed. Competing evidence,
unresolved targets, partiality and conflicts are preserved. Literal secrets,
raw source and host paths are prohibited from public payloads.

## Validation and capacity

The whole candidate is validated before publication for schema compatibility,
identity uniqueness, referential integrity, semantic direction, provenance,
safe metadata, deterministic digest reproduction and capacity. Production caps
are 25,000 entities, 50,000 relationships, 75,000 evidence records, 10,000
unresolved relationships, 5,000 conflicts and a 128 MiB canonical payload.
Exceeding a cap fails closed: no truncation, evidence loss or partial publish.

## Lifecycle and publication

An internal header progresses `BUILDING -> VALIDATING -> PUBLISHED` or
`VALIDATION_FAILED`. Validation diagnostics are committed independently before
the failure header is finalized. Publication inserts all canonical child rows,
verifies counts/references/digest, marks the version `PUBLISHED`, and links
`Analysis.published_version_id` in one PostgreSQL transaction. Any error rolls
back all of those changes. Draft and failed versions are never public.

Analysis completion requires the durable published-version pointer. Projection
is outside synchronous M4 execution; legacy pending projection rows are skipped
after publication with the existing `projection_deferred` reason.

## Query boundary

The M4 result API returns published versions only. Every route requires the
existing trusted service credential, delegated actor context and an exact
project-scope match. Collections use deterministic logical-ID ordering with
bounded `limit`/`offset`. Resource URLs use stable persistence UUIDs while DTOs
may include canonical logical IDs. Cross-project records, drafts, raw source,
credentials and internal failure payloads are not exposed.

Changes to this contract require explicit owner approval and schema-version
change control. F1, F2 and F3 remain unchanged.
