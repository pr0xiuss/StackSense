---
trigger: always_on
description: Universal software engineering principles for maintainable, modular, production-quality code across projects.
---

# Engineering Principles

## 1. Core Principles

- Follow SOLID principles, separation of concerns, and appropriate low-level design.
- Favor high cohesion, low coupling, explicit responsibilities, and maintainable code.
- Prefer simple, readable solutions over unnecessary complexity or premature abstraction.
- Apply design patterns when they solve a real problem, not merely to satisfy a checklist.
- Optimize for correctness, maintainability, testability, and clear ownership of behavior.

## 2. Architecture and Boundaries

- Inspect and respect the existing architecture before introducing or changing boundaries.
- Place each responsibility in the appropriate module and architectural layer.
- Keep business logic independent of infrastructure and framework concerns where the architecture permits.
- Maintain clear dependency direction and avoid circular dependencies.
- Reuse existing abstractions and conventions instead of creating competing implementations.
- Do not impose a fixed directory structure or architectural style on every project.
- Avoid unrelated refactoring, speculative features, and unnecessary dependencies.

## 3. Dependency Injection

- Prefer explicit dependency injection for services and external collaborators when appropriate.
- Depend on abstractions rather than concrete infrastructure implementations where this improves modularity and testability.
- Keep object construction and dependency wiring in the appropriate composition root or established DI mechanism.
- Avoid hidden dependencies, unnecessary global state, and tightly coupled object construction.
- Do not introduce interfaces or DI layers for trivial components without a meaningful benefit.

## 4. Components and Contracts

- Keep classes, functions, and modules focused on coherent responsibilities.
- Design clear contracts with explicit inputs, outputs, and failure behavior.
- Use repositories, services, DTOs, interfaces, and separate domain/application/infrastructure models when justified by the requirements and existing architecture.
- Keep API contracts, application models, domain objects, and persistence models appropriately separated where necessary.
- Avoid oversized classes, excessive indirection, duplicated abstractions, and unnecessary transformations.
- Preserve existing public contracts unless a change is explicitly required and its impact is understood.

## 5. Language and Project Conventions

- Follow the repository's established naming, typing, import, formatting, documentation, and error-handling conventions.
- Use language-appropriate idioms and the project's supported runtime and dependency versions.
- Do not impose language-specific practices on unrelated projects.
- Prefer explicit, readable code over clever but difficult-to-maintain implementations.
- Introduce new dependencies only when their benefits justify the added complexity and maintenance burden.

## 6. Error Handling and Reliability

- Handle expected failures explicitly and consistently with the project's conventions.
- Validate data at appropriate boundaries and maintain clear invariants.
- Avoid silently swallowing exceptions or returning misleading success results.
- Preserve useful diagnostic context without exposing secrets or sensitive information.
- Consider resource cleanup, transaction boundaries, concurrency, idempotency, and retry behavior where relevant.
- Ensure failure handling does not leave application state inconsistent.

## 7. Engineering Judgment

- Treat these principles as design constraints and decision-making guidance, not a mechanical checklist.
- Prefer the smallest coherent design that satisfies the requirements without compromising architectural integrity.
- Distinguish necessary abstractions from speculative generalization.
- When an established project convention conflicts with a proposed design, evaluate the trade-offs before changing it.
- When a material architectural decision is ambiguous, document the alternatives and seek clarification rather than silently inventing a convention.