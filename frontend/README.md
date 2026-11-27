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
| `VITE_STORE_TIME_ZONE` | `Asia/Manila` | Time zone used to display dates and times. Match the backend's `STORE_TIME_ZONE`. |

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
│   ├── client.ts   #   axios instance, CSRF, error normalization, 401 → "session ended", sync status
│   ├── errors.ts   #   ApiError + toApiError (display-safe messages)
│   └── auth.ts catalog.ts inventory.ts sales.ts customers.ts stringing.ts preorders.ts
├── auth/           # AuthProvider (session state), useAuth, RequireAuth, RequirePermission
├── styles/         # _tokens.scss (design tokens), main.scss (themed Bootstrap), components/*.scss
├── components/
│   ├── QueryState.tsx
│   └── ui/         # Shared components: Button, fields, SearchBox, FilterMenu, StatusChips, DataTable,
│                   # Pagination, KpiCard, StatusBadge, Card, Banner, Modal, ConfirmCheck, Toast
├── layouts/        # AppLayout (skip link, sidebar, page header), Sidebar, PageHeader, SyncPill, UserBadge
├── lib/            # format.ts (money/dates), money.ts (exact peso math), statusBadges.ts, connection.ts, cx.ts, pageWindow.ts
├── routes/         # workAreas.ts (sidebar + routes + page titles), router.tsx
├── features/       # One folder per area, e.g. features/products (screens, dialogs, hooks, tests)
├── pages/          # Sign-in, Home, Not found, Access denied, placeholders
└── test/           # MSW server, handlers, fixtures, renderApp, axe helper
```

## Conventions

- **State**: the session lives in `AuthProvider`. Server data goes through React Query, using
  each module's `*Keys` factories. Everything else stays in component state. The query cache
  is cleared on sign-out and when a session expires.
- **Errors**: API calls only ever reject with `ApiError`. Show `error.message`, or
  `error.fieldErrors[field]` next to a form field. Never render a raw response.
- **Money** is a `string` (DRF decimal). Never convert it to a float for arithmetic. Use
  `lib/money.ts` (`addMoney`, `multiplyMoney`, `sumMoney`, `compareMoney`) for client-side
  totals. They use integer cents, so ₱0.10 + ₱0.20 is exactly ₱0.30. The server's totals are
  always authoritative.
- **Business dates** (`sale_date`, `YYYY-MM-DD`) are shown with `formatDateOnly`. Never parse
  them as a `Date`, which can shift the day.
- **Sales** (`features/sales`): the cart is a pure reducer (`cartReducer.ts`). Completing a
  sale calls the single, idempotent `POST /api/sales/checkout/` with the cart's
  `client_transaction_id`, so a retry after a network error never creates a second sale.
- **Design tokens**: colors, fonts, radii and shadows live only in `src/styles/_tokens.scss`.
  Components use the Sass variables or the `--ar-*` custom properties. Never hardcode a color.
- **Shared components first**: build screens from `components/ui` (constitution Principle III).
  If a pattern is missing, add a shared component with tests and an axe check.
- **Status badges**: add or change a status in `src/lib/statusBadges.ts` only, then render it
  with `<StatusBadge domain="…" value="…" />`.
- **Page headers**: the title and subtitle come from the route. Set `title` and `subtitle` on
  the work area, or on its `children` entry for sub-pages, in `src/routes/workAreas.ts`. Pages
  don't render their own `<h1>`.
- **Adding a work area**: add an entry to `src/routes/workAreas.ts` with `path`, `navLabel`,
  `title`, `subtitle`, `icon`, `load` and, if needed, `permission` and `children`. The route,
  the sidebar link, the page header and the guards are derived from it. Put the screens in
  `src/features/<area>/`.
- **Feedback**: confirm every money or stock change with `useToast().success(...)`.
  Destructive actions use a `Modal`, a required reason and a `ConfirmCheck`.
- **Adding an endpoint**: add a typed function to the matching `src/api/<domain>.ts`, mirroring
  the backend serializer. Also add a case to `src/api/domain.test.ts`.
