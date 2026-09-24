---
name: production-engineering
description: Apply production-quality engineering standards to StackSense implementations, covering architecture, SOLID, dependency design, persistence, APIs, security, reliability, testing, and operational correctness.
---

# Production Engineering Skill

## Purpose

Implement StackSense as production-quality software.

Production quality means:

- correct architecture
- clear responsibility ownership
- high cohesion and low coupling
- explicit dependencies
- appropriate abstraction
- testability
- security
- data integrity
- reliability
- observability where required
- compatibility with frozen contracts

Do not optimize local convenience at the expense of system architecture.

---

## 1. Architecture and Responsibility

Before implementation, establish:

```text
Requirement:
Owning module:
Owning layer:
Upstream contracts:
Downstream consumers:
Dependencies:
Persistence:
Authorization:
Failure behavior:
Security implications:
```

Every responsibility must have a clear owner.

Do not implement a responsibility merely because the current module needs its output.

Follow existing StackSense architecture and repository conventions.

Do not silently reinterpret architectural decisions.

---

## 2. Layer Boundaries

Use the established structure where applicable:

```text
<module>/
├── domain/
├── application/
│   └── dto/
├── infra/
└── repositories/
```

Do not create layers mechanically.

**Domain**

Owns:

- domain concepts
- invariants
- lifecycle behavior
- domain rules

Must not directly depend on:

- FastAPI
- HTTP
- ORM infrastructure
- infrastructure repositories
- external service implementations
- framework-specific DI

**Application**

Owns use-case orchestration.

May coordinate:

- domain objects
- repository contracts
- authorization
- transactions
- DTOs
- current-user context
- external application contracts

Must not become a repository, router, or infrastructure implementation.

**Infrastructure**

Owns implementation details:

- ORM models
- persistence
- external integrations
- adapters
- framework integrations
- concrete contract implementations

Infrastructure implements contracts; it does not redefine business behavior.

---

## 3. Domain Engineering

Keep meaningful domain behavior close to the state it governs.

Identify and enforce:

- valid identifiers
- valid lifecycle states
- valid transitions
- required relationships
- permitted operations
- domain-specific invariants

An invariant that must hold regardless of entry point must not exist only in an API handler.

Do not duplicate invariants unnecessarily across layers.

Do not create anemic domain structures merely for convenience.

---

## 4. Application Engineering

Application services should orchestrate cohesive use cases.

They may handle:

```text
Authorization
    ↓
Validation
    ↓
Domain Operations
    ↓
Persistence Contracts
    ↓
Transaction
    ↓
Response
```

Keep unrelated use cases separate.

Do not put infrastructure implementation details into application services.

Do not make application services responsible for HTTP mechanics or ORM behavior.

---

## 5. DTO Engineering

DTOs represent meaningful application/API boundaries.

They should have:

- explicit names
- explicit fields
- appropriate validation
- stable contract semantics
- clear input/output responsibility

Do not expose persistence models directly.

Do not expose internal persistence fields merely because they exist.

Do not create DTOs that add no meaningful boundary.

---

## 6. SOLID

Apply SOLID pragmatically.

**SRP**

Each component should have one coherent reason to change.

Avoid combining:

- HTTP
- authorization
- domain rules
- persistence
- serialization
- external integration

in one component.

**OCP**

Create extension points only where real variation exists.

Avoid speculative plugin architectures.

**LSP**

Implementations must preserve the behavioral contract of their abstraction.

Do not create inheritance hierarchies merely for reuse.

**ISP**

Keep interfaces focused on consumer needs.

Avoid giant interfaces containing unrelated operations.

**DIP**

Prefer:

```text
Application
    ↓
Contract
    ↑
Infrastructure Implementation
```

over direct application dependency on infrastructure.

Introduce abstractions when they provide meaningful decoupling, substitution, or testability.

---

## 7. Dependency Injection

Dependencies should be explicit.

Prefer constructor injection where appropriate.

Avoid:

- hidden global dependencies
- service locators
- unnecessary singleton state
- constructing infrastructure inside business logic
- hard-coded concrete dependencies

DI composition belongs at the appropriate application/composition boundary.

Tests should be able to replace appropriate dependencies without modifying production logic.

Do not create DI abstractions when there is no meaningful variation or testing benefit.

---

## 8. Cohesion and Coupling

**High Cohesion**

Keep closely related behavior together.

Avoid:

- god services
- god repositories
- utility dumping grounds
- miscellaneous helper classes
- catch-all business modules

Do not split naturally cohesive behavior into artificial micro-classes.

**Low Coupling**

Minimize dependencies between unrelated responsibilities.

Prefer dependencies on:

- domain concepts
- focused contracts
- stable interfaces
- explicit application boundaries

Avoid unnecessary dependence on:

- concrete infrastructure
- unrelated modules
- implementation details
- global mutable state

Every dependency should have a reason to exist.

---

## 9. Design Patterns

Patterns are tools, not requirements.

Start with:

```text
What design problem exists?
```

not:

```text
Which pattern can I use?
```

Possible categories include:

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
- Observer
- Chain of Responsibility
- Mediator

Before introducing a pattern, identify:

```text
Problem:
Why simpler composition is insufficient:
Responsibility isolated:
Dependency controlled:
Benefit:
Complexity introduced:
```

If the pattern cannot be justified, do not use it.

Prefer composition over inheritance unless there is a genuine substitutable relationship.

---

## 10. Absolute Imports

StackSense requires absolute imports.

Prefer:

```python
from backend.platform.projects.application.service import ProjectService
```

over:

```python
from .service import ProjectService
```

Check for:

- relative imports
- duplicate import paths
- circular dependencies
- obsolete imports
- forbidden architectural dependencies

---

## 11. Repository Engineering

Use repository abstractions where persistence needs to be inverted.

Prefer meaningful contracts:

```text
ProjectRepository
ProjectAccessRepository
RepositoryRepository
```

over speculative:

```text
GenericRepository[T]
```

unless genuinely required.

Repositories should focus on persistence.

They must not silently become responsible for:

- authorization
- HTTP behavior
- business workflows
- domain orchestration
- unrelated external APIs

Preserve established StackSense transaction behavior.

Where the existing convention is that repositories flush but do not own the outer commit, preserve it.

---

## 12. Database and Data Integrity

Review:

- primary keys
- foreign keys
- indexes
- unique constraints
- nullability
- delete behavior
- timestamps
- query patterns
- pagination
- transaction boundaries
- migration ordering

Use database constraints for invariants that must hold under concurrency.

Application pre-checks alone are insufficient for concurrency-sensitive uniqueness.

Protect state using:

- domain invariants
- database constraints
- transactions
- foreign keys
- unique constraints
- explicit lifecycle states

---

## 13. Transactions

Identify transaction boundaries explicitly.

For multi-step operations:

```text
Validate
    ↓
Authorize
    ↓
Domain Operation
    ↓
Persist Related State
    ↓
Commit
```

Consider:

- commit ownership
- rollback behavior
- partial failure
- flush behavior
- integrity constraints
- concurrent requests

Do not introduce a generic Unit of Work unless the architecture requires it.

---

## 14. Migration Discipline

Every schema change requires a migration.

Never rewrite historical migrations merely to simplify current work.

For new schema changes:

1. create a new migration
2. verify ordering
3. verify upgrade
4. verify downgrade where required
5. inspect resulting schema
6. verify ORM alignment
7. run relevant integration tests

Do not leave contradictory or duplicate migrations.

---

## 15. API Engineering

API handlers should remain thin.

They should primarily perform:

- HTTP input handling
- dependency injection
- DTO conversion
- application-service invocation
- response mapping

Do not:

- put substantial business logic in routers
- perform direct database operations from routes
- duplicate authorization logic across endpoints
- expose infrastructure details

Follow existing `/api/v1/` conventions.

---

## 16. Authorization and Isolation

Authorization is a first-class architectural responsibility.

For repository resources:

```text
Repository
    ↓
project_id
    ↓
ProjectAuthorization
    ↓
ProjectAccess
    ↓
CurrentUser
```

Do not introduce independent Repository RBAC unless explicitly required.

Do not duplicate role matrices inside feature services.

For every protected operation verify:

- current user
- resource
- owning project
- required permission
- denial behavior

Current hierarchy:

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

Do not reintroduce Organization.

Do not bypass project authorization through alternate endpoints, direct identifiers, repository queries, background jobs, or hidden dependencies.

---

## 17. Frozen M1/M2

M1 and M2 are frozen.

Do not casually modify:

- Project semantics
- Project persistence
- ProjectAccess
- ProjectRole
- CurrentUserProvider
- ProjectAuthorization
- established API contracts
- historical migration chain
- architecture tests

If a genuine insufficiency is discovered:

```text
Identify issue
    ↓
Explain affected contract
    ↓
Propose architectural change
    ↓
Obtain approval
    ↓
Update authoritative architecture
    ↓
Implement
    ↓
Verify
```

Never silently mutate frozen modules.

---

## 18. M3 Boundary

M3 owns Repository Registration:

- repository identity
- project relationship
- registration
- registration metadata
- lifecycle
- persistence
- application services
- authorization integration
- API contracts

M3 must not absorb M4.

M4 owns:

- source acquisition
- ingestion
- validation
- file discovery
- artifact ingestion
- revision/snapshot acquisition
- physical source storage
- ingestion workers
- ingestion queues
- ingestion retries
- ingestion resource controls

Keep the distinction:

```text
M3:
What repository is registered?

M4:
How is its source safely acquired and prepared?
```

---

## 19. Analysis Boundary

Repository registration is not source analysis.

Do not move these into M3:

- parsing
- AST processing
- symbol extraction
- dependency extraction
- architecture inference
- findings
- recommendations
- graph construction
- RAG
- embeddings
- AI
- diagrams
- reports

A registered repository is an input to later analysis.

---

## 20. Untrusted Repository Content

Repository content is untrusted.

Never execute repository-controlled code during registration or ordinary repository handling.

Do not:

- run repository scripts
- execute build commands
- install repository-controlled packages
- import arbitrary repository modules
- execute shell commands derived from repository content
- trust repository configuration as executable instructions

Validate external inputs and respect safe acquisition/storage boundaries.

---

## 21. Security

Security must be considered during implementation.

Review:

- authentication
- authorization
- project isolation
- input validation
- secrets
- credentials
- connection information
- URL validation
- path handling
- error disclosure
- logging
- resource limits
- untrusted content

Never log:

- passwords
- tokens
- private keys
- database credentials
- sensitive connection strings

Do not expose stack traces or infrastructure details through public responses.

---

## 22. Resource Safety

Avoid unbounded resource usage.

Control:

- database result sizes
- pagination
- file sizes
- recursion
- memory usage
- retries
- worker creation
- external requests
- queue growth
- repository processing

Respect architecture-defined resource limits.

Do not place expensive processing into synchronous request paths when architecture assigns it to background processing.

---

## 23. Concurrency

Consider concurrent:

- registration
- updates
- deletion
- authorization changes
- duplicate operations
- database writes

Use appropriate:

- database constraints
- transactions
- atomic operations
- isolation/locking where justified

Application pre-checks alone do not protect concurrency-sensitive invariants.

---

## 24. External Integrations

When integrating external systems:

- isolate them behind appropriate contracts
- validate external responses
- handle timeouts
- define retry behavior
- avoid infinite retries
- prevent provider-specific errors from leaking through domain APIs
- inject credentials/configuration
- define failure semantics

Do not allow an external SDK to become a hidden application dependency.

---

## 25. Configuration

Configuration must be explicit and environment-aware.

Never hard-code:

- credentials
- secrets
- passwords
- environment-specific URLs
- deployment-specific paths

Use the established StackSense configuration system.

Do not make configuration a hidden domain dependency.

---

## 26. Logging and Observability

Logs should support diagnosis without exposing sensitive information.

Log meaningful events such as:

- important lifecycle transitions
- failures
- unexpected conditions
- integration failures
- background-job failures

Avoid sensitive or unnecessary source data.

Where observability is required, measure appropriate:

- request latency
- operation success/failure
- job status
- integration failures
- database failures
- important lifecycle transitions

Keep telemetry concerns outside domain logic.

---

## 27. Query and Performance Engineering

Avoid unnecessary database work.

Review:

- query count
- indexes
- filtering
- pagination
- authorization filtering
- loading strategy
- duplicate queries
- unbounded reads

Do not load entire tables when a paginated contract exists.

Do not optimize prematurely.

Prioritize:

```text
Correctness
    ↓
Architecture
    ↓
Security
    ↓
Maintainability
    ↓
Measured Performance
```

When performance matters, measure before optimizing.

Do not add caching, batching, asynchronous processing, or complex concurrency without a demonstrated need.

---

## 28. Caching

Introduce caching only when:

- repeated access is demonstrably expensive
- consistency semantics are understood
- invalidation is defined
- ownership is clear

Specify:

```text
Cached data:
Owner:
TTL:
Invalidation:
Consistency:
Failure behavior:
```

A cache must never silently become a second source of truth.

---

## 29. Background Processing and Idempotency

Use background processing only when architecture assigns the work to it or synchronous execution is inappropriate.

Define:

- input
- state
- retry behavior
- failure behavior
- idempotency
- resource limits
- observability

For retryable operations, explicitly determine whether they are idempotent.

Especially consider:

- registration
- ingestion
- external calls
- background jobs
- state transitions

---

## 30. Failure Thinking

For significant operations ask:

```text
What if it fails halfway?

What if the database is unavailable?

What if the request is retried?

What if two requests happen simultaneously?

What if an external service times out?

What if input is malicious?

What if a dependency returns malformed data?

What if the process crashes after persistence but before response?
```

Where architecture requires it, define deliberate failure behavior.

---

## 31. Testability

Production code must support appropriate:

- unit tests
- domain tests
- application tests
- integration tests
- API tests
- architecture tests
- regression tests

Do not weaken production architecture to simplify tests.

Do not mock everything.

Use real infrastructure when infrastructure behavior is what the test verifies.

Tests should verify behavior and contracts rather than implementation trivia.

Meaningful coverage includes:

- happy paths
- negative cases
- authorization failures
- cross-project isolation
- conflicts
- not-found behavior
- lifecycle transitions
- persistence failures
- transaction failures
- concurrency behavior
- regression cases

---

## 32. Type Safety and Readability

Use explicit typing consistent with StackSense.

Prefer explicit types for:

- contracts
- DTOs
- domain entities
- dependency providers
- parameters
- return values

Avoid `Any` unless justified.

Prefer:

- descriptive names
- cohesive methods
- explicit control flow
- clear boundaries
- minimal hidden behavior

Avoid:

- clever one-liners
- deeply nested conditionals
- magic values
- unexplained constants
- excessive metaprogramming
- unnecessary generic abstractions

Readable code is a production feature.

---

## 33. Refactoring and Compatibility

Do not perform unrelated refactoring during feature implementation.

If existing code blocks correct implementation:

1. identify the concrete reason
2. make the smallest necessary change
3. preserve contracts where possible
4. add/update regression tests
5. verify the change
6. document the reason

Before changing an existing contract, identify:

- current consumers
- tests
- API clients
- persistence dependencies
- module dependencies

Do not break frozen/public contracts without approved architectural change.

---

## 34. Production Readiness

Before considering implementation complete, verify:

**Architecture**

- Correct module owns the responsibility
- Current architecture is respected
- Frozen contracts are preserved
- Cross-module boundaries remain intact
- Organization was not reintroduced

**Design**

- Responsibilities are cohesive
- Coupling is controlled
- Dependencies are explicit
- DIP is applied where useful
- Patterns are justified
- No speculative abstractions exist
- Composition is preferred where appropriate

**Implementation**

- Absolute imports used
- DTOs are explicit
- Services are cohesive
- Repository contracts are meaningful
- Persistence is isolated
- API handlers are thin
- DI is correct
- Error handling follows project conventions

**Security**

- Authorization enforced
- Project isolation preserved
- Repository content treated as untrusted
- Repository code is never executed during registration
- Secrets protected
- Sensitive errors/data are not exposed
- Resource limits respected

**Persistence**

- Constraints correct
- Indexes appropriate
- Foreign keys correct
- Transactions correct
- Migrations correct
- Concurrency-sensitive invariants protected

**Testing**

- Appropriate unit tests exist
- Integration tests exist where required
- Authorization/isolation tested
- Negative cases covered
- Regression tests pass
- Architecture tests pass

**Operations**

- Logging is appropriate
- Sensitive data is not logged
- Failure behavior is deliberate
- External integrations handle failures
- Background work is bounded and observable where applicable

---

## 35. Final Diff and Engineering Evidence

Inspect the final diff for:

- unintended files
- temporary files
- debug statements
- secrets
- generated artifacts
- duplicate modules
- accidental migrations
- unrelated refactors
- commented-out production code
- weakened tests
- unexpected dependencies
- architecture violations

The implementation report should identify:

```text
Module:
Implemented capabilities:
Contracts added/consumed:
Persistence changes:
API changes:
Authorization:
Security considerations:
Tests added:
Verification performed:
Cross-module impact:
Known issues:
```

Do not claim architectural approval or freeze.

Independent review remains a separate control.

---

## 36. No Silent Architecture Changes

If implementation reveals an architectural insufficiency:

Do not:

- reinterpret architecture silently
- add undocumented workarounds
- modify master.txt without authorization
- modify frozen contracts without approval
- create hidden compatibility layers

Instead:

```text
Identify conflict
    ↓
Describe technical issue
    ↓
Identify affected boundaries
    ↓
Propose smallest architectural change
    ↓
Obtain approval
    ↓
Update architecture/ADR
    ↓
Implement
    ↓
Verify
```

All architectural changes must remain explicit and traceable.

---

## Final Standard

Production engineering means:

```text
Correct Architecture
        +
Correct Behavior
        +
Clear Design
        +
Explicit Dependencies
        +
Security
        +
Data Integrity
        +
Testability
        +
Operational Reliability
```

Do not optimize for:

- maximum abstraction
- maximum number of files
- maximum pattern usage
- speculative extensibility

Optimize for:

- Architecturally correct
- Behaviorally correct
- Secure
- Testable
- Maintainable
- Observable where required
- Resilient to expected failure
- Consistent with StackSense

Prefer the simplest design that fully satisfies the architecture.
Never sacrifice architectural integrity for local convenience.
