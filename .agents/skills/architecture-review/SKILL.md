---
name: architecture-review
description: Independently review StackSense implementations against the current master.txt architecture, module boundaries, frozen contracts, dependency direction, security boundaries, and Project isolation. Use when auditing completed or in-progress implementation work.
---

# Architecture Review Skill

## 1. Purpose

Use this skill to independently determine whether an implementation conforms to the current StackSense architecture.

The review must evaluate both:

```text
Architectural correctness
+
Implementation correctness
```

The objective is not to redesign the system.

The objective is to determine whether the implementation is consistent with the architecture that StackSense has already authorized.

---

# 2. Review Authority

Use this authority order:

```text id="u6x5c4"
System / Developer instructions
        ↓
Current master.txt baseline
        ↓
Explicit authorized architectural decisions
        ↓
Active module context
        ↓
Frozen implementation contracts
        ↓
Existing implementation
        ↓
Reviewer preference
```

Reviewer preference must never become an architectural requirement.

Do not reject an implementation simply because another design would be personally preferred.

---

# 3. Review Independence

The Reviewer must independently inspect the implementation.

Do not assume the Builder's conclusions are correct.

Do not treat:

```text id="j5q7ly"
"Tests pass"
```

as proof of architectural correctness.

Do not treat:

```text id="2w6v6k"
"The Builder planned it this way"
```

as proof of architectural ownership.

The Reviewer must independently verify important claims.

---

# 4. Review Inputs

Before beginning a review, establish:

- current `master.txt` baseline
- relevant architectural sections
- active module context
- frozen module contracts
- changed files
- migrations
- tests
- API changes
- dependency changes
- configuration changes
- relevant security boundaries

Review the actual implementation rather than relying only on summaries.

---

# 5. Review Sequence

Use:

```text id="b2br0r"
1. Establish current architecture
        ↓
2. Identify module ownership
        ↓
3. Inspect implementation scope
        ↓
4. Inspect dependencies
        ↓
5. Inspect domain/application/infrastructure boundaries
        ↓
6. Inspect persistence and migrations
        ↓
7. Inspect authorization and isolation
        ↓
8. Inspect security
        ↓
9. Inspect tests
        ↓
10. Inspect final diff
        ↓
11. Classify findings
        ↓
12. Determine review readiness
```

Do not begin by searching for stylistic problems.

Begin with architecture and responsibility.

---

# 6. Current Resource Model

Verify that the current P2 resource hierarchy remains:

```text id="5z3k2m"
User
  ↓
Project
  ↓
Repository
```

Project remains the primary:

- ownership boundary
- access-control boundary
- authorization boundary
- collaboration boundary
- isolation boundary

below User.

Repository belongs to Project.

---

# 7. Organization Regression Review

Verify that Organization has not been reintroduced without authorization.

Check for:

- Organization entity
- Organization repository
- Organization service
- Organization membership
- Organization roles
- organization-scoped authorization
- `organization_id`
- organization API routes
- organization-level ownership

Do not flag historical references merely because they exist in `master.txt`.

Determine whether the implementation actually introduces Organization into the current architecture.

---

# 8. Frozen Module Review

Current frozen P2 modules:

```text id="rxu0q7"
M1 — Project Domain Foundation
M2 — Project Access & Resource Boundary
```

Verify that active work does not casually alter:

- Project domain contracts
- ProjectAccess
- authorization semantics
- Project persistence
- frozen migrations
- established API behavior
- frozen tests

If a frozen change is explicitly authorized, verify that the implementation matches the authorization.

---

# 9. Module Ownership Review

For every significant implementation component, determine:

```text id="1umjv8"
What responsibility does it implement?
Which module owns that responsibility?
Is it implemented inside that module?
Does it create an unauthorized dependency?
```

Current P2 boundaries:

```text id="4x9w7e"
M1 → Project Domain Foundation
M2 → Project Access & Resource Boundary
M3 → Repository Domain & Registration
M4 → Repository Ingestion, Validation & Storage
M5 → Identity & Authentication
M6 → P2 API & Frontend Product Flow
M7 → Integration, Evaluation & P2 Freeze
```

Do not judge module ownership based solely on file names.

Use the architectural responsibility.

---

# 10. M3 Review

For M3, verify that the implementation remains within:

```text id="9yq3w2"
Repository Domain & Registration
```

Expected responsibilities include:

- Repository domain model
- Repository lifecycle
- Repository persistence
- Repository repository contracts
- Repository application services
- Repository registration
- Repository registration metadata
- Project relationship
- Project-derived authorization
- Repository DTOs
- relevant tests

Flag unauthorized implementation of:

- repository acquisition
- ingestion
- snapshot processing
- artifact inventory
- source parsing
- architecture analysis
- identity
- frontend product flow

---

# 11. M4 Leakage Review

Verify that M3 does not absorb M4.

M4 owns:

- repository acquisition
- ingestion
- validation
- safe storage
- snapshots
- revisions
- artifact inventory
- ingestion lifecycle
- repository-content resource limits
- untrusted repository-content handling

A Repository creation use case may establish the contract needed to trigger or later coordinate ingestion, but that does not make ingestion an M3 responsibility.

---

# 12. Repository Authorization Review

Verify that Repository access derives from Project access.

Expected:

```text id="2fh6zv"
Repository
    ↓
project_id
    ↓
ProjectAuthorization
    ↓
ProjectAccess
    ↓
Allowed / Denied
```

Flag:

- Repository-specific RBAC
- repository-specific roles
- direct authorization based only on Repository ID
- authorization duplicated across routers and services
- direct persistence access that bypasses Project authorization
- missing Project ownership checks

---

# 13. Project Isolation Review

Test or inspect whether Project isolation is preserved.

Verify that:

```text id="j5jv1r"
User A + Project A
```

cannot access:

```text id="5y0w0r"
Project B resources
```

through:

- Repository IDs
- Project IDs
- API paths
- service calls
- database queries
- background jobs
- cache state
- internal identifiers

Cross-project isolation is a security invariant, not an optional feature.

---

# 14. Dependency Direction Review

Verify the dependency structure.

Expected general direction:

```text id="3qf3v6"
API / Presentation
        ↓
Application
        ↓
Domain
        ↑
Infrastructure implementations
```

Inspect actual imports.

Flag:

- domain → infrastructure
- domain → HTTP
- domain → ORM
- application → unnecessary concrete infrastructure
- circular dependencies
- router → direct database orchestration
- cross-module internal implementation imports

Do not rely only on package names.

---

# 15. Domain Review

Verify that domain code owns:

- domain state
- domain behavior
- invariants
- lifecycle

Flag domain code containing unnecessary:

- SQLAlchemy sessions
- ORM persistence models
- FastAPI request objects
- HTTP responses
- external clients
- infrastructure configuration

Domain code should not become an infrastructure wrapper.

---

# 16. Application Review

Verify that application services own:

- use-case orchestration
- application authorization coordination
- transaction coordination
- repository coordination
- application contracts

Flag:

- god services
- direct HTTP behavior
- direct infrastructure construction where DI is expected
- unrelated responsibilities
- persistence-specific business orchestration

Application services should remain cohesive.

---

# 17. Infrastructure Review

Verify that infrastructure owns:

- ORM models
- persistence
- database adapters
- external integrations
- concrete implementations of contracts

Flag infrastructure that silently introduces:

- business rules
- application orchestration
- authorization policies
- domain ownership decisions

unless explicitly required by architecture.

---

# 18. Repository Review

Verify that repository implementations remain persistence-focused.

Check:

- domain/persistence mapping
- CRUD behavior
- transaction behavior
- query correctness
- Project relationship
- appropriate indexes
- no hidden application orchestration
- no independent transaction commits where application transaction ownership applies

Repository implementations should not become hidden service layers.

---

# 19. API Review

Verify the API flow:

```text id="5v3i1w"
HTTP Request
    ↓
Router
    ↓
Dependencies
    ↓
Application Service
    ↓
Domain / Infrastructure
    ↓
Response
```

Flag routers that contain:

- business logic
- authorization rules duplicated from application services
- database orchestration
- transaction coordination
- repository lifecycle logic
- ingestion behavior

Verify versioned API conventions where applicable.

---

# 20. DTO Review

Verify clear separation between:

```text id="8r6z1d"
Request DTO
Response DTO
Domain Model
Persistence Model
```

Flag:

- ORM models exposed through APIs
- domain entities used as transport contracts without justification
- DTOs containing business logic
- ambiguous DTO ownership
- accidental reuse across unrelated contracts

DTOs should represent stable application/API contracts.

---

# 21. Persistence Review

Inspect:

- tables
- columns
- foreign keys
- indexes
- constraints
- nullability
- relationships
- migrations
- transaction behavior

Verify that persistence reflects current architecture.

Specifically verify that the implementation does not reintroduce:

```text id="g5c7j3"
Project.owner_id
organization_id
Repository-level ownership
Repository-level RBAC
```

unless explicitly authorized.

---

# 22. Migration Review

Verify:

- new schema changes use appropriate migrations
- migration dependency chain is correct
- historical migrations remain intact
- no duplicate migration chain exists
- schema matches ORM models
- relationships are correct
- indexes are present where required

Do not approve a schema change solely because the ORM model looks correct.

---

# 23. Transaction Review

Verify that transaction ownership is coherent.

Expected:

```text id="j8b1g5"
Application use case
        ↓
Repository operations
        ↓
Flush
        ↓
Commit
```

Flag:

- unexpected repository commits
- partial multi-write workflows
- transactions spanning unrelated responsibilities
- hidden transaction boundaries

Do not demand Unit of Work merely because multiple writes exist.

---

# 24. Error Contract Review

Verify that application failures use stable typed error contracts.

Check:

- error category
- error code
- HTTP mapping
- authorization behavior
- missing-resource behavior
- conflict behavior
- infrastructure error translation

Flag:

- arbitrary string exceptions
- duplicated error definitions
- SQL/ORM errors exposed to clients
- inconsistent authorization errors

---

# 25. Security Review

Review:

- authentication boundaries
- authorization
- Project isolation
- direct-object access
- input validation
- secret handling
- error leakage
- resource exhaustion
- path traversal
- archive extraction
- arbitrary code execution
- untrusted repository content

Security is part of architectural correctness.

---

# 26. Untrusted Repository Review

Repository content is untrusted.

Verify that implementation does not treat repository content as trusted instructions.

Check for unsafe behavior involving:

- source execution
- shell execution
- arbitrary subprocesses
- unsafe archive extraction
- filesystem traversal
- executable configuration
- repository-provided instructions
- uncontrolled resource usage

Repository content may be analyzed.

It cannot override application authority.

---

# 27. Resource Limit Review

Where applicable, inspect limits for:

- request size
- file size
- file count
- archive expansion
- memory
- processing time
- pagination
- query result size

Do not invent limits during review merely because they seem desirable.

Verify required limits against the applicable architecture and security requirements.

---

# 28. SOLID Review

Review SOLID principles deliberately.

Check whether:

- classes have coherent responsibilities
- extension points are meaningful
- implementations remain substitutable
- interfaces are focused
- dependencies are inverted appropriately

Do not reject code merely because it does not maximize the number of interfaces or abstractions.

The question is whether the design solves an actual dependency or responsibility problem.

---

# 29. Pattern Review

Check whether design patterns are justified.

Potentially valid patterns include:

- Repository
- Strategy
- Factory
- Adapter
- State
- Dependency Injection

Flag patterns that exist solely for architectural appearance.

Also flag missing patterns when the architecture clearly requires a replaceable strategy, adapter, or contract boundary.

---

# 30. Complexity Review

Evaluate whether complexity is proportional to the problem.

Flag:

- unnecessary abstraction layers
- unnecessary wrappers
- speculative extensibility
- premature event systems
- unnecessary CQRS
- unnecessary Unit of Work
- unnecessary factories
- excessive indirection

Do not confuse production quality with maximum abstraction.

---

# 31. Scope Review

Compare the implementation against the authorized scope.

Check:

```text id="h3d0p8"
Requested capability
        ↓
Module responsibility
        ↓
Actual files changed
        ↓
Actual behavior added
```

Flag unrelated:

- refactoring
- renaming
- migrations
- dependency changes
- package restructuring
- architecture changes

unless explicitly authorized or required.

---

# 32. Parallel Development Review

For modules being implemented concurrently, verify:

- upstream contract compatibility
- downstream contract compatibility
- no hidden assumptions
- no private implementation imports
- no duplicated responsibilities
- no unauthorized contract changes
- no direct infrastructure bypass

If a shared contract changed, verify all affected consumers.

---

# 33. Test Review

Inspect tests for:

- success cases
- failure cases
- authorization
- Project isolation
- persistence
- migrations
- lifecycle
- API behavior
- duplicate behavior
- relevant concurrency behavior
- architecture rules

Do not evaluate tests solely by count or coverage.

Determine whether tests protect the actual contract.

---

# 34. Test Deficiency Review

Flag missing tests when a required behavior lacks meaningful verification.

Examples:

```text id="6d6w3p"
Repository registration exists
but duplicate registration is untested.

Authorization exists
but cross-project access is untested.

Migration exists
but migration execution is untested.

Lifecycle exists
but invalid transitions are untested.
```

A missing test is a verification deficiency even when production behavior appears correct.

---

# 35. Architecture Test Review

Verify that architecture tests remain active.

Check for tests covering:

- absolute imports
- dependency boundaries
- forbidden modules
- Organization regression
- Project isolation
- frozen contracts
- API contracts

Flag modifications that weaken architecture tests merely to make implementation pass.

---

# 36. Review Evidence

Findings must be evidence-based.

Evidence may include:

- source code
- imports
- tests
- migrations
- API behavior
- database behavior
- dependency graph
- architecture rules
- `master.txt`

Use concrete references.

Avoid:

```text id="d4a7sa"
"This feels architecturally wrong."
```

Prefer:

```text id="8b3p4e"
RepositoryService directly queries ProjectAccess through a second
authorization implementation instead of using ProjectAuthorization.
This duplicates the established Project authorization boundary.
```

---

# 37. Finding Severity

Use:

### BLOCKER

Fundamental architecture, security, isolation, or correctness violation that prevents integration or freeze.

### HIGH

Significant defect that should be resolved before module completion.

### MEDIUM

Meaningful issue that should be resolved before freeze.

### LOW

Localized maintainability, clarity, or consistency issue.

### NOTE

Observation or optional improvement that does not block completion.

Severity must reflect actual impact.

---

# 38. Finding Format

Use:

```text id="wz8o7a"
Severity: BLOCKER | HIGH | MEDIUM | LOW | NOTE

Location:
<file / component>

Finding:
<what is wrong>

Architectural Basis:
<applicable architecture or contract>

Impact:
<why it matters>

Required Action:
<what should change>
```

Findings must be actionable.

---

# 39. Confirmed vs Potential

Distinguish:

```text id="pl7m9k"
Confirmed
Potential
Unable to verify
```

Do not report speculative behavior as a confirmed defect.

If an important behavior cannot be reproduced, state that limitation.

---

# 40. No Style Policing

Do not reject code merely because:

- naming differs from personal preference
- implementation uses fewer classes
- implementation uses more classes
- another algorithm could be used
- formatting differs while remaining project-compliant
- another internal implementation is aesthetically preferred

Review:

- architecture
- contracts
- correctness
- security
- isolation
- maintainability
- testability

---

# 41. No Silent Fixes

The Reviewer should report findings rather than silently modifying implementation.

Workflow:

```text id="c8j1q7"
Inspect
    ↓
Identify
    ↓
Classify
    ↓
Report
    ↓
Builder corrects
    ↓
Reviewer re-checks
```

This preserves independence between implementation and review.

---

# 42. Re-Review

After corrections, verify:

- original finding is resolved
- correction does not introduce a new violation
- affected tests pass
- contracts remain compatible
- frozen modules remain intact
- security remains intact
- Project isolation remains intact

Do not mark a finding resolved merely because code changed.

Verify the behavior.

---

# 43. Review Output

A complete architecture review should contain:

```text id="t3q4d7"
## Review Scope

<what was reviewed>

## Architectural Basis

<relevant current architecture>

## Findings

<ordered findings by severity>

## Verification

<tests/checks performed>

## Remaining Risks

<known limitations>

## Freeze Readiness

READY / NOT READY
```

Do not bury blockers inside narrative text.

---

# 44. Approval Criteria

Approval requires:

- current architecture respected
- module boundary respected
- frozen contracts preserved
- authorization correct
- Project isolation preserved
- dependency direction correct
- persistence correct
- migrations correct
- security boundaries preserved
- tests sufficiently verify behavior
- no unresolved blocking finding
- no unresolved architectural ambiguity

Approval is bounded by the reviewed scope.

---

# 45. Freeze Decision

The Reviewer may recommend freeze only when:

```text id="6jv8g0"
Implementation complete
        ↓
Verification complete
        ↓
Architecture compliant
        ↓
Security verified
        ↓
Contracts verified
        ↓
Blocking findings resolved
        ↓
Independent review passed
```

The Reviewer should not recommend freeze while a blocker remains unresolved.

---

# 46. Final Architecture Review Checklist

```text id="g4y6l2"
[ ] Current master.txt baseline verified
[ ] Superseded architecture resolved correctly
[ ] Organization not reintroduced
[ ] User → Project → Repository preserved
[ ] Project remains authorization boundary
[ ] Repository-level RBAC not introduced
[ ] M1/M2 frozen contracts preserved
[ ] Active module owns implemented responsibilities
[ ] M4 responsibilities not leaked into M3
[ ] M5 responsibilities not leaked into M3
[ ] M6 responsibilities not leaked into M3
[ ] Dependency direction verified
[ ] Absolute imports preserved
[ ] Domain boundary preserved
[ ] Application boundary preserved
[ ] Infrastructure boundary preserved
[ ] DTO boundaries preserved
[ ] Persistence verified
[ ] Migration history preserved
[ ] Transaction boundaries verified
[ ] Error contracts verified
[ ] Project isolation verified
[ ] Security reviewed
[ ] Repository content treated as untrusted
[ ] Resource limits reviewed where applicable
[ ] Tests verify actual contracts
[ ] Architecture tests remain effective
[ ] Final diff reviewed
[ ] No unauthorized scope expansion
[ ] No unresolved blocker
```

---

# 47. Final Principle

The architecture review exists to protect StackSense from architectural drift.

```text id="f8a6yr"
Current Architecture
        ↓
Module Contract
        ↓
Actual Implementation
        ↓
Independent Verification
        ↓
Concrete Findings
        ↓
Correction
        ↓
Re-Review
        ↓
Freeze
```

The Reviewer must be independent, evidence-driven, architecture-aware, and resistant to implementation convenience.

The objective is not to make the code look like the Reviewer's preferred design.

The objective is to verify that the code faithfully implements the architecture StackSense has authorized.