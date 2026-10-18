---
trigger: always_on
description: Discover repository documentation, architecture, code conventions, dependencies, and tooling before making project-specific decisions.
---

# Project Discovery

## 1. Understand the Repository

Before planning or making changes:

- Identify the repository root and relevant application or package directories.
- Inspect applicable agent instructions and repository guidelines.
- Identify the programming languages, frameworks, runtime versions, and dependency managers.
- Inspect relevant dependency manifests, configuration files, build scripts, and CI workflows.
- Identify application entry points, module boundaries, and important execution paths.
- Locate existing tests and understand their organization.
- Inspect Git status when work may modify the repository.

Do not assume that a project uses a particular language, framework, directory structure, or architectural pattern.

## 2. Discover Documentation

Search for relevant documentation before designing a solution.

Consider:

- Agent instruction files and contributor guidelines.
- README files and module-specific documentation.
- Architecture specifications and architectural decision records.
- Requirements, implementation plans, API contracts, and data models.
- Testing instructions, development guides, and deployment documentation.

Read the relevant sections rather than relying solely on filenames or search snippets.

Identify which documents are authoritative for the requested task. Respect explicitly frozen architectural decisions unless a change is authorized.

Do not assume that documentation is complete or current.

## 3. When Documentation Is Missing

If documentation is absent or insufficient:

- Inspect the existing implementation to reconstruct relevant architecture and conventions.
- Trace callers, dependencies, data flow, and error-handling paths.
- Examine representative files from the affected modules.
- Inspect tests to understand expected behavior and established testing patterns.
- Examine configuration and CI workflows to determine actual development commands.
- Distinguish verified facts from assumptions and proposed design decisions.

Do not invent missing requirements or assume that an undocumented convention is mandatory.

If critical information cannot be established from the repository, identify the uncertainty and seek clarification when it could materially affect the design.

## 4. Reconcile Documentation with Code

When documentation and implementation disagree:

1. Identify the exact discrepancy.
2. Determine the documented intent and the implementation's actual behavior.
3. Inspect relevant history or architectural decisions when available and useful.
4. Preserve authoritative constraints and established public contracts.
5. Avoid silently changing architecture to match an assumption.
6. Report unresolved conflicts and propose a resolution when necessary.

Neither documentation nor existing code should be treated as infallible. Use the available evidence and the task's authorized scope to determine the appropriate next step.

## 5. Discover Existing Abstractions

Before proposing new components:

- Search for existing services, repositories, interfaces, DTOs, utilities, adapters, and shared contracts where relevant.
- Inspect how dependencies are constructed and injected.
- Identify established validation, error-handling, logging, and configuration mechanisms.
- Check whether similar behavior already exists elsewhere in the repository.
- Understand module ownership and permitted dependency directions.
- Prefer extending appropriate existing components over introducing duplicate implementations.

Do not create new abstractions solely because they are common in other projects.

## 6. Discover Testing and Quality Tooling

Inspect the repository's actual tooling and configuration.

Identify applicable:

- Unit, integration, and end-to-end test frameworks.
- Fixtures, test helpers, and mocking conventions.
- Formatters, linters, type checkers, and build tools.
- Dependency and environment setup instructions.
- CI commands and relevant quality gates.

For Python projects, inspect the relevant configuration for tools such as Black, Ruff, Mypy, and Pytest.

For other languages, identify the project's configured equivalents.

Do not invent commands, assume tools are installed, or impose a new toolchain without justification.

## 7. Keep Discovery Proportionate

- Investigate deeply enough to understand the affected behavior and its dependencies.
- Prefer targeted inspection over indiscriminate reading of the entire repository.
- Expand the investigation when changes cross module boundaries or affect public contracts.
- Reuse reliable findings from the current task when they remain applicable.
- Revalidate important assumptions when the repository or implementation changes.
- Avoid unnecessary documentation searches that do not improve the decision.

The objective is sufficient architectural understanding, not exhaustive exploration for its own sake.

## 8. Discovery Output

For substantial tasks, summarize the relevant findings:

- Repository structure and technology stack.
- Applicable documentation and authoritative constraints.
- Existing architecture and module boundaries.
- Relevant components and dependency relationships.
- Established conventions and testing practices.
- Available quality tools and commands.
- Documentation/code discrepancies.
- Assumptions, missing information, and unresolved questions.

Keep the summary focused on information that materially affects the task.

Use these findings to inform planning, implementation, and review. Do not duplicate the entire repository's documentation into every task report.

## 9. Final Rules

- Discover before assuming.
- Inspect relevant code before designing changes.
- Prefer authoritative project documentation while verifying implementation reality.
- Preserve existing architectural constraints.
- Reuse existing abstractions when appropriate.
- Distinguish verified facts, assumptions, and proposals.
- Avoid unnecessary exploration and unrelated changes.
- Escalate material ambiguities instead of silently inventing requirements.