---
name: module-implementation
description: Implement an assigned StackSense module within its approved architectural boundary, integrating existing contracts while preserving frozen modules, dependency direction, security, persistence, testing, and cross-module interfaces.
---

# Module Implementation Skill

## Purpose

Implement an assigned StackSense module as production-quality software while preserving:

- the authoritative architecture
- approved module scope
- frozen predecessor contracts
- existing project conventions
- explicit module boundaries
- security and authorization requirements
- persistence and transaction rules
- required verification

This skill is for the **Builder**.

The Builder implements the approved design. The Builder does not redefine architecture, expand module ownership, or silently modify frozen decisions.

---

## 1. Implementation Authority

Follow this authority order:

1. current `master.txt`
2. explicit superseding decisions in `master.txt`
3. active module scope and approved module context
4. frozen predecessor contracts
5. existing repository implementation
6. established project conventions
7. implementation judgment

When implementation conflicts with architecture:

- do not silently change the architecture
- do not silently change frozen contracts
- do not invent ownership-changing workarounds
- identify the conflict
- surface the issue
- obtain the required architectural decision
- implement only after the decision is approved

The Builder implements architecture; the Builder is not the architecture authority.

---

## 2. Preconditions

Before writing production code, establish:

- active phase
- active module
- objective
- responsibilities
- explicit exclusions
- upstream dependencies
- downstream consumers
- exposed contracts
- consumed contracts
- persistence requirements
- authorization requirements
- security requirements
- testing requirements
- verification requirements

Read the relevant portions of `master.txt` and inspect the existing implementation before creating new abstractions.

Do not begin from a vague feature description when authoritative architecture exists.

---

## 3. Architecture-First Implementation

Before creating files, answer:

```text
What belongs to this module?
What does not belong to this module?
What state does it own?
What state belongs elsewhere?
What contracts does it expose?
What contracts does it consume?
Which module owns each side effect?
Which frozen contracts must remain unchanged?
```

The implementation must preserve these boundaries.

Do not discover or redefine architecture accidentally through code.

---

## 4. Existing Code First

Inspect existing code for:

- domain conventions
- application services
- repository contracts
- persistence models
- DTO conventions
- dependency injection
- authorization
- error handling
- migrations
- tests
- naming conventions
- module boundaries

Prefer existing contracts and patterns when they are architecturally correct.

Do not create duplicate:

- services
- repositories
- contracts
- authorization mechanisms
- current-user abstractions
- persistence subsystems

unless a concrete architectural requirement requires them.

---

## 5. Module Structure

Follow the existing StackSense structure.

Where justified:

```text
module/
├── domain/
├── application/
│   └── dto/
├── infra/
└── repositories/
```

Do not mechanically create every layer.

Create a layer or abstraction only when it provides a meaningful responsibility such as:

- dependency inversion
- persistence isolation
- external-system isolation
- testability
- domain protection
- replaceable behavior

---

## 6. Domain

The domain represents business concepts, state, invariants, and meaningful behavior.

Domain code must not directly depend on:

- FastAPI
- HTTP request/response objects
- SQLAlchemy
- database sessions
- infrastructure implementations
- external SDKs
- framework-specific DI

Identify and enforce meaningful invariants at the lowest appropriate boundary.

Avoid both:

- anemic domain models when meaningful behavior belongs in the domain
- artificial domain abstractions when the behavior is actually application or infrastructure logic

---

## 7. Application Layer

Application services orchestrate use cases.

Typical flow:

```text
input
  ↓
authorization
  ↓
validation
  ↓
domain behavior
  ↓
repository/contracts
  ↓
transactional side effects
  ↓
output
```

Application services should not become:

- routers
- repositories
- infrastructure implementations
- domain models
- unrelated workflow containers

Use explicit application contracts when they provide meaningful dependency inversion.

Follow existing naming conventions such as:

```text
Default<Name>Service
```

when implementing an established service abstraction.

---

## 8. Repository Contracts and Persistence

When persistence requires dependency inversion, define a focused repository contract.

Prefer meaningful operations such as:

```text
get_by_id
save
delete
list_for_project
find_by_external_identifier
```

when they correspond to actual use cases.

Avoid speculative generic CRUD abstractions.

Concrete persistence implementations belong in infrastructure and may depend on:

- SQLAlchemy
- sessions
- persistence models
- database-specific behavior

Application code should depend on the contract rather than the concrete implementation.

Preserve established transaction behavior. Where the project convention is that repositories flush but do not own the outer commit, preserve that convention.

---

## 9. Persistence Models and Migrations

Keep persistence representation separate from API/domain contracts where the architecture requires it.

Persistence models may contain:

- columns
- indexes
- foreign keys
- constraints
- relationships
- database-specific configuration

Do not expose ORM models directly through API contracts.

Every schema change requires a migration.

Verify:

- columns
- nullability
- indexes
- foreign keys
- uniqueness
- delete behavior
- timestamps
- constraints
- migration ordering
- upgrade behavior
- downgrade behavior where required
- ORM/schema alignment

Never rewrite historical migrations merely to clean up current implementation.

Create a new corrective migration when required.

---

## 10. Project and Repository Boundary

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

Do not reintroduce an Organization hierarchy from historical architecture.

Do not introduce Repository-level RBAC unless explicitly required by the current architecture.

---

## 11. Authorization

Repository authorization derives from Project access.

Conceptual flow:

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

For direct Repository operations:

1. resolve the repository
2. determine its project_id
3. authorize against the Project
4. perform the operation only after authorization succeeds

Use the existing:

- `ProjectAuthorization`
- `ProjectAccess`
- `ProjectRole`
- `CurrentUserProvider`

Do not create:

- RepositoryRole
- RepositoryAccess
- RepositoryMembership
- duplicate role matrices
- parallel authorization systems

unless explicitly required by the authoritative architecture.

---

## 12. Current User

Use the established `CurrentUserProvider`.

Do not obtain identity through:

- hard-coded IDs
- global mutable state
- request parsing inside application services
- persistence-specific mechanisms

Preserve the existing test override mechanism.

Do not introduce a second current-user abstraction.

---

## 13. M3 Boundary

When implementing M3, keep it focused on Repository Registration.

M3 may own:

- Repository identity
- Repository-to-Project relationship
- registration
- registration metadata
- repository lifecycle
- persistence
- application services
- authorization integration
- API contracts
- registration tests

M3 must not absorb M4 responsibilities.

---

## 14. M3 / M4 Boundary

M4 owns repository acquisition and ingestion.

Do not implement M4 responsibilities inside M3:

- source acquisition
- ingestion
- file discovery
- file filtering
- artifact ingestion
- revision acquisition
- snapshot acquisition
- physical source storage
- ingestion workers
- ingestion queues
- ingestion retry infrastructure
- repository-content processing

The boundary is:

```text
M3:
What repository is registered for this project?

M4:
How is repository source safely acquired and prepared?
```

Keep registration and acquisition separate.

---

## 15. Analysis Boundary

Repository registration is not source analysis.

Do not introduce into M3:

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
- AI explanation
- diagrams
- reports
- analysis execution

The registration module identifies the source. Analysis determines what the source contains.

---

## 16. DTOs and API

Use explicit DTOs for application/API boundaries.

DTOs should:

- represent intended contracts
- validate external input
- expose only intended fields
- avoid persistence leakage
- use meaningful names
- remain stable and understandable

Do not return ORM models directly from API routes.

Routers should remain thin and handle primarily:

- HTTP input
- dependency injection
- DTO conversion
- application service invocation
- response mapping

Do not put substantial business logic or direct database operations in routers.

Follow existing `/api/v1/` conventions.

---

## 17. Error Handling

Use the established application error system.

Preserve:

- error codes
- categories
- HTTP mappings
- not-found semantics
- conflict semantics
- authorization semantics

Distinguish where appropriate between:

- validation
- authorization
- not found
- conflict
- domain failure
- infrastructure failure
- unexpected failure

Do not expose raw infrastructure exceptions.

Do not swallow failures with broad exception handling.

Translate infrastructure failures into application errors at the appropriate boundary.

---

## 18. Transactions

Identify atomic operations.

For multi-step operations:

```text
validate
  ↓
authorize
  ↓
domain operation
  ↓
persist related state
  ↓
commit
```

Ensure partial failure cannot leave invalid application state.

Respect existing transaction ownership.

Do not introduce a generic Unit of Work merely because a transaction exists.

Introduce additional transaction abstractions only when they solve a concrete architectural problem.

---

## 19. Dependency Injection and SOLID

Use dependency injection for meaningful replaceable or infrastructure-dependent behavior such as:

- repositories
- services
- authorization components
- current-user provider
- external clients

Prefer explicit constructor/provider injection.

Apply SOLID pragmatically:

- SRP: cohesive responsibilities
- OCP: real extensibility, not speculative plugins
- LSP: implementations honor contracts
- ISP: focused interfaces
- DIP: high-level code depends on stable contracts where appropriate

Do not create abstractions solely to claim SOLID compliance.

---

## 20. Design Patterns

Use patterns only when they solve an actual problem.

Potentially justified patterns include:

- Factory
- Strategy
- Adapter
- Facade
- Decorator
- State
- Repository
- Dependency Injection

Before introducing a pattern, identify:

```text
Problem:
Why simpler composition is insufficient:
Responsibility isolated:
Dependency controlled:
Testability/extensibility benefit:
Complexity introduced:
```

Avoid speculative:

- factories for one implementation
- strategy hierarchies with no variation
- generic base classes
- builders without construction complexity
- event buses
- CQRS
- mediator layers
- generic repositories

Production quality means appropriate complexity, not maximum abstraction.

---

## 21. Absolute Imports

All Python imports must follow the project requirement for absolute imports.

Prefer:

```python
from backend.platform.projects.application.service import ProjectService
```

over:

```python
from .service import ProjectService
```

Check modified code for:

- relative imports
- obsolete import paths
- duplicate module paths
- circular imports
- forbidden architectural dependencies

---

## 22. Security and Untrusted Content

Treat all external input as untrusted.

For repository functionality, repository metadata and repository content are untrusted.

Never execute repository-controlled code during registration.

Do not:

- run repository scripts
- execute build commands
- install repository-controlled packages
- import arbitrary repository modules
- execute shell commands derived from repository content

Validate:

- identifiers
- URLs
- names
- paths
- metadata
- user-controlled strings

Protect:

- credentials
- tokens
- secrets
- connection information

Never log secrets or expose sensitive infrastructure details through API errors.

---

## 23. Resource Safety

Avoid unbounded:

- file reads
- recursive traversal
- database queries
- in-memory collections
- retries
- worker creation
- external calls

Respect architecture-defined resource limits.

Do not perform expensive ingestion or repository processing inside registration paths when that responsibility belongs to a bounded subsystem.

---

## 24. Persistence and Concurrency

Review database behavior for:

- query count
- filtering
- pagination
- indexes
- authorization filtering
- eager/lazy loading
- duplicate queries
- unbounded reads

For concurrency-sensitive invariants, prefer database constraints and atomic operations over application pre-checks alone.

Consider:

- duplicate registration
- concurrent updates
- delete/update races
- integrity failures

Translate expected integrity failures into appropriate application errors.

---

## 25. Testing

Every production capability requires meaningful tests appropriate to the feature.

Consider:

- happy path
- invalid input
- not found
- authorization failure
- cross-project isolation
- duplicate/conflict behavior
- persistence behavior
- transaction failure
- concurrency
- regression

Use the appropriate test level:

**Unit** — for:

- domain behavior
- lifecycle rules
- pure application logic
- authorization decisions

**Integration** — for:

- repositories
- persistence
- migrations
- transactions
- API/application integration

**Architecture** — for:

- import boundaries
- forbidden dependencies
- module structure
- architectural invariants

Do not replace persistence/integration tests with mocks when actual integration behavior is what must be verified.

Do not weaken existing tests to make implementation pass.

---

## 26. Verification

Run the repository's configured verification tools as appropriate:

- pytest
- ruff
- black
- mypy
- alembic checks
- architecture tests
- integration tests

Use actual project configuration.

When a test fails:

1. reproduce it
2. identify the cause
3. compare implementation and test against architecture
4. fix the implementation if it is wrong
5. change the test only when the requirement legitimately changed and that change is authorized

Never modify tests merely to hide an implementation defect.

---

## 27. Scope Control

Implement only the assigned capability and necessary supporting work.

Do not silently expand into:

- future phases
- unrelated modules
- architecture redesign
- speculative infrastructure
- unrelated refactoring
- unrelated performance work
- unrelated UI changes

Supporting changes should be minimal and directly justified by the assigned capability.

---

## 28. Frozen M1 and M2

M1 and M2 are frozen.

Do not casually modify:

- Project semantics
- Project persistence
- ProjectAccess
- ProjectRole
- CurrentUserProvider
- ProjectAuthorization
- existing API contracts
- existing migrations
- existing architecture rules

If integration exposes a genuine missing contract:

1. identify the issue
2. identify the affected boundary
3. surface it
4. obtain approval
5. update the authoritative architecture/ADR if required
6. implement against the approved decision

Do not silently mutate frozen modules.

---

## 29. Cross-Module Contracts

For M3–M7 parallel development, make cross-module dependencies explicit.

For every dependency identify:

```text
Provider:
Consumer:
Contract:
Input:
Output:
Failure behavior:
Authorization responsibility:
Persistence responsibility:
Lifecycle responsibility:
```

Do not rely on undocumented assumptions.

If a downstream module needs information not provided by the current contract, surface the missing contract instead of creating ad-hoc coupling.

---

## 30. Code Quality

Production code should be:

- readable
- explicit
- cohesive
- testable
- maintainable
- appropriately typed
- deterministic where required
- appropriately abstracted
- free of unnecessary duplication

Avoid:

- giant services
- giant routers
- god repositories
- hidden global state
- magic values
- duplicated authorization
- duplicated persistence logic
- dead code
- commented-out production code
- speculative abstractions

Prefer clear code over clever code.

---

## 31. Comments and Documentation

Comments should explain non-obvious:

- architectural decisions
- invariants
- security constraints
- compatibility behavior
- reasons for unusual implementation choices

Do not use comments to justify architecture violations or restate obvious code.

---

## 32. No Silent Architecture Changes

If implementation reveals that the architecture appears insufficient:

Do not:

- reinterpret architecture silently
- add undocumented workarounds
- modify master.txt without authorization
- modify frozen contracts without approval
- create hidden compatibility layers

Instead:

1. identify the conflict
2. explain the technical issue
3. identify affected boundaries
4. propose the smallest required change
5. obtain approval
6. update the authoritative architecture/ADR
7. implement the approved decision
8. verify the result

Architecture changes must remain explicit and traceable.

---

## 33. Completion Checklist

Before reporting completion:

**Architecture**

- Current master.txt was consulted
- Superseding decisions were respected
- Module scope is correct
- No unauthorized architecture changes exist
- Organization hierarchy was not reintroduced
- Frozen predecessor contracts remain intact

**Design**

- Responsibilities are cohesive
- Domain/application/infrastructure boundaries are correct
- Dependencies point in the correct direction
- Repository contracts are meaningful
- DTOs are explicit
- DI is correct
- No unnecessary abstractions were introduced
- Patterns solve real problems

**Implementation**

- Absolute imports are used
- API handlers remain thin
- Error handling follows project conventions
- Transactions are correct
- Persistence mappings are correct
- Migrations are correct
- Authorization uses existing project mechanisms

**Security**

- Authorization is enforced
- Project isolation is preserved
- Repository content is treated as untrusted
- Repository code is never executed during registration
- Secrets are protected
- Sensitive information is not exposed
- Resource limits are respected

**Testing**

- Relevant unit tests exist
- Relevant integration tests exist
- Authorization tests exist
- Isolation tests exist
- Negative cases are covered
- Migration behavior is verified
- Architecture tests pass
- Existing tests still pass

**Verification**

- Formatting passes
- Linting passes
- Type checking passes where configured
- Relevant tests pass
- Final diff was inspected

---

## 34. Final Diff Review

Inspect the final change set for:

- unintended files
- temporary files
- debug statements
- secrets
- generated artifacts
- duplicate modules
- accidental migrations
- unrelated refactors
- commented-out code
- weakened tests
- unexpected dependency changes
- architecture boundary violations

The final diff should tell a coherent implementation story.

---

## 35. Completion Report

When implementation is complete, report:

```text
Module:
<module>

Implemented:
<capabilities>

Contracts:
<contracts added or consumed>

Persistence:
<schema/migration changes>

API:
<API changes>

Authorization:
<authorization behavior>

Security:
<security considerations>

Tests:
<tests added>

Verification:
<commands and results>

Cross-Module Impact:
<affected contracts>

Known Issues:
<remaining issues, if any>
```

Do not claim that the module is approved or frozen.

Independent review remains a separate control.

---

## 36. Builder / Reviewer Separation

The Builder must not act as the independent Reviewer.

Builder verification asks:

```text
Does the implementation appear to work?
```

Independent review asks:

```text
Does the implementation satisfy the authoritative architecture and requirements?
```

The Builder should provide enough implementation and verification evidence for independent review to audit the result.

---

## Final Principle

Implement the smallest production-quality solution that fully satisfies the authoritative StackSense architecture.

Preserve existing contracts.
Respect frozen modules.
Keep responsibilities inside their assigned boundaries.
Use abstractions only when they solve real problems.
Treat security and authorization as architectural requirements.
Test behavior, boundaries, and regressions.
Never silently redefine architecture.

The Builder's job is to faithfully implement the approved architecture with production-quality engineering.
