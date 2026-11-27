# Contract: Auth API (`/api/auth/`)

All responses are JSON unless the status is 204. Session cookie: `sessionid` (HttpOnly,
SameSite=Lax). CSRF cookie: `csrftoken`; unsafe methods must send `X-CSRFToken`.

## Global change: unauthenticated status

Every endpoint in the API that requires authentication now returns **401** with
`WWW-Authenticate: Session` when called without a valid session. Previously it returned 403.
**403** now means only "authenticated, but not permitted".

---

## GET `/api/auth/csrf/`

- Auth: none.
- Effect: sets the `csrftoken` cookie.
- **204** with no body.

## POST `/api/auth/login/`

- Auth: none. CSRF: **required**.
- Throttle: scope `login` (default `10/min` per client IP, where `X-Forwarded-For` is trusted
  only `DJANGO_NUM_PROXIES` hops back) and scope `login_username` (default `10/min` per
  normalized username).
- Request:

```json
{ "username": "maria", "password": "••••••" }
```

| Status | Body |
|---|---|
| 200 | `CurrentUser` (see below). Sets a new `sessionid`; rotates `csrftoken`. |
| 400 (field missing) | `{"username": ["This field is required."]}` and/or `password` |
| 400 (bad credentials / inactive) | `{"non_field_errors": ["Invalid username or password."]}` |
| 403 (missing/invalid CSRF) | `{"detail": "CSRF Failed: ..."}` |
| 429 | `{"detail": "Request was throttled. Expected available in N seconds."}` + `Retry-After` |

If a session already exists, it is replaced (the previous user is logged out).

## POST `/api/auth/logout/`

- Auth: none required. The endpoint is idempotent, so calling it while signed out still
  returns 204. CSRF: required when a session exists.
- Effect: `django.contrib.auth.logout()` flushes the session.
- **204** with no body.

## GET `/api/auth/me/`

- Auth: required.

| Status | Body |
|---|---|
| 200 | `CurrentUser` |
| 401 | `{"detail": "Authentication credentials were not provided."}` |

### `CurrentUser`

```json
{
  "id": 3,
  "username": "maria",
  "first_name": "Maria",
  "last_name": "Santos",
  "display_name": "Maria Santos",
  "is_superuser": false,
  "permissions": ["preorders.cancel_preorder", "sales.refund_payment"]
}
```

---

## Required tests (`backend/accounts/tests/test_auth_api.py`)

- The CSRF endpoint sets the cookie.
- Login succeeds: it returns `CurrentUser` and later calls to `me` return 200.
- Login with a wrong password, an unknown user, or an inactive user returns the same 400
  message.
- Login with missing fields returns field errors.
- Login without a CSRF token returns 403 when using `APIClient(enforce_csrf_checks=True)`.
- After 10 failed logins the next attempt returns 429.
- Spoofed `X-Forwarded-For` values don't reset the per-IP limit. With `NUM_PROXIES=1`, clients
  behind the proxy are limited separately. One username is limited across addresses, ignoring
  case and whitespace (`test_login_hardening.py`).
- Behind an HTTPS proxy, login succeeds with `SECURE_PROXY_SSL_HEADER` or `CSRF_TRUSTED_ORIGINS`
  and is rejected without them.
- Logout ends the session: `me` then returns 401. Logout while signed out returns 204.
- `me` returns 401 when anonymous. `permissions` reflects group and user permissions.
- Anonymous requests to an existing protected endpoint (for example `customer-list-create`)
  return exactly 401.
- An authenticated user without permission hitting a permission-gated action gets exactly 403.
