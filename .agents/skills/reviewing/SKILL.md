
---
name: reviewing
description: >
  Independently reviews software changes against requirements, approved plans,
  project architecture, engineering principles, security, reliability, and test
  quality. Verifies implementation evidence and PROJECT_CONTEXT.md execution
  records, then produces a severity-ranked report with actionable findings.
  Use after implementing a module, feature, phase task, or significant refactor,
  or when independently auditing existing changes.
---

# Reviewing Skill

## Objective

Perform an independent, evidence-based review of software changes.

Determine whether the implementation satisfies its requirements and acceptance
criteria, follows the approved plan, respects the project's architecture, and
has adequate verification evidence.

Prioritize correctness, security, reliability, regression prevention, and
architectural integrity over personal preferences.

**Read-only by default.** Inspect, verify, and report. Do not modify source
code, tests, configuration, approved plans, or PROJECT_CONTEXT.md during
review. Make changes only when the user explicitly authorizes remediation,
and then keep remediation separate from the review findings.

## 1. Establish Review Context

Before reviewing:

1. Identify the repository root and applicable agent instructions.
2. Inspect Git status, branch, relevant diffs, and recent history when useful.
3. Identify the requested scope and distinguish task changes from unrelated
   or pre-existing work.
4. Read PROJECT_CONTEXT.md if present.
5. Locate the approved plan, requirements, acceptance criteria, architecture
   documents, and relevant decisions or ADRs.
6. Inspect affected code, callers, dependencies, tests, and configuration.
7. Identify the project's language, framework, architecture, and quality tools.

Preserve all user and collaborator changes. Never assume every working-tree
modification belongs to the task under review.

If PROJECT_CONTEXT.md or an approved plan is absent, incomplete, or outdated,
continue using available evidence and state the limitation when material.
Do not invent missing requirements or assume a plan was approved.

## 2. Establish Evidence Before Judging

Read the implementation and enough surrounding code to understand its actual
behavior. Trace relevant execution paths, data flow, dependencies, public
contracts, persistence, and error handling.

Use the repository's actual architecture and conventions. Do not infer a
violation from a directory name or isolated code fragment.

Classify observations as:

- **Confirmed defect:** Supported by code, reproduction, or verification.
- **Unverified risk:** Plausible concern that available evidence cannot confirm.
- **Verification gap:** A required or important check has not been established.
- **Informational:** A useful observation or optional improvement, not a defect.

Do not present speculation as fact. Do not reject sound code merely because
another implementation is possible.

## 3. Functional Correctness and Requirements

Check the implementation against stated requirements and the approved plan.

Consider, where relevant:

- Missing functionality or unmet acceptance criteria.
- Incorrect business logic, algorithms, assumptions, or edge cases.
- Invalid state transitions, inconsistent data, or transaction boundaries.
- Input validation, error handling, and failure recovery.
- API contracts, serialization, compatibility, and response behavior.
- Resource leaks, race conditions, concurrency, retries, and idempotency.
- Incorrect dependency wiring, configuration, or persistence behavior.
- Accidental deletions, unintended behavior changes, and regressions.

Trace the relevant path before claiming a defect. Focus testing and analysis on
the realistic risks introduced by the change.

## 4. Architecture and Engineering Review

Evaluate against the project's actual design and established conventions.

### Design principles

Check for coherent responsibilities, appropriate module boundaries, high
cohesion, low coupling, unnecessary duplication, oversized components, and
abstractions that add complexity without value.

Apply SOLID pragmatically. Do not demand a redesign solely because an
alternative design exists.

### Dependency injection and dependency direction

Where appropriate, inspect dependency construction, registrations, interfaces,
and wiring. Identify concrete problems such as hidden dependencies, improper
infrastructure coupling, circular dependencies, or incorrect registrations.

Do not require dependency injection for trivial objects without meaningful
external dependencies.

### Layers, contracts, and data transfer

Where the architecture uses them, review domain, application, presentation,
and infrastructure boundaries; repository and service responsibilities;
DTOs; persistence models; and error contracts.

Check that business logic and persistence responsibilities are placed
appropriately, dependencies follow intended direction, and public contracts
remain consistent.

Treat repositories, services, interfaces, DTOs, and specific directory
structures as context-dependent design choices, not mandatory boilerplate.
Report missing abstractions only when requirements or architecture justify them.

## 5. Security and Reliability

Assess risks relevant to the change, including:

- Authentication, authorization, validation, and trust boundaries.
- Injection, unsafe query construction, and insecure deserialization.
- Secret exposure, sensitive logs, and unsafe error responses.
- Unsafe file, process, or network operations.
- Resource exhaustion, missing limits, and dependency risks.
- Transaction safety, cleanup, retries, idempotency, and concurrency.
- Insecure configuration defaults or unintended permission changes.

Prioritize concrete vulnerabilities and realistic failure scenarios. Do not
label theoretical concerns as exploitable vulnerabilities without evidence.
State relevant assumptions and distinguish confirmed exposure from potential
risk.

## 6. Test Quality and Coverage

Inspect test assertions and behavior, not just test counts or coverage numbers.

### Unit tests
Check important business rules, boundaries, validation, failure paths, and
whether assertions verify intended behavior rather than implementation details.

### Integration tests
Check changed interactions with persistence, adapters, dependency wiring,
serialization, and external boundaries. Do not rely exclusively on mocks
where real boundary behavior matters.

### End-to-end tests
Determine whether affected externally observable workflows require E2E
coverage, based on the change and its risk.

### Regression protection
Identify meaningful behavior changes or defects without appropriate regression
tests. Flag brittle tests, excessive mocking, hidden shared state, and tests
that can pass without validating the requirement.

Recommend unit, integration, and E2E tests where justified. Do not require
every test level for every change. Never modify or weaken tests during review.

## 7. Independently Verify Quality Checks

Inspect project configuration, available CI results, and actual execution
evidence. Run appropriate checks when the environment permits and doing so is
safe. Prefer targeted checks followed by broader validation where practical.

For Python projects, consider configured Black, Ruff, Mypy, and Pytest checks.
For other stacks, use the project's actual formatting, linting, type-checking,
build, and test tools.

Classify each check as:

- **Passed:** Executed successfully.
- **Failed:** Executed and reported a failure.
- **Blocked:** Could not execute because of an identified limitation.
- **Not run:** Was not executed.

Do not claim checks passed based only on an implementation report or a
PROJECT_CONTEXT.md entry. Independently verify important claims when practical.

Distinguish failures introduced by the change from pre-existing failures when
evidence permits. Do not modify source files simply to make checks pass.
Do not claim full verification when only targeted checks were run.

## 8. Review the Plan and Diff

Compare actual changes against the approved plan, requirements, and scope.

Identify:

- Planned work that is missing or incomplete.
- Unplanned files, dependencies, or behavior changes.
- Unnecessary refactoring or configuration changes.
- Contract changes not covered by the plan.
- Missing tests or acceptance criteria.
- Deviations that are justified by implementation discoveries.
- Deviations that require explanation, approval, or follow-up.

A deviation is not automatically a defect. Evaluate its necessity, impact,
compatibility, and whether it was appropriately documented or approved.

Never discard unrelated changes, rewrite the plan, or alter the working tree
during review.

## 9. Audit PROJECT_CONTEXT.md

When PROJECT_CONTEXT.md exists, review it as a shared handoff and execution
record—not as proof that the code works.

Compare its claims with the actual repository, approved plan, Git changes,
tests, and available verification evidence.

Check the following where applicable:

- The current phase and module match the requested work.
- The approved plan and acceptance criteria remain identifiable.
- Reported completed work corresponds to actual implementation.
- Listed changed files are accurate and materially complete.
- Test and quality-check statuses reflect actual results.
- Deviations, blockers, and outstanding work are not concealed.
- The next action is consistent with module dependencies and verified state.
- Other modules' plans have not been silently changed by implementation.
- Phase completion or context compaction has not been claimed prematurely.

Treat inconsistencies as findings when they could mislead the next developer
or AI session, cause unsafe work, or lose important project context.

Do not update PROJECT_CONTEXT.md during review. Report the specific correction
needed so the authorized planning or implementation workflow can update it.

If the context file is missing or incomplete, do not automatically treat that
as a code defect. Report the resulting handoff or verification limitation when
it materially affects continuity or correctness.

## 10. Findings and Severity

Order actionable findings by severity.

### Critical
Catastrophic defects, severe exploitable security vulnerabilities, or major
data-loss risks requiring immediate attention.

### High
Substantial functional defects, security issues, or regressions that make an
important workflow incorrect or unreliable.

### Medium
Meaningful correctness, reliability, maintainability, architecture, or testing
issues with concrete impact that should be addressed.

### Low
Limited-impact defects or worthwhile improvements that do not substantially
compromise the implementation.

### Informational
Observations and optional improvements that are not confirmed defects. Keep
these separate from actionable defect counts.

Severity must reflect realistic impact and likelihood, not personal preference
or lines changed.

Every actionable finding must include:

- **ID:** Unique identifier, such as REV-001.
- **Severity:** Critical, High, Medium, or Low.
- **Location:** File and line range when applicable.
- **Problem:** What is incorrect or missing.
- **Evidence:** Code path, condition, reproduction, or verification result.
- **Impact:** What can go wrong and under which circumstances.
- **Recommendation:** A specific, practical correction.
- **Test recommendation:** How to verify the correction.

Keep findings independently actionable and concise. Do not duplicate the same
underlying defect across multiple findings. Never fabricate line numbers,
execution results, vulnerabilities, or reproduction steps.

## 11. Review Verdict

Finish with exactly one verdict.

### APPROVE
No material defects were found, requirements for the reviewed scope are
satisfied, and the available verification evidence is sufficient.

### APPROVE WITH FOLLOW-UPS
No blocking defects were identified, but minor issues or non-blocking risks
remain and are clearly documented.

### CHANGES REQUIRED
Actionable defects, unmet acceptance criteria, material architectural
violations, or significant verification gaps require correction before approval.

### INCONCLUSIVE
Available code, requirements, environment, or evidence is insufficient to
reach a reliable verdict.

Do not approve after only a superficial inspection. A passing test suite alone
does not establish correctness. Critical or High findings require CHANGES
REQUIRED. If important checks could not run, explain whether that prevents
reliable approval.

## 12. Required Review Report

Use this structure:

### 1. Review Summary
State the reviewed scope and overall result.

### 2. Verdict
Give one verdict and a concise justification.

### 3. Findings
List actionable findings in severity order. If none exist, state that clearly.
Keep informational observations separate.

### 4. Plan and Requirement Compliance
Summarize satisfied criteria, missing requirements, and significant deviations.

### 5. Architecture and Security Assessment
Summarize relevant design, boundary, dependency, security, and reliability
concerns without duplicating detailed findings.

### 6. Testing Assessment
Describe test quality, coverage gaps, and needed regression protection.

### 7. Verification Results
List checks actually performed, their status, and limitations.

### 8. PROJECT_CONTEXT.md Consistency
Report verified inconsistencies or state that no material inconsistency was
identified. If no context file exists, say so when relevant.

### 9. Remaining Risks
Identify unresolved risks, assumptions, and unverified concerns.

### 10. Recommended Next Actions
List corrective actions in priority order. Make clear which findings must be
fixed before approval and which follow-ups are optional.

## 13. Final Rules

- Remain read-only unless remediation is explicitly authorized.
- Inspect actual code, dependencies, relevant execution paths, and tests.
- Evaluate against approved requirements and real project conventions.
- Apply SOLID, DI, and architectural principles pragmatically.
- Require evidence for actionable findings.
- Separate confirmed defects, unverified risks, and optional improvements.
- Verify important PROJECT_CONTEXT.md claims independently.
- Never silently change an approved plan or project context during review.
- Do not fabricate results or conceal verification gaps.
- Do not treat missing documentation alone as a code defect.
- Do not approve solely because tests pass.
- Do not reject sound code merely because another design is possible.
- End with a clear verdict and actionable next steps.
