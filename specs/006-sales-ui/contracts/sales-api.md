# Contract: Sales API changes

Base path: `/api/sales/`. All endpoints require sign-in (401 otherwise). The conventions are
the same as the earlier contracts.

## Sale representation (changed)

- **List and detail** gain:
  - `sale_date` (`YYYY-MM-DD`, or null for drafts);
  - `items_summary` (string);
  - `payment_methods` (an array of distinct receipt methods, e.g. `["CASH", "GCASH"]`).
- **Detail** gains `events`: an array of `{id, action, changes, reason, performed_by: {id, username, display_name}, created_at}`.
- **Line items**: `unit_cost_price` and `gross_profit` are present only for users with
  `catalog.view_product_cost`.

## GET `/api/sales/` (changed)

- The parameters are unchanged: `status`, `customer_id`, `search`, `page`.
- The order is `sale_date` descending (drafts first, since PostgreSQL sorts nulls first under
  DESC), then `-created_at` and `-id`. This matches the `sale_date_list_idx` index.
- 4 queries.

## POST `/api/sales/checkout/` (new)

```json
{
  "client_transaction_id": "8f6c…",
  "draft_id": null,
  "customer_id": 12,
  "items": [{"product_id": 7, "quantity": 1}, {"product_id": 9, "quantity": 2}],
  "discount_amount": "40.00",
  "sale_date": "2026-11-27",
  "backdate_reason": "",
  "payment": {"payment_method": "CASH", "amount": "650.00", "reference_number": ""}
}
```

- `draft_id`, `customer_id`, `discount_amount`, `sale_date` (defaults to today), `payment` and
  `backdate_reason` are optional.
- Each item may carry `discount_amount` (a line discount, default 0). The editor sends back the
  line discounts saved on a draft, so they are never dropped.
- `client_transaction_id` only counts as a repeat for a finalized sale created by the same
  user. Any other reuse, including a draft's id, returns 400 `{"client_transaction_id": [...]}`.
- An unknown `draft_id` returns 400 `{"draft_id": ["This draft no longer exists."]}`.

| Status | Meaning |
|---|---|
| 201 | Sale detail. The status is COMPLETED when paid in full, PENDING_PAYMENT otherwise. |
| 200 | Sale detail of an existing sale with the same `client_transaction_id` (an idempotent repeat) |
| 400 | Field errors. Also: stock shortage (`{"items": ["Insufficient stock for BG66 Ultimax. Available: 0, requested change: -1."]}`), an inactive product, the discount over the total, the payment over the total, a future `sale_date`, a backdate without a reason, or `draft_id` not a draft |
| 403 | `payment` sent without `sales.record_payment`, or a past `sale_date` without `sales.backdate_sale` |

## PUT `/api/sales/{id}/draft/` (new)

The body is `{customer_id, items, discount_amount}`. It returns 200 with the sale detail, or 400
when the sale is not a draft or a validation fails.

## POST `/api/sales/{id}/customer/` (new)

The body is `{"customer_id": 12, "reason": "Customer asked for a receipt"}`.

| Status | Meaning |
|---|---|
| 200 | Sale detail, with the new event |
| 400 | The sale is a draft or cancelled, the customer is archived or unchanged, or the reason is blank |
| 404 | The sale or customer doesn't exist |

## Required tests

- **Services** (`test_checkout.py`, `test_sale_events.py`):
  - checkout without payment, with partial payment and with full payment;
  - idempotent repeat;
  - checkout from a draft;
  - rollback on a stock shortage (no sale left behind, stock unchanged);
  - an inactive product;
  - the discount or payment over the total;
  - each backdate rule;
  - replacing a draft cart;
  - the customer-change rules and event.
- **API**: 401, 403 and 400 per endpoint, and the success shape. Cost fields are hidden without
  the permission. Query counts for list, detail and checkout.
- **Migrations**: the backfill sets `sale_date` from `finalized_at` in the store time zone, and
  the constraint rejects a finalized sale without a date.
- **Concurrency**: two checkouts competing for the last unit: one succeeds and the other gets
  400, with no negative stock.
