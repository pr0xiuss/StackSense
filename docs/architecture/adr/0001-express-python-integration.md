# ADR-0001 — Express/Python Platform and Analysis Integration

Status: **Accepted**  
Decision date: 2026-11-04

## Context

StackSense deliberately has two independently owned backends and databases.
Express/MongoDB is the user-facing platform authority. Python/FastAPI/PostgreSQL
is the analysis authority. UUID compatibility is not permission for either service
to read the other service's database.

## Decision

Express owns users, authentication, projects, memberships/RBAC, repository
registration, immutable revisions, artifact metadata, and artifact storage access.
Python owns Analysis, Jobs, JobAttempts, stages, events, diagnostics, orchestration,
and later Python-only analysis/model responsibilities. PostgreSQL is intentional,
authoritative M1 infrastructure—not temporary compatibility storage.

Neither backend directly accesses the other's database. Cross-service references
are opaque UUIDs stored without cross-database foreign keys.

### Express to Python

Express authenticates the user and enforces project RBAC, then calls Python's
internal `/api/v1/analyses` lifecycle routes with:

- `X-Service-Token`
- `X-Actor-Id`
- `X-Actor-Role`
- `X-Project-Id`
- optional `X-Correlation-Id`

Python compares the service secret in constant time, validates UUIDs and the
approved role vocabulary, requires exact delegated/request project equality, and
still scopes every PostgreSQL query by project. Owner/Admin/Developer may create
or cancel; Viewer is read-only. Browsers never call this boundary directly.

### Python to Express

Python uses a separate `PLATFORM_API_SECRET_KEY`/`X-Service-Token` credential and
the Express internal routes:

- `GET /api/v1/internal/projects/{project}/repositories/{repository}/revisions/{revision}/manifest`
- `GET /api/v1/internal/projects/{project}/repositories/{repository}/revisions/{revision}/artifacts/{artifact}/content?max_bytes=N`

Express verifies the complete ownership chain in MongoDB. Manifests expose only
immutable revision and artifact contract fields; storage keys are removed. Content
responses are bounded to 50 MiB. Python validates the returned chain, safe relative
paths, and manifest totals before constructing immutable `AnalysisInput`.

### Reliability and security

Analysis creation commits PostgreSQL lifecycle state before RabbitMQ publication.
Undispatched/stale jobs are recovered from PostgreSQL; delivery is at-least-once.
Queue messages contain identifiers only. REST is authoritative; SSE is a durable
event notification/replay view and is relayed by Express when frontend integration
is implemented. Errors retain the structured `{error:{code,message,details}}`
shape and never return credentials, storage keys, raw tracebacks, or unrestricted
source. Production secrets must differ from development defaults and be supplied
by deployment secret management; TLS, network allow-listing, and rotation are
deployment requirements.

## Consequences

- M1 PostgreSQL tables keep Express UUID references as indexed values, not foreign
  keys to legacy Python Phase 2 tables.
- The retained Python Phase 2 implementation remains historical/reference code,
  but production M1 composition does not read its project/revision/artifact tables.
- Platform API unavailability is an explicit bounded input/infrastructure failure;
  no database fallback or synchronization mechanism is permitted.
- M5/M6 may add Express lifecycle proxy/SSE relay endpoints, but cannot move
  analysis persistence to MongoDB or expose Python service credentials.
