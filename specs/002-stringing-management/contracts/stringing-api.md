# API Contract: Stringing Orders

Base path: `/api/stringing/`. All endpoints require authentication (`401`/`403` otherwise).

**Conventions** (same as [customers](../../001-customer-management/contracts/customers-api.md)):

- Responses are JSON, and money is a string with 2 decimals. Timestamps are ISO 8601 UTC.
- Lists are paged as `{count, next, previous, results}`, 20 per page, `?page=N`.
- Field errors return `400` as `{"field": ["message"]}`. Business-rule errors return `400` as a
  list of messages or `{"detail": "..."}`.
- Unknown ids return `404`. Missing permissions return `403`.
- **Financial fields** (`direct_cost`, `profit`) are omitted from every response unless the user
  has `stringing.view_stringing_financials`.

| Method | Path | Purpose | Permission | Spec |
|---|---|---|---|---|
| GET | `/api/stringing/orders/` | Search / filter list | authenticated | FR-018–020 |
| POST | `/api/stringing/orders/` | Create order | authenticated | FR-001–006 |
| GET | `/api/stringing/orders/{id}/` | Details | authenticated | FR-016, FR-029 |
| PATCH | `/api/stringing/orders/{id}/` | Edit order | authenticated (+financials to change `direct_cost`) | FR-007–009 |
| POST | `/api/stringing/orders/{id}/status/` | Change status | authenticated | FR-010–013 |
| POST | `/api/stringing/orders/{id}/cancel/` | Cancel with reason | `stringing.cancel_stringingorder` | FR-021–023 |
| GET | `/api/stringing/orders/{id}/payments/` | List payments and refunds | authenticated | FR-016 |
| POST | `/api/stringing/orders/{id}/payments/` | Record receipt or refund | `sales.record_payment` (receipt) / `sales.process_refund` (refund) | FR-014–017 |
| GET | `/api/stringing/orders/{id}/history/` | Audit history | authenticated | FR-025 |
| GET | `/api/stringing/reports/revenue/` | Revenue and profit | `stringing.view_stringing_financials` | FR-026–028 |

`DELETE` on orders is not routed (`405`) — FR-024.

---

## Order representation (detail; list items use the same shape without `notes`)

```json
{
  "id": 41,
  "order_number": "STR-2026-000041",
  "customer": {"id": 12, "full_name": "Ana Reyes", "phone_number": "0917 123 4567", "is_active": true},
  "racket_description": "Yonex Astrox 88D, 4U",
  "string_type": "BG80",
  "tension": "26 lbs",
  "notes": "",
  "service_price": "450.00",
  "discount_amount": "50.00",
  "total_amount": "400.00",
  "direct_cost": "180.00",
  "profit": "220.00",
  "amount_paid": "200.00",
  "balance": "200.00",
  "refund_due": "0.00",
  "payment_state": "PARTIAL",
  "status": "READY",
  "status_display": "Ready for Pickup",
  "created_by": {"id": 3, "username": "maria"},
  "created_at": "2026-11-26T02:10:00Z",
  "updated_at": "2026-11-26T05:00:00Z",
  "ready_at": "2026-11-26T05:00:00Z",
  "completed_at": null,
  "paid_in_full_at": null,
  "cancelled_at": null,
  "cancelled_by": null,
  "cancellation_reason": ""
}
```

`customer` is `null` for walk-in orders.

## GET `/api/stringing/orders/`

| Param | Values | Default |
|---|---|---|
| `search` | text: order number, racket, string, customer name; phone-like text also matches customer phone (normalized) | — |
| `status` | comma list of `RECEIVED,IN_PROGRESS,READY,COMPLETED,CANCELLED` | all |
| `payment_state` | `UNPAID` \| `PARTIAL` \| `PAID` | all |
| `customer` | customer id | — |
| `received_from`, `received_to` | `YYYY-MM-DD`, store-local, inclusive | — |
| `ordering` | `-created_at` \| `created_at` \| `status` | `-created_at` |
| `page` | int | 1 |

An invalid status, payment state, date or ordering value → `400`.

## POST `/api/stringing/orders/`

```json
{
  "customer": 12,
  "racket_description": "Yonex Astrox 88D, 4U",
  "string_type": "BG80",
  "tension": "26 lbs",
  "notes": "",
  "service_price": "450.00",
  "discount_amount": "50.00",
  "direct_cost": "180.00"
}
```

`customer`, `tension`, `notes`, `discount_amount` (default 0) and `direct_cost` (default 0) are
optional. → `201` with the detail representation. Errors: blank racket or string, negative
amounts, discount > price, archived customer (`{"customer": ["This customer is archived ..."]}`).

## PATCH `/api/stringing/orders/{id}/`

Accepts any subset of the POST fields. Errors:

- The order is COMPLETED or CANCELLED → `400`.
- The new total would be below the amount paid → `400`, e.g.
  `["Total cannot be less than the 200.00 already paid."]`.
- `direct_cost` is sent without the financials permission → `403`.

→ `200` detail.

## POST `/api/stringing/orders/{id}/status/`

```json
{"status": "COMPLETED", "expected_status": "READY"}
```

`expected_status` is optional. If it is sent and does not match the current status, → `400`
`{"detail": "...", "current_status": "COMPLETED"}`. Other errors:

- The transition is not allowed → `400`, naming the allowed next statuses.
- COMPLETED with a balance → `400` `["Balance of 200.00 must be paid before pickup."]`.
- `CANCELLED` is not accepted here → `400` (use `/cancel/`).

→ `200` detail.

## POST `/api/stringing/orders/{id}/cancel/`

```json
{"reason": "Customer changed mind"}
```

Errors: blank reason, or the order is COMPLETED or CANCELLED → `400`. → `200` detail, with
`refund_due` set to the net amount paid.

## GET / POST `/api/stringing/orders/{id}/payments/`

The GET is paged, newest first. Each item uses the existing `PaymentSerializer` shape: `id`,
`amount`, `payment_method`, `payment_type`, `status`, `payment_date`, `reference_number`, `notes`,
`received_by`.

POST:

```json
{"payment_type": "RECEIPT", "amount": "200.00", "payment_method": "GCASH", "reference_number": "", "notes": ""}
```

- For `REFUND`, `reason` is required (stored as notes).
- Errors: amount ≤ 0, unknown method, receipt above the balance, receipt on a cancelled order,
  refund above the net paid → `400`.

→ `201`:

```json
{"payment": {...}, "order": {...detail...}}
```

The order is included so the UI can show the new balance and payment state.

## GET `/api/stringing/orders/{id}/history/`

Not paged; one order has a bounded number of events. Results are in time order, oldest first:

```json
[
  {"type": "CREATED", "at": "...", "by": {"id": 3, "username": "maria"}},
  {"type": "STATUS_CHANGED", "at": "...", "by": {...}, "from_status": "RECEIVED", "to_status": "IN_PROGRESS"},
  {"type": "UPDATED", "at": "...", "by": {...}, "changes": {"discount_amount": ["0.00", "50.00"]}},
  {"type": "PAYMENT", "at": "...", "by": {...}, "payment_type": "RECEIPT", "amount": "200.00", "payment_method": "CASH"},
  {"type": "CANCELLED", "at": "...", "by": {...}, "from_status": "READY", "reason": "Customer changed mind"}
]
```

Without the financials permission, `direct_cost` entries are removed from `changes`.

## GET `/api/stringing/reports/revenue/?date_from=2026-11-01&date_to=2026-11-30`

Both dates are required, store-local and inclusive. If `date_from > date_to` → `400`.

```json
{
  "date_from": "2026-11-01",
  "date_to": "2026-11-30",
  "orders_count": 37,
  "gross_service_price": "16650.00",
  "total_discounts": "850.00",
  "net_revenue": "15800.00",
  "total_direct_cost": "6660.00",
  "profit": "9140.00",
  "total_refunds": "100.00",
  "net_revenue_after_refunds": "15700.00",
  "profit_after_refunds": "9040.00",
  "cancelled_count": 2,
  "unpaid_count": 5,
  "outstanding_balance": "1650.00"
}
```

Counted orders are those that are not cancelled and have `paid_in_full_at` in range.
`cancelled_count` counts orders with `cancelled_at` in range. `unpaid_count` and
`outstanding_balance` cover non-cancelled orders received in range that are not paid in full.
`total_refunds` sums refunds made after pickup on completed orders, by refund date; the
`*_after_refunds` fields subtract it. A range with no data returns zeros.

## Change to an existing endpoint

`POST /api/sales/payments/`: receipts now require `sales.record_payment` (`403` otherwise), see R6.
