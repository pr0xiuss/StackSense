---
name: module-planning
description: Create implementation-ready plans for StackSense modules by translating the authoritative architecture into responsibilities, components, contracts, dependencies, implementation order, tests, and verification without redefining architecture.
---

# Module Planning Skill

## Purpose

Create a production-quality implementation plan before significant code changes.

The planning flow is:

```text
Architecture
    ↓
Responsibilities
    ↓
Components
    ↓
Dependencies
    ↓
Contracts
    ↓
Implementation Order
    ↓
Tests
    ↓
Verification
```

The plan is a design artifact, not an opportunity to redefine architecture.

---

## 1. Planning Authority

Plans must be based on:

1. current `master.txt`
2. explicit superseding architectural decisions
3. active phase and module scope
4. frozen predecessor contracts
5. existing repository implementation
6. established project conventions

Do not design from the module name alone.

Do not use superseded historical architecture as current authority.

Do not invent requirements unsupported by the architecture or approved scope.

---

## 2. Understand Before Designing

Before planning, establish:

- current architecture and baseline
- active phase and module
- module objective and responsibilities
- explicit exclusions
- frozen modules
- existing implementation
- relevant contracts
- upstream and downstream dependencies
- persistence ownership
- authorization requirements
- security boundaries
- testing requirements
- verification requirements

Inspect existing code before proposing new components.

Extend the existing architecture; do not create a parallel architecture.

---

## 3. Planning Questions

Answer these before designing:

```text
What problem does this module solve?

What responsibilities belong to it?

What responsibilities do not belong to it?

What state does it own?

What state belongs elsewhere?

What contracts does it consume?

What contracts does it expose?

What persistence does it require?

What authorization does it require?

What external systems does it depend on?

What security boundaries apply?

How will it be tested?

How will it be independently verified?
```

If the architecture does not answer an essential question, record it as an open question instead of inventing an answer.

---

## 4. Responsibility Mapping

Map responsibilities before creating classes.

For each responsibility:

```text
Responsibility:
Owner:
Layer:
Inputs:
Outputs:
Dependencies:
Persistence:
Authorization:
Failure behavior:
Tests:
```

Every responsibility must have one clear owner.

Do not duplicate ownership across modules.

---

## 5. Component Identification

Identify only required components.

Possible categories:

- domain entities
- value objects
- domain services
- application services
- DTOs
- repository contracts
- repository implementations
- persistence models
- mappers
- routers
- API dependencies
- authorization components
- configuration
- DI registrations
- tests

Do not mechanically create every category.

Every component must have a concrete responsibility.

---

## 6. Component Justification

For every significant component:

```text
Component:
Responsibility:
Why it exists:
Why this layer owns it:
Dependencies:
Consumers:
Tests:
```

Remove components that have no clear responsibility.

Do not create classes merely because a layer exists in an architecture diagram.

---

## 7. Domain Design

Identify domain concepts before persistence concepts.

Determine:

- entities
- value objects
- identifiers
- lifecycle state
- invariants
- state transitions
- domain behavior

Do not design database tables first and treat them as the domain model.

Domain concepts must represent the business concepts defined by the architecture.

---

## 8. Domain Services

Use a domain service only when logic:

- is genuinely domain behavior
- does not naturally belong to an entity/value object
- coordinates multiple domain concepts

Application orchestration belongs in the application layer.

Infrastructure operations belong in infrastructure.

Do not create domain services merely because service classes are common.

---

## 9. Application Design

For each use case:

```text
Use Case:
Input:
Authorization:
Validation:
Domain operations:
Contracts used:
Persistence:
Transaction:
Output:
Failure modes:
Tests:
```

Application services orchestrate use cases without absorbing infrastructure details.

Prefer cohesive use-case orchestration over one large service containing unrelated behavior.

---

## 10. DTO Design

For each required DTO:

```text
Name:
Purpose:
Fields:
Validation:
Source:
Consumer:
Output mapping:
```

Rules:

- DTOs must not expose persistence models directly.
- Do not add speculative fields.
- Do not include fields owned by another module without an explicit contract.
- DTOs must represent actual application/API boundaries.

---

## 11. Contract Design

Identify contracts before implementation.

Possible contracts:

- application service interfaces
- repository interfaces
- authorization contracts
- external service interfaces
- module-to-module contracts

For each:

```text
Contract:
Owner:
Consumer:
Operations:
Inputs:
Outputs:
Failure semantics:
Transaction expectations:
Authorization expectations:
```

Contracts must be stable enough for consumers without becoming speculative abstractions.

---

## 12. Dependency Analysis

For every significant dependency ask:

- Who owns the responsibility?
- Who should depend on whom?
- Is abstraction necessary?
- Does Dependency Inversion apply?
- Can the dependency be injected?
- Does it create unwanted coupling?
- Does it cross a module boundary?
- Is the dependency frozen?
- Is it owned by another phase?

Make dependency direction explicit.

---

## 13. Dependency Direction

Prefer the established architectural direction:

```text
Presentation / API
        ↓
Application
        ↓
Domain / Contracts
        ↑
Infrastructure implementations
```

The exact graph must follow `master.txt`.

Avoid invalid dependencies such as:

```text
Domain → SQLAlchemy
Domain → FastAPI
Domain → HTTP
Domain → Infrastructure client
```

when they violate the architectural boundary.

---

## 14. Dependency Injection

For each meaningful injectable dependency:

```text
Abstraction:
Concrete implementation:
Composition location:
Runtime consumer:
Test override:
```

Typical candidates:

- repositories
- services
- current-user provider
- authorization components
- external clients

Do not create DI providers without meaningful variation or testing value.

---

## 15. SOLID Analysis

Consider SOLID during planning.

**SRP**

For every component: what single coherent responsibility does it own?

Split unrelated responsibilities, but do not create artificial micro-classes.

**OCP**

Identify real expected variation.

Do not build speculative plugin systems.

**LSP**

For interfaces with multiple implementations, verify that all implementations satisfy the same behavioral contract.

**ISP**

Keep interfaces focused on consumer needs.

Avoid giant contracts containing unrelated operations.

**DIP**

Protect high-level policies from unnecessary dependency on:

- databases
- frameworks
- external services
- infrastructure implementations

Introduce abstractions only where justified.

---

## 16. Design Pattern Analysis

Start with:

```text
What design problem exists?
```

Not:

```text
Which pattern should I use?
```

Consider creational, structural, and behavioral patterns only when an actual design problem justifies them.

Examples:

**Creational:**

- Factory
- Builder
- Abstract Factory

**Structural:**

- Adapter
- Facade
- Decorator
- Composite
- Proxy

**Behavioral:**

- Strategy
- State
- Command
- Chain of Responsibility
- Observer
- Mediator

Do not use patterns for appearance, portfolio value, or ceremony.

---

## 17. Pattern Decision

For every non-trivial pattern:

```text
Pattern:
Problem:
Why this pattern:
Why simpler composition is insufficient:
Alternatives considered:
Expected benefit:
Complexity introduced:
```

If the pattern does not clearly improve the design, remove it.

---

## 18. Folder and File Structure

Prefer the existing StackSense structure where appropriate:

```text
module/
├── domain/
├── application/
│   └── dto/
├── infra/
└── repositories/
```

Adapt this to the existing repository structure.

Do not mechanically duplicate folders.

For significant files, specify:

```text
Path:
Purpose:
Contains:
Depends on:
Consumed by:
Tests:
```

Avoid empty or speculative folders/files.

---

## 19. M3 Planning

When planning M3, explicitly cover:

**Domain**

Repository identity, project relationship, lifecycle behavior, and other repository-registration concepts defined by the architecture.

**Application**

Repository registration and related use cases coordinating:

- authorization
- validation
- domain behavior
- persistence contracts
- transaction boundaries

**DTO**

Required application/API request and response contracts.

**Repository Contracts**

Persistence abstractions only where dependency inversion genuinely requires them.

**Infrastructure**

Concrete database persistence.

**API**

Project-scoped repository registration and required repository-management endpoints.

**DI**

Composition of contracts with concrete implementations.

**Tests**

Plan:

- domain tests
- application tests
- authorization tests
- persistence tests
- API tests
- isolation tests
- migration tests
- architecture tests
- regression tests

---

## 20. M3 Authorization

Repository authorization derives from Project access.

Plan:

```text
Current User
    ↓
Repository
    ↓
project_id
    ↓
ProjectAuthorization
    ↓
ProjectAccess
    ↓
Permission Decision
```

Do not create Repository-specific RBAC.

Do not introduce:

- RepositoryRole
- RepositoryAccess
- RepositoryMembership

unless explicitly required by the authoritative architecture.

---

## 21. M3 / M4 Boundary

Keep these responsibilities separate.

**M3 — Repository Registration**

M3 may own:

- repository identity
- project relationship
- registration
- registration metadata
- lifecycle
- persistence
- authorization
- registration API

**M4 — Repository Acquisition / Ingestion**

M4 owns:

- source acquisition
- ingestion
- validation
- safe storage
- file discovery
- snapshot/revision acquisition
- artifact inventory
- ingestion workers
- resource controls

Do not allow M3 planning to absorb M4 responsibilities.

---

## 22. M3 / Analysis Boundary

M3 planning must explicitly exclude:

- parsing
- symbol extraction
- dependency extraction
- architecture inference
- analysis findings
- recommendation generation
- graph construction
- RAG
- embeddings
- AI
- diagrams
- reports

Conceptually:

```text
M3 identifies and registers the source.
M4 acquires and ingests the source.
Analysis determines what the source contains.
```

Keep these responsibilities separate.

---

## 23. Project Hierarchy

The current hierarchy is:

```text
User
  ↓
Project
  ↓
Repository
```

Project is the primary:

- ownership boundary
- collaboration boundary
- authorization boundary
- access boundary
- isolation boundary
- repository boundary

Do not reintroduce Organization into planning.

Historical Organization-oriented material must not override the current baseline.

---

## 24. Frozen M1/M2

M1 and M2 are frozen.

For every dependency:

```text
Frozen contract:
How this module consumes it:
What must remain unchanged:
Compatibility tests:
```

Do not plan modifications to frozen modules unless an explicit architectural change has been approved.

---

## 25. Cross-Module Contracts

M3–M7 may be implemented in parallel, so boundaries must be explicit.

For each boundary:

```text
Provider:
Consumer:
Contract:
Input:
Output:
Failure behavior:
Authorization:
Persistence ownership:
Lifecycle ownership:
```

At minimum inspect relevant boundaries such as:

- M3 ↔ M4
- M3 ↔ M5
- M3 ↔ M6
- M3 ↔ M7

Do not rely on undocumented assumptions between module owners.

---

## 26. Security Planning

Security is part of design, not final cleanup.

Identify:

- authentication dependency
- authorization boundary
- project isolation
- input validation
- secrets and credentials
- repository trust boundary
- path handling
- URL validation
- error disclosure
- logging
- resource limits

Repository contents are untrusted.

Do not plan arbitrary execution of repository-controlled code.

---

## 27. Persistence Planning

For every persistent entity:

```text
Table:
Primary key:
Foreign keys:
Indexes:
Unique constraints:
Nullable fields:
Lifecycle fields:
Delete behavior:
Migration:
Repository operations:
```

Database state must be owned by the correct module.

Do not create state belonging to another module.

---

## 28. Migration Planning

For every schema change:

```text
Migration:
Tables affected:
Columns:
Indexes:
Constraints:
Foreign keys:
Upgrade:
Downgrade:
Compatibility:
Tests:
```

Never rewrite historical migrations merely to simplify current work.

New schema changes require new migrations.

---

## 29. API Planning

For every endpoint:

```text
Method:
Path:
Purpose:
Authorization:
Request DTO:
Response DTO:
Success status:
Error statuses:
Service operation:
Isolation behavior:
Tests:
```

Use existing `/api/v1/` conventions.

Routers delegate to application services.

Do not put business logic in endpoint handlers.

---

## 30. Error Planning

For every significant failure:

```text
Condition:
Error type:
Error code:
Category:
HTTP status:
User-visible behavior:
Logging behavior:
Test:
```

Consider:

- validation
- authorization
- not found
- conflict
- domain failure
- infrastructure failure
- unexpected failure

Reuse the existing project error model rather than inventing parallel error handling.

---

## 31. Transaction Planning

For every multi-step use case:

```text
Transaction boundary:
Operations inside transaction:
Commit owner:
Rollback behavior:
Failure scenarios:
Concurrency constraints:
```

Do not introduce a generic Unit of Work unless the architecture requires it.

---

## 32. Concurrency Planning

Identify operations vulnerable to races, including where applicable:

- duplicate registration
- duplicate membership
- concurrent updates
- delete/update races

Where an invariant must hold under concurrency, prefer database constraints where appropriate.

Plan concurrency tests when race behavior materially affects correctness.

---

## 33. Test Planning

Derive tests from requirements.

Use a matrix:

```text
Requirement | Test Type | Test Case | Expected Result
```

Cover relevant:

- happy paths
- invalid input
- authorization
- isolation
- conflicts/duplicates
- not found
- lifecycle
- persistence
- transaction failure
- concurrency
- regression
- architecture boundaries

Test count is not a quality metric.

---

## 34. Architecture Test Planning

Identify invariants that should be mechanically protected.

Examples:

- absolute imports
- forbidden dependencies
- forbidden Organization references
- module boundary violations
- domain → infrastructure violations
- M1/M2 compatibility
- required files/modules
- accidental duplicate modules

Architecture tests should protect decisions that are expensive to rediscover manually.

---

## 35. Verification Planning

Define verification before implementation.

Typical sequence:

```text
Formatting
    ↓
Linting
    ↓
Type Checking
    ↓
Unit Tests
    ↓
Integration Tests
    ↓
Architecture Tests
    ↓
Migration Verification
    ↓
Full Test Suite
    ↓
Final Diff Inspection
```

Use the project's actual configured tooling.

Never claim verification without evidence.

---

## 36. Implementation Order

Provide an implementation sequence based on the actual dependency graph.

A typical sequence is:

```text
1. Domain contracts
2. Persistence model
3. Migration
4. Repository contract
5. Repository implementation
6. Application service
7. DTOs
8. Dependency injection
9. API
10. Tests
11. Verification
```

Change the sequence when actual dependencies require it.

Do not blindly follow a template.

---

## 37. Dependency Graph

Represent significant dependencies explicitly.

Example:

```text
Domain
  ↓
Application Contract
  ↓
Application Service
  ↓
Repository Contract
  ↓
Infrastructure Repository
  ↓
Persistence
```

And:

```text
API
  ↓
DTO
  ↓
Application Service
  ↓
Authorization
  ↓
Domain + Repository Contract
```

The actual graph must match StackSense architecture.

---

## 38. Testability Planning

For each component ask:

- Can it be tested independently?
- Which dependency requires substitution?
- Can dependencies be injected?
- Is state deterministic?
- Does it require a database?
- Should it be unit or integration tested?
- Is mocking actually useful?

Do not mock everything.

Mock external boundaries when appropriate.

Use integration tests for actual persistence/framework behavior.

---

## 39. Complexity Review

Before approving the plan:

```text
Can any component be removed?

Can any abstraction be removed?

Can any dependency be simplified?

Can two components remain one cohesive component?

Can a pattern be replaced by composition?

Can a future concern be deferred?

Can an existing project contract be reused?
```

Prefer the simplest design that fully satisfies the architecture.

---

## 40. Plan Review Checklist

Before implementation:

**Architecture**

- Current architecture was read
- Superseding decisions identified
- Historical conflicts resolved correctly
- Module scope explicit
- Out-of-scope responsibilities explicit

**Components**

- Every component has a responsibility
- Every component has a reason to exist
- Domain boundaries clear
- Application responsibilities clear
- Infrastructure responsibilities clear
- Repository contracts justified
- DTOs justified
- DI registrations justified

**Dependencies**

- Dependency direction clear
- DIP applied where useful
- Unnecessary coupling avoided
- Cross-module dependencies documented
- Frozen contracts preserved

**Design**

- SOLID considered
- Patterns justified by actual problems
- No speculative abstractions
- Folder structure follows existing conventions

**Security**

- Authorization boundary defined
- Project isolation defined
- Repository content treated as untrusted
- Secrets protected
- Resource limits considered

**Persistence**

- Schema defined
- Constraints defined
- Indexes defined
- Migration planned
- Transaction boundaries defined
- Concurrency considered

**Testing**

- Unit tests planned
- Integration tests planned
- API tests planned
- Authorization tests planned
- Isolation tests planned
- Architecture tests planned
- Regression tests planned

**Verification**

- Verification commands identified
- Success criteria explicit
- Final diff inspection included
- Independent review can verify implementation

---

## 41. Planning Output

A completed module plan should contain:

```text
# Module Implementation Plan

Module:
Phase:
Objective:

Architecture Baseline:

Responsibilities:

Out of Scope:

Frozen Dependencies:

Upstream Contracts:

Downstream Contracts:

Domain Design:

Application Design:

DTOs:

Repository Contracts:

Persistence:

Migrations:

Authorization:

API:

Dependency Injection:

Security:

Cross-Module Boundaries:

File Structure:

Implementation Order:

Test Plan:

Verification Plan:

Risks:

Open Questions:

Definition of Done:
```

The plan must be detailed enough for another engineer to implement the module without inventing missing architecture.

---

## 42. Open Questions

If an essential architectural decision is missing:

```text
Open Question:
Why it matters:
Affected boundary:
Possible options:
Required decision:
```

Do not silently answer architectural questions through implementation.

Keep unresolved decisions visible.

---

## 43. Definition of Done

Planning is complete when:

- active module is understood
- responsibilities are explicit
- boundaries are explicit
- dependencies are explicit
- contracts are explicit
- persistence is defined
- authorization is defined
- security requirements are defined
- API contracts are defined
- test strategy is defined
- verification strategy is defined
- implementation order is defined
- cross-module contracts are explicit
- open architectural questions are identified

Only then should significant implementation begin.

---

## 44. Core Principle

A good module plan prevents architecture from being discovered accidentally during coding.

The planning chain is:

```text
Architecture
    ↓
Responsibility
    ↓
Design
    ↓
Contracts
    ↓
Implementation
    ↓
Tests
    ↓
Verification
```

Do not optimize for:

- the largest design
- the most patterns
- the most files
- speculative extensibility

Optimize for:

```text
Correct boundaries
+
Clear contracts
+
Minimal necessary complexity
+
Production-quality implementation
+
Verifiable behavior
```

The purpose of planning is not to predict every line of code.

The purpose is to make architectural intent precise enough that implementation can proceed without inventing architecture.
