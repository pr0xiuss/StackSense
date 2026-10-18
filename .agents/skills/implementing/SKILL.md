---
name: implementing
description: >
  Implements an approved phase or module plan in an existing software
  repository. Reads and maintains PROJECT_CONTEXT.md as the shared handoff
  between developers and AI sessions, follows project architecture and
  engineering conventions, creates meaningful tests, runs applicable quality
  checks, and records verified implementation progress. Use when implementing
  an approved module, feature, phase task, or scoped software change.
---

# Implementing Skill

## Objective

Execute approved implementation plans with maintainable code, appropriate
tests, and evidence-based verification.

Use PROJECT_CONTEXT.md as the primary handoff for the current phase, module
plans, execution state, and next actions when the file exists.

Adapt to the repository's actual language, framework, architecture, tooling,
and conventions. Never impose a fixed architecture on every project.

Implement the requested scope, preserve approved decisions, and maintain
accurate execution records so another developer or AI session can continue
without reconstructing the original conversation.

## 1. Establish the Implementation Context

Before modifying files:

1. Identify the repository root and applicable agent instructions.
2. Inspect Git status, the current branch, and relevant diffs.
3. Read PROJECT_CONTEXT.md if it exists.
4. Identify the current phase, requested module, approved plan, prerequisites,
   acceptance criteria, and outstanding blockers.
5. Read relevant architecture documentation, requirements, and ADRs.
6. Inspect the actual source code, callers, dependencies, and tests involved.
7. Identify the project's language, framework, configuration, and quality tools.

Treat PROJECT_CONTEXT.md as a shared handoff, not unquestionable proof of
the current implementation state. Verify relevant claims against the code,
tests, Git state, and available execution evidence.

If no context file exists, use the approved plan and repository instructions
as the source of task context. Do not create an unnecessary phase context
structure for a trivial task.

If the plan is missing, unapproved, materially outdated, or inconsistent
with the repository, resolve the discrepancy before implementing affected
changes.

Preserve all unrelated user modifications and collaborator work.

## 2. Select and Scope the Work

Determine exactly which module or task the user wants implemented.

When working from a phase plan:

- Implement only the requested module and its necessary approved dependencies.
- Respect the documented module dependency order.
- Check that prerequisite modules and contracts are actually available.
- Identify integration assumptions and shared interfaces.
- Avoid implementing future modules prematurely.
- Avoid unrelated refactoring and unapproved scope expansion.

If the requested module depends on unfinished work, determine whether safe,
independent progress is possible. Otherwise, report the blocker rather than
fabricating dependencies or silently changing the design.

If the user requests an entire phase, follow the approved phase plan and
work through its modules in dependency order.

## 3. Follow the Approved Plan

For each implementation task:

1. Confirm its intended behavior and acceptance criteria.
2. Inspect existing components and their callers.
3. Reuse established abstractions, contracts, utilities, and conventions.
4. Implement the approved changes.
5. Add or update relevant automated tests.
6. Run appropriate verification checks.
7. Inspect the complete task-related diff.
8. Record actual results in PROJECT_CONTEXT.md when present.

Do not treat file creation as proof of completion.

If implementation reveals a necessary design change, explain its rationale,
impact, alternatives, and consequences.

Obtain approval before materially changing architecture, public contracts,
database schemas, dependency versions, compatibility guarantees, or other
approved design decisions.

Do not silently replace the approved plan with a new design.

## 4. Engineering Standards

### SOLID and low-level design

- Apply SOLID principles where they improve correctness, maintainability,
  modularity, or testability.
- Prefer high cohesion, low coupling, explicit responsibilities, and clear
  module boundaries.
- Avoid oversized classes, unnecessary duplication, and tightly coupled
  components.
- Prefer the smallest coherent design that satisfies the requirements.
- Do not introduce abstractions solely to satisfy a checklist.

### Dependency injection

- Follow the project's established dependency-injection mechanism.
- Inject collaborators when appropriate instead of constructing infrastructure
  dependencies throughout business logic.
- Preserve dependency direction and register dependencies in the appropriate
  composition root when required.
- Avoid hidden dependencies, unnecessary global state, and circular dependencies.

### Architecture and boundaries

Respect the existing architecture and authoritative project specifications.

Where applicable, preserve separation between domain behavior, application
orchestration, infrastructure implementations, and presentation concerns.

These are contextual examples, not mandatory directories for every project.

Do not force a domain/application/infrastructure structure onto a project
that does not use it.

### Contracts, repositories, services, and DTOs

- Reuse existing contracts and data-transfer conventions.
- Keep services focused on their intended responsibilities.
- Use repository abstractions where they establish a meaningful persistence
  boundary and fit the existing architecture.
- Use DTOs where needed to separate API, application, domain, and persistence
  concerns.
- Avoid unnecessary interfaces, repositories, services, transformations,
  and duplicate abstractions.
- Preserve public contracts unless an approved change explicitly requires
  modifying them.

### Code conventions

Follow established naming, imports, typing, formatting, logging, documentation,
and error-handling conventions.

Use language-appropriate practices and supported dependency versions.

Avoid unrelated refactoring, speculative features, and unnecessary dependencies.

### Reliability

Handle expected failures explicitly, validate inputs at appropriate boundaries,
preserve useful diagnostic context, and avoid swallowing exceptions.

Consider resource cleanup, transactions, concurrency, idempotency, and retries
when relevant to the change.

## 5. Implement Tests Alongside the Code

Inspect the existing testing infrastructure before adding or modifying tests.

### Unit tests

Test meaningful individual behaviors, including:

- Expected successful outcomes.
- Business rules and important branches.
- Boundary conditions and invalid inputs.
- Dependency failures and error handling.
- Regression scenarios.

Use mocks, fakes, or stubs where they provide useful isolation. Avoid tests
that depend unnecessarily on internal implementation details.

### Integration tests

Test important interactions across component boundaries, including persistence,
database behavior, adapters, serialization, and dependency wiring when relevant.

Use the project's established integration-test infrastructure.

### End-to-end tests

Add or update E2E tests when critical externally observable workflows change.

Do not introduce unnecessary E2E infrastructure or require E2E coverage for
every isolated change.

### Test quality

- Test observable behavior and meaningful outcomes.
- Keep tests deterministic and maintainable.
- Preserve existing meaningful assertions.
- Never weaken, delete, skip, or bypass tests merely to make them pass.
- Investigate whether a failure comes from the implementation, the test,
  the specification, or the environment.

## 6. Run Quality Checks

Discover the actual project configuration and established commands before
running quality checks.

For applicable Python projects, consider:

- Black for formatting.
- Ruff for linting.
- Mypy for static type checking.
- Pytest for automated tests.

Typical commands may include:

- `black --check .`
- `ruff check .`
- `mypy .`
- `pytest`

These are examples, not universal defaults. Use the project's configured
scope and commands where available.

For other ecosystems, use their configured formatting, linting, type-checking,
build, and testing tools.

Run targeted checks first, followed by broader regression checks when practical.

If formatting changes are needed, use the established formatter and inspect
the resulting diff.

Report unavailable tools, environmental limitations, failed checks, and
pre-existing failures explicitly. Never claim that an unexecuted check passed.

## 7. Maintain PROJECT_CONTEXT.md

When PROJECT_CONTEXT.md exists, maintain it as the shared execution handoff.

Before updating it:

1. Read the relevant current content.
2. Inspect the latest Git state and existing changes.
3. Identify the exact module and execution-ledger sections affected.
4. Preserve the approved phase plan and unrelated collaborator updates.
5. Reconcile the proposed update with the actual implementation and verification
   evidence.

If the file does not exist but an approved phase plan requires a shared context
file, create it following the project's conventions. Do not invent a detailed
phase plan during implementation.

### Approved plans are protected

Do not rewrite approved module plans merely because implementation differs
from expectations.

Keep the approved design separate from actual execution records.

If a material deviation is necessary, document the discrepancy and proposed
change. Obtain approval where required before changing the approved plan.

Do not expand or rewrite unrelated future modules.

### Update the execution ledger

After meaningful implementation and verification milestones, update the
relevant module's execution record with:

- **Module:** Module identifier and name.
- **Status:** Current implementation state.
- **Completed work:** Behavior and responsibilities actually implemented.
- **Files changed:** Relevant created, modified, or deleted files.
- **Tests added or updated:** Important coverage introduced.
- **Verification:** Commands executed and their actual results.
- **Deviations:** Differences from the approved plan and their justification.
- **Outstanding work:** Missing requirements, defects, and unimplemented tasks.
- **Blockers:** Dependencies or decisions preventing progress.
- **Next action:** The next concrete step, when known.

Use these status meanings consistently:

- **Not Started:** No implementation work has begun.
- **In Progress:** Work has begun but is unfinished.
- **Implemented:** Coding is complete, but required verification is incomplete
  or has not established full acceptance.
- **Verified:** Relevant implementation checks passed, but the module's full
  acceptance criteria or dependencies may remain outstanding.
- **Complete:** Required acceptance criteria and applicable verification are
  satisfied, with no unresolved blocking issues.
- **Blocked:** Progress cannot safely continue without a dependency,
  decision, or external resolution.

Do not mark a module Complete merely because its implementation code exists
or its unit tests pass.

Record failed, blocked, and unrun checks accurately. Do not report planned
tests as executed tests.

### Preserve collaborator changes

PROJECT_CONTEXT.md may be edited by multiple developers.

- Keep updates localized to the relevant module and current handoff.
- Re-read the file before writing if other changes may have occurred.
- Do not replace the entire file merely to update one module.
- If concurrent changes conflict, preserve both sets of work and reconcile
  the conflict explicitly.
- Never overwrite another collaborator's execution records without verifying
  their relevance and status.

If the context file cannot be updated safely, report that limitation rather
than claiming the handoff is synchronized.

## 8. Phase Completion and Context Compaction

Routine implementation must not compact the active phase context automatically.

When the user explicitly declares the entire phase complete:

1. Verify the recorded module statuses and phase acceptance criteria.
2. Check relevant test results, outstanding blockers, and unresolved defects.
3. Identify limitations explicitly accepted by the user.
4. Preserve a concise summary of the completed phase, including delivered
   capabilities, important contracts, architectural decisions, dependencies,
   and unresolved issues.
5. Compact the detailed phase section only as part of the authorized
   phase-transition operation.
6. Preserve brief summaries of completed and upcoming phases.
7. Expand the next phase into detailed planning only when its plan is available
   and sufficiently established.

Do not delete valuable architectural decisions, historical evidence, or
authoritative documentation when compacting the context.

If the next phase is not fully planned or approved, request or perform the
appropriate planning step before implementing it.

## 9. Final Verification

Before reporting the task complete:

1. Inspect the full task-related diff.
2. Check for accidental, unrelated, generated, or sensitive files.
3. Verify dependency wiring and architectural boundaries.
4. Confirm that implementation matches the approved requirements.
5. Verify that relevant tests were added or updated.
6. Run applicable quality checks.
7. Evaluate the relevant acceptance criteria.
8. Update PROJECT_CONTEXT.md with accurate results and remaining work.

If the context file is tracked by Git, include its legitimate changes in the
final diff. Never include unrelated context changes merely to make the handoff
appear complete.

Do not claim full completion while material acceptance criteria remain unmet.

## 10. Final Implementation Report

Provide a report containing:

### Summary
What was implemented and which requirements were addressed.

### Module and phase status
The status of the requested module and any affected prerequisites.

### Files changed
Created, modified, and deleted files with concise explanations.

### Tests
Important unit, integration, and E2E tests added or updated.

### Quality checks
Commands actually executed and their results. Separate passed, failed,
blocked, and unrun checks.

### Context update
Sections of PROJECT_CONTEXT.md updated and the recorded implementation status.

### Deviations and risks
Material deviations, unresolved defects, environmental limitations, and
outstanding decisions.

### Next action
The next recommended module, corrective task, or required approval.

## 11. Final Rules

- Follow approved plans and applicable repository instructions.
- Read PROJECT_CONTEXT.md before continuing an established phase.
- Verify relevant context claims against the actual repository.
- Implement only the authorized scope and necessary dependencies.
- Preserve user changes, collaborator work, and approved plans.
- Apply SOLID, DI, high cohesion, and low coupling pragmatically.
- Add meaningful tests and run applicable quality checks.
- Never fabricate results or conceal verification failures.
- Update the execution ledger with actual work and evidence.
- Never compact a phase without explicit user authorization.
- Never claim unverified work is complete.
- Finish with an accurate implementation report and next action.