# Context Authority

> This file is an operational context artifact for the StackSense agent workflow.
> It does **not** replace or override `master.txt`.
> `master.txt` remains the sole architectural source of truth.

## Authority Order

1. System / Developer instructions
2. Current authoritative `master.txt`
3. Explicitly approved architectural decisions
4. This shared context
5. Existing implementation

If this file conflicts with the current `master.txt`, treat `master.txt` as authoritative. Do not silently reconcile or modify the architecture.

## Purpose

This file provides the shared implementation context for the frozen M1 and M2 foundations so downstream modules can integrate with them without reconstructing their contracts from the full architecture document.

## Scope

This context covers:

- M1 and M2 responsibilities
- Frozen domain and application contracts
- Shared persistence contracts
- Authorization contracts
- Identity/current-user contracts
- Error contracts
- API conventions
- Testing expectations
- Integration constraints for downstream modules

## Frozen Foundation Rule

M1 and M2 are frozen foundations.

Downstream modules must integrate with their existing contracts and must not casually modify, replace, or reinterpret them.

Any required architectural change must follow the architecture change process defined by `master.txt`.

## Boundary Rule

This file does not authorize new responsibilities for M1 or M2.

Downstream modules must not introduce:

- Organization as a first-class hierarchy
- Repository-level RBAC
- Project ownership fields that contradict the frozen model
- Cross-module responsibilities that belong to later modules


# M1–M2 Shared Context

**Location:** `.agents/context/shared/M1-M2-CONTEXT.md`

**Status:** FROZEN  
**Purpose:** Shared downstream context for all modules built after M2.

---

## 1. Purpose

This document captures the implementation-relevant contracts and architectural decisions established by Modules 1 and 2.

It is a **downstream context document**, not a replacement for `master.txt`.

The architectural authority remains:

```text
master.txt
```

Agents must use this document to understand the stable M1–M2 foundation without repeatedly reconstructing it from implementation details.

If this document conflicts with `master.txt`, `master.txt` is authoritative.

If a downstream implementation appears to require changing a frozen M1–M2 decision, the agent must stop and report the conflict rather than silently modifying the foundation.

---

# 2. Architectural Hierarchy

The current authoritative ownership hierarchy is:

```text
User
  │
  └── Project
        │
        └── Repository
```

## 2.1 Project is the primary boundary

Project is the primary boundary for:

- ownership
- collaboration
- authorization
- access control
- isolation
- repository association

Repository access is derived through the owning Project.

## 2.2 Organization is not part of the current hierarchy

The current architecture does **not** contain Organization as a first-class ownership boundary.

Do not introduce:

```text
Organization
    └── Project
```

Do not add organization entities, organization foreign keys, organization-level authorization, or organization-scoped APIs unless a future architectural decision explicitly introduces them.

Older organization-oriented material elsewhere in the architecture is historical/superseded where it conflicts with the current baseline.

---

# 3. M1 Foundation

M1 established the initial Project platform foundation.

M1 is frozen.

Downstream modules must integrate with the existing contracts rather than redesigning them.

---

# 4. Project Domain

The Project domain model is:

```text
Project
├── id: UUID
├── name: str
├── description: str | None
├── created_at: datetime
└── updated_at: datetime
```

The Project domain does **not** contain:

```text
owner_id
```

Ownership is represented through ProjectAccess.

Do not reintroduce `owner_id` into Project.

---

# 5. Project Persistence

The `projects` table contains:

```text
id            UUID            PRIMARY KEY
name          VARCHAR(255)
description   VARCHAR(2000)   NULLABLE
created_at    TIMESTAMPTZ
updated_at    TIMESTAMPTZ
```

Important constraints:

- no `owner_id` column
- no Project name uniqueness requirement
- hard delete is supported
- timestamps are persisted
- Project identity is UUID-based

Downstream modules must not assume additional Project fields unless they are explicitly introduced by architecture.

---

# 6. Project Access Model

M1/M2 established ProjectAccess as the access-control boundary.

The conceptual model is:

```text
Project
   │
   └── ProjectAccess
          ├── project_id
          ├── user_id
          └── role
```

A ProjectAccess record grants one user a role within one Project.

---

# 7. ProjectAccess Persistence

The `project_access` table uses:

```text
PRIMARY KEY (project_id, user_id)
```

It contains:

```text
project_id
user_id
role
```

ProjectAccess has:

- foreign key from `project_id` → `projects.id`
- `ON DELETE CASCADE` for the Project relationship
- no database foreign key to User in the current implementation
- index on `user_id`

The composite primary key prevents duplicate ProjectAccess records for the same:

```text
(project_id, user_id)
```

---

# 8. Project Roles

The authoritative Project roles are:

```text
OWNER
ADMIN
DEVELOPER
VIEWER
```

They are represented using the project's `ProjectRole` string enum.

---

# 9. Project Role Matrix

The current permission model is:

| Capability | OWNER | ADMIN | DEVELOPER | VIEWER |
|---|---:|---:|---:|---:|
| Read Project | Yes | Yes | Yes | Yes |
| Create Project resources | Yes | Yes | Yes | No |
| Update Project resources | Yes | Yes | Yes | No |
| Delete Project resources | Yes | Yes | No | No |
| Manage Project membership | Yes | Yes | No | No |

This matrix is the basis for downstream Project-scoped authorization.

Do not invent an independent authorization model for Repository or other Project-owned resources.

---

# 10. ProjectAccess Domain Contract

ProjectAccess is represented conceptually as an immutable value:

```text
ProjectAccess
├── project_id: UUID
├── user_id: UUID
└── role: ProjectRole
```

The domain representation is immutable.

---

# 11. ProjectAccess Lifecycle

Supported operations include:

```text
grant access
retrieve access
list project members
list user's projects
update role
revoke access
```

Duplicate membership grants are treated as a conflict.

Missing membership during operations that require an existing membership is represented as a typed application error.

---

# 12. Project Access Repository Contract

The access repository supports operations equivalent to:

```text
save(...)
get(...)
list_for_project(...)
list_for_user(...)
update_role(...)
delete(...)
```

Repository responsibilities:

- persistence
- retrieval
- mapping persistence ↔ domain
- enforcing persistence-level integrity handling

Repository responsibilities do **not** include:

- HTTP concerns
- authorization policy
- business orchestration
- API response formatting

Repositories flush persistence changes but do not own transaction commits.

---

# 13. Project Repository Contract

The Project repository provides persistence operations equivalent to:

```text
save(...)
get_by_id(...)
list_all(...)
delete(...)
```

Important distinction:

```text
ProjectRepository.list_all()
```

is an internal repository operation.

User-facing Project listing is **access-scoped** and must use ProjectAccess.

A user must not receive Projects merely because they exist in the database.

---

# 14. User-Scoped Project Listing

User-facing Project listing follows:

```text
ProjectAccess
      │
      ▼
Projects accessible to user
```

The access repository provides:

```text
list_for_user(user_id, limit, offset)
```

Current pagination rules:

```text
limit >= 1
limit <= 100
default limit = 50
offset >= 0
```

The user-facing API must not use unrestricted ProjectRepository listing to determine accessible Projects.

---

# 15. Project Authorization

Authorization is centralized through:

```text
ProjectAuthorization
```

The authorization component provides operations conceptually equivalent to:

```text
get_access(...)
require_access(...)
require_create_access(...)
require_update_access(...)
require_delete_access(...)
require_manage_access(...)
```

Its responsibility is to translate:

```text
current user
    +
project
    +
required capability
```

into an authorization decision.

Downstream Project-owned modules must reuse this mechanism.

They must not independently query ProjectAccess and reproduce the role matrix unless a concrete architectural contract explicitly requires otherwise.

---

# 16. Authorization Semantics

The authorization flow is conceptually:

```text
Current User
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

Unauthorized access to a Project-scoped resource must not leak whether a resource exists when the API contract intentionally uses non-enumerating behavior.

For Project retrieval and similar access-controlled operations, unauthorized access is represented as an appropriate access-denied/not-found contract according to the established API behavior.

---

# 17. Current User Contract

Identity is represented to downstream application code through:

```text
CurrentUserProvider
```

Location:

```text
backend/platform/identity/application/current_user.py
```

The provider is an abstract contract.

The current implementation includes:

```text
StaticCurrentUserProvider
```

for the temporary identity mechanism and tests.

Application services should depend on the provider abstraction rather than directly depending on the temporary implementation.

---

# 18. Dependency Injection

Current-user resolution is provided through the established dependency mechanism:

```text
get_current_user_provider(...)
get_current_user(...)
```

Tests may override the provider using:

```text
StaticCurrentUserProvider(user_id)
```

Downstream modules must preserve dependency inversion.

Do not hard-code a concrete identity implementation into domain or application services.

---

# 19. API Conventions

The primary API namespace is:

```text
/api/v1/
```

Project endpoints are Project-scoped.

The API layer should remain thin.

Routers are responsible for:

- request parsing
- dependency resolution
- invoking application services
- returning API responses

Routers should not contain:

- database orchestration
- authorization algorithms
- domain business logic
- persistence mapping

---

# 20. DTO Conventions

Application/API DTOs use explicit Pydantic models.

DTOs should represent API/application contracts rather than persistence models.

Existing naming follows patterns such as:

```text
CreateProjectRequest
ProjectResponse
```

Downstream DTOs should follow the same explicit naming convention.

Do not expose SQLAlchemy persistence models directly as API contracts.

---

# 21. Application Service Conventions

Application services orchestrate use cases.

The established naming convention is:

```text
<Name>Service
Default<Name>Service
```

For example:

```text
ProjectService
DefaultProjectService
```

Services may coordinate:

- authorization
- repositories
- domain objects
- transactions
- DTO mapping

They should not absorb unrelated infrastructure responsibilities.

---

# 22. Transaction Boundary

M1/M2 use the existing SQLAlchemy transaction mechanism.

Application-level operations that modify multiple related records must execute within the appropriate transaction boundary.

For example, Project creation coordinates:

```text
Project creation
        +
OWNER ProjectAccess grant
```

as one transactional operation.

Repositories flush changes but do not independently commit the transaction.

Do not introduce a Unit of Work abstraction mechanically.

Introduce additional transaction abstractions only if a concrete architectural requirement establishes the need.

---

# 23. Error Contract

The project uses typed application errors and centralized error handling.

Examples include:

```text
ProjectAccessDeniedError
ProjectAccessAlreadyExistsError
ProjectAccessNotFoundError
```

Errors carry stable machine-readable codes and categories.

Example categories include:

```text
AUTHORIZATION
```

HTTP translation is centralized rather than duplicated across routers.

Downstream modules should define typed application errors for meaningful domain/application failure cases instead of returning arbitrary error dictionaries from services.

---

# 24. Access Conflict Semantics

A duplicate ProjectAccess grant is a conflict.

The persistence layer protects against concurrent duplicate creation using the database composite primary key.

An integrity violation is translated into the appropriate application-level conflict error.

Do not rely solely on:

```text
check then insert
```

for uniqueness.

Database constraints remain authoritative for concurrent writes.

---

# 25. Project API Surface

The established Project API includes operations conceptually equivalent to:

```text
POST   /api/v1/projects
GET    /api/v1/projects
GET    /api/v1/projects/{project_id}
DELETE /api/v1/projects/{project_id}
```

ProjectAccess is exposed through a Project-scoped access API conceptually equivalent to:

```text
/projects/{project_id}/access
```

supporting:

```text
grant
list
update role
revoke
```

The exact existing router implementation is authoritative for spelling and response details.

Downstream modules must inspect existing code before adding related routes.

---

# 26. Repository Ownership and Authorization

Repository belongs to a Project.

The authorization relationship is:

```text
User
 │
 ▼
ProjectAccess
 │
 ▼
Project
 │
 ▼
Repository
```

There is **no independent Repository RBAC model** in M1/M2.

Do not create:

```text
RepositoryAccess
RepositoryRole
RepositoryMember
```

or equivalent authorization systems unless a future architecture decision explicitly introduces them.

---

# 27. Repository Direct Access

When a downstream module receives a Repository identifier directly, authorization must resolve:

```text
repository
    ↓
repository.project_id
    ↓
ProjectAuthorization
    ↓
current user's ProjectAccess
    ↓
required capability
```

Repository ownership does not bypass Project authorization.

---

# 28. M1/M2 Frozen Boundaries

Downstream modules must treat the following as frozen:

```text
Project identity model
Project fields
ProjectAccess model
ProjectRole values
Project role matrix
CurrentUserProvider abstraction
ProjectAuthorization mechanism
Project-scoped authorization model
Project ownership hierarchy
API versioning convention
Repository transaction conventions
Absolute import convention
Typed application error approach
```

Changing these requires an explicit architectural decision.

---

# 29. What M1/M2 Do Not Own

M1/M2 do not own the following concerns:

```text
Repository acquisition
Repository connection handling
Repository upload handling
Repository snapshot creation
Repository revision management
Repository file discovery
Repository artifact inventory
Safe repository storage
Repository resource limits
Repository content validation
Repository parsing
Source-code analysis
Architecture interpretation
IR construction
Knowledge graph construction
RAG
AI explanation
Diagram generation
Report generation
Frontend implementation
Background scheduling
Deployment infrastructure
```

Those responsibilities belong to later modules according to the architecture.

---

# 30. M3 Boundary

M3 builds the Repository platform on top of the M1/M2 foundation.

M3 owns Repository:

```text
domain
registration
lifecycle
persistence
contracts
application services
DTOs
Project relationship
Project-scoped authorization
API
tests
```

M3 establishes the Repository object and its application-level lifecycle/registration semantics.

M3 does **not** own repository acquisition/ingestion internals.

---

# 31. M4 Boundary

M4 owns Repository acquisition and ingestion concerns, including areas such as:

```text
repository acquisition
ingestion
validation
snapshot
revision
artifact inventory
safe storage
resource limits
untrusted repository handling
```

M4 must integrate with the Repository contracts established by M3.

M3 must not absorb M4's ingestion responsibilities merely because they involve Repository data.

---

# 32. Critical M3/M4 Boundary

The boundary is:

```text
M3
Repository identity + registration + lifecycle + persistence + application contracts
                              │
                              ▼
M4
Acquisition + ingestion + validation + snapshot + revision + artifact inventory + storage
```

M3 must not implement:

```text
git clone
repository download
archive extraction
filesystem ingestion
source discovery
snapshot processing
revision ingestion
artifact indexing
```

unless explicitly required by the M3 contract.

M4 must not redefine Repository identity or bypass M3's Repository contracts.

---

# 33. Repository Content Is Untrusted

Repository contents must be treated as untrusted input.

The architecture requires safe handling of repository data.

Do not introduce arbitrary code execution while implementing Repository acquisition or related workflows.

M3 should therefore model and persist Repository state without interpreting repository contents.

---

# 34. Migration Rules

M1/M2 migration history is frozen.

Existing migrations must not be rewritten to accommodate downstream modules.

M3 must introduce its own migration(s).

Do not:

- edit historical migration files
- squash existing M1/M2 migrations
- rewrite migration history
- recreate previous tables unnecessarily

If schema evolution requires correction, create a new migration.

---

# 35. Existing Migration History

The established M1/M2 migration sequence includes:

```text
efcb63702631
    initial projects

d270d0bce7f6
    ProjectAccess / temporary ownership state

bf1b64e1ccdd
    removed ownership column

64ab0e257e77
    user_id index
```

These historical migrations are not to be rewritten.

The resulting current schema is authoritative.

---

# 36. Import Convention

The project uses absolute imports from the repository root.

Preferred:

```python
from backend.platform.projects.domain.models import Project
```

Avoid relative imports such as:

```python
from .models import Project
```

or:

```python
from ..domain.models import Project
```

This convention applies to downstream modules.

---

# 37. Architecture Layering

The project uses explicit architectural boundaries.

The relevant layers include:

```text
Presentation / API
        │
        ▼
Application
        │
        ▼
Domain / Core
        │
        ▼
Infrastructure
```

Repositories and infrastructure implementations remain behind application/domain contracts where dependency inversion requires it.

The exact placement of a component must follow the existing architecture and module structure.

Do not create layers mechanically.

---

# 38. Existing Code Before New Code

Before implementing downstream functionality, agents must inspect:

```text
existing domain models
existing repositories
existing services
existing DTOs
existing dependency registration
existing authorization
existing error handling
existing migrations
existing routers
existing tests
```

Do not recreate functionality that already exists.

Do not introduce duplicate abstractions because an existing contract was not discovered.

---

# 39. Design Principles

All downstream implementation must preserve:

- SOLID
- high cohesion
- low coupling
- dependency inversion
- dependency injection
- explicit contracts
- testability
- clear ownership boundaries
- deterministic behavior where required
- production-grade error handling
- secure persistence and API behavior

Design patterns should be introduced only where they solve a concrete problem.

Do not use patterns for decoration.

---

# 40. Forbidden Architectural Drift

Downstream agents must not introduce the following without explicit architectural approval:

```text
Organization hierarchy
Project.owner_id
Repository-level RBAC
duplicate authorization systems
duplicate identity systems
mechanical Unit of Work
CQRS without concrete need
event sourcing without concrete need
unnecessary service/repository abstractions
direct infrastructure dependencies in domain logic
relative imports
M4 ingestion logic inside M3
analysis logic inside M3/M4
LLM logic inside M1/M2/M3
silent changes to frozen contracts
```

---

# 41. Security Expectations

All downstream Project-owned functionality must preserve:

```text
authorization before protected mutation
Project isolation
non-enumerating access behavior where required
typed authorization errors
safe transaction boundaries
database constraint enforcement
validated API input
no accidental secret exposure
no trust of repository content
```

Security decisions must follow `master.txt`.

---

# 42. Testing Expectations

M1/M2 establish that downstream work must verify more than happy-path functionality.

Relevant categories include:

```text
unit tests
integration tests
authorization tests
isolation tests
persistence tests
API contract tests
migration tests
architecture/import tests
regression tests
```

For Project-owned resources, tests should verify that users cannot access resources outside Projects for which they have appropriate ProjectAccess.

---

# 43. Regression Rule

M1/M2 behavior is a regression boundary.

Downstream changes must not break:

```text
Project creation
Project retrieval
Project listing isolation
Project deletion
ProjectAccess lifecycle
role authorization
CurrentUserProvider injection
typed error handling
database persistence
existing API contracts
```

If a downstream implementation requires breaking one of these, the agent must report the architectural conflict instead of silently changing the contract.

---

# 44. Agent Operating Rule

Agents working on downstream modules must treat this document as:

```text
stable context
+
integration contract
+
boundary reference
```

They must still consult:

```text
master.txt
```

for complete architectural meaning.

This file does not authorize deviations from the architecture.

---

# 45. Conflict Resolution

If an implementation requirement conflicts with this context:

```text
1. Stop implementation of the conflicting portion.
2. Identify the exact conflict.
3. Check master.txt.
4. Determine whether the conflict is already resolved by a later authoritative decision.
5. If not resolved, surface the architectural decision required.
6. Do not silently modify the architecture.
7. Do not silently modify frozen M1/M2 behavior.
```

Architecture changes require explicit approval and appropriate architecture/ADR updates before implementation.

---

# 46. Downstream Module Dependency

The intended dependency progression is:

```text
M1
 │
 ▼
M2
 │
 ▼
M3
 │
 ├──────────────► M4
 │
 ├──────────────► M5
 │
 ├──────────────► M6
 │
 └──────────────► M7
```

M3–M7 may be developed in parallel where their contracts permit it, but shared contracts and boundaries must be established before implementation.

---

# 47. Final Contract

For all downstream modules:

```text
Project is the ownership boundary.
ProjectAccess is the access boundary.
ProjectRole is the authorization role model.
ProjectAuthorization is the authorization mechanism.
CurrentUserProvider is the identity application contract.
Repository access derives from ProjectAccess.
Organization is not part of the current hierarchy.
Project.owner_id does not exist.
M1/M2 migrations are frozen.
M1/M2 contracts are frozen.
M3 owns Repository registration/lifecycle/persistence/contracts.
M4 owns Repository acquisition/ingestion.
Repository contents are untrusted.
Absolute imports are mandatory.
Architecture changes require explicit approval.
master.txt remains the ultimate source of truth.
```