# Research: Frontend Foundation

All Technical Context unknowns are resolved below. Versions are the latest stable releases on
2026-11-27 (`npm view`), pinned with `^` in `package.json`.

## R1. Authentication mechanism (FR-001, FR-005, FR-006)

- **Decision**: Reuse Django's session authentication. The session cookie is `HttpOnly`,
  `SameSite=Lax`. CSRF protection uses Django's `csrftoken` cookie, which axios echoes back in the
  `X-CSRFToken` header (`xsrfCookieName` / `xsrfHeaderName`).
- **Rationale**: Session auth is already configured in DRF. No token is ever readable by page
  scripts, so an XSS bug cannot steal one. Sign-out invalidates the session on the server at once.
  No new backend dependency is needed.
- **Alternatives considered**: JWT (SimpleJWT) access and refresh tokens. This needs token storage
  (localStorage can be read by XSS; an in-memory token is lost on reload), a refresh endpoint and
  a revocation list. It also adds a dependency. That complexity buys nothing for a single-origin
  staff app.

## R2. Distinguishing "not signed in" from "not permitted" (FR-007, FR-015)

- **Finding**: DRF picks the status code from the *first* authentication class's
  `authenticate_header()`. `SessionAuthentication` returns `None` there, so unauthenticated
  requests currently get **403**, the same status as permission errors. The frontend would then
  either sign people out on permission errors or never notice an expired session.
- **Decision**: Add `accounts.authentication.SessionAuthentication`, a subclass whose
  `authenticate_header()` returns `'Session'`, and make it the first default authentication
  class. Unauthenticated requests then return **401** with `WWW-Authenticate: Session`, which does
  not trigger the browser's Basic-auth popup. Permission failures stay **403**.
  `BasicAuthentication` is removed from the defaults. No client uses it, and leaving it enabled in
  production accepts passwords on every request.
- **Impact on existing tests**: The existing auth sweep tests assert `status in (401, 403)`, so
  they keep passing. A new test asserts exactly 401 for anonymous requests and 403 for
  authenticated requests that lack permission.
- **Alternatives considered**: Inspect the 403 body's `detail` text on the client. This is
  brittle (localized text) and was rejected.

## R3. Session lifetime (Clarification Q2)

- **Decision**: Set `SESSION_COOKIE_AGE = 8 * 60 * 60` (overridable by the `DJANGO_SESSION_AGE`
  env var) and `SESSION_SAVE_EVERY_REQUEST = True`, which makes the expiry sliding. Also set
  `SESSION_COOKIE_HTTPONLY = True` (the default, stated explicitly), `SESSION_COOKIE_SAMESITE =
  "Lax"`, and `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` from `DJANGO_SECURE_COOKIES`
  (true in production). There is no client-side idle timer.
- **Rationale**: This matches the clarification. `SAVE_EVERY_REQUEST` costs one session-row write
  per request, which is negligible at single-store load.

## R4. Dev and prod origin topology (FR-017)

- **Decision**: The browser always calls a **same-origin** relative base URL, `/api`
  (`VITE_API_BASE_URL`, default `/api`). In development, Vite's `server.proxy` forwards `/api` to
  `VITE_DEV_API_TARGET` (default `http://localhost:8000`). In production, a reverse proxy serves
  the built frontend and `/api` on one origin.
- **Rationale**: With a single origin, cookies, CSRF and SameSite just work. There are no CORS
  preflights, and axios sends the XSRF header automatically for same-origin requests. The
  existing CORS settings stay as they are, and nothing has to be widened.
- **Alternatives considered**: Cross-origin calls from `:5173` to `:8000`. These need
  `CORS_ALLOW_CREDENTIALS`, `CSRF_TRUSTED_ORIGINS` and `withXSRFToken`, which is a larger attack
  surface and was rejected.

## R5. Back-office auth endpoints (Clarification Q1, FR-002–FR-004)

- **Decision**: Add the following endpoints in `accounts` under `/api/auth/`:
  - `GET csrf/` sets the CSRF cookie (`ensure_csrf_cookie`) and returns 204.
  - `POST login/` uses `authenticate()` then `login()`. It is CSRF-protected even though the
    caller is anonymous (`csrf_protect`), which prevents login-CSRF.
  - `POST logout/`.
  - `GET me/`.
  The exact shapes are in [contracts/auth-api.md](contracts/auth-api.md).
  `me` returns `permissions` as the sorted list from `user.get_all_permissions()`
  (`"app_label.codename"`).
- **Rate limiting**: two throttles apply to login only. Each defaults to `10/min` and can be
  overridden by env:
  - `ScopedRateThrottle` (scope `login`) is keyed by client IP.
  - `accounts.throttling.LoginUsernameThrottle` (scope `login_username`) is keyed by the
    normalized username, so rotating addresses can't speed up guessing one account.

  The client IP comes from `REMOTE_ADDR`. `X-Forwarded-For` is only trusted `NUM_PROXIES` hops
  back (`DJANGO_NUM_PROXIES`, default 0); otherwise DRF would use the whole header, which
  clients can forge (code review, 2026-11-27). The limits use Django's cache. The default
  local-memory cache works per process, so a multi-worker deployment needs a shared cache. A
  throttled request returns 429 with a `Retry-After` header.
- **Reverse proxy**: `DJANGO_BEHIND_HTTPS_PROXY` sets `SECURE_PROXY_SSL_HEADER`, and
  `DJANGO_CSRF_TRUSTED_ORIGINS` sets `CSRF_TRUSTED_ORIGINS`. Without one of them, a proxy that
  terminates HTTPS would make Django's CSRF origin check reject every login.
- **Generic failure**: Wrong credentials and inactive accounts both return 400 with
  `{"non_field_errors": ["Invalid username or password."]}`. `ModelBackend` already rejects
  inactive users.

## R6. Routing library (FR-009–FR-013)

- **Decision**: `react-router` ^8.5 in *data/declarative library mode*: `createBrowserRouter` +
  `RouterProvider`, with nested layout routes (`RequireAuth`, `AppLayout`) and a central
  route table that declares each work area's `path`, `label` and optional `permission`.
  The navigation and the permission guard both read from this table.
- **Rationale**: This is the de facto standard. It gives nested layouts, bookmarkable URLs, and
  `useLocation` for the "return to where you were" flow. Framework mode (SSR, file routes) is
  not needed for a client-only SPA.
- **Alternatives considered**: TanStack Router has better type safety but is a heavier mental
  model and less widely known. Wouter is too minimal for nested guarded layouts.

## R7. Global state (FR-018–FR-020)

- **Decision**:
  - **Session**: an `AuthProvider` (React context + `useReducer`) holds
    `{status: 'checking' | 'authenticated' | 'anonymous' | 'unreachable', user, endReason}`.
  - **Server data**: `@tanstack/react-query` ^5.108 with one `QueryClient`. On sign-out or
    session expiry, `queryClient.clear()` runs so the next person never sees the previous
    person's data (SC-006).
  - **Everything else** (forms, filters, open modals) stays in component state.
- **Cross-tab identity**: while signed in, `AuthProvider` re-checks `GET /auth/me/` when the
  window regains focus or becomes visible. A different user id replaces the identity and
  clears the cache. A 401 is handled as an expired session. Without this, a tab could show
  the previous staff member while its requests run as the new one, because a replaced session
  never produces a 401.
- **Rationale**: Only two things are truly global. React Query provides caching, deduplication,
  loading/error states and invalidation, which would otherwise be rebuilt by hand. Context is
  enough for a rarely changing session object.
- **Alternatives considered**: Redux Toolkit/RTK Query and Zustand. Both add a store with no
  current need. Rejected under the "only global state where necessary" request and the
  constitution's dependency-justification rule.

## R8. API client design (FR-014–FR-016)

- **Decision**: One axios instance in `src/api/client.ts` with:
  - `baseURL` from the config, `withCredentials: true`, the XSRF cookie and header names, and
    `timeout: 15000`.
  - A response interceptor that turns every failure into an `ApiError` (see
    [data-model.md](data-model.md#apierror)) and, on 401, calls a single registered
    `onUnauthenticated` handler. The handler fires once per session: a latch is set on the
    first 401 and cleared only by a successful sign-in, so concurrent or late 401s redirect once.
  - Typed helpers `get/post/patch/del<T>` and `getPage<T>()`. `getPage` returns `Paginated<T>`
    and accepts DRF `page`, `search`, `ordering` and filter params.
  - One module per domain (`src/api/{catalog,inventory,sales,customers,stringing,preorders}.ts`)
    with hand-written TypeScript types that mirror the serializers, plus endpoint functions.
    Money is typed as `Money = string`, because DRF serializes `DecimalField` as a string;
    numbers never pass through a float (constitution: money).
- **Rationale**: Hand-written types are small (about 1.3k lines of serializers), have no
  generator dependency, and get reviewed alongside the serializer they mirror.
- **Alternatives considered**: `drf-spectacular` + `openapi-typescript`. Many views are plain
  `APIView`s with input/output serializers chosen in code, so the generated schema would need
  `@extend_schema` on almost every view. Reconsider once the API surface is stable.
- **Fetch vs axios**: The constitution prescribes axios, and axios is already installed.

## R9. Testing (FR-021, FR-022)

- **Frontend**: `vitest` ^5.1 (shares the Vite config) + `jsdom` ^31, `@testing-library/react`
  ^16.3, `@testing-library/user-event` ^14.6, `@testing-library/jest-dom` ^8, and `msw` ^3.0 to
  mock the HTTP layer at the network boundary. With msw, the real axios client and interceptors
  run under test.
- **Backend**: The Django test runner, with `APITestCase` in `accounts/tests/test_auth_api.py`.
  The empty `accounts/tests.py` is replaced by a `tests/` package (constitution organization).
  Throttle tests clear the cache in `setUp`.

## R10. Bundle budget (Principle IV)

- Estimated gzipped sizes: react + react-dom ≈ 60 KB, react-router ≈ 22 KB, react-query ≈ 13 KB,
  axios ≈ 14 KB, Bootstrap CSS ≈ 25 KB (CSS, not counted in the JS budget). The JS total is about
  110 KB, well under the 300 KB budget. Work-area pages are lazy-loaded (`lazy` route property) so
  later features don't grow the initial bundle. The devtools for React Query are dev-only and are
  not added now.
