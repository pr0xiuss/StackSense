# Module Context: M5 — Identity & Authentication

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

M5 owns the identity and authentication capabilities required by the StackSense product.

Its responsibilities must integrate with the Project-based authorization model established by M1/M2.

## Critical Responsibilities

M5 is concerned with:

- user identity
- authentication
- identity lifecycle
- authentication mechanisms
- current-user resolution
- authentication security
- identity-related infrastructure
- integration with authorization boundaries

## Authorization Boundary

Authentication establishes **who the current user is**.

Project authorization determines **what that user may do within a Project**.

Do not replace ProjectAccess / ProjectAuthorization with a separate authorization hierarchy.

## Project Boundary

The authoritative ownership and access model remains:

`User → Project → Repository`

Do not reintroduce Organization as a first-class hierarchy.

Do not introduce Repository-level RBAC without an explicit architectural decision.

## Frozen Dependencies

M1 and M2 contracts remain authoritative.

M5 must integrate with existing identity/current-user and authorization contracts rather than silently replacing them.

## Security Rule

Identity and authentication functionality must follow the security requirements defined by `master.txt`.

Do not weaken authentication, authorization, isolation, credential handling, or security boundaries for implementation convenience.

## Implementation Rule

This context provides implementation guidance only.

It does not authorize architectural expansion or changes to `master.txt`.


**Location:** `.agents/context/modules/M5-CONTEXT.md`

**Status:** FROZEN FOR IMPLEMENTATION  
**Phase:** P2 — Project & Repository Platform  
**Module:** M5 — Identity & Authentication  
**Upstream:** M1 Foundation + M2 Project Access + existing identity seam  
**Downstream:** M3 Repository Platform, M4 Repository Ingestion, M6 API & Frontend Product Flow, M7 Integration & P2 Freeze

---

# 1. Purpose

M5 establishes the real identity and authentication foundation for StackSense.

M1/M2 already introduced an intentional identity abstraction:

```text
CurrentUserProvider
```

and a temporary implementation:

```text
StaticCurrentUserProvider
```

M5 replaces the temporary identity implementation with the real authentication and user-identity mechanism.

The most important M5 principle is:

```text
M5 replaces the identity implementation.

M5 does NOT redesign the authorization architecture.
```

The established ProjectAccess and ProjectAuthorization model remains the resource authorization boundary.

---

# 2. Architectural Authority

The ultimate architectural authority is:

```text
master.txt
```

This file captures the implementation context for M5.

It does not replace or supersede `master.txt`.

If this context conflicts with the authoritative architecture:

```text
1. Stop the conflicting implementation.
2. Verify master.txt.
3. Identify the authoritative decision.
4. Resolve the contract explicitly.
5. Do not silently change the architecture.
```

---

# 3. Required Upstream Context

Before implementing M5, the developer must read:

```text
.agents/context/shared/M1-M2-CONTEXT.md
.agents/context/modules/M3-CONTEXT.md
.agents/context/modules/M4-CONTEXT.md
```

M5 must understand the existing identity seam before modifying identity behavior.

---

# 4. P2 Module Map

The relevant P2 architecture is:

```text
M1
Project Domain Foundation
        │
        ▼
M2
Project Access & Resource Boundary
        │
        ├──────────────► M3 Repository Platform
        │
        └──────────────► M4 Repository Ingestion
                               
M5
Identity & Authentication
        │
        ├──────────────► M3
        ├──────────────► M4
        └──────────────► M6

M6
P2 API & Frontend Product Flow

M7
Integration, Evaluation & P2 Freeze
```

M5 provides the authenticated identity that M2 authorization already expects.

---

# 5. M5 Mission

M5 must establish a production-ready identity boundary that answers:

```text
Who is making this request?
```

and provides that identity to the existing authorization system.

The desired conceptual flow is:

```text
Authentication
      │
      ▼
Authenticated User
      │
      ▼
CurrentUserProvider
      │
      ▼
ProjectAuthorization
      │
      ▼
ProjectAccess
      │
      ▼
ProjectRole
      │
      ▼
Resource Permission
```

M5 owns the first portion.

M2 owns the Project authorization portion.

---

# 6. Authentication vs Authorization

These are separate concerns.

Authentication answers:

```text
Who are you?
```

Authorization answers:

```text
What are you allowed to do?
```

Therefore:

```text
Authentication
      ↓
Identity
      ↓
Authorization
```

M5 must not merge these responsibilities.

---

# 7. What M5 Owns

M5 owns the identity/authentication boundary, including where required:

```text
User identity
User persistence
Authentication
Credential handling
Authentication tokens/session mechanism
Current-user resolution
Authentication dependencies
Authentication API
Authentication-related security
Identity lifecycle
Identity-related persistence
Identity tests
```

The exact implementation must follow the authoritative architecture and frozen technology stack.

---

# 8. What M5 Does Not Own

M5 does not own:

```text
ProjectAccess
ProjectRole
ProjectAuthorization
Repository authorization
Repository-level RBAC
Project ownership
Repository ownership
Repository ingestion
Repository storage
Source analysis
IR
Architecture Model
Knowledge Graph
RAG
AI
Frontend business authorization
```

M5 supplies identity to these systems.

It does not replace their resource-specific contracts.

---

# 9. Existing Identity Seam

The existing identity contract is:

```text
backend/platform/identity/application/current_user.py
```

It contains the established:

```text
CurrentUserProvider
```

abstraction.

The temporary implementation is:

```text
StaticCurrentUserProvider
```

This seam exists specifically so downstream authentication can be implemented without forcing the rest of the application to depend on a temporary identity mechanism.

---

# 10. CurrentUserProvider Is the Stable Boundary

The preferred dependency direction is:

```text
Application Service
       │
       ▼
CurrentUserProvider
       │
       ▼
Authenticated Identity Implementation
```

Application services must not directly depend on:

```text
JWT library
OAuth provider SDK
FastAPI request internals
authorization header parsing
password database implementation
```

unless such dependencies belong behind the identity infrastructure boundary.

---

# 11. M5 Must Preserve Existing Callers

Existing consumers use the established identity dependency.

M5 should preserve the existing application-facing contract wherever possible.

The desired migration is:

```text
Before M5:

CurrentUserProvider
       ↓
StaticCurrentUserProvider


After M5:

CurrentUserProvider
       ↓
Real authenticated provider
```

rather than:

```text
Before M5:

CurrentUserProvider


After M5:

Every service rewritten around a new authentication architecture
```

The abstraction was introduced to prevent that kind of unnecessary rewrite.

---

# 12. Temporary Identity Must Be Removed From Production Behavior

`StaticCurrentUserProvider` is a testing/development seam, not the final production authentication mechanism.

M5 should establish the real provider for authenticated application requests.

The temporary provider may remain available for deterministic tests where appropriate.

Do not make production authentication depend on a hard-coded user.

---

# 13. User Identity

M5 owns the canonical User identity model required by the platform.

The User should have a stable identifier that can be referenced by:

```text
ProjectAccess.user_id
audit records
authentication identity
future resource ownership/access records
```

The exact User fields must follow the authoritative architecture.

Do not add speculative profile/product fields merely because they may become useful later.

---

# 14. User vs ProjectAccess

A User and ProjectAccess are different concepts.

```text
User
    ↓
identity

ProjectAccess
    ↓
relationship between User and Project
```

The correct model remains:

```text
User
   │
   └── ProjectAccess
          │
          ├── project_id
          └── role
```

Do not merge ProjectAccess into User.

---

# 15. No Project Owner Field

M5 must not introduce:

```text
Project.owner_id
```

User identity does not change the established Project ownership model.

Ownership remains represented through:

```text
ProjectAccess(role=OWNER)
```

---

# 16. ProjectAccess User Relationship

M2 established:

```text
ProjectAccess.user_id
```

as the identity reference.

M5 owns the canonical User persistence model.

Where the final architecture requires database-level referential integrity between User and ProjectAccess, M5 may establish it through a new migration.

Do not rewrite historical M2 migrations.

---

# 17. Migration Rule

M5 must create new migrations for identity schema changes.

Never rewrite:

```text
M1 migrations
M2 migrations
```

Historical migration files are frozen.

If M5 requires:

```text
users
```

or a User foreign-key relationship, it must be introduced through a new migration.

---

# 18. User Persistence

The User persistence model belongs to infrastructure.

Conceptually:

```text
User Domain
      │
      ▼
User Repository Contract
      │
      ▼
SQLAlchemy User Model
      │
      ▼
PostgreSQL
```

Do not expose SQLAlchemy User models directly to API consumers.

---

# 19. User Repository

M5 may provide a User repository contract for actual application use cases.

Typical operations may include:

```text
save
get_by_id
get_by_identity
```

Additional operations should exist only when required by concrete authentication/identity use cases.

Do not create a large generic User repository containing speculative operations.

---

# 20. User Identity Lookup

Authentication needs a deterministic mapping between an authenticated principal and the canonical application User.

Conceptually:

```text
Authenticated Principal
        │
        ▼
Identity Lookup
        │
        ▼
Application User
        │
        ▼
CurrentUserProvider
```

The identity lookup mechanism must follow the authoritative authentication architecture.

---

# 21. Authentication Boundary

The authentication layer should isolate external authentication mechanisms from application identity.

Conceptually:

```text
HTTP Request
      │
      ▼
Authentication Infrastructure
      │
      ▼
Authenticated Principal
      │
      ▼
User Identity Resolution
      │
      ▼
CurrentUserProvider
```

Application services should consume the resulting identity rather than parsing authentication credentials themselves.

---

# 22. Authentication Technology

The high-level architecture identifies:

```text
JWT / OAuth 2.0
```

as the authentication/authorization integration area.

The exact authentication mechanism and provider behavior must follow the frozen technology decisions in `master.txt`.

Do not introduce a second authentication mechanism merely because it is easier to implement.

---

# 23. Token/Session Boundary

If JWT-based authentication is used, token parsing and validation belong to the authentication infrastructure.

Application services must receive:

```text
authenticated user
```

rather than:

```text
raw JWT
```

If an OAuth2 provider is used, provider-specific details must remain behind the identity boundary.

Do not leak provider SDK models into domain/application contracts.

---

# 24. Authentication Failure

Authentication failure is different from authorization failure.

Conceptually:

```text
No valid identity
       ↓
Authentication failure
```

whereas:

```text
Valid identity
       ↓
No ProjectAccess
       ↓
Authorization failure
```

Do not translate every authentication problem into a ProjectAccess error.

---

# 25. Authentication Error Contract

M5 should use the existing typed application error conventions.

Potential categories include:

```text
AUTHENTICATION
AUTHORIZATION
VALIDATION
CONFLICT
NOT_FOUND
```

Exact error codes and categories must follow the established project error contract.

Raw authentication-library exceptions must not leak through the API.

---

# 26. Invalid Credentials

Invalid credentials must not reveal unnecessary information.

Avoid responses that distinguish sensitive account details such as:

```text
user exists
password was wrong
token belongs to a real account
```

unless the authoritative authentication contract explicitly requires such behavior.

---

# 27. Token Expiration

Expired credentials must be handled as authentication failure.

The application should not treat an expired identity as an authenticated user.

Where refresh behavior exists, it must remain within the authentication boundary.

Do not allow expired credentials to reach ProjectAuthorization as if they were valid.

---

# 28. Token Validation

Authentication infrastructure must validate the required properties of credentials according to the selected mechanism.

For JWT-style authentication this generally includes the configured claims and cryptographic validation.

The exact validation rules must come from the authoritative authentication contract.

Do not implement ad-hoc token parsing.

---

# 29. Secret Handling

Secrets must never be:

```text
logged
returned in API responses
stored in plain text unnecessarily
embedded in source code
embedded in repository metadata
stored in frontend source
included in exception messages
```

This includes:

```text
passwords
access tokens
refresh tokens
provider client secrets
private keys
repository credentials
```

---

# 30. Password Handling

If local credential authentication is part of the approved M5 architecture:

```text
passwords must never be stored in plaintext
```

Authentication must use an approved password hashing mechanism.

Do not implement custom cryptographic algorithms.

Do not log passwords during development or tests.

---

# 31. OAuth Provider Boundary

If OAuth2/external identity providers are supported, provider-specific behavior belongs in infrastructure.

Conceptually:

```text
OAuth Provider
      │
      ▼
Authentication Adapter
      │
      ▼
Canonical User
      │
      ▼
CurrentUserProvider
```

Do not make ProjectAccess depend on:

```text
GitHubUser
GoogleUser
OAuthUser
ProviderUser
```

as its identity type.

ProjectAccess references the canonical application User.

---

# 32. External Provider Identity

If external authentication identities are stored, they should be represented separately from the canonical User identity.

Conceptually:

```text
User
  │
  └── External Identity
          ├── provider
          └── provider subject
```

The exact schema must follow the authoritative architecture.

Do not assume a provider email address is sufficient as a permanent identity key.

---

# 33. User Identity Stability

Application User identity must remain stable even if external authentication details change.

For example, changing an external provider attribute must not silently create a second application User when the architecture expects the same identity.

The exact account-linking semantics must follow the approved authentication design.

---

# 34. Current User Resolution

The current-user dependency should conceptually perform:

```text
Request
   ↓
Authenticate
   ↓
Resolve principal
   ↓
Resolve canonical User
   ↓
CurrentUserProvider
   ↓
Application service
```

It should not:

```text
load arbitrary Project
determine ProjectRole
perform Repository authorization
```

Those are authorization/resource responsibilities.

---

# 35. CurrentUserProvider vs ProjectAuthorization

These abstractions must remain separate.

```text
CurrentUserProvider
    ↓
Who is the user?

ProjectAuthorization
    ↓
What can this user do in this Project?
```

Do not combine them into:

```text
UserAuthorizationService
```

that owns every identity and resource decision unless a future architectural decision explicitly establishes such a design.

---

# 36. Authorization Remains M2

M5 must preserve the established:

```text
ProjectAuthorization
```

contract.

The flow remains:

```text
CurrentUserProvider
       ↓
ProjectAuthorization
       ↓
ProjectAccess
       ↓
ProjectRole
```

M5 must not replace this with a generic role system.

---

# 37. No Repository RBAC

M5 must not introduce:

```text
RepositoryRole
RepositoryAccess
RepositoryMember
```

Authentication does not imply Repository-level authorization.

Repository authorization remains derived from the owning Project.

---

# 38. No Organization Identity Boundary

M5 must not reintroduce Organization as a first-class authorization/ownership layer.

Do not create:

```text
OrganizationUser
OrganizationMembership
OrganizationRole
organization_id
```

unless a future authoritative architecture decision explicitly introduces them.

The current hierarchy remains:

```text
User
  ↓
Project
  ↓
Repository
```

---

# 39. User Lifecycle

M5 should define the User lifecycle required by the architecture.

Potential lifecycle concerns include:

```text
creation
activation
authentication eligibility
deactivation
```

The exact state model must follow the authoritative contract.

Do not invent a complex account-state machine without a concrete requirement.

---

# 40. Disabled Users

If user deactivation is supported, a disabled user must not be treated as authenticated merely because their credential is structurally valid.

The authentication/current-user boundary must enforce the appropriate identity state.

Existing ProjectAccess records should not automatically be destroyed merely because a user is disabled unless the architecture explicitly requires that behavior.

---

# 41. User Deletion

User deletion has implications for:

```text
ProjectAccess
audit records
future resource ownership
external identities
historical activity
```

Do not implement hard deletion casually.

If user deletion is required, its data-retention and referential semantics must be explicitly defined.

---

# 42. ProjectAccess Preservation

M5 must preserve ProjectAccess semantics.

The following remain authoritative:

```text
OWNER
ADMIN
DEVELOPER
VIEWER
```

with the established permissions.

M5 must not change ProjectAccess roles merely because authentication is being implemented.

---

# 43. Test Identity Seam

The test suite must retain a deterministic way to establish a current user.

The existing:

```text
StaticCurrentUserProvider
```

can remain useful for tests.

A test should be able to establish:

```text
current user = UUID
```

without:

```text
real OAuth provider
real external network call
real production token
```

---

# 44. Authentication Test Strategy

Authentication tests should include:

```text
valid credentials
invalid credentials
expired credentials
malformed credentials
missing credentials
unknown identity
disabled identity where applicable
current-user resolution
```

External-provider tests should use deterministic mocks/fakes where appropriate.

---

# 45. Authorization Regression Tests

After M5 implementation, M2 authorization behavior must remain unchanged.

Tests must verify:

```text
OWNER
ADMIN
DEVELOPER
VIEWER
```

still receive the established permissions.

M5 should not cause:

```text
authenticated user
    =
all permissions
```

---

# 46. Cross-Project Isolation

Authentication must not weaken Project isolation.

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

Authenticating as User A must not provide any ability to access Project B.

M5 establishes identity.

M2 authorization establishes Project access.

---

# 47. Authentication Does Not Grant Project Access

This rule is non-negotiable.

A successfully authenticated user may have:

```text
zero ProjectAccess records
```

and therefore may have no access to Project resources.

Authentication:

```text
User exists
```

does not mean:

```text
User can access every Project
```

---

# 48. New User vs Project Membership

Creating/authenticating a User must not automatically create ProjectAccess unless the authoritative product flow explicitly requires that specific operation.

Do not implement:

```text
new User
   ↓
automatically OWNER of all Projects
```

or any equivalent implicit access.

Project membership remains explicit.

---

# 49. Authentication API

M5 may expose authentication endpoints according to the authoritative API contract.

The API layer should remain thin.

Conceptually:

```text
Authentication Router
       ↓
Authentication Service
       ↓
Identity/Auth Contracts
       ↓
Infrastructure
```

The router must not implement cryptographic or credential logic directly.

---

# 50. Authentication DTOs

Authentication API contracts should use explicit DTOs.

Examples conceptually include:

```text
LoginRequest
AuthenticationResponse
CurrentUserResponse
```

Exact names and fields must follow the established API contract.

Do not expose internal authentication-library models.

---

# 51. Current User Endpoint

If the product exposes a current-user endpoint, it should return canonical application-user information appropriate for the frontend.

It must not expose:

```text
password hashes
private credentials
refresh tokens unless explicitly required
internal authentication secrets
provider client secrets
```

---

# 52. Authentication Response

Authentication responses should contain only the credentials/session information required by the approved authentication mechanism.

Do not return:

```text
database models
internal provider objects
password hashes
ProjectAccess internals
Repository internals
```

unless explicitly part of a documented contract.

---

# 53. Frontend Authentication Boundary

M6 consumes M5 authentication APIs.

M6 should be responsible for:

```text
login UI
authenticated UI state
logout interaction
authentication error presentation
route protection UX
```

M6 is not responsible for:

```text
token validation
cryptographic verification
backend authorization
ProjectAccess enforcement
```

---

# 54. Simple Frontend Requirement

The frontend must remain intentionally simple.

M5 should not force a large frontend authentication architecture.

A basic structure is sufficient:

```text
pages/
components/
api/
minimal hooks/state
```

Do not introduce:

```text
AuthDomain
AuthRepository
AuthUseCase
AuthController
AuthPresenter
```

in the frontend merely to mirror backend layering.

---

# 55. Backend Is Authoritative

Frontend authentication state is a UI concern.

Backend authentication remains authoritative.

A frontend state such as:

```text
isAuthenticated = true
```

must never be treated by the backend as proof of identity.

Every protected backend request must pass through the real authentication mechanism.

---

# 56. Logout

Logout behavior must follow the chosen authentication mechanism.

If authentication is stateless JWT-based, frontend credential removal and server-side token policy must follow the approved security design.

If server-side sessions or revocation are used, logout must invalidate the appropriate server-side state.

Do not invent hybrid behavior without a concrete requirement.

---

# 57. Token Storage

The frontend must follow the security architecture for credential storage.

Do not place sensitive credentials into:

```text
source code
URL parameters
local logs
```

The exact browser storage strategy must follow the approved authentication design.

Do not choose a storage mechanism solely for implementation convenience.

---

# 58. CORS / Browser Boundary

Authentication must work correctly across the frontend/backend deployment boundary.

Where CORS or credential configuration is required, it must be explicitly configured.

Do not use unrestricted:

```text
Access-Control-Allow-Origin: *
```

with credentialed authentication.

Exact deployment configuration belongs to the infrastructure/security architecture.

---

# 59. CSRF Considerations

If authentication uses browser-managed cookies, CSRF protections must be considered.

If authentication uses another mechanism, the relevant browser security properties must be preserved.

Do not assume that "JWT" automatically eliminates every browser security concern.

The exact mechanism must follow the selected architecture.

---

# 60. Secret Configuration

Authentication secrets/configuration must come from the approved configuration/secret boundary.

Do not hard-code:

```text
JWT secret
OAuth client secret
private key
password
token
```

into source code.

Development defaults must not become production secrets.

---

# 61. Environment Configuration

Authentication configuration should be explicit and validated.

Missing required production authentication configuration should fail safely rather than silently enabling insecure authentication.

Do not silently fall back to:

```text
StaticCurrentUserProvider
```

in production.

---

# 62. Dependency Injection

Authentication services should receive dependencies through dependency injection where appropriate.

Examples may include:

```text
UserRepository
CurrentUserProvider
Token service
Credential verifier
External identity adapter
```

The exact dependencies must follow actual use cases.

Do not instantiate infrastructure services directly inside routers.

---

# 63. Authentication Service

An authentication application service may coordinate:

```text
credential verification
principal resolution
User lookup/creation
token/session issuance
current-user resolution
```

It should not perform:

```text
Project authorization
Repository authorization
ingestion
source storage
analysis
```

---

# 64. Identity Provider Adapter

If an external provider is used, isolate it behind an application/infrastructure contract.

Conceptually:

```text
Authentication Service
        │
        ▼
Identity Provider Contract
        │
        ▼
OAuth / External Provider
```

The rest of StackSense should not depend on provider-specific SDK classes.

---

# 65. Provider Failure

External authentication-provider failures must be translated into safe application-level errors.

Do not expose provider stack traces or raw network errors to users.

Logs may retain controlled diagnostic information where appropriate.

---

# 66. Network Failure

Authentication should distinguish:

```text
invalid credentials
```

from:

```text
authentication provider unavailable
```

where the architecture requires different behavior.

Do not report every infrastructure outage as an invalid password.

---

# 67. Rate Limiting

If authentication rate limiting is part of the approved security architecture, it should be applied at the appropriate boundary.

Relevant targets may include:

```text
login attempts
token requests
password reset operations
```

Do not create an unrelated custom rate-limiting subsystem if one already exists in the infrastructure layer.

---

# 68. Brute Force Protection

If local authentication is supported, the implementation must account for repeated failed authentication attempts according to the security architecture.

Do not implement arbitrary account-locking behavior without a defined recovery path.

---

# 69. Auditability

Authentication/security events may require audit logging.

Examples:

```text
login success
login failure
logout
identity creation
identity deactivation
credential changes
```

The exact audit requirements must follow the authoritative architecture.

Do not log sensitive credential values.

---

# 70. Audit Logs vs Application Logs

Authentication audit events and ordinary debugging logs have different purposes.

Application logs should not become an accidental credential audit trail.

Never log:

```text
password
access token
refresh token
private key
authorization header
```

in plaintext.

---

# 71. User Privacy

Only the minimum necessary user identity information should be exposed to downstream modules and APIs.

Do not create a large profile system merely because a User entity exists.

---

# 72. User DTOs

User responses should expose only fields appropriate for the application.

Potentially appropriate:

```text
user ID
display identity
authentication-related public identity
```

The exact response contract must follow the authoritative product design.

Never expose:

```text
password hash
credential secrets
provider secrets
internal security metadata
```

---

# 73. Error Handling

M5 must integrate with:

```text
backend/platform/errors.py
```

and the central error handling approach.

Authentication errors should be represented through typed application errors rather than ad-hoc router responses.

---

# 74. No Raw Authentication Exceptions

Do not expose:

```text
JWTDecodeError
OAuthError
PasswordHashError
ProviderSDKException
DatabaseError
```

directly to API consumers.

Translate them into stable application/API error semantics.

---

# 75. User Conflict Handling

If User creation can encounter an identity conflict, it must be handled as an application-level conflict.

The database should provide the final concurrency guarantee for unique identity constraints.

Do not rely solely on:

```text
check if user exists
then create
```

for concurrent operations.

---

# 76. Database Constraints

Where identity uniqueness is required, enforce it in PostgreSQL.

Examples may include:

```text
canonical identity
external provider + provider subject
```

depending on the final authentication architecture.

Do not assume application-level checks are sufficient for concurrent requests.

---

# 77. Transaction Boundaries

User creation and related identity records should use the established SQLAlchemy transaction model.

Repositories flush.

The application-level transaction owns commit/rollback.

Do not introduce a separate Unit of Work merely for authentication.

---

# 78. Existing M1/M2 Regression

M5 must preserve:

```text
Project creation
Project listing
Project retrieval
Project deletion
ProjectAccess grant
ProjectAccess listing
ProjectAccess role updates
ProjectAccess revoke
ProjectAuthorization
```

The only intended change is that current-user identity becomes real rather than temporary.

---

# 79. Identity Testability

The authentication implementation must remain testable.

Tests should be able to substitute:

```text
CurrentUserProvider
```

without requiring external identity infrastructure.

This is essential for:

```text
unit tests
integration tests
authorization tests
Project isolation tests
Repository tests
M4 tests
```

---

# 80. Test Dependency Injection

Existing tests may override the current-user provider.

M5 must preserve that ability.

A test should be able to establish:

```text
User A
```

and:

```text
User B
```

deterministically and verify:

```text
Project A accessible to User A
Project B inaccessible to User A
```

without external authentication calls.

---

# 81. Authentication Integration Tests

Integration tests should verify:

```text
request
   ↓
authentication
   ↓
current user
   ↓
ProjectAuthorization
   ↓
ProjectAccess
   ↓
resource operation
```

This ensures that M5 identity actually integrates with M2 authorization.

---

# 82. M5 and M3

M3 should not need to understand authentication implementation details.

It should continue to depend on:

```text
CurrentUserProvider
ProjectAuthorization
```

Therefore:

```text
M5
   ↓
CurrentUserProvider
   ↓
M3
```

is the intended integration.

M3 must not import:

```text
JWT implementation
OAuth provider SDK
password hashing implementation
```

---

# 83. M5 and M4

M4 similarly consumes authenticated identity through the existing seam.

M5 must not implement repository acquisition authorization itself.

The flow remains:

```text
M5
  ↓
CurrentUserProvider
  ↓
M4
  ↓
ProjectAuthorization
  ↓
ProjectAccess
```

---

# 84. M5 and M6

M6 consumes M5 authentication APIs and current-user information.

M6 must not recreate authentication semantics in the frontend.

The frontend can maintain minimal authentication state for UX.

The backend remains authoritative.

---

# 85. M5 and M7

M7 must verify that:

```text
real authentication
      ↓
CurrentUserProvider
      ↓
ProjectAuthorization
      ↓
ProjectAccess
      ↓
Project/Repository access
```

works end-to-end.

---

# 86. Parallel Development Rule

M5 may be implemented in parallel with M3, M4, and M6.

Therefore M5 must consume stable contracts rather than waiting for every downstream implementation.

The critical stable contract is:

```text
CurrentUserProvider
```

M5 should replace its implementation behind that boundary.

---

# 87. Contract Gap Rule

If M5 discovers that the existing identity seam is insufficient:

```text
STOP
   ↓
identify missing contract
   ↓
check master.txt
   ↓
determine whether the gap is architectural
   ↓
propose the smallest required change
   ↓
update contract/ADR if approved
   ↓
implement
```

Do not silently replace:

```text
CurrentUserProvider
```

with an incompatible architecture.

---

# 88. No Authentication Rewrite of M2

M5 must not rewrite:

```text
ProjectAccess
ProjectRole
ProjectAuthorization
```

just because authentication now exists.

The correct relationship is:

```text
M5 = identity
M2 = resource authorization
```

---

# 89. No Implicit Membership

Authentication must not automatically grant Project access.

A newly authenticated User may have:

```text
no Projects
```

until ProjectAccess is established.

---

# 90. No Implicit Ownership

M5 must not make a User the owner of a Project simply because:

```text
the User created the account
```

or:

```text
the User authenticated
```

Project ownership remains an explicit ProjectAccess role.

---

# 91. No Identity Leakage

M5 must not expose internal authentication details to downstream resource modules.

M3/M4 need:

```text
User identity
```

not:

```text
JWT claims object
OAuth token
provider SDK object
password credentials
```

---

# 92. Security Boundary

The complete protected-resource flow is:

```text
HTTP Request
     │
     ▼
Authentication
     │
     ├── failure → authentication error
     │
     ▼
Current User
     │
     ▼
ProjectAuthorization
     │
     ├── denied → authorization error
     │
     ▼
Resource
```

This separation must remain intact.

---

# 93. M5 Database Design

M5 may require identity-related persistence such as:

```text
users
external identities where required
authentication/session state where required
```

The exact schema must follow `master.txt`.

Do not add tables for speculative authentication features.

---

# 94. User Identifier

The application User identifier must be stable and suitable for references from:

```text
ProjectAccess
future audit records
future resource relationships
```

The exact type should remain consistent with the existing UUID-based ProjectAccess contract.

---

# 95. User Foreign-Key Integration

If M5 adds a database foreign key from:

```text
project_access.user_id
```

to:

```text
users.id
```

it must preserve existing data and migration order.

A safe migration must account for any existing ProjectAccess rows before enforcing a new constraint.

Do not assume the database is empty.

---

# 96. Fresh Database Verification

M5 schema changes must work on a fresh database:

```text
alembic upgrade head
```

and on an existing database containing M1/M2 data.

Both scenarios must be tested.

---

# 97. Existing Data Compatibility

M5 must not invalidate existing ProjectAccess records.

If existing `user_id` values need canonical User records, the migration/data strategy must explicitly account for them.

Do not silently delete or reinterpret existing ProjectAccess data.

---

# 98. Identity Migration Strategy

If existing test/development users are synthetic because M2 used:

```text
StaticCurrentUserProvider
```

the transition to real User persistence must be deliberate.

Do not assume test UUIDs correspond to real production users.

Tests may continue using deterministic synthetic identities through the test provider.

---

# 99. Authentication Configuration

Authentication configuration must be centralized in the existing configuration system.

Potential configuration categories include:

```text
authentication mode
token settings
issuer
audience
provider configuration
credential hashing configuration
expiration settings
```

Only configuration required by the selected architecture should be introduced.

---

# 100. Production vs Test Configuration

Production authentication and test identity must remain clearly separated.

Production:

```text
real authentication
```

Tests:

```text
deterministic identity provider
```

Do not make test convenience silently weaken production authentication.

---

# 101. No Hard-Coded Test User

Production code must not contain:

```text
DEFAULT_USER_ID
TEST_USER_ID
STATIC_USER_ID
```

as an authentication fallback.

Synthetic identity belongs in test configuration/provider overrides.

---

# 102. API Authentication Middleware/Dependency

Authentication should be enforced through the appropriate FastAPI dependency/middleware boundary.

Protected endpoints should obtain the authenticated identity through the established application dependency.

Do not make every router manually parse:

```text
Authorization
```

headers.

---

# 103. Public vs Protected Endpoints

M5 must explicitly distinguish authentication-required endpoints from public endpoints.

Do not accidentally expose:

```text
Project APIs
Repository APIs
Ingestion APIs
User-sensitive APIs
```

without authentication.

The exact public endpoint set must follow the API contract.

---

# 104. Authentication Dependency Reuse

Protected APIs should reuse the centralized authentication dependency.

Do not create:

```text
get_user_from_jwt
get_user_from_token
get_authenticated_user
resolve_user
```

as multiple competing implementations unless they have genuinely distinct contracts.

---

# 105. Current User Error

When a protected request has no valid authenticated identity, the current-user dependency must fail through the established authentication error contract.

It must not return:

```text
None
```

and allow downstream services to continue as if a user existed.

---

# 106. Identity Resolution Failure

If credentials are valid but the canonical User cannot be resolved, the system must have explicit behavior.

Do not silently create a new User on every request unless automatic provisioning is an explicit part of the authentication contract.

---

# 107. Account Provisioning

If external authentication uses just-in-time user provisioning, the provisioning behavior must be explicit.

Conceptually:

```text
External Principal
      │
      ├── existing User → resolve
      │
      └── new principal → create User if approved
```

Do not make account provisioning an accidental side effect.

---

# 108. External Identity Linking

If users can authenticate through multiple providers, identity linking must be explicit.

Do not automatically merge accounts based solely on unverified matching attributes.

The exact account-linking policy must follow the security architecture.

---

# 109. Token Revocation

If the chosen authentication mechanism supports revocation/session state, the revocation model must be explicit.

Do not claim that logout invalidates a stateless credential server-side if it does not.

The frontend must not represent logout semantics inaccurately.

---

# 110. Authentication Observability

M5 should provide structured security observability where required.

Useful events may include:

```text
authentication success
authentication failure
token validation failure
identity provisioning
identity deactivation
logout
```

Do not log secret credential values.

---

# 111. Security Monitoring

Repeated authentication failures may be relevant to monitoring and rate limiting.

Use existing observability infrastructure.

Do not create a separate security-monitoring stack solely for M5.

---

# 112. Performance

Authentication should not introduce unnecessary database queries for every operation beyond what the selected identity mechanism requires.

Where appropriate, the architecture may allow safe identity caching, but caching must not create stale authorization decisions.

ProjectAuthorization remains responsible for current ProjectAccess evaluation.

---

# 113. Authorization Freshness

Do not cache Project roles inside authentication tokens as the authoritative resource authorization state unless explicitly designed.

Project membership can change independently of authentication.

Therefore:

```text
authenticated identity
```

and:

```text
current ProjectAccess
```

are separate concerns.

---

# 114. Role Changes

If a user's Project role changes:

```text
OWNER → ADMIN
ADMIN → DEVELOPER
DEVELOPER → VIEWER
```

the next authorization decision must respect the current ProjectAccess state.

M5 must not accidentally freeze Project roles inside long-lived authentication state.

---

# 115. User Deactivation and ProjectAccess

If a User is deactivated:

```text
authentication
    ↓
must no longer establish an active identity
```

ProjectAccess records may remain for data integrity/history unless the architecture explicitly says otherwise.

Do not use ProjectAccess deletion as a substitute for identity deactivation.

---

# 116. Error Enumeration

Authentication APIs must avoid leaking sensitive account existence information where the authentication model requires generic failures.

Similarly, protected Project/Repository resources must continue to follow the established non-enumerating authorization behavior.

---

# 117. Testing Matrix

M5 tests should cover:

| Scenario | Expected |
|---|---|
| Valid authentication | Authenticated User |
| Missing credentials | Authentication failure |
| Invalid credentials | Authentication failure |
| Expired credentials | Authentication failure |
| Unknown identity | Defined identity failure |
| Disabled User | Authentication denied |
| Authenticated User without ProjectAccess | Authorization denied |
| VIEWER | Read-only resource access |
| DEVELOPER | No delete |
| ADMIN | Full Project resource permissions |
| OWNER | Full Project resource permissions |

The role behavior comes from M2 and must not be redefined by M5.

---

# 118. Integration Test Matrix

At minimum verify:

```text
authenticate User A
    ↓
resolve User A
    ↓
ProjectAuthorization
    ↓
Project A
    ↓
allowed

authenticate User A
    ↓
ProjectAuthorization
    ↓
Project B
    ↓
denied
```

Repeat through Repository/M4 operations where appropriate.

---

# 119. Architecture Tests

M5 architecture tests should prevent:

```text
JWT code inside domain
OAuth SDK inside domain
password logic inside routers
ProjectAccess duplication
ProjectRole duplication
Repository RBAC
Organization identity hierarchy
authentication logic inside M3/M4
relative imports
direct SQLAlchemy access from routers
raw credential logging
hard-coded production user
```

---

# 120. API Tests

Authentication API tests should verify:

```text
request validation
authentication success
authentication failure
current-user response
credential/token behavior
error contract
protected endpoint access
```

Do not test only the happy login path.

---

# 121. Database Tests

M5 database tests should verify:

```text
User persistence
identity uniqueness
ProjectAccess relationship
foreign-key behavior if introduced
migration correctness
concurrent identity creation
```

---

# 122. Concurrency

Identity creation may encounter concurrent requests for the same canonical identity.

The database must enforce uniqueness where required.

The application should translate duplicate identity creation into a stable application-level result.

Do not rely solely on:

```text
SELECT
then INSERT
```

for uniqueness.

---

# 123. No Raw Database Exceptions

Database errors such as:

```text
IntegrityError
OperationalError
```

must not leak through authentication APIs.

Translate them at the appropriate boundary.

---

# 124. Production Engineering Standards

M5 must preserve:

```text
SOLID
high cohesion
low coupling
dependency inversion
dependency injection
explicit contracts
testability
typed errors
secure secret handling
transaction integrity
database constraints
observability
```

Do not introduce abstractions without a concrete responsibility.

---

# 125. No Mechanical Authentication Layers

Avoid unnecessary structures such as:

```text
AuthenticationManager
AuthenticationCoordinator
AuthenticationFacade
AuthenticationHelper
TokenManagerManager
UserManager
GenericIdentityService
```

unless each abstraction has a distinct responsibility.

The goal is clear boundaries, not maximum file count.

---

# 126. Backend Structure

M5 should fit the existing StackSense backend structure.

Conceptually:

```text
backend/
└── platform/
    └── identity/
        ├── domain/
        ├── application/
        ├── repositories/
        └── infra/
```

The exact package placement must follow the existing repository structure.

Do not mechanically create directories that contain only one trivial file.

---

# 127. Existing Current User Location

The existing identity seam is under:

```text
backend/platform/identity/application/current_user.py
```

M5 should extend the established identity module rather than creating a competing:

```text
backend/auth/
backend/security/
backend/users/
```

architecture without a concrete architectural reason.

---

# 128. Import Convention

Absolute imports are mandatory.

Preferred:

```python
from backend.platform.identity.application.current_user import (
    CurrentUserProvider,
)
```

Avoid:

```python
from .current_user import CurrentUserProvider
```

or:

```python
from ..application.current_user import CurrentUserProvider
```

---

# 129. DTO Convention

Use explicit Pydantic DTOs.

Preferred examples:

```text
LoginRequest
AuthenticationResponse
CurrentUserResponse
```

Avoid generic:

```text
UserDTO
AuthDTO
ResponseDTO
```

unless an actual contract requires those names.

---

# 130. Service Naming

Follow the existing application service convention.

Where an application service is warranted:

```text
AuthenticationService
DefaultAuthenticationService
```

or another explicit domain-specific name.

Do not create a service merely because every module is expected to have one.

---

# 131. Repository Naming

Where a User repository is required:

```text
UserRepository
```

for the application contract and an appropriately named infrastructure implementation.

Do not create multiple repositories for:

```text
authentication
identity
current-user
user
```

unless they represent genuinely different persistence boundaries.

---

# 132. Domain Model Independence

Identity domain models must not depend on:

```text
FastAPI
Pydantic request objects
JWT libraries
OAuth SDKs
SQLAlchemy
HTTP headers
```

Infrastructure and API layers adapt those technologies to the domain/application contracts.

---

# 133. Authentication Adapter Pattern

An adapter is appropriate where an external provider must be isolated.

Conceptually:

```text
Application
    │
    ▼
IdentityProvider Contract
    ▲
    │
Infrastructure Adapter
    │
    ▼
External Provider
```

This is preferred over embedding provider SDK calls inside application services.

---

# 134. Strategy Pattern

A Strategy-style abstraction may be justified if StackSense genuinely supports multiple authentication mechanisms.

For example:

```text
LocalAuthenticationStrategy
OAuthAuthenticationStrategy
```

But do not create a strategy hierarchy merely because multiple providers may exist in the future.

Implement the smallest architecture required by the current contract.

---

# 135. Authentication Provider vs Authorization Provider

Do not use the word "provider" ambiguously.

Conceptually:

```text
CurrentUserProvider
    → provides current application User

Identity/Auth Provider
    → authenticates external credentials/principal
```

They may have related implementations, but their contracts are distinct.

---

# 136. M5 → M6 Contract

M6 needs enough information to establish:

```text
authenticated session/state
current user
login/logout behavior
authentication failures
```

M6 does not need:

```text
JWT internals
OAuth SDK objects
password hashes
database models
```

---

# 137. M5 → M3 Contract

M3 needs:

```text
CurrentUserProvider
ProjectAuthorization
```

M5 provides the authenticated identity behind the first.

M5 must not require M3 to know how authentication works.

---

# 138. M5 → M4 Contract

M4 similarly consumes authenticated identity and ProjectAuthorization.

M4 must not depend directly on:

```text
authentication tokens
```

or:

```text
provider-specific identity objects
```

---

# 139. M5 → M7 Contract

M7 must be able to verify the complete authentication-to-resource path.

M5 should therefore provide:

```text
authentication tests
identity integration tests
test identity override
API contract tests
security behavior
migration verification
```

---

# 140. M5 Definition of Done

M5 is complete only when:

```text
Canonical User identity exists
Real authentication mechanism is implemented
CurrentUserProvider remains the stable application seam
StaticCurrentUserProvider is no longer the production identity mechanism
Authentication API exists where required
User persistence exists
Identity uniqueness is enforced
Authentication failures are typed
Secrets are protected
Authentication does not bypass ProjectAuthorization
ProjectAccess remains unchanged
ProjectRole remains unchanged
No Repository RBAC exists
No Organization hierarchy is introduced
M1/M2 migrations remain untouched
M5 migrations work on fresh and existing databases
Protected endpoints require authentication
Current-user resolution works
Existing M2 tests still pass
M3/M4 integration works
M6 can consume authentication contracts
Security tests pass
Architecture tests pass
Absolute imports are preserved
Formatting/lint/type checks pass
End-to-end authenticated Project flow works
```

---

# 141. M5 Implementation Order

Recommended implementation sequence:

```text
1. Read master.txt identity/authentication sections
2. Read M1-M2-CONTEXT.md
3. Inspect CurrentUserProvider implementation
4. Inspect existing ProjectAuthorization
5. Inspect existing ProjectAccess persistence
6. Inspect existing API dependency registration
7. Define canonical User domain model
8. Define User persistence model
9. Define User repository contract
10. Define authentication contract
11. Define credential/token/provider abstraction required by architecture
12. Implement authentication infrastructure
13. Implement User identity resolution
14. Replace StaticCurrentUserProvider in production dependency wiring
15. Preserve StaticCurrentUserProvider for tests
16. Add required migrations
17. Add authentication API
18. Add current-user API where required
19. Integrate protected API dependencies
20. Add authentication tests
21. Add identity/authorization integration tests
22. Run M1/M2 regression suite
23. Run M3/M4 integration tests
24. Run architecture/security checks
25. Verify fresh database migration
26. Verify end-to-end authentication flow
27. Produce implementation report
```

---

# 142. Security Checklist

Before declaring M5 complete:

```text
[ ] Passwords are never stored in plaintext
[ ] Credentials are never logged
[ ] Tokens are never logged
[ ] Secrets are not hard-coded
[ ] Authentication failures are safe
[ ] Authorization failures remain distinct
[ ] CurrentUserProvider is used
[ ] Static identity is not used in production
[ ] Protected endpoints require authentication
[ ] Project authorization remains authoritative
[ ] ProjectAccess is preserved
[ ] Repository authorization remains Project-derived
[ ] Organization is not reintroduced
[ ] User identity is stable
[ ] Identity uniqueness is database-enforced
[ ] Authentication provider failures are safely handled
[ ] External provider credentials are protected
[ ] Test authentication does not weaken production authentication
```

---

# 143. Architecture Checklist

```text
[ ] master.txt followed
[ ] M1/M2 contracts preserved
[ ] CurrentUserProvider preserved
[ ] ProjectAuthorization preserved
[ ] ProjectAccess preserved
[ ] ProjectRole preserved
[ ] no Project.owner_id
[ ] no Organization
[ ] no Repository RBAC
[ ] no duplicate authorization framework
[ ] no authentication logic in domain models
[ ] no provider SDK leakage into domain/application contracts
[ ] no raw persistence models in API
[ ] no relative imports
[ ] no rewritten historical migrations
[ ] dependency injection preserved
[ ] routers remain thin
[ ] application services remain focused
```

---

# 144. Testing Checklist

```text
[ ] User persistence tests
[ ] identity uniqueness tests
[ ] authentication success tests
[ ] authentication failure tests
[ ] expired credential tests
[ ] malformed credential tests
[ ] current-user resolution tests
[ ] test identity override tests
[ ] ProjectAuthorization regression tests
[ ] ProjectAccess role tests
[ ] cross-Project isolation tests
[ ] protected endpoint tests
[ ] API contract tests
[ ] migration tests
[ ] concurrency tests
[ ] security tests
[ ] architecture tests
[ ] full regression suite
```

---

# 145. Independent Review

The independent reviewer must audit M5 independently of the Builder's report.

Review:

```text
Authentication architecture
User identity model
CurrentUserProvider
ProjectAuthorization integration
ProjectAccess preservation
Credential security
Token/session behavior
External provider isolation
Secret handling
Database schema
Migrations
Error handling
API contracts
Dependency injection
Testability
Frontend integration contract
Regression
Security
Architecture boundaries
```

The reviewer must not silently modify the implementation.

---

# 146. Reviewer Severity

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

Do not report personal preference as a defect.

---

# 147. M5 Forbidden Outcomes

M5 implementation is invalid if it introduces:

```text
Organization identity hierarchy
Project.owner_id
Repository-level RBAC
duplicate ProjectAuthorization
duplicate ProjectAccess
authentication logic inside M3
authentication logic inside M4
JWT/OAuth logic inside domain models
provider SDK leakage
raw credential logging
plaintext passwords
hard-coded production users
StaticCurrentUserProvider in production
authentication bypass for protected APIs
implicit Project membership
implicit Project ownership
rewritten M1/M2 migrations
relative imports
raw authentication exceptions exposed through API
frontend-authoritative authentication
mechanical authentication abstractions
unnecessary frontend architecture
```

---

# 148. Final M5 Contract

M5 can be summarized as:

```text
M5 = Identity & Authentication

Consumes:
    Existing CurrentUserProvider contract
    ProjectAccess
    ProjectAuthorization
    M1/M2 persistence conventions
    Existing API/error conventions

Owns:
    User identity
    User persistence
    Authentication
    Credential/token/session handling
    Current-user resolution
    Authentication API
    Identity security
    Identity tests

Provides:
    Canonical User identity
    Real CurrentUserProvider implementation
    Authentication application contract
    Authentication API contract
    Testable identity boundary

Does not own:
    Project authorization
    ProjectAccess
    ProjectRole
    Repository authorization
    Repository ingestion
    Source storage
    Source analysis
    IR
    Architecture Model
    Knowledge Graph
    RAG
    AI
    Frontend business authorization
```

---

# 149. Final Identity Flow

```text
                         ┌──────────────────────┐
                         │      HTTP Request     │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Authentication     │
                         │      M5              │
                         └──────────┬───────────┘
                                    │
                              authenticated
                               application
                                  identity
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ CurrentUserProvider  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                              Canonical User
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ ProjectAuthorization │
                         │        M2            │
                         └──────────┬───────────┘
                                    │
                                    ▼
                            ProjectAccess
                                    │
                                    ▼
                             ProjectRole
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Protected Resource  │
                         │      M3 / M4         │
                         └──────────────────────┘
```

---

# 150. Non-Negotiable Rules

```text
1. master.txt remains the ultimate source of truth.

2. M1 and M2 are frozen.

3. M5 owns identity and authentication.

4. M2 owns Project authorization.

5. Authentication and authorization remain separate.

6. CurrentUserProvider is the stable identity seam.

7. StaticCurrentUserProvider must not be the production identity mechanism.

8. ProjectAccess remains the Project membership/access model.

9. ProjectRole remains OWNER, ADMIN, DEVELOPER, VIEWER.

10. ProjectAuthorization remains the resource authorization mechanism.

11. Authentication does not grant ProjectAccess.

12. Authentication does not grant Project ownership.

13. Project.owner_id must not be introduced.

14. Organization must not be reintroduced.

15. Repository-level RBAC must not be introduced.

16. User identity must remain distinct from ProjectAccess.

17. User persistence belongs to M5.

18. M5 must not redesign M2 authorization.

19. M5 must not expose authentication implementation details to M3/M4.

20. Credentials and secrets must never be logged.

21. Passwords must never be stored in plaintext.

22. Raw authentication/provider exceptions must not reach API clients.

23. Authentication configuration must not be hard-coded.

24. Production authentication must not fall back to a static user.

25. Tests must retain a deterministic identity seam.

26. Existing M1/M2 migrations must not be rewritten.

27. New identity schema changes require new migrations.

28. Database constraints remain authoritative for identity uniqueness.

29. Absolute imports are mandatory.

30. Dependency injection must be preserved.

31. Routers remain thin.

32. API DTOs remain explicit.

33. Domain/application code must not depend directly on provider SDKs.

34. Frontend authentication is UX; backend authentication is authoritative.

35. Project role changes must remain independent of authentication credentials.

36. Parallel developers consume established contracts rather than creating competing abstractions.

37. Any identity contract gap must be surfaced explicitly.

38. No silent architecture changes are permitted.
```