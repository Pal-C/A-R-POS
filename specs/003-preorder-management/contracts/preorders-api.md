# API Contract: Pre-orders

Base path: `/api/preorders/`. Every endpoint requires authentication (`401`/`403` otherwise).

**Conventions**: these match the [stringing contract](../../002-stringing-management/contracts/stringing-api.md).

- Money is sent as a string with 2 decimals.
- Lists are paged: `{count, next, previous, results}`, 20 per page.
- Field errors come back as `400` with field keys; rule violations come back as `400` with
  messages; a missing record is `404`; a missing permission is `403`.

| Method | Path | Purpose | Permission | Spec |
|---|---|---|---|---|
| GET | `/api/preorders/` | Search and filter | authenticated | FR-018–020 |
| POST | `/api/preorders/` | Create | authenticated | FR-001–004 |
| GET | `/api/preorders/{id}/` | Details | authenticated | FR-014 |
| PATCH | `/api/preorders/{id}/` | Edit | authenticated (+`preorders.override_preorder_price` to change price after payment) | FR-005 |
| POST | `/api/preorders/{id}/status/` | Single status change | authenticated | FR-007–008, FR-010 |
| POST | `/api/preorders/{id}/fulfill/` | Fulfill | authenticated | FR-016 |
| POST | `/api/preorders/{id}/cancel/` | Cancel with a reason | `preorders.cancel_preorder` | FR-022–023 |
| GET/POST | `/api/preorders/{id}/payments/` | List, or record a receipt or refund | `sales.record_payment` / `sales.process_refund` for POST | FR-012–015 |
| GET | `/api/preorders/{id}/history/` | Audit history | authenticated | FR-025 |
| GET | `/api/preorders/products/{product_id}/summary/` | Waiting units per status, plus the Ordered pre-orders | authenticated | FR-021, FR-009 |
| POST | `/api/preorders/products/{product_id}/arrivals/` | Mark the product as arrived | authenticated | FR-009 |

There is no `DELETE` route, so a delete request gets `405` (FR-024).

## Pre-order representation

```json
{
  "id": 7,
  "order_number": "PO-2026-000007",
  "customer": {"id": 12, "full_name": "Ana Reyes", "phone_number": "0917 123 4567", "is_active": true},
  "product": {"id": 3, "sku": "RKT-AX100", "name": "Astrox 100ZZ", "is_active": true},
  "quantity": 2,
  "agreed_unit_price": "5000.00",
  "total_amount": "10000.00",
  "amount_paid": "4000.00",
  "balance": "6000.00",
  "refund_due": "0.00",
  "payment_state": "PARTIAL",
  "expected_arrival_date": "2026-12-15",
  "is_overdue": false,
  "notes": "",
  "status": "ORDERED",
  "status_display": "Ordered from Supplier",
  "created_by": {"id": 3, "username": "maria"},
  "created_at": "...", "updated_at": "...",
  "ordered_at": "...", "arrived_at": null,
  "fulfilled_at": null, "fulfilled_by": null,
  "cancelled_at": null, "cancelled_by": null, "cancellation_reason": ""
}
```

List items have the same shape without `notes`.

## GET `/api/preorders/`

| Param | Values | Default |
|---|---|---|
| `search` | Order number, customer name, product name or SKU. Text that looks like a phone number is also matched against the customer's normalized phone. | — |
| `status` | comma list of `PENDING,ORDERED,ARRIVED,FULFILLED,CANCELLED` | all |
| `payment_state` | `UNPAID` \| `PARTIAL` \| `PAID` (never matches cancelled) | all |
| `customer`, `product` | id | — |
| `expected_from`, `expected_to` | `YYYY-MM-DD`, inclusive | — |
| `overdue` | `true` | — |
| `ordering` | `-created_at` \| `created_at` \| `expected_arrival_date` | `-created_at` |

An invalid value returns `400` keyed by the parameter name.

## POST `/api/preorders/`

```json
{"customer": 12, "product": 3, "quantity": 2, "agreed_unit_price": "5000.00", "expected_arrival_date": "2026-12-15", "notes": ""}
```

- `agreed_unit_price` is optional and defaults to the product's selling price.
- `expected_arrival_date` and `notes` are optional.
- Success returns `201` with the detail representation.
- Returns `400` when:
  - a required field is missing;
  - the quantity is below 1 or the price is negative;
  - the date is in the past;
  - the customer is archived or the product is inactive.

## PATCH `/api/preorders/{id}/`

Accepts any of `quantity`, `agreed_unit_price`, `expected_arrival_date` or `notes`.

- Returns `400` when:
  - a field is not editable in the current status;
  - the new total would be below the amount paid;
  - the new date is in the past.
- Returns `403` when the price is changed after a payment without `override_preorder_price`.
- Success returns `200` with the detail representation.

## POST `/api/preorders/{id}/status/`

```json
{"status": "ORDERED", "expected_status": "PENDING"}
```

- `FULFILLED` and `CANCELLED` are rejected with `400`; use `/fulfill/` and `/cancel/` instead.
- An invalid transition returns `400` and names the allowed next statuses.
- If `expected_status` no longer matches, the response is `400`
  `{"detail": "...", "current_status": "..."}`.
- Success returns `200` with the detail representation.

## POST `/api/preorders/{id}/fulfill/`

The body is empty.

- Returns `400` if the pre-order isn't Arrived (`"The goods have not arrived yet."`) or still has a
  balance (`"Balance of 6000.00 must be paid before handover."`).
- Success returns `200` with the detail representation.

## POST `/api/preorders/{id}/cancel/`

```json
{"reason": "Supplier discontinued"}
```

- Returns `400` when the reason is blank or the pre-order is already final.
- Returns `403` without the permission.
- Success returns `200` with the detail representation, where `refund_due` is the amount paid.

## GET / POST `/api/preorders/{id}/payments/`

This works the same as the stringing payments endpoint.

- POST body: `{"payment_type": "RECEIPT"|"REFUND", "amount", "payment_method", "reference_number", "notes", "reason"}`.
  A refund requires `reason`.
- Success returns `201` with `{"payment": {...}, "preorder": {...detail...}}`.
- Returns `400` for a receipt on a Fulfilled or Cancelled pre-order, or for an amount above the
  balance.

## GET `/api/preorders/{id}/history/`

Returns a list ordered from oldest to newest. Entry `type` is one of `CREATED`, `UPDATED`,
`STATUS_CHANGED` (with `from_status` and `to_status`, plus `arrival` for a delivery),
`CANCELLED` (with `reason`), or `PAYMENT`.

## GET `/api/preorders/products/{product_id}/summary/`

```json
{
  "product": {"id": 3, "sku": "RKT-AX100", "name": "Astrox 100ZZ", "is_active": true},
  "waiting": {
    "PENDING": {"orders": 1, "units": 1},
    "ORDERED": {"orders": 2, "units": 3},
    "ARRIVED": {"orders": 0, "units": 0}
  },
  "ordered_preorders": [ {...list item...}, ... ]
}
```

`ordered_preorders` is listed oldest first and is used for selecting orders on arrival. An unknown
product returns `404`.

## POST `/api/preorders/products/{product_id}/arrivals/`

```json
{"received_quantity": 3}
```

or, to choose the orders yourself:

```json
{"received_quantity": 3, "preorder_ids": [7, 9]}
```

Success returns `200`:

```json
{"marked": [ {...list item...} ], "units_used": 3, "units_left": 0}
```

- Returns `400` when:
  - `received_quantity` is below 1;
  - a selected id isn't an Ordered pre-order of this product;
  - the selected quantities together exceed `received_quantity`.
- If no pre-orders are waiting, the response is `200` with `marked: []` and
  `units_left = received_quantity`.
- An unknown product returns `404`.
