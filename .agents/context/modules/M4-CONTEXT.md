# Module Context: M4 — Repository Acquisition & Ingestion

> This file is an operational context artifact for the StackSense agent workflow.
> It does **not** replace or override `master.txt`.
> `master.txt` remains the sole architectural source of truth.

## Authority Order

1. System / Developer instructions
2. Current authoritative `master.txt`
3. Explicitly approved architectural decisions
4. This module context
5. Existing implementation

If this file conflicts with the current `master.txt`, treat `master.txt` as authoritative. Do not silently reconcile or modify the architecture.

## Module Role

M4 owns repository acquisition and ingestion after repository registration.

The primary boundary is:

`Repository → Validation → Safe Storage → File Discovery → Analysis Input`

## Critical Responsibilities

M4 owns concerns such as:

- repository acquisition
- connection or upload handling
- ingestion
- validation
- snapshots
- revisions
- artifact inventory
- file discovery
- safe repository storage
- resource limits
- ingestion lifecycle
- ingestion status
- repository-content safety

## Critical Boundary

Repository contents are untrusted input.

M4 must enforce the repository acquisition and storage boundary defined by `master.txt`.

No arbitrary repository code may be executed as part of acquisition or ingestion.

## Analysis Boundary

M4 prepares safe analysis input.

M4 does **not** own:

- parsing
- intermediate representation construction
- identity analysis
- architecture interpretation
- knowledge graph construction
- retrieval/RAG
- AI explanation

Those concerns belong to downstream analysis and knowledge/AI modules.

## Upstream Dependency

M4 consumes the Repository capability established by M3.

M3 owns repository registration and management; M4 owns acquisition and ingestion.

Do not collapse these responsibilities into one module.

## Implementation Rule

This context provides implementation guidance only.

It does not authorize architectural expansion or changes to `master.txt`.


**Location:** `.agents/context/modules/M4-CONTEXT.md`

**Status:** FROZEN FOR IMPLEMENTATION  
**Phase:** P2 — Project & Repository Platform  
**Module:** M4 — Repository Ingestion, Validation & Storage  
**Upstream:** M1 Foundation → M2 Project Access → M3 Repository Platform  
**Downstream:** M5 Identity & Authentication, M6 API & Frontend Product Flow, M7 Integration & P2 Freeze

---

# 1. Purpose

M4 establishes the controlled pipeline for taking a registered StackSense Repository and safely preparing its source material for later analysis.

The core responsibility is:

```text
Registered Repository
        │
        ▼
Acquisition / Input
        │
        ▼
Validation
        │
        ▼
Safe Storage
        │
        ▼
Revision / Source Artifacts
        │
        ▼
Ready for Analysis
```

M4 is a **repository ingestion and preparation module**.

It is not the analysis engine.

It does not interpret architecture, build the IR, resolve symbols, construct the Architecture Model, build the knowledge graph, perform RAG, or invoke AI.

---

# 2. Architectural Authority

The ultimate architectural authority is:

```text
master.txt
```

This context document exists to provide implementation-specific guidance for the M4 developer.

It does not replace or supersede `master.txt`.

If this document conflicts with `master.txt`:

```text
1. Stop the conflicting implementation.
2. Verify the authoritative architecture.
3. Identify the conflict.
4. Resolve it explicitly.
5. Do not silently alter the architecture.
```

M4 must not use implementation convenience as justification for architectural changes.

---

# 3. Required Upstream Context

Before implementing M4, the developer must understand:

```text
.agents/context/shared/M1-M2-CONTEXT.md
.agents/context/modules/M3-CONTEXT.md
```

M3 is the immediate upstream module.

M4 consumes the Repository contract established by M3.

M4 must not recreate M3 concepts simply because M4 needs to interact with them.

---

# 4. P2 Module Map

The P2 module boundary is:

```text
M1
Project Domain Foundation
        │
        ▼
M2
Project Access & Resource Boundary
        │
        ▼
M3
Repository Domain & Registration
        │
        ▼
M4
Repository Ingestion, Validation & Storage
        │
        ├──────────────► M6 API / Frontend
        │
        └──────────────► M7 Integration
```

M5 provides the real identity/authentication implementation around the existing identity seam.

M4 must remain independently understandable and must integrate through stable contracts.

---

# 5. M4 Mission

M4 must make it possible for StackSense to safely accept repository source material and establish a controlled, persistent representation of that source.

M4 owns the lifecycle between:

```text
Repository registered
```

and:

```text
Repository source prepared for analysis
```

The module must provide the infrastructure and application contracts necessary for:

```text
repository acquisition
repository ingestion
repository validation
repository snapshot/revision handling
source artifact inventory
safe source storage
resource-limit enforcement
ingestion lifecycle management
ingestion failure handling
```

Only responsibilities actually required by the authoritative architecture should be implemented.

---

# 6. M4 Core Boundary

The fundamental boundary is:

```text
M3
Repository Resource
    │
    │ Repository ID / Project relationship
    ▼
M4
Acquisition
    │
    ▼
Validation
    │
    ▼
Snapshot / Revision
    │
    ▼
Artifact Inventory
    │
    ▼
Safe Storage
    │
    ▼
Analysis Input
```

M4 prepares source material.

Later modules consume the resulting controlled artifacts.

---

# 7. What M4 Owns

M4 owns repository-content preparation concerns including:

```text
Repository acquisition
Repository ingestion
Repository input validation
Repository source safety checks
Repository snapshot handling
Repository revision handling
Repository artifact inventory
Repository source storage
Ingestion resource limits
Ingestion lifecycle
Ingestion failure classification
Ingestion application contracts
Ingestion persistence
Ingestion infrastructure
Ingestion tests
```

The exact implementation must follow the contracts established by `master.txt` and M3.

---

# 8. What M4 Does Not Own

M4 must not implement:

```text
Language detection as analysis
Framework detection as analysis
AST parsing
Tree-sitter analysis
Language-specific parsing
Symbol extraction
Import resolution
Inheritance resolution
Dependency resolution
Relationship extraction
Architecture construction
Request-flow construction
Dependency graph interpretation
Architecture Model construction
Knowledge graph construction
RAG
Search ranking
AI reasoning
LLM interaction
Diagram generation
Report generation
Frontend implementation
Project authorization policy
Authentication
User management
```

M4 may perform only the minimum file/content classification required for safe ingestion and validation.

---

# 9. Ingestion Is Not Analysis

This distinction is non-negotiable.

M4:

```text
source preparation
```

Later analysis phases:

```text
source understanding
```

Therefore:

```text
Upload / Acquire
        ↓
Validate
        ↓
Store
        ↓
Create Revision / Artifacts
        ↓
READY FOR ANALYSIS
```

is valid.

Whereas:

```text
Upload
   ↓
Parse source
   ↓
Resolve symbols
   ↓
Build architecture
```

is outside M4.

---

# 10. Repository vs Revision vs Artifact

M4 must preserve the distinction between:

```text
Repository
Repository Revision
Source Artifact
Ingestion Operation
Analysis Job
```

Conceptually:

```text
Repository
    │
    ├── Revision
    │      │
    │      └── Artifacts
    │
    └── Revision
           │
           └── Artifacts
```

A Repository represents the logical project source container.

A Revision represents a particular captured version/state of that source.

An Artifact represents an individual stored/discovered source item or other ingestion output defined by the architecture.

An ingestion operation represents the process of acquiring and preparing the source.

An Analysis Job belongs to later analysis responsibilities.

Do not collapse these concepts into one model.

---

# 11. M3 Boundary

M3 owns:

```text
Repository identity
Repository registration
Repository-to-Project relationship
Repository lifecycle at the resource level
Repository metadata owned by M3
Repository persistence contract
Repository application service
Repository API
```

M4 consumes that Repository.

M4 must not redefine:

```text
Repository
Repository ID
Repository ownership
Project authorization
Repository-level RBAC
```

---

# 12. M4 Must Not Create a Second Repository Model

Do not introduce:

```text
M4Repository
IngestionRepository
RepositorySource
RepositoryResource
RepositoryStorageEntity
```

as a second representation of the M3 Repository merely because M4 needs repository data.

If M4 needs information that M3 does not expose, identify the contract gap.

Do not silently create a parallel abstraction.

---

# 13. M4 and Repository Identity

M4 must reference the Repository established by M3.

The conceptual dependency is:

```text
Repository ID
      │
      ▼
M4 ingestion
      │
      ▼
Revision / artifacts
```

M4-owned records may reference the Repository.

M4 must not generate a competing Repository identifier.

---

# 14. Project Relationship

Every Repository is associated with a Project through M3.

M4 inherits that ownership boundary.

Conceptually:

```text
Current User
      │
      ▼
Repository
      │
      ▼
project_id
      │
      ▼
ProjectAuthorization
      │
      ▼
ProjectAccess
```

M4 operations must remain Project-scoped.

---

# 15. Authorization

M4 must use the established M2 authorization mechanism.

The authorization chain is:

```text
Current User
      │
      ▼
Repository
      │
      ▼
Repository.project_id
      │
      ▼
ProjectAuthorization
      │
      ▼
ProjectAccess
      │
      ▼
ProjectRole
      │
      ▼
Required capability
```

Do not create:

```text
IngestionRole
RepositoryRole
IngestionAccess
RepositoryPermission
```

as a separate authorization system.

---

# 16. Ingestion Permissions

The exact operation-to-capability mapping must follow the established Project role matrix and M3 contract.

At the Project level:

```text
OWNER       → full Project resource permissions
ADMIN       → full Project resource permissions
DEVELOPER   → create/update/read, no delete
VIEWER      → read only
```

M4 must reuse `ProjectAuthorization` rather than reproducing this matrix.

---

# 17. No Authorization Bypass for Background Work

If ingestion is eventually executed asynchronously, the worker must not bypass authorization simply because it runs outside the HTTP request.

The initiating application operation must establish that:

```text
requesting user
    +
repository
    +
project
```

are authorized.

The resulting job/work item must retain enough trusted context to ensure the operation cannot be redirected to an unauthorized Repository.

Workers must never trust arbitrary client-supplied identifiers without validating the persisted ownership relationship.

---

# 18. Repository Acquisition

M4 owns acquisition from supported source types defined by the architecture.

The architecture identifies source categories including:

```text
Git repositories
GitHub
GitLab
Bitbucket
Self-hosted Git
Local ZIP/upload
```

The exact supported providers and acquisition mechanisms must follow the frozen technology and product requirements.

Do not add a provider merely because its implementation is convenient.

---

# 19. Acquisition Abstraction

Different source mechanisms should be isolated behind appropriate application/infrastructure contracts where multiple acquisition strategies genuinely exist.

Conceptually:

```text
Ingestion Service
       │
       ▼
Acquisition Contract
       │
       ├── Git provider implementation
       ├── archive/upload implementation
       └── other approved source implementation
```

The exact abstraction should be determined by actual variation.

Do not create a large provider framework if only one concrete strategy is currently required.

---

# 20. Acquisition Is Untrusted

All acquired repository content must be treated as untrusted.

This applies regardless of source:

```text
GitHub
GitLab
Bitbucket
self-hosted Git
ZIP
local upload
future providers
```

The fact that content comes from a known provider does not make the repository source executable or trusted.

---

# 21. No Arbitrary Code Execution

M4 must never execute repository code during ingestion.

Forbidden examples include:

```text
executing shell scripts
running repository build commands
executing package lifecycle scripts
importing arbitrary Python modules
running JavaScript/Node scripts
executing Makefiles
running project tests
executing setup scripts
executing configuration files
```

M4 is an ingestion system, not a build system.

---

# 22. Safe Archive Handling

If archive uploads are supported, archive contents must be treated as untrusted.

Validation must protect against issues such as:

```text
path traversal
absolute paths
unexpected extraction targets
resource exhaustion
oversized files
oversized archives
excessive file counts
unsafe archive structures
```

Extraction must remain within the controlled storage boundary.

Never allow archive entries to escape the intended repository storage root.

---

# 23. Path Safety

Repository paths are untrusted input.

M4 must prevent:

```text
../
absolute paths
path traversal
unexpected filesystem references
symlink escapes where applicable
```

The implementation must normalize and validate paths before using them for storage.

A path supplied by a repository must never be able to choose an arbitrary host filesystem destination.

---

# 24. Resource Limits

M4 must enforce resource limits appropriate to repository ingestion.

Relevant dimensions include:

```text
maximum repository size
maximum archive size
maximum individual file size
maximum file count
maximum extraction size
maximum path length
maximum ingestion workload
```

Exact limits must come from the authoritative resource-limit configuration.

Do not invent arbitrary production limits without checking the architecture/configuration.

---

# 25. Resource Exhaustion

M4 must defend against resource exhaustion.

Potential attack patterns include:

```text
huge repository
huge archive
many tiny files
deep directory structures
repeated ingestion
compressed archive expansion
unexpectedly large individual files
```

Validation should occur as early as safely possible.

Do not fully materialize content before checking limits when doing so could itself violate the resource constraints.

---

# 26. Storage Boundary

M4 must use a controlled storage abstraction.

Conceptually:

```text
Ingestion Application Service
            │
            ▼
     Storage Contract
            │
            ▼
Filesystem / Object Storage
```

The ingestion service should not scatter raw filesystem manipulation throughout application code.

Storage implementation belongs to infrastructure.

---

# 27. Database vs Source Storage

The operational database and source storage have different responsibilities.

Conceptually:

```text
PostgreSQL
    │
    ├── repository references
    ├── revision metadata
    ├── artifact metadata
    ├── lifecycle state
    └── ingestion state

Controlled Storage
    │
    ├── repository snapshots
    ├── source files
    └── stored artifacts
```

Do not place complete repository source contents into ordinary relational metadata tables.

Do not treat the database as a general-purpose source archive.

---

# 28. Storage Technology

The storage implementation must follow the architecture's approved infrastructure.

The high-level architecture identifies object storage concepts such as:

```text
S3
MinIO
GCS
```

The exact runtime implementation must follow the frozen technology stack and existing infrastructure configuration.

Do not introduce a new storage platform simply because it is familiar.

---

# 29. Storage Key Design

Stored source material must have deterministic, controlled storage identifiers.

Storage keys must not be derived by blindly concatenating untrusted repository paths into host filesystem paths.

A safe conceptual structure is:

```text
project/repository/revision/artifact
```

with the actual implementation determined by the storage contract.

Storage identifiers should be:

```text
deterministic
collision-resistant
isolated
non-ambiguous
safe
```

---

# 30. Project Isolation in Storage

Stored source data must preserve Project isolation.

Conceptually:

```text
Project A
   └── Repository A
         └── Revision A
               └── Artifacts

Project B
   └── Repository B
         └── Revision B
               └── Artifacts
```

M4 must never allow a Repository A ingestion operation to write into Repository B's storage namespace.

Storage paths/keys must not rely solely on client-supplied names.

---

# 31. Revision

A Repository Revision represents a captured version of Repository source.

A revision should provide enough identity and metadata to distinguish one captured repository state from another.

Possible revision identity information may include source-specific metadata such as:

```text
commit/reference information
capture identifier
source revision identifier
timestamps
```

The exact fields must follow the authoritative architecture.

Do not invent Git-specific fields for all sources if the source type does not provide them.

---

# 32. Revision Must Be Immutable

Once a revision represents a captured repository state, its source contents should be treated as immutable.

Conceptually:

```text
Revision A
    ↓
stored artifacts
    ↓
immutable snapshot
```

A new repository state should produce a new revision rather than silently overwriting the old revision.

This supports later:

```text
versioning
comparison
reproducibility
analysis history
```

---

# 33. Revision vs Current Repository State

Do not treat:

```text
Repository
```

and:

```text
Revision
```

as interchangeable.

Repository:

```text
logical source container
```

Revision:

```text
specific captured state
```

This distinction is important for future analysis reproducibility.

---

# 34. Artifact Inventory

M4 owns discovery and inventory of source artifacts.

The inventory should establish what has been ingested without interpreting architectural meaning.

Conceptually:

```text
Revision
    │
    ├── Artifact
    ├── Artifact
    ├── Artifact
    └── Artifact
```

An artifact may contain metadata such as:

```text
relative path
size
storage reference
content type / classification where required
hash where required
revision relationship
```

Exact fields must follow the architecture.

---

# 35. Artifact Inventory Is Not IR

An artifact inventory answers:

```text
What source material was ingested?
```

The Intermediate Representation answers:

```text
What program entities and relationships were extracted from that source?
```

Therefore:

```text
M4 Artifact
    ≠
IR Entity
```

M4 must not create IR objects while discovering files.

---

# 36. File Classification

M4 may classify files enough to determine:

```text
allowed
ignored
unsupported
unsafe
stored
```

This is ingestion classification.

It must not perform semantic language/framework analysis.

For example:

```text
".py is an allowed source artifact"
```

may be an ingestion decision.

But:

```text
"this Python file contains a FastAPI controller"
```

belongs to later analysis.

---

# 37. Ignore Rules

Repository ingestion must respect the architecture's ignore rules.

Ignore rules may identify content that should not be ingested or should be excluded from analysis input.

The implementation must define precedence between:

```text
global ignore rules
repository-specific ignore rules
security exclusions
resource limits
supported-file rules
```

according to the authoritative architecture.

Do not silently invent a different ignore precedence.

---

# 38. Ignored Files vs Rejected Files

M4 should distinguish:

```text
ignored
```

from:

```text
rejected
```

Conceptually:

```text
Ignored
→ valid repository content that is intentionally excluded

Rejected
→ input that violates an ingestion/validation requirement
```

Examples:

```text
node_modules/
.git/
generated cache
```

may be ignored according to rules.

A path traversal attempt should not merely be "ignored"; it is a security validation failure.

---

# 39. Supported Extensions

M4 may maintain supported-file rules where required.

However:

```text
supported extension
```

does not mean:

```text
supported for analysis
```

M4 only determines what may safely become ingestion input.

Language/framework detection belongs to the later analysis pipeline unless explicitly required for ingestion validation.

---

# 40. Hidden and Generated Files

M4 should follow the architecture's repository scanning and ignore rules rather than assuming:

```text
all files = source
```

Generated artifacts, dependency directories, caches, binaries, VCS internals, and other excluded content should be handled according to the defined ingestion policy.

Do not create arbitrary exclusions merely because they are common elsewhere.

---

# 41. Ingestion Lifecycle

M4 must model ingestion as a controlled lifecycle.

The lifecycle should make it possible to distinguish states such as:

```text
not started
in progress
validation
storage
ready
failed
```

However, the exact lifecycle vocabulary must be taken from the authoritative architecture.

Do not add or rename lifecycle states without verifying the established contract.

---

# 42. State Transitions

Lifecycle transitions must be explicit.

Conceptually:

```text
Current State
      +
Requested Transition
      │
      ▼
Transition Rule
      │
      ├── valid → persist new state
      └── invalid → typed application error
```

Do not allow arbitrary state mutation from API input.

---

# 43. Failure State

A failed ingestion must retain enough state to explain that ingestion did not complete.

A failure should distinguish, where required:

```text
validation failure
acquisition failure
storage failure
resource-limit failure
security failure
unexpected infrastructure failure
```

The exact failure classification should follow the project's established error/failure model.

---

# 44. Partial Ingestion

M4 must account for partial work.

For example:

```text
source acquired
    ↓
some artifacts stored
    ↓
validation/storage failure
```

The system must not incorrectly mark the Repository as fully ready.

The architecture must define whether partial artifacts are:

```text
removed
retained as a failed revision
marked incomplete
quarantined
```

The implementation must follow that contract.

Do not invent cleanup semantics casually.

---

# 45. Database Transaction vs External Storage

This distinction is critical.

PostgreSQL transactions can roll back:

```text
database rows
```

They cannot automatically roll back:

```text
object storage writes
filesystem writes
remote repository operations
```

Therefore M4 must explicitly handle consistency between:

```text
database state
```

and:

```text
external source storage
```

Do not claim atomicity across both unless the infrastructure actually provides it.

---

# 46. Failure Recovery

If M4 performs multi-step ingestion:

```text
Acquire
→ Validate
→ Store
→ Persist metadata
→ Mark ready
```

each step must have a clear failure behavior.

The implementation should prevent states such as:

```text
Repository = READY
```

when required artifacts were never successfully stored.

---

# 47. Idempotency

Repeated ingestion requests must have defined semantics.

M4 should avoid accidental duplication when the same source revision is ingested repeatedly.

Possible approaches include:

```text
revision identity
content hash
source revision identifier
ingestion request identity
```

The exact mechanism must follow the architecture.

Do not invent an idempotency model that conflicts with revision semantics.

---

# 48. Duplicate Ingestion

The implementation must explicitly define what happens when:

```text
same Repository
+
same source revision
+
multiple ingestion attempts
```

occurs.

The desired behavior may be:

```text
reuse existing revision
reject duplicate
create a new capture
return existing result
```

The choice must follow the authoritative contract.

Do not rely on accidental database uniqueness.

---

# 49. Acquisition Credentials

If private repositories are supported, acquisition may require credentials.

Credentials must be treated as secrets.

Never:

```text
store credentials in source artifacts
log credentials
return credentials in DTOs
place credentials in repository metadata
include tokens in error messages
```

Secrets should use the approved secret-management mechanism.

M4 should receive only the minimum credential material required for acquisition.

---

# 50. External Provider Boundary

Provider-specific acquisition logic should remain isolated.

Conceptually:

```text
M4 Application
      │
      ▼
Acquisition Contract
      │
      ├── GitHub adapter
      ├── GitLab adapter
      ├── Bitbucket adapter
      └── local/archive adapter
```

Provider SDKs should not leak into domain models.

The domain should not know provider-specific SDK classes.

---

# 51. Local Upload Boundary

If local ZIP upload is supported:

```text
Browser
   ↓
API
   ↓
M4 ingestion
   ↓
safe validation
   ↓
controlled extraction
   ↓
storage
```

The frontend must not directly write source files into server storage.

The browser is not a trusted storage layer.

---

# 52. Remote Git Boundary

For remote Git acquisition:

```text
M4
   ↓
provider/acquisition adapter
   ↓
controlled temporary location
   ↓
validation
   ↓
revision
   ↓
safe storage
```

The implementation must not execute repository hooks or project scripts during acquisition.

---

# 53. Temporary Storage

If acquisition requires temporary filesystem space, the temporary location must be:

```text
controlled
isolated
resource-limited
cleaned up
```

Temporary files must not become the authoritative Repository storage location.

Cleanup must be handled on:

```text
success
validation failure
storage failure
unexpected failure
```

where appropriate.

---

# 54. Symlink Handling

Repository contents may contain symbolic links or link-like filesystem structures.

M4 must not allow links to escape the controlled ingestion/storage boundary.

The exact supported behavior must follow the security contract.

If symlinks are rejected, they should produce an explicit validation result rather than silently creating a security boundary violation.

---

# 55. Repository Content Must Remain Passive

The ingestion pipeline should treat source as data.

The following are passive inputs:

```text
Python
Java
JavaScript
TypeScript
Go
configuration
documentation
SQL
other supported artifacts
```

They are never executed merely because they are present.

---

# 56. No Language Parser in M4

M4 must not import or invoke:

```text
tree-sitter
language-specific parsers
AST analyzers
symbol extractors
```

for the purpose of understanding source architecture.

Those responsibilities belong to the analysis engine.

---

# 57. No Framework Detection in M4

M4 should not determine architectural framework semantics.

For example:

```text
FastAPI controller
Django view
NestJS controller
Spring service
```

are analysis concepts.

M4 may store source files that later analysis can inspect.

It does not need to understand what those files mean.

---

# 58. No Architecture Model in M4

M4 must not create:

```text
Structure
Relationships
Dependencies
Flows
Metadata
Constraints
Evidence
```

as Architecture Model semantics.

Those are downstream analysis concepts.

M4's metadata is ingestion metadata.

---

# 59. No Knowledge Graph in M4

M4 must not create graph relationships such as:

```text
CALLS
IMPORTS
IMPLEMENTS
DEPENDS_ON
USES
```

unless such information is merely represented as raw ingestion metadata rather than interpreted relationships.

Architectural relationships belong to later analysis/knowledge stages.

---

# 60. No AI in M4

M4 must not invoke an LLM to:

```text
validate source
classify architecture
detect language semantics
summarize repository
generate metadata
```

M4 must remain deterministic and evidence-preserving.

---

# 61. Deterministic Ingestion

Given the same valid source and same ingestion configuration, ingestion behavior should be deterministic wherever practical.

This includes:

```text
path normalization
ignore handling
artifact discovery
metadata generation
hashing
revision identification
storage key construction
```

Nondeterminism must not be introduced without a concrete reason.

---

# 62. Evidence Preservation

M4 should preserve enough information for downstream analysis to know:

```text
where the artifact came from
which Repository it belongs to
which Revision it belongs to
where it is stored
what its path was
what ingestion rules applied
```

Later analysis must be able to trace extracted information back to source artifacts.

---

# 63. Reproducibility

A Repository Revision should provide a reproducible analysis input.

Conceptually:

```text
Revision
    │
    ├── source artifact A
    ├── source artifact B
    ├── source artifact C
    └── ...
```

Later analysis should be able to identify exactly which source revision produced an analysis result.

M4 must preserve the identity required for this.

---

# 64. Content Hashing

If content hashing is part of the authoritative ingestion contract, M4 may compute hashes for:

```text
artifact content
revision content
stored object
```

Hashing should be deterministic.

Do not invent hash semantics merely for convenience.

If hashes are used for integrity, they must be documented and tested.

---

# 65. Artifact Metadata

Artifact metadata should remain ingestion-focused.

Appropriate categories may include:

```text
artifact ID
revision ID
relative path
size
storage reference
content hash where required
classification
timestamps
```

Do not add semantic fields such as:

```text
class_count
controller_count
dependency_count
architecture_role
```

Those belong to analysis.

---

# 66. Application Contracts

M4 should expose clear application-level contracts for operations such as:

```text
ingest repository
validate source
create revision
list revisions
retrieve revision
list artifacts
retrieve artifact metadata
```

Only create contracts for actual use cases.

Do not expose internal storage operations as application APIs.

---

# 67. Storage Contract

A storage abstraction may provide operations conceptually similar to:

```text
store(...)
retrieve(...)
exists(...)
delete(...)
```

The exact contract should be based on actual M4 use cases.

Avoid exposing raw filesystem paths to application services if a storage reference abstraction can provide safer isolation.

---

# 68. Acquisition Contract

An acquisition abstraction may represent operations such as:

```text
acquire(source)
```

returning a controlled acquisition result.

The result should not expose arbitrary infrastructure internals.

The application layer should not know whether acquisition used:

```text
Git CLI
provider SDK
HTTP archive
local ZIP
```

unless that distinction is explicitly part of the application contract.

---

# 69. Validation Contract

Validation should be composable where multiple independent validation rules exist.

Potential validation categories:

```text
path safety
size limits
file count
supported artifact rules
archive safety
repository structure
storage constraints
```

A strategy/chain-style abstraction is justified only if the actual validation rules are sufficiently independent and variable.

Do not create a validation framework for a handful of static checks if simple cohesive code is clearer.

---

# 70. Domain vs Application vs Infrastructure

A reasonable M4 separation is:

```text
Domain
    ingestion/revision/artifact state and intrinsic rules

Application
    ingestion orchestration
    authorization
    transaction coordination
    contracts

Repositories
    persistence interfaces

Infrastructure
    SQLAlchemy persistence
    source acquisition adapters
    filesystem/object storage
    provider integrations
```

The exact package layout must follow the existing StackSense structure.

Do not mechanically create every layer.

---

# 71. Domain Independence

M4 domain code must not depend directly on:

```text
FastAPI
SQLAlchemy
GitHub SDK
GitLab SDK
filesystem implementation
S3 client
MinIO client
Redis
Celery
```

Use application/infrastructure contracts where dependency inversion is needed.

---

# 72. Background Processing

The high-level architecture includes:

```text
Job Orchestrator
Task Queue
Scan Job
Parse Job
IR Job
Build Architecture Job
Build Graph Job
Index Job
Embedding Job
Report Job
```

M4 should not implement the complete analysis job pipeline.

If M4 requires asynchronous ingestion, it may expose an ingestion job boundary, but it must remain limited to M4 ingestion responsibilities.

The broader orchestration system belongs to the appropriate later module.

---

# 73. M4 and Queue Integration

If M4 uses a task queue:

```text
API/Application
      ↓
enqueue ingestion work
      ↓
worker
      ↓
M4 ingestion service
```

The worker should invoke the same application/domain logic rather than creating a second implementation of ingestion.

The queue is an execution mechanism, not a second business layer.

---

# 74. Job State vs Repository State

Do not confuse:

```text
ingestion job state
```

with:

```text
Repository lifecycle state
```

A job may be:

```text
queued
running
failed
completed
```

while the Repository itself has a separate lifecycle.

These are different concepts.

If both are required, model them separately.

---

# 75. Idempotent Worker Behavior

If a worker retries an ingestion job, the ingestion operation must not corrupt Repository state.

Retry behavior should account for:

```text
partial storage
existing revision
duplicate artifacts
existing metadata
```

Retries must either:

```text
resume safely
restart safely
or fail deterministically
```

according to the established ingestion contract.

---

# 76. Observability

M4 should provide useful structured observability for ingestion.

Relevant events may include:

```text
ingestion requested
acquisition started
acquisition completed
validation started
validation failed
revision created
artifact inventory created
storage started
storage failed
ingestion completed
ingestion failed
```

Logs must not expose:

```text
credentials
access tokens
private repository URLs containing secrets
raw secret values
sensitive source content
```

Observability should follow the project's existing logging/monitoring infrastructure.

---

# 77. Metrics

Where required, useful ingestion metrics may include:

```text
ingestion duration
repository size
artifact count
validation failures
storage failures
ingestion failures
successful ingestions
resource-limit rejections
```

Do not introduce a separate metrics system.

Use the existing observability architecture.

---

# 78. Error Classification

M4 failures should be distinguishable.

Conceptual categories:

```text
INVALID_INPUT
VALIDATION_FAILURE
SECURITY_FAILURE
RESOURCE_LIMIT
ACQUISITION_FAILURE
STORAGE_FAILURE
CONFLICT
INVALID_STATE
AUTHORIZATION_FAILURE
INFRASTRUCTURE_FAILURE
```

Exact error categories/codes must follow the project's established error system.

---

# 79. Typed Application Errors

M4 must not expose raw infrastructure exceptions.

For example:

```text
ProviderException
FilesystemError
ObjectStorageError
IntegrityError
ArchiveError
```

should be translated into appropriate application-level errors where they cross the application boundary.

The API should not reveal internal stack traces.

---

# 80. API Boundary

M4's HTTP exposure should remain thin.

The router should:

```text
receive request
resolve current user/dependencies
invoke M4 application service
return DTO/result
```

It should not:

```text
extract ZIP files
walk directories
call Git
write files
construct storage keys
perform SQL
implement lifecycle rules
```

---

# 81. DTO Boundary

API DTOs should represent application contracts.

Examples of conceptual DTO categories:

```text
StartIngestionRequest
IngestionResponse
RevisionResponse
ArtifactResponse
IngestionStatusResponse
```

Exact DTOs should be created only for actual API use cases.

Do not expose internal infrastructure results.

---

# 82. API Response Semantics

The API must distinguish between:

```text
ingestion accepted
ingestion running
ingestion completed
ingestion failed
validation rejected
authorization denied
resource not found
```

Do not return HTTP 200 with a generic success payload for every state.

The exact status codes must follow the established API contract.

---

# 83. Upload Handling

If local uploads are supported, the API layer should hand the uploaded content to the ingestion application layer.

The router must not implement:

```text
archive extraction
file traversal
path validation
storage key construction
artifact creation
```

Those belong to M4 application/infrastructure boundaries.

---

# 84. Request Size Limits

Upload endpoints must enforce appropriate request-size/resource limits.

Do not rely only on application-level validation after the complete payload has already exhausted server resources.

Where possible:

```text
transport limit
    +
application limit
    +
storage limit
```

should cooperate.

Exact limits must follow architecture/configuration.

---

# 85. Remote Source Validation

Remote source URLs/repository identifiers are untrusted input.

M4 must validate them according to the supported provider contract.

Do not allow arbitrary network behavior through a generic URL fetcher.

The system should not become an unrestricted server-side request mechanism.

---

# 86. SSRF Considerations

If M4 fetches remote resources, the acquisition layer must respect the security architecture and avoid turning repository acquisition into arbitrary internal network access.

Provider-specific acquisition should constrain requests to supported destinations/protocols.

Do not implement:

```text
GET any user-supplied URL
```

as a generic repository ingestion mechanism.

---

# 87. Credential Isolation

Provider credentials should be passed through the approved secret boundary.

Do not place secrets in:

```text
Repository metadata
Revision metadata
Artifact metadata
logs
DTO responses
storage paths
database error strings
```

---

# 88. API Authentication

M4 relies on the identity/authentication boundary provided by M5 and the existing `CurrentUserProvider` abstraction.

M4 must not implement:

```text
JWT parsing
OAuth login
password authentication
user registration
```

inside ingestion services.

---

# 89. API Authorization

M4 authorization remains Project-derived.

For example:

```text
POST /projects/{project_id}/repositories/{repository_id}/ingestion
```

must verify:

```text
repository belongs to project_id
current user has required ProjectAccess
```

before beginning the operation.

---

# 90. Enumeration Protection

A user must not be able to infer another Project's repository/revision/artifact existence through identifier probing.

M4 APIs must follow the established non-enumerating error behavior.

---

# 91. Persistence

M4 persistence may require separate entities for:

```text
revisions
artifacts
ingestion records/jobs
```

The exact schema must follow the authoritative architecture.

Do not put every ingestion concept into the M3 Repository table.

---

# 92. Migrations

M4 database schema changes require new Alembic migrations.

Never rewrite:

```text
M1 migrations
M2 migrations
```

or modify historical migration files merely to simplify M4.

Migration history is part of the project contract.

---

# 93. Migration Safety

M4 migrations must be:

```text
ordered
repeatable
consistent
reviewable
compatible with existing M1/M2 schema
```

Fresh database setup must work:

```text
alembic upgrade head
```

without manual intervention.

---

# 94. Foreign Keys

M4-owned persistence should preserve the appropriate relationship chain:

```text
Project
  ↓
Repository
  ↓
Revision
  ↓
Artifact
```

Foreign keys and deletion semantics must follow the authoritative lifecycle requirements.

Do not add cascading deletion simply because it makes tests easier.

---

# 95. Deletion Semantics

Repository/revision/artifact deletion must be handled deliberately.

Deleting a Repository may involve:

```text
database metadata
source storage
revisions
artifacts
future analysis references
```

Therefore M4 must not assume a simple:

```text
DELETE repository
```

automatically means:

```text
delete everything immediately
```

The final behavior must follow the authoritative lifecycle contract.

---

# 96. Storage Cleanup

If M4 owns source storage cleanup, cleanup must be safe and idempotent.

A failed cleanup should not cause the database to falsely claim that content was never stored.

External storage cleanup must be observable.

---

# 97. Data Integrity

M4 must preserve consistency between:

```text
Repository
Revision
Artifact
Storage reference
```

An Artifact must not reference a nonexistent Repository Revision.

A Revision must not reference a nonexistent Repository.

Storage references must be controlled and validated.

---

# 98. Artifact Integrity

Where content hashes are part of the contract, the system should be able to verify that stored content corresponds to the expected artifact.

This is particularly important for:

```text
reproducibility
analysis input integrity
duplicate detection
storage correctness
```

Do not introduce hash-based semantics without defining what is hashed and why.

---

# 99. Analysis Handoff

M4's final responsibility is to provide a reliable input boundary for later analysis.

Conceptually:

```text
M4
    │
    ▼
Repository Revision
    │
    ▼
Artifact Inventory
    │
    ▼
Controlled Source Access
    │
    ▼
Analysis Engine
```

The analysis engine should not need to rediscover:

```text
where source came from
which revision it belongs to
whether it passed ingestion validation
where it is stored
```

---

# 100. M4 → Analysis Boundary

M4 provides:

```text
repository identity
revision identity
artifact identity
artifact path metadata
storage references
ingestion validity
source availability
```

Later analysis provides:

```text
language detection
framework detection
parsing
IR
symbol resolution
relationship extraction
architecture construction
```

Keep these responsibilities separate.

---

# 101. No Semantic Interpretation

M4 should not answer questions such as:

```text
What architecture does this repository use?
Which module depends on which?
Which class implements which interface?
Which endpoint calls which service?
```

Those are analysis questions.

M4 should answer:

```text
Was this source safely acquired?
What artifacts exist?
Where are they stored?
Which revision do they belong to?
Is the source ready for analysis?
```

---

# 102. Testing Philosophy

M4 testing must verify both behavior and boundaries.

Required categories include:

```text
unit tests
integration tests
database tests
storage tests
API tests
security tests
resource-limit tests
isolation tests
migration tests
architecture tests
regression tests
```

Tests should cover failure paths, not only successful ingestion.

---

# 103. Acquisition Tests

Provider/acquisition tests should verify:

```text
successful acquisition
provider failure
invalid source
authentication failure where applicable
network failure
timeout
unexpected response
cleanup after failure
```

Do not make the entire test suite dependent on live third-party providers.

Use deterministic test doubles where appropriate.

---

# 104. Archive Security Tests

If archives are supported, tests must include:

```text
valid archive
path traversal archive
absolute-path archive
oversized archive
oversized extracted content
too many files
malformed archive
nested archive behavior where relevant
```

The goal is to prove that untrusted archive input cannot escape the storage boundary or exhaust resources.

---

# 105. Storage Tests

Storage integration tests should verify:

```text
store
retrieve
exists
delete where supported
isolation
collision behavior
cleanup
failure behavior
```

Use the project's supported storage implementation/test infrastructure.

---

# 106. Isolation Tests

At minimum:

```text
Project A
  Repository A
  Revision A
  Artifact A

Project B
  Repository B
  Revision B
  Artifact B
```

A user authorized only for Project A must not be able to:

```text
ingest B
read B
list B revisions
read B artifacts
modify B ingestion
delete B content
```

---

# 107. Lifecycle Tests

Tests must verify valid and invalid lifecycle transitions.

Example conceptual structure:

```text
state A
   ↓
valid transition
   ↓
state B
```

and:

```text
state A
   ↓
invalid transition
   ↓
typed error
```

Exact states must follow the authoritative contract.

---

# 108. Idempotency Tests

Where idempotency is part of the contract, test:

```text
same request twice
same revision twice
worker retry
partial failure followed by retry
concurrent ingestion attempts
```

The result must remain consistent.

---

# 109. Concurrency Tests

M4 should consider concurrent operations such as:

```text
two ingestion requests
same Repository
same revision
```

The database/storage design must prevent inconsistent duplicate state where the contract requires uniqueness.

Database constraints remain authoritative for concurrency.

---

# 110. API Tests

API tests should verify:

```text
authentication
authorization
Project scoping
request validation
resource limits
success responses
failure responses
lifecycle state
revision responses
artifact responses
error codes
```

Do not test only HTTP 200 responses.

---

# 111. Architecture Tests

M4 architecture tests should prevent:

```text
relative imports
M4 domain importing infrastructure
routers manipulating files
M4 creating Repository duplicates
M4 implementing Repository RBAC
M4 importing analysis engine internals prematurely
M4 executing repository source
M4 bypassing ProjectAuthorization
```

---

# 112. Performance

M4 must avoid unnecessary memory amplification.

Do not assume every repository can safely be:

```text
read entirely into RAM
```

Resource limits should influence:

```text
streaming
temporary storage
archive extraction
hashing
artifact processing
```

The exact implementation should follow resource constraints.

---

# 113. Large Repository Handling

Large repositories must not cause uncontrolled:

```text
RAM usage
disk usage
temporary-file accumulation
database row explosion
network retries
worker concurrency
```

M4 should process source in controlled units where practical.

---

# 114. Cleanup Guarantees

Every temporary resource created during ingestion should have a defined cleanup path.

Conceptually:

```text
try
    acquire
    validate
    store
finally
    cleanup temporary resources
```

The actual implementation must account for failure and process interruption.

---

# 115. No Silent Data Loss

M4 must not silently discard source artifacts because they are inconvenient.

If an artifact is excluded:

```text
ignore rule
unsupported artifact
security rejection
resource-limit rejection
```

the behavior must be defined by the ingestion contract.

Where auditability requires it, the exclusion reason should be observable.

---

# 116. Error Reporting

User-facing errors should be actionable without exposing sensitive internals.

Good:

```text
repository exceeds configured ingestion limit
```

Bad:

```text
OSError: [Errno 28] No space left on device at /srv/app/secrets/...
```

Internal diagnostic detail may remain in secure logs where appropriate.

---

# 117. No Raw Source Leakage

API responses should not return complete repository source content unless a specific later feature explicitly requires controlled source viewing.

M4's normal API contracts should return:

```text
metadata
status
references
identifiers
```

rather than entire source trees.

---

# 118. Frontend Boundary

M6 consumes M4 through API contracts.

M6 should be able to display:

```text
repository status
ingestion status
revision information
artifact counts/metadata where required
errors
```

without knowing:

```text
storage implementation
database schema
acquisition provider internals
```

---

# 119. Frontend Complexity Constraint

The StackSense frontend is intentionally simple.

M4 should not require M6 to create a large frontend abstraction hierarchy.

The frontend should remain approximately:

```text
pages/screens
basic shared components where genuinely reused
API layer
minimal hooks/state
```

Do not introduce frontend architecture complexity merely because M4 has a sophisticated backend pipeline.

---

# 120. M7 Integration Contract

M7 must be able to verify:

```text
Repository
    ↓
Ingestion
    ↓
Validation
    ↓
Revision
    ↓
Artifact inventory
    ↓
Storage
    ↓
Ready for analysis
```

M4 must provide enough tests and observability for M7 to verify this complete path.

---

# 121. Vertical Slice

The P2 vertical slice should be capable of demonstrating:

```text
Authenticate
     ↓
Open/Create Project
     ↓
Register Repository
     ↓
Provide repository source
     ↓
Start ingestion
     ↓
Validate source
     ↓
Store source
     ↓
Create revision/artifact state
     ↓
Display repository/ingestion status
     ↓
Repository ready for later analysis
```

M4 owns the ingestion segment.

---

# 122. M4 Definition of Done

M4 is complete only when:

```text
Repository acquisition contract exists
Ingestion application service exists
Validation boundary exists
Safe storage contract exists
Revision handling exists
Artifact inventory exists
Resource limits are enforced
Untrusted input is safely handled
Project authorization is enforced
Ingestion lifecycle is implemented
Failure behavior is defined
Persistence exists
Migrations exist
API contracts exist where required
Tests exist
Security tests exist
Isolation tests exist
Architecture tests pass
M1/M2 regression passes
M3 integration works
No analysis logic leaked into M4
No duplicate Repository model exists
No Repository-level RBAC exists
No arbitrary code execution exists
Absolute imports are preserved
Formatting/lint/type checks pass
M4 vertical slice works
```

---

# 123. M4 Implementation Order

Recommended implementation order:

```text
1. Read master.txt M4/repository ingestion sections
2. Read M1-M2-CONTEXT.md
3. Read M3-CONTEXT.md
4. Inspect actual M1/M2/M3 implementation
5. Identify exact M3 Repository contract
6. Define M4 domain concepts
7. Define Revision/Artifact/Ingestion contracts
8. Define lifecycle and failure semantics
9. Define persistence models
10. Define migrations
11. Define storage contract
12. Implement storage infrastructure
13. Define acquisition contract
14. Implement acquisition adapters
15. Implement validation
16. Implement ingestion orchestration
17. Implement revision/artifact persistence
18. Integrate authorization
19. Add API contracts where required
20. Add integration tests
21. Add security/resource-limit tests
22. Add architecture tests
23. Run complete regression
24. Verify M3 integration
25. Verify M6-facing API contract
26. Produce implementation report
```

Do not implement the entire future analysis pipeline merely because the ingestion pipeline eventually feeds it.

---

# 124. Parallel Development Rule

M4 may be developed in parallel with M5 and M6.

Therefore M4 must rely on stable contracts rather than unfinished implementation details.

If M5 is not complete:

```text
depend on CurrentUserProvider contract
```

Do not wait for or recreate the entire authentication implementation.

If M6 is not complete:

```text
implement backend contracts
```

Do not couple M4 services to frontend code.

If M3 is not complete:

```text
implement against the agreed M3 Repository contract
```

Do not create a parallel Repository model.

---

# 125. Contract Gap Rule

If M4 discovers:

```text
M3 does not expose information required by M4
```

the correct process is:

```text
STOP
   ↓
document the missing contract
   ↓
verify master.txt
   ↓
propose the smallest contract change
   ↓
approve/update architecture if required
   ↓
implement
```

Incorrect:

```text
M3Repository
    +
M4Repository
```

or:

```text
M4 secretly queries M3 database tables
```

---

# 126. Security Checklist

Before declaring M4 complete, verify:

```text
[ ] Repository content is treated as untrusted
[ ] Repository code is never executed
[ ] Archive traversal is prevented
[ ] Path traversal is prevented
[ ] Symlink escapes are prevented where relevant
[ ] Resource limits are enforced
[ ] Upload limits are enforced
[ ] Remote acquisition is constrained
[ ] SSRF risks are addressed
[ ] Credentials are not logged
[ ] Credentials are not stored in source metadata
[ ] Cross-Project access is impossible
[ ] Storage namespaces are isolated
[ ] Raw infrastructure errors do not reach clients
[ ] Temporary files are cleaned
[ ] Failed ingestion cannot become READY incorrectly
```

---

# 127. Architecture Checklist

Before declaring M4 complete:

```text
[ ] master.txt followed
[ ] M1/M2 contracts preserved
[ ] M3 Repository contract reused
[ ] no Organization reintroduced
[ ] no Project.owner_id reintroduced
[ ] no Repository-level RBAC
[ ] no duplicate Repository model
[ ] no analysis engine logic
[ ] no IR logic
[ ] no Architecture Model logic
[ ] no Knowledge Graph logic
[ ] no AI logic
[ ] absolute imports only
[ ] domain/infrastructure boundaries preserved
[ ] routers remain thin
[ ] DTOs are explicit
[ ] repositories do not commit
[ ] migrations do not rewrite history
```

---

# 128. Testing Checklist

```text
[ ] unit tests
[ ] acquisition tests
[ ] validation tests
[ ] archive security tests
[ ] storage tests
[ ] revision tests
[ ] artifact tests
[ ] lifecycle tests
[ ] failure tests
[ ] resource-limit tests
[ ] authorization tests
[ ] Project isolation tests
[ ] concurrency tests
[ ] API tests
[ ] migration tests
[ ] architecture tests
[ ] full regression suite
```

---

# 129. Independent Review

The independent reviewer must inspect M4 independently of the Builder's implementation report.

Review categories:

```text
Architecture
M3 integration
Domain design
Application boundaries
Persistence
Storage safety
Acquisition safety
Resource limits
Security
Authorization
Project isolation
Lifecycle correctness
Revision semantics
Artifact inventory
Error handling
API contracts
Tests
Migration correctness
Regression
M6 integration
M7 readiness
```

The reviewer must not silently modify M4.

---

# 130. Reviewer Severity

Findings use:

```text
BLOCKER
MAJOR
MINOR
OBSERVATION
```

The review conclusion uses:

```text
PASS
PASS WITH NON-BLOCKING FINDINGS
CHANGES REQUIRED
```

Every substantive finding should include:

```text
location
evidence
why it violates the contract
expected behavior
```

Do not report personal style preferences as architectural defects.

---

# 131. M4 Forbidden Outcomes

M4 implementation is invalid if it introduces:

```text
Organization hierarchy
Project.owner_id
Repository-level RBAC
M4-specific duplicate Repository model
analysis engine logic
IR construction
Architecture Model construction
Knowledge Graph construction
AI/LLM usage
arbitrary source execution
unbounded extraction
unsafe archive extraction
path traversal
uncontrolled filesystem writes
generic arbitrary URL fetching
credential leakage
direct database access from routers
relative imports
rewritten historical migrations
silent M3 contract changes
frontend-dependent ingestion logic
```

---

# 132. Final M4 Contract

M4 can be summarized as:

```text
M4 = Repository Ingestion, Validation & Storage

Consumes:
    M3 Repository identity
    M3 Project relationship
    M2 ProjectAuthorization
    M2 CurrentUserProvider seam
    existing persistence conventions

Owns:
    acquisition
    ingestion
    validation
    resource limits
    revision handling
    artifact inventory
    safe storage
    ingestion lifecycle
    ingestion failure handling

Provides:
    ingestion application contract
    revision contract
    artifact contract
    storage references
    ingestion status
    controlled source input for analysis

Does not own:
    Repository identity
    Project authorization model
    authentication
    source parsing
    IR
    symbol resolution
    relationship extraction
    Architecture Model
    Knowledge Graph
    RAG
    AI
    diagrams
    reports
    frontend architecture
```

---

# 133. Final Boundary Diagram

```text
                         M1 + M2
                    Frozen Foundation
                           │
                           ▼
                         M3
                 Repository Platform
                           │
                    Repository ID
                    + Project ID
                           │
                           ▼
              ┌─────────────────────────┐
              │           M4            │
              │ Repository Ingestion    │
              │                         │
              │ Acquisition             │
              │      ↓                  │
              │ Validation              │
              │      ↓                  │
              │ Revision                │
              │      ↓                  │
              │ Artifact Inventory      │
              │      ↓                  │
              │ Safe Storage            │
              │      ↓                  │
              │ Ready for Analysis      │
              └────────────┬────────────┘
                           │
                           ▼
                    Future Analysis
                           │
                           ▼
                         P3+
```

---

# 134. Non-Negotiable Rules

```text
1. master.txt remains the ultimate source of truth.

2. M1 and M2 are frozen.

3. M3 owns Repository identity and registration.

4. M4 owns Repository ingestion, validation, revision/artifact preparation, and storage.

5. M4 must not create a second Repository model.

6. Project remains the authorization and isolation boundary.

7. Repository-level RBAC must not be introduced.

8. Repository contents are untrusted.

9. Repository code must never be executed during ingestion.

10. Archive/path traversal must be prevented.

11. Resource limits must be enforced.

12. External storage consistency must not be confused with database transaction atomicity.

13. Revision and Repository are distinct concepts.

14. Artifact inventory and IR are distinct concepts.

15. Ingestion and analysis are distinct phases.

16. M4 must not construct IR.

17. M4 must not construct the Architecture Model.

18. M4 must not construct the Knowledge Graph.

19. M4 must not invoke AI/LLMs.

20. Authentication belongs to M5.

21. M4 must use the existing CurrentUserProvider seam.

22. M4 must use ProjectAuthorization.

23. Routers remain thin.

24. DTOs remain explicit.

25. Infrastructure implementations remain behind appropriate contracts.

26. Repositories flush but do not independently commit.

27. Historical Alembic migrations must not be rewritten.

28. Absolute imports are mandatory.

29. Failed ingestion must never be incorrectly represented as ready.

30. Parallel developers consume established contracts rather than creating competing abstractions.

31. Any contract gap must be surfaced explicitly.

32. No silent architecture changes are permitted.
```