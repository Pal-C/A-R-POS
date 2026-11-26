# API Contract: Customers

Base path: `/api/customers/`. All endpoints require authentication (`401`/`403` otherwise).

**Conventions** (match existing apps):

- Responses are JSON, and money is a string with 2 decimals.
- Lists use the project pagination: `{count, next, previous, results}`, 20 per page, `?page=N`.
- Validation errors return `400` with Django REST Framework's field-keyed shape, e.g.
  `{"full_name": ["This field may not be blank."]}`. Business-rule errors use
  `{"detail": "..."}` or a list of messages.
- Unknown ids return `404`.

| Method | Path | Purpose | Permission | Spec |
|---|---|---|---|---|
| GET | `/api/customers/` | List and search customers | authenticated | FR-006–008 |
| POST | `/api/customers/` | Create a customer | authenticated | FR-001–003 |
| GET | `/api/customers/{id}/` | Details and summary | authenticated | FR-009, FR-013 |
| PATCH | `/api/customers/{id}/` | Edit a customer | authenticated | FR-004 |
| DELETE | `/api/customers/{id}/` | Permanently delete (no history only) | `customers.delete_customer` | FR-019, FR-019a |
| POST | `/api/customers/{id}/archive/` | Archive | `customers.archive_customer` | FR-015–018 |
| POST | `/api/customers/{id}/reactivate/` | Reactivate | `customers.archive_customer` | FR-015 |
| GET | `/api/customers/{id}/sales/` | Sales history | authenticated | FR-010 |
| GET | `/api/customers/{id}/stringing-orders/` | Stringing order history | authenticated | FR-011 |
| GET | `/api/customers/{id}/preorders/` | Pre-order history | authenticated | FR-012 |
| GET | `/api/customers/phone-matches/` | Duplicate phone lookup | authenticated | FR-003 |

---

## GET `/api/customers/`

Query parameters:

| Param | Values | Default | Notes |
|---|---|---|---|
| `search` | text | — | Trimmed. If the text contains only phone characters (digits, spaces, `+ - ( )`), it is matched against the normalized phone; otherwise it is a case-insensitive substring match on name. An empty value returns the unfiltered list. |
| `status` | `active` \| `archived` \| `all` | `active` | Any other value → `400`. |
| `page` | int | 1 | — |

Results are ordered by `full_name`, then `id`. Each list item:

```json
{
  "id": 12,
  "full_name": "Ana Reyes",
  "phone_number": "0917 123 4567",
  "email": "ana@example.com",
  "is_active": true
}
```

## POST `/api/customers/`

Request (only these fields are accepted; anything else is ignored):

```json
{
  "full_name": "Ana Reyes",
  "phone_number": "0917 123 4567",
  "email": "",
  "address": "",
  "notes": ""
}
```

Field rules:

- `full_name`: required and must not be blank once trimmed.
- `phone_number`: optional; may contain only digits, spaces and `+ - ( )`, and at most 30
  characters.
- `email`: optional, but must be a valid address when given.

`201` response: the customer detail (below), plus a `duplicate_phone_customers` list. The list is
empty when no other active customer shares the normalized phone. The customer is created either way.

## GET `/api/customers/{id}/`

```json
{
  "id": 12,
  "full_name": "Ana Reyes",
  "phone_number": "0917 123 4567",
  "email": "ana@example.com",
  "address": "Quezon City",
  "notes": "Prefers 26 lbs",
  "is_active": true,
  "created_at": "2026-11-26T03:10:00Z",
  "updated_at": "2026-11-26T03:10:00Z",
  "last_archive_event": null,
  "summary": {
    "sales_count": 4,
    "stringing_orders_count": 2,
    "preorders_count": 1,
    "total_spent": "8450.00",
    "outstanding_balance": "1200.00",
    "open_preorders_count": 1,
    "unfinished_stringing_orders_count": 0
  }
}
```

- `last_archive_event` is `null`, or
  `{"action": "ARCHIVED", "performed_by": 3, "performed_by_name": "manager", "created_at": "…"}`.
- All fields except the editable five are read-only.

## PATCH `/api/customers/{id}/`

- Accepts any subset of `full_name`, `phone_number`, `email`, `address`, `notes`, with the same
  rules as create.
- `is_active`, timestamps and any other fields are ignored. Archiving uses the dedicated endpoints.
- Archived customers can still be edited.

`200` response: customer detail plus `duplicate_phone_customers` (other active customers only,
excluding this one).

## DELETE `/api/customers/{id}/`

- `204`: deleted, and a `DELETED` audit event was recorded.
- `400`: the customer has history:
  `{"detail": "This customer has sales, stringing orders or pre-orders and cannot be deleted. Archive them instead."}`
- `403`: the user lacks `customers.delete_customer`.

## POST `/api/customers/{id}/archive/`

- Request body: none.
- `200`: customer detail with `is_active: false` and `last_archive_event.action: "ARCHIVED"`.
- `400`: the customer is already archived.
- `403`: the user lacks `customers.archive_customer`.

The confirmation step and open-items warning (FR-015, FR-018) are client-side: before calling
this, the client shows `summary.open_preorders_count`,
`summary.unfinished_stringing_orders_count` and `summary.outstanding_balance` from the detail
response.

## POST `/api/customers/{id}/reactivate/`

- `200`: customer detail with `is_active: true` and `last_archive_event.action: "REACTIVATED"`.
- `400`: the customer is not archived.
- `403`: the user lacks `customers.archive_customer`.

## GET `/api/customers/{id}/sales/`

Paginated, newest first (`finalized_at` desc, then `id` desc). Drafts are excluded.

```json
{
  "id": 42,
  "sale_number": "S20261126-000042",
  "finalized_at": "2026-11-26T05:00:00Z",
  "status": "PENDING_PAYMENT",
  "total_amount": "3350.00",
  "amount_paid": "2000.00",
  "balance": "1350.00"
}
```

`balance` is `"0.00"` for cancelled sales, consistent with `Sale.balance`.

## GET `/api/customers/{id}/stringing-orders/`

Paginated, newest first (`created_at` desc).

```json
{
  "id": 7,
  "order_number": "STR-0007",
  "racket_description": "Yonex Astrox 88D",
  "string_type": "BG66 Ultimax",
  "tension": "26 lbs",
  "status": "READY",
  "total_amount": "450.00",
  "created_at": "…",
  "completed_at": null
}
```

## GET `/api/customers/{id}/preorders/`

Paginated, newest first (`created_at` desc).

```json
{
  "id": 3,
  "order_number": "PO-0003",
  "product": 15,
  "product_name": "Victor Thruster K",
  "product_sku": "RKT-015",
  "quantity": 1,
  "total_amount": "9800.00",
  "expected_arrival_date": "2026-12-10",
  "status": "ORDERED",
  "amount_paid": "5000.00",
  "created_at": "…"
}
```

## GET `/api/customers/phone-matches/?phone=…&exclude_id=…`

- Returns up to 5 **active** customers whose normalized phone equals the normalized `phone`
  (list-item shape, not paginated).
- A blank or non-numeric `phone` returns `[]`.
- `exclude_id` leaves out the customer being edited.

---

## Performance budgets (constitution Principle IV)

| Endpoint | Budget (p95) | Query count |
|---|---|---|
| List / search | ≤ 300 ms at 20k customers | constant (count + page) |
| Detail + summary | ≤ 300 ms at 500+ transactions | constant (≈ 8), asserted in tests |
| History lists | ≤ 300 ms | constant per page, asserted in tests |
| Phone matches | ≤ 200 ms | 1 |
