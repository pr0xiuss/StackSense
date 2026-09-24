# Module Context: M3 — Repository Management

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

M3 owns Repository registration and repository-management concerns within:

`User → Project → Repository`

M3 integrates with the frozen M1/M2 foundation.

## Critical Boundaries

M3 owns repository:

- domain representation
- registration
- lifecycle
- persistence
- repository contracts
- application services
- DTOs
- project relationship
- authorization integration
- API exposure
- tests

M3 does **not** own:

- repository acquisition
- ingestion
- source storage
- snapshot acquisition
- revision processing
- artifact inventory
- file discovery
- parsing
- architecture analysis
- RAG
- AI

Those responsibilities belong to later modules as defined by `master.txt`.

## Authorization Boundary

Repository authorization derives from the Repository's `project_id` and the existing ProjectAccess / ProjectAuthorization model.

Do not introduce independent Repository-level RBAC.

## Frozen Dependencies

M1 and M2 are frozen.

M3 must integrate with their existing contracts and must not casually modify them.

## Hierarchy Rule

Do not reintroduce Organization as a first-class hierarchy.

The authoritative hierarchy is:

`User → Project → Repository`

## Implementation Rule

This context provides implementation guidance only.

It does not authorize architectural expansion, new responsibilities, or changes to `master.txt`.


**Location:** `.agents/context/modules/M3-CONTEXT.md`

**Status:** FROZEN FOR IMPLEMENTATION  
**Module:** M3 — Repository Platform  
**Upstream:** M1 Foundation + M2 Identity & Project Access  
**Downstream:** M4 Repository Acquisition & Ingestion, M5 Identity/Auth extensions, M6 API/Frontend, M7 Integration & Freeze

---

# 1. Purpose

M3 establishes the **Repository Platform** on top of the frozen M1 and M2 foundation.

M3 is responsible for the application's representation of a Repository as a first-class resource belonging to a Project.

M3 provides the stable Repository contracts that later modules consume.

The central responsibility is:

```text
Project
   │
   └── Repository
          ├── identity
          ├── registration
          ├── metadata
          ├── lifecycle
          └── persistence
```

M3 does **not** implement repository acquisition, source ingestion, repository parsing, source-code analysis, architecture interpretation, knowledge extraction, or AI functionality.

---

# 2. Architectural Authority

The authoritative architecture remains:

```text
master.txt
```

This file is a module-specific implementation context.

It does not replace `master.txt`.

If this document conflicts with `master.txt`, the authoritative architecture wins.

If implementation conflicts with this context or with a frozen M1/M2 contract:

```text
stop
→ identify the conflict
→ verify against master.txt
→ surface the required architectural decision
→ do not silently change the architecture
```

---

# 3. Required Upstream Context

M3 depends on:

```text
.agents/context/shared/M1-M2-CONTEXT.md
```

The M1–M2 shared context is mandatory reading before implementing M3.

M3 must reuse:

```text
Project
ProjectAccess
ProjectRole
CurrentUserProvider
ProjectAuthorization
typed application errors
existing transaction conventions
existing repository conventions
existing API conventions
```

M3 must not recreate these concepts.

---

# 4. M3 Mission

M3 establishes a stable Repository platform capable of:

```text
create Repository registration
retrieve Repository
list Project repositories
update Repository metadata allowed by contract
manage Repository lifecycle state
delete Repository where contract permits
persist Repository state
authorize Repository operations through Project access
expose Repository application contracts
expose Repository API contracts
provide tests for Repository behavior
```

The exact final capabilities must remain aligned with the authoritative architecture and approved M3 implementation plan.

---

# 5. M3 Ownership

M3 owns:

```text
Repository domain model
Repository identity
Repository-to-Project relationship
Repository registration
Repository lifecycle
Repository persistence
Repository repository contracts
Repository application services
Repository DTOs
Repository authorization integration
Repository API surface
Repository-related tests
Repository-specific errors
Repository schema migrations
```

M3 provides contracts consumed by M4.

---

# 6. Explicit Non-Ownership

M3 does not own:

```text
repository acquisition
git cloning
remote repository fetching
archive download
archive extraction
filesystem ingestion
repository snapshot acquisition
revision ingestion
source file discovery
artifact inventory generation
repository content storage pipeline
resource-limited ingestion workers
source parsing
AST analysis
IR generation
architecture interpretation
knowledge graph construction
RAG
LLM interaction
AI explanation
diagram generation
report generation
frontend implementation
background scheduling
deployment infrastructure
```

If an M3 implementation begins requiring these concerns, the boundary must be reviewed rather than silently expanded.

---

# 7. Repository as a Project-Owned Resource

The authoritative relationship is:

```text
Project
   │
   └── Repository
```

Every Repository belongs to exactly one Project.

Repository authorization derives from that Project.

The conceptual authorization path is:

```text
Current User
     │
     ▼
Repository
     │
     ▼
repository.project_id
     │
     ▼
ProjectAuthorization
     │
     ▼
ProjectAccess
     │
     ▼
ProjectRole
```

M3 must not introduce Repository-level RBAC.

---

# 8. No Repository-Level RBAC

Do not introduce concepts such as:

```text
RepositoryAccess
RepositoryRole
RepositoryMember
RepositoryPermission
RepositoryAuthorizationPolicy
```

unless a future authoritative architecture decision explicitly introduces them.

Current Repository authorization is Project-derived.

For example:

```text
User has ProjectAccess to Project X
                  │
                  ▼
Repository R belongs to Project X
                  │
                  ▼
User's access to R is derived from Project X access
```

---

# 9. Repository Identity

M3 must provide a stable Repository identifier.

The Repository identifier must be suitable for:

```text
API references
database identity
foreign-key relationships
cross-module contracts
M4 acquisition references
future analysis references
auditability
```

The exact identifier type and fields must follow the authoritative architecture and implementation plan.

Do not introduce duplicate identifiers for different layers without a concrete requirement.

---

# 10. Repository Domain Model

The Repository domain model should represent **Repository identity and registration state**, not ingestion internals.

The model must distinguish:

```text
Repository identity
Project relationship
user-facing metadata
lifecycle state
timestamps
```

from later acquisition-specific data.

M3 must not add fields merely because they might eventually be useful to M4.

Only fields justified by the M3 contract belong in the M3 domain model.

---

# 11. Repository Metadata Boundary

M3 may own metadata required to register and identify a Repository.

M3 must not prematurely model:

```text
commit trees
source files
file hashes
snapshots
revisions
branches
clone paths
archive contents
discovered artifacts
analysis units
AST nodes
IR nodes
```

unless the authoritative M3 contract explicitly requires a specific field.

These concerns belong to later repository acquisition and analysis boundaries.

---

# 12. Project Relationship

Repository must contain a stable relationship to its owning Project.

Conceptually:

```text
Repository
    │
    └── project_id
```

The Project relationship must be persisted using the established database conventions.

A Repository must not exist without a valid Project relationship.

The database should enforce referential integrity where the architecture permits and requires it.

---

# 13. Repository Lifecycle

M3 owns the Repository's application-level lifecycle.

The lifecycle must represent meaningful Repository states defined by the architecture.

M3 must not invent lifecycle states solely for implementation convenience.

Lifecycle state should answer:

```text
What state is the Repository registration currently in?
```

It should not attempt to represent every M4 ingestion operation.

---

# 14. Lifecycle vs Acquisition State

M3 must maintain a clear distinction between:

```text
Repository registration lifecycle
```

and:

```text
Repository acquisition/ingestion execution
```

Conceptually:

```text
M3
Repository exists
Repository is registered
Repository is active/inactive according to contract
Repository metadata is maintained

M4
Repository acquisition begins
Repository content is obtained
Snapshot/revision is created
Files are discovered
Artifacts are stored
Ingestion progresses
```

M3 must not turn the Repository entity into an ingestion workflow engine.

---

# 15. Repository Creation

Repository creation is an application use case.

Conceptually:

```text
Create Repository
       │
       ├── validate request
       ├── resolve Project
       ├── authorize current user
       ├── construct Repository
       ├── persist Repository
       └── return Repository response
```

Authorization must occur before protected mutation.

The creation operation must not bypass ProjectAuthorization.

---

# 16. Repository Creation Authorization

The user creating a Repository must possess the Project capability required by the role matrix.

Under the current M2 role model:

```text
OWNER       → allowed
ADMIN       → allowed
DEVELOPER   → allowed
VIEWER      → denied
```

The implementation must use the established authorization abstraction rather than duplicating this matrix.

---

# 17. Repository Retrieval

Repository retrieval is Project-scoped.

The conceptual flow is:

```text
Repository ID
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
required read access
```

A Repository must not be returned to a user without the required Project access.

---

# 18. Repository Listing

Repository listing must be Project-scoped.

Conceptually:

```text
Project
   │
   ▼
Repositories belonging to Project
```

The API must not expose repositories belonging to other Projects.

Pagination should follow the established project API conventions.

Do not use unrestricted global repository listing as a user-facing operation unless explicitly required by architecture.

---

# 19. Repository Deletion

Repository deletion is a Project-scoped mutation.

The required permission is derived from the M2 role matrix.

Under the established matrix:

```text
OWNER       → delete allowed
ADMIN       → delete allowed
DEVELOPER   → delete denied
VIEWER      → delete denied
```

Deletion behavior must account for downstream relationships.

If M4 or later modules establish dependent resources that prevent or alter deletion semantics, the deletion contract must be resolved explicitly rather than assuming database cascade behavior.

---

# 20. Repository Update

Repository updates must be limited to fields M3 owns.

M3 must not allow clients to update internal acquisition state or future analysis state.

The update contract must explicitly define which metadata is mutable.

Do not expose persistence-model fields automatically through update DTOs.

---

# 21. Repository Persistence

M3 follows the established persistence architecture.

The expected separation is:

```text
Domain
   │
   ▼
Application
   │
   ▼
Repository Contract
   │
   ▼
Infrastructure Implementation
   │
   ▼
SQLAlchemy / PostgreSQL
```

Domain objects must not depend directly on SQLAlchemy persistence implementation.

---

# 22. Repository Contract

The Repository persistence contract should provide only operations required by M3 use cases.

Typical responsibilities include:

```text
save
get_by_id
list_by_project
update
delete
```

Additional operations should be introduced only when a concrete use case requires them.

Do not create generic repository methods merely because a CRUD repository template contains them.

---

# 23. Repository Mapping

Persistence models and domain models must remain appropriately separated.

Mapping responsibilities belong in the infrastructure/repository boundary.

Conceptually:

```text
SQLAlchemy Model
      │
      ▼
Repository Mapper
      │
      ▼
Domain Repository
```

Application services should not contain repetitive SQLAlchemy-to-domain mapping logic.

---

# 24. Transaction Behavior

M3 follows the M1/M2 transaction convention.

Repositories:

```text
persist
flush
return
```

They do not independently commit transactions.

Application services coordinate transactional use cases.

Do not introduce a Unit of Work abstraction mechanically.

---

# 25. Repository Creation Transaction

A Repository creation operation must have a clear transaction boundary.

At minimum:

```text
authorization
+
Repository persistence
```

must be treated as one application operation.

If additional M3-owned records are created as part of Repository registration, they should participate in the same appropriate transaction.

---

# 26. Repository Errors

M3 should define typed application errors for meaningful Repository failures.

Examples of conceptual categories include:

```text
RepositoryNotFound
RepositoryAccessDenied
RepositoryAlreadyExists
RepositoryInvalidState
RepositoryConflict
```

Exact error names and codes must follow the established error conventions and authoritative architecture.

Do not expose raw database exceptions through the API.

---

# 27. Not Found vs Access Denied

M3 must preserve the project's non-enumerating access behavior where required.

A user who lacks permission to access a Repository must not be able to use the API to infer protected Repository existence.

The exact HTTP/error mapping must follow the established application error contract.

---

# 28. DTO Layer

M3 should define explicit DTOs for application/API boundaries.

Typical categories include:

```text
CreateRepositoryRequest
UpdateRepositoryRequest
RepositoryResponse
RepositoryListResponse
```

Exact DTOs should be created only where the corresponding use cases exist.

DTOs must not expose internal persistence details.

---

# 29. DTO Validation

Input DTOs must validate:

```text
required fields
field lengths
allowed values
identifier formats
optional metadata
```

Validation should happen at the appropriate boundary.

Business rules that depend on persistence or authorization belong in the application/domain layer rather than being encoded entirely in Pydantic validation.

---

# 30. Application Service

The Repository application service owns Repository use-case orchestration.

Expected responsibility includes:

```text
authorize
load required Project/Repository data
construct domain objects
invoke domain behavior
invoke persistence contracts
map results to DTOs
coordinate transactions
```

It should not:

```text
perform raw SQL
contain HTTP-specific logic
clone repositories
parse source files
execute repository code
invoke LLMs
build architecture graphs
```

---

# 31. Dependency Injection

M3 services must receive infrastructure dependencies through dependency injection.

Examples include:

```text
RepositoryRepository
ProjectRepository
ProjectAuthorization
CurrentUserProvider
```

The exact dependency set should be driven by the use case.

Do not instantiate infrastructure implementations directly inside application services.

---

# 32. API Layer

M3's API layer must remain thin.

The router should:

```text
receive request
resolve dependencies
invoke service
translate successful result
```

It should not:

```text
perform authorization algorithms
construct SQLAlchemy models
implement transactions
perform persistence directly
contain Repository business rules
```

---

# 33. API Versioning

M3 APIs belong under:

```text
/api/v1/
```

Repository routes should remain consistent with the existing Project API hierarchy.

Conceptually:

```text
/api/v1/projects/{project_id}/repositories
```

Project-scoped nested routing should be preferred where it accurately expresses the resource relationship.

Exact route design must follow the authoritative M3 API contract and existing router conventions.

---

# 34. Repository API Isolation

Repository endpoints must always establish the Project boundary.

For nested routes:

```text
/api/v1/projects/{project_id}/repositories/{repository_id}
```

the implementation must verify that:

```text
repository.project_id == project_id
```

before returning or modifying the resource.

Do not trust a client-provided Project identifier without validating the persisted relationship.

---

# 35. Direct Repository Identifier APIs

If an API accepts only:

```text
repository_id
```

authorization must still resolve the Repository's owning Project.

Conceptually:

```text
repository_id
     │
     ▼
Repository
     │
     ▼
project_id
     │
     ▼
ProjectAuthorization
```

A Repository identifier does not itself establish authorization.

---

# 36. Database Schema

M3 requires a dedicated Repository persistence table.

The schema must contain the fields required by the authoritative Repository contract.

At minimum, the design must account for:

```text
Repository identity
Project foreign key
Repository metadata owned by M3
Repository lifecycle state where required
created timestamp
updated timestamp
```

Do not add M4-specific ingestion columns merely for future convenience.

---

# 37. Database Constraints

Database constraints should enforce invariants that belong at the persistence boundary.

Potential constraints include:

```text
primary key
foreign key to Project
non-null required fields
valid length constraints where appropriate
unique constraints only where the architecture requires uniqueness
```

Do not use database constraints to encode assumptions that belong to higher-level business policy unless appropriate.

---

# 38. Repository Naming and Uniqueness

Repository naming/identity semantics must follow the authoritative architecture.

Do not assume that:

```text
repository name globally unique
```

or:

```text
repository name unique within Project
```

unless the M3 contract explicitly requires it.

If uniqueness is required, enforce it at the database level as well as at the application level.

---

# 39. Migration

M3 must introduce a new migration.

M1/M2 migration history must remain untouched.

The migration should create the Repository schema required by M3.

Migration requirements:

```text
deterministic
reversible where supported
consistent with SQLAlchemy models
foreign-key correct
safe for existing M1/M2 data
```

---

# 40. Project Deletion Interaction

Project deletion must be considered when defining Repository foreign-key behavior.

Because Repository is Project-owned, the schema must have explicit deletion semantics.

The chosen behavior must be consistent with the authoritative architecture.

Do not casually introduce cascade deletion if later module resources make such deletion unsafe.

Do not casually block Project deletion either.

The behavior must be an explicit architectural contract.

---

# 41. Repository Lifecycle Integrity

M3 must prevent invalid lifecycle transitions where the architecture defines lifecycle semantics.

A transition should be treated as:

```text
current state
      +
requested transition
      ↓
valid / invalid
```

Invalid transitions should produce a typed application error.

Do not allow arbitrary state mutation simply because the database column accepts a string/enum.

---

# 42. Domain Rules

Domain behavior should contain rules intrinsic to Repository state.

Examples:

```text
valid lifecycle transitions
valid state-dependent operations
immutable identity
metadata invariants
```

Authorization remains an application boundary concern.

Database persistence remains an infrastructure concern.

---

# 43. Repository Immutability

Repository identity should be treated as stable.

A Repository's:

```text
id
project relationship
```

must not be casually changed through normal update operations.

Moving a Repository between Projects is not an ordinary metadata update.

If cross-Project movement is ever required, it must be explicitly designed as a separate operation with authorization and isolation implications.

---

# 44. No Project Reassignment by Default

M3 should not expose:

```text
update repository.project_id
```

as a generic update operation.

A Repository belongs to the Project in which it was registered.

Project reassignment would affect:

```text
authorization
isolation
access
downstream ingestion
history
references
```

and therefore requires an explicit architectural decision.

---

# 45. M4 Integration Contract

M4 consumes M3 Repository identity and lifecycle contracts.

The expected conceptual relationship is:

```text
M3
Repository
    │
    │ Repository ID
    ▼
M4
Acquisition / Ingestion
```

M4 should not create a second Repository identity model.

M4 should reference the M3 Repository.

---

# 46. M4 Does Not Redefine Repository

M4 must not:

```text
duplicate Repository domain model
duplicate Repository table
create independent Repository IDs
replace M3 Repository lifecycle
bypass Project authorization
create Repository-level RBAC
```

If M4 needs additional ingestion state, it should introduce its own appropriately bounded model.

---

# 47. M3 Does Not Inspect Repository Contents

M3 must not inspect:

```text
source files
directories
Git metadata
archives
build files
dependency manifests
ASTs
configuration files
```

M3 is responsible for the Repository **resource**, not its **contents**.

---

# 48. Security Boundary

Repository content is untrusted.

Although M3 does not acquire repository content, M3 must not create APIs or persistence behavior that assumes repository content is trusted.

M4 is responsible for safe acquisition and handling.

M3 should provide safe resource identity and authorization boundaries that M4 can rely upon.

---

# 49. Resource Isolation

Repository operations must maintain Project isolation.

A request must never allow:

```text
Project A user
      ↓
Repository belonging to Project B
```

through:

```text
crafted repository_id
crafted project_id
mixed route parameters
direct database lookup
```

Isolation must be tested explicitly.

---

# 50. Concurrency

Repository creation and mutation must account for concurrent requests.

If uniqueness constraints exist, the database remains the final concurrency authority.

The implementation should:

```text
attempt operation
→ rely on DB constraint
→ translate conflict
```

rather than assuming application-level pre-checks are sufficient.

---

# 51. Testing Strategy

M3 tests must cover:

```text
Repository domain behavior
Repository creation
Repository retrieval
Repository listing
Repository updates
Repository deletion
Project isolation
Project authorization
role matrix
not-found behavior
conflict behavior
persistence mapping
database constraints
transaction behavior
API contracts
migration behavior
regression against M1/M2
architecture/import rules
```

Tests should verify both allowed and denied paths.

---

# 52. Authorization Matrix Tests

At minimum, M3 authorization tests should verify:

| Operation | OWNER | ADMIN | DEVELOPER | VIEWER |
|---|---:|---:|---:|---:|
| Read Repository | Yes | Yes | Yes | Yes |
| Create Repository | Yes | Yes | Yes | No |
| Update Repository | Yes | Yes | Yes | No |
| Delete Repository | Yes | Yes | No | No |

These are derived from the existing Project role model.

Do not create a second Repository-specific role matrix.

---

# 53. Isolation Tests

M3 must test cross-Project isolation.

Example scenario:

```text
Project A
  └── Repository A

Project B
  └── Repository B
```

A user with access only to Project A must not be able to:

```text
retrieve Repository B
update Repository B
delete Repository B
list Repository B
```

The exact error behavior must follow the established API contract.

---

# 54. API Tests

API tests should verify:

```text
correct status codes
correct response DTOs
validation failures
authorization failures
not-found semantics
Project scoping
pagination
mutation behavior
error contracts
```

Tests must not rely only on unit-level mocks for security-critical behavior.

Integration tests should exercise actual persistence where appropriate.

---

# 55. Architecture Tests

M3 must preserve project architecture rules.

Tests should detect:

```text
relative imports
wrong module ownership
duplicate Repository models
forbidden Organization dependencies
Repository-level RBAC
M4 leakage
direct infrastructure dependencies in domain
router business logic
```

Architecture tests should protect boundaries rather than merely enforce filenames.

---

# 56. File and Package Structure

M3 should fit the existing module structure.

Where justified, the expected organization is conceptually:

```text
backend/
└── platform/
    └── repositories/
        ├── domain/
        ├── application/
        ├── repositories/
        └── infra/
```

Additional packages should be created only when justified by actual responsibilities and existing project conventions.

Do not mechanically create every layer if a component does not need one.

---

# 57. Naming Conventions

Follow established naming conventions.

Examples:

```text
Repository
RepositoryService
DefaultRepositoryService
RepositoryRepository
CreateRepositoryRequest
UpdateRepositoryRequest
RepositoryResponse
```

Avoid ambiguous names such as:

```text
Manager
Handler
Helper
Utils
CommonRepository
BaseManager
```

unless the responsibility is genuinely represented by that abstraction.

---

# 58. Dependency Direction

Preferred dependency direction:

```text
API
 │
 ▼
Application
 │
 ├── Domain
 │
 └── Contracts
       ▲
       │
Infrastructure
```

Infrastructure implements application/domain contracts.

Domain must not import:

```text
FastAPI
SQLAlchemy
HTTP request objects
LLM clients
filesystem acquisition implementations
```

unless an authoritative architectural requirement explicitly says otherwise.

---

# 59. Design Pattern Guidance

Use patterns when they solve concrete problems.

Potentially justified patterns include:

```text
Factory
Strategy
State
Adapter
Repository
Dependency Injection
```

But only where they improve:

```text
testability
extensibility
isolation
clarity
maintainability
```

Do not introduce a pattern merely to demonstrate design-pattern knowledge.

---

# 60. No Mechanical Abstraction

Avoid creating:

```text
GenericCRUDService
GenericRepository
BaseRepositoryForEverything
UniversalMapper
GenericManager
GenericController
```

unless a real shared behavior exists and abstraction materially improves the design.

M3 should optimize for clear domain boundaries, not abstraction count.

---

# 61. Observability

M3 should follow established observability conventions.

Where required, application operations should produce useful structured logs/telemetry without exposing:

```text
secrets
credentials
tokens
repository credentials
sensitive repository content
```

Observability should remain proportional to the actual M3 responsibility.

Do not add speculative monitoring infrastructure.

---

# 62. Performance

M3 should preserve reasonable API and database performance.

Avoid:

```text
N+1 queries
unbounded Project repository listing
unbounded Repository listing
repeated authorization queries when batching is possible
unnecessary serialization
```

Pagination must be used for collection APIs.

Performance optimizations should not bypass authorization boundaries.

---

# 63. API Pagination

Repository collection endpoints should follow the established pagination convention where applicable:

```text
limit
offset
```

The same safety expectations apply:

```text
limit >= 1
limit <= 100
offset >= 0
```

Default behavior should remain consistent with the existing Project APIs.

---

# 64. Validation vs Authorization

Keep these concerns separate.

Validation answers:

```text
Is this request structurally valid?
```

Authorization answers:

```text
Is this user allowed to perform this operation?
```

Persistence answers:

```text
Can this state be safely stored?
```

Domain behavior answers:

```text
Is this state transition valid?
```

Do not combine these concerns into one router or DTO.

---

# 65. Failure Classification

M3 should distinguish at least conceptually between:

```text
validation failure
authentication/identity failure
authorization failure
not found
conflict
invalid lifecycle transition
persistence failure
unexpected infrastructure failure
```

Typed errors should preserve stable machine-readable semantics.

---

# 66. No Raw Exception Leakage

Do not return:

```text
SQLAlchemy IntegrityError
database stack traces
filesystem exceptions
internal Python exceptions
```

directly to API clients.

Infrastructure failures must be translated at the appropriate application boundary.

---

# 67. API Contract Stability

Once M3 API contracts are established and consumed by downstream modules, changes must be treated as contract changes.

M4, M6, and M7 may depend on:

```text
Repository IDs
Repository DTOs
Repository lifecycle semantics
Repository API routes
Repository error codes
```

Therefore API changes must be deliberate and coordinated.

---

# 68. Cross-Module Contract

M3 must publish enough stable information for M4 to perform acquisition without redefining Repository identity.

At minimum, downstream consumers need to know:

```text
Repository ID
Project ID
Repository lifecycle/availability state
M3-owned metadata required for acquisition
```

The exact contract must follow the authoritative architecture.

---

# 69. M4 Input Boundary

M4 should consume M3 through application/domain contracts rather than reaching into M3 persistence implementation details.

Preferred:

```text
M4
 │
 ▼
M3 Repository Contract
```

Avoid:

```text
M4
 │
 └── directly imports M3 SQLAlchemy models
```

unless a concrete architectural decision explicitly requires shared persistence models.

---

# 70. M6 Input Boundary

M6 consumes M3 API/application contracts for:

```text
Repository creation
Repository listing
Repository details
Repository lifecycle display
```

M6 must not duplicate Repository business rules in frontend code.

Frontend validation may improve user experience, but backend validation and authorization remain authoritative.

---

# 71. M7 Responsibility

M7 validates that M3 integrates correctly with the rest of the platform.

M7 should verify:

```text
M1/M2 regression
M3 contracts
M4 integration
M5 identity integration
M6 API/frontend integration
migration chain
architecture rules
end-to-end vertical slice
```

M3 should provide enough tests and contracts for M7 to perform this integration verification.

---

# 72. Implementation Order

Recommended M3 implementation sequence:

```text
1. Re-read master.txt relevant Repository sections
2. Read M1-M2-CONTEXT.md
3. Inspect existing M1/M2 implementation
4. Confirm M3 architecture boundary
5. Define Repository domain model
6. Define lifecycle/state semantics
7. Define persistence model
8. Define Repository contract
9. Define migration
10. Implement repository infrastructure
11. Implement application service
12. Integrate ProjectAuthorization
13. Define DTOs
14. Implement API routes
15. Implement unit tests
16. Implement integration tests
17. Implement API tests
18. Run architecture checks
19. Run formatting/lint/type checks
20. Run full regression suite
21. Produce implementation report
```

Do not skip architecture verification because tests pass.

---

# 73. Definition of M3 Complete

M3 is complete only when:

```text
Repository domain exists
Repository persistence exists
Repository migration exists
Repository application contracts exist
Repository application service exists
Project authorization is integrated
Repository API exists
Repository DTOs are defined
Repository errors are typed
Project isolation is tested
Role authorization is tested
Persistence behavior is tested
API behavior is tested
M1/M2 regression passes
Architecture checks pass
Absolute imports are preserved
M4 boundary is preserved
No Repository RBAC exists
No Organization hierarchy exists
No Project.owner_id exists
No ingestion logic leaked into M3
Code is formatted/linted/type-checked
Vertical Repository workflow works
```

---

# 74. M3 Completion Report

At the end of implementation, the Builder should report:

```text
Implemented:
- ...

Files added:
- ...

Files changed:
- ...

Database:
- ...

API:
- ...

Authorization:
- ...

Tests:
- ...

Architecture verification:
- ...

M4 boundary verification:
- ...

Known limitations:
- ...

Commands executed:
- ...

Result:
- ...
```

The report must distinguish:

```text
implemented
verified
not implemented
blocked
```

Do not claim verification that was not actually performed.

---

# 75. Independent Review Requirements

After implementation, the independent reviewer must audit M3 without relying on the Builder's conclusions.

The reviewer must independently inspect:

```text
architecture compliance
M1/M2 integration
Repository domain correctness
Project relationship
authorization
Project isolation
database schema
migration correctness
service boundaries
dependency inversion
API contracts
error handling
tests
M4 boundary
security
regression
```

The reviewer must not silently modify code.

---

# 76. Reviewer Decision Vocabulary

The independent review may conclude:

```text
PASS
PASS WITH NON-BLOCKING FINDINGS
CHANGES REQUIRED
```

Findings use:

```text
BLOCKER
MAJOR
MINOR
OBSERVATION
```

Every finding must contain evidence.

The reviewer must not replace evidence with subjective architectural preference.

---

# 77. Forbidden M3 Outcomes

M3 implementation is invalid if it introduces:

```text
Organization
Project.owner_id
Repository RBAC
RepositoryAccess
RepositoryRole
M4 ingestion inside M3
source parsing inside M3
AI inside M3
knowledge graph inside M3
direct repository content execution
relative imports
duplicate CurrentUserProvider
duplicate ProjectAuthorization
duplicate ProjectAccess model
direct database access from routers
raw SQL in domain services
silent M1/M2 modifications
historical migration rewrites
unbounded user-facing repository listing
cross-Project repository access
```

---

# 78. Final M3 Contract

The M3 module can be summarized as:

```text
M3 = Repository Platform

Owns:
    Repository identity
    Repository registration
    Repository lifecycle
    Repository persistence
    Repository application contracts
    Repository API
    Project-scoped authorization integration
    Repository tests

Consumes:
    Project
    ProjectAccess
    ProjectRole
    CurrentUserProvider
    ProjectAuthorization
    M1/M2 error and transaction conventions

Provides:
    Repository identity
    Repository persistence contract
    Repository application contract
    Repository API contract
    Repository lifecycle contract

Does not own:
    acquisition
    ingestion
    snapshots
    revisions
    artifact inventory
    source parsing
    analysis
    knowledge
    AI
    diagrams
    reports
    frontend
```

---

# 79. Non-Negotiable Rules

```text
1. master.txt remains the ultimate authority.

2. M1 and M2 are frozen.

3. Project is the ownership boundary.

4. Organization must not be reintroduced.

5. Project.owner_id must not be reintroduced.

6. Repository access derives from ProjectAccess.

7. Repository-level RBAC must not be introduced.

8. M3 owns Repository registration and lifecycle.

9. M4 owns acquisition and ingestion.

10. M3 must not inspect or interpret repository contents.

11. Repository content is untrusted.

12. Absolute imports are mandatory.

13. Application services must use dependency injection.

14. Routers remain thin.

15. Domain must remain independent from infrastructure.

16. Repositories flush but do not own transaction commits.

17. Existing migrations must not be rewritten.

18. Cross-Project access must be impossible.

19. API contracts must use explicit DTOs.

20. Errors must be typed and centrally translated.

21. Tests must verify architecture as well as functionality.

22. No silent architecture changes are permitted.
```

---

# 80. Final Boundary Diagram

```text
                         MASTER ARCHITECTURE
                                │
                                ▼
                    ┌─────────────────────┐
                    │     M1 + M2         │
                    │  Frozen Foundation  │
                    └──────────┬──────────┘
                               │
                     Project + Authorization
                               │
                               ▼
                    ┌─────────────────────┐
                    │        M3           │
                    │ Repository Platform │
                    │                     │
                    │ Identity            │
                    │ Registration        │
                    │ Lifecycle           │
                    │ Persistence         │
                    │ Application         │
                    │ API                 │
                    └──────────┬──────────┘
                               │
                         Repository ID
                         + stable contract
                               │
                               ▼
                    ┌─────────────────────┐
                    │        M4           │
                    │ Acquisition/Ingest  │
                    │                     │
                    │ Fetch               │
                    │ Validate            │
                    │ Snapshot            │
                    │ Revision            │
                    │ Inventory           │
                    │ Safe Storage        │
                    └─────────────────────┘
```

M3 exists to make the Repository a stable, authorized, persistent Project-owned resource while preserving a strict boundary between **Repository management** and **Repository content acquisition/analysis**.