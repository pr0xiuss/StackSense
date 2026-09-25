# Module Context: M7 — Integration, Verification & Freeze

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

M7 owns final integration, system-level verification, cross-module validation, and release/freeze readiness across the completed StackSense modules.

M7 integrates the capabilities delivered by M1–M6 without taking ownership of their internal domain responsibilities.

## Critical Responsibilities

M7 focuses on:

- cross-module integration
- end-to-end workflows
- contract verification
- regression testing
- architecture verification
- security verification
- isolation verification
- deployment/readiness validation
- final documentation consistency
- vertical-slice verification
- freeze readiness

## Module Boundary

M7 must not absorb domain responsibilities belonging to M1–M6.

Its purpose is to verify and integrate the system, not to redesign individual modules for convenience.

## Architecture Verification

M7 must verify that:

- module boundaries remain intact
- dependencies follow the approved direction
- frozen foundations remain unchanged
- Project remains the primary ownership/access boundary
- Organization has not been reintroduced
- Repository-level RBAC has not been introduced
- M3/M4 responsibilities remain separated
- analysis boundaries remain intact
- API and frontend contracts remain consistent
- security and isolation requirements hold

## Evidence Rule

A module is not considered complete merely because its local tests pass.

M7 should verify:

- functional behavior
- architecture compliance
- cross-module contracts
- integration behavior
- persistence behavior
- security boundaries
- regression behavior
- end-to-end vertical slices

## Freeze Rule

Freeze is performed only after the required verification evidence is complete and the implementation conforms to `master.txt`.

If implementation conflicts with the architecture, follow the architecture change process rather than silently changing the architecture.

## Implementation Rule

This context provides implementation and verification guidance only.

It does not authorize architectural expansion or changes to `master.txt`.


**Location:** `.agents/context/modules/M7-CONTEXT.md`

**Status:** FROZEN FOR IMPLEMENTATION  
**Phase:** P2 — Project & Repository Platform  
**Module:** M7 — Integration, Evaluation & P2 Freeze  
**Upstream:** M1 + M2 + M3 + M4 + M5 + M6  
**Purpose:** Final P2 integration, verification, evaluation preparation, stabilization, and freeze

---

# 1. Purpose

M7 is the final integration boundary of P2.

M7 is not another feature-development module.

Its responsibility is to take:

```text
M1
Project Domain Foundation

M2
Project Access & Resource Boundary

M3
Repository Domain & Registration

M4
Repository Ingestion, Validation & Storage

M5
Identity & Authentication

M6
P2 API & Frontend Product Flow
```

and verify that they operate together as one coherent production-quality P2 system.

The goal is:

```text
implemented modules
        ↓
integrated contracts
        ↓
working vertical slice
        ↓
verification
        ↓
evaluation
        ↓
stabilization
        ↓
P2 FREEZE
```

---

# 2. Architectural Authority

The ultimate architectural source of truth is:

```text
master.txt
```

This file records the implementation context for M7.

It does not override `master.txt`.

If a conflict is discovered:

```text
1. Stop.
2. Inspect the authoritative architecture.
3. Identify the conflicting decision.
4. Resolve the conflict explicitly.
5. Do not silently modify architecture.
```

---

# 3. Required Context

Before beginning M7, the implementer/reviewer must understand:

```text
.agents/context/shared/M1-M2-CONTEXT.md

.agents/context/modules/M3-CONTEXT.md
.agents/context/modules/M4-CONTEXT.md
.agents/context/modules/M5-CONTEXT.md
.agents/context/modules/M6-CONTEXT.md
```

M7 depends on all previous module contracts.

---

# 4. M7 Mission

M7 must establish that:

```text
Authentication
       ↓
Current User
       ↓
Project
       ↓
ProjectAccess
       ↓
ProjectAuthorization
       ↓
Repository
       ↓
Repository Ingestion
       ↓
Validation
       ↓
Storage
       ↓
Repository Ready
```

works end-to-end through the actual product.

The final P2 product experience must be demonstrable through the frontend and backend together.

---

# 5. P2 Completion Rule

P2 is not complete merely because:

```text
M1 = complete
M2 = complete
M3 = complete
M4 = complete
M5 = complete
M6 = complete
```

The phase is complete only when the integrated system satisfies:

```text
Backend capability
+
Frontend capability
+
Integrated contracts
+
Tests
+
Architecture compliance
+
Security
+
Observability where required
+
Documentation
+
Working vertical slice
+
Demonstrable product
```

---

# 6. M7 Does Not Redefine Modules

M7 must not become a place where unresolved module responsibilities are casually moved.

For example:

```text
M3 missing Repository behavior
```

must not become:

```text
M7 implements Repository behavior
```

Likewise:

```text
M4 missing ingestion behavior
```

must not become:

```text
M7 implements ingestion
```

M7 integrates and verifies.

It does not become a miscellaneous feature module.

---

# 7. Current P2 Hierarchy

The current hierarchy is:

```text
User
  ↓
Project
  ↓
Repository
  ↓
Repository Revision / Source
  ↓
Analysis
```

P2 ends before the actual analysis engine.

---

# 8. Organization Rule

The current P2 architecture does not use Organization as a first-class implementation boundary.

Do not reintroduce:

```text
Organization
organization_id
OrganizationService
OrganizationRepository
Organization UI
Organization authorization
```

during integration.

Older Organization-oriented material in historical architecture sections must not override the current P2 baseline.

---

# 9. Project Boundary

Project remains the primary:

```text
ownership boundary
authorization boundary
access boundary
isolation boundary
repository boundary
```

M7 must verify that all modules respect this.

---

# 10. Project Ownership

Project does not use:

```text
Project.owner_id
```

Ownership is represented through:

```text
ProjectAccess
    role = OWNER
```

M7 must verify that no downstream module has reintroduced another ownership mechanism.

---

# 11. ProjectAccess

The established roles are:

```text
OWNER
ADMIN
DEVELOPER
VIEWER
```

Permissions:

| Role | Read | Create | Update | Delete |
|---|---:|---:|---:|---:|
| OWNER | ✓ | ✓ | ✓ | ✓ |
| ADMIN | ✓ | ✓ | ✓ | ✓ |
| DEVELOPER | ✓ | ✓ | ✓ | ✗ |
| VIEWER | ✓ | ✗ | ✗ | ✗ |

Membership management:

```text
OWNER
ADMIN
```

M7 must verify these semantics remain unchanged.

---

# 12. Authorization Chain

The expected authorization chain is:

```text
Request
   ↓
Authenticated User
   ↓
ProjectAuthorization
   ↓
ProjectAccess
   ↓
ProjectRole
   ↓
Permission
   ↓
Resource Operation
```

For Repository resources:

```text
Request
   ↓
Repository
   ↓
repository.project_id
   ↓
ProjectAuthorization
   ↓
ProjectAccess
   ↓
Permission
```

---

# 13. No Repository RBAC

M7 must explicitly verify that no module introduced:

```text
RepositoryRole
RepositoryAccess
RepositoryPermission
RepositoryMember
```

as a competing authorization system.

Repository authorization derives from Project authorization.

---

# 14. Identity Boundary

M5 replaces the temporary identity implementation behind the existing identity seam.

The intended architecture remains:

```text
Authentication
       ↓
CurrentUserProvider
       ↓
Current User
       ↓
ProjectAuthorization
```

M7 must verify that M5 did not force M1/M2 to adopt a different authorization model.

---

# 15. Authentication vs Authorization

M7 must distinguish:

```text
Authentication:
Who is the User?
```

from:

```text
Authorization:
What can this User access/do?
```

Successful authentication must not automatically imply access to every Project.

---

# 16. Repository Boundary

M3 owns:

```text
Repository identity
Repository registration
Repository metadata
Repository lifecycle defined by the M3 contract
Project relationship
Repository application/API contract
```

M4 owns:

```text
source acquisition
ingestion
validation
storage
revision/artifact lifecycle
```

M7 must verify that these boundaries remain clear.

---

# 17. Ingestion Boundary

M4's conceptual pipeline is:

```text
Repository Source
       ↓
Ingestion
       ↓
Validation
       ↓
Controlled Storage
       ↓
Revision / Artifacts
       ↓
Ready for Analysis
```

M7 must verify that M6 does not pretend ingestion is complete before the backend says it is complete.

---

# 18. Analysis Boundary

M7 must verify that P2 did not accidentally absorb P3 analysis responsibilities.

P2 must not implement:

```text
AST parsing
symbol extraction
relationship extraction
architecture construction
knowledge graph construction
RAG
AI reasoning
diagram generation
```

The P2 endpoint is:

```text
Repository Ready for Analysis
```

---

# 19. Untrusted Repository Rule

Repository contents are untrusted.

M7 must verify that the integrated system does not execute repository code during ingestion.

Forbidden behavior includes executing:

```text
setup.py
package scripts
Makefiles
shell scripts
repository binaries
arbitrary commands
```

as part of repository ingestion.

---

# 20. Source Storage Boundary

M7 must verify that:

```text
PostgreSQL
```

stores application metadata/state/references while:

```text
approved storage layer
```

stores actual repository/source content according to the architecture.

Do not introduce arbitrary source-file storage directly into relational domain tables merely for convenience.

---

# 21. Transaction Boundary

M7 must verify that database transactions and external storage operations are not incorrectly treated as one atomic transaction.

For example:

```text
PostgreSQL rollback
```

does not automatically imply:

```text
filesystem/object storage rollback
```

If M4 uses external storage, its consistency/recovery behavior must be explicit.

---

# 22. Persistence Model

The established persistence model is:

```text
SQLAlchemy 2.x
synchronous Session
```

Repositories:

```text
Repository Contract
       ↓
SQLAlchemy Implementation
       ↓
Session
```

Repositories flush but do not independently commit.

M7 must detect accidental introduction of a conflicting persistence model.

---

# 23. Migration Policy

Historical migrations must not be rewritten.

M7 must use:

```text
new corrective migration
```

when a schema correction is genuinely required.

M7 must verify the complete migration chain on a fresh database.

---

# 24. Fresh Database Verification

A mandatory M7 check is:

```text
Fresh PostgreSQL database
        ↓
alembic upgrade head
        ↓
all migrations
        ↓
successful schema
        ↓
application startup
```

Testing only against an already-modified developer database is insufficient.

---

# 25. Migration History

M7 must verify that M1/M2 historical migrations remain intact.

The M2 migration sequence established:

```text
efcb63702631
initial projects

d270d0bce7f6
ProjectAccess / temporary ownership state

bf1b64e1ccdd
ownership column removal

64ab0e257e77
user_id index
```

M7 must not rewrite this history.

New module migrations must build on top of it.

---

# 26. Vertical Slice

The primary P2 vertical slice is:

```text
Browser
   ↓
Authentication
   ↓
Current User
   ↓
Projects
   ↓
Create Project
   ↓
Project Access
   ↓
Register Repository
   ↓
Provide Repository Source
   ↓
Start Ingestion
   ↓
Validate
   ↓
Store
   ↓
Repository State
   ↓
Ready for Analysis
```

This must work using the real integrated system.

---

# 27. Evaluation 1

P2 should prepare the platform for the first meaningful StackSense evaluation:

```text
Source Understanding
```

The core product question is:

```text
Can StackSense correctly establish and prepare the contents of a repository for analysis?
```

P2 establishes the repository and ingestion foundation required for that evaluation.

---

# 28. Evaluation Flow

The broader evaluation flow is:

```text
Open StackSense
      ↓
Open/create Project
      ↓
Add Repository
      ↓
Start ingestion
      ↓
Show Repository status
      ↓
Start analysis
      ↓
Show analysis job/status
      ↓
Show detected languages/frameworks
      ↓
Show extracted source entities
```

The latter analysis stages belong to later phases.

M7 must ensure P2 leaves the system in a correct state for them.

---

# 29. Product Demonstration

The P2 demonstration should visibly prove:

```text
1. User can authenticate.
2. User can access Projects.
3. User can create a Project where permitted.
4. User can open a Project.
5. User can register a Repository.
6. User can provide Repository source.
7. Ingestion begins.
8. Validation/storage occurs.
9. Repository state changes correctly.
10. Repository reaches the appropriate ready state.
```

---

# 30. Multi-User Isolation

M7 must explicitly test multiple Users.

Example:

```text
User A
   ↓
Project A
   ↓
Repository A
```

and:

```text
User B
   ↓
Project B
   ↓
Repository B
```

User A must not access Project B or Repository B without appropriate ProjectAccess.

---

# 31. Cross-Project Isolation

Test attempts such as:

```text
User A
GET /projects/{project_b_id}
```

and:

```text
User A
GET /projects/{project_b_id}/repositories/{repository_b_id}
```

must follow the established authorization/non-enumeration behavior.

---

# 32. ID Manipulation

M7 must verify that changing:

```text
project_id
repository_id
revision_id
```

in a URL or request body does not bypass authorization.

IDs are opaque identifiers.

The backend must establish resource scope.

---

# 33. Viewer Verification

A User with:

```text
VIEWER
```

must be able to read according to the established contract but must not be able to perform unauthorized mutations.

Test:

```text
read
create
update
delete
membership management
```

and verify the role matrix.

---

# 34. Developer Verification

A:

```text
DEVELOPER
```

must be able to:

```text
read
create
update
```

but not:

```text
delete
```

where the established resource operation maps to those permissions.

---

# 35. Admin Verification

An:

```text
ADMIN
```

must have the established Project-level management permissions, including membership management where specified.

M7 must not silently expand ADMIN beyond the approved role matrix.

---

# 36. Owner Verification

An:

```text
OWNER
```

must retain the established full Project permissions.

M7 should verify ownership remains represented through:

```text
ProjectAccess(role=OWNER)
```

rather than a Project owner column.

---

# 37. Authentication Tests

M7 must test:

```text
unauthenticated request
invalid credentials/token
expired authentication where applicable
authenticated request
current-user resolution
```

The exact authentication mechanism follows M5.

---

# 38. Authorization Tests

M7 must test:

```text
authenticated but unauthorized User
authorized User
role-specific mutation
cross-project access
Repository access through Project
```

Authentication success must not be treated as authorization success.

---

# 39. Project Tests

M7 should verify:

```text
create Project
list accessible Projects
get accessible Project
reject inaccessible Project
delete Project where permitted
ProjectAccess creation
ProjectAccess role behavior
```

---

# 40. Repository Tests

M7 should verify:

```text
Repository creation/registration
Repository retrieval
Repository/project relationship
Repository isolation
Repository lifecycle
Repository authorization
```

according to the M3 contract.

---

# 41. Ingestion Tests

M7 should verify:

```text
source accepted
source rejected when invalid
unsupported files handled
ignored files handled
resource limits enforced
path traversal rejected
storage failure handled
revision/artifact state correct
ingestion state correct
```

according to M4.

---

# 42. Frontend Tests

M7 must verify the actual product flow, not only isolated frontend components.

At minimum:

```text
login/authentication
Projects page
Project creation
Project details
Repository registration
Repository details
ingestion status
loading
empty state
authorization failure
authentication failure
network failure
```

---

# 43. Frontend Simplicity Verification

M7 must explicitly check that M6 did not create unnecessary frontend architecture.

The intended frontend remains simple.

Do not reject the implementation because it is not architecturally equivalent to the backend.

The desired approach is:

```text
simple
direct
maintainable
small
```

with only the abstractions genuinely required.

---

# 44. No Views Layer

M7 must verify that M6 did not introduce a separate:

```text
views/
```

architecture layer.

Pages/screens are sufficient.

---

# 45. No Excessive Component Decomposition

M7 should flag unnecessary structures such as:

```text
one-file-per-button
one-file-per-label
one-file-per-form-field
deep component trees
```

when they add complexity without meaningful reuse.

This is a maintainability concern.

---

# 46. API Contract Verification

M7 must verify:

```text
backend DTO
      ↓
HTTP response
      ↓
frontend API client
      ↓
frontend state
      ↓
UI
```

remains compatible.

No silent field renaming or response-shape changes should exist.

---

# 47. API Versioning

New P2 API functionality must use:

```text
/api/v1/
```

according to the established API architecture.

M7 must detect accidental unversioned new endpoints.

---

# 48. HTTP Status Verification

Verify established semantics such as:

```text
create → 201
successful retrieval → 200
successful delete → 204
conflict → 409
authorization/non-enumeration behavior → established contract
```

Repository/ingestion-specific statuses must follow their approved contracts.

---

# 49. Error Contract Verification

M7 must verify:

```text
domain/application error
       ↓
central error handling
       ↓
stable API error
       ↓
frontend error handling
```

Raw exceptions such as:

```text
IntegrityError
SQLAlchemy exceptions
filesystem exceptions
stack traces
```

must not leak directly to API consumers.

---

# 50. Error Categories

The integrated system should distinguish:

```text
validation
authentication
authorization
not found
conflict
storage/ingestion failure
network failure
internal server failure
```

The exact error code/category system must follow the existing implementation.

---

# 51. Security Verification

M7 must explicitly verify:

```text
[ ] authentication required where appropriate
[ ] Project authorization enforced
[ ] Repository authorization derived from Project
[ ] cross-project isolation
[ ] role permissions
[ ] membership management permissions
[ ] no frontend-only authorization
[ ] no source execution
[ ] no path traversal
[ ] resource limits
[ ] no secrets in logs
[ ] no secrets in frontend
[ ] safe error responses
```

---

# 52. Repository Security

M7 must verify that repository source is treated as untrusted data.

The integrated system must not:

```text
execute repository code
execute package installation scripts
execute shell scripts from the repository
import arbitrary repository modules
```

as part of P2 ingestion.

---

# 53. Path Traversal Verification

If archives or filesystem extraction are supported, test malicious paths such as:

```text
../../secret
../../../etc/passwd
absolute filesystem paths
symlink escape attempts
```

where relevant to the implemented storage mechanism.

The implementation must remain within its intended storage boundary.

---

# 54. Resource Limits

M7 must verify configured limits for:

```text
repository size
file size
archive size
file count
ingestion workload
```

where those limits are part of the M4 contract.

The exact limits must come from the authoritative architecture/configuration.

Do not invent new limits solely for M7.

---

# 55. Storage Failure

Simulate or test:

```text
storage unavailable
write failure
partial operation
database failure
```

and verify the system does not falsely report:

```text
READY
```

when the underlying operation did not complete successfully.

---

# 56. Recovery

If M4 defines recovery/retry behavior, M7 must verify it.

For example:

```text
FAILED
   ↓
retry
   ↓
INGESTING
   ↓
READY
```

Only use lifecycle states actually defined by the implementation contract.

---

# 57. Concurrency

M7 should test relevant concurrent operations such as:

```text
two simultaneous ProjectAccess grants
two Repository registrations
duplicate ingestion requests
simultaneous state transitions
```

where the underlying module defines concurrency-sensitive behavior.

The objective is to verify that database constraints and service logic protect invariants.

---

# 58. Database Integrity

M7 must verify:

```text
foreign keys
unique constraints
primary keys
indexes
cascade behavior
nullable/non-nullable constraints
timestamps
```

against the approved architecture.

Do not add constraints simply because they seem generally useful if they conflict with the established design.

---

# 59. Transaction Verification

Verify that:

```text
application service
      ↓
repositories
      ↓
shared Session
```

participate in the intended transaction.

Repositories must not independently commit.

---

# 60. Migration Verification

Run:

```text
alembic upgrade head
```

against a fresh database.

Then verify:

```text
application startup
database connectivity
required tables
required indexes
required constraints
```

---

# 61. Rollback Verification

Where applicable, test failure inside a transaction and verify:

```text
database changes rollback
```

without incorrectly claiming external storage automatically rolled back.

External storage consistency must follow M4's explicit behavior.

---

# 62. Regression Verification

M7 must ensure M1/M2 behavior remains unchanged after M3–M6 integration.

Especially verify:

```text
Project creation
Project listing
Project isolation
Project deletion
ProjectAccess
ProjectRole
ProjectAuthorization
CurrentUserProvider seam
```

---

# 63. Existing M1/M2 Tests

All existing M1/M2 tests must continue to pass.

M7 must not weaken or delete existing tests merely because later modules changed.

If a test fails:

```text
identify regression
```

before modifying the test.

---

# 64. Test Modification Rule

Do not change a test solely to make a failing implementation pass.

First determine:

```text
Is the implementation wrong?
Is the test stale?
Did the architecture deliberately change?
Was the contract changed through an approved decision?
```

Only then modify the test if justified.

---

# 65. Architecture Tests

M7 must verify architecture-level constraints including:

```text
absolute imports
module boundaries
dependency direction
no Organization reintroduction
no Repository RBAC
no Project.owner_id
no duplicate authorization mechanism
no persistence leakage
no API business logic
no source execution
```

---

# 66. Dependency Direction

Expected conceptual direction:

```text
API
 ↓
Application
 ↓
Domain
```

with infrastructure implementations behind appropriate contracts.

Infrastructure should not become the domain model.

M7 must verify that new modules do not create circular or inverted dependencies.

---

# 67. Absolute Imports

Backend imports must remain absolute.

Valid:

```python
from backend.platform.projects.domain.project import Project
```

Invalid:

```python
from ..domain.project import Project
```

M7 must run the existing architecture test/check for this.

---

# 68. No Circular Dependency Fixes by Architecture Violation

If a circular import appears:

```text
do not solve it by making boundaries meaningless
```

First determine:

```text
wrong dependency direction
missing contract
incorrect module responsibility
```

Then fix the architectural cause.

---

# 69. Observability

M7 must verify required observability for the implemented P2 system.

At minimum, important operational failures should be diagnosable through appropriate:

```text
logs
health checks
application errors
ingestion failures
authentication failures
```

Do not log sensitive credentials or source secrets.

---

# 70. Health Checks

Application health should be verifiable.

Where existing infrastructure provides health endpoints, M7 should verify:

```text
application running
database reachable
required infrastructure available
```

according to the existing health contract.

---

# 71. Logging

Logs should provide enough context to diagnose failures.

Avoid logging:

```text
passwords
tokens
authorization headers
private credentials
secrets
```

Repository source contents should not be dumped into logs unnecessarily.

---

# 72. Documentation

Before P2 freeze, documentation must be updated where required.

At minimum verify:

```text
README
developer setup
environment configuration
database/migration instructions
API documentation
module documentation
P2 evaluation instructions
```

---

# 73. Developer Setup

A fresh developer should be able to understand:

```text
how to install dependencies
how to configure environment
how to start backend
how to start frontend
how to start database
how to run migrations
how to run tests
```

without relying entirely on private chat history.

---

# 74. API Documentation

The API contract should be discoverable through the existing FastAPI/OpenAPI mechanism and/or project documentation.

M7 must verify that new M3–M6 endpoints are represented correctly.

---

# 75. Frontend Documentation

M6's intentionally simple frontend structure should be understandable to another developer.

Documentation should not describe a complex architecture that does not exist.

---

# 76. Evaluation Dataset

Evaluation should use a known, reproducible repository dataset.

Representative supported technologies may include:

```text
Python
Django
FastAPI
Flask

JavaScript
Express
Node.js

TypeScript
NestJS
Next.js
```

where practical and where those technologies are within the supported architecture.

P2 does not perform the later language/framework analysis itself.

---

# 77. Evaluation Reproducibility

The evaluation should document:

```text
repository source
repository size
ingestion method
environment
configuration
expected state
observed state
```

so the evaluation can be repeated.

---

# 78. Feature Freeze

Before final evaluation:

```text
feature complete
      ↓
tests
      ↓
bug fixes
      ↓
integration verification
      ↓
evaluation preparation
      ↓
temporary feature freeze
      ↓
evaluation
```

Avoid major architecture changes immediately before evaluation.

---

# 79. Freeze Policy

During the P2 freeze, prefer:

```text
bug fixes
security fixes
reliability fixes
test fixes
documentation fixes
small UX/demo polish
```

Avoid:

```text
new architecture
new framework
new database
large refactor
unrelated features
new abstractions without necessity
```

---

# 80. Freeze Does Not Mean Broken Code Is Accepted

A freeze does not mean:

```text
"do not touch anything"
```

It means:

```text
stabilize the architecture
```

Critical bugs and security issues must still be fixed.

---

# 81. Contract Stability

After P2 freeze, module contracts should be considered stable.

The intended direction is:

```text
M1
 ↓
M2
 ↓
M3
 ↓
M4
 ↓
M5
 ↓
M6
 ↓
M7 freeze
```

Later phases should consume these contracts rather than forcing unnecessary P2 redesign.

---

# 82. Contract Gap Protocol

If integration reveals:

```text
M3 lacks capability required by M4
M4 lacks capability required by M6
M5 identity contract breaks M2
M6 requires unsupported backend state
```

do not silently patch around it.

Use:

```text
STOP
 ↓
identify contract gap
 ↓
inspect master.txt
 ↓
identify correct owner
 ↓
propose smallest valid change
 ↓
approve/update contract
 ↓
implement
 ↓
test
```

---

# 83. No Parallel Abstractions

Forbidden integration fixes include:

```text
M4Repository
FrontendRepositoryService
M6AuthorizationService
M7ProjectService
AlternativeCurrentUserProvider
RepositoryPermissionEngine
```

when they merely duplicate existing concepts.

If an existing contract is insufficient, improve the correct owner rather than creating a competing abstraction.

---

# 84. No Silent Architecture Changes

M7 must not silently change:

```text
Project hierarchy
ownership semantics
authorization model
Repository boundary
ingestion boundary
authentication seam
API contract
database ownership
frontend architecture
```

Architecture changes require deliberate review and documentation.

---

# 85. Git / Branch Integration

M7 should verify that the parallel module branches can be integrated cleanly.

The goal is:

```text
M3 branch
      \
M4 branch
       \
M5 branch
        \
M6 branch
         ↓
       M7
         ↓
P2 integrated branch
```

Resolve conflicts by preserving architecture and contracts rather than choosing whichever implementation is easiest to merge.

---

# 86. Merge Conflict Rule

When resolving conflicts:

```text
do not automatically choose ours
do not automatically choose theirs
```

Instead determine:

```text
Which change represents the approved architectural contract?
Which module owns the responsibility?
Does the conflict indicate a duplicated abstraction?
```

Then resolve accordingly.

---

# 87. Schema Conflict Rule

If parallel modules introduce conflicting migrations:

```text
STOP
```

Then determine:

```text
correct schema
migration ordering
ownership
constraint responsibility
```

Do not create arbitrary duplicate migrations just to make Alembic run.

---

# 88. API Conflict Rule

If M3/M4/M5/M6 expose conflicting API contracts:

```text
STOP
```

Determine the authoritative contract before integration.

Do not maintain two endpoints indefinitely merely because both branches implemented different assumptions.

---

# 89. Frontend Conflict Rule

If frontend branches introduce duplicate:

```text
components
API clients
state systems
routing systems
```

prefer the simplest structure consistent with M6.

The frontend is intentionally not a complex architecture.

---

# 90. M7 Verification Sequence

Recommended sequence:

```text
1. Read master.txt P2 sections.
2. Read all M1–M6 contexts.
3. Inspect the complete integrated tree.
4. Inspect module boundaries.
5. Inspect migrations.
6. Inspect API contracts.
7. Inspect frontend structure.
8. Run architecture checks.
9. Run static checks.
10. Run unit tests.
11. Run integration tests.
12. Create fresh database.
13. Run all migrations.
14. Run backend.
15. Run frontend.
16. Verify authentication.
17. Verify Project flow.
18. Verify Repository flow.
19. Verify ingestion flow.
20. Verify role matrix.
21. Verify cross-project isolation.
22. Verify error behavior.
23. Verify storage failure behavior.
24. Verify security constraints.
25. Verify frontend/backend contract.
26. Execute vertical slice.
27. Fix defects.
28. Repeat verification.
29. Prepare evaluation.
30. Freeze P2.
```

---

# 91. Static Verification

Run the project's established tooling.

Where configured, verify:

```text
pytest
ruff
black --check
mypy
```

and the appropriate frontend checks.

Do not invent commands that do not exist in the repository.

Use the repository's actual tooling configuration as authoritative.

---

# 92. Test Verification

The complete test suite should include:

```text
M1 tests
M2 tests
M3 tests
M4 tests
M5 tests
M6 frontend tests
M6 backend/API tests
integration tests
architecture tests
security/isolation tests
```

---

# 93. Test Failure Protocol

If a test fails:

```text
1. Identify failure.
2. Identify responsible module.
3. Determine whether behavior or test is incorrect.
4. Check architecture contract.
5. Fix the responsible implementation.
6. Re-run focused test.
7. Re-run affected integration tests.
8. Re-run complete suite.
```

Do not suppress the failure.

---

# 94. Coverage Philosophy

Coverage percentage is not the sole definition of correctness.

Priority should be:

```text
critical behavior
security boundaries
authorization
transactions
lifecycle transitions
API contracts
integration flow
```

rather than artificially maximizing trivial line coverage.

---

# 95. End-to-End Verification

The complete E2E test should demonstrate:

```text
1. User authenticates.
2. User reaches Projects.
3. User creates Project.
4. Project is persisted.
5. Owner access exists.
6. User opens Project.
7. User registers Repository.
8. Repository belongs to Project.
9. Source is provided.
10. Ingestion starts.
11. Validation executes.
12. Storage succeeds.
13. Repository/revision state updates.
14. Frontend reflects actual state.
15. Repository is ready for analysis.
```

---

# 96. Negative E2E Verification

Also demonstrate:

```text
unauthenticated access denied
unauthorized Project access denied
unauthorized Repository access denied
viewer mutation denied
developer delete denied
invalid source rejected
unsafe path rejected
storage failure handled
```

---

# 97. P2 Evaluation Checklist

```text
[ ] Authentication works
[ ] Project creation works
[ ] Project listing works
[ ] Project isolation works
[ ] Project access works
[ ] Role matrix works
[ ] Repository registration works
[ ] Repository belongs to correct Project
[ ] Source acquisition works
[ ] Ingestion works
[ ] Validation works
[ ] Storage works
[ ] Revision/artifact state works
[ ] Repository lifecycle works
[ ] Frontend reflects backend state
[ ] Unauthorized operations fail
[ ] Invalid source fails safely
[ ] Resource limits are enforced
[ ] Fresh database works
[ ] Full migrations work
[ ] API documentation is correct
[ ] Frontend flow is demonstrable
```

---

# 98. M7 Definition of Done

M7 is complete only when:

```text
[ ] M1 remains frozen and passing
[ ] M2 remains frozen and passing
[ ] M3 is integrated
[ ] M4 is integrated
[ ] M5 is integrated
[ ] M6 is integrated
[ ] Authentication works
[ ] Project access works
[ ] Repository access works
[ ] Repository registration works
[ ] Repository ingestion works
[ ] Repository validation works
[ ] Repository storage works
[ ] Repository lifecycle works
[ ] Frontend product flow works
[ ] API contracts are compatible
[ ] Project isolation is verified
[ ] Repository isolation is verified
[ ] Role matrix is verified
[ ] Security checks pass
[ ] Resource-limit checks pass
[ ] Storage failure behavior is verified
[ ] Fresh database migration works
[ ] Existing migrations are preserved
[ ] Backend tests pass
[ ] Frontend tests pass
[ ] Integration tests pass
[ ] Architecture tests pass
[ ] Static checks pass
[ ] No Organization boundary was reintroduced
[ ] No Project.owner_id was introduced
[ ] No Repository RBAC was introduced
[ ] No duplicate authorization system was introduced
[ ] No repository code execution exists
[ ] No P3 analysis leakage exists
[ ] Frontend remains intentionally simple
[ ] No Views layer was introduced
[ ] No excessive frontend decomposition exists
[ ] Documentation is updated
[ ] P2 vertical slice works
[ ] Evaluation is reproducible
[ ] P2 is ready to freeze
```

---

# 99. Final P2 Architecture Verification

The final integrated architecture should conceptually remain:

```text
                         ┌───────────────────┐
                         │       User        │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │ Authentication    │
                         │       M5          │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │ Current User      │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │     Project       │
                         │       M1          │
                         └─────────┬─────────┘
                                   │
                              access
                                   │
                                   ▼
                         ┌───────────────────┐
                         │  ProjectAccess    │
                         │       M2          │
                         └─────────┬─────────┘
                                   │
                            authorization
                                   │
                                   ▼
                         ┌───────────────────┐
                         │    Repository     │
                         │       M3          │
                         └─────────┬─────────┘
                                   │
                               source
                                   │
                                   ▼
                         ┌───────────────────┐
                         │    Ingestion      │
                         │       M4          │
                         └─────────┬─────────┘
                                   │
                         validate / store
                                   │
                                   ▼
                         ┌───────────────────┐
                         │ Revision / Source │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │ Ready for P3      │
                         │     Analysis      │
                         └───────────────────┘

                         Frontend / API
                              M6
                                │
                                ▼
                         Integrated Product
                                │
                                ▼
                         Verification / Freeze
                                M7
```

---

# 100. M7 Ownership

M7 owns:

```text
integration verification
contract verification
cross-module testing
regression testing
security verification
migration verification
vertical-slice verification
evaluation preparation
documentation verification
stabilization
P2 freeze
```

M7 does not own:

```text
Project domain
ProjectAccess domain
Repository domain
Repository ingestion implementation
Authentication implementation
Frontend feature architecture
Analysis engine
IR
Architecture Model
Knowledge Graph
RAG
AI
Diagram Engine
```

---

# 101. Final P2 Boundary

At the end of P2:

```text
User
  ↓
Authentication
  ↓
Project
  ↓
Project Access
  ↓
Repository
  ↓
Repository Source
  ↓
Ingestion
  ↓
Validation
  ↓
Storage
  ↓
Repository Revision / Artifacts
  ↓
READY FOR ANALYSIS
```

The next phase consumes this stable foundation.

P2 does not need to solve the analysis problem.

---

# 102. Non-Negotiable Rules

```text
1. master.txt remains the ultimate architectural authority.

2. M7 integrates; it does not become a miscellaneous feature module.

3. M1 and M2 remain frozen.

4. M3 owns Repository domain and registration.

5. M4 owns ingestion, validation, and storage.

6. M5 owns identity and authentication.

7. M6 owns the P2 product-facing API/frontend flow.

8. Project remains the primary ownership and authorization boundary.

9. Organization must not be reintroduced.

10. Project.owner_id must not be introduced.

11. ProjectAccess remains the membership/access model.

12. ProjectAuthorization remains the resource authorization mechanism.

13. Repository-level RBAC must not be introduced.

14. Authentication and authorization remain separate concerns.

15. Repository source remains untrusted input.

16. Repository source must never be executed during ingestion.

17. P2 does not implement the P3 analysis engine.

18. P2 does not implement AI/RAG/Knowledge Graph functionality.

19. Backend state remains authoritative.

20. Frontend state remains presentation state.

21. Frontend authorization checks are UX only.

22. API contracts must remain explicit and consistent.

23. DTOs must not be replaced by persistence models.

24. Historical Alembic migrations must not be rewritten.

25. Fresh-database migration verification is mandatory.

26. Repositories must not independently commit transactions.

27. Absolute backend imports remain mandatory.

28. Architecture boundaries must remain intact.

29. Parallel module conflicts must be resolved according to ownership and contract, not convenience.

30. Missing capabilities must be raised as contract gaps.

31. No silent architecture changes are permitted.

32. No silent API contract changes are permitted.

33. No silent database contract changes are permitted.

34. Frontend must remain intentionally simple.

35. No Views layer should be introduced.

36. No excessive frontend component decomposition should be introduced.

37. No duplicate frontend HTTP client should be introduced.

38. No duplicate authorization system should be introduced.

39. No duplicate Repository abstraction should be introduced.

40. No P2 feature should be considered complete until the integrated vertical slice works.
```

---

# 103. Final Freeze Statement

P2 may be declared frozen only after the system can demonstrate:

```text
Authenticated User
        ↓
Accessible Project
        ↓
Correct ProjectAccess
        ↓
Authorized Repository
        ↓
Safe Source Acquisition
        ↓
Validated Ingestion
        ↓
Controlled Storage
        ↓
Correct Repository State
        ↓
Ready for Analysis
```

with:

```text
tests passing
architecture verified
security verified
migrations verified
frontend/backend contracts verified
documentation updated
evaluation reproducible
```

Only then should P2 transition into its frozen state and become the stable foundation for the next phase.