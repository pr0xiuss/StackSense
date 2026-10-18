---
trigger: always_on
description: Require meaningful automated tests, appropriate quality checks, evidence-based verification, and truthful reporting of implementation results.
---

# Testing and Verification

## 1. Testing Principles

- Add or update meaningful tests for new and modified behavior.
- Inspect the existing test structure, fixtures, conventions, and configuration before creating new test infrastructure.
- Test observable behavior and important requirements rather than merely increasing line coverage.
- Cover successful outcomes, relevant edge cases, invalid inputs, and expected failure paths.
- Preserve existing tests and meaningful assertions.
- Never weaken, delete, skip, or bypass tests merely to obtain a passing result.
- Avoid brittle tests that depend unnecessarily on implementation details.

## 2. Choose Appropriate Test Levels

### Unit Tests
- Test isolated business rules, functions, classes, and decision logic.
- Use mocks, fakes, or stubs where they meaningfully isolate dependencies.
- Verify important boundaries, failure handling, and invariants.

### Integration Tests
- Test meaningful interactions between components and external boundaries.
- Cover persistence, database behavior, dependency wiring, serialization, and adapters when relevant.
- Do not rely exclusively on mocks when actual integration behavior is important.

### End-to-End Tests
- Cover critical externally observable workflows when the change warrants them.
- Verify important interactions across the relevant application boundaries.
- Avoid introducing unnecessary E2E infrastructure for isolated changes.

Select test levels according to risk, requirements, and existing project conventions. Do not mechanically require every test level for every task.

## 3. Discover Project Tooling

- Inspect project manifests, test configuration, task runners, CI workflows, and repository instructions.
- Use established commands and the project's configured tools.
- Do not assume a particular language, framework, test runner, or directory structure.
- Prefer existing test infrastructure over creating duplicate frameworks or configuration.
- Identify unavailable dependencies, missing configuration, and environmental limitations.

For applicable Python projects, consider:
- Black for formatting.
- Ruff for linting.
- Mypy for static type checking.
- Pytest for automated tests.

Use the project's actual configuration, supported Python version, and established command scope. For other ecosystems, use their configured equivalents.

## 4. Verification Process

After implementing changes:

1. Run targeted tests for the modified behavior.
2. Run relevant integration tests where applicable.
3. Run broader regression tests when practical.
4. Run applicable formatting, linting, type-checking, build, and other configured checks.
5. Inspect the final diff for accidental changes.
6. Compare results against the task's acceptance criteria.
7. Identify unresolved failures and unverified behavior.

Run checks in a sensible order. If a check fails, investigate the cause rather than blindly retrying or suppressing it.

When correcting a failure, rerun the affected checks and any broader checks necessary to verify that the correction did not introduce regressions.

## 5. Report Actual Results

For every important check, distinguish:

- **Passed:** The check executed and completed successfully.
- **Failed:** The check executed and reported a failure.
- **Blocked:** The check could not execute because of an identified limitation.
- **Not run:** The check was not executed.

Report the command or test scope where useful, along with relevant failures and limitations.

- Never claim that a test, build, formatter, linter, or type checker passed without execution evidence.
- Do not infer that the full suite passes from a targeted test run.
- Distinguish pre-existing failures from newly introduced failures when evidence permits.
- Do not conceal failures, environmental problems, or incomplete verification.
- Do not claim that a defect is fixed until the relevant behavior has been verified.

## 6. Coverage and Risk

- Identify important behavior that remains untested.
- Prioritize regression protection for changed contracts, business rules, persistence behavior, and critical workflows.
- Consider failure paths and boundary conditions, not only happy paths.
- Use coverage metrics as supporting evidence rather than proof of correctness.
- Recommend additional tests when they address a meaningful risk.
- Avoid redundant tests that provide no additional behavioral confidence.

## 7. Completion Criteria

Before reporting a task as complete:

- Confirm the required behavior is implemented.
- Verify the applicable acceptance criteria.
- Confirm relevant tests have been added or updated.
- Run applicable quality checks and record their results.
- Inspect the resulting changes.
- Disclose failed, blocked, and unrun checks.
- List unresolved defects, risks, and remaining work.

Passing tests alone does not prove correctness. Conversely, an unrelated pre-existing failure does not automatically invalidate a change. Evaluate the evidence and report the distinction clearly.