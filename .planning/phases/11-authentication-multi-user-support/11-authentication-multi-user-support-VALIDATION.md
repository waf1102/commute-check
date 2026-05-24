# Phase 11: Authentication & Multi-User Support - Validation

## Test Framework
| Property | Value |
|---|---|
| Framework | `pytest` |
| Config file | `pyproject.toml` or `pytest.ini` (assumed from existing `tests/` structure) |
| Quick run command | `pytest tests/test_{module}.py::test_{name} -x` |
| Full suite command | `pytest` |

## Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | Expected Result |
|---|---|---|---|---|
| AUTH-01 | User registration (success) | E2E, Integration | `pytest tests/test_api.py::test_user_registration_success` | New user created in database, valid JWT returned upon auto-login or subsequent login. |
| AUTH-02 | User registration (failure: duplicate email) | Integration | `pytest tests/test_api.py::test_user_registration_failure_duplicate_email` | API returns 400/409 error, user not created. |
| AUTH-03 | User registration (failure: weak password) | Integration | `pytest tests/test_api.py::test_user_registration_failure_weak_password` | API returns 400 error, user not created. |
| AUTH-04 | User login (success) | E2E, Integration | `pytest tests/test_api.py::test_user_login_success` | Valid JWT (e.g., via `HttpOnly` cookie) returned. Protected frontend routes accessible. |
| AUTH-05 | User login (failure: bad credentials) | Integration | `pytest tests/test_api.py::test_user_login_failure_bad_credentials` | API returns 400/401 error, no JWT returned. Protected frontend routes inaccessible. |
| AUTH-06 | Protected route access (authenticated) | E2E, Integration | `pytest tests/test_api.py::test_protected_route_access_authenticated` | User can successfully access and retrieve data from a protected backend route. |
| AUTH-07 | Protected route access (unauthenticated) | E2E, Integration | `pytest tests/test_api.py::test_protected_route_access_unauthenticated` | API returns 401 Unauthorized error for protected routes. Frontend redirects to login. |
| AUTH-08 | Data isolation (user can only see own data) | Integration | `pytest tests/test_api.py::test_data_isolation_user_own_data` | When logged in as User A, API returns only data explicitly owned by User A. |
| AUTH-09 | Data isolation (user cannot see other user's data) | Integration | `pytest tests/test_api.py::test_data_isolation_user_other_data` | When logged in as User A, API returns empty or 403 Forbidden when attempting to access data owned by User B. |
| AUTH-10 | Password hashing strength | Unit | `pytest tests/test_security.py::test_password_hashing_strength` | Verify `passlib` is used with a strong algorithm (e.g., Bcrypt/Argon2) and salt is generated. |
| AUTH-11 | JWT expiration | Unit, Integration | `pytest tests/test_security.py::test_jwt_expiration` | Expired JWTs are rejected by the backend. |

## Sampling Rate
-   **Per task commit:** Execute relevant specific integration and unit tests (`pytest tests/test_{module}.py::test_{name} -x`).
-   **Per wave merge:** Run the full `pytest` suite for backend tests.
-   **Phase gate:** The full `pytest` suite must pass, and manual verification/E2E tests for SvelteKit (if available) must confirm frontend behavior.

## Wave 0 Gaps
-   [ ] `tests/test_api.py`: Create new integration tests for all backend authentication and data isolation endpoints.
-   [ ] `tests/test_security.py`: Create new unit tests for password hashing and JWT validation (though much is handled by `fastapi-users`).
-   [ ] `pip install pytest pytest-asyncio httpx` (if not already present): Ensure test dependencies are installed.
-   [ ] **SvelteKit E2E Tests**: Implement end-to-end tests for the frontend. This will involve:
    -   User registration via UI.
    -   User login via UI.
    -   Accessing protected routes.
    -   Verification of frontend redirects on unauthenticated access.
    -   Verification of data displayed in the UI is specific to the logged-in user.
    -   **Recommendation:** Investigate frameworks like Playwright or Cypress for SvelteKit E2E testing. This is a crucial missing piece for full validation.
