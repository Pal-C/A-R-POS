# Data Model: Frontend Foundation

No database changes. Django settings change (session lifetime and auth classes), and the
existing `accounts.User` model is read. The entities below are **client-side types** and
**API payloads**.

## CurrentUser

Returned by `GET /api/auth/me/` and `POST /api/auth/login/`.

| Field | Type | Notes |
|---|---|---|
| `id` | number | |
| `username` | string | |
| `first_name` | string | may be empty |
| `last_name` | string | may be empty |
| `display_name` | string | `get_full_name()` or falls back to `username` |
| `is_superuser` | boolean | superusers pass every client permission check |
| `permissions` | string[] | `"app_label.codename"`, sorted; from `get_all_permissions()` |

Client helper: `hasPermission(user, perm)` returns `user.is_superuser || user.permissions.includes(perm)`.

## Session (AuthContext state)

| Field | Type | Notes |
|---|---|---|
| `status` | `'checking' \| 'authenticated' \| 'anonymous' \| 'unreachable'` | initial state is `checking` |
| `user` | `CurrentUser \| null` | non-null only when `authenticated` |
| `endReason` | `'signed_out' \| 'expired' \| null` | drives the message on the sign-in screen |
| `checkError` | string \| null | display-safe reason the session check failed (network vs server error) |

**Transitions**

```text
checking      --me 200-------------------> authenticated
checking      --me 401-------------------> anonymous (endReason=null)
checking      --network / server error---> unreachable(checkError) --retry--> checking
anonymous     --login 200----------------> authenticated (endReason=null)
authenticated --logout (any outcome)-----> anonymous (endReason=signed_out) + clear cache
authenticated --any request 401----------> anonymous (endReason=expired)    + clear cache
authenticated --focus: me is another user-> authenticated (new user)          + clear cache
authenticated --focus: me 401------------> anonymous (endReason=expired)    + clear cache
```

## ApiError

All client failures are normalized to this shape. The client never throws an axios error
to screens.

| Field | Type | Notes |
|---|---|---|
| `kind` | `'validation' \| 'unauthenticated' \| 'forbidden' \| 'not_found' \| 'conflict' \| 'rate_limited' \| 'network' \| 'unexpected'` | |
| `status` | number \| null | null for network errors |
| `message` | string | human-readable, safe to show |
| `fieldErrors` | `Record<string, string[]>` | from DRF field keys; empty unless `validation` |
| `nonFieldErrors` | string[] | DRF `non_field_errors` / `detail` |

**Mapping**

| Response | kind | message |
|---|---|---|
| no response / timeout | `network` | "Cannot reach the server. Check the connection and try again." |
| 400 | `validation` | first non-field error, else "Please correct the highlighted fields." |
| 401 | `unauthenticated` | "Your session has ended. Please sign in again." |
| 403 | `forbidden` | "You don't have permission to do that." |
| 404 | `not_found` | "Not found." |
| 409 | `conflict` | server `detail` if string, else "This record changed. Reload and try again." |
| 429 | `rate_limited` | "Too many attempts. Try again in N seconds." (from `Retry-After`) |
| 5xx / other | `unexpected` | "Something went wrong. Please try again." (details only to `console.error`) |

Nested DRF errors (for example `items: [{quantity: [...]}]`) are flattened to dotted keys
(`items.0.quantity`).

## Paginated<T>

This mirrors DRF `PageNumberPagination`.

| Field | Type |
|---|---|
| `count` | number |
| `next` | string \| null |
| `previous` | string \| null |
| `results` | T[] |

## WorkArea (route table entry)

| Field | Type | Notes |
|---|---|---|
| `path` | string | e.g. `/preorders` |
| `label` | string | navigation text, using constitution terminology |
| `permission` | string \| undefined | if set, the area is hidden in the navigation and guarded |
| `lazy` | `() => Promise<{Component}>` | code-split page |

The initial areas are Home `/`, Sales `/sales`, Products `/products`, Inventory `/inventory`,
Customers `/customers`, Stringing Orders `/stringing`, and Pre-orders `/preorders`. None require
a permission today, because every list endpoint only needs authentication. The `permission`
field exists so that later features can gate areas.

## Domain types (`src/api/*.ts`)

These are hand-written mirrors of the existing serializers (see research R8): `Product`,
`InventoryMovement`, `Sale`, `SaleItem`, `Payment`, `Customer`, `StringingOrder`, `PreOrder`,
and the event and history types. The rules are:

- Money and decimal quantities are `string` (alias `Money`).
- Datetimes are ISO `string`.
- Status fields are string-literal unions that match the backend `TextChoices` values.
