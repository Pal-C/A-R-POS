# Data Model: Pre-order Management

## PreOrder (existing, extended) — `preorders.models`

| Field | Type | Notes |
|---|---|---|
| `order_number` | Char(30), unique | `PO-{year}-{seq:06d}` from `preorder_number_seq` (R1). Not editable. |
| `customer` | FK Customer, `PROTECT` | Required; must be active at creation (`ensure_usable`). Not editable. |
| `product` | FK Product, `PROTECT` | Required; must be active at creation. Not editable. |
| `quantity` | PositiveInteger | ≥ 1. Editable while PENDING/ORDERED. |
| `agreed_unit_price` | Decimal(10,2) | ≥ 0; defaults to `product.selling_price`. Editable while PENDING/ORDERED; after any payment, only with `override_preorder_price`. |
| `expected_arrival_date` | Date, null | Today or later (store-local) when set or changed. Editable until FULFILLED/CANCELLED. |
| `notes` | Text, blank | **New.** |
| `status` | TextChoices | PENDING (default), ORDERED, ARRIVED, FULFILLED, CANCELLED. |
| `created_by` / `created_at` | FK User `PROTECT` / DateTime | Existing. |
| `updated_at` | DateTime, auto_now | **New.** |
| `ordered_at` | DateTime, null | **New.** Set on → ORDERED; cleared on ORDERED → PENDING. |
| `arrived_at` | DateTime, null | **New.** Set on → ARRIVED; cleared on ARRIVED → ORDERED. |
| `fulfilled_at` | DateTime, null | Existing. |
| `fulfilled_by` | FK User, null, `PROTECT` | **New.** |
| `settled_at` | DateTime, null | **New.** Set at fulfillment, or later for legacy fulfilled rows once they are paid in full. Only allowed on FULFILLED rows. |
| `cancelled_at` | DateTime, null | **New.** |
| `cancelled_by` | FK User, null, `PROTECT` | **New.** |
| `cancellation_reason` | Text, blank | **New.** |

**Derived**:

- `total_amount` = quantity × agreed_unit_price.
- `amount_paid` = net paid (posted receipts − refunds).
- `is_settled` = FULFILLED and `settled_at` is set.
- `balance` = total − paid. It is 0 for CANCELLED and settled orders.
- `refund_due` = paid for CANCELLED orders, otherwise 0.
- `payment_state` is PAID for settled orders. Otherwise it is UNPAID (paid = 0 and total > 0),
  PARTIAL (0 < paid < total) or PAID (paid ≥ total).
- `is_overdue` = `expected_arrival_date` < store-local today and status ∈ {PENDING, ORDERED}.

**Constraints (DB)**:

- Existing: quantity > 0, price ≥ 0.
- New `preorder_cancel_fields_consistent`: CANCELLED ⇔ `cancelled_at` and `cancelled_by` are set
  and the reason is not blank.
- New `preorder_fulfilled_fields_consistent`: FULFILLED ⇔ `fulfilled_at` and `fulfilled_by` are
  set.
- New `preorder_settled_only_when_fulfilled`: if `settled_at` is set, the status must be FULFILLED.

**Indexes**: `(status, -created_at)`, `(product, status)`, `(expected_arrival_date)`,
`(-created_at)`.

**Meta.permissions**: `cancel_preorder`, `override_preorder_price` (R7).

### State transitions

```text
PENDING ⇄ ORDERED ⇄ ARRIVED ──fulfill (balance 0)──▶ FULFILLED
   │         │         │
   └─────────┴─────────┴──cancel(reason)──▶ CANCELLED
```

- Moves go one step at a time, forward or back. FULFILLED and CANCELLED are final.
- ORDERED → ARRIVED also happens in bulk through `mark_product_arrived` (R4).
- Receipts are refused on FULFILLED and CANCELLED orders. Refunds are allowed in any status, up to
  the amount paid.

## PreOrderEvent (new) — append-only audit

| Field | Type | Notes |
|---|---|---|
| `preorder` | FK PreOrder, `PROTECT`, related `events` | |
| `event_type` | TextChoices | CREATED, UPDATED, STATUS_CHANGED, CANCELLED |
| `from_status` / `to_status` | Char, blank | |
| `changes` | JSON, default `{}` | UPDATED: `{field: [old, new]}`, with money as strings and dates in ISO format. |
| `extra` | JSON, default `{}` | Arrival batch: `{"arrival": {"received_quantity": n}}`. |
| `reason` | Text, blank | CANCELLED. |
| `performed_by` | FK User, `PROTECT` | |
| `created_at` | DateTime, auto_now_add | |

Index `(preorder, created_at)`.

## Payment (existing) — schema unchanged

`sales.services.record_payment` adds one rule: receipts are refused on FULFILLED pre-orders.

## Validation summary (spec → rule)

| Spec | Rule | Enforced in |
|---|---|---|
| FR-001 | quantity ≥ 1; price ≥ 0; arrival date today or later | serializer + service + DB checks |
| FR-002 | Unique number, never reused | sequence + unique |
| FR-003 | Active customer and product at creation | service |
| FR-005 | Editable fields by status; total ≥ paid; price override permission after payment | service (row lock) |
| FR-008 | Allowed transitions only | service table |
| FR-009 | Arrival: ORDERED only, quantities fit, all or nothing | service (locks) |
| FR-013 | Receipt ≤ balance | `record_payment` |
| FR-016 | Fulfill only when ARRIVED and balance 0 | service (row lock) |
| FR-017 | No stock change | no inventory calls (test asserts no `InventoryMovement` rows) |
| FR-022 | Cancel needs a reason, the permission, and a non-final status | service + view + DB constraint |
| FR-024 | No delete | no endpoint; admin read-only |
