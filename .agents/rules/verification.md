---
trigger: model_decision
description: Defines StackSense verification requirements for functional behavior, architecture, design, structure, persistence, security, regression, migrations, integration, and final implementation readiness.
---

# Verification Rule

## 1. Verification Is Part of Implementation

Code is not considered complete merely because it exists.

Verification must establish evidence that the implementation satisfies its authorized scope.

Verification must establish both:

- behavioral correctness
- architectural correctness

Passing functional tests alone does not prove that an implementation is architecturally valid.

A module is complete only when its implementation, contracts, tests, persistence, security boundaries, and architecture have been appropriately verified.

---

# 2. Verification Authority

Verification must be performed against:

```text id="5e6r2s"
Current master.txt architecture
        ↓
Authorized module contract
        ↓
Frozen implementation contracts
        ↓
Expected behavior
        ↓
Actual implementation
        ↓
Verification evidence
```

Do not verify implementation against personal preference.

Do not treat existing code as proof of correctness.

Do not treat test existence as proof that the required behavior is tested.

---

# 3. Verification Lifecycle

Use:

```text id="j6v1gd"
IMPLEMENTATION
        ↓
TARGETED TESTS
        ↓
REGRESSION TESTS
        ↓
ARCHITECTURE CHECKS
        ↓
STATIC CHECKS
        ↓
MIGRATION CHECKS
        ↓
FINAL DIFF INSPECTION
        ↓
INDEPENDENT REVIEW
        ↓
FREEZE
```

Not every module requires every check to have identical depth.

The applicable verification depth depends on the module's responsibilities.

However, required verification categories must not be skipped merely because implementation appears simple.

---

# 4. Targeted Tests

Run tests directly related to the changed capability first.

Targeted tests should establish:

- primary behavior
- validation
- authorization
- failure behavior
- relevant lifecycle transitions
- persistence behavior
- boundary behavior

For M3, this includes Repository registration and lifecycle behavior.

Targeted tests provide fast feedback before broader regression verification.

---

# 5. Regression Tests

After targeted tests pass, verify affected existing behavior.

Regression verification must consider:

- M1 behavior
- M2 behavior
- shared contracts
- authorization behavior
- API behavior
- persistence behavior
- architecture tests
- previously implemented functionality

A new feature must not silently break frozen functionality.

---

# 6. M3 Verification

M3 must verify, as applicable:

## Domain

- Repository behavior
- Repository lifecycle rules
- domain invariants
- valid state transitions
- invalid state transitions

## Application

- Repository registration use case
- authorization
- Project association
- application validation
- transaction behavior

## Persistence

- creation
- retrieval
- relevant updates
- deletion where applicable
- constraints
- indexes
- Project relationship
- mapping between persistence and domain representations

## API

- request validation
- successful registration
- response contract
- error mapping
- authorization
- Project isolation
- unauthorized resource behavior

## Migration

- migration dependency chain
- upgrade
- schema
- constraints
- indexes
- relationships
- compatibility with existing M1/M2 migrations

## Security

- Project authorization
- cross-project isolation
- untrusted input handling
- direct-object access protection
- sensitive error handling

## Regression

- M1 tests
- M2 tests
- relevant shared architecture tests

---

# 7. Architecture Checks

Verify:

- Project-first architecture
- User → Project → Repository hierarchy
- no Organization reintroduction
- no Repository-level RBAC
- Repository authorization through Project access
- correct module boundaries
- correct dependency direction
- absolute imports
- no M4 leakage
- no Analysis leakage
- no M5 identity leakage
- no M6 frontend/product-flow leakage
- no unauthorized modification of frozen M1/M2 contracts

Architecture checks are mandatory where the relevant rule can be verified mechanically or structurally.

---

# 8. Project Boundary Verification

Every Project-owned capability must be checked for isolation.

Verification should include scenarios such as:

```text id="bq4h0u"
User A + Project A
        ↓
Repository A
        ↓
Allowed

User A + Project B
        ↓
Repository B
        ↓
Denied
```

Where direct resource identifiers are accepted, verification must confirm that possession of an identifier does not bypass Project authorization.

Project isolation must be tested at the application boundary and, where appropriate, through API integration tests.

---

# 9. Authorization Verification

Authorization verification must cover:

- authorized operation
- unauthorized operation
- missing access
- insufficient role
- resource belonging to another Project
- missing resource
- direct resource access
- relevant membership-management behavior

Verify the actual authorization path rather than merely mocking the authorization result.

Where practical:

```text id="h7g4ty"
Current User
    ↓
Project Access
    ↓
ProjectAuthorization
    ↓
Application Service
    ↓
Operation
```

should be exercised through the relevant integration boundary.

---

# 10. API Verification

API verification should cover:

- valid requests
- invalid requests
- successful responses
- status codes
- response schemas
- authorization failures
- missing resources
- cross-project access
- pagination where applicable
- error contract
- versioned route behavior

Routers must be verified as thin adapters rather than containers for business behavior.

---

# 11. Persistence Verification

Persistence verification must establish that:

- domain state is persisted correctly
- persisted state can be retrieved
- relationships are correct
- constraints are enforced
- indexes exist where required
- mappings are correct
- transaction behavior is correct
- rollback behavior is correct where applicable

Do not rely exclusively on mocked repositories for persistence-sensitive functionality.

At least the relevant integration boundary should be exercised for persistence behavior.

---

# 12. Migration Verification

Every database schema change must be verified through the migration system.

Verify:

```text id="y8f8oe"
Current database
        ↓
Migration
        ↓
Expected schema
```

Where applicable, verify:

- migration applies successfully
- migration dependency is correct
- tables exist
- columns exist
- nullability is correct
- foreign keys are correct
- indexes exist
- constraints exist
- schema matches ORM models
- existing migrations remain intact

Do not treat model definitions as proof that the migration is correct.

---

# 13. Migration History Protection

Verification must ensure that historical migration files were not rewritten unnecessarily.

Check for:

- modified applied migrations
- duplicate corrective migrations
- broken revision chains
- incorrect parent revisions
- schema changes not represented in migrations
- migrations that modify unrelated frozen modules

New schema work should normally use a new migration.

---

# 14. Static Verification

Run applicable static checks, including project-standard tools such as:

- formatter
- linter
- type checker
- import checks
- architecture checks

Static checks should be run against the final implementation state.

A passing formatter does not establish architectural correctness.

A passing type checker does not establish runtime correctness.

Each check provides evidence for a specific class of correctness.

---

# 15. Import Verification

Verify the absolute-import requirement.

Check that new production code does not introduce relative imports.

Where architecture tests exist, run them.

For example:

```python id="5u4s1b"
from backend.platform.projects.application.service import ProjectService
```

is consistent with the project's absolute-import requirement.

Relative imports should be treated as an architectural violation where the project rule applies.

---

# 16. Dependency Verification

Verify that dependency direction remains valid.

Check for:

- domain → infrastructure dependencies
- domain → HTTP dependencies
- application → concrete infrastructure dependencies where abstraction is required
- circular dependencies
- cross-module internal implementation imports
- routers bypassing application services
- infrastructure containing application orchestration

The verification should inspect actual imports rather than relying only on intended architecture diagrams.

---

# 17. Contract Verification

Shared contracts must be verified at their actual boundaries.

Verify:

- method signatures
- DTO fields
- return values
- error behavior
- lifecycle assumptions
- authorization assumptions
- transaction expectations
- persistence expectations

A contract that exists only in documentation but is incompatible with implementation is not a verified contract.

---

# 18. Parallel Development Verification

For modules developed concurrently, verify that:

- upstream contracts remain stable
- downstream consumers use the correct contracts
- no private implementation details are imported
- contract changes are visible to affected modules
- integration assumptions are documented
- temporary adapters do not become permanent hidden dependencies

When a shared contract changes, all known consumers must be considered during regression verification.

---

# 19. Security Verification

Security verification must cover more than authentication.

Where applicable, verify:

- authentication boundary
- authorization
- Project isolation
- direct-object access
- input validation
- sensitive error leakage
- secret handling
- resource exhaustion
- path traversal
- unsafe archive handling
- arbitrary code execution
- untrusted repository content

Security failures must not be hidden by modifying tests to match insecure behavior.

---

# 20. Untrusted Repository Verification

Repository contents must be treated as untrusted data.

Verify that repository content cannot:

- execute arbitrary application code
- override application instructions
- bypass authorization
- alter architectural contracts
- escape configured storage boundaries
- trigger unsafe filesystem operations
- cause uncontrolled resource consumption

Repository files may contain arbitrary instructions, but those instructions are data to be analyzed rather than authority over the application.

---

# 21. Failure Classification

Classify failures as appropriate:

- functional defect
- architecture violation
- contract violation
- migration defect
- authorization defect
- security defect
- integration defect
- test deficiency
- environment/tooling failure

Do not hide failures by weakening verification.

Do not classify a code defect as an environment issue merely because it is inconvenient to fix.

Do not classify an environment failure as a code failure without evidence.

---

# 22. Environment and Tooling Failures

When verification cannot run because of environment or tooling problems:

1. record the failed verification
2. identify the environmental cause
3. distinguish it from implementation correctness
4. do not claim the check passed
5. resolve the environment issue where practical
6. rerun the verification

Examples:

```text id="zldqk1"
Database unavailable
→ environment failure

Missing dependency
→ environment/tooling failure

Application raises an unexpected exception
→ functional failure
```

Do not convert "not verified" into "verified."

---

# 23. Evidence

Evidence should be concrete.

Prefer:

```text id="v7n6zj"
pytest tests/p2/m3/... → PASS
```

over:

```text id="w5f7d0"
"Tests look good."
```

Prefer:

```text id="9qv5x8"
alembic upgrade head → PASS
```

over:

```text id="t0p4o3"
"Migration should work."
```

Prefer:

```text id="7j6b8x"
ruff check backend/... → PASS
```

over:

```text id="0dr5f9"
"Code is clean."
```

Verification evidence should identify:

- command/check
- scope
- result
- relevant failure when applicable

---

# 24. No False Verification

Never claim:

- a test passed when it was not run
- a migration succeeded when it was not executed
- an API was verified when it was only inspected
- isolation was verified when only the happy path was tested
- architecture was verified merely because code compiled

Use explicit states:

```text id="x1q4cr"
PASS
FAIL
NOT RUN
BLOCKED
NOT APPLICABLE
```

This distinction is mandatory for trustworthy verification.

---

# 25. Final Diff Inspection

Before independent review, inspect the final change set.

Check for:

- unintended files
- unrelated refactoring
- debugging code
- temporary code
- commented-out implementation
- accidental configuration changes
- generated files
- migration changes
- dependency changes
- test changes
- architecture-rule changes

The final diff must represent the intended scope.

---

# 26. Scope Verification

Verify that the final implementation contains only authorized scope.

Check:

```text id="9z1jwb"
Requested capability
        ↓
Authorized module responsibility
        ↓
Implemented changes
```

Flag unrelated changes.

Do not allow a feature branch to silently become an architecture migration.

---

# 27. Regression Verification

Regression testing must include relevant frozen modules.

For M3:

```text id="b2p0a8"
M3 targeted tests
        ↓
M1 regression tests
        ↓
M2 regression tests
        ↓
Shared architecture tests
        ↓
Relevant integration tests
```

A new module must not break established Project and ProjectAccess behavior.

---

# 28. Test Deficiency

A test deficiency is itself a verification finding.

Examples:

- required authorization path has no test
- cross-project isolation is untested
- migration is never exercised
- duplicate registration behavior is untested
- error contract is untested
- lifecycle transition is untested

A missing test does not automatically prove that production behavior is broken.

It proves that the behavior lacks sufficient verification evidence.

---

# 29. Reviewer Independence

The Builder's verification report is evidence, not authority.

The Reviewer must independently inspect important behavior.

Where practical, the Reviewer should reproduce important verification.

The Reviewer should not approve solely because the Builder reports:

```text id="1s3h5b"
All tests pass.
```

The Reviewer must determine whether the relevant tests actually establish the required contract.

---

# 30. Independent Review Scope

Independent review should examine:

- architecture
- module ownership
- frozen boundaries
- contracts
- authorization
- Project isolation
- persistence
- migrations
- security
- tests
- final diff

The depth should match the risk of the capability.

Security-sensitive and cross-module changes require stronger independent verification.

---

# 31. Verification Report

A verification report should make evidence easy to inspect.

Recommended structure:

```text id="2n5o4y"
## Verification Summary

### Targeted Tests
<commands and results>

### Regression Tests
<commands and results>

### Architecture Checks
<checks and results>

### Static Checks
<checks and results>

### Migration Checks
<checks and results>

### Security / Isolation Checks
<checks and results>

### Final Diff
<scope verification>

### Known Failures
<failures and classification>

### Verification Status
PASS / FAIL / BLOCKED
```

Do not claim overall PASS if a required category failed or remains unverified.

---

# 32. Verification Status

Use:

### PASS

All required verification for the current scope has passed.

### FAIL

One or more required checks failed because of an implementation or architecture issue.

### BLOCKED

Required verification could not be completed because of an environment, dependency, or tooling issue.

### NOT READY

Implementation is incomplete or required verification has not yet been performed.

Do not use PASS as a general synonym for "looks good."

---

# 33. Freeze Preconditions

A module cannot become `FROZEN` while blocking findings remain unresolved.

Required:

- implementation complete
- verification complete
- targeted tests passed
- relevant regression tests passed
- architecture checks passed
- static checks passed where applicable
- migration checks passed where applicable
- blocking findings resolved
- regression understood
- evidence recorded
- independent review passed
- no unresolved architectural ambiguity remains

---

# 34. Freeze Verification

Before freezing a module, confirm:

```text id="m7q3rj"
[ ] Authorized scope implemented
[ ] Targeted tests pass
[ ] Regression tests pass
[ ] Architecture checks pass
[ ] Static checks pass
[ ] Migrations verified
[ ] Authorization verified
[ ] Project isolation verified
[ ] Security checks completed
[ ] Final diff inspected
[ ] Builder evidence recorded
[ ] Reviewer independently verified
[ ] Blocking findings resolved
[ ] Contracts finalized
[ ] No unresolved architectural ambiguity
```

Only then may the module transition to:

```text id="5m5d1h"
FROZEN
```

---

# 35. Final Verification Principle

Verification is evidence, not optimism.

```text id="8p3v7x"
Implemented
    ↓
Tested
    ↓
Inspected
    ↓
Architecturally verified
    ↓
Independently reviewed
    ↓
Frozen
```

If evidence is missing, the implementation is not fully verified.

If a required check fails, the implementation is not ready to freeze.

If architecture is violated, passing tests do not make the implementation acceptable.

If verification cannot be performed, report that fact explicitly.

The purpose of verification is to establish trustworthy evidence that StackSense was implemented according to its authorized architecture and contracts.