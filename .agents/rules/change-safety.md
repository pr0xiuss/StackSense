---
trigger: always_on
description: Protect existing work, control implementation scope, preserve Git changes, and require authorization for risky or destructive operations.
---

# Change Safety

## 1. Inspect Before Changing

- Inspect Git status, relevant diffs, and the current branch before modifying files.
- Read the relevant source files, callers, configuration, and tests before changing existing behavior.
- Identify uncommitted changes and distinguish existing user work from task-related modifications where possible.
- Never assume the working tree is clean.
- Check whether the requested changes conflict with existing work, project instructions, or an approved implementation plan.

## 2. Preserve Existing Work

- Never discard, overwrite, reset, or revert unrelated user changes.
- Do not use destructive Git operations, including hard resets, forced checkouts, or indiscriminate cleanup, without explicit authorization.
- Avoid broad replacement scripts or bulk edits that could unintentionally alter unrelated files.
- Inspect generated changes and diffs before considering the task complete.
- Do not delete files, tests, configurations, or documentation merely because they appear unnecessary without verifying their purpose and impact.

## 3. Respect Scope and Approved Plans

- Keep changes limited to the requested task and its necessary dependencies.
- Follow the approved implementation plan when one exists.
- Do not silently expand scope, introduce unrelated refactoring, or redesign established architecture.
- If implementation reveals a necessary change to the approved design, explain the reason and impact.
- Seek approval before material changes to architecture, public contracts, persistence schemas, dependency versions, or backward compatibility.
- Fix directly related defects when appropriate; report unrelated defects separately rather than silently expanding the task.

## 4. Risky and Destructive Operations

- Obtain explicit authorization before destructive operations, production-impacting actions, or irreversible data changes.
- Do not run destructive database migrations, delete persistent data, or modify production infrastructure without appropriate authorization.
- Do not expose, overwrite, rotate, or commit secrets and credentials.
- Do not disable security controls, authentication, validation, tests, or CI checks merely to make a task pass.
- Before executing migrations, cleanup operations, or bulk modifications, understand their scope, reversibility, and potential impact.
- Prefer reversible, narrowly scoped changes and safe verification methods.

## 5. Dependencies and Configuration

- Avoid adding, removing, or upgrading dependencies without a task-related justification.
- Inspect compatibility, existing constraints, and the project's dependency-management conventions before changing dependencies.
- Do not overwrite project configuration with generic defaults.
- Preserve existing environment-specific settings and avoid committing local secrets or machine-specific configuration.
- Explain material configuration changes and their operational consequences.

## 6. Handling Uncertainty

- If a requested operation could cause data loss, break compatibility, or compromise security, stop before the risky action and clarify the intended outcome.
- If requirements conflict with existing constraints, identify the conflict instead of silently choosing an interpretation.
- Do not invent approval or infer authorization for consequential actions from the mere existence of a task.
- Continue with safe, independent work when possible, and clearly report blocked work.

## 7. Final Diff Inspection

Before finishing:

- Inspect all task-related changes.
- Identify accidental edits, unrelated files, generated artifacts, and sensitive information.
- Verify that no existing user work was unintentionally altered.
- Confirm that changes remain within the approved scope.
- Report significant deviations, unresolved risks, and any operations that could not be safely completed.