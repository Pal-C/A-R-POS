  # Quickstart: Frontend Foundation

## Prerequisites

- PostgreSQL running (`docker compose up -d db`), and `backend/.env` filled from `.env.example`.
- Node 22+ and npm.
- A staff user: `cd backend && .venv/bin/python manage.py createsuperuser`. Also create one
  plain staff user without permissions in the admin.

## Run

```bash
# terminal 1
cd backend && .venv/bin/python manage.py runserver 8000
# terminal 2
cd frontend && npm install && npm run dev      # http://localhost:5173, /api proxied to :8000
```

Optional `frontend/.env.local` overrides: `VITE_API_BASE_URL` (default `/api`) and
`VITE_DEV_API_TARGET` (default `http://localhost:8000`).

## Automated checks (all must pass)

```bash
cd backend && .venv/bin/python manage.py test && .venv/bin/ruff check .
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

After `npm run build`, check that the main JS chunk is under 300 KB gzipped. Vite prints the
gzip sizes.

## Manual validation scenarios

| # | Steps | Expected | Spec |
|---|---|---|---|
| 1 | Open `http://localhost:5173/preorders` signed out | Sign-in screen; after signing in you land on `/preorders` | US1-1 |
| 2 | Enter a wrong password | "Invalid username or password"; password cleared | US1-2 |
| 3 | Submit with empty fields | No request in Network tab; fields flagged | US1-3 |
| 4 | Sign out | Sign-in screen with "You have been signed out"; Back button doesn't reveal data | US1-5, SC-006 |
| 5 | Sign in, reload | Still signed in; no flash of sign-in screen | US2-1 |
| 6 | Sign in in two tabs; sign out in tab A; navigate in tab B | Tab B shows sign-in with "Your session has ended", then returns to the same page | US2-2 |
| 7 | Click every nav item; use Back/Forward; open `/nope` | Correct page and URL; "Page not found" with Home link | US3 |
| 8 | Stop the backend; reload | "Cannot reach the server" with Retry; start the backend and click Retry to recover | US4-2 |
| 9 | 11 quick failed logins | "Too many attempts…" message | FR-004 |
| 10 | `curl -i localhost:8000/api/customers/` | `401` with `WWW-Authenticate: Session` | R2 |
