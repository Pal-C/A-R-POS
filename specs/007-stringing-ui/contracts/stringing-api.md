# API Contract Changes: Stringing Orders (007)

This document lists only the changes to
[002's stringing contract](../../002-stringing-management/contracts/stringing-api.md). The
conventions are the same: money is a 2-decimal string, field errors are `400 {"field": [...]}`,
and financial fields are hidden without `stringing.view_stringing_financials`.

| Method | Path | Change | Permission |
|---|---|---|---|
| GET | `/api/stringing/orders/` | New fields in each item | authenticated |
| POST | `/api/stringing/orders/` | New fields; optional `deposit` and `client_transaction_id` | authenticated (+`sales.record_payment` for `deposit`) |
| GET | `/api/stringing/orders/{id}/` | New fields | authenticated |
| PATCH | `/api/stringing/orders/{id}/` | New editable fields | authenticated |
| POST | `/api/stringing/orders/{id}/cancel/` | `materials_used` is required | `stringing.cancel_stringingorder` |
| **GET** | **`/api/stringing/orders/status-counts/`** | **New** | authenticated |
| GET | `/api/stringing/reports/revenue/` | New `gross_add_ons`; net revenue includes add-ons | `stringing.view_stringing_financials` |

## Order representation: new fields (list and detail)

```json
{
  "string_color": "White",
  "string_from_store": true,
  "has_stencil": true,
  "stencil_price": "50.00",
  "has_grip": false,
  "grip_price": "0.00",
  "add_ons_total": "50.00",
  "total_amount": "300.00",
  "materials_used": null
}
```

`total_amount` is `service_price + add_ons_total − discount_amount`. `balance`, `refund_due`
and `payment_state` follow from it.

## POST /api/stringing/orders/

```json
{
  "customer": 12,
  "racket_description": "Arcsaber 11",
  "string_type": "BG80",
  "string_color": "White",
  "tension": "27 lbs",
  "notes": "",
  "service_price": "350.00",
  "has_stencil": true,  "stencil_price": "50.00",
  "has_grip": true,     "grip_price": "120.00",
  "string_from_store": true,
  "discount_amount": "100.00",
  "deposit": {"amount": "270.00", "payment_method": "GCASH", "reference_number": ""},
  "client_transaction_id": "7c2e…uuid"
}
```

- **201**: the order detail is returned, with `amount_paid` and `balance` reflecting the deposit.
- **200**: a repeated `client_transaction_id` by the same user. The existing order is returned
  unchanged.
- **400**:
  - field errors, plus `stencil_price`/`grip_price` above 0 when the add-on isn't selected;
  - `discount_amount` above service + add-ons;
  - `deposit.amount` ≤ 0 or above the total;
  - `client_transaction_id` reused by another user.
  - On any error nothing is saved: no order and no payment. Order numbers come from a database
    sequence, so a rolled-back create may leave a gap in the numbering, as already happens
    today.
- **403**: `deposit` sent without `sales.record_payment`.

## PATCH /api/stringing/orders/{id}/

These fields become editable: `string_color`, `string_from_store`, `has_stencil`,
`stencil_price`, `has_grip` and `grip_price`.

- Unselecting an add-on without also sending its price as 0 is a 400 field error. The client
  always sends both.
- Each change is recorded in the UPDATED event.
- A new total below the amount already paid is refused, as before.

## POST /api/stringing/orders/{id}/cancel/

```json
{"reason": "Customer changed mind", "materials_used": false}
```

- `materials_used` is required (a boolean); without it the response is `400 {"materials_used": [...]}`.
- It is stored on the order and in the CANCELLED event (`changes.materials_used`).

## GET /api/stringing/orders/status-counts/

**Query**: the same filters as the list (`search`, `payment_state`, `customer`,
`received_from`, `received_to`). `status` is ignored, and invalid dates give the same 400 as
the list.

**200**:

```json
{"all": 28, "RECEIVED": 5, "IN_PROGRESS": 6, "READY": 3, "COMPLETED": 13, "CANCELLED": 1}
```

The endpoint runs one query.

## Required tests

- **Models**: each new constraint rejects invalid data, and existing rows keep their totals
  after the migration.
- **Services**:
  - create with add-ons and a deposit (amount paid, balance, and a payment row);
  - each deposit rejection rolls back the order;
  - idempotent repeat, and reuse by another user;
  - edit add-ons (the event diff, and the total-below-paid refusal);
  - cancel stores `materials_used` and writes it to the event;
  - a zero total from add-ons and discount is paid in full on create.
- **Selectors**: status counts with a search and with a date range; the revenue report includes
  add-ons.
- **API**:
  - 401, 403 (deposit without permission; cancel without permission) and 400 per changed
    endpoint;
  - the new fields in the response shape;
  - financial fields still hidden;
  - query counts for list, detail, status-counts (1) and create.
- **Concurrency**: two simultaneous creates with the same `client_transaction_id` give one
  order.

## Frontend client (`src/api/stringing.ts`)

- The new fields are added to `StringingOrderListItem` and `StringingOrderWrite`.
- `StringingOrderCreate` = `StringingOrderWrite & {deposit?, client_transaction_id}`.
- `cancel(id, {reason, materials_used})`.
- `statusCounts(params)` uses the key `stringingKeys.counts(params)`.
- `StringingRevenueReport.gross_add_ons`.
