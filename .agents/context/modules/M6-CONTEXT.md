# Module Context: M6 — API & Frontend

> This file is an operational context artifact for the StackSense agent workflow.
> It does **not** replace or override `master.txt`.
> `master.txt` remains the sole architectural source of truth.

## Authority Order

1. System / Developer instructions
2. Current authoritative `master.txt`
3. Explicitly approved architectural decisions
4. This module context
5. Existing implementation

If this file conflicts with the current `master.txt`, treat `master.txt` as authoritative. Do not silently reconcile or modify the architecture.

## Module Role

M6 owns the product-facing API and frontend integration required to expose the capabilities implemented by the backend modules.

It consumes established backend contracts rather than redefining backend domain ownership.

## Critical Responsibilities

M6 is responsible for:

- API presentation/integration
- API DTO consumption and exposure
- frontend application flows
- frontend/backend contract integration
- project and repository user flows
- authentication integration
- loading/error states
- API contract tests
- frontend integration tests

## Backend Boundary

M6 must not move domain or infrastructure responsibilities into the API/frontend layer.

Routers/controllers should remain thin and delegate business behavior to application services.

Frontend code must consume backend contracts rather than duplicate backend business rules.

## Product Flows

Relevant flows include capabilities such as:

- project creation/listing
- repository creation
- repository connection/upload
- repository status
- repository details
- ingestion status
- authentication/current-user flows

The exact contract remains governed by `master.txt` and the implemented backend interfaces.

## Authorization Boundary

The frontend must respect the existing ProjectAccess / ProjectAuthorization model.

Do not introduce client-side authorization as a replacement for backend authorization.

## API Boundary

The primary API convention is `/api/v1/`.

API changes must preserve established contracts and error semantics unless an explicit architectural change is approved.

## Implementation Rule

This context provides implementation guidance only.

It does not authorize architectural expansion or changes to `master.txt`.


**Location:** `.agents/context/modules/M6-CONTEXT.md`

**Status:** FROZEN FOR IMPLEMENTATION  
**Phase:** P2 — Project & Repository Platform  
**Module:** M6 — P2 API & Frontend Product Flow  
**Upstream:** M1 Foundation + M2 Project Access + M3 Repository Platform + M4 Repository Ingestion + M5 Identity & Authentication  
**Downstream:** M7 Integration, Evaluation & P2 Freeze

---

# 1. Purpose

M6 turns the P2 backend capabilities into a usable product flow.

M6 owns the P2-facing API integration and the corresponding frontend experience.

The objective is not to create a large frontend architecture.

The objective is a simple, maintainable, working vertical slice:

```text
Authentication
      ↓
Project
      ↓
Repository
      ↓
Repository Ingestion
      ↓
Repository Status
```

The backend remains the source of truth.

The frontend is responsible for:

```text
presentation
interaction
navigation
API consumption
loading states
error presentation
basic client-side validation
```

The frontend must not become a second business-logic engine.

---

# 2. Architectural Authority

The ultimate architectural authority is:

```text
master.txt
```

This file captures the implementation context and constraints for M6.

It does not replace or supersede `master.txt`.

If this file conflicts with the authoritative architecture:

```text
1. Stop the conflicting implementation.
2. Verify master.txt.
3. Identify the authoritative decision.
4. Resolve the conflict explicitly.
5. Do not silently change the architecture.
```

---

# 3. Required Upstream Context

Before implementing M6, the developer must understand:

```text
.agents/context/shared/M1-M2-CONTEXT.md
.agents/context/modules/M3-CONTEXT.md
.agents/context/modules/M4-CONTEXT.md
.agents/context/modules/M5-CONTEXT.md
```

M6 depends directly on the contracts established by those modules.

---

# 4. P2 Module Map

The relevant P2 flow is:

```text
M1
Project Domain Foundation
        │
        ▼
M2
Project Access & Resource Boundary
        │
        ├──────────────┐
        ▼              ▼
M3                    M4
Repository             Ingestion,
Domain &               Validation &
Registration            Storage
        │              │
        └──────┬───────┘
               ▼
M5
Identity & Authentication
               │
               ▼
M6
P2 API & Frontend Product Flow
               │
               ▼
M7
Integration, Evaluation & P2 Freeze
```

M6 consumes the established backend capabilities.

It must not redefine them.

---

# 5. M6 Mission

M6 must provide the product-facing path for:

```text
User
  ↓
Authenticate
  ↓
View accessible Projects
  ↓
Create Project
  ↓
Open Project
  ↓
Register Repository
  ↓
Connect/upload repository source
  ↓
Start/observe ingestion
  ↓
View Repository state
```

The exact operation names and endpoints must follow the actual backend contracts implemented by M3/M4/M5.

---

# 6. Backend and Frontend Responsibility

M6 consists of two closely related responsibilities:

```text
Backend API integration
+
Frontend product flow
```

The backend remains authoritative for:

```text
authorization
resource ownership
ProjectAccess
Repository state
ingestion state
validation
persistence
security
business invariants
```

The frontend remains responsible for:

```text
rendering
forms
navigation
user interaction
loading states
error states
API invocation
basic presentation-level validation
```

---

# 7. Core Principle

The frontend must never become the authoritative source of business truth.

For example:

```text
Frontend:
"User is allowed to delete this Repository."

Backend:
"User is actually authorized to delete this Repository."
```

The backend decision wins.

Frontend role-based visibility is only UX.

---

# 8. Current Resource Hierarchy

M6 must use the current P2 hierarchy:

```text
User
  ↓
Project
  ↓
Repository
  ↓
Repository Revision / Source
```

Do not introduce:

```text
Organization
Workspace
Tenant
Account
Repository Owner
```

as a new frontend hierarchy unless explicitly established by the authoritative architecture.

---

# 9. Project is the Primary Product Boundary

The frontend should organize the primary product flow around:

```text
Projects
```

rather than:

```text
Organizations
```

or:

```text
repositories belonging directly to users
```

The conceptual UI structure is:

```text
Projects
  ├── Project A
  │     ├── Overview
  │     └── Repositories
  │
  └── Project B
        ├── Overview
        └── Repositories
```

---

# 10. Project Access Semantics

M6 must understand that a Project list represents Projects accessible to the authenticated User.

The User may be:

```text
OWNER
ADMIN
DEVELOPER
VIEWER
```

Therefore the frontend must not assume:

```text
every Project is owned by the current User
```

or:

```text
current User can mutate every visible Project
```

---

# 11. Project Roles

The established roles are:

```text
OWNER
ADMIN
DEVELOPER
VIEWER
```

The existing permissions are:

| Role | Read | Create | Update | Delete |
|---|---:|---:|---:|---:|
| OWNER | ✓ | ✓ | ✓ | ✓ |
| ADMIN | ✓ | ✓ | ✓ | ✓ |
| DEVELOPER | ✓ | ✓ | ✓ | ✗ |
| VIEWER | ✓ | ✗ | ✗ | ✗ |

Membership management is restricted to:

```text
OWNER
ADMIN
```

M6 must consume these backend semantics.

It must not redefine them.

---

# 12. Frontend Role Handling

The frontend may use the current Project role to improve UX.

For example:

```text
VIEWER
    → hide/disable mutation controls

DEVELOPER
    → allow create/update
    → hide/disable delete

ADMIN
    → allow Project resource mutations
    → allow membership management

OWNER
    → allow Project resource mutations
    → allow membership management
```

These are presentation decisions only.

The backend must independently enforce every permission.

---

# 13. Do Not Build a Frontend Authorization Engine

Do not create a large client-side permission framework such as:

```text
AuthorizationEngine
PermissionGraph
PolicyEvaluator
RoleResolver
ResourceAuthorizationService
```

merely to reproduce backend rules.

A small helper or direct role check is acceptable where useful.

The backend remains authoritative.

---

# 14. Frontend Architecture Philosophy

The frontend must remain intentionally simple.

The user explicitly requires:

```text
basic frontend structure
minimal files
minimal folders
MVC-like organization where useful
no "views" layer
no excessive reusable-component architecture
```

Do not mirror the backend's domain/application/infrastructure layering in React.

Do not create a large enterprise frontend architecture merely because the backend is architecturally sophisticated.

---

# 15. Preferred Frontend Structure

The exact existing frontend root must be preserved.

Conceptually, a simple structure such as:

```text
frontend/
├── src/
│   ├── components/
│   ├── pages/
│   ├── api/
│   ├── hooks/
│   ├── App.jsx
│   └── main.jsx
```

is sufficient where these directories are actually needed.

Do not create empty or speculative directories.

---

# 16. No Views Folder

Do not introduce:

```text
views/
```

as a separate architectural layer.

Page components can directly represent the application's screens/routes.

For example:

```text
pages/
├── LoginPage.jsx
├── ProjectsPage.jsx
├── ProjectPage.jsx
└── RepositoryPage.jsx
```

The exact names should follow the existing frontend structure.

---

# 17. No Excessive Component Decomposition

Do not split every small UI element into its own file.

Avoid structures such as:

```text
components/
├── project/
│   ├── ProjectHeader/
│   ├── ProjectHeaderTitle/
│   ├── ProjectHeaderActions/
│   ├── ProjectHeaderButton/
│   └── ...
```

when the elements are only used once and are simple enough to remain in the page.

Reusable components should exist when reuse or meaningful separation actually justifies them.

---

# 18. Components

Use components for genuinely reusable UI or meaningful UI units.

Examples:

```text
Navbar
Modal
Button
LoadingState
ErrorState
RepositoryCard
ProjectCard
```

only where they are genuinely useful.

Do not create components solely to reduce the line count of a page.

---

# 19. Pages

Pages represent user-facing product flows.

Likely P2 pages include:

```text
Login
Projects
Project Details
Repository Details
```

Additional pages should only be introduced where required by the actual product flow.

---

# 20. API Layer

Frontend API calls should have a simple centralized location.

Conceptually:

```text
src/api/
```

with focused API modules where necessary.

For example:

```text
api/
├── auth.js
├── projects.js
└── repositories.js
```

The exact implementation should follow the existing frontend foundation.

Do not create a large generated-style SDK manually if the project does not require one.

---

# 21. HTTP Client

Use the existing frontend HTTP/API client foundation.

If the project already uses:

```text
fetch
```

continue using it.

If it already uses:

```text
axios
```

continue using it.

Do not introduce a second HTTP library for M6.

---

# 22. API Contract Authority

The backend API contract is authoritative.

M6 must consume the actual API contract established by the backend.

Do not invent frontend response structures such as:

```text
data.items
```

or:

```text
payload.results
```

unless the backend actually provides them or a deliberate frontend adapter defines them.

---

# 23. DTO/API Shape

Frontend types/interfaces or response handling should correspond to backend API contracts.

Do not expose SQLAlchemy models.

The boundary is:

```text
Backend API DTO
       ↓
Frontend API client
       ↓
Page/UI state
```

---

# 24. API Versioning

The backend primary API path is:

```text
/api/v1/
```

M6 must use the established versioned API.

Do not introduce unversioned frontend API calls for new P2 functionality.

---

# 25. Project API

M6 must consume the established Project API.

The current conceptual endpoints are:

```text
POST /api/v1/projects
GET  /api/v1/projects
GET  /api/v1/projects/{project_id}
DELETE /api/v1/projects/{project_id}
```

Exact response shapes and any additional operations must come from the implemented backend contract.

---

# 26. Project Listing

Project listing represents:

```text
Projects accessible to the current User
```

not:

```text
Projects owned by the current User
```

The current backend pagination contract uses:

```text
limit
offset
```

with bounded values.

M6 must consume this contract rather than silently replacing it with a different backend semantic.

---

# 27. Project Pagination

The existing backend contract uses:

```text
limit
offset
```

with:

```text
limit <= 100
offset >= 0
```

and a default bounded result size.

The frontend may implement simple pagination controls where necessary.

Do not redesign the backend pagination contract.

---

# 28. Project Creation

Project creation should use the established backend contract.

Conceptually:

```text
Project Form
    ↓
POST /api/v1/projects
    ↓
Backend Project Creation
    ↓
ProjectAccess OWNER grant
    ↓
Project Response
    ↓
Frontend navigation/update
```

The frontend must not separately create ownership state.

---

# 29. Project Ownership

When the current User creates a Project, ownership is established by the backend's ProjectAccess behavior.

The frontend must not send:

```text
owner_id
```

as a Project creation field.

Do not recreate the removed Project ownership model in the frontend.

---

# 30. Project Details

Project details should present information returned by the backend.

Possible content:

```text
Project name
Description
Repository list
Relevant access information
Repository status
```

Do not expose internal persistence metadata unless the API explicitly provides it.

---

# 31. Project Deletion

Project deletion is destructive.

The frontend should:

```text
show confirmation
explain consequence
disable duplicate submission
show loading state
send backend request
wait for backend response
handle failure
update navigation/state
```

The frontend must not assume deletion succeeded merely because the user clicked the button.

---

# 32. Repository Product Flow

The Repository product flow is:

```text
Project
   ↓
Repository registration
   ↓
Repository source acquisition
   ↓
Ingestion
   ↓
Validation
   ↓
Storage
   ↓
Repository status
```

M6 consumes the M3/M4 contracts.

It must not implement ingestion logic itself.

---

# 33. Repository Registration vs Ingestion

These are distinct operations.

```text
M3:
Repository identity/registration
```

and:

```text
M4:
Repository ingestion/validation/storage
```

M6 must not collapse them into one frontend concept if the backend exposes them separately.

---

# 34. Repository Creation

The frontend should create/register the Repository using the M3 API contract.

It should not send M4-specific internal fields unless they are explicitly part of the public API.

Do not invent:

```text
analysis_config
parser_config
architecture_model
knowledge_graph_id
```

for P2 Repository creation.

---

# 35. Repository Source Acquisition

Depending on the actual M4 contract, source may be provided through:

```text
Git provider
repository URL
local upload
archive
other approved acquisition mechanism
```

M6 must implement only the acquisition mechanisms actually included in the current P2 contract.

Do not create unsupported provider integrations merely because the architecture diagram contains them.

---

# 36. Uploads

If local archive upload is part of the approved M4 contract, M6 must treat uploaded content as untrusted.

The browser is only transmitting source content.

Validation/security remains a backend responsibility.

---

# 37. No Direct Storage Access

The frontend must never directly access:

```text
PostgreSQL
Redis
filesystem storage
repository storage paths
private object-storage credentials
```

The correct flow is:

```text
Browser
   ↓
FastAPI
   ↓
M4 ingestion/storage
   ↓
Storage
```

---

# 38. Repository Status

The frontend must display the backend's actual Repository lifecycle state.

It must not infer readiness from:

```text
upload button clicked
HTTP 200 from upload request
frontend timer
```

The backend state is authoritative.

---

# 39. Ingestion State

M6 should represent ingestion as a stateful operation.

Conceptually:

```text
Registered
    ↓
Ingesting
    ↓
Validating
    ↓
Stored / Ready
```

with appropriate failure states.

The exact state vocabulary must come from the M4 contract.

Do not invent states that have no backend equivalent.

---

# 40. Failed Ingestion

If ingestion fails, the UI should communicate:

```text
operation failed
```

and provide an appropriate recovery path where the backend supports retry.

Do not display:

```text
Ready
```

after a failed ingestion merely because the initial upload succeeded.

---

# 41. Long-Running Operations

Repository ingestion may not complete during the initial HTTP request.

M6 must be prepared for asynchronous or stateful backend processing if that is what M4 exposes.

Possible flow:

```text
Start ingestion
      ↓
202 / operation response
      ↓
Repository page
      ↓
poll/status refresh
      ↓
Ready / Failed
```

The exact mechanism must follow the backend contract.

Do not invent polling endpoints.

---

# 42. Loading States

Every asynchronous operation should have an appropriate loading state.

Examples:

```text
Loading projects...
Creating project...
Loading repository...
Registering repository...
Starting ingestion...
Refreshing status...
Deleting...
```

Avoid making the UI appear frozen.

---

# 43. Duplicate Submission Prevention

While a mutation is in progress:

```text
disable duplicate submission
```

where appropriate.

This is particularly important for:

```text
Project creation
Repository registration
Ingestion start
Deletion
```

The backend remains responsible for final idempotency/concurrency guarantees where required.

---

# 44. Validation

Frontend validation may provide immediate UX feedback for simple constraints such as:

```text
required field
empty name
obviously invalid input
file selection
```

But backend validation remains authoritative.

Do not duplicate complex M3/M4 validation logic in JavaScript.

---

# 45. Error Categories

M6 should distinguish at least:

```text
validation error
authentication error
authorization error
not found
conflict
network failure
backend/server failure
ingestion failure
```

Do not collapse all failures into:

```text
Something went wrong.
```

when the API provides actionable information.

---

# 46. Authentication Error

If authentication expires or is invalid:

```text
backend
    ↓
authentication failure
    ↓
frontend
    ↓
appropriate login/session handling
```

Do not silently treat an authentication failure as:

```text
Project not found
```

unless the backend contract intentionally uses a non-enumerating response for that resource.

---

# 47. Authorization Error

If the authenticated User lacks Project access:

```text
backend
    ↓
authorization denial
    ↓
frontend
    ↓
permission/error state
```

The frontend must not attempt to bypass it by changing IDs or routes.

---

# 48. Not Found

If a Project or Repository does not exist or is intentionally hidden due to authorization semantics, the frontend must display an appropriate resource-unavailable state.

Do not assume every 404 means:

```text
resource definitely never existed
```

because non-enumerating authorization can intentionally produce 404 behavior.

---

# 49. Conflict

Conflict responses may occur for:

```text
duplicate ProjectAccess
duplicate Repository registration
concurrent resource creation
```

depending on the relevant backend contract.

M6 should present a useful conflict message where the API provides one.

---

# 50. Network Failure

Network failure should be distinguishable from backend validation/authorization failures.

The UI should allow appropriate recovery such as:

```text
Retry
Refresh
Return to previous page
```

where appropriate.

---

# 51. Error Messages

Prefer backend-provided stable application error information where safe.

Do not display:

```text
stack traces
database errors
internal paths
provider exceptions
secret values
```

to users.

---

# 52. Frontend State

Use the simplest state mechanism sufficient for the P2 flow.

Do not introduce a large global state framework unless the existing frontend foundation already uses one or the actual product flow requires it.

Simple local state is preferred for simple pages.

---

# 53. No Global State for Everything

Avoid putting every value into a global store.

Examples that can usually remain local:

```text
form values
modal visibility
loading state
validation messages
temporary UI state
```

Global/shared state should be used only when genuinely shared across screens.

---

# 54. Authentication State

Authentication state may need to be shared across the application.

Keep its implementation simple.

Do not build an elaborate frontend authentication domain.

The backend remains authoritative.

---

# 55. Routing

Use the existing frontend routing mechanism if one already exists.

P2 likely needs routes conceptually similar to:

```text
/login
/projects
/projects/:projectId
/projects/:projectId/repositories/:repositoryId
```

Exact routes should follow the existing application conventions.

Do not create route hierarchies merely to mirror backend modules.

---

# 56. Protected Routes

Frontend route protection is a UX mechanism.

A protected page may redirect unauthenticated users to login.

But backend APIs must still enforce authentication.

Never rely solely on frontend route protection.

---

# 57. Navigation

Navigation should make the P2 flow obvious:

```text
Projects
   ↓
Project
   ↓
Repositories
   ↓
Repository
```

Do not expose internal architectural terminology such as:

```text
RepositoryAggregate
IngestionService
ArtifactStore
```

to ordinary users.

---

# 58. Project List UX

The Project list should support:

```text
loading
empty state
success
pagination if required
create Project
open Project
error
```

An empty list should be a valid state, not treated as an error.

---

# 59. Empty Project State

If the User has no accessible Projects:

```text
Projects
   ↓
No Projects
```

The UI can provide a clear next action such as:

```text
Create Project
```

provided the User has permission to create one.

Do not assume every authenticated User can create Projects if the backend says otherwise.

---

# 60. Project Creation Form

Keep the form simple.

Current Project fields are:

```text
name
description
```

Do not add:

```text
owner
organization
repository
analysis engine
AI provider
```

to Project creation unless explicitly required by the API contract.

---

# 61. Repository List UX

Within a Project, the Repository list should support:

```text
loading
empty state
repository registration
repository status
open repository
ingestion status
error
```

Do not imply that Repository registration means source ingestion has completed.

---

# 62. Repository Details UX

Repository details should expose useful P2 information returned by M3/M4.

Conceptually:

```text
Repository identity
Repository metadata
Lifecycle state
Ingestion state
Revision/source information where exposed
Errors where appropriate
```

Do not expose internal storage paths.

---

# 63. Ingestion Controls

If the backend exposes an explicit ingestion action, the UI may provide:

```text
Start ingestion
Retry ingestion
Refresh status
```

only when allowed by the backend state/contract.

Do not let the frontend determine valid lifecycle transitions independently.

---

# 64. State Transition Authority

Backend:

```text
authoritative
```

Frontend:

```text
reflective
```

Therefore:

```text
Frontend:
"Start ingestion button is visible."

Backend:
"Is this transition actually allowed?"
```

The backend answer is authoritative.

---

# 65. Polling

If ingestion is asynchronous and the backend provides a status endpoint, M6 may implement lightweight polling.

Keep it simple.

For example:

```text
start operation
   ↓
poll status periodically
   ↓
stop when terminal state reached
```

Do not create a generic workflow orchestration framework in the frontend.

---

# 66. Polling Safety

Polling should:

```text
stop on terminal state
stop when component/page is unmounted
avoid uncontrolled intervals
handle network errors
avoid excessive request frequency
```

Use the backend's operation/status contract.

---

# 67. Refresh

Where appropriate, the UI may provide:

```text
Refresh
```

for Project/Repository state.

A refresh should re-fetch authoritative backend state rather than attempting to reconstruct it locally.

---

# 68. Optimistic Updates

Avoid optimistic updates for business-critical operations unless the state transition is simple and rollback is reliable.

For example:

```text
Project deletion
Repository ingestion
```

should generally wait for backend confirmation before presenting final state.

---

# 69. Backend/API Layer Responsibilities

M6 backend work should focus on the public application API necessary to expose the M3/M4/M5 capabilities.

The backend API layer should:

```text
authenticate request
authorize request
validate DTO
invoke application service
return DTO
```

It should not:

```text
perform repository ingestion itself
access storage directly
implement SQL queries
implement authentication cryptography
contain frontend-specific business rules
```

---

# 70. Thin Router Rule

FastAPI routers should remain thin.

Conceptually:

```text
Router
  ↓
Dependency
  ↓
Application Service
  ↓
Domain / Repository / Infrastructure
```

Do not place business logic into route handlers merely because the endpoint is small.

---

# 71. API Dependency Injection

M6 should reuse the existing dependency registration mechanisms.

Do not create independent dependency systems for each router.

The API should resolve:

```text
CurrentUserProvider
ProjectAuthorization
ProjectService
RepositoryService
IngestionService
```

through the established architecture.

---

# 72. API Authorization

Every protected endpoint must use the appropriate authorization contract.

For Project resources:

```text
Current User
    ↓
ProjectAuthorization
    ↓
ProjectAccess
```

For Repository resources:

```text
Repository
    ↓
project_id
    ↓
ProjectAuthorization
```

Do not implement authorization by checking:

```text
repository.user_id
```

or frontend ownership state.

---

# 73. API Enumeration Protection

M2 established non-enumerating behavior for unauthorized Project retrieval.

M6 must preserve that behavior.

The frontend must not infer ownership or existence from response differences beyond the documented API contract.

---

# 74. Repository Authorization

M6 must consume the M3/M4 repository authorization behavior.

The frontend must not implement a separate Repository permission system.

---

# 75. Authentication Integration

M6 uses M5's identity/authentication contract.

The desired backend flow is:

```text
Request
  ↓
Authentication
  ↓
CurrentUser
  ↓
ProjectAuthorization
  ↓
Application Service
```

M6 must not bypass the authentication dependency for convenience.

---

# 76. API DTOs

M6 API endpoints should use explicit request/response DTOs.

Examples:

```text
CreateProjectRequest
ProjectResponse
CreateRepositoryRequest
RepositoryResponse
```

Exact DTOs depend on M3/M4 contracts.

Do not expose domain models directly.

---

# 77. HTTP Status Codes

M6 must preserve the established API semantics.

Existing Project examples include:

```text
POST create → 201
GET → 200
DELETE → 204
unauthorized access → established non-enumerating response
conflict → 409
```

Exact behavior for Repository/Ingestion endpoints must follow their contracts.

Do not change status codes merely to make frontend handling easier.

---

# 78. API Error Contract

The frontend should consume the centralized backend error format.

M6 must not create endpoint-specific error shapes without an explicit requirement.

The backend should continue translating application errors into stable API errors.

---

# 79. CORS

The frontend/backend integration must work under the actual development and deployment origins.

CORS configuration belongs to backend/infrastructure configuration.

Do not weaken security with unrestricted credentialed CORS.

---

# 80. File Upload UX

If M4 supports file/archive upload:

```text
file selection
    ↓
basic client validation
    ↓
upload request
    ↓
backend validation
    ↓
ingestion state
```

The frontend must not inspect source files to determine whether they are safe.

Backend validation remains authoritative.

---

# 81. Upload Limits

Frontend may provide an early user-friendly warning when file size exceeds a known limit.

But the backend must enforce the actual resource limit.

Do not treat frontend checks as security controls.

---

# 82. Untrusted Repository Content

The frontend should never execute or preview repository code in a way that creates a code-execution path.

Avoid:

```text
eval(uploadedSource)
```

or executing scripts received from repositories.

The repository is untrusted input.

---

# 83. No Analysis Logic in M6

M6 must not implement:

```text
language detection
framework detection
AST parsing
symbol extraction
relationship extraction
architecture construction
knowledge graph construction
AI explanation
```

Those responsibilities belong to later analysis/knowledge phases.

M6 only exposes the P2 ingestion boundary and the state needed for the next phase.

---

# 84. No P3 Leakage

Do not add P3 analysis UI merely because the product will eventually support it.

M6 may leave an explicit product boundary such as:

```text
Repository ready for analysis
```

without implementing the analysis experience.

---

# 85. No AI UI Requirement in M6

The high-level architecture contains AI capabilities, but M6 P2 implementation must not prematurely build:

```text
AI assistant
RAG interface
AI recommendations
AI architecture explanation
```

unless explicitly included in the P2 contract.

---

# 86. No Graph UI Requirement in M6

Do not implement:

```text
Knowledge Graph viewer
architecture graph
dependency graph
```

as part of P2 unless explicitly required.

Those are later product capabilities.

---

# 87. No Diagram Engine UI in M6

M6 should not implement diagram generation.

The P2 product flow ends at the repository being successfully ingested and ready for subsequent analysis.

---

# 88. Frontend Simplicity Rule

The frontend should favor:

```text
fewer files
fewer abstractions
direct page logic
small reusable components
simple API modules
simple state
```

over:

```text
large component libraries
deep folder trees
generic UI abstraction layers
multiple state-management layers
frontend domain/application/infrastructure mirroring
```

---

# 89. Frontend File Creation Rule

Before creating a new frontend file, ask:

```text
Does this code have a genuine independent responsibility?

Will it be reused?

Is the file meaningfully easier to maintain separately?

Does the existing structure already provide a suitable place?
```

If not, keep the code in the existing page/component/API module.

---

# 90. No One-Component-One-File Rule

Do not mechanically create a file for every:

```text
button
label
form field
card
section
text block
handler
```

Simple UI can remain together.

---

# 91. No Frontend Design-System Project

M6 is not responsible for creating a custom design system.

Use the existing styling/UI foundation.

Only introduce shared UI primitives when there is actual repeated use.

---

# 92. Frontend Styling

Use the existing project styling approach.

Do not introduce a second CSS framework or styling paradigm without an explicit requirement.

Keep styles close to the UI they serve when that is consistent with the existing frontend.

---

# 93. Responsive Behavior

P2 pages should remain usable across reasonable desktop/mobile viewport sizes where required by the existing product expectations.

Do not turn M6 into a separate responsive-design project.

---

# 94. Accessibility

Basic accessibility must be preserved:

```text
semantic controls
labels for inputs
keyboard-accessible actions
meaningful button text
visible error states
```

Do not sacrifice accessibility for frontend simplicity.

---

# 95. Loading UI

Loading states should avoid unnecessary layout jumps where practical.

A simple:

```text
Loading...
```

is acceptable where the page is otherwise straightforward.

Do not create a large skeleton-component architecture unless actually needed.

---

# 96. Empty UI

Every collection screen should have a meaningful empty state.

Examples:

```text
No projects yet.
No repositories in this project.
No repository revision available.
```

Where an action is available, provide it.

---

# 97. Error UI

Errors should be visible and actionable where possible.

Examples:

```text
Unable to load projects. Retry.
You do not have access to this project.
Repository ingestion failed. Retry.
Session expired. Sign in again.
```

Avoid displaying internal implementation details.

---

# 98. Form UX

Forms should:

```text
show required fields
validate obvious input errors
disable duplicate submission
show backend validation failures
preserve useful entered data after recoverable errors
```

Do not create complex form abstractions unless the existing frontend foundation requires them.

---

# 99. Navigation After Mutations

After successful mutations, navigate or update the current page based on the product flow.

Examples:

```text
Create Project
    ↓
open Project

Register Repository
    ↓
open Repository

Delete Project
    ↓
return to Projects
```

Exact navigation behavior should follow the existing frontend conventions.

---

# 100. Browser Refresh

Refreshing a Project/Repository page should reconstruct state from the backend.

Do not depend on an in-memory frontend state being present for the page to work.

---

# 101. Deep Links

Where routing supports direct URLs:

```text
/projects/:projectId
/projects/:projectId/repositories/:repositoryId
```

the page should fetch the required backend data.

Do not assume users always arrive through the Projects page.

---

# 102. Frontend Security

Do not treat frontend state as security.

Never rely on:

```text
hidden button
disabled button
protected route
localStorage flag
React state
```

for backend authorization.

The backend must validate every protected operation.

---

# 103. Sensitive Data

Do not store unnecessary sensitive authentication data in frontend state.

Do not log:

```text
tokens
passwords
authorization headers
private credentials
```

to the browser console.

---

# 104. API Logging

Development logging should not expose:

```text
Authorization
Cookie
password
token
secret
```

even when debugging API calls.

---

# 105. Testing Philosophy

M6 testing should verify the product flow without creating a huge frontend testing framework.

Focus on:

```text
important pages
important interactions
API integration
loading/error states
role-based UX
authentication flow
repository ingestion flow
```

---

# 106. Frontend Unit Tests

Where the frontend test setup supports them, test meaningful UI behavior:

```text
Project page renders
Project creation works
Repository page renders
loading state works
error state works
role-based controls are displayed appropriately
```

Do not test trivial JSX snapshots merely for coverage.

---

# 107. Frontend Integration Tests

Integration tests should verify:

```text
Page
  ↓
API client
  ↓
mocked/controlled backend
  ↓
response
  ↓
UI state
```

Important scenarios include:

```text
successful Project load
Project creation
Repository registration
ingestion state
authorization failure
authentication failure
network failure
```

---

# 108. Backend API Tests

M6 backend/API tests should verify:

```text
authentication dependency
authorization dependency
DTO validation
service invocation
HTTP status
response DTO
error contract
```

Routers should not be tested as isolated business engines.

---

# 109. Contract Testing

M6 should verify backend/frontend API compatibility.

The important contract is:

```text
Backend response
      ↓
Frontend API client
      ↓
Expected frontend state
```

If backend DTOs change, M6 must be updated deliberately.

Do not silently transform incompatible responses.

---

# 110. M6 Integration Test

The primary product integration should approximate:

```text
Authenticate
     ↓
GET Projects
     ↓
Create Project
     ↓
Open Project
     ↓
Create/Register Repository
     ↓
Start ingestion
     ↓
Observe ingestion state
     ↓
Repository becomes ready
```

The exact final ingestion state depends on M4.

---

# 111. Role-Based UI Test

At minimum verify:

```text
OWNER:
    mutation controls visible where applicable

ADMIN:
    mutation controls visible where applicable

DEVELOPER:
    delete controls not presented as available

VIEWER:
    mutation controls not presented as available
```

Again:

```text
UI visibility ≠ authorization
```

Backend tests remain authoritative.

---

# 112. Authentication Integration Test

Verify:

```text
Unauthenticated request
    ↓
authentication failure

Authenticated User
    ↓
CurrentUserProvider
    ↓
Project access
```

and:

```text
Authenticated User
    ↓
No ProjectAccess
    ↓
authorization denial
```

---

# 113. Project Isolation Test

Verify that the frontend cannot accidentally cause cross-project access.

Example:

```text
User A
    ↓
Project A
    ↓
Repository A

User B
    ↓
Project B
    ↓
Repository B
```

User A must not gain Project B access by manipulating:

```text
URL
project_id
repository_id
frontend state
```

The backend must enforce this.

---

# 114. Repository Isolation Test

Verify that a Repository belonging to Project A cannot be accessed by a User who lacks access to Project A.

The frontend must not assume repository IDs are globally accessible.

---

# 115. M6 and M3

M6 consumes M3's Repository contract.

M6 must not create:

```text
RepositoryV2
FrontendRepositoryModel
RepositoryRegistrationModel
```

as competing backend concepts.

A frontend representation is acceptable if it is simply a client-side representation of the API response.

---

# 116. M6 and M4

M6 consumes M4's ingestion/storage contract.

M6 must not implement:

```text
file discovery
path validation
archive extraction
storage
revision creation
artifact persistence
```

Those belong to M4.

---

# 117. M6 and M5

M6 consumes M5 authentication.

M6 must not implement:

```text
JWT verification
OAuth provider interaction
password hashing
identity provisioning
```

The frontend interacts with the authentication API only.

---

# 118. M6 and M2

M6 consumes M2 authorization semantics.

M6 must not implement:

```text
ProjectAccess persistence
ProjectRole rules
ProjectAuthorization
```

The UI may reflect the current role but cannot establish authorization.

---

# 119. API Boundary

The backend API should provide enough information for M6 to render the required UI without exposing internal implementation details.

If M6 requires information not present in the public contract:

```text
STOP
↓
identify contract gap
↓
check master.txt
↓
raise the gap
↓
update the API contract deliberately
```

Do not expose database models simply to satisfy the frontend.

---

# 120. Parallel Development Rule

M6 may be implemented while M3/M4/M5 are still being completed.

Therefore M6 should consume:

```text
established API contracts
DTO definitions
lifecycle definitions
authentication contract
authorization contract
```

rather than depending on internal implementation details.

---

# 121. Contract Gap Rule

If an upstream module does not expose something M6 genuinely requires:

```text
STOP
   ↓
identify missing contract
   ↓
verify master.txt
   ↓
determine whether the capability belongs upstream
   ↓
propose the smallest contract change
   ↓
obtain approval
   ↓
update contract
   ↓
continue implementation
```

Do not create a frontend workaround that changes business semantics.

---

# 122. No Mock-Driven Architecture

During parallel development, mocks may be used for frontend testing.

However, mocks must represent the actual approved backend contract.

Do not design the backend around an invented frontend mock.

---

# 123. No Frontend-First Contract Changes

If the frontend developer prefers a different response shape:

```text
do not change backend architecture solely for convenience
```

First determine whether the existing contract is authoritative.

Use a small frontend adapter only when appropriate and consistent with the architecture.

---

# 124. API Contract Stability

Once M3/M4/M5 contracts are established, M6 should treat them as integration contracts.

Breaking changes must be deliberate.

Do not silently rename:

```text
fields
states
IDs
status values
error codes
```

because they are inconvenient in the UI.

---

# 125. Frontend Data Naming

Frontend data naming should remain consistent with backend API semantics.

Do not silently rename:

```text
project_id
repository_id
created_at
updated_at
status
```

into unrelated concepts throughout the application.

A small UI-specific mapping is acceptable if clearly isolated.

---

# 126. Dates and Times

Backend timestamps are authoritative.

The frontend may format timestamps for display.

It must not modify the underlying timestamps or treat local display time as persisted state.

---

# 127. IDs

IDs should be treated as opaque identifiers.

Do not infer semantics from UUID structure.

Do not construct IDs on the frontend.

Do not use names as substitutes for IDs where the backend contract expects IDs.

---

# 128. Delete Confirmation

Delete confirmation should clearly indicate the resource affected.

For Project deletion, the UI should not imply that only the visible page disappears if the backend semantics delete the Project and its related ProjectAccess/resources.

The actual consequence must follow the backend contract.

---

# 129. Mutation Recovery

After a failed mutation:

```text
do not silently remove the item from UI
```

unless the backend confirmed success.

Re-fetch or restore state as appropriate.

---

# 130. Stale State

When returning to a Project or Repository after a mutation, the frontend should use backend state rather than assuming the previous client state remains correct.

Simple re-fetching is preferable to elaborate cache invalidation machinery for this phase.

---

# 131. No Premature Client Cache

Do not introduce a large caching framework solely for M6.

If the existing frontend already has a data-fetching/cache mechanism, use it.

Otherwise simple fetch/state patterns are sufficient for the P2 scope.

---

# 132. Performance

M6 should meet the general P2 frontend performance expectations without premature optimization.

Avoid:

```text
unnecessary API requests
unbounded polling
large duplicated data structures
loading the entire Project dataset when pagination exists
```

---

# 133. Accessibility of Errors

Form/API errors should be visible to users and associated with the relevant action/input where practical.

Do not communicate critical errors only through console logs.

---

# 134. Browser Refresh During Ingestion

If a User refreshes the Repository page during ingestion:

```text
page reload
    ↓
GET repository/status
    ↓
display current backend state
```

The frontend must not reset the Repository to:

```text
Registered
```

merely because local state was lost.

---

# 135. Browser Close During Ingestion

If ingestion continues server-side, closing the browser must not falsely cancel or mark the ingestion as failed.

The backend lifecycle is authoritative.

---

# 136. Frontend API Error Boundary

The frontend should have a simple consistent approach for API errors.

Do not implement a different error interpretation on every page.

A small shared helper is acceptable if it genuinely reduces duplication.

---

# 137. Simple Frontend Helpers

Acceptable shared helpers include:

```text
api request helper
error parser
authentication state helper
formatting helper
```

Avoid creating generic abstractions without repeated use.

---

# 138. Frontend Environment Configuration

Frontend API base URLs/configuration should use the existing project environment/configuration mechanism.

Do not hard-code production API URLs into source.

---

# 139. Development Configuration

Local development may point to the local backend.

Production deployment should use the appropriate configured backend endpoint.

Do not create separate hard-coded API clients for each environment.

---

# 140. No Backend Secrets in Frontend

Never expose:

```text
database credentials
JWT signing secrets
OAuth client secrets
private keys
repository storage credentials
```

in frontend environment variables that are bundled into the browser.

Public frontend configuration is not secret.

---

# 141. M6 Backend Security

All protected M6 endpoints must enforce:

```text
authentication
+
Project/resource authorization
```

Frontend visibility does not replace these checks.

---

# 142. API Input Validation

The backend remains responsible for final validation.

M6 may provide UX validation but must not assume it is enough.

Examples:

```text
Project name
Repository name
Repository source
upload size
```

must be validated by the backend according to their contracts.

---

# 143. API Idempotency

If an operation can be retried safely, the backend should provide appropriate semantics.

M6 should not invent client-side idempotency keys unless the API contract supports them.

For network retry behavior, avoid automatically repeating destructive operations without knowing whether the first request succeeded.

---

# 144. Retry Behavior

Safe reads:

```text
GET Projects
GET Project
GET Repository
```

may be retried where appropriate.

Mutations:

```text
POST
DELETE
ingestion start
```

should not be blindly retried unless the API contract guarantees safe retry semantics.

---

# 145. Product Flow — Authentication

The expected product flow begins approximately as:

```text
Open StackSense
      ↓
Authentication state
      ↓
Login if required
      ↓
Authenticated User
      ↓
Projects
```

M5 defines the authentication contract.

M6 presents the user-facing experience.

---

# 146. Product Flow — Projects

```text
Projects
   │
   ├── Load accessible Projects
   │
   ├── Empty state
   │
   ├── Create Project
   │
   └── Open Project
```

---

# 147. Product Flow — Project

```text
Project
   │
   ├── Project information
   │
   ├── Repository list
   │
   ├── Register Repository
   │
   └── Project actions allowed by backend permissions
```

---

# 148. Product Flow — Repository

```text
Repository
   │
   ├── Metadata
   │
   ├── Source/acquisition information
   │
   ├── Ingestion state
   │
   ├── Revision/status information
   │
   └── Ready for analysis
```

---

# 149. Product Flow — Ingestion

```text
Repository registered
       ↓
Source supplied
       ↓
Ingestion started
       ↓
Backend validation
       ↓
Storage
       ↓
Revision/artifact state
       ↓
Ready
```

Failure:

```text
       ↓
     Failed
       ↓
Retry if supported
```

---

# 150. P2 Vertical Slice

The complete M6 product experience should demonstrate:

```text
Browser
  ↓
Login
  ↓
Authenticated User
  ↓
Projects
  ↓
Create Project
  ↓
Project Details
  ↓
Register Repository
  ↓
Provide Repository Source
  ↓
Start/observe ingestion
  ↓
Repository becomes ready
```

This is the core P2 user-facing slice.

---

# 151. P3 Boundary

M6 should end at:

```text
Repository ready for analysis
```

It should not implement the full P3 analysis experience.

Later phases may consume:

```text
Repository Revision
Source Artifacts
Analysis Input
```

but M6 does not implement those analysis engines.

---

# 152. M6 Definition of Done

M6 is complete only when:

```text
Authentication flow is usable
Project list is usable
Project creation is usable
Project details are usable
Repository registration is usable
Repository source acquisition flow is usable
Ingestion state is visible
Repository readiness is visible
Backend authorization is enforced
Frontend role visibility reflects permissions where appropriate
Frontend remains simple
No Views layer is introduced
No excessive component architecture is introduced
No duplicated frontend business logic exists
API contracts match backend contracts
Loading states work
Empty states work
Error states work
Authentication failures are handled
Authorization failures are handled
Network failures are handled
Destructive operations require confirmation
Duplicate mutation submission is prevented
Backend remains authoritative
Frontend does not access storage directly
Frontend does not execute repository source
M1/M2 behavior remains unchanged
M3/M4/M5 contracts are consumed correctly
Frontend tests pass
Backend API tests pass
Integration tests pass
Architecture tests pass
Absolute imports remain enforced
End-to-end P2 vertical slice works
```

---

# 153. M6 Implementation Order

Recommended implementation sequence:

```text
1. Read master.txt P2/API/frontend sections
2. Read M1-M2 shared context
3. Read M3 context
4. Read M4 context
5. Read M5 context
6. Inspect existing frontend structure
7. Inspect existing frontend routing
8. Inspect existing frontend API client
9. Inspect existing backend OpenAPI/API contracts
10. Identify exact M3/M4/M5 endpoints
11. Verify DTOs and response shapes
12. Implement/finish required backend API endpoints
13. Implement authentication UI
14. Implement Projects page
15. Implement Project creation
16. Implement Project details
17. Implement Repository registration flow
18. Implement Repository details
19. Implement ingestion/status flow
20. Add loading states
21. Add empty states
22. Add error handling
23. Add appropriate role-based UI visibility
24. Add frontend integration tests
25. Add backend API tests
26. Add end-to-end P2 flow
27. Verify cross-project isolation
28. Verify authentication/authorization
29. Verify fresh database
30. Run full regression suite
31. Run architecture/security checks
32. Prepare M7 integration handoff
```

---

# 154. Frontend File Creation Checklist

Before adding a frontend file:

```text
[ ] Is the responsibility genuinely separate?
[ ] Is the code reused?
[ ] Is separation actually improving maintainability?
[ ] Does an existing page/component/API module already fit?
[ ] Is the file necessary for the P2 vertical slice?
```

If the answer is mostly no:

```text
keep the code in the existing file.
```

---

# 155. Frontend Anti-Patterns

Do not introduce:

```text
components for every HTML element
deep component nesting
views/ layer
frontend domain layer
frontend application layer
frontend infrastructure layer
repository pattern for every API call
generic service factories
global state for local UI
large client-side permission engine
large client-side cache
custom design system
duplicate HTTP libraries
duplicate routing systems
premature abstraction
```

---

# 156. Backend Anti-Patterns

Do not introduce:

```text
business logic in routers
direct SQLAlchemy access from routers
direct storage access from routers
authentication logic in routers
frontend-specific domain models in backend
duplicate Repository models
duplicate authorization systems
Repository RBAC
Organization hierarchy
Project.owner_id
raw persistence models in API responses
```

---

# 157. API Contract Gap Protocol

If M6 needs something not exposed by the backend:

```text
Question 1:
Does master.txt require it?

Question 2:
Does the upstream module already own it?

Question 3:
Can the existing contract provide it?

Question 4:
Would adding it violate a frozen boundary?
```

If the answer indicates a genuine missing capability:

```text
STOP
↓
document contract gap
↓
coordinate with upstream module
↓
approve contract change
↓
implement deliberately
```

Do not solve it with hidden frontend assumptions.

---

# 158. M6 Security Checklist

```text
[ ] Protected API endpoints require authentication
[ ] Project authorization is backend-enforced
[ ] Repository authorization derives from Project
[ ] Frontend controls are not treated as security
[ ] No secrets are bundled into frontend
[ ] Tokens/credentials are not logged
[ ] Repository source is never executed
[ ] Upload limits are backend-enforced
[ ] Cross-project access is denied
[ ] Unauthorized resources are handled according to API contract
[ ] Destructive actions require confirmation
[ ] Mutations are not blindly retried
[ ] CORS is not unnecessarily permissive
[ ] Backend remains authoritative
```

---

# 159. M6 Architecture Checklist

```text
[ ] master.txt followed
[ ] M1/M2 frozen contracts preserved
[ ] M3 contract consumed
[ ] M4 contract consumed
[ ] M5 authentication contract consumed
[ ] Project remains primary product boundary
[ ] Organization not reintroduced
[ ] Project.owner_id not introduced
[ ] Repository RBAC not introduced
[ ] ProjectAccess not duplicated
[ ] ProjectAuthorization not duplicated
[ ] Authentication not duplicated
[ ] Frontend remains simple
[ ] No Views layer
[ ] No excessive component decomposition
[ ] No frontend business-truth duplication
[ ] API routers remain thin
[ ] DTOs are explicit
[ ] Absolute imports are preserved
[ ] Existing HTTP/client foundation is reused
[ ] Existing routing foundation is reused
```

---

# 160. Testing Checklist

```text
[ ] Authentication UI tests
[ ] Project list tests
[ ] Project creation tests
[ ] Project detail tests
[ ] Repository registration tests
[ ] Repository detail tests
[ ] Ingestion state tests
[ ] Loading state tests
[ ] Empty state tests
[ ] Validation error tests
[ ] Authentication error tests
[ ] Authorization error tests
[ ] Network failure tests
[ ] Role-based UI tests
[ ] Backend API tests
[ ] API contract tests
[ ] Project isolation tests
[ ] Repository isolation tests
[ ] End-to-end P2 flow
[ ] Full regression suite
```

---

# 161. Independent Review

The independent reviewer must review M6 separately from the Builder's implementation report.

Review:

```text
API contract correctness
authentication integration
authorization integration
Project flow
Repository flow
ingestion flow
frontend simplicity
frontend structure
state management
error handling
loading/empty states
security
cross-project isolation
backend/frontend contract compatibility
testing
architecture compliance
regression
```

The reviewer must not silently modify the implementation.

---

# 162. Reviewer Severity

Use:

```text
BLOCKER
MAJOR
MINOR
OBSERVATION
```

with decision:

```text
PASS
PASS WITH NON-BLOCKING FINDINGS
CHANGES REQUIRED
```

Findings must be evidence-based.

Do not report personal frontend style preference as an architectural defect unless it violates an explicit requirement.

---

# 163. M6 Forbidden Outcomes

M6 implementation is invalid if it introduces:

```text
Organization UI hierarchy
Project.owner_id UI/API field
Repository-level RBAC UI
frontend-authoritative authorization
frontend-authoritative lifecycle state
direct frontend storage access
repository source execution
large frontend architecture
Views layer
excessive component decomposition
duplicate HTTP client
duplicate routing architecture
duplicate backend business logic
duplicate authentication logic
duplicate ProjectAccess logic
duplicate ProjectAuthorization logic
P3 analysis UI implemented as P2 requirement
AI/RAG functionality implemented prematurely
Knowledge Graph functionality implemented prematurely
uncontrolled polling
blind mutation retries
hard-coded production API URLs
frontend secrets
raw backend exceptions displayed to users
SQLAlchemy models exposed through API
relative backend imports
silent API contract changes
```

---

# 164. Final M6 Contract

```text
M6 = P2 API & Frontend Product Flow

Consumes:
    M1 Project foundation
    M2 ProjectAccess / ProjectAuthorization
    M3 Repository contracts
    M4 Ingestion/validation/storage contracts
    M5 Authentication/current-user contracts

Owns:
    P2-facing API integration
    frontend product flow
    frontend navigation
    frontend forms
    frontend loading/error/empty states
    API consumption
    P2 product integration tests

Provides:
    usable authenticated Project experience
    usable Repository experience
    ingestion/status experience
    backend/frontend contract integration
    P2 vertical product slice

Does not own:
    Project domain
    ProjectAccess
    ProjectAuthorization
    User authentication internals
    Repository domain
    repository storage
    ingestion implementation
    source validation implementation
    source analysis
    IR
    Architecture Model
    Knowledge Graph
    RAG
    AI
    diagram generation
```

---

# 165. Final Product Flow

```text
                         ┌──────────────────────┐
                         │       Browser        │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Authentication     │
                         │         M5           │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       Projects       │
                         │         M6           │
                         └──────────┬───────────┘
                                    │
                              create/open
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       Project        │
                         │    M2 boundary       │
                         └──────────┬───────────┘
                                    │
                           register repository
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     Repository       │
                         │         M3           │
                         └──────────┬───────────┘
                                    │
                             provide source
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      Ingestion       │
                         │         M4           │
                         └──────────┬───────────┘
                                    │
                         validate / store / state
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Repository Ready for │
                         │      Analysis        │
                         └──────────────────────┘
                                    │
                                    ▼
                              P3 boundary
```

---

# 166. Non-Negotiable Rules

```text
1. master.txt remains the ultimate source of truth.

2. M1 and M2 are frozen.

3. M6 consumes M3, M4, and M5 contracts.

4. Project remains the primary product boundary.

5. Organization must not be reintroduced.

6. Project.owner_id must not be introduced.

7. ProjectAccess remains the membership/access model.

8. ProjectAuthorization remains the authorization mechanism.

9. Repository authorization remains derived from Project authorization.

10. Repository-level RBAC must not be introduced.

11. Authentication remains an M5 responsibility.

12. Ingestion remains an M4 responsibility.

13. Repository identity/registration remains an M3 responsibility.

14. M6 must not execute repository source.

15. M6 must not access PostgreSQL directly from the frontend.

16. M6 must not access private storage directly from the frontend.

17. Backend state is authoritative.

18. Frontend state is presentation state.

19. Frontend role checks are UX only.

20. Backend authorization is mandatory.

21. API contracts must match the established backend contracts.

22. Do not silently change backend response shapes for frontend convenience.

23. Do not introduce a Views folder.

24. Do not introduce a complex frontend architecture.

25. Do not mechanically split every component into its own file.

26. Do not create reusable components without genuine reuse or meaningful responsibility.

27. Prefer a simple pages/components/api/hooks structure where needed.

28. Do not introduce a large frontend state-management system without a concrete need.

29. Do not introduce a second HTTP client.

30. Do not introduce a second routing system.

31. Do not introduce P3 analysis functionality into M6.

32. Do not introduce AI/RAG functionality into M6.

33. Do not introduce Knowledge Graph functionality into M6.

34. Do not make ingestion appear complete before the backend says it is complete.

35. Do not blindly retry destructive mutations.

36. Do not expose backend stack traces or secrets to users.

37. Do not log tokens, passwords, or secrets.

38. Do not hard-code production API URLs or secrets.

39. Do not rewrite historical migrations.

40. Absolute imports are mandatory on the backend.

41. Routers remain thin.

42. DTOs remain explicit.

43. Persistence models must not be exposed directly through API responses.

44. Any missing upstream capability must be raised as a contract gap.

45. Parallel developers consume upstream contracts rather than creating competing abstractions.

46. No silent architecture changes are permitted.
```

---

# 167. M6 Handoff to M7

M6 is ready for M7 when the following can be demonstrated:

```text
Authenticated User
      ↓
Projects page
      ↓
Create Project
      ↓
Open Project
      ↓
Register Repository
      ↓
Provide Repository Source
      ↓
Start/observe ingestion
      ↓
Repository status
      ↓
Ready for Analysis
```

and:

```text
authentication works
authorization works
Project isolation works
Repository isolation works
ingestion state is accurate
frontend/backend contracts match
frontend remains simple
tests pass
architecture checks pass
security checks pass
```

At that point M7 can perform full integration, evaluation preparation, regression verification, and P2 freeze.