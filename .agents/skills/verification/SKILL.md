# Verification Skill

## Purpose

Verify both behavioral correctness and production-quality engineering.

Verification must determine whether the implementation:

- behaves according to requirements
- conforms to the authoritative architecture
- preserves frozen contracts
- respects module boundaries
- satisfies security requirements
- maintains production-quality design
- remains testable
- is ready for independent review

Passing functional tests alone is not sufficient.

---

# 1. Verification Authority

Verification must be based on:

1. current `master.txt`
2. explicit superseding architectural decisions
3. active module requirements
4. frozen predecessor contracts
5. actual implementation
6. tests and verification evidence

Do not treat Builder claims as verification evidence by themselves.

Do not verify against historical architecture when the current baseline supersedes it.

---

# 2. Verification Scope

Before verification, establish:

- active phase
- active module
- expected responsibilities
- explicit exclusions
- upstream contracts
- downstream contracts
- frozen modules
- security requirements
- persistence requirements
- API requirements
- expected tests

Verification must remain within the active scope while still checking for boundary violations and regressions.

---

# 3. Functional Verification

Verify that the implementation behaves according to its requirements.

Check:

- successful operations
- invalid input
- missing resources
- authorization failures
- conflicts
- lifecycle behavior
- persistence behavior
- transaction behavior
- error behavior
- API behavior
- cross-project isolation

Do not verify only the happy path.

---

# 4. Architectural Verification

Verify:

- current Project-first architecture
- no unauthorized Organization reintroduction
- M1 boundaries
- M2 boundaries
- M3/M4 boundary
- analysis boundary
- correct dependency direction
- correct package ownership
- correct layer responsibilities
- frozen contract preservation
- absolute import requirements

Current hierarchy must remain:

```text
User
  ↓
Project
  ↓
Repository
```

Project remains the primary ownership, collaboration, authorization, access, and isolation boundary.

---

# 5. M1/M2 Regression Verification

M1 and M2 are frozen.

Verify that new work has not changed their behavior.

Check:

- Project semantics
- Project persistence
- ProjectAccess
- ProjectRole
- CurrentUserProvider
- ProjectAuthorization
- existing API behavior
- existing error contracts
- existing migrations
- existing tests

New modules must integrate with frozen contracts rather than redefine them.

---

# 6. M3 Verification

For M3 verify that Repository Domain & Registration remains within scope.

Check:

- Repository identity
- Project relationship
- repository registration
- registration metadata
- lifecycle behavior
- persistence
- application services
- authorization
- API contracts
- tests

Verify that Repository authorization derives from Project access.

Conceptually:

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

---

# 7. M3/M4 Boundary Verification

Verify that M3 has not absorbed M4 responsibilities.

Check for accidental implementation of:

- repository acquisition
- ingestion
- file discovery
- file filtering
- artifact ingestion
- revision acquisition
- snapshot acquisition
- physical source storage
- ingestion workers
- ingestion queues
- ingestion retries

M3 answers:

```text
What repository is registered for this project?
```

M4 answers:

```text
How is repository source safely acquired and prepared?
```

These responsibilities must remain separate.

---

# 8. Analysis Boundary Verification

Verify that repository registration has not become source analysis.

Check for unauthorized implementation of:

- parsing
- AST extraction
- symbol extraction
- dependency extraction
- architecture inference
- findings
- recommendations
- graph construction
- RAG
- embeddings
- AI
- diagram generation
- report generation
- analysis execution

Registration identifies the source.

Analysis determines what the source contains.

---

# 9. Design Verification

Inspect the implementation for production-quality design.

Verify:

- SOLID
- cohesion
- coupling
- dependency injection
- meaningful contracts
- appropriate abstractions
- appropriate design patterns
- clear layer boundaries
- testability
- maintainability

---

# 10. SOLID Verification

## Single Responsibility Principle

Ask:

```text
Does each component have one coherent reason to change?
```

Look for:

- god services
- god repositories
- routers containing business logic
- classes combining persistence and domain behavior
- classes combining HTTP, authorization, and persistence

Do not split cohesive components artificially.

---

## Open/Closed Principle

Check whether real variations are isolated behind appropriate contracts.

Do not require speculative extensibility.

Do not penalize simple code merely because it does not introduce an abstraction.

---

## Liskov Substitution Principle

For every abstraction with multiple implementations:

- inspect behavioral compatibility
- inspect error semantics
- inspect return semantics
- inspect preconditions/postconditions

An implementation must honor the contract it claims to implement.

---

## Interface Segregation Principle

Verify that interfaces are focused.

Look for:

- giant repository interfaces
- unrelated operations grouped together
- consumers depending on methods they do not need

Prefer focused contracts.

---

## Dependency Inversion Principle

Verify that high-level application/domain policy does not directly depend on low-level infrastructure where inversion is required.

Expected conceptual direction:

```text
Application
    ↓
Contract
    ↑
Infrastructure Implementation
```

Do not allow:

```text
Application
    ↓
Concrete ORM / Infrastructure
```

when this violates the architecture.

---

# 11. Cohesion Verification

Ask:

```text
Does each component own a coherent responsibility?
```

Look for:

- utility dumping grounds
- miscellaneous helpers
- unrelated service methods
- repositories containing business workflows
- domain objects containing infrastructure behavior

High cohesion is preferred.

---

# 12. Coupling Verification

Identify unnecessary dependencies.

Check for dependencies on:

- unrelated modules
- concrete infrastructure
- implementation details
- global state
- framework internals

Verify that module boundaries are explicit.

Do not confuse legitimate dependencies with unnecessary coupling.

---

# 13. Dependency Injection Verification

Verify:

- dependencies are explicit
- concrete infrastructure is composed at the appropriate boundary
- services are testable
- dependencies can be replaced in tests
- hidden globals are not used
- service locators are not introduced unnecessarily

Verify the actual DI wiring, not merely the existence of interfaces.

---

# 14. Contract Verification

For every significant contract verify:

- owner
- consumer
- operations
- input semantics
- output semantics
- error behavior
- lifecycle behavior
- authorization expectations

Check that implementations actually honor their contracts.

Do not approve an interface merely because its method signatures look correct.

---

# 15. Abstraction Verification

Every significant abstraction must solve a real problem.

Ask:

1. Why does this abstraction exist?
2. Who consumes it?
3. What dependency does it control?
4. Is there meaningful implementation variation?
5. Does it improve testability?
6. Does it preserve an architectural boundary?

Reject unnecessary abstraction-driven complexity.

Examples requiring scrutiny:

- generic repositories
- unnecessary factories
- speculative strategies
- unnecessary base classes
- unused interfaces
- unnecessary Unit of Work
- unnecessary event systems

---

# 16. Design Pattern Verification

For every significant design pattern ask:

1. What problem does it solve?
2. Why is simpler code insufficient?
3. Does it improve maintainability?
4. Does it reduce coupling or isolate variation?
5. Is it consistent with the architecture?
6. Does its complexity justify its benefit?

Reject pattern-driven complexity that exists primarily for appearance.

---

# 17. Structure Verification

Where applicable verify that the module follows the established structure:

```text
domain/
application/
infra/
repositories/
```

Do not mechanically require every layer.

Verify that each package owns a meaningful responsibility.

Check for:

- misplaced files
- duplicate responsibilities
- infrastructure inside domain
- business logic inside routers
- persistence logic inside application services
- API concerns inside domain objects

---

# 18. Domain Verification

Verify that domain code:

- represents domain concepts
- contains appropriate invariants
- contains appropriate lifecycle behavior
- does not depend on infrastructure
- does not depend on FastAPI
- does not depend on ORM implementation details
- remains testable independently

Do not require domain abstractions where the architecture does not need them.

---

# 19. Application Verification

Verify that application services:

- coordinate use cases
- invoke appropriate authorization
- use appropriate contracts
- manage orchestration
- respect transaction boundaries
- return appropriate DTO/domain results
- do not directly manipulate ORM internals
- do not contain HTTP concerns

Check for oversized application services.

---

# 20. DTO Verification

Verify that DTOs:

- represent the intended contract
- validate appropriate external input
- expose only intended fields
- do not expose persistence models
- do not contain unnecessary implementation details
- use meaningful names

Check both request and response DTOs.

---

# 21. Persistence Verification

Verify:

- application does not depend unnecessarily on ORM details
- persistence contracts are meaningful
- infrastructure implements the appropriate contract
- DTOs do not expose persistence models
- mappings are correct
- database constraints match requirements
- transaction behavior is correct

Inspect actual database models and migrations.

Do not verify persistence solely from Python ORM declarations.

---

# 22. Migration Verification

For every migration verify:

- correct revision ordering
- correct upgrade behavior
- correct schema
- correct foreign keys
- correct indexes
- correct constraints
- correct nullability
- appropriate delete behavior
- compatibility with existing migrations

Do not rewrite historical migrations to conceal implementation errors.

Verify that duplicate corrective migrations are not unnecessarily left behind.

---

# 23. Database Integrity Verification

Check database-level invariants.

Where appropriate verify:

- primary keys
- foreign keys
- unique constraints
- not-null constraints
- indexes
- cascading behavior

Application pre-checks are not sufficient for concurrency-sensitive invariants.

---

# 24. Transaction Verification

Verify:

- transaction boundaries
- commit ownership
- rollback behavior
- partial failure behavior
- flush behavior
- multi-step atomicity

For operations requiring multiple writes, verify that a failure does not leave invalid partial state.

Do not introduce unnecessary transaction abstractions.

---

# 25. API Verification

Verify:

- HTTP method
- path
- request validation
- response contract
- status codes
- error behavior
- authorization
- dependency injection
- pagination
- project isolation

Routers must remain thin.

Do not allow direct database access from API handlers.

---

# 26. Authorization Verification

For every protected operation verify:

1. current user is resolved correctly
2. resource is resolved correctly
3. owning Project is determined correctly
4. ProjectAuthorization is invoked
5. required permission is correct
6. unauthorized behavior is correct

Check for authorization bypasses through:

- direct IDs
- alternate routes
- repository queries
- background operations
- administrative shortcuts

Do not introduce Repository-level RBAC without an explicit architectural requirement.

---

# 27. Isolation Verification

Verify that users cannot access or mutate resources belonging to projects they do not have access to.

Test:

- direct resource lookup
- list endpoints
- update
- delete
- repository registration
- nested resources
- alternate identifiers

Where the architecture requires not-found behavior to prevent enumeration, verify that unauthorized resources do not leak their existence.

---

# 28. Security Verification

Verify that:

- external input is validated
- authorization is enforced
- secrets are protected
- sensitive values are not logged
- stack traces are not exposed
- repository content is untrusted
- repository-controlled code is not executed
- unsafe paths are rejected
- resource limits are respected

Security verification must include negative cases.

---

# 29. Untrusted Repository Verification

For repository-related functionality explicitly inspect whether the implementation:

- executes repository scripts
- imports repository code
- executes build commands
- installs repository-controlled packages
- invokes arbitrary shell commands
- trusts repository configuration as executable instructions

Any unauthorized execution of repository-controlled content is a critical finding.

---

# 30. Error Verification

Verify that failures map correctly to the project's error architecture.

Check:

- validation
- authorization
- not found
- conflict
- domain failure
- infrastructure failure
- unexpected failure

Verify:

- error code
- error category
- HTTP status
- response structure
- information disclosure

Do not allow raw ORM/database exceptions to leak through application boundaries.

---

# 31. Concurrency Verification

Identify concurrency-sensitive operations.

Check:

- duplicate creation
- concurrent updates
- concurrent deletion
- duplicate access grants
- conflicting lifecycle transitions

Verify that database constraints or appropriate transaction behavior protect required invariants.

Application pre-checks alone should not be considered sufficient when races are possible.

---

# 32. Functional Test Verification

Run or inspect relevant tests.

At minimum, where applicable:

```text
unit tests
integration tests
API tests
authorization tests
isolation tests
architecture tests
migration tests
regression tests
```

Verify that tests prove behavior rather than merely execute code.

---

# 33. Test Quality Verification

Inspect tests for:

- meaningful assertions
- positive cases
- negative cases
- authorization failures
- isolation failures
- conflict behavior
- not-found behavior
- lifecycle behavior
- persistence behavior
- transaction failures
- regression behavior

Look for tests that accidentally mock away the behavior they claim to verify.

Do not accept test quantity as evidence of quality.

---

# 34. Architecture Test Verification

Run architecture tests where available.

Verify:

- absolute imports
- module boundaries
- forbidden dependencies
- forbidden Organization references
- M1/M2 preservation
- M3/M4 separation
- domain/infrastructure separation
- accidental duplicate modules

Architecture tests should protect important architectural decisions.

---

# 35. Static Verification

Run applicable static checks:

```text
ruff
black
mypy
```

and any project-specific tools.

Interpret failures rather than blindly suppressing them.

Do not add broad lint/type ignores to conceal design problems.

---

# 36. Migration Verification

Run appropriate migration checks.

Verify:

- current revision
- upgrade path
- schema generation
- database compatibility
- migration consistency

Where practical, test migration behavior against a clean database.

---

# 37. Full Regression Verification

After feature-specific tests pass, run the broader test suite.

Verify that:

- M1 still works
- M2 still works
- existing APIs still work
- existing authorization still works
- existing architecture tests still pass
- existing database behavior remains valid

A feature is not complete if it breaks frozen behavior.

---

# 38. Verification Evidence

Use concrete evidence.

Acceptable evidence includes:

- test results
- static analysis results
- migration output
- source inspection
- architecture checks
- database checks
- API tests
- integration tests

Do not write:

```text
Everything looks good.
```

Instead record:

```text
pytest:
PASS

ruff:
PASS

architecture tests:
PASS

migration verification:
PASS
```

where those checks were actually performed.

---

# 39. Failed Verification

When verification fails:

1. reproduce the failure
2. identify the actual cause
3. compare behavior against architecture
4. determine whether implementation or test is incorrect
5. correct the implementation when necessary
6. rerun affected verification
7. run regression verification

Do not weaken tests simply to produce a green result.

Do not suppress verification failures without understanding them.

---

# 40. Verification Order

Prefer the following sequence:

```text
Architecture Inspection
        ↓
Source Inspection
        ↓
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
Full Regression Suite
        ↓
Final Diff Inspection
```

Adjust the sequence to the repository tooling where necessary.

---

# 41. Final Diff Verification

Inspect the final change set.

Check for:

- unintended files
- debug code
- temporary files
- generated artifacts
- secrets
- accidental migrations
- duplicate modules
- unrelated refactoring
- weakened tests
- unexpected dependency changes
- architectural violations

The final diff must correspond to the intended implementation scope.

---

# 42. Builder Claim Verification

The Builder may report:

```text
Implemented
Tested
Verified
Complete
```

These statements are not evidence by themselves.

Independently inspect:

- source
- tests
- migrations
- configuration
- verification output
- architectural boundaries

Verification must be evidence-driven.

---

# 43. Review Readiness

Verification should produce enough evidence for the Independent Reviewer to audit the implementation efficiently.

Record:

```text
Module:
Scope:
Implemented capabilities:
Tests:
Verification commands:
Results:
Migration status:
Architecture status:
Security status:
Known issues:
```

Do not declare architectural approval.

Independent review remains separate.

---

# 44. Freeze Readiness

A module is not ready for freeze if it is functionally correct but has a significant:

- architectural defect
- security defect
- persistence defect
- boundary violation
- maintainability defect
- testability defect

Correctness includes:

```text
Behavior
+
Architecture
+
Security
+
Maintainability
+
Testability
```

Passing tests alone does not establish freeze readiness.

---

# 45. Definition of Done

Verification is complete only when:

- [ ] Functional behavior is verified
- [ ] Architecture is verified
- [ ] Module boundaries are verified
- [ ] Frozen contracts are verified
- [ ] Authorization is verified
- [ ] Project isolation is verified
- [ ] Security is verified
- [ ] Persistence is verified
- [ ] Migrations are verified
- [ ] Tests are meaningful and passing
- [ ] Static analysis is passing where configured
- [ ] Architecture tests are passing
- [ ] Regression tests are passing
- [ ] Final diff is inspected
- [ ] Evidence is recorded
- [ ] Known issues are explicitly documented

---

# 46. Verification Result

The verification result should be one of:

```text
READY FOR INDEPENDENT REVIEW
```

or:

```text
VERIFICATION FAILED
```

Use `READY FOR INDEPENDENT REVIEW` only when the implementation satisfies the applicable verification requirements.

Do not use verification to declare the module frozen.

Freeze remains subject to independent review.

---

# 47. Final Principle

Verification is not simply:

```text
Does the code run?
```

It is:

```text
Does the implementation work correctly?

+
Does it follow the authoritative architecture?

+
Does it preserve frozen contracts?

+
Does it respect module boundaries?

+
Is it secure?

+
Is it maintainable?

+
Is it testable?

+
Can another engineer independently verify it?
```

A green test suite is evidence of correctness, not proof of architectural correctness.

Verify behavior.

Verify architecture.

Verify boundaries.

Verify security.

Verify persistence.

Verify regressions.

Then hand the implementation to the independent Reviewer.