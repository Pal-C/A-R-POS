# Ace&Rally POS — Frontend

React 19 + TypeScript (strict) + Vite, served on a single origin with the Django API.
See `specs/004-frontend-foundation/` for the spec, plan, and design decisions.

## Setup

```bash
npm install
cp .env.example .env.local   # optional; defaults work for local development
npm run dev                  # http://localhost:5173, /api proxied to the Django server
```

The backend must be running (`cd ../backend && .venv/bin/python manage.py runserver 8000`).

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `/api` | API base URL used by the browser. Keep it a **same-origin relative path**, because the session cookie and CSRF token depend on it. |
| `VITE_DEV_API_TARGET` | `http://localhost:8000` | Where the dev server proxies `/api` (dev only). |

In production, serve `dist/` and proxy `/api` to Django on the same origin.

## Scripts

| Script | What it does |
|---|---|
| `npm run dev` | Dev server with the API proxy |
| `npm test` | Vitest + Testing Library + MSW (`npm run test:watch` runs it in watch mode) |
| `npm run typecheck` | `tsc -b` (strict) |
| `npm run lint` | ESLint |
| `npm run build` | Typecheck and production build |

## Layout

```text
src/
├── api/            # The only place that talks HTTP
│   ├── client.ts   #   axios instance, CSRF, error normalization, 401 → "session ended"
│   ├── errors.ts   #   ApiError + toApiError (display-safe messages)
│   ├── auth.ts     #   /api/auth/* (csrf, login, logout, me)
│   └── catalog.ts inventory.ts sales.ts customers.ts stringing.ts preorders.ts
├── auth/           # AuthProvider (session state), useAuth, RequireAuth, RequirePermission
├── routes/         # workAreas.ts (route + nav table), router.tsx
├── layouts/        # AppLayout (nav, signed-in user, sign out)
├── components/     # Shared UI (QueryState: loading / empty / error)
├── pages/          # Sign-in, Home, Not found, Access denied, placeholders
└── test/           # MSW server, default handlers, renderApp helper
```

## Conventions

- **State**: the session lives in `AuthProvider`. Server data goes through React Query, using
  each module's `*Keys` factories. Everything else stays in component state. The query cache
  is cleared on sign-out and when a session expires.
- **Errors**: API calls only ever reject with `ApiError`. Show `error.message`, or
  `error.fieldErrors[field]` next to a form field. Never render a raw response.
- **Money** is a `string` (DRF decimal). Never convert it to a float for arithmetic.
- **Adding a work area**: add an entry to `src/routes/workAreas.ts` with its `path`, `label`,
  `load` and, if needed, `permission`. The route, nav link and guards are derived from it.
- **Adding an endpoint**: add a typed function to the matching `src/api/<domain>.ts`, mirroring
  the backend serializer. Also add a case to `src/api/domain.test.ts`.
