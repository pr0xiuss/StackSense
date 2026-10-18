---
name: planning
description: >
  Analyzes a software repository and produces a complete, phased implementation
  plan with detailed module specifications, file-level responsibilities,
  dependencies, tests, acceptance criteria, and risks. Maintains a rolling
  PROJECT_CONTEXT.md containing the detailed current phase, concise summaries
  of other phases, and the verified execution state. Use before implementing
  a new feature, module, phase, or significant refactor.
---

# Planning Skill

## Objective

Produce a technically grounded, reviewable implementation plan that another
developer or AI agent can execute without rediscovering the entire project.

Adapt to the repository's actual documentation, architecture, language,
framework, conventions, and existing implementation.

For phase-level work, plan the entire requested phase and all its modules
before implementation begins.

Maintain a repository-level PROJECT_CONTEXT.md as the shared handoff between
developers, AI sessions, planning, and implementation.

This skill performs analysis and planning. It must not implement application
behavior or modify application source code. It may create or update
PROJECT_CONTEXT.md as required by this skill.

## 1. Discover the Repository

Before planning:

1. Identify the repository root and relevant project directories.
2. Inspect Git status and preserve existing user modifications.
3. Read applicable agent instructions, repository guidelines, and development
   instructions.
4. Identify languages, frameworks, runtime versions, dependency managers,
   entry points, configuration, and build systems.
5. Locate relevant architecture documents, requirements, ADRs, API contracts,
   existing plans, tests, and CI workflows.
6. Inspect relevant source code, callers, dependencies, and existing
   abstractions.
7. Identify established testing and quality-check commands.

Do not assume a file, framework, command, architectural layer, or convention
exists without supporting evidence.

Keep discovery proportionate to the task, expanding it when dependencies,
public contracts, or architectural boundaries require deeper investigation.

## 2. Establish the Source of Truth

Determine which documents and instructions are authoritative for the task.

Inspect relevant:

- Agent and repository instructions.
- Architecture specifications and architectural decision records.
- Requirements and acceptance criteria.
- Module documentation and existing implementation plans.
- API contracts, data models, and testing instructions.

If documentation is missing or incomplete, reconstruct the relevant design
from the existing codebase.

If documentation conflicts with implementation:

1. Identify the discrepancy and its impact.
2. Determine the documented intent and actual behavior.
3. Preserve explicit architectural constraints unless an authorized change
   is part of the task.
4. Record unresolved conflicts and assumptions.

Distinguish verified facts, approved decisions, proposed decisions, and
unresolved questions. Never silently convert assumptions into requirements.

## 3. Inspect the Existing Architecture

Trace relevant execution paths rather than relying on filenames alone.

Determine:

- Module boundaries and ownership of responsibilities.
- Existing classes, functions, services, contracts, and data models.
- Dependency direction and dependency-injection conventions.
- Repository interfaces and concrete implementations where applicable.
- Data flow, persistence, validation, and error handling.
- Public APIs, external integrations, and compatibility constraints.
- Existing test organization, fixtures, and quality tools.
- Existing abstractions that should be reused.

Follow the project's actual architecture. Do not impose a fixed directory
structure or introduce unnecessary layers.

## 4. Apply Engineering Standards

Design solutions that favor:

- SOLID principles and appropriate low-level design.
- Dependency inversion and dependency injection where warranted.
- High cohesion, low coupling, and clear responsibility boundaries.
- Meaningful contracts, DTOs, repositories, and services when appropriate.
- Appropriate separation of domain, application, infrastructure, and
  presentation responsibilities where those layers exist.
- Reuse of existing abstractions and conventions.
- Testability, maintainability, readability, and reliable error handling.

Do not mechanically introduce interfaces, factories, repositories, services,
DTOs, or additional layers without a meaningful architectural reason.

Avoid unrelated refactoring, unnecessary dependencies, speculative features,
and premature generalization.

## 5. Plan the Entire Requested Phase

When the request concerns a phase, do not plan only the first module.

Analyze and plan every module belonging to the requested phase before
implementation begins.

For the phase, define:

- Overall objective and expected outcome.
- Scope and explicit non-goals.
- Architectural constraints and dependencies.
- All modules and their individual objectives.
- Module dependency relationships and implementation order.
- Shared contracts and integration boundaries.
- Cross-module concerns and potential conflicts.
- Testing and verification strategy.
- Phase-level acceptance criteria.
- Risks, assumptions, and unresolved decisions.

For each module, identify its responsibilities, inputs, outputs, dependencies,
expected behavior, and relationship to other modules.

Distinguish modules that can be implemented independently from those that
require prerequisites.

Do not invent additional modules merely to make the plan appear comprehensive.

## 6. Produce File-Level Specifications

For every planned module, identify the files that should be created, modified,
reused, or deleted.

For each file, provide:

- **Path:** Exact repository-relative path where established, or an explicitly
  labeled proposed path when the design is not yet confirmed.
- **Action:** Create, modify, reuse, or delete.
- **Purpose:** Why the file is needed.
- **Components:** Proposed or existing classes, functions, methods, types,
  contracts, and schemas.
- **Responsibilities:** A concise one- or two-line explanation of each
  significant component.
- **Dependencies:** What it calls, implements, consumes, or receives through DI.
- **Tests:** Specific behavior and failure cases to verify.
- **Rationale:** Why the responsibility belongs at that location.

Inspect existing files before naming components to modify. Label uncertain
design details as proposals rather than claiming they already exist.

Include necessary changes to configuration, dependency wiring, database
schemas, API contracts, and documentation when justified.

## 7. Define Testing and Quality Gates

Specify meaningful tests for each module and for cross-module interactions.

Consider:

- Unit tests for business rules, boundaries, and failure handling.
- Integration tests for persistence, dependency wiring, and external boundaries.
- End-to-end tests for critical externally observable workflows.
- Regression tests for changed behavior and public contracts.

Choose test levels according to risk and project conventions. Do not require
every test level for every change.

Discover actual project tooling and commands.

For applicable Python projects, consider Black, Ruff, Mypy, and Pytest.
For other ecosystems, identify their configured equivalents.

Do not assume tools are installed or commands exist without checking.

Define module-level and phase-level acceptance criteria that can be verified
against actual behavior and test results.

## 8. Maintain PROJECT_CONTEXT.md

Use one repository-level PROJECT_CONTEXT.md as the shared planning and
execution handoff for the project.

Before creating or updating it:

1. Search for an existing project context file and read it completely enough
   to understand its structure and current state.
2. Inspect Git status and preserve existing user modifications.
3. Reconcile the context with the current task, approved plans, relevant code,
   and recorded execution evidence.
4. Reuse the existing file and structure when possible.
5. Do not overwrite unrelated project context or silently discard history.

If no context file exists, create one at the repository root unless established
repository conventions provide a more appropriate location.

### Required context structure

Maintain these sections, adapting their detail to the project:

1. **Project Overview:** Purpose, current development stage, and authoritative
   documentation references.
2. **Global Constraints:** Critical architectural rules, compatibility
   requirements, and established decisions.
3. **Phase Index:** Brief summaries of completed, current, and upcoming phases.
4. **Current Phase Plan:** Detailed objectives, all module plans, dependencies,
   file specifications, acceptance criteria, and testing strategy.
5. **Execution Ledger:** Actual implementation status, changed files, test
   results, deviations, blockers, and outstanding work for each module.
6. **Decisions and Risks:** Approved decisions, proposed changes, unresolved
   questions, and relevant risks.
7. **Current Handoff:** Current module, last verified milestone, remaining work,
   blockers, and the next recommended action.

Keep the current phase detailed enough for a fresh AI session or collaborator
to continue without the original conversation.

Keep other phases concise. Completed phases should retain their objectives,
delivered capabilities, important contracts, decisions, and unresolved issues.
Upcoming phases should retain their objectives and important dependencies
without duplicating full implementation plans.

Do not copy entire source files, documentation, or raw test logs into the
context file. Reference authoritative files and summarize relevant evidence.

### Plan approval and immutability

Clearly distinguish draft plans from approved plans.

Before approval, the current phase plan may be revised as part of planning.

After approval, treat the plan as the agreed baseline. Do not silently rewrite
approved module plans or architectural decisions during implementation.

If new evidence requires a material change, document the discrepancy, impact,
and proposed adjustment for approval.

The execution ledger may change as implementation progresses, but it must
describe actual work rather than planned work presented as completed.

## 9. Rolling Phase Context

Keep one phase detailed at a time.

### During planning

- Fully plan every module in the requested phase.
- Keep completed and other phases summarized.
- Keep upcoming phase summaries brief and dependency-aware.
- Record the requested phase as planned, not implemented.
- Preserve unresolved decisions and approval requirements.

### During implementation

The implementing skill owns routine updates to the execution ledger.

Planning must not overwrite implementation status, test evidence, or collaborator
updates that have already been recorded.

When implementation reveals a design issue, revise the approved plan only
through the established approval process.

### When a phase is declared complete

Compact the current phase only after the user explicitly declares the phase
complete and the available evidence has been checked.

Before compacting:

1. Verify module statuses, acceptance criteria, and relevant test evidence.
2. Identify unresolved defects, blockers, and explicitly accepted limitations.
3. Preserve a concise phase completion summary, important contracts, decisions,
   dependencies, and outstanding issues.
4. Retain references to detailed plans, ADRs, test reports, and other historical
   artifacts when they exist.
5. Promote the next phase's summary into the detailed planning section only
   when its plan is available and sufficiently established.

If the next phase has not been fully planned, expand it through a new planning
pass before implementation begins.

Do not claim that a phase is complete merely because all modules have been
attempted. Never delete important decisions or misrepresent incomplete work
during compaction.

## 10. Collaborative Handoffs

Design the context file so another developer or AI session can continue
from the repository alone.

Record:

- The current approved phase and module.
- Module prerequisites and integration contracts.
- Work actually completed and its verification evidence.
- Work that remains and why.
- Material deviations from the approved plan.
- Outstanding decisions and blockers.
- The next recommended action.

Do not depend on conversation history being available.

Treat the context file as the shared record of planning and execution state,
not as proof that the implementation is correct. Verify its claims against
the repository when relevant.

Keep edits localized to the relevant sections. Preserve concurrent collaborator
changes and reconcile Git conflicts instead of overwriting another person's work.

## 11. Planning Report

Produce a reviewable report containing:

1. Task and phase objectives.
2. Project context and authoritative sources.
3. Relevant existing architecture and conventions.
4. Proposed design and important architectural decisions.
5. Complete phase and module breakdown.
6. Module dependencies and implementation order.
7. File-by-file specifications.
8. Testing strategy and quality gates.
9. Module-level and phase-level acceptance criteria.
10. Risks, assumptions, and unresolved questions.
11. PROJECT_CONTEXT.md changes and current status.
12. A concise summary suitable for independent review.

The report must be detailed enough for another model or developer to evaluate
the plan without rediscovering the entire repository.

Clearly identify whether the plan is a draft or ready for approval.

## 12. Final Rules

- Never implement application behavior during planning.
- Plan the entire requested phase before implementation begins.
- Never invent files, functions, dependencies, requirements, or test results.
- Distinguish facts, proposals, approved decisions, and assumptions.
- Respect authoritative architecture documents and existing constraints.
- Preserve approved plans and actual execution records.
- Keep the current phase detailed and other phases concise.
- Update PROJECT_CONTEXT.md without overwriting unrelated work.
- Compact a phase only after explicit user confirmation and evidence checks.
- Do not mark planned work as implemented or unverified work as complete.
- End with unresolved decisions, approval requirements, and the recommended
  next action.