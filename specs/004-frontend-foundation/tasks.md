---
description: "Task list for Frontend Foundation"
---

# Tasks: Frontend Foundation

**Input**: Design documents from `/specs/004-frontend-foundation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/auth-api.md,
contracts/frontend-modules.md, quickstart.md

**Tests**: Required. FR-021 and FR-022 call for them, and so does constitution Principle II.
Within each story, write the test tasks first and make sure they fail before you implement.

**Organization**: Tasks are grouped by user story so each story can be built and tested on
its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on unfinished tasks)
- **[Story]**: US1–US4 from spec.md
- Paths: `backend/…`, `frontend/…` (web app layout, per plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Turn the Vite starter into a strict, testable project.

- [X] T001 Add runtime deps `react-router@^8.5` and `@tanstack/react-query@^5.108`, and dev deps `vitest@^5.1`, `jsdom@^31`, `@testing-library/react@^16.3`, `@testing-library/user-event@^14.6`, `@testing-library/jest-dom@^8` and `msw@^3.0`, in frontend/package.json (run `npm install` from `frontend/`). Add the scripts `"test": "vitest run"`, `"test:watch": "vitest"` and `"typecheck": "tsc -b"`.
- [X] T002 [P] Set `"strict": true` in frontend/tsconfig.app.json and add `"vitest/globals"` and `"@testing-library/jest-dom"` to `types`. Confirm frontend/tsconfig.node.json covers vite.config.ts.
- [X] T003 [P] In frontend/vite.config.ts, add `server.proxy['/api']` targeting `process.env.VITE_DEV_API_TARGET ?? 'http://localhost:8000'` (read with `loadEnv`, `changeOrigin: false`). Also add a `test` block: `environment: 'jsdom'`, `globals: true`, `setupFiles: ['src/test/setup.ts']`, `css: false`. Covers research R4 and R9.
- [X] T004 [P] Create frontend/.env.example with `VITE_API_BASE_URL=/api` and `VITE_DEV_API_TARGET=http://localhost:8000`, with comments. Check that frontend/.env stays untracked by git. If its `VITE_API_BASE_URL` is an absolute `http://…:8000` URL, tell the developer to switch it to `/api` (do not edit their .env).
- [X] T005 [P] Remove the starter files frontend/src/App.tsx, frontend/src/App.css and frontend/src/assets/, and the unused files in frontend/public/ (keep favicon.svg). Reduce frontend/src/index.css to a minimal reset. Set the `<title>` in frontend/index.html to "Ace&Rally POS".

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the API client, error model, test harness and backend status-code fix. All
stories depend on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests first

- [X] T006 [P] Write unit tests for `toApiError` in frontend/src/api/errors.test.ts. Cover every row of the mapping table in data-model.md#apierror (network/timeout, 400 field + non_field + `detail`, 401, 403, 404, 409 string and object `detail`, 429 with `Retry-After`, 500, an unknown status, and a non-axios thrown value). Also cover nested DRF error flattening to dotted keys (`items.0.quantity`).
- [X] T007 [P] Write backend tests in backend/accounts/tests/test_auth_classes.py, and create backend/accounts/tests/__init__.py. They must show that:
  - an anonymous GET to `customer-list-create` returns exactly 401 with the header `WWW-Authenticate: Session`;
  - an authenticated user without `customers.delete_customer` doing DELETE on `customer-detail` gets exactly 403;
  - HTTP Basic credentials are no longer accepted (the response is 401).
  These cover research R2 and contracts/auth-api.md "Global change".

### Implementation

- [X] T008 Delete backend/accounts/tests.py (it conflicts with the new `tests/` package). Create backend/accounts/authentication.py: `SessionAuthentication(rest_framework.authentication.SessionAuthentication)` with `authenticate_header()` returning `"Session"`, and a docstring giving the reason (R2).
- [X] T009 Update `REST_FRAMEWORK` in backend/config/settings.py:
  - `DEFAULT_AUTHENTICATION_CLASSES = ["accounts.authentication.SessionAuthentication"]` (Basic removed).
  - `DEFAULT_THROTTLE_RATES = {"login": os.getenv("DJANGO_LOGIN_THROTTLE_RATE", "10/min")}`.

  Add the session settings from R3: `SESSION_COOKIE_AGE = int(os.getenv("DJANGO_SESSION_AGE", 28800))`, `SESSION_SAVE_EVERY_REQUEST = True`, `SESSION_COOKIE_HTTPONLY = True` and `SESSION_COOKIE_SAMESITE = "Lax"`. Set `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` from `DJANGO_SECURE_COOKIES`. Document the new variables in backend/.env.example. Run the full backend suite and fix any test that asserted 403 for anonymous access (expected: none, since the sweeps accept 401 or 403).
- [X] T010 [P] Create frontend/src/config.ts exporting `config.apiBaseUrl` (from `import.meta.env.VITE_API_BASE_URL`, default `/api`). Add `ImportMetaEnv` typings in frontend/src/vite-env.d.ts.
- [X] T011 Implement frontend/src/api/errors.ts per contracts/frontend-modules.md: the `ApiError` class, `toApiError`, `isApiError` and `flattenFieldErrors`, using the messages and kinds in data-model.md#apierror (ApiError.kind, ApiError.message, ApiError.fieldErrors, ApiError.nonFieldErrors). `unexpected` errors are logged with `console.error` and never put in `message`. T006 must pass.
- [X] T012 Write tests for the client in frontend/src/api/client.test.ts (msw):
  - `withCredentials` is set and requests go to `config.apiBaseUrl`;
  - the `X-CSRFToken` header echoes the `csrftoken` cookie on POST, PATCH and DELETE;
  - rejections are always `ApiError`;
  - three concurrent 401s call the registered unauthenticated handler exactly once;
  - a 401 from `/auth/login/` or `/auth/me/` does **not** call the handler;
  - `apiGetPage` returns `Paginated<T>` and serializes `page`, `search`, `ordering` and filters, dropping `undefined`.
- [X] T013 Implement frontend/src/api/client.ts per contracts/frontend-modules.md: an axios instance (`baseURL`, `withCredentials: true`, `xsrfCookieName: 'csrftoken'`, `xsrfHeaderName: 'X-CSRFToken'`, `timeout: 15000`), a response interceptor that maps errors to `ApiError` and calls the handler on 401 (debounced, auth endpoints excluded), `setUnauthenticatedHandler`, and the typed helpers `apiGet`, `apiGetPage`, `apiPost`, `apiPatch` and `apiDelete`. Also export the `Money` and `Paginated<T>` types (data-model.md#paginatedt: Paginated.count, Paginated.next, Paginated.previous, Paginated.results). T012 must pass.
- [X] T014 [P] Create frontend/src/api/queryClient.ts with a `createQueryClient()` factory. Queries retry at most once, and never on an `ApiError` with status 4xx. Set `staleTime: 30_000` and `refetchOnWindowFocus: false` (counter machines shouldn't refetch on every focus).
- [X] T015 Create the test harness:
  - frontend/src/test/server.ts: msw `setupServer`.
  - frontend/src/test/handlers.ts: default handlers for `/api/auth/csrf/`, `/api/auth/me/` (401 by default) and `/api/auth/login/`, plus helpers `asUser(user)` and `asAnonymous()`.
  - frontend/src/test/setup.ts: jest-dom, server listen/reset/close, `onUnhandledFrame: 'error'`, and clearing cookies between tests.
  - frontend/src/test/renderApp.tsx: renders the provider tree with a fresh QueryClient and `createMemoryRouter` at a given URL.

**Checkpoint**: `npm test` (errors and client tests) and `manage.py test` (all suites) pass.

---

## Phase 3: User Story 1 - Staff sign in and out (Priority: P1) 🎯 MVP

**Goal**: Staff can sign in with username and password, see who is signed in, and sign out.
Protected pages need a session.

**Independent Test**: Sign in, see your name, sign out, and confirm protected pages are
unreachable (quickstart scenarios 1–4).

### Tests for User Story 1

- [X] T016 [P] [US1] Write backend API tests in backend/accounts/tests/test_auth_api.py covering every bullet in contracts/auth-api.md "Required tests". Exceptions: the 401/403 split is covered by T007, and the throttle test calls `cache.clear()` in `setUp`. Use `APIClient(enforce_csrf_checks=True)` for the CSRF cases. Assert that the success body has exactly the CurrentUser keys (data-model.md#currentuser: CurrentUser.id, CurrentUser.username, CurrentUser.first_name, CurrentUser.last_name, CurrentUser.display_name, CurrentUser.is_superuser, CurrentUser.permissions).
- [X] T017 [P] [US1] Write unit tests for the reducer in frontend/src/auth/authReducer.test.ts, covering every transition in data-model.md#session-authcontext-state (Session.status, Session.user, Session.endReason).
- [X] T018 [P] [US1] Write unit tests for `safeNextPath` in frontend/src/auth/safeNextPath.test.ts. It accepts `/preorders?x=1#y`. It rejects `null`, `''`, `//evil.com`, `/\evil.com`, `https://evil.com`, `javascript:alert(1)`, `/login` and `/login?next=/x`, and returns `/` for each of them (FR-008).
- [X] T019 [P] [US1] Write integration tests in frontend/src/pages/LoginPage.test.tsx (msw + renderApp):
  - signing out then visiting `/preorders` shows the sign-in page, and successful sign-in lands on `/preorders` (US1-1);
  - wrong credentials show "Invalid username or password" and clear the password (US1-2);
  - empty fields send no request and flag the fields (US1-3);
  - while pending, the submit button is disabled and a double click sends one request (US1-4, edge case);
  - a 429 shows the rate-limit message;
  - an authenticated visit to `/login` redirects to `/` (US3-5).
- [X] T020 [P] [US1] Write integration tests in frontend/src/layouts/AppLayout.test.tsx. The display name and "Sign out" are shown (FR-013). Sign out calls `/auth/logout/`, shows the sign-in page with "You have been signed out", and clears the query cache (seed a query, then assert it is gone, SC-006). Sign out while logout returns a network error still signs out locally (edge case).

### Implementation for User Story 1

- [X] T021 [P] [US1] Create backend/accounts/serializers.py. `LoginSerializer` has required `username` and `password` (`trim_whitespace=False` for the password) and a `validate` that calls `authenticate(request=…)`, raising the generic `non_field_errors` message from contracts/auth-api.md. `CurrentUserSerializer` has the fields in data-model.md#currentuser (CurrentUser.display_name = `get_full_name() or username`; CurrentUser.permissions = `sorted(user.get_all_permissions())`).
- [X] T022 [US1] Create backend/accounts/views.py, replacing the stub:
  - `CsrfView` (GET, `AllowAny`, `ensure_csrf_cookie`, returns 204);
  - `LoginView` (POST, `AllowAny`, `csrf_protect` via `method_decorator` on `dispatch`, `ScopedRateThrottle` with `throttle_scope = "login"`, `django.contrib.auth.login`, returns 200 with CurrentUser);
  - `LogoutView` (POST, `AllowAny`, `logout`, returns 204);
  - `MeView` (GET, `IsAuthenticated`).
  Views stay thin (Principle I). Each view gets a docstring stating its session side effects.
- [X] T023 [US1] Create backend/accounts/urls.py with the names `auth-csrf`, `auth-login`, `auth-logout` and `auth-me`, and add `path("api/auth/", include("accounts.urls"))` to backend/config/urls.py. T016 must pass, and ruff must be clean.
- [X] T024 [P] [US1] Create frontend/src/api/auth.ts with the `CurrentUser` type and `authApi` (`csrf`, `login`, `logout`, `me`) per contracts/frontend-modules.md.
- [X] T025 [P] [US1] Implement frontend/src/auth/authReducer.ts (state, actions and transitions from data-model.md#session-authcontext-state) and frontend/src/auth/safeNextPath.ts. T017 and T018 must pass.
- [X] T026 [US1] Implement frontend/src/auth/AuthProvider.tsx and frontend/src/auth/useAuth.ts per contracts/frontend-modules.md:
  - On mount, run `Promise.all([authApi.csrf(), authApi.me()])`. Map 200 to `authenticated`, 401 to `anonymous`, and `network` to `unreachable`.
  - `login` calls csrf if the cookie is missing, then login, then dispatches.
  - `logout` uses try/finally: it always dispatches `signed_out` and calls `queryClient.clear()`.
  - `hasPermission` returns true for superusers.
  - No browser storage is used.
- [X] T027 [P] [US1] Implement frontend/src/auth/RequireAuth.tsx as a layout route:
  - `checking` renders `SessionCheckingPage`;
  - `unreachable` renders `ServerUnreachablePage`;
  - `anonymous` does `<Navigate to={'/login?next=' + encodeURIComponent(path+search+hash)} replace />`;
  - otherwise it renders `<Outlet/>`.
  Also create frontend/src/pages/SessionCheckingPage.tsx (accessible "Checking your session…" status, `role="status"`).
- [X] T028 [US1] Implement frontend/src/pages/LoginPage.tsx:
  - labelled username and password inputs, autofocus on the username, `autocomplete` attributes;
  - client-side required checks;
  - the submit button is disabled while pending;
  - field and non-field errors come from `ApiError`, and the password is cleared on error;
  - an `endReason` message ("You have been signed out." / "Your session has ended. Please sign in again.");
  - on success, `navigate(safeNextPath(next), {replace: true})`;
  - an authenticated visitor is redirected to `/`.
  Use minimal Bootstrap form classes only (design is deferred).
- [X] T029 [US1] Implement frontend/src/layouts/AppLayout.tsx (top bar with "Ace&Rally POS", the user's `display_name`, a Sign out button, and `<Outlet/>`) and frontend/src/pages/HomePage.tsx ("Welcome, {display_name}").
- [X] T030 [US1] Create frontend/src/routes/router.tsx with `/login` → LoginPage, and a `RequireAuth` > `AppLayout` > `/` → HomePage branch. Rewrite frontend/src/main.tsx to render `QueryClientProvider(createQueryClient())` > `AuthProvider` > `RouterProvider`, keeping the Bootstrap CSS import. T019 and T020 must pass.

**Checkpoint**: quickstart scenarios 1–4 work against the real backend. This is the MVP.

---

## Phase 4: User Story 2 - Session survives reloads and ends safely (Priority: P1)

**Goal**: A reload keeps the session. A session that ends on the server sends staff to sign in
once, with a message, and afterwards returns them to the same page.

**Independent Test**: quickstart scenarios 5, 6 and 8.

### Tests for User Story 2

- [X] T031 [P] [US2] Write integration tests in frontend/src/auth/AuthProvider.test.tsx:
  - when `me` returns 200, the requested route renders and the sign-in page never appears (assert the checking state first, US2-1, edge case "no flash");
  - when a later data request returns 401, the app shows sign-in with "Your session has ended…", the cache is cleared, and signing in returns to the original path (US2-2, SC-004);
  - three parallel 401s cause one redirect (edge case);
  - a 403 does not sign the user out (US4-4);
  - when the network is down on load, the unreachable page appears with Retry, and Retry with the server back up shows the page (edge case "offline on load").

### Implementation for User Story 2

- [X] T032 [US2] In frontend/src/auth/AuthProvider.tsx, register `setUnauthenticatedHandler` on mount (unregister on unmount). The handler dispatches `expired` (only when it is currently `authenticated`) and calls `queryClient.clear()`. Make sure `RequireAuth` builds `next` from the current location, so the user is returned to it.
- [X] T033 [P] [US2] Create frontend/src/pages/ServerUnreachablePage.tsx with the "Cannot reach the server. Check the connection and try again." message and a Retry button that calls `useAuth().retry()`. Wire `retry` in AuthProvider (`unreachable` → `checking` → repeat the session check). T031 must pass.

**Checkpoint**: US1 and US2 both work. Manual scenario 6 (two tabs) passes.

---

## Phase 5: User Story 3 - Navigate between work areas (Priority: P2)

**Goal**: Bookmarkable work areas, a navigation bar that respects permissions, and Not Found and
Access Denied screens.

**Independent Test**: quickstart scenario 7, plus the permission test below.

### Tests for User Story 3

- [X] T034 [P] [US3] Write integration tests in frontend/src/routes/router.test.tsx:
  - for **every** entry in `workAreas`, a signed-out visit redirects to `/login?next=<path>` (SC-003);
  - a signed-in visit renders the area's label as the heading;
  - the navigation marks the current area (`aria-current="page"`);
  - `/does-not-exist` shows "Page not found" with a Home link, whether signed in or out;
  - with a test area that requires `x.y`, a user without the permission sees "You don't have access to this area" and the nav hides it, while a superuser sees it (US3-4).
  Inject the test area through a `createAppRouter(areas)` parameter.

### Implementation for User Story 3

- [X] T035 [P] [US3] Create frontend/src/routes/workAreas.ts with the `WorkArea` type and entries from data-model.md#workarea-route-table-entry (WorkArea.path, WorkArea.label, WorkArea.permission, WorkArea.lazy): Home `/`, Sales `/sales`, Products `/products`, Inventory `/inventory`, Customers `/customers`, Stringing Orders `/stringing`, Pre-orders `/preorders`. None has a permission. Each `lazy` loads `WorkAreaPlaceholder` bound to the area.
- [X] T036 [P] [US3] Create frontend/src/pages/placeholders/WorkAreaPlaceholder.tsx (an `<h1>` with the area label and a "Coming soon" note), frontend/src/pages/NotFoundPage.tsx and frontend/src/pages/AccessDeniedPage.tsx.
- [X] T037 [P] [US3] Create frontend/src/auth/RequirePermission.tsx. It renders `AccessDeniedPage` when `permission` is set and `!hasPermission(permission)`, and otherwise renders its children.
- [X] T038 [US3] Refactor frontend/src/routes/router.tsx into `createAppRouter(areas = workAreas)` plus `export const router`. It generates the area routes under `RequireAuth` > `AppLayout`, wrapping each in `RequirePermission`, and adds `*` → NotFoundPage at the top level. Update frontend/src/layouts/AppLayout.tsx to render the navigation from `areas` filtered by `hasPermission`, using `NavLink`. T034 must pass.

**Checkpoint**: All routes are guarded and navigable. US1 and US2 tests still pass.

---

## Phase 6: User Story 4 - Consistent server communication and error feedback (Priority: P2)

**Goal**: Typed access to every existing backend area, and a shared way to show loading,
empty, error and success states.

**Independent Test**: Open the Pre-orders placeholder. It shows loading, then a "N pre-orders"
count, or an empty state, or the mapped error alert. Stop the backend to see "Cannot reach the
server".

### Tests for User Story 4

- [X] T039 [P] [US4] Write integration tests in frontend/src/components/QueryState.test.tsx. Loading renders `role="status"`. Empty renders the given empty text. Each `ApiError` kind renders its `message` in `role="alert"` and never shows raw JSON (SC-005). A validation error with only field errors renders the generic message.
- [X] T040 [P] [US4] Write contract tests in frontend/src/api/domain.test.ts (msw). For each domain module, call `list()` and one detail or action function. Assert the HTTP method, URL path (with trailing slash), query params, and that the typed result is passed through. Cover all six modules.

### Implementation for User Story 4

Each domain module mirrors backend/<app>/serializers.py and backend/<app>/urls.py, and the
contract docs where they exist (specs/001–003 contracts). Money and decimal fields are `Money`
(string), statuses are literal unions matching `TextChoices`, and each module exports a
`<domain>Keys` query-key factory. If a module would go over about 500 lines, split it (for
example `sales/`).

- [X] T041 [P] [US4] Create frontend/src/api/catalog.ts (products: list, get, create, update, and the other actions in backend/catalog/views.py).
- [X] T042 [P] [US4] Create frontend/src/api/inventory.ts (movements, movement detail and reverse, restocks, adjustments, low-stock, out-of-stock, summary).
- [X] T043 [P] [US4] Create frontend/src/api/sales.ts (sales list, create, detail; items add, update, remove; finalize; cancel; payments).
- [X] T044 [P] [US4] Create frontend/src/api/customers.ts using specs/001-customer-management/contracts/customers-api.md (list/create, detail/update/delete, archive, reactivate, phone-matches, and the sales, stringing-orders and preorders sub-lists).
- [X] T045 [P] [US4] Create frontend/src/api/stringing.ts using specs/002-stringing-management/contracts/stringing-api.md (orders CRUD, status, cancel, payments, history, revenue report).
- [X] T046 [P] [US4] Create frontend/src/api/preorders.ts using specs/003-preorder-management/contracts/preorders-api.md (list/create, detail/update, status, fulfill, cancel, payments, history, product summary and arrivals). T040 must pass.
- [X] T047 [US4] Create frontend/src/components/QueryState.tsx. It is a minimal shared renderer for `{isPending, error, isEmpty}` with loading, empty and error states (it uses `isApiError` and shows `error.message`), and renders its children on success. Extend `WorkArea` with an optional `countQuery` (`() => Promise<Paginated<unknown>>` plus a noun). Set it on the Products, Sales, Customers, Stringing Orders and Pre-orders areas in frontend/src/routes/workAreas.ts. Have WorkAreaPlaceholder use `useQuery` + `QueryState` to show "N <noun>". T039 must pass, and T034 must still pass (update its msw handlers for the count endpoints).

**Checkpoint**: All four stories work on their own. Quickstart scenarios 1–10 pass.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T048 [P] Replace frontend/README.md with project-specific setup, env vars, scripts, the folder layout (plan.md), and the "how to add a work area / API module" conventions.
- [X] T049 Run the full gates: `cd backend && .venv/bin/python manage.py test && .venv/bin/ruff check . && .venv/bin/ruff format --check` on new/changed files (the existing files predate formatting and are out of scope), then `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`. Fix every failure. Confirm there is no `any` without a justification comment (`grep -rn ": any\|as any" frontend/src`).
- [X] T050 Check the bundle budget: from `npm run build` output, the main JS is ≤ 300 KB gzipped (expected about 110 KB) and the area pages are separate chunks (Principle IV, SC-007).
- [X] T051 Do a manual pass of specs/004-frontend-foundation/quickstart.md scenarios 1–10 against a running backend. Record the results, plus any deviations, in the PR description. (2026-11-27: the API smoke test passed through the dev proxy, and the user confirmed the browser scenarios with a real staff account.)

---

## Phase 8: Review Fixes (from /code-review, 2026-11-27)

- [X] T052 Add failing tests in backend/accounts/tests/test_login_hardening.py:
  - spoofed `X-Forwarded-For` values don't reset the limit;
  - with `NUM_PROXIES=1`, clients are limited separately;
  - a per-username limit applies across addresses, ignoring case and whitespace;
  - login behind an HTTPS proxy works with `SECURE_PROXY_SSL_HEADER` or `CSRF_TRUSTED_ORIGINS` and fails without them.
- [X] T053 Add `LoginUsernameThrottle` in backend/accounts/throttling.py and apply it in `LoginView` (backend/accounts/views.py). In backend/config/settings.py, add `NUM_PROXIES` (`DJANGO_NUM_PROXIES`, default 0), the `login_username` rate, `SECURE_PROXY_SSL_HEADER` (`DJANGO_BEHIND_HTTPS_PROXY`) and `CSRF_TRUSTED_ORIGINS` (`DJANGO_CSRF_TRUSTED_ORIGINS`). Document all of them in backend/.env.example.
- [X] T054 Make the session check send only network failures to "Cannot reach the server"; server errors show the generic message. Changes: a `checkError` field in frontend/src/auth/authReducer.ts and frontend/src/auth/AuthContext.ts, plus frontend/src/auth/AuthProvider.tsx and frontend/src/pages/ServerUnreachablePage.tsx.
- [X] T055 In frontend/src/auth/AuthProvider.tsx, re-check `/auth/me/` on window focus and visibility. A different user replaces the identity and clears the cache; a 401 ends the session.
- [X] T056 In frontend/src/api/client.ts, reset the one-time 401 latch only after a successful sign-in, not after any 2xx.
- [X] T057 Update research.md (R5, R7, R8), data-model.md (Session) and contracts/auth-api.md to match. Rerun all gates.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)** has no dependencies. T001 comes first, then T002–T005 run in parallel.
- **Foundational (Phase 2)** depends on Phase 1. It blocks every story.
- **US1 (Phase 3)** depends on Phase 2. It is the MVP.
- **US2 (Phase 4)** depends on US1 (it extends AuthProvider and RequireAuth).
- **US3 (Phase 5)** depends on US1 (router and AppLayout). It is independent of US2 and can run
  in parallel with it.
- **US4 (Phase 6)**: the domain modules T040–T046 depend only on Phase 2 and can start right
  after it. T047 depends on US3 (workAreas, placeholder).
- **Polish (Phase 7)** depends on all stories.

### Within each story

Write the tests and confirm they fail. Then build in this order: backend (serializers → views →
urls), then frontend (api → state → guards → pages → router wiring).

## Parallel Examples

```text
# Phase 2 kick-off
T006 errors.test.ts | T007 test_auth_classes.py | T010 config.ts | T014 queryClient.ts

# US1 tests together
T016 test_auth_api.py | T017 authReducer.test.ts | T018 safeNextPath.test.ts | T019 LoginPage.test.tsx | T020 AppLayout.test.tsx

# US1 independent implementation
T021 serializers.py | T024 api/auth.ts | T025 authReducer.ts + safeNextPath.ts | T027 RequireAuth.tsx

# US4 domain modules (all different files)
T041 catalog | T042 inventory | T043 sales | T044 customers | T045 stringing | T046 preorders
```

## Implementation Strategy

1. **MVP**: Phases 1–3. Staff can sign in and out against the real backend, with guarded routes.
   Stop and validate with quickstart scenarios 1–4.
2. **Add US2**: reload and expiry handling, which makes the app safe for daily use.
3. **Add US3**: navigation shell. Later domain features plug their pages into `workAreas`.
4. **Add US4**: typed API modules and the shared query states, ready for the design feature.
5. **Polish**: gates, budget and docs. Then `/code-review` and `/security-review` before merge
   (CLAUDE.md).
