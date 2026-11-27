# Implementation Plan: Frontend Foundation

**Branch**: `004-frontend-foundation` | **Date**: 2026-11-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-frontend-foundation/spec.md`

## Summary

This feature replaces the Vite starter in `frontend/` with an application shell that staff can
sign in to. It has six parts:

- **Routing**: a central route table with guarded layout routes, lazy-loaded placeholder pages
  for each work area, plus Not Found and Access Denied screens.
- **API client**: one axios instance. It normalizes every failure into a typed `ApiError` and
  sends a single "session ended" signal on 401. Typed modules cover every existing backend area.
- **Auth and session**: an `AuthProvider` that checks the session on load, signs in and out,
  and returns staff to the page they were on after re-signing in.
- **Global state**: limited to the session context and a React Query cache, which is cleared on
  sign-out.
- **Backend**: `/api/auth/` endpoints (csrf, login, logout, me) and a login throttle. An
  authentication-class fix makes "not signed in" return 401 instead of 403. Sessions become
  sliding with an 8-hour lifetime.
- **Visual design** is out of scope. Pages use plain Bootstrap defaults.

**Technical approach**: same-origin cookie sessions with CSRF ([R1](research.md#r1-authentication-mechanism-fr-001-fr-005-fr-006),
[R4](research.md#r4-dev-and-prod-origin-topology-fr-017)). In development, a Vite proxy handles
this. Error handling and the 401 signal live in the client
([R8](research.md#r8-api-client-design-fr-014fr-016)). State is limited to context + React Query
([R7](research.md#r7-global-state-fr-018fr-020)).

## Technical Context

**Language/Version**: TypeScript ~6.0 (strict), React 19.3, Vite 8.3. Backend: Python 3.15,
Django 6.1, DRF 3.18.

**Primary Dependencies**:

- Existing: react, react-dom, axios, bootstrap.
- **New runtime**: `react-router` ^8.5 and `@tanstack/react-query` ^5.108.
- **New dev**: `vitest` ^5.1, `jsdom` ^31, `@testing-library/react` ^16.3,
  `@testing-library/user-event` ^14.6, `@testing-library/jest-dom` ^8, `msw` ^3.0.
- **Backend**: no new dependencies.

**Storage**: N/A on the frontend. There is no browser storage of credentials or user data. The
session is stored server-side in the existing Django session table.

**Testing**: Vitest + Testing Library + MSW (frontend). Django `APITestCase` (backend).

**Target Platform**: current Chrome/Edge/Firefox on store machines. The backend runs on
Linux/macOS.

**Project Type**: web application. This feature is mainly frontend, with a small backend auth
addition.

**Performance Goals**:

- App shell interactive in ≤ 2 s.
- Main JS ≤ 300 KB gzipped (about 110 KB is expected,
  [R10](research.md#r10-bundle-budget-principle-iv)).
- Session check on load: one `me` request plus one `csrf` request, in parallel.
- **Checkout-path impact** (Principle IV): `SESSION_SAVE_EVERY_REQUEST` adds one session-row
  UPDATE per authenticated request. That is about 1 ms on PostgreSQL, well within the 200 and
  500 ms budgets. No other checkout code changes.

**Constraints**:

- No tokens or user data in localStorage or sessionStorage.
- Same-origin API.
- Every redirect target is validated.
- Money is kept as a string end to end.

**Scale/Scope**:

- About 10 concurrent staff.
- 9 routes and 4 new endpoints.
- 6 domain API modules covering about 45 existing endpoints.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How this plan complies |
|---|---|---|
| **I. Layering** | ✅ | Backend auth views are thin. Credential checks use Django's `authenticate`/`login`/`logout`. Serialization lives in `accounts/serializers.py`. No domain rules are added. On the frontend, HTTP lives only in `src/api/`, and screens call typed functions. |
| I. Transactions | ✅ N/A | No multi-row writes. Django handles session writes. |
| I. Explicit state | ✅ | The session status is a string-literal union with a reducer, and transitions are listed in data-model.md. Domain statuses are typed as unions that mirror `TextChoices`. |
| I. Static checks | ✅ | `tsc -b` with `"strict": true` (added to tsconfig), `eslint` with zero errors, and `ruff`. No `any` without a comment. |
| I. Size / dead code | ✅ | The starter's `App.css`, `assets/` and demo `App.tsx` are removed. Each API module stays under 500 lines, and sales is split if needed. |
| **II. Testing** | ✅ | Backend: every auth endpoint is tested for anonymous access, validation, success shape, CSRF, throttle and the 401/403 split. Frontend: unit tests for `toApiError` (every mapping row), `safeNextPath`, the auth reducer, the client 401 debounce and the error flattener, plus integration tests (MSW) for the sign-in flow, the reload session check, expiry redirect-and-return, sign-out cache clearing, route guards, not-found and unreachable states. |
| **III. UX consistency** | ✅ (foundation) | The single `ApiError` gives every screen the same messages and field-keyed errors. Loading, error, empty and success states are defined for the session check and sign-in. Terminology matches the constitution (Sales, Products, Inventory, Customers, Stringing Orders, Pre-orders). The sign-in form is keyboard-operable with labelled fields. The shared component library is deferred to the design feature (see Complexity Tracking). |
| **IV. Performance** | ✅ | Lazy routes, the bundle budget is checked in quickstart, React Query dedupes requests, and the checkout impact is stated above. |
| **Append-only / money / DB constraints / migrations** | ✅ N/A | No models or migrations. Money is typed as `string` on the client. |
| **Security** | ✅ | HttpOnly session cookie. CSRF on login (login-CSRF), logout and all unsafe methods. The login throttle and generic failure message prevent account enumeration. Basic auth is removed. Redirects are validated against open redirects. New settings come from env vars (`DJANGO_SESSION_AGE`, `DJANGO_SECURE_COOKIES`, `DJANGO_LOGIN_THROTTLE_RATE`). The client permission checks are UI-only; the server stays authoritative. |
| **New dependencies justified** | ✅ | react-router (routing, R6), react-query (server state, R7), and test tooling (R9). Alternatives are recorded in research. |

**Gate result**: PASS before research, and PASS again after design.

## Project Structure

### Documentation (this feature)

```text
specs/004-frontend-foundation/
├── plan.md
├── research.md            # R1–R10
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── auth-api.md
│   └── frontend-modules.md
├── checklists/requirements.md
└── tasks.md               # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── config/
│   ├── settings.py              # auth classes, session age/sliding, cookie flags, login throttle
│   └── urls.py                  # + path("api/auth/", include("accounts.urls"))
└── accounts/
    ├── authentication.py        # NEW: SessionAuthentication → 401 + WWW-Authenticate: Session
    ├── serializers.py           # NEW: LoginSerializer, CurrentUserSerializer
    ├── views.py                 # NEW: CsrfView, LoginView, LogoutView, MeView
    ├── urls.py                  # NEW
    ├── tests.py                 # REMOVED (empty)
    └── tests/                   # NEW: __init__.py, test_auth_api.py

frontend/
├── .env.example                 # NEW: VITE_API_BASE_URL, VITE_DEV_API_TARGET
├── vite.config.ts               # /api proxy + vitest config
├── tsconfig.app.json            # "strict": true; vitest/jest-dom types
├── package.json                 # deps + scripts: test, typecheck
├── index.html                   # title "Ace&Rally POS"
└── src/
    ├── main.tsx                 # QueryClientProvider > AuthProvider > RouterProvider
    ├── config.ts
    ├── api/
    │   ├── client.ts            # axios instance, interceptors, typed helpers, 401 handler
    │   ├── errors.ts            # ApiError, toApiError, flattenFieldErrors
    │   ├── auth.ts
    │   ├── catalog.ts  inventory.ts  sales.ts  customers.ts  stringing.ts  preorders.ts
    │   └── queryClient.ts       # QueryClient factory (retry rules: no retry on 4xx)
    ├── auth/
    │   ├── AuthProvider.tsx     # context + reducer; registers 401 handler; clears cache
    │   ├── authReducer.ts
    │   ├── useAuth.ts
    │   ├── RequireAuth.tsx  RequirePermission.tsx
    │   └── safeNextPath.ts
    ├── routes/
    │   ├── workAreas.ts         # route table (path, label, permission?, lazy)
    │   └── router.tsx
    ├── layouts/AppLayout.tsx    # nav (from workAreas, permission-filtered), user name, Sign out
    ├── pages/
    │   ├── LoginPage.tsx  HomePage.tsx  NotFoundPage.tsx  AccessDeniedPage.tsx
    │   ├── ServerUnreachablePage.tsx  SessionCheckingPage.tsx
    │   └── placeholders/WorkAreaPlaceholder.tsx   # one generic page used by every area
    └── test/
        ├── setup.ts             # jest-dom, msw server lifecycle, cache reset
        ├── server.ts  handlers.ts
        └── renderApp.tsx        # render with fresh QueryClient + memory router
    (tests co-located as *.test.ts(x))
```

Removed from `frontend/src`: `App.tsx`, `App.css`, `assets/`. `index.css` is reduced to a
minimal reset.

**Structure Decision**: web application. The frontend code lives in `frontend/src`, organized by
concern (api, auth, routes, layouts, pages). Backend changes are confined to `accounts` and
`config`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Principle III's shared Bootstrap component library is not built in this feature | The user explicitly deferred design to the next feature | Building components now would pre-empt design decisions the user still wants to discuss |
| Hand-written domain types can drift from the serializers | No schema generator is in place yet (R8) | `drf-spectacular` would need `@extend_schema` on most views. Drift is mitigated by keeping each module next to its contract doc and checking it at review |
