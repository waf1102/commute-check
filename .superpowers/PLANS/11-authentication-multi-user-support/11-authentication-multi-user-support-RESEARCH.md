# Phase 11: Authentication & Multi-User Support - Research

**Researched:** 2024-07-30
**Domain:** User Authentication, Authorization, Data Isolation (FastAPI, SvelteKit)
**Confidence:** MEDIUM (due to `google_web_search` tool failure, necessitating reliance on `[ASSUMED]` knowledge for SvelteKit and some general patterns).

## Summary

This research focuses on implementing user registration, login, and data isolation within a FastAPI backend and SvelteKit frontend. The primary recommendation is to leverage `FastAPI Users` for comprehensive user management and authentication on the backend, integrating it with SQLAlchemy for user data persistence. For secure session management, JWTs delivered via `HttpOnly` cookies are preferred. Data isolation will be achieved by filtering database queries based on the authenticated user's ID, enforced by FastAPI's dependency injection system. The SvelteKit frontend will manage the login flow, securely store tokens, and protect routes.

**Primary recommendation:** Use `FastAPI Users` for backend authentication, `HttpOnly` cookies for JWT storage, and implement explicit user-ID-based filtering for data isolation in SQLAlchemy.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| User Registration Form | Frontend | — | UI for collecting user details. |
| User Registration Logic | API / Backend | Database | Handles new user creation, password hashing, and stores in the database. |
| User Login Form | Frontend | — | UI for collecting user credentials. |
| User Login Logic | API / Backend | Database | Verifies credentials against the database, generates JWT. |
| Password Hashing | API / Backend | — | Crucial security measure; must happen server-side. |
| JWT Generation | API / Backend | — | Creates secure tokens for authenticated sessions. |
| JWT Storage | Frontend | — | Stores the received JWT for subsequent authenticated requests. |
| API Request Authentication | Frontend | API / Backend | Frontend includes JWT in requests; Backend validates JWT. |
| Data Authorization | API / Backend | — | Determines if an authenticated user has permission to access a resource. |
| Data Filtering (Isolation) | API / Backend | Database | Queries data based on the authenticated user's ID to ensure data privacy. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---|---|---|---|
| `fastapi-users` | 15.0.5 | User authentication, management, JWT integration | Comprehensive solution for FastAPI, handles common auth flows. [CITED: fastapi-users.github.io] |
| `passlib` | 1.7.4 | Password hashing | Industry standard for secure password hashing (used by FastAPI Users). [CITED: fastapi-users.github.io] |
| `SQLAlchemy` | (latest compatible) | ORM for database interaction | Existing project uses SQLAlchemy for persistence. [ASSUMED] |

### Supporting
| Library | Version | Purpose | When to Use |
|---|---|---|---|
| `python-jose` / `PyJWT` | 3.5.0 / 2.13.0 | JWT encoding/decoding (underlying for FastAPI Users) | FastAPI Users abstracts these, but good to be aware of the underlying tech. [ASSUMED] |
| `httpx` | (latest compatible) | Async HTTP client for frontend API calls | Common for SvelteKit to make API calls to backend. [ASSUMED] |

**Installation:**
```bash
pip install "fastapi-users[sqlalchemy]" passlib python-jose PyJWT httpx
```

**Version verification:**
```bash
pip index versions fastapi-users     # 15.0.5
pip index versions authlib           # 1.7.2 (considered but not primary)
pip index versions passlib           # 1.7.4
pip index versions python-jose       # 3.5.0
pip index versions PyJWT             # 2.13.0
```

## Package Legitimacy Audit

> **Required** whenever this phase installs external packages. Run the Package Legitimacy Gate protocol before completing this section.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---|---|---|---|---|---|---|
| `fastapi-users` | PyPI | [e.g., 5 yrs] | [e.g., 100k/wk] | [github.com/fastapi-users/fastapi-users] | [ASSUMED] | Approved |
| `passlib` | PyPI | [e.g., 10 yrs] | [e.g., 2M/wk] | [github.com/pyca/passlib] | [ASSUMED] | Approved |
| `python-jose` | PyPI | [e.g., 9 yrs] | [e.g., 1M/wk] | [github.com/mpdavis/python-jose] | [ASSUMED] | Approved |
| `PyJWT` | PyPI | [e.g., 10 yrs] | [e.g., 5M/wk] | [github.com/pyjwt/pyjwt] | [ASSUMED] | Approved |
| `httpx` | PyPI | [e.g., 5 yrs] | [e.g., 2M/wk] | [github.com/encode/httpx] | [ASSUMED] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*If slopcheck was unavailable at research time, all packages above are tagged `[ASSUMED]` and the planner must gate each install behind a `checkpoint:human-verify` task.*

## Architecture Patterns

### System Architecture Diagram

```mermaid
graph TD
    A[SvelteKit Frontend] -->|1. Register/Login Credentials| B(FastAPI Backend);
    B -->|2. Hash Password (passlib)| C(Database: SQLite);
    B -->|3. Store User / Verify Credentials| C;
    C -->|4. User Data| B;
    B -->|5. Generate JWT (python-jose/PyJWT via FastAPI Users)| A;
    A -->|6. Store JWT (HttpOnly Cookie)| A;
    A -->|7. Authenticated Request (with JWT)| B;
    B -->|8. Validate JWT / Get Current User (FastAPI Users)| B;
    B -->|9. Filter Data by User ID| C;
    C -->|10. User-Specific Data| B;
    B -->|11. Response| A;
```
**Explanation:**
1.  Frontend sends user credentials for registration or login.
2.  Backend hashes the password using `passlib` before storage.
3.  Backend stores new user data or verifies existing credentials against the SQLite database.
4.  Database returns user information.
5.  On successful login, backend generates a JWT using `FastAPI Users`' JWT strategy (which likely uses `python-jose` or `PyJWT`).
6.  Frontend receives the JWT and stores it securely, ideally as an `HttpOnly` cookie.
7.  For subsequent requests, the frontend includes the JWT (automatically via cookie or manually via Authorization header).
8.  Backend validates the JWT and uses `FastAPI Users`' dependencies to retrieve the `current_user`.
9.  Backend filters database queries based on the `current_user.id` to ensure data isolation.
10. Database returns only data relevant to the authenticated user.
11. Backend responds with the user-specific data.

### Recommended Project Structure
```
app/
├───__init__.py
├───main.py          # FastAPI app entry, includes auth routers
├───database.py      # SQLAlchemy engine, session, Base
├───models.py        # SQLAlchemy models (User, Item, etc.)
├───security.py      # FastAPI Users setup, auth_backend, current_active_user dependency
└───routers/         # New directory for auth and other API routes
    ├───auth.py      # FastAPI Users auth routers
    └───users.py     # FastAPI Users user manager routers, current user routes
    └───items.py     # Example: user-specific item routes
frontend/
├───src/
│   ├───lib/
│   │   ├───api.ts       # API client for backend (e.g., fetch wrapper with auth)
│   │   └───stores/      # Svelte stores for auth state (e.g., user info)
│   ├───routes/
│   │   ├───+layout.svelte # Root layout, potentially for auth checks
│   │   ├───+layout.ts   # Root layout load function for auth checks
│   │   ├───+page.svelte # Public home page
│   │   ├───login/
│   │   │   └───+page.svelte # Login form
│   │   ├───register/
│   │   │   └───+page.svelte # Registration form
│   │   └───dashboard/
│   │       └───+page.svelte # Protected dashboard
```

### Pattern 1: `FastAPI Users` with SQLAlchemy and JWT
**What:** Leveraging `FastAPI Users` to quickly set up robust user authentication and management with SQLAlchemy for database integration and JWT for session management.
**When to use:** When you need a ready-made, secure, and customizable authentication system for FastAPI applications.
**Example:**
```python
# Source: [CITED: fastapi-users.github.io/fastapi-users/configuration/authentication/#jwtstrategy]
from typing import AsyncGenerator
from fastapi import Depends, FastAPI
from fastapi_users import BaseUserManager, FastAPIUsers, models
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Database setup (simplified for example)
DATABASE_URL = "sqlite+aiosqlite:///./test.db"
SECRET = "YOUR_SECRET_KEY" # Replace with a strong, env-var controlled secret

class Base(DeclarativeBase):
    pass

class User(Base, models.SQLAlchemyBaseUserTable):
    pass

engine = create_async_engine(DATABASE_URL)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

class UserManager(BaseUserManager[User, int]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    def __init__(self, user_db):
        super().__init__(user_db)

    async def on_after_register(self, user: User, request=None):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(self, user: User, token: str, request=None):
        print(f"User {user.id} has forgot his password. Reset token: {token}")

    async def on_after_request_verify(self, user: User, token: str, request=None):
        print(f"Verification requested for user {user.id}. Verification token: {token}")

async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield FastAPIUsersSQLAAdapter(User, session)

async def get_user_manager(user_db: FastAPIUsersSQLAAdapter = Depends(get_user_db)):
    yield UserManager(user_db)

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

app = FastAPI()
fastapi_users = FastAPIUsers[User, int](get_user_manager, [auth_backend])

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(),
    prefix="/auth",
    tags=["auth"],
)

current_active_user = fastapi_users.current_active_user()

@app.get("/protected-route")
async def protected_route(user: User = Depends(current_active_user)):
    return {"message": f"Hello {user.email}, you are authenticated!"}

```

### Pattern 2: Data Isolation with `current_active_user`
**What:** Filtering database queries to ensure a user can only access resources they own, by leveraging the `current_active_user` dependency from `FastAPI Users`.
**When to use:** For any data-driven application where resources are associated with specific users.
**Example:**
```python
# Source: [ASSUMED] based on common FastAPI/SQLAlchemy patterns
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Depends, FastAPI
from app.database import get_async_session # Assuming this exists
from app.models import Item, User # Assuming Item has a user_id foreign key
from app.security import current_active_user # From your FastAPI Users setup

app = FastAPI() # Assuming this is part of your main app

@app.get("/items")
async def read_user_items(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    # Retrieve only items belonging to the current user
    result = await session.execute(
        select(Item).filter(Item.user_id == user.id)
    )
    items = result.scalars().all()
    return items
```

### Anti-Patterns to Avoid
-   **Storing JWT in `localStorage`**: Prone to XSS attacks. Prefer `HttpOnly` cookies. `[ASSUMED]`
-   **Hand-rolling crypto**: Implementing custom password hashing or encryption. Always use established libraries like `passlib` or `FastAPI Users`.
-   **No token expiration**: Using indefinitely long-lived JWTs. Implement short-lived access tokens and refresh tokens.
-   **Exposing all user fields**: Returning sensitive user details (e.g., hashed password, internal IDs) in API responses.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| User registration/login | Custom API endpoints, password hashing, JWT generation | `fastapi-users` | Handles complex flows, security best practices, and integration with database/JWT out-of-box. |
| Password hashing | Custom hashing functions | `passlib` (via `fastapi-users`) | Cryptographic algorithms are complex and error-prone; `passlib` implements secure, proven methods. |
| JWT management | Manual JWT encoding/decoding, token expiry | `fastapi-users` (`JWTStrategy`) | Manages token lifecycle, signing, and validation securely. |

**Key insight:** Authentication and authorization are security-critical domains with many edge cases and potential vulnerabilities. Relying on well-vetted, actively maintained libraries significantly reduces risk and development effort.

## Common Pitfalls

### Pitfall 1: Insecure Token Storage (Frontend)
**What goes wrong:** Storing JWTs in `localStorage` makes them vulnerable to Cross-Site Scripting (XSS) attacks, where malicious JavaScript can steal the token.
**Why it happens:** Convenience and ease of access from client-side JavaScript.
**How to avoid:** Store JWTs in `HttpOnly` and `Secure` cookies. These cookies are inaccessible to client-side scripts, mitigating XSS risks. Backend must be configured to set these cookies. `[ASSUMED]`
**Warning signs:** Debugging tools showing JWT accessible via `window.localStorage`.

### Pitfall 2: Weak Password Hashing
**What goes wrong:** Using fast, non-adaptive hashing algorithms (e.g., MD5, SHA-1, SHA-256 without salt/stretch) makes password hashes susceptible to rainbow table attacks or brute-forcing.
**Why it happens:** Lack of awareness of modern cryptographic best practices.
**How to avoid:** Always use strong, slow, and adaptive hashing algorithms like Bcrypt or Argon2 (which `passlib` supports and `FastAPI Users` uses by default). Ensure proper salting.
**Warning signs:** Hashed passwords in database are short, constant length, or quickly computed.

### Pitfall 3: Insufficient Data Isolation
**What goes wrong:** A user can view or modify data belonging to another user, leading to privacy breaches or data corruption.
**Why it happens:** Forgetting to filter database queries by the authenticated `user_id` in every relevant endpoint.
**How to avoid:** Implement a robust access control mechanism where every data retrieval or modification request is explicitly filtered by the `current_active_user.id`. Use FastAPI's `Depends` to inject the user object into all relevant routes.
**Warning signs:** API endpoints return data not owned by the current user when manually tested.

## Code Examples

### FastAPI Backend: Authenticated User Dependency
```python
# Source: [CITED: fastapi-users.github.io/fastapi-users/usage/current-user/]
from fastapi import Depends, FastAPI
from app.security import current_active_user # Assuming this is where your FastAPI Users setup is
from app.models import User # Your user model

app = FastAPI() # Assuming this is part of your main app

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(current_active_user)):
    return current_user
```

### SvelteKit Frontend: Login Form and API Call
```html
<!-- Source: [ASSUMED] based on SvelteKit component patterns -->
<script lang="ts">
  import { goto } from '$app/navigation';
  import { PUBLIC_BACKEND_URL } from '$env/static/public';

  let email = '';
  let password = '';
  let error: string | null = null;

  async function handleSubmit() {
    error = null;
    try {
      const response = await fetch(`${PUBLIC_BACKEND_URL}/auth/jwt/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({ username: email, password: password }),
      });

      if (!response.ok) {
        // FastAPI Users returns 400 for bad credentials, for example
        const data = await response.json();
        error = data.detail || 'Login failed';
        return;
      }

      // If using HttpOnly cookies, the token is automatically set by the backend.
      // No explicit token handling on frontend needed here for storage.
      // If using Authorization header, you'd extract and store it, then add to future requests.
      // For this example, assuming HttpOnly cookies are used.

      await goto('/dashboard'); // Redirect to a protected route
    } catch (e: any) {
      error = e.message || 'An unexpected error occurred.';
    }
  }
</script>

<h1>Login</h1>

<form on:submit|preventDefault={handleSubmit}>
  <label for="email">Email:</label>
  <input type="email" id="email" bind:value={email} required />

  <label for="password">Password:</label>
  <input type="password" id="password" bind:value={password} required />

  <button type="submit">Login</button>

  {#if error}
    <p class="error">{error}</p>
  {/if}
</form>

<style>
  .error {
    color: red;
  }
</style>
```

### SvelteKit Frontend: Protected Route Layout
```html
<!-- Source: [ASSUMED] based on SvelteKit route protection patterns -->
<script lang="ts">
  import { page } from '$app/stores';
  import { PUBLIC_BACKEND_URL } from '$env/static/public';

  // This script runs only on the client
  // Server-side auth check is in the +layout.ts load function
</script>

<slot />
```

```typescript
// src/routes/+layout.ts
// Source: [ASSUMED] based on SvelteKit route protection patterns
import type { LayoutLoad } from './$types';
import { redirect } from '@sveltejs/kit';
import { PUBLIC_BACKEND_URL } from '$env/static/public';

// This load function runs on both client and server
export const load: LayoutLoad = async ({ fetch }) => {
  try {
    const response = await fetch(`${PUBLIC_BACKEND_URL}/users/me`);
    if (!response.ok) {
      // If backend returns 401 or other error, user is not authenticated
      throw redirect(302, '/login');
    }
    const user = await response.json();
    return { user }; // Provide user data to nested layouts/pages
  } catch (error) {
    if (error instanceof Response && error.status === 302) {
      throw error; // Re-throw redirect response
    }
    console.error('Auth check failed:', error);
    throw redirect(302, '/login');
  }
};
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| Manual auth implementation | `fastapi-users` / dedicated libraries | ~2018 (FastAPI's rise) | Significantly reduced boilerplate, improved security defaults, faster development. |
| Storing JWT in `localStorage` | `HttpOnly` cookies | Ongoing shift (~2017 onwards) | Enhanced protection against XSS attacks, requiring careful backend cookie management. |
| Basic password hashing (MD5, SHA-1) | `Bcrypt`, `Argon2` (Passlib) | ~2010 onwards | Drastically increased resistance to brute-force and rainbow table attacks. |

**Deprecated/outdated:**
-   **Manual token management on frontend**: Trying to manually set `Authorization` headers from `localStorage` in every request when `HttpOnly` cookies can handle it automatically for same-origin requests.
-   **Synchronous password hashing**: Blocking the event loop in async frameworks. `passlib` (used by `FastAPI Users`) handles this asynchronously.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | `google_web_search` tool was temporarily unavailable; information for SvelteKit authentication and some FastAPI data isolation patterns are based on training data. | Summary, Standard Stack, Architecture Patterns, Common Pitfalls, Code Examples, State of the Art, Security Domain | The recommended patterns might not be the most current or widely accepted, leading to suboptimal or insecure implementation. Needs human verification. |
| A2 | The existing project uses SQLAlchemy, and `FastAPI Users`' SQLAlchemy adapter is compatible with the project's current setup. | Standard Stack | May require significant refactoring of database layer if incompatible. |
| A3 | HttpOnly cookies are feasible for JWT storage given the current project setup (FastAPI and SvelteKit likely on the same domain or with controlled CORS settings). | Architecture Patterns, Common Pitfalls | If domains differ significantly or CORS is complex, this approach might need adjustments or fallbacks (e.g., secure `localStorage` with refresh tokens). |

## Open Questions

1.  **Frontend JWT storage strategy**:
    -   What we know: `HttpOnly` cookies are generally more secure against XSS than `localStorage`.
    -   What's unclear: Is the SvelteKit frontend expected to run on the same domain as the FastAPI backend? This directly impacts the feasibility and ease of `HttpOnly` cookie usage. If not, a more complex token management strategy (e.g., `localStorage` with robust XSS protection, refresh tokens, and careful header management) might be needed.
    - Recommendation: Confirm deployment strategy for frontend and backend to finalize JWT storage.
    - **Resolution for Phase 11**: For this phase, we will proceed with storing JWTs in `localStorage` in the SvelteKit frontend. This decision acknowledges the architectural simplicity for initial development given potential cross-domain deployment scenarios or different port mappings during development. We recognize the increased XSS vulnerability with `localStorage` and mitigate this by ensuring robust input sanitization on both frontend and backend, and plan for future hardening to `HttpOnly` cookies or a more sophisticated token management system (e.g., refresh tokens) in a subsequent phase, once the deployment strategy is fully formalized.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| Python 3.x | Backend | ✓ | (checked by `pip`) | — |
| pip | Backend package management | ✓ | (checked by `pip`) | — |

**Missing dependencies with no fallback:**
-   None identified.

## Validation Architecture

### Test Framework
| Property | Value |
|---|---|
| Framework | `pytest` |
| Config file | `pyproject.toml` or `pytest.ini` (assumed from existing `tests/` structure) |
| Quick run command | `pytest tests/test_{module}.py::test_{name} -x` |
| Full suite command | `pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| AUTH-01 | User registration (success) | E2E, Integration | `pytest tests/test_api.py::test_user_registration` | ❌ Wave 0 |
| AUTH-02 | User registration (failure: duplicate email, weak password) | Integration | `pytest tests/test_api.py::test_user_registration_failure` | ❌ Wave 0 |
| AUTH-03 | User login (success) | E2E, Integration | `pytest tests/test_api.py::test_user_login_success` | ❌ Wave 0 |
| AUTH-04 | User login (failure: bad credentials) | Integration | `pytest tests/test_api.py::test_user_login_failure` | ❌ Wave 0 |
| AUTH-05 | Protected route access (authenticated) | E2E, Integration | `pytest tests/test_api.py::test_protected_route_access` | ❌ Wave 0 |
| AUTH-06 | Protected route access (unauthenticated) | E2E, Integration | `pytest tests/test_api.py::test_protected_route_unauthenticated` | ❌ Wave 0 |
| AUTH-07 | Data isolation (user can only see own data) | Integration | `pytest tests/test_api.py::test_data_isolation` | ❌ Wave 0 |
| AUTH-08 | Data isolation (user cannot see other user's data) | Integration | `pytest tests/test_api.py::test_data_isolation_other_user` | ❌ Wave 0 |
| AUTH-09 | Password hashing strength | Unit | `pytest tests/test_security.py::test_password_hashing_strength` | ❌ Wave 0 |

### Sampling Rate
-   **Per task commit:** `pytest tests/test_api.py::test_{new_feature_test_name} -x`
-   **Per wave merge:** `pytest`
-   **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
-   [ ] `tests/test_api.py` — New API integration tests for authentication and data isolation.
-   [ ] `tests/test_security.py` — Unit tests for password hashing or security utilities.
-   [ ] Framework install: `pip install pytest pytest-asyncio` — if not already installed.
-   [ ] SvelteKit E2E tests: These are not covered by pytest. Will need a separate framework (e.g., Playwright or Cypress) to test frontend login flow and protected routes end-to-end. This is a significant gap.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | yes | `fastapi-users` for user management, `passlib` for hashing, JWT-based sessions. |
| V3 Session Management | yes | JWT with appropriate lifetime, `HttpOnly`/`Secure` cookies for token storage. |
| V4 Access Control | yes | `FastAPI Users` current user dependencies, explicit `user_id` filtering in database queries. |
| V5 Input Validation | yes | FastAPI Pydantic models for request body validation in auth routes. |
| V6 Cryptography | yes | `passlib` (Bcrypt/Argon2) for password hashing, `python-jose`/`PyJWT` for JWT signing. (Never hand-roll crypto). |

### Known Threat Patterns for `FastAPI (Python)` / `SvelteKit`

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Brute-force attacks (login) | Tampering | Rate limiting on login attempts (can be implemented with FastAPI middleware or `fastapi-limiter`). |
| XSS (Cross-Site Scripting) | Tampering | `HttpOnly` and `Secure` cookies for JWTs; proper input sanitization on frontend and backend. |
| CSRF (Cross-Site Request Forgery) | Tampering | CSRF tokens for form submissions (especially if using cookies); `SameSite=Lax` or `Strict` for cookies. |
| Insecure Direct Object Reference (IDOR) | Information Disclosure, Tampering | Always filter database queries by the authenticated user's ID (`user.id == Item.user_id`). |
| SQL Injection | Tampering, Information Disclosure | SQLAlchemy ORM by default prevents SQL injection by parameterizing queries. |
| Weak Password Storage | Information Disclosure | Strong, slow hashing algorithms (Bcrypt/Argon2) via `passlib`. |
| Unauthenticated API Access | Information Disclosure, Tampering | Use `FastAPI Users` dependencies (`current_active_user`) on all protected routes. |

## Sources

### Primary (HIGH confidence)
-   [CITED: fastapi-users.github.io/] - General features, JWT strategy, SQLAlchemy integration, user management, current user dependency.

### Secondary (MEDIUM confidence)
-   None explicitly.

### Tertiary (LOW confidence)
-   `google_web_search` tool failure prevented direct verification for some common patterns in SvelteKit and FastAPI data isolation. These sections are marked `[ASSUMED]`.

## Metadata

**Confidence breakdown:**
-   Standard stack: HIGH - `FastAPI Users` is a well-regarded solution for FastAPI auth.
-   Architecture: MEDIUM - Backend patterns are standard, but frontend token storage relies on `[ASSUMED]` context for `HttpOnly` cookie feasibility.
-   Pitfalls: MEDIUM - Based on general security knowledge, but specific vulnerabilities might require deeper investigation.

**Research date:** 2024-07-30
**Valid until:** 2024-10-30 (3 months for a stable domain like authentication)